package com.exem.inspector.screen.config;

import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

import javax.sql.DataSource;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

import com.exem.inspector.common.db.RepositoryConfig;
import com.exem.inspector.config.ServiceConfig;

/**
 * Config Restore 서비스 — 원본 config_dump.py 의 api_config_restore 1:1.
 *
 * <p>업로드된 dump JSON 으로 Repository 를 복원한다.
 * Phase 1: 모든 테이블 DELETE (자식 우선, 역순).
 * Phase 2: 모든 테이블 INSERT (부모 우선, 정순).
 * 단일 트랜잭션 내에서 처리하고 오류 시 rollback.
 *
 * <p>__PATCH_INSP_RESTORE_ORDER__ — ora_app_call_tree_info 가 apm_db_info 보다 먼저
 * INSERT 되어야 한다(원본 주석 참조). apm_db_info 의 트리거가 자동으로 (db_id, 0)
 * 행을 ora_app_call_tree_info 에 삽입하기 때문에 순서를 유지하지 않으면 충돌이 발생한다.
 */
@Service
public class ConfigRestoreService {

    private static final Logger log = LoggerFactory.getLogger(ConfigRestoreService.class);
    private static final Pattern PAT_TS   = Pattern.compile("^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}$");
    private static final Pattern PAT_DATE = Pattern.compile("^\\d{4}-\\d{2}-\\d{2}$");
    private static final DateTimeFormatter ISO_TS   = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final DateTimeFormatter ISO_DATE = DateTimeFormatter.ofPattern("yyyy-MM-dd");

    private final ObjectProvider<DataSource> dataSourceProvider;
    private final ServiceConfig serviceConfig;

    public ConfigRestoreService(ObjectProvider<DataSource> dataSourceProvider,
                                 ServiceConfig serviceConfig) {
        this.dataSourceProvider = dataSourceProvider;
        this.serviceConfig = serviceConfig;
    }

    /** dump JSON Map 을 받아 restore 수행. */
    public RestoreResult restore(Map<String, Object> dumpData) {
        if (dumpData == null || !dumpData.containsKey("tables") || !dumpData.containsKey("dump_info")) {
            throw new IllegalArgumentException("Invalid dump format: missing tables or dump_info");
        }
        DataSource ds = dataSourceProvider.getIfAvailable();
        if (ds == null) {
            throw new IllegalStateException("DB connection failed: repository DataSource not configured");
        }

        RepositoryConfig repo;
        try {
            repo = serviceConfig.repository();
        } catch (RuntimeException e) {
            repo = null;
        }
        boolean isPg = ConfigDumpService.isPostgres(repo == null ? "" : repo.dbType());

        @SuppressWarnings("unchecked")
        Map<String, Object> tablesMap = (Map<String, Object>) dumpData.get("tables");
        @SuppressWarnings("unchecked")
        Map<String, Object> sequencesMap = (Map<String, Object>) dumpData.getOrDefault("sequences",
                java.util.Collections.<String, Object>emptyMap());
        @SuppressWarnings("unchecked")
        Map<String, Object> infoMap = (Map<String, Object>) dumpData.get("dump_info");
        String source = infoMap == null ? "unknown" : String.valueOf(infoMap.getOrDefault("source_db", "unknown"));

        List<RestoreTableResult> results = new ArrayList<>();
        List<TableOrder> tableOrder = new ArrayList<>();

        try (Connection conn = ds.getConnection()) {
            conn.setAutoCommit(false);

            // ── Oracle 세션 설정 ──────────────────────────────────────
            if (!isPg) {
                try (java.sql.Statement st = conn.createStatement()) {
                    st.execute("ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD HH24:MI:SS'");
                    st.execute("ALTER SESSION SET NLS_TIMESTAMP_FORMAT = 'YYYY-MM-DD HH24:MI:SS'");
                } catch (SQLException ignore) {
                    // 권한 부족 — 무시
                }
            }

            DatabaseMetaData dmd = conn.getMetaData();

            // ── Pre-scan: 메타 수집 ────────────────────────────────────
            for (Map.Entry<String, Object> e : tablesMap.entrySet()) {
                String tname = e.getKey();
                @SuppressWarnings("unchecked")
                Map<String, Object> tdata = (Map<String, Object>) e.getValue();
                if (tdata == null) {
                    results.add(skip(tname, "no rows"));
                    continue;
                }
                @SuppressWarnings("unchecked")
                List<List<Object>> rows = (List<List<Object>>) tdata.get("rows");
                @SuppressWarnings("unchecked")
                List<String> srcColsRaw = (List<String>) tdata.get("columns");
                if (rows == null || rows.isEmpty() || srcColsRaw == null || srcColsRaw.isEmpty()) {
                    results.add(skip(tname, "no rows"));
                    continue;
                }

                List<String> srcCols = new ArrayList<>(srcColsRaw.size());
                for (String c : srcColsRaw) srcCols.add(c.toLowerCase());

                List<String> tgtCols = targetColumns(dmd, tname, isPg);
                Map<String, String> colTypes = targetColumnTypes(dmd, tname, isPg);

                if (tgtCols.isEmpty()) {
                    results.add(skip(tname, "table not found in target"));
                    continue;
                }

                List<String> common = new ArrayList<>();
                for (String c : srcCols) if (tgtCols.contains(c)) common.add(c);
                List<String> srcOnly = new ArrayList<>();
                for (String c : srcCols) if (!tgtCols.contains(c)) srcOnly.add(c);
                List<String> tgtOnly = new ArrayList<>();
                for (String c : tgtCols) if (!srcCols.contains(c)) tgtOnly.add(c);

                if (common.isEmpty()) {
                    results.add(skip(tname, "no common columns"));
                    continue;
                }

                List<Integer> commonIdx = new ArrayList<>(common.size());
                for (String c : common) commonIdx.add(srcCols.indexOf(c));

                String tbl = isPg ? ("public." + tname) : tname.toUpperCase();
                String colList = isPg
                        ? String.join(", ", common)
                        : common.stream().map(String::toUpperCase)
                          .collect(java.util.stream.Collectors.joining(", "));

                tableOrder.add(new TableOrder(tname, rows, tbl, colList, common,
                        commonIdx, colTypes, srcOnly, tgtOnly));
            }

            // ── __PATCH_INSP_RESTORE_ORDER__ ─────────────────────────
            tableOrder.sort(Comparator.comparingInt(t -> restorePriority(t.tname)));

            // ── Phase 1: DELETE (역순) ────────────────────────────────
            for (int i = tableOrder.size() - 1; i >= 0; i--) {
                TableOrder t = tableOrder.get(i);
                try (java.sql.Statement st = conn.createStatement()) {
                    st.execute("DELETE FROM " + t.tbl);
                }
            }

            // ── Phase 2: INSERT (정순) ────────────────────────────────
            int totalInserted = 0;
            for (TableOrder t : tableOrder) {
                int inserted = 0;
                String placeholders;
                if (isPg) {
                    placeholders = String.join(", ", java.util.Collections.nCopies(t.common.size(), "?"));
                } else {
                    StringBuilder p = new StringBuilder();
                    for (int i = 0; i < t.common.size(); i++) {
                        if (i > 0) p.append(", ");
                        p.append("?");
                    }
                    placeholders = p.toString();
                }
                String sql = "INSERT INTO " + t.tbl + " (" + t.colList + ") VALUES (" + placeholders + ")";

                try (PreparedStatement ps = conn.prepareStatement(sql)) {
                    for (List<Object> row : t.rows) {
                        for (int i = 0; i < t.commonIdx.size(); i++) {
                            int srcIdx = t.commonIdx.get(i);
                            Object v = srcIdx < row.size() ? row.get(srcIdx) : null;
                            String col = t.common.get(i);
                            String ctype = t.colTypes.getOrDefault(col, "");
                            ps.setObject(i + 1, coerce(v, ctype));
                        }
                        ps.addBatch();
                        inserted++;
                    }
                    ps.executeBatch();
                }
                totalInserted += inserted;

                results.add(new RestoreTableResult(
                        t.tname, "ok", inserted, t.common.size(),
                        t.common.size() + t.srcOnly.size(),
                        null,
                        t.srcOnly.isEmpty() ? null : t.srcOnly,
                        t.tgtOnly.isEmpty() ? null : t.tgtOnly));
            }

            // ── Phase 3: Sequence reset ────────────────────────────────
            List<Map<String, Object>> seqResults = new ArrayList<>();
            for (Map.Entry<String, Object> se : sequencesMap.entrySet()) {
                String sname = se.getKey();
                Object sval = se.getValue();
                if (sval == null) continue;
                Map<String, Object> r = new LinkedHashMap<>();
                r.put("sequence", sname);
                r.put("value", sval);
                if (isPg) {
                    try (java.sql.Statement st = conn.createStatement()) {
                        long v = toLong(sval);
                        st.execute("SELECT setval('" + sname + "', " + Math.max(v, 1L) + ")");
                        r.put("status", "ok");
                    } catch (SQLException ex) {
                        r.put("status", "error");
                        r.put("error", trim(ex.getMessage(), 100));
                    }
                } else {
                    r.put("status", "manual");
                    r.put("note", "Oracle sequence requires manual verification");
                }
                seqResults.add(r);
            }

            conn.commit();
            return new RestoreResult(totalInserted, results, seqResults, source);

        } catch (SQLException ex) {
            log.warn("restore 실패", ex);
            throw new RuntimeException(trim(ex.getMessage(), 300), ex);
        }
    }

    // ── 보조 ────────────────────────────────────────────────────────────

    private static RestoreTableResult skip(String tname, String reason) {
        return new RestoreTableResult(tname, "skip", 0, null, null, reason, null, null);
    }

    /** 원본 _restore_priority 1:1. */
    private static int restorePriority(String name) {
        if ("ora_app_call_tree_info".equals(name)) return 0;
        if ("apm_db_info".equals(name)) return 1;
        return 2;
    }

    private static List<String> targetColumns(DatabaseMetaData dmd, String table, boolean isPg) {
        List<String> out = new ArrayList<>();
        try {
            String name = isPg ? table : table.toUpperCase();
            try (ResultSet rs = dmd.getColumns(null, null, name, "%")) {
                while (rs.next()) {
                    out.add(rs.getString("COLUMN_NAME").toLowerCase());
                }
            }
        } catch (SQLException e) {
            log.debug("targetColumns failed: {}", e.getMessage());
        }
        return out;
    }

    private static Map<String, String> targetColumnTypes(DatabaseMetaData dmd, String table, boolean isPg) {
        Map<String, String> out = new LinkedHashMap<>();
        try {
            String name = isPg ? table : table.toUpperCase();
            try (ResultSet rs = dmd.getColumns(null, null, name, "%")) {
                while (rs.next()) {
                    out.put(rs.getString("COLUMN_NAME").toLowerCase(),
                            rs.getString("TYPE_NAME").toUpperCase());
                }
            }
        } catch (SQLException e) {
            log.debug("targetColumnTypes failed: {}", e.getMessage());
        }
        return out;
    }

    /** 원본 row 변환 1:1 — String 형태의 timestamp/date 를 컬럼 타입에 맞춰 LocalDateTime/LocalDate 로 캐스팅. */
    private static Object coerce(Object v, String ctype) {
        if (v == null) return null;
        if (v instanceof String) {
            String s = (String) v;
            if (ctype != null && (ctype.contains("DATE") || ctype.contains("TIMESTAMP"))) {
                if (PAT_TS.matcher(s).matches()) {
                    return Timestamp.valueOf(LocalDateTime.parse(s, ISO_TS));
                }
                if (PAT_DATE.matcher(s).matches()) {
                    return java.sql.Date.valueOf(LocalDate.parse(s, ISO_DATE));
                }
            }
        }
        // BigDecimal, Long, Double, Boolean 등은 그대로 setObject 에 전달.
        return v;
    }

    private static long toLong(Object v) {
        if (v == null) return 0L;
        if (v instanceof Number) return ((Number) v).longValue();
        try { return Long.parseLong(String.valueOf(v).trim()); }
        catch (NumberFormatException e) { return 0L; }
    }

    private static String trim(String s, int max) {
        if (s == null) return "";
        return s.length() > max ? s.substring(0, max) : s;
    }

    private static final class TableOrder {
        final String tname;
        final List<List<Object>> rows;
        final String tbl;
        final String colList;
        final List<String> common;
        final List<Integer> commonIdx;
        final Map<String, String> colTypes;
        final List<String> srcOnly;
        final List<String> tgtOnly;
        TableOrder(String tname, List<List<Object>> rows, String tbl, String colList,
                   List<String> common, List<Integer> commonIdx,
                   Map<String, String> colTypes, List<String> srcOnly, List<String> tgtOnly) {
            this.tname = tname;
            this.rows = rows;
            this.tbl = tbl;
            this.colList = colList;
            this.common = common;
            this.commonIdx = commonIdx;
            this.colTypes = colTypes;
            this.srcOnly = srcOnly;
            this.tgtOnly = tgtOnly;
        }
    }
}
