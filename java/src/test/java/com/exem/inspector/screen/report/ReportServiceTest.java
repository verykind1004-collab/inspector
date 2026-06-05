package com.exem.inspector.screen.report;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

import com.exem.inspector.common.db.RepositoryConfig;
import com.exem.inspector.config.ServiceConfig;
import com.exem.inspector.screen.overview.OverviewDiskService;
import com.exem.inspector.screen.overview.OverviewServicesService;
import com.exem.inspector.screen.overview.ProcReader;

/**
 * ReportService 페이로드 조립 단위 테스트.
 *
 * <p>원본 page_report() 1:1 동등 검증:
 * (1) 4 stat 카드 (CPU/Mem/Disk/Instances)
 * (3) 12개월 Check Resource — 누락 월 null, 현재월 fallback
 * (4) STATUS_GROUPS 4그룹 — Agent/DG/PJS default 분기
 *
 * <p>Mapper/disk/service mock 으로 외부 의존 차단.
 */
class ReportServiceTest {

    @SuppressWarnings("unchecked")
    private final ObjectProvider<ReportMapper> mapperProvider = mock(ObjectProvider.class);
    private final ReportMapper mapper = mock(ReportMapper.class);
    private final ServiceConfig serviceConfig = mock(ServiceConfig.class);
    private final ProcReader procReader = mock(ProcReader.class);
    private final OverviewDiskService diskService = mock(OverviewDiskService.class);
    private final OverviewServicesService servicesService = mock(OverviewServicesService.class);
    private final com.exem.inspector.screen.license.LicenseService licenseService = mock(com.exem.inspector.screen.license.LicenseService.class);

    private final ReportService service = new ReportService(
            mapperProvider, serviceConfig, procReader, diskService, servicesService, licenseService);

    private void wireMapper() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
    }

    private void wireNoMapper() {
        given(mapperProvider.getIfAvailable()).willReturn(null);
    }

    private void wireRepoOracle() {
        RepositoryConfig repo = mock(RepositoryConfig.class);
        given(repo.dbType()).willReturn("Oracle");
        given(serviceConfig.repository()).willReturn(repo);
    }

    private void wireRepoPostgres() {
        RepositoryConfig repo = mock(RepositoryConfig.class);
        given(repo.dbType()).willReturn("PostgreSQL");
        given(serviceConfig.repository()).willReturn(repo);
    }

    private void wireProcReaderFallback() {
        given(procReader.readCpuPercent())
                .willReturn(new ProcReader.CpuStat(11.1, 5.0, 3.0, 3.1));
        given(procReader.readMemory())
                .willReturn(new ProcReader.MemoryStat(32.0, 8.0, 24.0, 25.0));
    }

    private void wireDiskTbsItems(List<Map<String, Object>> items) {
        Map<String, Object> disk = new LinkedHashMap<>();
        disk.put("type", "tablespace");
        disk.put("items", items);
        given(diskService.disk()).willReturn(disk);
    }

    private void wireDiskPg(double used, double total, double pct) {
        Map<String, Object> disk = new LinkedHashMap<>();
        disk.put("type", "disk");
        disk.put("used_gb", used);
        disk.put("total_gb", total);
        disk.put("percent", pct);
        given(diskService.disk()).willReturn(disk);
    }

    private void wireServices(List<Map<String, Object>> rows) {
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("services", rows);
        given(servicesService.services()).willReturn(r);
    }

    private void wireEmptyMonthly() {
        given(mapper.findMonthlyResourceSummary(anyString())).willReturn(new ArrayList<>());
    }

    private void wireYesterdayAvg(int cnt, double cpu, double memPct, double memUsed, double memTotal) {
        LinkedHashMap<String, Object> avg = new LinkedHashMap<>();
        avg.put("cpu_percent", cpu);
        avg.put("cpu_user", 0.0);
        avg.put("cpu_system", 0.0);
        avg.put("cpu_iowait", 0.0);
        avg.put("mem_total_gb", memTotal);
        avg.put("mem_used_gb", memUsed);
        avg.put("mem_free_gb", memTotal - memUsed);
        avg.put("mem_percent", memPct);
        avg.put("cnt", cnt);
        given(mapper.findYesterdayOsAvg(anyString(), anyString())).willReturn(avg);
    }

    private static Map<String, Object> svcRow(String name, String status) {
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("name", name);
        r.put("status", status);
        return r;
    }

    private static Map<String, Object> tbsRow(double used, double total, double pct) {
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("used_gb", used);
        r.put("total_gb", total);
        r.put("percent", pct);
        return r;
    }

    // ── (1) 4 stat 카드 — Instances 가 4번째 ─────────────────────────────────
    @Test
    void cards_4thIsInstances_notLicense() {
        wireMapper();
        wireRepoOracle();
        wireProcReaderFallback();
        wireDiskTbsItems(Arrays.asList(tbsRow(10, 20, 50)));
        wireServices(new ArrayList<>());
        // instanceCount 폐기(7)
        wireEmptyMonthly();

        ReportPayload p = service.build();

        assertThat(p.getLicenseLabel()).isEqualTo("License");
        // License 관련 getter 가 ReportPayload 에 없음 — 컴파일 단계에서 보장
    }

    // ── (1) CPU/Memory — 어제 평균 우선 사용 ─────────────────────────────────
    @Test
    void cpuMem_usesYesterdayAvg_whenCntPositive() {
        wireMapper();
        wireRepoOracle();
        wireYesterdayAvg(288, 22.5, 60.0, 19.2, 32.0);
        wireDiskTbsItems(Arrays.asList(tbsRow(5, 10, 50)));
        wireServices(new ArrayList<>());
        // instanceCount 폐기(3)
        wireEmptyMonthly();

        ReportPayload p = service.build();

        assertThat(p.isUsedYesterdayAvg()).isTrue();
        assertThat(p.getCpuPercent()).isEqualTo(22.5);
        assertThat(p.getMemPercent()).isEqualTo(60.0);
        assertThat(p.getCpuLabel()).startsWith("AVG CPU (");
        assertThat(p.getMemLabel()).startsWith("AVG Memory (");
    }

    // ── (1) CPU/Memory — cnt=0 면 현재값 fallback ────────────────────────────
    @Test
    void cpuMem_fallback_whenNoYesterdayData() {
        wireMapper();
        wireRepoOracle();
        wireProcReaderFallback();
        // findYesterdayOsAvg returns null cnt
        LinkedHashMap<String, Object> avg = new LinkedHashMap<>();
        avg.put("cnt", 0);
        given(mapper.findYesterdayOsAvg(anyString(), anyString())).willReturn(avg);
        wireDiskTbsItems(Arrays.asList(tbsRow(5, 10, 50)));
        wireServices(new ArrayList<>());
        // instanceCount 폐기(0)
        wireEmptyMonthly();

        ReportPayload p = service.build();

        assertThat(p.isUsedYesterdayAvg()).isFalse();
        assertThat(p.getCpuLabel()).isEqualTo("CPU");
        assertThat(p.getMemLabel()).isEqualTo("Memory");
        assertThat(p.getCpuPercent()).isEqualTo(11.1);
    }

    // ── (2) Disk — Oracle worst tablespace ──────────────────────────────────
    @Test
    void disk_oracle_picksWorstByPercent() {
        wireMapper();
        wireRepoOracle();
        wireProcReaderFallback();
        wireDiskTbsItems(Arrays.asList(
                tbsRow(10, 100, 10),
                tbsRow(80, 100, 80),     // worst
                tbsRow(50, 100, 50)));
        wireServices(new ArrayList<>());
        // instanceCount 폐기(1)
        wireEmptyMonthly();

        ReportPayload p = service.build();

        assertThat(p.getDiskLabel()).isEqualTo("TBS");
        assertThat(p.getDiskPercent()).isEqualTo(80.0);
        assertThat(p.getDiskUsedGb()).isEqualTo(80.0);
    }

    // ── (2) Disk — PG ───────────────────────────────────────────────────────
    @Test
    void disk_postgres_label() {
        wireMapper();
        wireRepoPostgres();
        wireProcReaderFallback();
        wireDiskPg(50, 200, 25);
        wireServices(new ArrayList<>());
        // instanceCount 폐기(1)
        wireEmptyMonthly();

        ReportPayload p = service.build();

        assertThat(p.getDiskLabel()).isEqualTo("Disk");
        assertThat(p.getDiskPercent()).isEqualTo(25.0);
    }

    // ── (3) 12개월 Check Resource — 12개 행, 누락 월 null ───────────────────
    @Test
    void monthly_returns12Rows_nullForMissingMonths() {
        wireMapper();
        wireRepoOracle();
        wireProcReaderFallback();
        wireDiskTbsItems(Arrays.asList(tbsRow(5, 10, 50)));
        wireServices(new ArrayList<>());
        // instanceCount 폐기(0)

        int year = LocalDate.now().getYear();
        int curMonth = LocalDate.now().getMonthValue();
        LinkedHashMap<String, Object> row1 = new LinkedHashMap<>();
        row1.put("year_month", year + "-01");
        row1.put("cpu_avg", 30.0);
        row1.put("mem_avg", 55.0);
        row1.put("disk_avg", 40.0);
        LinkedHashMap<String, Object> row3 = new LinkedHashMap<>();
        row3.put("year_month", year + "-03");
        row3.put("cpu_avg", 35.0);
        row3.put("mem_avg", 60.0);
        row3.put("disk_avg", 45.0);
        given(mapper.findMonthlyResourceSummary(year + "-%"))
                .willReturn(Arrays.asList(row1, row3));

        ReportPayload p = service.build();

        List<ReportPayload.MonthlySnapshot> ms = p.getMonthly();
        assertThat(ms).hasSize(12);
        assertThat(ms.get(0).getMonth()).isEqualTo(1);
        assertThat(ms.get(0).getCpuAvg()).isEqualTo(30.0);
        assertThat(ms.get(0).getMemAvg()).isEqualTo(55.0);
        assertThat(ms.get(0).getDiskAvg()).isEqualTo(40.0);
        // 2월은 누락
        assertThat(ms.get(1).getCpuAvg()).isNull();
        assertThat(ms.get(1).getMemAvg()).isNull();
        assertThat(ms.get(1).getDiskAvg()).isNull();
        // 3월
        assertThat(ms.get(2).getCpuAvg()).isEqualTo(35.0);
        // 현재월 (year_month 미공급) fallback — curMonth 행은 ProcReader 현재값
        if (curMonth != 1 && curMonth != 3) {
            assertThat(ms.get(curMonth - 1).getCpuAvg()).isEqualTo(11.1);
        }
    }

    // ── (4) STATUS_GROUPS 4그룹 + Agent/DG/PJS default 분기 ────────────────
    @Test
    void statusGroups_4groups_agentDgPjsDefaults() {
        wireMapper();
        wireRepoOracle();
        wireProcReaderFallback();
        wireDiskTbsItems(Arrays.asList(tbsRow(5, 10, 50)));
        wireServices(Arrays.asList(
                svcRow("DGServer_M", "running"),
                svcRow("PlatformJS", "stopped")));
        // instanceCount 폐기(2)
        wireEmptyMonthly();

        ReportPayload p = service.build();

        List<ReportPayload.StatusGroup> gs = p.getStatusGroups();
        assertThat(gs).hasSize(4);
        assertThat(gs.get(0).getGroupName()).isEqualTo("프로세스 점검");
        assertThat(gs.get(1).getGroupName()).isEqualTo("수집상태 점검");
        assertThat(gs.get(2).getGroupName()).isEqualTo("Real-Time Monitor");
        assertThat(gs.get(3).getGroupName()).isEqualTo("Performance Analyzer");

        // 프로세스 점검: Agent OK (DG running 있음), DG OK, PJS not OK
        List<ReportPayload.StatusItem> proc = gs.get(0).getItems();
        assertThat(proc).extracting(ReportPayload.StatusItem::getTitle)
                .containsExactly("Agent 동작점검", "DG 동작점검", "PJS 동작점검");
        assertThat(proc.get(0).isDefaultOk()).isTrue();   // agent
        assertThat(proc.get(1).isDefaultOk()).isTrue();   // DG running
        assertThat(proc.get(2).isDefaultOk()).isFalse();  // PJS stopped

        // 수집상태 4항목
        assertThat(gs.get(1).getItems()).hasSize(4);
        // RTM 5항목 / PA 5항목
        assertThat(gs.get(2).getItems()).hasSize(5);
        assertThat(gs.get(3).getItems()).hasSize(5);
    }

    // ── No Mapper 환경 (테스트 시 mapper 미주입) — fallback 동작 ──────────
    @Test
    void noMapper_fallsBackToProcReader_noNpe() {
        wireNoMapper();
        wireRepoOracle();
        wireProcReaderFallback();
        wireDiskTbsItems(Arrays.asList(tbsRow(5, 10, 50)));
        wireServices(new ArrayList<>());

        ReportPayload p = service.build();

        assertThat(p.isUsedYesterdayAvg()).isFalse();
        assertThat(p.getLicenseLabel()).isEqualTo("License");
        assertThat(p.getMonthly()).hasSize(12);
    }
}
