package com.exem.inspector.screen.disk;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import java.util.regex.Pattern;

import javax.sql.DataSource;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import com.exem.inspector.common.db.DbType;
import com.exem.inspector.config.ServiceConfig;

/**
 * Disk 화면(Vacuum/Age + Temp Table) Facade — 원본 pages/disk.py 의
 *
 * <ul>
 *   <li>_vacuum_log_html (VacuumLogReader 위임)</li>
 *   <li>_auto_vacuum_card (auto-vacuum 표) + VACUUM TABLE 백그라운드 워커 (_vt_worker)</li>
 *   <li>_age_card (age 표) + VACUUM FREEZE 백그라운드 워커 (_vf_worker)</li>
 *   <li>page_disk_temp_table 표 + DROP ALL 백그라운드 워커 (_tt_worker)</li>
 * </ul>
 * 와 1:1 동등.
 *
 * <p>3 개 워커는 각각 별도 lock + AtomicReference&lt;State&gt; — 원본 _vf_lock/_vt_lock/_tt_lock 1:1.
 * 동시에 같은 워커 두 번 시작 거부 ("Already running since X").
 *
 * <p>참고: vacuum / age 는 PostgreSQL 전용. temp_table 은 PG/Oracle 모두 지원.
 */
@Service
public class DiskService {

    private static final Logger log = LoggerFactory.getLogger(DiskService.class);
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    /** 안전성 체크 — 영숫자/언더스코어만. 원본 _re.search(r'[^a-zA-Z0-9_]') 부정조건 1:1. */
    private static final Pattern SAFE_IDENT = Pattern.compile("^[a-zA-Z0-9_]+$");

    private final ObjectProvider<DiskMapper> mapperProvider;
    private final ObjectProvider<DataSource> dataSourceProvider;
    private final ServiceConfig serviceConfig;
    private final VacuumLogReader vacuumLogReader;

    // ── 워커 상태 ────────────────────────────────────────────────────
    private final Object vfLock = new Object();
    private final AtomicReference<VacuumFreezeState> vfState =
            new AtomicReference<>(VacuumFreezeState.idle());

    private final Object vtLock = new Object();
    private final AtomicReference<VacuumTableState> vtState =
            new AtomicReference<>(VacuumTableState.idle());

    private final Object ttLock = new Object();
    private final AtomicReference<TempTableDropState> ttState =
            new AtomicReference<>(TempTableDropState.idle());

    public DiskService(ObjectProvider<DiskMapper> mapperProvider,
                       ObjectProvider<DataSource> dataSourceProvider,
                       ServiceConfig serviceConfig,
                       VacuumLogReader vacuumLogReader) {
        this.mapperProvider = mapperProvider;
        this.dataSourceProvider = dataSourceProvider;
        this.serviceConfig = serviceConfig;
        this.vacuumLogReader = vacuumLogReader;
    }

    // ──────────────────────── Cards (SELECT) ────────────────────────

    /** 원본 page_disk_vacuum_age 의 _vacuum_log_html() 부분 — VacuumLogReader 위임. */
    public Map<String, Object> vacuumLog() {
        return vacuumLogReader.toScreenPayload();
    }

    /** 원본 _auto_vacuum_card 의 SELECT 부분 — rows: [{schema, table_name, dead_tuples, vacuum_threshold, last_autovacuum}]. */
    public List<Map<String, Object>> autoVacuumCard() {
        DiskMapper m = mapperProvider.getIfAvailable();
        if (m == null) return Collections.emptyList();
        return liftRows(m.findAutoVacuumTargets());
    }

    /** 원본 _age_card 의 SELECT 부분 — rows: [{dbname, parameter_max_age, max_age, current_txid}]. */
    public List<Map<String, Object>> ageCard() {
        DiskMapper m = mapperProvider.getIfAvailable();
        if (m == null) return Collections.emptyList();
        return liftRows(m.findAge());
    }

    /** 원본 page_disk_temp_table 의 SELECT — rows: [{SCHEMA, TEMP TABLE}]. */
    public List<Map<String, Object>> tempTableList() {
        DiskMapper m = mapperProvider.getIfAvailable();
        if (m == null) return Collections.emptyList();
        return liftRows(m.findTempTables());
    }

    // ──────────────────────── VACUUM FREEZE ─────────────────────────

    /** 원본 api_vacuum_freeze 1:1 — 단일 워커. */
    public Map<String, Object> startVacuumFreeze() {
        Map<String, Object> resp = new LinkedHashMap<>();
        synchronized (vfLock) {
            VacuumFreezeState cur = vfState.get();
            if (cur.running) {
                resp.put("ok", false);
                resp.put("error", "Already running since " + nullSafe(cur.started));
                return resp;
            }
            vfState.set(VacuumFreezeState.starting());
        }
        Thread t = new Thread(this::runVacuumFreezeWorker, "disk-vacuum-freeze-worker");
        t.setDaemon(true);
        t.start();
        resp.put("ok", true);
        resp.put("message", "VACUUM FREEZE started");
        return resp;
    }

    /** 원본 api_vacuum_freeze_status 1:1. */
    public VacuumFreezeState vacuumFreezeStatus() { return vfState.get(); }

    private void runVacuumFreezeWorker() {
        long startMs = System.currentTimeMillis();
        DataSource ds = dataSourceProvider.getIfAvailable();
        if (ds == null) {
            vfState.set(VacuumFreezeState.finished(startMs, "Repository not configured"));
            return;
        }
        try {
            new JdbcTemplate(ds).execute("VACUUM FREEZE");
            vfState.set(VacuumFreezeState.finished(startMs, null));
        } catch (RuntimeException e) {
            log.warn("VACUUM FREEZE 실패", e);
            vfState.set(VacuumFreezeState.finished(startMs, e.getMessage()));
        }
    }

    // ──────────────────────── VACUUM TABLE (per-table) ──────────────

    /** 원본 api_vacuum_table 1:1 — auto-vacuum SQL 의 결과를 vacuum 대상으로 사용. */
    public Map<String, Object> startVacuumTable() {
        Map<String, Object> resp = new LinkedHashMap<>();
        synchronized (vtLock) {
            if (vtState.get().running) {
                resp.put("ok", false);
                resp.put("error", "Already running since " + nullSafe(vtState.get().started));
                return resp;
            }
        }
        DiskMapper mapper = mapperProvider.getIfAvailable();
        if (mapper == null) {
            resp.put("ok", false); resp.put("error", "Repository not configured");
            return resp;
        }
        List<LinkedHashMap<String, Object>> rows;
        try {
            rows = mapper.findAutoVacuumTargets();
        } catch (RuntimeException e) {
            resp.put("ok", false); resp.put("error", truncate(e.getMessage(), 120));
            return resp;
        }
        if (rows == null || rows.isEmpty()) {
            resp.put("ok", false); resp.put("error", "No tables to vacuum");
            return resp;
        }
        List<String[]> tables = extractSchemaTablePairs(rows, /*requireTtPrefix=*/false, /*requireSafe=*/false);
        if (tables.isEmpty()) {
            resp.put("ok", false); resp.put("error", "No valid tables found");
            return resp;
        }
        synchronized (vtLock) {
            vtState.set(VacuumTableState.starting(tables.size()));
        }
        Thread t = new Thread(() -> runVacuumTableWorker(tables), "disk-vacuum-table-worker");
        t.setDaemon(true);
        t.start();
        resp.put("ok", true);
        resp.put("message", "VACUUM TABLE started");
        resp.put("total", tables.size());
        return resp;
    }

    /** 원본 api_vacuum_table_status 1:1. */
    public VacuumTableState vacuumTableStatus() { return vtState.get(); }

    private void runVacuumTableWorker(List<String[]> tables) {
        long startMs = System.currentTimeMillis();
        DataSource ds = dataSourceProvider.getIfAvailable();
        if (ds == null) {
            vtState.set(vtState.get().finishedWithError(startMs, "Repository not configured"));
            return;
        }
        JdbcTemplate jdbc = new JdbcTemplate(ds);
        int done = 0;
        try {
            for (String[] pair : tables) {
                String fq = pair[0] + "." + pair[1];
                vtState.set(vtState.get().withProgress(fq, done));
                jdbc.execute("VACUUM " + fq);
                done++;
            }
            vtState.set(vtState.get().finishedOk(startMs, done));
        } catch (RuntimeException e) {
            log.warn("VACUUM TABLE 실패", e);
            vtState.set(vtState.get().finishedWithError(startMs, e.getMessage()).withDone(done));
        }
    }

    // ──────────────────────── TEMP TABLE DROP ALL ───────────────────

    /** 원본 api_temp_table_drop_all 1:1 — temp_table SQL 결과를 drop 대상으로. */
    public Map<String, Object> startTempTableDropAll() {
        Map<String, Object> resp = new LinkedHashMap<>();
        synchronized (ttLock) {
            if (ttState.get().running) {
                resp.put("ok", false); resp.put("error", "Already running");
                return resp;
            }
        }
        DiskMapper mapper = mapperProvider.getIfAvailable();
        if (mapper == null) {
            resp.put("ok", false); resp.put("error", "Repository not configured");
            return resp;
        }
        List<LinkedHashMap<String, Object>> rows;
        try {
            rows = mapper.findTempTables();
        } catch (RuntimeException e) {
            resp.put("ok", false); resp.put("error", truncate(e.getMessage(), 120));
            return resp;
        }
        if (rows == null || rows.isEmpty()) {
            resp.put("ok", false); resp.put("error", "No tables to drop");
            return resp;
        }
        List<String[]> tables = extractSchemaTablePairs(rows, /*requireTtPrefix=*/true, /*requireSafe=*/true);
        if (tables.isEmpty()) {
            resp.put("ok", false); resp.put("error", "No valid tt% tables");
            return resp;
        }
        synchronized (ttLock) {
            ttState.set(TempTableDropState.starting(tables.size()));
        }
        boolean isPg = DbType.fromConfigValue(serviceConfig.repository().dbType()) == DbType.POSTGRESQL;
        Thread t = new Thread(() -> runTempTableDropWorker(tables, isPg), "disk-temp-drop-worker");
        t.setDaemon(true);
        t.start();
        resp.put("ok", true);
        resp.put("total", tables.size());
        return resp;
    }

    /** 원본 api_temp_table_drop_status 1:1. */
    public TempTableDropState tempTableDropStatus() { return ttState.get(); }

    private void runTempTableDropWorker(List<String[]> tables, boolean isPg) {
        long startMs = System.currentTimeMillis();
        DataSource ds = dataSourceProvider.getIfAvailable();
        if (ds == null) {
            ttState.set(ttState.get().finishedWithError(startMs, "Repository not configured"));
            return;
        }
        JdbcTemplate jdbc = new JdbcTemplate(ds);
        int succeeded = 0, failed = 0;
        List<TempTableDropError> errors = new ArrayList<>();
        try {
            for (String[] pair : tables) {
                String fq = pair[0] + "." + pair[1];
                ttState.set(ttState.get().withProgress(fq, succeeded + failed));
                String stmt = isPg
                        ? "DROP TABLE IF EXISTS " + fq
                        : "DROP TABLE " + fq + " PURGE";
                try {
                    jdbc.execute(stmt);
                    succeeded++;
                } catch (RuntimeException e) {
                    failed++;
                    errors.add(new TempTableDropError(fq, truncate(e.getMessage(), 300)));
                }
            }
            ttState.set(ttState.get().finishedOk(startMs, succeeded, failed, errors));
        } catch (RuntimeException e) {
            log.warn("Temp Table drop 워커 실패", e);
            ttState.set(ttState.get().finishedWithError(startMs, e.getMessage())
                    .withCounts(succeeded, failed, errors));
        }
    }

    // ──────────────────────── 헬퍼 ──────────────────────────────────

    /**
     * 행에서 schema.table pair 추출 — 원본 disk.py 의 idx_schema/idx_table 패턴 1:1.
     * 컬럼명 대소문자 무시, "SCHEMA" 포함이 schema, "TABLE" 포함이고 "SCHEMA" 미포함이 table.
     */
    private static List<String[]> extractSchemaTablePairs(List<LinkedHashMap<String, Object>> rows,
                                                          boolean requireTtPrefix, boolean requireSafe) {
        if (rows == null || rows.isEmpty()) return Collections.emptyList();
        // 헤더 순서 추출 (LinkedHashMap → 첫 행의 key 순서)
        List<String> headers = new ArrayList<>(rows.get(0).keySet());
        int idxSchema = 0;
        int idxTable = 1;
        for (int i = 0; i < headers.size(); i++) {
            String hUpper = headers.get(i).toUpperCase();
            if (hUpper.contains("SCHEMA")) { idxSchema = i; }
        }
        for (int i = 0; i < headers.size(); i++) {
            String hUpper = headers.get(i).toUpperCase();
            if (hUpper.contains("TABLE") && !hUpper.contains("SCHEMA")) { idxTable = i; break; }
        }
        List<String[]> pairs = new ArrayList<>();
        for (LinkedHashMap<String, Object> row : rows) {
            List<String> keys = new ArrayList<>(row.keySet());
            String schema = strAt(row, keys, idxSchema);
            String table = strAt(row, keys, idxTable);
            if (schema.isEmpty() || table.isEmpty()) continue;
            if (requireTtPrefix && !table.toLowerCase().startsWith("tt")) continue;
            if (requireSafe && (!SAFE_IDENT.matcher(schema).matches() || !SAFE_IDENT.matcher(table).matches())) continue;
            pairs.add(new String[]{schema, table});
        }
        return pairs;
    }

    private static String strAt(LinkedHashMap<String, Object> row, List<String> keys, int idx) {
        if (idx < 0 || idx >= keys.size()) return "";
        Object v = row.get(keys.get(idx));
        return v == null ? "" : String.valueOf(v).trim();
    }

    private static List<Map<String, Object>> liftRows(List<LinkedHashMap<String, Object>> rows) {
        if (rows == null) return Collections.emptyList();
        List<Map<String, Object>> out = new ArrayList<>(rows.size());
        for (LinkedHashMap<String, Object> r : rows) out.add(r);
        return out;
    }

    private static String nullSafe(String s) { return s == null ? "" : s; }
    private static String truncate(String s, int max) {
        if (s == null) return null;
        return s.length() > max ? s.substring(0, max) : s;
    }

    // ──────────────────────── State DTOs ────────────────────────────

    /** 원본 _vf_state 1:1. */
    public static final class VacuumFreezeState {
        public final boolean running;
        public final String started;
        public final String finished;
        public final Double elapsed;
        public final String error;

        private VacuumFreezeState(boolean running, String started, String finished, Double elapsed, String error) {
            this.running = running; this.started = started; this.finished = finished;
            this.elapsed = elapsed; this.error = error;
        }
        public static VacuumFreezeState idle() { return new VacuumFreezeState(false, null, null, null, null); }
        public static VacuumFreezeState starting() {
            return new VacuumFreezeState(true, LocalDateTime.now().format(TS), null, null, null);
        }
        public static VacuumFreezeState finished(long startMs, String error) {
            double sec = round1((System.currentTimeMillis() - startMs) / 1000.0);
            return new VacuumFreezeState(false, null, LocalDateTime.now().format(TS), sec, error);
        }
        public boolean isRunning() { return running; }
        public String getStarted() { return started; }
        public String getFinished() { return finished; }
        public Double getElapsed() { return elapsed; }
        public String getError() { return error; }
    }

    /** 원본 _vt_state 1:1. */
    public static final class VacuumTableState {
        public final boolean running;
        public final String started;
        public final String finished;
        public final Double elapsed;
        public final String error;
        public final String current;
        public final int done;
        public final int total;

        private VacuumTableState(boolean running, String started, String finished, Double elapsed,
                                 String error, String current, int done, int total) {
            this.running = running; this.started = started; this.finished = finished;
            this.elapsed = elapsed; this.error = error;
            this.current = current; this.done = done; this.total = total;
        }
        public static VacuumTableState idle() {
            return new VacuumTableState(false, null, null, null, null, null, 0, 0);
        }
        public static VacuumTableState starting(int total) {
            return new VacuumTableState(true, LocalDateTime.now().format(TS), null, null, null, null, 0, total);
        }
        VacuumTableState withProgress(String cur, int done) {
            return new VacuumTableState(running, started, finished, elapsed, error, cur, done, total);
        }
        VacuumTableState withDone(int done) {
            return new VacuumTableState(running, started, finished, elapsed, error, current, done, total);
        }
        VacuumTableState finishedOk(long startMs, int done) {
            double sec = round1((System.currentTimeMillis() - startMs) / 1000.0);
            return new VacuumTableState(false, started, LocalDateTime.now().format(TS), sec, null, null, done, total);
        }
        VacuumTableState finishedWithError(long startMs, String err) {
            double sec = round1((System.currentTimeMillis() - startMs) / 1000.0);
            return new VacuumTableState(false, started, LocalDateTime.now().format(TS), sec, err, null, done, total);
        }
        public boolean isRunning() { return running; }
        public String getStarted() { return started; }
        public String getFinished() { return finished; }
        public Double getElapsed() { return elapsed; }
        public String getError() { return error; }
        public String getCurrent() { return current; }
        public int getDone() { return done; }
        public int getTotal() { return total; }
    }

    /** 원본 _tt_state 1:1. */
    public static final class TempTableDropState {
        public final boolean running;
        public final String started;
        public final String finished;
        public final Double elapsed;
        public final String error;
        public final String current;
        public final int done;
        public final int total;
        public final int succeeded;
        public final int failed;
        public final List<TempTableDropError> errors;

        private TempTableDropState(boolean running, String started, String finished, Double elapsed,
                                   String error, String current, int done, int total,
                                   int succeeded, int failed, List<TempTableDropError> errors) {
            this.running = running; this.started = started; this.finished = finished;
            this.elapsed = elapsed; this.error = error;
            this.current = current; this.done = done; this.total = total;
            this.succeeded = succeeded; this.failed = failed;
            this.errors = errors == null ? Collections.emptyList() : Collections.unmodifiableList(errors);
        }
        public static TempTableDropState idle() {
            return new TempTableDropState(false, null, null, null, null, null, 0, 0, 0, 0, Collections.emptyList());
        }
        public static TempTableDropState starting(int total) {
            return new TempTableDropState(true, LocalDateTime.now().format(TS), null, null, null, null,
                    0, total, 0, 0, Collections.emptyList());
        }
        TempTableDropState withProgress(String cur, int done) {
            return new TempTableDropState(running, started, finished, elapsed, error, cur, done, total,
                    succeeded, failed, errors);
        }
        TempTableDropState finishedOk(long startMs, int okN, int ngN, List<TempTableDropError> errs) {
            double sec = round1((System.currentTimeMillis() - startMs) / 1000.0);
            return new TempTableDropState(false, started, LocalDateTime.now().format(TS), sec, null, null,
                    okN + ngN, total, okN, ngN, errs);
        }
        TempTableDropState finishedWithError(long startMs, String err) {
            double sec = round1((System.currentTimeMillis() - startMs) / 1000.0);
            return new TempTableDropState(false, started, LocalDateTime.now().format(TS), sec, err, null,
                    done, total, succeeded, failed, errors);
        }
        TempTableDropState withCounts(int okN, int ngN, List<TempTableDropError> errs) {
            return new TempTableDropState(running, started, finished, elapsed, error, current,
                    okN + ngN, total, okN, ngN, errs);
        }
        public boolean isRunning() { return running; }
        public String getStarted() { return started; }
        public String getFinished() { return finished; }
        public Double getElapsed() { return elapsed; }
        public String getError() { return error; }
        public String getCurrent() { return current; }
        public int getDone() { return done; }
        public int getTotal() { return total; }
        public int getSucceeded() { return succeeded; }
        public int getFailed() { return failed; }
        public List<TempTableDropError> getErrors() { return errors; }
    }

    /** 원본 _tt_state["errors"] 의 한 entry: {table, error}. */
    public static final class TempTableDropError {
        private final String table;
        private final String error;
        public TempTableDropError(String table, String error) {
            this.table = table; this.error = error;
        }
        public String getTable() { return table; }
        public String getError() { return error; }
    }

    private static double round1(double v) { return Math.round(v * 10.0) / 10.0; }
}
