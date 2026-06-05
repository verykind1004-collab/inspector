package com.exem.inspector.screen.history;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

import java.math.BigDecimal;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

import com.exem.inspector.common.db.RepositoryConfig;
import com.exem.inspector.config.ServiceConfig;
import com.exem.inspector.config.ServicesBlock;

/**
 * HistoryDetailService 단위 테스트 — 원본 api_history_os/tbs 응답 shape 1:1.
 */
class HistoryDetailServiceTest {

    @SuppressWarnings("unchecked")
    private final ObjectProvider<HistoryMapper> mapperProvider = mock(ObjectProvider.class);
    private final HistoryMapper mapper = mock(HistoryMapper.class);
    private final ServiceConfig serviceConfig = mock(ServiceConfig.class);
    private final HistoryDetailService service = new HistoryDetailService(mapperProvider, serviceConfig);

    private void wireRepoOracle() {
        RepositoryConfig repo = mock(RepositoryConfig.class);
        given(repo.dbType()).willReturn("Oracle");
        given(serviceConfig.repository()).willReturn(repo);
    }

    private void wireRepoPg() {
        RepositoryConfig repo = mock(RepositoryConfig.class);
        given(repo.dbType()).willReturn("PostgreSQL");
        given(serviceConfig.repository()).willReturn(repo);
    }

    private void wireServices(String dgsM, java.util.List<String> dgsS) {
        ServicesBlock sb = mock(ServicesBlock.class);
        given(sb.dgserverM()).willReturn(dgsM);
        given(sb.dgserverS()).willReturn(dgsS);
        given(serviceConfig.services()).willReturn(sb);
    }

    private LinkedHashMap<String, Object> osRow(String ts,
                                                 Double cpuPct, Double cpuUser, Double cpuSys, Double cpuIo,
                                                 Double memTotal, Double memUsed, Double memFree, Double memPct) {
        LinkedHashMap<String, Object> r = new LinkedHashMap<>();
        r.put("ts", ts);
        r.put("cpu_pct",  cpuPct);
        r.put("cpu_user", cpuUser);
        r.put("cpu_sys",  cpuSys);
        r.put("cpu_io",   cpuIo);
        r.put("mem_total", memTotal);
        r.put("mem_used",  memUsed);
        r.put("mem_free",  memFree);
        r.put("mem_pct",   memPct);
        return r;
    }

    @Test
    void os_returnsRows_withOriginalKeys() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(mapper.findOsRange(anyString(), anyString())).willReturn(Arrays.asList(
                osRow("2026-06-05 09:00:00", 12.3, 8.0, 3.0, 1.3, 32.0, 18.2, 13.8, 56.9),
                osRow("2026-06-05 09:01:00", 15.5, 9.5, 4.0, 2.0, 32.0, 20.0, 12.0, 62.5)));

        HistoryOsPayload p = service.os("2026-06-05", "09:00", "10:00");

        assertThat(p.getDate()).isEqualTo("2026-06-05");
        assertThat(p.getFrom()).isEqualTo("09:00");
        assertThat(p.getTo()).isEqualTo("10:00");
        assertThat(p.getData()).hasSize(2);
        HistoryOsRow r0 = p.getData().get(0);
        assertThat(r0.getTs()).isEqualTo("2026-06-05 09:00:00");
        assertThat(r0.getCpuPct()).isEqualTo(12.3);
        assertThat(r0.getCpuUser()).isEqualTo(8.0);
        assertThat(r0.getCpuSys()).isEqualTo(3.0);
        assertThat(r0.getCpuIo()).isEqualTo(1.3);
        assertThat(r0.getMemTotal()).isEqualTo(32.0);
        assertThat(r0.getMemUsed()).isEqualTo(18.2);
        assertThat(r0.getMemFree()).isEqualTo(13.8);
        assertThat(r0.getMemPct()).isEqualTo(56.9);
    }

    @Test
    void os_acceptsBigDecimal_fromMapper() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(mapper.findOsRange(anyString(), anyString())).willReturn(Collections.singletonList(
                osRowGeneric("2026-06-05 09:00:00",
                        new BigDecimal("11.20"), new BigDecimal("7.50"),
                        new BigDecimal("2.40"), new BigDecimal("1.30"),
                        new BigDecimal("32.00"), new BigDecimal("18.00"),
                        new BigDecimal("14.00"), new BigDecimal("56.25"))));

        HistoryOsPayload p = service.os("2026-06-05", "00:00", "23:59");

        HistoryOsRow r = p.getData().get(0);
        assertThat(r.getCpuPct()).isEqualTo(11.20);
        assertThat(r.getMemPct()).isEqualTo(56.25);
    }

    @Test
    void os_normalizesBadDate_toToday() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(mapper.findOsRange(anyString(), anyString())).willReturn(Collections.emptyList());

        HistoryOsPayload p = service.os("bad-date", "00:00", "23:59");

        assertThat(p.getDate()).matches("\\d{4}-\\d{2}-\\d{2}");
    }

    @Test
    void os_normalizesBadTime_to0000And2359() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(mapper.findOsRange(anyString(), anyString())).willReturn(Collections.emptyList());

        HistoryOsPayload p = service.os("2026-06-05", "bad", "99:99");

        assertThat(p.getFrom()).isEqualTo("00:00");
        assertThat(p.getTo()).isEqualTo("23:59");
    }

    @Test
    void os_emptyWhenMapperNull() {
        given(mapperProvider.getIfAvailable()).willReturn(null);

        HistoryOsPayload p = service.os("2026-06-05", "00:00", "23:59");

        assertThat(p.getData()).isEmpty();
        assertThat(p.getDate()).isEqualTo("2026-06-05");
    }

    @Test
    void os_passesNormalizedTimestamps_toMapper() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(mapper.findOsRange("2026-06-05 09:00:00", "2026-06-05 09:59:59"))
                .willReturn(Collections.singletonList(osRow("2026-06-05 09:00:00",
                        1.0, null, null, null, null, null, null, null)));

        HistoryOsPayload p = service.os("2026-06-05", "09:00", "09:59");

        assertThat(p.getData()).hasSize(1);
        assertThat(p.getData().get(0).getCpuPct()).isEqualTo(1.0);
        assertThat(p.getData().get(0).getCpuUser()).isNull();
    }

    private LinkedHashMap<String, Object> osRowGeneric(String ts, Object... vals) {
        LinkedHashMap<String, Object> r = new LinkedHashMap<>();
        String[] keys = {"cpu_pct", "cpu_user", "cpu_sys", "cpu_io",
                         "mem_total", "mem_used", "mem_free", "mem_pct"};
        r.put("ts", ts);
        for (int i = 0; i < keys.length && i < vals.length; i++) r.put(keys[i], vals[i]);
        return r;
    }

    @Test
    void os_normalizeDate_handlesEmpty() {
        assertThat(HistoryDetailService.normalizeDate(null)).matches("\\d{4}-\\d{2}-\\d{2}");
        assertThat(HistoryDetailService.normalizeDate("")).matches("\\d{4}-\\d{2}-\\d{2}");
    }

    @Test
    void os_normalizeTime_acceptsValid() {
        assertThat(HistoryDetailService.normalizeTime("09:30", "00:00")).isEqualTo("09:30");
        assertThat(HistoryDetailService.normalizeTime("23:59", "00:00")).isEqualTo("23:59");
    }

    @Test
    void os_normalizeTime_rejectsBadFormat() {
        assertThat(HistoryDetailService.normalizeTime(null,     "00:00")).isEqualTo("00:00");
        assertThat(HistoryDetailService.normalizeTime("9:30",   "00:00")).isEqualTo("00:00");
        assertThat(HistoryDetailService.normalizeTime("0930",   "00:00")).isEqualTo("00:00");
        assertThat(HistoryDetailService.normalizeTime("ab:cd",  "00:00")).isEqualTo("00:00");
    }

    // ── api_history_tbs ─────────────────────────────────────────────

    private LinkedHashMap<String, Object> tbsRow(String ts, String name,
                                                  Double used, Double total, Double free, Double pct, String status) {
        LinkedHashMap<String, Object> r = new LinkedHashMap<>();
        r.put("ts", ts); r.put("name", name);
        r.put("used", used); r.put("total", total); r.put("free", free);
        r.put("pct", pct); r.put("status", status);
        return r;
    }

    @Test
    void tbs_returnsRows_withOriginalKeys() {
        wireRepoOracle();
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(mapper.findTbsRange(anyString(), anyString())).willReturn(Arrays.asList(
                tbsRow("2026-06-04 23:50:00", "SYSTEM", 12.5, 30.0, 17.5, 41.67, "OK"),
                tbsRow("2026-06-04 23:50:00", "USERS",  85.0, 100.0, 15.0, 85.00, "WARN"),
                tbsRow("2026-06-04 23:50:00", "TEMP",   91.0, 100.0,  9.0, 91.00, "CHECK")));

        HistoryTbsPayload p = service.tbs("2026-06-01", "2026-06-04");

        assertThat(p.getData()).hasSize(3);
        HistoryTbsRow r1 = p.getData().get(1);
        assertThat(r1.getName()).isEqualTo("USERS");
        assertThat(r1.getPct()).isEqualTo(85.00);
        assertThat(r1.getStatus()).isEqualTo("WARN");
        assertThat(p.isPg()).isFalse();
    }

    @Test
    void tbs_emptyToDate_usesFromDate() {
        wireRepoOracle();
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(mapper.findTbsRange("2026-06-01 00:00:00", "2026-06-01 23:59:59"))
                .willReturn(Collections.singletonList(
                        tbsRow("2026-06-01 23:50:00", "SYSTEM", 1.0, 10.0, 9.0, 10.0, "OK")));

        HistoryTbsPayload p = service.tbs("2026-06-01", null);

        assertThat(p.getData()).hasSize(1);
        assertThat(p.getData().get(0).getName()).isEqualTo("SYSTEM");
    }

    @Test
    void tbs_emptyWhenMapperNull() {
        wireRepoOracle();
        given(mapperProvider.getIfAvailable()).willReturn(null);

        HistoryTbsPayload p = service.tbs("2026-06-01", "2026-06-04");

        assertThat(p.getData()).isEmpty();
    }

    @Test
    void tbs_isPg_truePg_falseOracle() {
        wireRepoPg();
        given(mapperProvider.getIfAvailable()).willReturn(null);

        HistoryTbsPayload p = service.tbs("2026-06-01", "2026-06-04");

        assertThat(p.isPg()).isTrue();
    }

    // ── api_history_service ───────────────────────────────────────────

    private LinkedHashMap<String, Object> svcRow(String ts, String name, String status) {
        LinkedHashMap<String, Object> r = new LinkedHashMap<>();
        r.put("ts", ts);
        r.put("service_name", name);
        r.put("s", status);
        return r;
    }

    @Test
    void service_filtersByConfigOrder_dgserverM_Sn_PlatformJS_Repo() {
        wireServices("/home/inspector/dgs_m", Arrays.asList("/home/inspector/dgs_s1", "/home/inspector/dgs_s2"));
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(mapper.findServiceRange(anyString(), anyString())).willReturn(Arrays.asList(
                svcRow("2026-06-05 00:00:00", "DGServer_M",    "RUNNING"),
                svcRow("2026-06-05 00:00:00", "DGServer_S1",   "RUNNING"),
                svcRow("2026-06-05 00:00:00", "PlatformJS",    "RUNNING"),
                svcRow("2026-06-05 00:00:00", "Repository DB", "RUNNING"),
                svcRow("2026-06-05 00:00:00", "UnknownSvc",    "STOPPED")));

        HistoryServicePayload p = service.service("2026-06-05");

        // services 는 config 순서대로 + UnknownSvc 제외 (S2는 데이터 없어서 제외)
        assertThat(p.getServices()).containsExactly("DGServer_M", "DGServer_S1", "PlatformJS", "Repository DB");
        assertThat(p.getData()).containsOnlyKeys("DGServer_M", "DGServer_S1", "PlatformJS", "Repository DB");
        assertThat(p.getData().get("DGServer_M")).hasSize(1);
        assertThat(p.getDate()).isEqualTo("2026-06-05");
    }

    @Test
    void service_emptyDgserverM_skipsIt() {
        wireServices("", Collections.emptyList());
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(mapper.findServiceRange(anyString(), anyString())).willReturn(Arrays.asList(
                svcRow("2026-06-05 00:00:00", "DGServer_M", "RUNNING"),
                svcRow("2026-06-05 00:00:00", "PlatformJS", "RUNNING")));

        HistoryServicePayload p = service.service("2026-06-05");

        // DGServer_M 은 config 빈 값이라 ordered 명단에서 제외 → 응답에 안 포함됨
        assertThat(p.getServices()).containsExactly("PlatformJS");
    }

    @Test
    void service_normalizesBadDate_toToday() {
        wireServices("", Collections.emptyList());
        given(mapperProvider.getIfAvailable()).willReturn(null);

        HistoryServicePayload p = service.service("invalid");

        assertThat(p.getDate()).matches("\\d{4}-\\d{2}-\\d{2}");
    }
}
