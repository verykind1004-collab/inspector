package com.exem.inspector.screen.config;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Config Dump SQL 생성기 — 원본 config_dump.py 의 _generate_sql / _sql_literal 1:1.
 *
 * <p>{@link ConfigDumpService} 가 dump_data 를 만든 뒤 jsonContent 와 sqlContent 를
 * 동시 생성하기 위해 사용한다. 원본 page 가 download 시 사용하는 두 산출물을 한 응답에 담는다.
 *
 * <p>DELETE 역순(자식 먼저) + INSERT 정순(부모 먼저) + Sequence reset + COMMIT.
 */
final class SqlGen {

    private static final DateTimeFormatter ISO = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final Pattern PAT_TS   = Pattern.compile("^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}$");
    private static final Pattern PAT_DATE = Pattern.compile("^\\d{4}-\\d{2}-\\d{2}$");

    private SqlGen() {}

    static String generate(DumpInfo info, Map<String, DumpTable> tables,
                           Map<String, Object> sequences, boolean isPg) {
        StringBuilder sb = new StringBuilder();
        sb.append("-- MaxGauge Config Dump\n");
        sb.append("-- Generated: ").append(info.getCreatedAt()).append('\n');
        sb.append("-- Source: ").append(info.getSourceDb()).append('\n');
        sb.append("-- Menus: ").append(String.join(", ", info.getMenuLabels())).append('\n');
        sb.append("--\n");
        sb.append("-- WARNING: This SQL assumes the target has the SAME schema version.\n");
        sb.append("-- For cross-version migration, use the JSON file instead.\n");
        sb.append('\n');
        sb.append(isPg ? "BEGIN;\n" : "-- Transaction Start\n");
        if (!isPg) {
            sb.append("ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD HH24:MI:SS';\n");
            sb.append("ALTER SESSION SET NLS_TIMESTAMP_FORMAT = 'YYYY-MM-DD HH24:MI:SS';\n");
        }
        sb.append('\n');

        // 데이터 있는 테이블만 추출 — 빈 테이블은 주석 처리.
        List<Map.Entry<String, DumpTable>> items = new ArrayList<>();
        for (Map.Entry<String, DumpTable> e : tables.entrySet()) {
            DumpTable t = e.getValue();
            if (t == null || t.getRows() == null || t.getRows().isEmpty()) {
                sb.append("-- ").append(e.getKey()).append(": 0 rows (skip)\n\n");
                continue;
            }
            items.add(e);
        }

        // DELETE — 자식 먼저(역순).
        sb.append("-- DELETE (reverse order for FK safety)\n");
        for (int i = items.size() - 1; i >= 0; i--) {
            String tname = items.get(i).getKey();
            sb.append("DELETE FROM ").append(qualify(tname, isPg)).append(";\n");
        }
        sb.append('\n');

        // INSERT — 부모 먼저(정순).
        for (Map.Entry<String, DumpTable> e : items) {
            String tname = e.getKey();
            DumpTable t = e.getValue();
            List<String> cols = t.getColumns();
            String tbl = qualify(tname, isPg);
            String colList = isPg
                    ? String.join(", ", cols)
                    : cols.stream().map(String::toUpperCase).collect(Collectors.joining(", "));
            sb.append("-- ").append(tname).append(": ").append(t.getRows().size()).append(" rows\n");
            for (List<Object> row : t.getRows()) {
                List<String> vals = new ArrayList<>(row.size());
                for (Object v : row) vals.add(sqlLiteral(v, isPg));
                sb.append("INSERT INTO ").append(tbl).append(" (").append(colList)
                  .append(") VALUES (").append(String.join(", ", vals)).append(");\n");
            }
            sb.append('\n');
        }

        // Sequence reset
        if (sequences != null && !sequences.isEmpty()) {
            sb.append("-- Sequence reset\n");
            for (Map.Entry<String, Object> se : sequences.entrySet()) {
                long sval = toLong(se.getValue());
                if (isPg) {
                    sb.append("SELECT setval('").append(se.getKey()).append("', ")
                      .append(Math.max(sval, 1L)).append(");\n");
                } else {
                    sb.append("-- Oracle: ALTER SEQUENCE ").append(se.getKey().toUpperCase())
                      .append(" or verify current value >= ").append(sval).append('\n');
                }
            }
            sb.append('\n');
        }

        sb.append("COMMIT;");
        return sb.toString();
    }

    /** 원본 _sql_literal 1:1. */
    static String sqlLiteral(Object val, boolean isPg) {
        if (val == null) return "NULL";

        if (val instanceof Boolean) {
            boolean b = (Boolean) val;
            return isPg ? (b ? "TRUE" : "FALSE") : (b ? "1" : "0");
        }
        if (val instanceof Number) {
            return val.toString();
        }
        if (val instanceof java.time.LocalDateTime) {
            String s = ISO.format((LocalDateTime) val);
            return isPg ? "'" + s + "'" : "TO_TIMESTAMP('" + s + "','YYYY-MM-DD HH24:MI:SS')";
        }
        if (val instanceof java.util.Date) {
            String s = ISO.format(((java.util.Date) val).toInstant()
                    .atZone(java.time.ZoneId.systemDefault()).toLocalDateTime());
            return isPg ? "'" + s + "'" : "TO_TIMESTAMP('" + s + "','YYYY-MM-DD HH24:MI:SS')";
        }
        if (val instanceof byte[]) {
            // 원본 _sql_literal: bytes → UTF-8 디코드 후 일반 문자열 escape 경로로 합류.
            String decoded = new String((byte[]) val, java.nio.charset.StandardCharsets.UTF_8)
                    .replace("'", "''");
            return "'" + decoded + "'";
        }

        // String — safeValue 단계에서 Timestamp 등은 이미 String 으로 정규화됨.
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

    private static String qualify(String table, boolean isPg) {
        return isPg ? ("public." + table) : table.toUpperCase();
    }

    private static long toLong(Object v) {
        if (v == null) return 0L;
        if (v instanceof Number) return ((Number) v).longValue();
        try { return Long.parseLong(String.valueOf(v).trim()); }
        catch (NumberFormatException e) { return 0L; }
    }
}
