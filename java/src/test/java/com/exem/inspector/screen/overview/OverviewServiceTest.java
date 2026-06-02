package com.exem.inspector.screen.overview;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

import java.util.Map;

import org.junit.jupiter.api.Test;

/**
 * OverviewService 페이로드 조립 단위 테스트.
 *
 * <p>ProcReader / HostInfo 를 mock 하여 응답 키·임계 분류만 검증.
 * 원본 _pct_status 규칙(60/80, 80/90) 보존 확인 포함.
 */
class OverviewServiceTest {

    private final ProcReader procReader = mock(ProcReader.class);
    private final HostInfo hostInfo = mock(HostInfo.class);
    private final OverviewService service = new OverviewService(procReader, hostInfo);

    @Test
    void system_returnsHostnameOsUptimeCores() {
        given(hostInfo.hostname()).willReturn("inspector-test");
        given(hostInfo.osDisplay()).willReturn("Linux 5.10.0");
        given(procReader.readUptime()).willReturn("1d 2h 3m 4s");
        given(procReader.readCpuCores()).willReturn(16);

        Map<String, Object> r = service.system();

        assertThat(r)
                .containsEntry("hostname", "inspector-test")
                .containsEntry("os", "Linux 5.10.0")
                .containsEntry("uptime", "1d 2h 3m 4s")
                .containsEntry("cores", 16);
        // LinkedHashMap 순서 보존 검증 (원본 카드 표시 순서)
        assertThat(r.keySet()).containsExactly("hostname", "os", "uptime", "cores");
    }

    @Test
    void vitals_buildsCpuMemoryWithStatus_ok() {
        given(procReader.readCpuPercent())
                .willReturn(new ProcReader.CpuStat(10.0, 5.0, 3.0, 1.0));
        given(procReader.readMemory())
                .willReturn(new ProcReader.MemoryStat(16.0, 4.0, 12.0, 25.0));

        Map<String, Object> v = service.vitals();

        @SuppressWarnings("unchecked")
        Map<String, Object> cpu = (Map<String, Object>) v.get("cpu");
        @SuppressWarnings("unchecked")
        Map<String, Object> mem = (Map<String, Object>) v.get("mem");

        assertThat(cpu).containsEntry("percent", 10.0)
                .containsEntry("user", 5.0)
                .containsEntry("system", 3.0)
                .containsEntry("iowait", 1.0)
                .containsEntry("status", "ok");
        assertThat(mem).containsEntry("percent", 25.0)
                .containsEntry("total_gb", 16.0)
                .containsEntry("used_gb", 4.0)
                .containsEntry("free_gb", 12.0)
                .containsEntry("status", "ok");
    }

    @Test
    void vitals_status_warning_atCpuWarn() {
        given(procReader.readCpuPercent())
                .willReturn(new ProcReader.CpuStat(70.0, 65.0, 5.0, 0.0));
        given(procReader.readMemory())
                .willReturn(new ProcReader.MemoryStat(16.0, 14.0, 2.0, 87.0));

        Map<String, Object> v = service.vitals();
        @SuppressWarnings("unchecked")
        Map<String, Object> cpu = (Map<String, Object>) v.get("cpu");
        @SuppressWarnings("unchecked")
        Map<String, Object> mem = (Map<String, Object>) v.get("mem");

        // CPU 70% → ≥60 warn, <80 crit → warning
        assertThat(cpu).containsEntry("status", "warning");
        // Mem 87% → ≥80 warn, <90 crit → warning
        assertThat(mem).containsEntry("status", "warning");
    }

    @Test
    void vitals_status_critical_atOrAboveCrit() {
        given(procReader.readCpuPercent())
                .willReturn(new ProcReader.CpuStat(80.0, 60.0, 18.0, 2.0));
        given(procReader.readMemory())
                .willReturn(new ProcReader.MemoryStat(16.0, 15.0, 1.0, 95.0));

        Map<String, Object> v = service.vitals();
        @SuppressWarnings("unchecked")
        Map<String, Object> cpu = (Map<String, Object>) v.get("cpu");
        @SuppressWarnings("unchecked")
        Map<String, Object> mem = (Map<String, Object>) v.get("mem");

        // CPU 80% → ≥80 crit (경계 포함)
        assertThat(cpu).containsEntry("status", "critical");
        assertThat(mem).containsEntry("status", "critical");
    }

    @Test
    void pctStatus_boundary() {
        // 원본 _pct_status 와 동일: ≥crit critical, ≥warn warning, else ok
        assertThat(OverviewService.pctStatus(59.9, 60, 80)).isEqualTo("ok");
        assertThat(OverviewService.pctStatus(60.0, 60, 80)).isEqualTo("warning");
        assertThat(OverviewService.pctStatus(79.9, 60, 80)).isEqualTo("warning");
        assertThat(OverviewService.pctStatus(80.0, 60, 80)).isEqualTo("critical");
        assertThat(OverviewService.pctStatus(100.0, 60, 80)).isEqualTo("critical");
    }
}
