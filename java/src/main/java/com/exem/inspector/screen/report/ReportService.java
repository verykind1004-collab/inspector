package com.exem.inspector.screen.report;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

import com.exem.inspector.common.db.DbType;
import com.exem.inspector.config.ServiceConfig;
import com.exem.inspector.screen.overview.OverviewDiskService;
import com.exem.inspector.screen.overview.OverviewServicesService;
import com.exem.inspector.screen.overview.ProcReader;

/**
 * MaxGauge Daily Report 통합 서비스 — 원본 page_report() 의 데이터 부분과 1:1 동등.
 *
 * <p>5블록 데이터:
 * (1) 4 stat 카드 — CPU/Memory(어제 평균 또는 현재) + Disk(TBS worst 또는 PG) + Instances
 * (3) 12개월 Check Resource — INSP_MONTHLY_SUMMARY, 누락월은 cpu/mem/disk null (현재월은 현재값 fallback)
 * (4) Check Status STATUS_GROUPS — 4그룹 × 항목, default OK (서비스 상태 기반 자동 분기 일부)
 *
 * <p>고객사명/지원제품 + 특이사항 + 점검일/엔지니어/고객확인/서명 은 FE contenteditable 영역(서버 데이터 없음).
 * License 카드/Check Status License 행은 원본 페이지에 없으므로 제거.
 */
@Service
public class ReportService {

    private static final Logger log = LoggerFactory.getLogger(ReportService.class);

    private static final DateTimeFormatter YYYY_MM_DD = DateTimeFormatter.ofPattern("yyyy-MM-dd");

    private final ObjectProvider<ReportMapper> mapperProvider;
    private final ServiceConfig serviceConfig;
    private final ProcReader procReader;
    private final OverviewDiskService diskService;
    private final OverviewServicesService servicesService;

    public ReportService(ObjectProvider<ReportMapper> mapperProvider,
                         ServiceConfig serviceConfig,
                         ProcReader procReader,
                         OverviewDiskService diskService,
                         OverviewServicesService servicesService) {
        this.mapperProvider = mapperProvider;
        this.serviceConfig = serviceConfig;
        this.procReader = procReader;
        this.diskService = diskService;
        this.servicesService = servicesService;
    }

    public ReportPayload build() {
        LocalDate today = LocalDate.now();
        LocalDate yesterday = today.minusDays(1);
        String yStr = yesterday.format(YYYY_MM_DD);
        String tStr = today.format(YYYY_MM_DD);

        DbType dbType = DbType.fromConfigValue(serviceConfig.repository().dbType());
        ReportMapper mapper = mapperProvider.getIfAvailable();

        // ── 1. CPU/Memory — INSP_OS_HISTORY 어제 평균 우선, 없으면 현재값 ─────
        double cpuPct, memUsedGb, memTotalGb, memPct;
        String cpuLabel, memLabel;
        boolean usedYesterdayAvg = false;

        if (mapper != null) {
            try {
                LinkedHashMap<String, Object> avg = mapper.findYesterdayOsAvg(yStr, tStr);
                Object cObj = avg == null ? null : avg.get("cnt");
                Integer cnt = cObj == null ? null : ((Number) cObj).intValue();
                if (cnt != null && cnt > 0) {
                    cpuPct     = dbl(avg.get("cpu_percent"));
                    memTotalGb = dbl(avg.get("mem_total_gb"));
                    memUsedGb  = dbl(avg.get("mem_used_gb"));
                    memPct     = dbl(avg.get("mem_percent"));
                    cpuLabel = "AVG CPU (" + yStr + ")";
                    memLabel = "AVG Memory (" + yStr + ")";
                    usedYesterdayAvg = true;
                } else {
                    double[] cur = fallbackCurrent();
                    cpuPct = cur[0]; memUsedGb = cur[1]; memTotalGb = cur[2]; memPct = cur[3];
                    cpuLabel = "CPU"; memLabel = "Memory";
                }
            } catch (RuntimeException e) {
                log.warn("INSP_OS_HISTORY 어제 평균 실패 — 현재값으로 fallback", e);
                double[] cur = fallbackCurrent();
                cpuPct = cur[0]; memUsedGb = cur[1]; memTotalGb = cur[2]; memPct = cur[3];
                cpuLabel = "CPU"; memLabel = "Memory";
            }
        } else {
            double[] cur = fallbackCurrent();
            cpuPct = cur[0]; memUsedGb = cur[1]; memTotalGb = cur[2]; memPct = cur[3];
            cpuLabel = "CPU"; memLabel = "Memory";
        }

        // ── 2. Disk — Oracle 은 worst tablespace, PG 는 pg disk ──────────────
        DiskAgg disk = aggregateDisk(dbType);

        // ── 3. Instance count (4번째 stat 카드) ──────────────────────────────
        int instanceCount = 0;
        if (mapper != null) {
            try { instanceCount = mapper.countInstances(); }
            catch (RuntimeException e) { log.warn("instance count 실패", e); }
        }

        // ── 4. Services 상태 (내부 사용 — Check Status default 판정용) ───────
        List<Map<String, Object>> services = collectServices();

        // ── 5. Monthly Resource Summary (12개월) ─────────────────────────────
        List<ReportPayload.MonthlySnapshot> monthly = buildMonthly(mapper, today.getYear(),
                today.getMonthValue(), cpuPct, memPct, disk.percent);

        // ── 6. Check Status STATUS_GROUPS (원본 page_report STATUS_GROUPS) ───
        List<ReportPayload.StatusGroup> statusGroups = buildStatusGroups(services);

        return new ReportPayload(
                tStr,
                cpuLabel, cpuPct,
                memLabel, memUsedGb, memTotalGb, memPct,
                disk.label, disk.usedGb, disk.totalGb, disk.percent,
                instanceCount,
                usedYesterdayAvg,
                monthly,
                statusGroups);
    }

    private double[] fallbackCurrent() {
        ProcReader.CpuStat cpu = procReader.readCpuPercent();
        ProcReader.MemoryStat mem = procReader.readMemory();
        return new double[] { cpu.getPercent(), mem.getUsedGb(), mem.getTotalGb(), mem.getPercent() };
    }

    @SuppressWarnings("unchecked")
    private DiskAgg aggregateDisk(DbType dbType) {
        try {
            Map<String, Object> disk = diskService.disk();
            String type = String.valueOf(disk.get("type"));
            if ("disk".equals(type)) {
                return new DiskAgg("Disk",
                        dbl(disk.get("used_gb")), dbl(disk.get("total_gb")), dbl(disk.get("percent")));
            }
            // tablespace 타입: items[] 중 percent 최대값 행 (원본 worst = max by percent)
            Object itemsObj = disk.get("items");
            if (!(itemsObj instanceof List)) return new DiskAgg("TBS", 0, 0, 0);
            List<Map<String, Object>> items = (List<Map<String, Object>>) itemsObj;
            Map<String, Object> worst = null;
            double worstPct = -1;
            for (Map<String, Object> r : items) {
                double p = dbl(r.get("percent"));
                if (p > worstPct) { worstPct = p; worst = r; }
            }
            if (worst == null) return new DiskAgg("TBS", 0, 0, 0);
            return new DiskAgg("TBS",
                    dbl(worst.get("used_gb")), dbl(worst.get("total_gb")), dbl(worst.get("percent")));
        } catch (RuntimeException e) {
            log.warn("disk 조회 실패", e);
            return new DiskAgg(dbType == DbType.POSTGRESQL ? "Disk" : "TBS", 0, 0, 0);
        }
    }

    private List<Map<String, Object>> collectServices() {
        List<Map<String, Object>> services = new ArrayList<>();
        try {
            Map<String, Object> svc = servicesService.services();
            Object rowsObj = svc.get("services");
            if (rowsObj instanceof List) {
                for (Object r : (List<?>) rowsObj) {
                    if (r instanceof Map) {
                        @SuppressWarnings("unchecked")
                        Map<String, Object> rowMap = (Map<String, Object>) r;
                        services.add(rowMap);
                    }
                }
            }
        } catch (RuntimeException e) {
            log.warn("services 조회 실패", e);
        }
        return services;
    }

    /**
     * 원본 _monthly_resource_data + page_report() 의 cur_month fallback 로직 1:1.
     * 누락 월은 null 셀. 현재월에 데이터 없으면 현재 cpu/mem/disk percent 로 채움.
     */
    private List<ReportPayload.MonthlySnapshot> buildMonthly(ReportMapper mapper,
                                                              int year,
                                                              int curMonth,
                                                              double curCpu,
                                                              double curMem,
                                                              double curDisk) {
        Map<Integer, double[]> data = new LinkedHashMap<>();   // month -> [cpuAvg, memAvg, diskAvg]
        if (mapper != null) {
            try {
                List<LinkedHashMap<String, Object>> rows =
                        mapper.findMonthlyResourceSummary(year + "-%");
                if (rows != null) {
                    for (LinkedHashMap<String, Object> r : rows) {
                        String ym = String.valueOf(r.get("year_month"));
                        int month;
                        try {
                            month = Integer.parseInt(ym.split("-")[1]);
                        } catch (RuntimeException e) {
                            continue;
                        }
                        Double cpu = nbl(r.get("cpu_avg"));
                        Double mem = nbl(r.get("mem_avg"));
                        Double dsk = nbl(r.get("disk_avg"));
                        data.put(month, new double[] {
                                cpu == null ? Double.NaN : cpu,
                                mem == null ? Double.NaN : mem,
                                dsk == null ? Double.NaN : dsk });
                    }
                }
            } catch (RuntimeException e) {
                log.warn("monthly summary 조회 실패", e);
            }
        }

        // 현재월 데이터 없으면 현재값으로 채움 (원본 page_report cur_month fallback)
        if (!data.containsKey(curMonth)) {
            data.put(curMonth, new double[] { curCpu, curMem, curDisk });
        }

        List<ReportPayload.MonthlySnapshot> out = new ArrayList<>(12);
        for (int m = 1; m <= 12; m++) {
            double[] v = data.get(m);
            if (v == null) {
                out.add(new ReportPayload.MonthlySnapshot(m, null, null, null));
            } else {
                out.add(new ReportPayload.MonthlySnapshot(m,
                        Double.isNaN(v[0]) ? null : v[0],
                        Double.isNaN(v[1]) ? null : v[1],
                        Double.isNaN(v[2]) ? null : v[2]));
            }
        }
        return out;
    }

    /**
     * 원본 STATUS_GROUPS 4그룹 — 토글 가능(클라이언트), 서비스 상태 기반 default 분기.
     * DG/PJS 동작점검만 services 상태로 default 판정, 나머지는 기본 OK (원본 _rtog 와 동등).
     */
    private List<ReportPayload.StatusGroup> buildStatusGroups(List<Map<String, Object>> services) {
        boolean dgOk = anyServiceRunning(services, "DGServer");
        boolean pjsOk = anyServiceRunning(services, "PlatformJS");
        boolean agentOk = dgOk || pjsOk;   // Agent 동작은 DG/PJS 중 하나 이상 running

        return Arrays.asList(
                new ReportPayload.StatusGroup("프로세스 점검", Arrays.asList(
                        new ReportPayload.StatusItem("Agent 동작점검", agentOk),
                        new ReportPayload.StatusItem("DG 동작점검", dgOk),
                        new ReportPayload.StatusItem("PJS 동작점검", pjsOk))),
                new ReportPayload.StatusGroup("수집상태 점검", Arrays.asList(
                        new ReportPayload.StatusItem("os stat 수집점검", true),
                        new ReportPayload.StatusItem("db stat 수집점검", true),
                        new ReportPayload.StatusItem("session stat 수집점검", true),
                        new ReportPayload.StatusItem("sql stat 수집점검", true))),
                new ReportPayload.StatusGroup("Real-Time Monitor", Arrays.asList(
                        new ReportPayload.StatusItem("CPU/Memory", true),
                        new ReportPayload.StatusItem("Trend Chart", true),
                        new ReportPayload.StatusItem("SQL Elapsed Time", true),
                        new ReportPayload.StatusItem("Active Sessions", true),
                        new ReportPayload.StatusItem("Script Manager", true))),
                new ReportPayload.StatusGroup("Performance Analyzer", Arrays.asList(
                        new ReportPayload.StatusItem("Top-N Analysis", true),
                        new ReportPayload.StatusItem("Performance Trend", true),
                        new ReportPayload.StatusItem("Long-Term Trend", true),
                        new ReportPayload.StatusItem("Session/SQL List", true),
                        new ReportPayload.StatusItem("Capacity Planning", true))));
    }

    private boolean anyServiceRunning(List<Map<String, Object>> services, String namePrefix) {
        for (Map<String, Object> s : services) {
            String name = str(s.get("name"));
            String status = str(s.get("status"));
            if (name.startsWith(namePrefix) || name.contains(namePrefix)) {
                if ("running".equals(status)) return true;
            }
        }
        return false;
    }

    private static double dbl(Object o) {
        if (o == null) return 0;
        if (o instanceof Number) return ((Number) o).doubleValue();
        try { return Double.parseDouble(String.valueOf(o)); }
        catch (NumberFormatException e) { return 0; }
    }

    /** null-safe Double; 변환 실패 시 null. */
    private static Double nbl(Object o) {
        if (o == null) return null;
        if (o instanceof Number) return ((Number) o).doubleValue();
        try { return Double.parseDouble(String.valueOf(o)); }
        catch (NumberFormatException e) { return null; }
    }

    private static String str(Object o) { return o == null ? "" : String.valueOf(o); }

    private static final class DiskAgg {
        final String label; final double usedGb; final double totalGb; final double percent;
        DiskAgg(String label, double usedGb, double totalGb, double percent) {
            this.label = label; this.usedGb = usedGb; this.totalGb = totalGb; this.percent = percent;
        }
    }
}
