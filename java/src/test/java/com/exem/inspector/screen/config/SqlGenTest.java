package com.exem.inspector.screen.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;

/**
 * SqlGen 단위 테스트 — 원본 config_dump.py 의 _generate_sql / _sql_literal 1:1 동등 검증.
 *
 * <p>{@link ConfigDumpService} 내부에서만 호출되는 정적 유틸이므로 헬퍼로 직접 호출.
 */
class SqlGenTest {

    private DumpInfo info(String dbType, String... menuKeys) {
        List<String> keys = Arrays.asList(menuKeys);
        List<String> labels = new java.util.ArrayList<>();
        Map<String, ConfigDumpMenu> all = ConfigDumpMenu.defaults();
        for (String k : keys) {
            ConfigDumpMenu m = all.get(k);
            labels.add(m == null ? k : m.getLabel());
        }
        return new DumpInfo("2026-06-04 10:30:00",
                "10.10.45.68:1521/ORA19 (Oracle)", dbType,
                keys, labels, "1.0");
    }

    private DumpTable table(List<String> cols, List<List<Object>> rows) {
        return new DumpTable(cols, rows, rows.size());
    }

    private Map<String, DumpTable> tables(Map.Entry<String, DumpTable>... entries) {
        Map<String, DumpTable> m = new LinkedHashMap<>();
        for (Map.Entry<String, DumpTable> e : entries) m.put(e.getKey(), e.getValue());
        return m;
    }

    private Map.Entry<String, DumpTable> entry(String k, DumpTable v) {
        return new java.util.AbstractMap.SimpleEntry<>(k, v);
    }

    // ── header ──────────────────────────────────────────────────────────

    @Test
    void header_oracle_emitsAlterSessionAndNoBegin() {
        String sql = SqlGen.generate(info("oracle", "instance"),
                Collections.<String, DumpTable>emptyMap(),
                Collections.<String, Object>emptyMap(), false);

        assertThat(sql).contains("-- MaxGauge Config Dump");
        assertThat(sql).contains("ALTER SESSION SET NLS_DATE_FORMAT");
        assertThat(sql).contains("ALTER SESSION SET NLS_TIMESTAMP_FORMAT");
        assertThat(sql).contains("-- Transaction Start");
        assertThat(sql).doesNotContain("BEGIN;");
        assertThat(sql).endsWith("COMMIT;");
        assertThat(sql).contains("-- Menus: Instance Management");
    }

    @Test
    void header_postgres_emitsBeginAndNoAlterSession() {
        String sql = SqlGen.generate(info("pg", "alert"),
                Collections.<String, DumpTable>emptyMap(),
                Collections.<String, Object>emptyMap(), true);

        assertThat(sql).contains("BEGIN;");
        assertThat(sql).doesNotContain("ALTER SESSION");
        assertThat(sql).endsWith("COMMIT;");
        assertThat(sql).contains("-- Menus: Alert Management");
    }

    // ── DELETE 역순 + INSERT 정순 ──────────────────────────────────────

    @Test
    void tables_oracleDeleteReverseInsertForward() {
        Map<String, DumpTable> ts = tables(
                entry("apm_db_info", table(Arrays.asList("db_id", "db_name"),
                        Collections.<List<Object>>singletonList(Arrays.<Object>asList(1, "ORA1")))),
                entry("ora_service_name", table(Arrays.asList("service_id", "name"),
                        Collections.<List<Object>>singletonList(Arrays.<Object>asList(10, "SVC1")))));

        String sql = SqlGen.generate(info("oracle", "instance"), ts,
                Collections.<String, Object>emptyMap(), false);

        int dOraSvc = sql.indexOf("DELETE FROM ORA_SERVICE_NAME;");
        int dApmDb  = sql.indexOf("DELETE FROM APM_DB_INFO;");
        assertThat(dOraSvc).isGreaterThan(-1);
        assertThat(dApmDb).isGreaterThan(dOraSvc);

        int iApmDb  = sql.indexOf("INSERT INTO APM_DB_INFO");
        int iOraSvc = sql.indexOf("INSERT INTO ORA_SERVICE_NAME");
        assertThat(iApmDb).isGreaterThan(-1);
        assertThat(iOraSvc).isGreaterThan(iApmDb);

        // Oracle: 컬럼 대문자
        assertThat(sql).contains("(DB_ID, DB_NAME)");
    }

    @Test
    void tables_postgresQualifiesPublicSchemaAndKeepsCase() {
        Map<String, DumpTable> ts = tables(
                entry("apm_db_info", table(Arrays.asList("db_id", "db_name"),
                        Collections.<List<Object>>singletonList(Arrays.<Object>asList(1, "DB1")))));

        String sql = SqlGen.generate(info("pg", "instance"), ts,
                Collections.<String, Object>emptyMap(), true);

        assertThat(sql).contains("DELETE FROM public.apm_db_info;");
        assertThat(sql).contains("INSERT INTO public.apm_db_info (db_id, db_name)");
    }

    @Test
    void emptyTable_emitsSkipComment() {
        Map<String, DumpTable> ts = tables(
                entry("apm_db_info", table(Arrays.asList("db_id"),
                        Collections.<List<Object>>emptyList())));

        String sql = SqlGen.generate(info("oracle", "instance"), ts,
                Collections.<String, Object>emptyMap(), false);

        assertThat(sql).contains("-- apm_db_info: 0 rows (skip)");
        assertThat(sql).doesNotContain("INSERT INTO APM_DB_INFO");
        assertThat(sql).doesNotContain("DELETE FROM APM_DB_INFO");
    }

    // ── Sequence ────────────────────────────────────────────────────────

    @Test
    void sequence_postgresEmitsSetval() {
        Map<String, Object> seqs = new LinkedHashMap<>();
        seqs.put("apm_db_seq", 100L);
        String sql = SqlGen.generate(info("pg", "instance"),
                Collections.<String, DumpTable>emptyMap(), seqs, true);

        assertThat(sql).contains("SELECT setval('apm_db_seq', 100);");
    }

    @Test
    void sequence_oracleEmitsCommentOnly() {
        Map<String, Object> seqs = new LinkedHashMap<>();
        seqs.put("apm_db_seq", 42L);
        String sql = SqlGen.generate(info("oracle", "instance"),
                Collections.<String, DumpTable>emptyMap(), seqs, false);

        assertThat(sql).contains("-- Oracle: ALTER SEQUENCE APM_DB_SEQ or verify current value >= 42");
        assertThat(sql).doesNotContain("setval");
    }

    @Test
    void sequence_postgresZeroIsClampedTo1() {
        Map<String, Object> seqs = new LinkedHashMap<>();
        seqs.put("zero_seq", 0L);
        String sql = SqlGen.generate(info("pg", "instance"),
                Collections.<String, DumpTable>emptyMap(), seqs, true);

        assertThat(sql).contains("SELECT setval('zero_seq', 1);");
    }

    // ── sqlLiteral 단위 ────────────────────────────────────────────────

    @Test
    void sqlLiteral_nullReturnsLiteralNULL() {
        assertThat(SqlGen.sqlLiteral(null, false)).isEqualTo("NULL");
        assertThat(SqlGen.sqlLiteral(null, true)).isEqualTo("NULL");
    }

    @Test
    void sqlLiteral_booleanOraclePgDifferent() {
        assertThat(SqlGen.sqlLiteral(true,  false)).isEqualTo("1");
        assertThat(SqlGen.sqlLiteral(false, false)).isEqualTo("0");
        assertThat(SqlGen.sqlLiteral(true,  true)).isEqualTo("TRUE");
        assertThat(SqlGen.sqlLiteral(false, true)).isEqualTo("FALSE");
    }

    @Test
    void sqlLiteral_numbersReturnRaw() {
        assertThat(SqlGen.sqlLiteral(42, false)).isEqualTo("42");
        assertThat(SqlGen.sqlLiteral(3.14, true)).isEqualTo("3.14");
        assertThat(SqlGen.sqlLiteral(new java.math.BigDecimal("100"), false)).isEqualTo("100");
    }

    @Test
    void sqlLiteral_stringEscapesSingleQuote() {
        assertThat(SqlGen.sqlLiteral("o'brien", true)).isEqualTo("'o''brien'");
        assertThat(SqlGen.sqlLiteral("o'brien", false)).isEqualTo("'o''brien'");
    }

    @Test
    void sqlLiteral_isoTimestampStringConvertsToOracleToTimestamp() {
        String ts = "2026-06-04 10:30:00";
        assertThat(SqlGen.sqlLiteral(ts, false))
                .isEqualTo("TO_TIMESTAMP('2026-06-04 10:30:00','YYYY-MM-DD HH24:MI:SS')");
        assertThat(SqlGen.sqlLiteral(ts, true)).isEqualTo("'2026-06-04 10:30:00'");
    }

    @Test
    void sqlLiteral_isoDateStringConvertsToOracleToDate() {
        String d = "2026-06-04";
        assertThat(SqlGen.sqlLiteral(d, false))
                .isEqualTo("TO_DATE('2026-06-04','YYYY-MM-DD')");
        assertThat(SqlGen.sqlLiteral(d, true)).isEqualTo("'2026-06-04'");
    }

    @Test
    void sqlLiteral_bytesDecodedAsUtf8AndQuoted() {
        // 원본 1:1: bytes → decode('utf-8','replace') 후 일반 escape 경로.
        byte[] b = "ab'c".getBytes(java.nio.charset.StandardCharsets.UTF_8);
        assertThat(SqlGen.sqlLiteral(b, false)).isEqualTo("'ab''c'");
        assertThat(SqlGen.sqlLiteral(b, true)).isEqualTo("'ab''c'");
    }
}
