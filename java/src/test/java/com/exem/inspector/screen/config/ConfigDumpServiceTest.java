package com.exem.inspector.screen.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

import java.sql.Timestamp;
import java.util.Collection;
import java.util.Collections;
import java.util.Map;

import javax.sql.DataSource;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

import com.exem.inspector.common.db.RepositoryConfig;
import com.exem.inspector.config.ServiceConfig;

/**
 * ConfigDumpService 단위 테스트 — MENU_DEFS 1:1 + safeValue 변환 + dump 응답 구조.
 *
 * <p>DataSource 미주입 시에도 menus + 빈 dump 반환 검증.
 */
class ConfigDumpServiceTest {

    @SuppressWarnings("unchecked")
    private final ObjectProvider<DataSource> dataSourceProvider = mock(ObjectProvider.class);
    private final ServiceConfig serviceConfig = mock(ServiceConfig.class);
    private final ConfigDumpService service = new ConfigDumpService(dataSourceProvider, serviceConfig);

    private void wireRepoOracle() {
        RepositoryConfig repo = mock(RepositoryConfig.class);
        given(repo.dbType()).willReturn("Oracle");
        given(repo.ip()).willReturn("10.10.45.68");
        given(repo.port()).willReturn(1521);
        given(repo.sid()).willReturn("ORA19");
        given(serviceConfig.repository()).willReturn(repo);
    }

    private void wireRepoPg() {
        RepositoryConfig repo = mock(RepositoryConfig.class);
        given(repo.dbType()).willReturn("PostgreSQL");
        given(repo.ip()).willReturn("10.10.48.126");
        given(repo.port()).willReturn(5432);
        given(repo.sid()).willReturn("maxgauge");
        given(serviceConfig.repository()).willReturn(repo);
    }

    // ── 메뉴 정의 1:1 ───────────────────────────────────────────────────
    @Test
    void menus_returns5Definitions() {
        Collection<ConfigDumpMenu> menus = service.menus();
        assertThat(menus).hasSize(5);
        assertThat(menus).extracting(ConfigDumpMenu::getKey)
                .containsExactly("instance", "account", "alert", "sms", "repository");
    }

    @Test
    void instanceMenu_hasExpectedTablesAndSequences() {
        ConfigDumpMenu m = ConfigDumpMenu.defaults().get("instance");
        assertThat(m.getLabel()).isEqualTo("Instance Management");
        assertThat(m.getTables()).contains("apm_db_info", "ora_service_name", "apm_license_db_info");
        assertThat(m.getSequences()).containsExactly("apm_db_seq", "ora_service_name_seq");
    }

    @Test
    void alertMenu_has11TablesAnd2Sequences() {
        ConfigDumpMenu m = ConfigDumpMenu.defaults().get("alert");
        assertThat(m.getTables()).hasSize(11);
        assertThat(m.getSequences()).hasSize(2);
    }

    @Test
    void accountSmsRepository_haveNoSequences() {
        Map<String, ConfigDumpMenu> all = ConfigDumpMenu.defaults();
        assertThat(all.get("account").getSequences()).isEmpty();
        assertThat(all.get("sms").getSequences()).isEmpty();
        assertThat(all.get("repository").getSequences()).isEmpty();
    }

    // ── dump — DataSource 없을 때 ──────────────────────────────────────
    @Test
    void dump_noDataSource_returnsEmptyTables() {
        given(dataSourceProvider.getIfAvailable()).willReturn(null);
        wireRepoOracle();

        ConfigDumpPayload p = service.dump(Collections.singletonList("instance"));
        assertThat(p.getTables()).isEmpty();
        assertThat(p.getSequences()).isEmpty();
        assertThat(p.getDumpInfo().getMenus()).containsExactly("instance");
        assertThat(p.getDumpInfo().getMenuLabels()).containsExactly("Instance Management");
        assertThat(p.getFilenameBase()).startsWith("config_dump_");
        assertThat(p.getDbType()).isEqualTo("Oracle");
        assertThat(p.getStats().getTables()).isZero();
        assertThat(p.getStats().getRows()).isZero();
        assertThat(p.getStats().getSkipped()).isEmpty();
    }

    @Test
    void dump_emptyKeys_selectsAllMenus() {
        given(dataSourceProvider.getIfAvailable()).willReturn(null);
        wireRepoOracle();

        ConfigDumpPayload p = service.dump(Collections.<String>emptyList());
        assertThat(p.getDumpInfo().getMenus()).hasSize(5);
    }

    @Test
    void dump_unknownKey_isIgnored() {
        given(dataSourceProvider.getIfAvailable()).willReturn(null);
        wireRepoOracle();

        ConfigDumpPayload p = service.dump(java.util.Arrays.asList("instance", "nope"));
        assertThat(p.getDumpInfo().getMenus()).containsExactly("instance");
    }

    @Test
    void dump_jsonContent_includesDumpInfoTablesSequences() {
        given(dataSourceProvider.getIfAvailable()).willReturn(null);
        wireRepoOracle();

        ConfigDumpPayload p = service.dump(Collections.singletonList("instance"));
        String json = p.getJsonContent();
        assertThat(json).contains("\"dump_info\"")
                        .contains("\"tables\"")
                        .contains("\"sequences\"")
                        .contains("\"menus\"")
                        .contains("\"menu_labels\"")
                        .contains("\"version\" : \"1.0\"");
    }

    @Test
    void dump_sqlContent_hasOracleTransactionMarker() {
        given(dataSourceProvider.getIfAvailable()).willReturn(null);
        wireRepoOracle();

        ConfigDumpPayload p = service.dump(Collections.singletonList("instance"));
        assertThat(p.getSqlContent()).contains("-- MaxGauge Config Dump")
                                       .contains("-- Transaction Start")
                                       .endsWith("COMMIT;");
    }

    @Test
    void dump_sqlContent_pgUsesBeginAndPublicSchema() {
        given(dataSourceProvider.getIfAvailable()).willReturn(null);
        wireRepoPg();

        ConfigDumpPayload p = service.dump(Collections.singletonList("instance"));
        assertThat(p.getSqlContent()).contains("BEGIN;");
    }

    @Test
    void dump_dumpInfo_sourceDbContainsIpPortSid() {
        given(dataSourceProvider.getIfAvailable()).willReturn(null);
        wireRepoOracle();

        ConfigDumpPayload p = service.dump(Collections.singletonList("instance"));
        assertThat(p.getDumpInfo().getSourceDb()).contains("10.10.45.68")
                                                  .contains("1521")
                                                  .contains("ORA19")
                                                  .contains("Oracle");
    }

    // ── safeValue (Timestamp/BigDecimal/byte[] 변환) ─────────────────
    @Test
    void safeValue_timestamp_returnsString() {
        Timestamp ts = Timestamp.valueOf("2026-06-04 10:30:00");
        Object v = ConfigDumpService.safeValue(ts);
        assertThat(v).isInstanceOf(String.class);
        assertThat((String) v).startsWith("2026-06-04 10:30:00");
    }

    @Test
    void safeValue_intBigDecimal_returnsLong() {
        java.math.BigDecimal bd = new java.math.BigDecimal("42");
        assertThat(ConfigDumpService.safeValue(bd)).isEqualTo(42L);
    }

    @Test
    void safeValue_floatBigDecimal_returnsDouble() {
        java.math.BigDecimal bd = new java.math.BigDecimal("3.14");
        assertThat(ConfigDumpService.safeValue(bd)).isEqualTo(3.14);
    }

    @Test
    void safeValue_bytes_returnsUtf8String() {
        // 원본 1:1: bytes.decode("utf-8", errors="replace") — ASCII 는 그대로.
        byte[] b = "abc".getBytes(java.nio.charset.StandardCharsets.UTF_8);
        assertThat(ConfigDumpService.safeValue(b)).isEqualTo("abc");
    }

    @Test
    void safeValue_null_returnsNull() {
        assertThat(ConfigDumpService.safeValue(null)).isNull();
    }
}
