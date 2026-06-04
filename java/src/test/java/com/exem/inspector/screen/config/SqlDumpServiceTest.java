package com.exem.inspector.screen.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import com.exem.inspector.common.db.RepositoryConfig;
import com.exem.inspector.config.ServiceConfig;

/**
 * SqlDumpService 단위 테스트 — _generate_sql / _sql_literal 1:1 동등 검증.
 *
 * <p>ConfigDumpService 는 mock 으로 주입(실 DB 접근 불요).
 */
class SqlDumpServiceTest {

    private ConfigDumpService dumpService;
    private ServiceConfig serviceConfig;
    private SqlDumpService sqlService;

    @BeforeEach
    void setUp() {
        dumpService = mock(ConfigDumpService.class);
        serviceConfig = mock(ServiceConfig.class);
        RepositoryConfig repo = mock(RepositoryConfig.class);
        given(repo.dbType()).willReturn("Oracle");
        given(repo.ip()).willReturn("10.10.45.68");
        given(repo.port()).willReturn(1521);
        given(serviceConfig.repository()).willReturn(repo);
        sqlService = new SqlDumpService(dumpService, serviceConfig);
    }

    // ── helper ──────────────────────────────────────────────────────────

    private ConfigDumpPayload payload(String dbType,
                                       Map<String, List<Map<String, Object>>> tables,
                                       Map<String, Object> seqs,
                                       List<String> menus) {
        return new ConfigDumpPayload("config_dump_20260604_103000", dbType, menus,
                tables, seqs, Collections.<String>emptyList());
    }

    private Map<String, Object> row(Object... kv) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) m.put((String) kv[i], kv[i + 1]);
        return m;
    }

    // ── header ──────────────────────────────────────────────────────────

    @Test
    void header_oracle_emitsAlterSessionAndNoBegin() {
        ConfigDumpPayload p = payload("Oracle",
                Collections.<String, List<Map<String, Object>>>emptyMap(),
                Collections.<String, Object>emptyMap(),
                Collections.singletonList("instance"));
        String sql = sqlService.build(p).getSql();

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
        ConfigDumpPayload p = payload("PostgreSQL",
                Collections.<String, List<Map<String, Object>>>emptyMap(),
                Collections.<String, Object>emptyMap(),
                Collections.singletonList("alert"));
        String sql = sqlService.build(p).getSql();

        assertThat(sql).contains("BEGIN;");
        assertThat(sql).doesNotContain("ALTER SESSION");
        assertThat(sql).endsWith("COMMIT;");
        assertThat(sql).contains("-- Menus: Alert Management");
    }

    // ── DELETE 역순 + INSERT 정순 ──────────────────────────────────────

    @Test
    void tables_oracleDeleteReverseInsertForward() {
        Map<String, List<Map<String, Object>>> tables = new LinkedHashMap<>();
        tables.put("apm_db_info",
                Collections.singletonList(row("db_id", 1, "db_name", "ORA1")));
        tables.put("ora_service_name",
                Collections.singletonList(row("service_id", 10, "name", "SVC1")));

        ConfigDumpPayload p = payload("Oracle", tables,
                Collections.<String, Object>emptyMap(),
                Collections.singletonList("instance"));
        String sql = sqlService.build(p).getSql();

        // DELETE 역순: ora_service_name 먼저, apm_db_info 다음
        int dOraSvc = sql.indexOf("DELETE FROM ORA_SERVICE_NAME;");
        int dApmDb  = sql.indexOf("DELETE FROM APM_DB_INFO;");
        assertThat(dOraSvc).isGreaterThan(-1);
        assertThat(dApmDb).isGreaterThan(dOraSvc);

        // INSERT 정순: apm_db_info 먼저
        int iApmDb  = sql.indexOf("INSERT INTO APM_DB_INFO");
        int iOraSvc = sql.indexOf("INSERT INTO ORA_SERVICE_NAME");
        assertThat(iApmDb).isGreaterThan(-1);
        assertThat(iOraSvc).isGreaterThan(iApmDb);

        // Oracle: 컬럼 대문자
        assertThat(sql).contains("(DB_ID, DB_NAME)");
    }

    @Test
    void tables_postgresQualifiesPublicSchemaAndKeepsCase() {
        Map<String, List<Map<String, Object>>> tables = new LinkedHashMap<>();
        tables.put("apm_db_info",
                Collections.singletonList(row("db_id", 1, "db_name", "DB1")));

        ConfigDumpPayload p = payload("PostgreSQL", tables,
                Collections.<String, Object>emptyMap(),
                Collections.singletonList("instance"));
        String sql = sqlService.build(p).getSql();

        assertThat(sql).contains("DELETE FROM public.apm_db_info;");
        assertThat(sql).contains("INSERT INTO public.apm_db_info (db_id, db_name)");
    }

    @Test
    void emptyTable_emitsSkipComment() {
        Map<String, List<Map<String, Object>>> tables = new LinkedHashMap<>();
        tables.put("apm_db_info", Collections.<Map<String, Object>>emptyList());

        ConfigDumpPayload p = payload("Oracle", tables,
                Collections.<String, Object>emptyMap(),
                Collections.singletonList("instance"));
        String sql = sqlService.build(p).getSql();

        assertThat(sql).contains("-- apm_db_info: 0 rows (skip)");
        assertThat(sql).doesNotContain("INSERT INTO APM_DB_INFO");
        assertThat(sql).doesNotContain("DELETE FROM APM_DB_INFO");
    }

    // ── Sequence ────────────────────────────────────────────────────────

    @Test
    void sequence_postgresEmitsSetval() {
        Map<String, Object> seqs = new LinkedHashMap<>();
        seqs.put("apm_db_seq", 100L);
        ConfigDumpPayload p = payload("PostgreSQL",
                Collections.<String, List<Map<String, Object>>>emptyMap(),
                seqs, Collections.singletonList("instance"));
        String sql = sqlService.build(p).getSql();

        assertThat(sql).contains("SELECT setval('apm_db_seq', 100);");
    }

    @Test
    void sequence_oracleEmitsCommentOnly() {
        Map<String, Object> seqs = new LinkedHashMap<>();
        seqs.put("apm_db_seq", 42L);
        ConfigDumpPayload p = payload("Oracle",
                Collections.<String, List<Map<String, Object>>>emptyMap(),
                seqs, Collections.singletonList("instance"));
        String sql = sqlService.build(p).getSql();

        assertThat(sql).contains("-- Oracle: ALTER SEQUENCE APM_DB_SEQ or verify current value >= 42");
        assertThat(sql).doesNotContain("setval");
    }

    @Test
    void sequence_postgresZeroIsClampedTo1() {
        Map<String, Object> seqs = new LinkedHashMap<>();
        seqs.put("zero_seq", 0L);
        ConfigDumpPayload p = payload("PostgreSQL",
                Collections.<String, List<Map<String, Object>>>emptyMap(),
                seqs, Collections.singletonList("instance"));
        String sql = sqlService.build(p).getSql();

        assertThat(sql).contains("SELECT setval('zero_seq', 1);");
    }

    // ── sqlLiteral 단위 ────────────────────────────────────────────────

    @Test
    void sqlLiteral_nullReturnsLiteralNULL() {
        assertThat(SqlDumpService.sqlLiteral(null, false)).isEqualTo("NULL");
        assertThat(SqlDumpService.sqlLiteral(null, true)).isEqualTo("NULL");
    }

    @Test
    void sqlLiteral_booleanOraclePgDifferent() {
        assertThat(SqlDumpService.sqlLiteral(true,  false)).isEqualTo("1");
        assertThat(SqlDumpService.sqlLiteral(false, false)).isEqualTo("0");
        assertThat(SqlDumpService.sqlLiteral(true,  true)).isEqualTo("TRUE");
        assertThat(SqlDumpService.sqlLiteral(false, true)).isEqualTo("FALSE");
    }

    @Test
    void sqlLiteral_numbersReturnRaw() {
        assertThat(SqlDumpService.sqlLiteral(42, false)).isEqualTo("42");
        assertThat(SqlDumpService.sqlLiteral(3.14, true)).isEqualTo("3.14");
        assertThat(SqlDumpService.sqlLiteral(new java.math.BigDecimal("100"), false)).isEqualTo("100");
    }

    @Test
    void sqlLiteral_stringEscapesSingleQuote() {
        assertThat(SqlDumpService.sqlLiteral("o'brien", true)).isEqualTo("'o''brien'");
        assertThat(SqlDumpService.sqlLiteral("o'brien", false)).isEqualTo("'o''brien'");
    }

    @Test
    void sqlLiteral_isoTimestampStringConvertsToOracleToTimestamp() {
        String ts = "2026-06-04 10:30:00";
        assertThat(SqlDumpService.sqlLiteral(ts, false))
                .isEqualTo("TO_TIMESTAMP('2026-06-04 10:30:00','YYYY-MM-DD HH24:MI:SS')");
        // PG 는 단순 quote
        assertThat(SqlDumpService.sqlLiteral(ts, true)).isEqualTo("'2026-06-04 10:30:00'");
    }

    @Test
    void sqlLiteral_isoDateStringConvertsToOracleToDate() {
        String d = "2026-06-04";
        assertThat(SqlDumpService.sqlLiteral(d, false))
                .isEqualTo("TO_DATE('2026-06-04','YYYY-MM-DD')");
        assertThat(SqlDumpService.sqlLiteral(d, true)).isEqualTo("'2026-06-04'");
    }

    @Test
    void sqlLiteral_bytesEmitsBinaryMarker() {
        byte[] b = new byte[] { 1, 2, 3, 4 };
        assertThat(SqlDumpService.sqlLiteral(b, false)).isEqualTo("'[binary 4B]'");
    }

    // ── generate(): dumpService 위임 검증 ──────────────────────────────

    @Test
    void generate_delegatesToDumpService() {
        Map<String, List<Map<String, Object>>> tables = new LinkedHashMap<>();
        tables.put("apm_db_info", Collections.singletonList(row("db_id", 1)));
        ConfigDumpPayload p = payload("Oracle", tables,
                Collections.<String, Object>emptyMap(),
                Collections.singletonList("instance"));
        given(dumpService.dump(Arrays.asList("instance"))).willReturn(p);

        SqlDumpResult r = sqlService.generate(Arrays.asList("instance"));
        assertThat(r.getFilenameBase()).isEqualTo("config_dump_20260604_103000");
        assertThat(r.getSql()).contains("INSERT INTO APM_DB_INFO");
    }
}
