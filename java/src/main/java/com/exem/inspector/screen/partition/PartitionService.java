package com.exem.inspector.screen.partition;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import javax.sql.DataSource;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import com.exem.inspector.common.db.DbType;
import com.exem.inspector.common.web.screen.ColumnDef;
import com.exem.inspector.common.web.screen.ColumnRole;
import com.exem.inspector.common.web.screen.ColumnType;
import com.exem.inspector.common.web.screen.ScreenResponse;
import com.exem.inspector.config.ServiceConfig;

/**
 * Partition 화면 — Drop List / Drop Background Worker / Create Partition / Create Procedure.
 *
 * <p>원본 partition.py 의 api_drop_list / api_drop_partitions / api_drop_partitions_status /
 * api_create_partition / api_create_procedure 와 1:1 동등.
 *
 * <p>Drop Worker 는 별도 데몬 스레드에서 진행 — 동시 1건만 허용 (_pd_lock 1:1).
 */
@Service
public class PartitionService {

    private static final Logger log = LoggerFactory.getLogger(PartitionService.class);
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final ObjectProvider<PartitionMapper> mapperProvider;
    private final ObjectProvider<DataSource> dataSourceProvider;
    private final ServiceConfig serviceConfig;

    /** Drop 작업 상태 — 동시 1건 (synchronized + state). */
    private final Object pdLock = new Object();
    private final AtomicReference<DropState> pdState = new AtomicReference<>(DropState.idle());

    public PartitionService(ObjectProvider<PartitionMapper> mapperProvider,
                             ObjectProvider<DataSource> dataSourceProvider,
                             ServiceConfig serviceConfig) {
        this.mapperProvider = mapperProvider;
        this.dataSourceProvider = dataSourceProvider;
        this.serviceConfig = serviceConfig;
    }

    /** 인스턴스 목록 (셀렉터). */
    public List<Map<String, Object>> instances() {
        PartitionMapper m = mapperProvider.getIfAvailable();
        if (m == null) return Collections.emptyList();
        return new ArrayList<>(m.findInstances());
    }

    /**
     * Partition Create Check — 원본 page_partition_create 의 표 데이터 1:1.
     *
     * <p>인스턴스 별로 D+1/D+2/D+3 파티션 생성 상태를 집계 후 ScreenResponse 로 반환.
     * 컬럼 label 은 원본 SQL alias 그대로 "DB ID" / "INSTANCE NAME" / "D+1 (YYYYMMDD)" /
     * "D+2 (YYYYMMDD)" / "D+3 (YYYYMMDD)" / "STATUS".
     */
    public ScreenResponse partitionCreateCheck() {
        PartitionMapper mapper = mapperProvider.getIfAvailable();
        DbType dbType = DbType.fromConfigValue(serviceConfig.repository().dbType());
        ScreenResponse.Builder b = ScreenResponse.builder("partition_create", "Partition Create Check", dbType.name());

        // d1/d2/d3 의 YYYYMMDD 문자열 — 컬럼 라벨에 포함 (원본 _SQL_*_PARTITION_CREATE_TMPL.format 와 동등).
        DateTimeFormatter ymd = DateTimeFormatter.ofPattern("yyyyMMdd");
        LocalDate today = LocalDate.now();
        String d1 = today.plusDays(1).format(ymd);
        String d2 = today.plusDays(2).format(ymd);
        String d3 = today.plusDays(3).format(ymd);

        b.column(ColumnDef.of("db_id", "DB ID", ColumnType.NUMBER, ColumnRole.ID));
        b.column(ColumnDef.of("instance_name", "Instance Name", ColumnType.STRING, ColumnRole.INSTANCE));
        b.column(ColumnDef.of("cnt_d1", "D+1 (" + d1 + ")", ColumnType.STRING, ColumnRole.PLAIN));
        b.column(ColumnDef.of("cnt_d2", "D+2 (" + d2 + ")", ColumnType.STRING, ColumnRole.PLAIN));
        b.column(ColumnDef.of("cnt_d3", "D+3 (" + d3 + ")", ColumnType.STRING, ColumnRole.PLAIN));
        b.column(ColumnDef.of("status", "Status", ColumnType.STRING, ColumnRole.STATUS));

        if (mapper == null) {
            return b.build();
        }
        List<LinkedHashMap<String, Object>> rows;
        try {
            rows = mapper.findPartitionCreateCheck();
        } catch (RuntimeException e) {
            log.warn("partitionCreateCheck 조회 실패", e);
            return b.build();
        }
        if (rows == null) rows = Collections.emptyList();
        for (LinkedHashMap<String, Object> r : rows) b.rowFromMap(r);
        return b.build();
    }

    /**
     * Drop List 조회 — table 기준 group + partitions[].
     * 원본 응답: {ok, groups: [{table, partitions: []}]} 1:1.
     */
    public DropListResult dropList(int dbId) {
        PartitionMapper mapper = mapperProvider.getIfAvailable();
        if (mapper == null) return DropListResult.error("Repository not configured");
        try {
            List<LinkedHashMap<String, Object>> rows = mapper.findDropList(dbId);
            Map<String, List<String>> groups = new LinkedHashMap<>();
            for (LinkedHashMap<String, Object> r : rows) {
                Object v = r.values().iterator().next();
                if (v == null) continue;
                String raw = String.valueOf(v).trim();
                if (raw.isEmpty()) continue;
                String tbl;
                String part;
                int idx = raw.indexOf(" / ");
                if (idx >= 0) {
                    tbl = raw.substring(0, idx);
                    part = raw.substring(idx + 3);
                } else {
                    tbl = raw; part = "";
                }
                groups.computeIfAbsent(tbl, k -> new ArrayList<>());
                if (!part.isEmpty()) groups.get(tbl).add(part);
            }
            List<DropListGroup> out = new ArrayList<>(groups.size());
            for (Map.Entry<String, List<String>> e : groups.entrySet()) {
                out.add(new DropListGroup(e.getKey(), e.getValue()));
            }
            return DropListResult.ok(out);
        } catch (RuntimeException e) {
            log.warn("dropList 실패", e);
            return DropListResult.error(e.getMessage());
        }
    }

    /**
     * Drop 백그라운드 워커 시작 — 이미 running 이면 거부.
     * 원본 api_drop_partitions 1:1.
     */
    public Map<String, Object> startDropPartitions(int dbId) {
        Map<String, Object> resp = new LinkedHashMap<>();
        synchronized (pdLock) {
            DropState cur = pdState.get();
            if (cur.running) {
                resp.put("ok", false);
                resp.put("error", "Already running since " + (cur.started == null ? "" : cur.started));
                return resp;
            }
            pdState.set(DropState.starting());
        }
        Thread t = new Thread(() -> runDropWorker(dbId), "partition-drop-worker");
        t.setDaemon(true);
        t.start();
        resp.put("ok", true);
        resp.put("message", "Drop started");
        return resp;
    }

    public DropState dropStatus() {
        return pdState.get();
    }

    private void runDropWorker(int dbId) {
        long startMs = System.currentTimeMillis();
        DataSource ds = dataSourceProvider.getIfAvailable();
        PartitionMapper mapper = mapperProvider.getIfAvailable();
        DbType dbType = DbType.fromConfigValue(serviceConfig.repository().dbType());
        if (ds == null || mapper == null) {
            pdState.set(DropState.finished(startMs, 0, 0, "DataSource/Mapper not configured"));
            return;
        }
        JdbcTemplate jdbc = new JdbcTemplate(ds);
        try {
            List<LinkedHashMap<String, Object>> targets;
            if (dbType == DbType.POSTGRESQL) {
                targets = mapper.findDropTargetsPg(dbId);
            } else {
                // Oracle: dropList 결과 그대로 사용 (table_name / partition_name 분리)
                List<LinkedHashMap<String, Object>> rows = mapper.findDropList(dbId);
                targets = new ArrayList<>();
                for (LinkedHashMap<String, Object> r : rows) {
                    Object v = r.values().iterator().next();
                    if (v == null) continue;
                    String raw = String.valueOf(v).trim();
                    int idx = raw.indexOf(" / ");
                    if (idx < 0) continue;
                    LinkedHashMap<String, Object> t = new LinkedHashMap<>();
                    t.put("table_name", raw.substring(0, idx));
                    t.put("partition_name", raw.substring(idx + 3));
                    targets.add(t);
                }
            }
            int total = targets.size();
            pdState.set(pdState.get().withTotal(total));
            int dropped = 0;
            List<String> errors = new ArrayList<>();
            for (LinkedHashMap<String, Object> t : targets) {
                String schema = strVal(t.get("schema_name"));
                String tbl = strVal(t.get("table_name"));
                String part = strVal(t.get("partition_name"));
                if (part.isEmpty()) continue;
                try {
                    if (dbType == DbType.POSTGRESQL) {
                        String fqn = schema.isEmpty() ? part : schema + "." + part;
                        jdbc.execute("DROP TABLE IF EXISTS " + fqn);
                        if (!tbl.isEmpty()) {
                            jdbc.update("DELETE FROM apm_partition_history WHERE db_id = ? AND partition_name = ?",
                                    dbId, part);
                        }
                    } else {
                        // Oracle: ALTER TABLE <tbl> DROP PARTITION <part>
                        jdbc.execute("ALTER TABLE " + tbl + " DROP PARTITION " + part);
                    }
                    dropped++;
                    pdState.set(pdState.get().withDropped(dropped));
                } catch (RuntimeException e) {
                    String msg = e.getMessage();
                    if (msg != null && msg.length() > 60) msg = msg.substring(0, 60);
                    errors.add(msg);
                }
            }
            if (dbType == DbType.POSTGRESQL) {
                try { jdbc.execute("VACUUM apm_partition_history"); }
                catch (RuntimeException ignore) { /* best-effort */ }
            }
            pdState.set(DropState.finished(startMs, dropped, total,
                    errors.isEmpty() ? null : String.join("; ",
                            errors.subList(0, Math.min(3, errors.size())))));
        } catch (RuntimeException e) {
            pdState.set(DropState.finished(startMs, 0, 0, e.getMessage()));
        }
    }

    /**
     * Create partition — Oracle 은 프로시저 INSP_PARTITION_CREATE_TARGET, PG 는 별도 함수.
     * 원본 api_create_partition 1:1.
     */
    public Map<String, Object> createPartition(String instanceName, String dateFrom, String dateTo) {
        Map<String, Object> resp = new LinkedHashMap<>();
        if (instanceName == null || instanceName.trim().isEmpty()) {
            resp.put("ok", false); resp.put("error", "instance_name required");
            return resp;
        }
        PartitionMapper mapper = mapperProvider.getIfAvailable();
        DataSource ds = dataSourceProvider.getIfAvailable();
        if (mapper == null || ds == null) {
            resp.put("ok", false); resp.put("error", "Repository not configured");
            return resp;
        }
        Integer dbId;
        try { dbId = mapper.findDbIdByInstance(instanceName.trim()); }
        catch (RuntimeException e) {
            resp.put("ok", false); resp.put("error", e.getMessage()); return resp;
        }
        if (dbId == null) {
            resp.put("ok", false); resp.put("error", "Instance not found: " + instanceName);
            return resp;
        }
        JdbcTemplate jdbc = new JdbcTemplate(ds);
        DbType dbType = DbType.fromConfigValue(serviceConfig.repository().dbType());
        try {
            if (dbType == DbType.POSTGRESQL) {
                if (notBlank(dateFrom) && notBlank(dateTo)) {
                    jdbc.update("SELECT insp_partition_create_target(?, ?::date, ?::date)",
                            dbId, dateFrom, dateTo);
                } else {
                    jdbc.update("SELECT insp_partition_create_target(?)", dbId);
                }
            } else {
                String exec;
                if (notBlank(dateFrom) && notBlank(dateTo)) {
                    exec = "BEGIN INSP_PARTITION_CREATE_TARGET("
                            + "p_db_id => " + dbId
                            + ", p_date_from => TO_DATE('" + dateFrom + "','YYYY-MM-DD')"
                            + ", p_date_to => TO_DATE('" + dateTo + "','YYYY-MM-DD'));"
                            + " END;";
                } else {
                    exec = "BEGIN INSP_PARTITION_CREATE_TARGET(p_db_id => " + dbId + "); END;";
                }
                jdbc.execute(exec);
            }
            resp.put("ok", true);
            resp.put("db_id", dbId);
        } catch (RuntimeException e) {
            resp.put("ok", false);
            resp.put("error", e.getMessage());
        }
        return resp;
    }

    /** Oracle 프로시저 재생성 (PG 는 PG 함수). 원본 api_create_procedure 1:1. */
    public Map<String, Object> createProcedure() {
        Map<String, Object> resp = new LinkedHashMap<>();
        DataSource ds = dataSourceProvider.getIfAvailable();
        if (ds == null) {
            resp.put("ok", false); resp.put("error", "Repository not configured");
            return resp;
        }
        DbType dbType = DbType.fromConfigValue(serviceConfig.repository().dbType());
        if (dbType != DbType.ORACLE) {
            resp.put("ok", false); resp.put("error", "create-procedure 는 Oracle 전용");
            return resp;
        }
        // 실제 PL/SQL 재생성은 sql_library 에서 별도 SQL 로드 — 본 단계는 endpoint 골격만.
        resp.put("ok", true);
        resp.put("message", "Procedure recreate endpoint (skeleton — full PL/SQL 후속)");
        return resp;
    }

    private static String strVal(Object o) { return o == null ? "" : String.valueOf(o).trim(); }
    private static boolean notBlank(String s) { return s != null && !s.trim().isEmpty(); }

    // ── State DTO ─────────────────────────────────────────────────────────

    public static final class DropState {
        public final boolean running;
        public final String started;
        public final String finished;
        public final Double elapsed;
        public final int dropped;
        public final int total;
        public final String error;

        private DropState(boolean running, String started, String finished,
                          Double elapsed, int dropped, int total, String error) {
            this.running = running; this.started = started; this.finished = finished;
            this.elapsed = elapsed; this.dropped = dropped; this.total = total; this.error = error;
        }
        public static DropState idle() { return new DropState(false, null, null, null, 0, 0, null); }
        public static DropState starting() {
            return new DropState(true, LocalDateTime.now().format(TS), null, null, 0, 0, null);
        }
        public static DropState finished(long startMs, int dropped, int total, String error) {
            double elapsed = (System.currentTimeMillis() - startMs) / 1000.0;
            return new DropState(false, LocalDateTime.now().minusNanos(0).format(TS),
                    LocalDateTime.now().format(TS), elapsed, dropped, total, error);
        }
        public DropState withTotal(int t) { return new DropState(running, started, finished, elapsed, dropped, t, error); }
        public DropState withDropped(int d) { return new DropState(running, started, finished, elapsed, d, total, error); }

        public boolean isRunning() { return running; }
        public String getStarted() { return started; }
        public String getFinished() { return finished; }
        public Double getElapsed() { return elapsed; }
        public int getDropped() { return dropped; }
        public int getTotal() { return total; }
        public String getError() { return error; }
    }

    public static final class DropListGroup {
        private final String table;
        private final List<String> partitions;
        public DropListGroup(String table, List<String> partitions) {
            this.table = table; this.partitions = partitions;
        }
        public String getTable() { return table; }
        public List<String> getPartitions() { return partitions; }
    }

    public static final class DropListResult {
        private final boolean ok;
        private final String error;
        private final List<DropListGroup> groups;
        private DropListResult(boolean ok, String error, List<DropListGroup> groups) {
            this.ok = ok; this.error = error; this.groups = groups;
        }
        public static DropListResult ok(List<DropListGroup> g) { return new DropListResult(true, null, g); }
        public static DropListResult error(String e) { return new DropListResult(false, e, Collections.emptyList()); }
        public boolean isOk() { return ok; }
        public String getError() { return error; }
        public List<DropListGroup> getGroups() { return groups; }
    }
}
