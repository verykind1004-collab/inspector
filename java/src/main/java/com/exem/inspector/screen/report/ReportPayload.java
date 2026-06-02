package com.exem.inspector.screen.report;

import java.util.List;
import java.util.Map;

import com.exem.inspector.screen.license.LicenseInfoRow;

/**
 * MaxGauge Daily Report 통합 응답.
 *
 * <p>원본 page_report() 의 4 카드 + Check Status + Instance Count + TBS 차트 데이터.
 * 본 단계는 핵심 데이터(4 카드 + Check Status + Instance Count) 까지. TBS History 차트는 후속.
 */
public class ReportPayload {

    private final String reportDate;       // YYYY-MM-DD (now)
    private final String cpuLabel;         // "AVG CPU (yyyy-MM-dd)" 또는 "CPU"
    private final double cpuPercent;
    private final String memLabel;
    private final double memUsedGb;
    private final double memTotalGb;
    private final double memPercent;
    private final String diskLabel;        // "TBS"(Oracle) / "Disk"(PG)
    private final double diskUsedGb;
    private final double diskTotalGb;
    private final double diskPercent;
    private final String licenseLabel;     // "License"
    private final String licenseValue;     // "TRIAL (D-28)" 또는 "TERM" 또는 "-"
    private final int instanceCount;       // apm_db_info count
    private final List<Map<String, Object>> services;  // [{name, status, port, version}]
    private final List<CheckRow> checks;   // RTS/SNDF/.../License 9 행
    private final boolean usedYesterdayAvg; // true 면 INSP_OS_HISTORY 어제 평균, false 면 현재값(fallback)

    public ReportPayload(String reportDate,
                         String cpuLabel, double cpuPercent,
                         String memLabel, double memUsedGb, double memTotalGb, double memPercent,
                         String diskLabel, double diskUsedGb, double diskTotalGb, double diskPercent,
                         String licenseLabel, String licenseValue,
                         int instanceCount,
                         List<Map<String, Object>> services,
                         List<CheckRow> checks,
                         boolean usedYesterdayAvg) {
        this.reportDate = reportDate;
        this.cpuLabel = cpuLabel;
        this.cpuPercent = cpuPercent;
        this.memLabel = memLabel;
        this.memUsedGb = memUsedGb;
        this.memTotalGb = memTotalGb;
        this.memPercent = memPercent;
        this.diskLabel = diskLabel;
        this.diskUsedGb = diskUsedGb;
        this.diskTotalGb = diskTotalGb;
        this.diskPercent = diskPercent;
        this.licenseLabel = licenseLabel;
        this.licenseValue = licenseValue;
        this.instanceCount = instanceCount;
        this.services = services;
        this.checks = checks;
        this.usedYesterdayAvg = usedYesterdayAvg;
    }

    public String getReportDate() { return reportDate; }
    public String getCpuLabel() { return cpuLabel; }
    public double getCpuPercent() { return cpuPercent; }
    public String getMemLabel() { return memLabel; }
    public double getMemUsedGb() { return memUsedGb; }
    public double getMemTotalGb() { return memTotalGb; }
    public double getMemPercent() { return memPercent; }
    public String getDiskLabel() { return diskLabel; }
    public double getDiskUsedGb() { return diskUsedGb; }
    public double getDiskTotalGb() { return diskTotalGb; }
    public double getDiskPercent() { return diskPercent; }
    public String getLicenseLabel() { return licenseLabel; }
    public String getLicenseValue() { return licenseValue; }
    public int getInstanceCount() { return instanceCount; }
    public List<Map<String, Object>> getServices() { return services; }
    public List<CheckRow> getChecks() { return checks; }
    public boolean isUsedYesterdayAvg() { return usedYesterdayAvg; }

    /** Check Status 표 한 행 — title/defaultOk. 원본 _radio_row 의 입력 데이터와 동등. */
    public static final class CheckRow {
        private final String title;
        private final boolean defaultOk;
        public CheckRow(String title, boolean defaultOk) {
            this.title = title;
            this.defaultOk = defaultOk;
        }
        public String getTitle() { return title; }
        public boolean isDefaultOk() { return defaultOk; }
    }

    // LicenseInfoRow 는 license 패키지 재사용(여기선 사용 안 함이지만 향후 확장 대비 import 유지)
    @SuppressWarnings("unused")
    private static final Class<?> LICENSE_REUSE = LicenseInfoRow.class;
}
