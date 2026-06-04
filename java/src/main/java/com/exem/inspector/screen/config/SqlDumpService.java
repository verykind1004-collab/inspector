package com.exem.inspector.screen.config;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;

import com.exem.inspector.common.db.RepositoryConfig;
import com.exem.inspector.config.ServiceConfig;

/**
 * Config Dump → SQL 변환 서비스 — 원본 config_dump.py::_generate_sql / _sql_literal 1:1.
 *
 * <p>ConfigDumpService.dump() 결과를 받아 Oracle / PostgreSQL 분기로 SQL 텍스트 생성.
 * DELETE 역순(자식 먼저) + INSERT 정순(부모 먼저) + Sequence reset + COMMIT.
 */
@Service
public class SqlDumpService {

    private static final DateTimeFormatter ISO = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final Pattern PAT_TS   = Pattern.compile("^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}$");
    private static final Pattern PAT_DATE = Pattern.compile("^\\d{4}-\\d{2}-\\d{2}$");

    private final ConfigDumpService dumpService;
    private final ServiceConfig serviceConfig;

    public SqlDumpService(ConfigDumpService dumpService, ServiceConfig serviceConfig) {
        this.dumpService = dumpService;
        this.serviceConfig = serviceConfig;
    }

    /** menuKeys 로 dump 후 SQL 텍스트 생성. */
    public SqlDumpResult generate(List<String> menuKeys) {
        ConfigDumpPayload p = dumpService.dump(menuKeys);
        return build(p);
    }

    /** dump 결과 단일 객체로부터 SQL 생성 (단위 테스트용 분리 진입점). */
    public SqlDumpResult build(ConfigDumpPayload p) {
        boolean isPg = isPostgres(p.getDbType());
        String sourceLabel = resolveSourceLabel();
        List<String> menuLabels = resolveMenuLabels(p.getSelectedMenus());

        StringBuilder sb = new StringBuilder();
        appendHeader(sb, sourceLabel, menuLabels, isPg);

        // ── 1) 데이터 있는 테이블만 추출 — 빈 테이블은 주석 처리하고 skip
        List<Map.Entry<String, List<Map<String, Object>>>> tableItems = new ArrayList<>();
        for (Map.Entry<String, List<Map<String, Object>>> e : p.getTables().entrySet()) {
            List<Map<String, Object>> rows = e.getValue();
            if (rows == null || rows.isEmpty()) {
                sb.append("-- ").append(e.getKey()).append(": 0 rows (skip)\n\n");
                continue;
            }
            tableItems.add(e);
        }

        // ── 2) DELETE — FK 안전성을 위해 자식 먼저(역순)
        sb.append("-- DELETE (reverse order for FK safety)\n");
        for (int i = tableItems.size() - 1; i >= 0; i--) {
            String t = tableItems.get(i).getKey();
            sb.append("DELETE FROM ").append(qualifyTable(t, isPg)).append(";\n");
        }
        sb.append("\n");

        // ── 3) INSERT — 부모 먼저(정순)
        for (Map.Entry<String, List<Map<String, Object>>> e : tableItems) {
            String t = e.getKey();
            List<Map<String, Object>> rows = e.getValue();
            List<String> cols = new ArrayList<>(rows.get(0).keySet());
            String tbl     = qualifyTable(t, isPg);
            String colList = isPg
                    ? String.join(", ", cols)
                    : cols.stream().map(String::toUpperCase).collect(Collectors.joining(", "));
            sb.append("-- ").append(t).append(": ").append(rows.size()).append(" rows\n");
            for (Map<String, Object> row : rows) {
                List<String> vals = new ArrayList<>(cols.size());
                for (String c : cols) vals.add(sqlLiteral(row.get(c), isPg));
                sb.append("INSERT INTO ").append(tbl).append(" (").append(colList)
                  .append(") VALUES (").append(String.join(", ", vals)).append(");\n");
            }
            sb.append("\n");
        }

        // ── 4) Sequence reset
        Map<String, Object> seqs = p.getSequences();
        if (seqs != null && !seqs.isEmpty()) {
            sb.append("-- Sequence reset\n");
            for (Map.Entry<String, Object> se : seqs.entrySet()) {
                long sval = toLong(se.getValue());
                if (isPg) {
                    sb.append("SELECT setval('").append(se.getKey()).append("', ")
                      .append(Math.max(sval, 1L)).append(");\n");
                } else {
                    sb.append("-- Oracle: ALTER SEQUENCE ").append(se.getKey().toUpperCase())
                      .append(" or verify current value >= ").append(sval).append("\n");
                }
            }
            sb.append("\n");
        }

        sb.append("COMMIT;");
        return new SqlDumpResult(sb.toString(), p.getFilenameBase());
    }

    // ── header ──────────────────────────────────────────────────────────

    private static void appendHeader(StringBuilder sb, String source, List<String> labels, boolean isPg) {
        sb.append("-- MaxGauge Config Dump\n");
        sb.append("-- Generated: ").append(LocalDateTime.now().format(ISO)).append("\n");
        sb.append("-- Source: ").append(source).append("\n");
        sb.append("-- Menus: ").append(String.join(", ", labels)).append("\n");
        sb.append("--\n");
        sb.append("-- WARNING: This SQL assumes the target has the SAME schema version.\n");
        sb.append("-- For cross-version migration, use the JSON file instead.\n");
        sb.append("\n");
        if (isPg) sb.append("BEGIN;\n");
        else      sb.append("-- Transaction Start\n");
        if (!isPg) {
            sb.append("ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD HH24:MI:SS';\n");
            sb.append("ALTER SESSION SET NLS_TIMESTAMP_FORMAT = 'YYYY-MM-DD HH24:MI:SS';\n");
        }
        sb.append("\n");
    }

    private String resolveSourceLabel() {
        try {
            RepositoryConfig r = serviceConfig.repository();
            if (r == null) return "(unknown)";
            int port = r.port() > 0 ? r.port() : 1521;
            return r.ip() + ":" + port + " (" + r.dbType() + ")";
        } catch (RuntimeException e) {
            return "(unknown)";
        }
    }

    private static List<String> resolveMenuLabels(Collection<String> keys) {
        Map<String, ConfigDumpMenu> all = ConfigDumpMenu.defaults();
        List<String> out = new ArrayList<>();
        if (keys == null) return out;
        for (String k : keys) {
            ConfigDumpMenu m = all.get(k);
            if (m != null) out.add(m.getLabel());
        }
        return out;
    }

    private static boolean isPostgres(String dbType) {
        return dbType != null && dbType.toLowerCase().contains("postgres");
    }

    private static String qualifyTable(String table, boolean isPg) {
        return isPg ? ("public." + table) : table.toUpperCase();
    }

    private static long toLong(Object v) {
        if (v == null) return 0L;
        if (v instanceof Number) return ((Number) v).longValue();
        try { return Long.parseLong(String.valueOf(v).trim()); }
        catch (NumberFormatException e) { return 0L; }
    }

    // ── sql literal (원본 _sql_literal 1:1) ─────────────────────────────

    /** Visible for testing. */
    static String sqlLiteral(Object val, boolean isPg) {
        if (val == null) return "NULL";

        if (val instanceof Boolean) {
            boolean b = (Boolean) val;
            return isPg ? (b ? "TRUE" : "FALSE") : (b ? "1" : "0");
        }
        if (val instanceof Number) {
            // BigDecimal/Long/Integer/Double — toString 그대로 (원본 동일).
            return val.toString();
        }
        if (val instanceof java.util.Date) {
            String s = ISO.format(((java.util.Date) val).toInstant()
                    .atZone(java.time.ZoneId.systemDefault()).toLocalDateTime());
            return isPg ? "'" + s + "'" : "TO_TIMESTAMP('" + s + "','YYYY-MM-DD HH24:MI:SS')";
        }
        if (val instanceof java.time.LocalDateTime) {
            String s = ISO.format((java.time.LocalDateTime) val);
            return isPg ? "'" + s + "'" : "TO_TIMESTAMP('" + s + "','YYYY-MM-DD HH24:MI:SS')";
        }
        if (val instanceof byte[]) {
            return "'[binary " + ((byte[]) val).length + "B]'";
        }

        // String 또는 기타 — escape 후 패턴 매칭 (sanitize 단계에서 Timestamp 가 String 으로 변환되므로 필요).
        String s = val.toString().replace("'", "''");
        if (!isPg) {
            if (PAT_TS.matcher(s).matches()) {
                return "TO_TIMESTAMP('" + s + "','YYYY-MM-DD HH24:MI:SS')";
            }
            if (PAT_DATE.matcher(s).matches()) {
                return "TO_DATE('" + s + "','YYYY-MM-DD')";
            }
        }
        return "'" + s + "'";
    }
}
