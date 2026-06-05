package com.exem.inspector.screen.config;

import java.math.BigDecimal;
import java.sql.Date;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.Time;
import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import javax.sql.DataSource;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.ResultSetExtractor;
import org.springframework.stereotype.Service;

import com.exem.inspector.common.db.DbType;
import com.exem.inspector.common.db.RepositoryConfig;
import com.exem.inspector.config.ServiceConfig;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * Config Dump 서비스 — 원본 config_dump.py 의 api_config_dump 와 1:1 동등.
 *
 * <p>선택한 메뉴(들)에 속한 tables + sequences 를 SELECT *  결과로 dump 한 뒤
 * dump_info / tables(columns, rows, count) / sequences 구조로 JSON 직렬화하고
 * 동일 구조를 기반으로 SQL 텍스트도 함께 생성한다(원본 _generate_sql 인라인).
 *
 * <p>repository DataSource 가 미설정이면 빈 dump 를 반환한다(skipped 누적).
 */
@Service
public class ConfigDumpService {

    private static final Logger log = LoggerFactory.getLogger(ConfigDumpService.class);
    private static final DateTimeFormatter TS_FILE = DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss");
    private static final DateTimeFormatter TS_HUMAN = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final String VERSION = "1.0";

    private final ObjectProvider<DataSource> dataSourceProvider;
    private final ServiceConfig serviceConfig;
    private final ObjectMapper jsonMapper = new ObjectMapper();

    public ConfigDumpService(ObjectProvider<DataSource> dataSourceProvider,
                              ServiceConfig serviceConfig) {
        this.dataSourceProvider = dataSourceProvider;
        this.serviceConfig = serviceConfig;
    }

    /** 메뉴 정의 노출 — 원본 MENU_DEFS 5개. */
    public Collection<ConfigDumpMenu> menus() {
        return ConfigDumpMenu.defaults().values();
    }

    /**
     * 선택한 메뉴 키들에 대해 tables + sequences 를 dump.
     * 알 수 없는 키는 무시. 빈 리스트면 모든 메뉴 dump (원본 동일).
     */
    public ConfigDumpPayload dump(List<String> menuKeys) {
        Map<String, ConfigDumpMenu> all = ConfigDumpMenu.defaults();
        List<ConfigDumpMenu> selected = new ArrayList<>();
        if (menuKeys == null || menuKeys.isEmpty()) {
            selected.addAll(all.values());
        } else {
            for (String k : menuKeys) {
                ConfigDumpMenu m = all.get(k);
                if (m != null) selected.add(m);
            }
        }

        RepositoryConfig repo = repositoryConfigSafe();
        String dbTypeRaw = repo == null ? "" : repo.dbType();
        boolean isPg = isPostgres(dbTypeRaw);
        String dbTypeKey = isPg ? "pg" : "oracle";

        // ── 메뉴별 테이블/시퀀스 평탄화(중복 제거, 순서 보존) ──────────────
        List<String> selectedKeys = new ArrayList<>();
        List<String> selectedLabels = new ArrayList<>();
        List<String> allTables = new ArrayList<>();
        List<String> allSeqs = new ArrayList<>();
        java.util.Set<String> seenT = new java.util.LinkedHashSet<>();
        java.util.Set<String> seenS = new java.util.LinkedHashSet<>();
        for (ConfigDumpMenu m : selected) {
            selectedKeys.add(m.getKey());
            selectedLabels.add(m.getLabel());
            for (String t : m.getTables()) {
                if (seenT.add(t)) allTables.add(t);
            }
            for (String s : m.getSequences()) {
                if (seenS.add(s)) allSeqs.add(s);
            }
        }

        Map<String, DumpTable> tableDumps = new LinkedHashMap<>();
        Map<String, Object> sequenceValues = new LinkedHashMap<>();
        List<String> skipped = new ArrayList<>();
        int totalRows = 0;

        DataSource ds = dataSourceProvider.getIfAvailable();
        if (ds != null) {
            JdbcTemplate jdbc = new JdbcTemplate(ds);
            for (String table : allTables) {
                DumpTable dt = dumpTable(jdbc, table, isPg);
                if (dt == null) {
                    skipped.add(table);
                } else {
                    tableDumps.put(table, dt);
                    totalRows += dt.getCount();
                }
            }
            for (String seq : allSeqs) {
                Long v = getSeqValue(jdbc, seq, isPg);
                sequenceValues.put(seq, v == null ? 0L : v);
            }
        }

        String sourceDb = "";
        if (repo != null) {
            sourceDb = repo.ip() + ":" + repo.port() + "/" + repo.sid() + " (" + dbTypeRaw + ")";
        }

        DumpInfo dumpInfo = new DumpInfo(
                LocalDateTime.now().format(TS_HUMAN),
                sourceDb,
                dbTypeKey,
                selectedKeys,
                selectedLabels,
                VERSION);
        DumpStats stats = new DumpStats(tableDumps.size(), totalRows, skipped);
        String filenameBase = "config_dump_" + LocalDateTime.now().format(TS_FILE);

        String jsonContent = serializeDumpData(dumpInfo, tableDumps, sequenceValues);
        String sqlContent = SqlGen.generate(dumpInfo, tableDumps, sequenceValues, isPg);

        return new ConfigDumpPayload(stats, dumpInfo, tableDumps, sequenceValues,
                jsonContent, sqlContent, filenameBase, dbTypeRaw);
    }

    // ── 내부 유틸 ───────────────────────────────────────────────────────

    private RepositoryConfig repositoryConfigSafe() {
        try {
            return serviceConfig.repository();
        } catch (RuntimeException e) {
            return null;
        }
    }

    static boolean isPostgres(String dbType) {
        return dbType != null && dbType.toLowerCase().contains("postgres");
    }

    /** Oracle 이면 식별자 대문자, PG 면 public 스키마 한정자 — 원본 _dump_table 1:1. */
    private DumpTable dumpTable(JdbcTemplate jdbc, String table, boolean isPg) {
        try {
            if (!isPg) {
                // 원본은 NLS_DATE_FORMAT 세션 설정 후 SELECT — 안전을 위해 적용 시도(권한 부족이면 무시).
                try {
                    jdbc.execute("ALTER SESSION SET NLS_DATE_FORMAT='YYYY-MM-DD HH24:MI:SS'");
                } catch (RuntimeException ignore) {
                    // ignore
                }
            }
            String sql = isPg
                    ? "SELECT * FROM public." + table
                    : "SELECT * FROM " + table.toUpperCase();
            return jdbc.query(sql, (ResultSetExtractor<DumpTable>) ConfigDumpService::readResultAsDumpTable);
        } catch (RuntimeException e) {
            log.debug("table dump skip: {} ({})", table, e.getMessage());
            return null;
        }
    }

    private static DumpTable readResultAsDumpTable(ResultSet rs) throws java.sql.SQLException {
        ResultSetMetaData md = rs.getMetaData();
        int n = md.getColumnCount();
        List<String> cols = new ArrayList<>(n);
        for (int i = 1; i <= n; i++) cols.add(md.getColumnLabel(i).toLowerCase());
        List<List<Object>> rows = new ArrayList<>();
        while (rs.next()) {
            List<Object> row = new ArrayList<>(n);
            for (int i = 1; i <= n; i++) row.add(safeValue(rs.getObject(i)));
            rows.add(row);
        }
        return new DumpTable(cols, rows, rows.size());
    }

    /** 원본 _json_safe 1:1 — Timestamp/Date/Decimal/byte[] 처리. */
    static Object safeValue(Object v) {
        if (v == null) return null;
        if (v instanceof Boolean) return v;
        if (v instanceof Number) {
            if (v instanceof BigDecimal) {
                BigDecimal bd = (BigDecimal) v;
                if (bd.scale() <= 0) return bd.longValueExact();
                return bd.doubleValue();
            }
            return v;
        }
        if (v instanceof Timestamp) return ((Timestamp) v).toLocalDateTime().format(TS_HUMAN);
        if (v instanceof Date) return v.toString();
        if (v instanceof Time) return v.toString();
        if (v instanceof java.util.Date) {
            return TS_HUMAN.format(((java.util.Date) v).toInstant()
                    .atZone(java.time.ZoneId.systemDefault()).toLocalDateTime());
        }
        if (v instanceof byte[]) return new String((byte[]) v, java.nio.charset.StandardCharsets.UTF_8);
        return v.toString();
    }

    private Long getSeqValue(JdbcTemplate jdbc, String seq, boolean isPg) {
        // 원본 _get_seq_value 1:1 — SEQ_TABLE_MAP 의 (table,col) 에 대해 MAX(col) 조회.
        SeqMap m = SeqMap.forSeq(seq);
        if (m == null) return 0L;
        try {
            String sql = isPg
                    ? "SELECT COALESCE(MAX(" + m.col + "),0) FROM public." + m.table
                    : "SELECT NVL(MAX(" + m.col + "),0) FROM " + m.table.toUpperCase();
            return jdbc.queryForObject(sql, Long.class);
        } catch (RuntimeException e) {
            log.debug("seq value skip: {} ({})", seq, e.getMessage());
            return 0L;
        }
    }

    private String serializeDumpData(DumpInfo info, Map<String, DumpTable> tables,
                                     Map<String, Object> sequences) {
        Map<String, Object> root = new LinkedHashMap<>();
        Map<String, Object> dumpInfoMap = new LinkedHashMap<>();
        dumpInfoMap.put("created_at", info.getCreatedAt());
        dumpInfoMap.put("source_db", info.getSourceDb());
        dumpInfoMap.put("db_type", info.getDbType());
        dumpInfoMap.put("menus", info.getMenus());
        dumpInfoMap.put("menu_labels", info.getMenuLabels());
        dumpInfoMap.put("version", info.getVersion());
        root.put("dump_info", dumpInfoMap);

        Map<String, Object> tablesOut = new LinkedHashMap<>();
        for (Map.Entry<String, DumpTable> e : tables.entrySet()) {
            DumpTable t = e.getValue();
            Map<String, Object> tobj = new LinkedHashMap<>();
            tobj.put("columns", t.getColumns());
            tobj.put("rows", t.getRows());
            tobj.put("count", t.getCount());
            tablesOut.put(e.getKey(), tobj);
        }
        root.put("tables", tablesOut);
        root.put("sequences", sequences);

        try {
            return jsonMapper.writerWithDefaultPrettyPrinter().writeValueAsString(root);
        } catch (JsonProcessingException e) {
            log.warn("dump json 직렬화 실패", e);
            return "{}";
        }
    }

    // ── SEQ_TABLE_MAP (원본 1:1) ───────────────────────────────────────

    private static final class SeqMap {
        final String table;
        final String col;
        SeqMap(String table, String col) { this.table = table; this.col = col; }
        static SeqMap forSeq(String seq) {
            if ("apm_db_seq".equals(seq))                return new SeqMap("apm_db_info",           "db_id");
            if ("ora_service_name_seq".equals(seq))      return new SeqMap("ora_service_name",      "service_id");
            if ("apm_alert_user_sql_seq".equals(seq))    return new SeqMap("apm_alert_user_sql",    "id");
            if ("apm_alert_user_script_seq".equals(seq)) return new SeqMap("apm_alert_user_script", "id");
            return null;
        }
    }
}
