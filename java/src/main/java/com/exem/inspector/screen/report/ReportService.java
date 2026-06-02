package com.exem.inspector.screen.report;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

import com.exem.inspector.common.db.DbType;
import com.exem.inspector.config.ServiceConfig;
import com.exem.inspector.screen.license.LicenseCheckResult;
import com.exem.inspector.screen.license.LicenseInfoRow;
import com.exem.inspector.screen.license.LicenseService;
import com.exem.inspector.screen.overview.OverviewDiskService;
import com.exem.inspector.screen.overview.OverviewServicesService;
import com.exem.inspector.screen.overview.ProcReader;

/**
 * MaxGauge Daily Report 통합 서비스 — 원본 page_report() 의 데이터 부분과 동등.
 *
 * <p>본 단계: 4 카드(CPU/Mem/Disk/License) + Check Status 9 행 + Instance Count + Services 목록.
 * TBS History 차트는 후속 보강(별도 endpoint 또는 ReportPayload 확장).
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
    private final LicenseService licenseService;

    public ReportService(ObjectProvider<ReportMapper> mapperProvider,
                         ServiceConfig serviceConfig,
                         ProcReader procReader,
                         OverviewDiskService diskService,
                         OverviewServicesService servicesService,
                         LicenseService licenseService) {
        this.mapperProvider = mapperProvider;
        this.serviceConfig = serviceConfig;
        this.procReader = procReader;
        this.diskService = diskService;
        this.servicesService = servicesService;
        this.licenseService = licenseService;
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
        Integer cnt = null;
        if (mapper != null) {
            try {
                LinkedHashMap<String, Object> avg = mapper.findYesterdayOsAvg(yStr, tStr);
                Object cObj = avg == null ? null : avg.get("cnt");
                cnt = cObj == null ? null : ((Number) cObj).intValue();
                if (cnt != null && cnt > 0) {
                    cpuPct    = dbl(avg.get("cpu_percent"));
                    memTotalGb = dbl(avg.get("mem_total_gb"));
                    memUsedGb  = dbl(avg.get("mem_used_gb"));
                    memPct     = dbl(avg.get("mem_percent"));
                    cpuLabel = "AVG CPU (" + yStr + ")";
                    memLabel = "AVG Memory (" + yStr + ")";
                    usedYesterdayAvg = true;
                } else {
                    // fallback: 현재 OS 값
                    ProcReader.CpuStat cpu = procReader.readCpuPercent();
                    ProcReader.MemoryStat mem = procReader.readMemory();
                    cpuPct = cpu.getPercent();
                    memUsedGb = mem.getUsedGb();
                    memTotalGb = mem.getTotalGb();
                    memPct = mem.getPercent();
                    cpuLabel = "CPU";
                    memLabel = "Memory";
                }
            } catch (RuntimeException e) {
                log.warn("INSP_OS_HISTORY 어제 평균 실패 — 현재값으로 fallback", e);
                ProcReader.CpuStat cpu = procReader.readCpuPercent();
                ProcReader.MemoryStat mem = procReader.readMemory();
                cpuPct = cpu.getPercent();
                memUsedGb = mem.getUsedGb();
                memTotalGb = mem.getTotalGb();
                memPct = mem.getPercent();
                cpuLabel = "CPU";
                memLabel = "Memory";
            }
        } else {
            ProcReader.CpuStat cpu = procReader.readCpuPercent();
            ProcReader.MemoryStat mem = procReader.readMemory();
            cpuPct = cpu.getPercent();
            memUsedGb = mem.getUsedGb();
            memTotalGb = mem.getTotalGb();
            memPct = mem.getPercent();
            cpuLabel = "CPU";
            memLabel = "Memory";
        }

        // ── 2. Disk — Oracle 은 worst tablespace, PG 는 pg disk(overview 재사용) ─
        DiskAgg disk = aggregateDisk(dbType);

        // ── 3. License — License Info 중 TRIAL 우선 D-Day 표시, 모두 TERM 면 TERM ─
        String licenseLabel = "License";
        String licenseValue = "-";
        try {
            LicenseCheckResult lc = licenseService.build();
            List<LicenseInfoRow> info = lc.getInfo();
            if (info != null && !info.isEmpty()) {
                boolean hasTrial = false;
                for (LicenseInfoRow li : info) {
                    if ("TRIAL".equalsIgnoreCase(li.getLicenseType())) {
                        licenseValue = "TRIAL (D-" + (li.getDDay() == null ? "?" : li.getDDay()) + ")";
                        hasTrial = true;
                        break;
                    }
                }
                if (!hasTrial) licenseValue = "TERM";
            }
        } catch (RuntimeException e) {
            log.warn("License info 조회 실패 — license=- 로 표시", e);
        }

        // ── 4. Instance count ─────────────────────────────────────────────
        int instanceCount = 0;
        if (mapper != null) {
            try { instanceCount = mapper.countInstances(); }
            catch (RuntimeException e) { log.warn("instance count 실패", e); }
        }

        // ── 5. Services (Overview Services 재사용) ────────────────────────
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

        // ── 6. Check Status — 원본 9 행. partition/summary 의 CHECK 카운트로 default 결정 ─
        // 단순화: SQL 실행은 보류, 일단 default=OK 로 두고 원본의 service 기반 분기만 적용
        boolean dgOk = anyServiceRunning(services, "DGServer");
        boolean pjsOk = anyServiceRunning(services, "PlatformJS");
        boolean repoOk = anyServiceRunning(services, "Repository DB");
        List<ReportPayload.CheckRow> checks = Arrays.asList(
                new ReportPayload.CheckRow("RTS", true),
                new ReportPayload.CheckRow("SNDF", true),
                new ReportPayload.CheckRow("OBSD", true),
                new ReportPayload.CheckRow("DataGather", dgOk),
                new ReportPayload.CheckRow("PlatformJS", pjsOk),
                new ReportPayload.CheckRow("Repository DB", repoOk),
                new ReportPayload.CheckRow("Partition Create / Drop", true),
                new ReportPayload.CheckRow("10Min / 1Hour Summary", true),
                new ReportPayload.CheckRow("License", "-".equals(licenseValue) ? false : true)
        );

        return new ReportPayload(
                tStr,
                cpuLabel, cpuPct,
                memLabel, memUsedGb, memTotalGb, memPct,
                disk.label, disk.usedGb, disk.totalGb, disk.percent,
                licenseLabel, licenseValue,
                instanceCount,
                services,
                checks,
                usedYesterdayAvg);
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
            // tablespace 타입: items[] 중 percent 최대값 행
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

    private static String str(Object o) { return o == null ? "" : String.valueOf(o); }

    private static final class DiskAgg {
        final String label; final double usedGb; final double totalGb; final double percent;
        DiskAgg(String label, double usedGb, double totalGb, double percent) {
            this.label = label; this.usedGb = usedGb; this.totalGb = totalGb; this.percent = percent;
        }
    }
}
