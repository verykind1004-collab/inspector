package com.exem.inspector.screen.report;

import java.util.List;

/**
 * MaxGauge Daily Report 통합 응답 — 원본 page_report() 1:1 동등.
 *
 * <p>원본 보고서 블록 5개:
 * (1) 4 stat 카드 (CPU/Memory/TBS or Disk/Instances)
 * (2) 고객사명/지원제품 contenteditable 행 → 서버 데이터 없음(FE 영역)
 * (3) Check Resource 12개월 × 3행 (CPU/Memory/TBS) — INSP_MONTHLY_SUMMARY
 * (4) Check Status STATUS_GROUPS 4그룹 — 토글 가능(클라이언트 사이드)
 * (5) 특이사항 + 점검일/엔지니어/고객확인/서명 — 서버 데이터 없음(FE 영역)
 *
 * <p>License 카드/Check Status License 행은 원본에 없으므로 제거.
 * Services 별도 표도 원본에 없으므로 제거(status 결정은 내부 사용만).
 */
public class ReportPayload {

    private final String reportDate;        // YYYY-MM-DD (오늘)
    private final String cpuLabel;          // "AVG CPU (yyyy-MM-dd)" 또는 "CPU"
    private final double cpuPercent;
    private final String memLabel;          // "AVG Memory (yyyy-MM-dd)" 또는 "Memory"
    private final double memUsedGb;
    private final double memTotalGb;
    private final double memPercent;
    private final String diskLabel;         // "TBS"(Oracle worst tablespace) / "Disk"(PG)
    private final double diskUsedGb;
    private final double diskTotalGb;
    private final double diskPercent;
    private final int instanceCount;        // 4번째 stat 카드 (apm_db_info COUNT)
    private final boolean usedYesterdayAvg; // true 면 INSP_OS_HISTORY 어제 평균
    private final List<MonthlySnapshot> monthly;   // 1~12월, 12개. null 셀은 빈 값
    private final List<StatusGroup> statusGroups;  // 원본 STATUS_GROUPS 4그룹

    public ReportPayload(String reportDate,
                         String cpuLabel, double cpuPercent,
                         String memLabel, double memUsedGb, double memTotalGb, double memPercent,
                         String diskLabel, double diskUsedGb, double diskTotalGb, double diskPercent,
                         int instanceCount,
                         boolean usedYesterdayAvg,
                         List<MonthlySnapshot> monthly,
                         List<StatusGroup> statusGroups) {
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
        this.instanceCount = instanceCount;
        this.usedYesterdayAvg = usedYesterdayAvg;
        this.monthly = monthly;
        this.statusGroups = statusGroups;
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
    public int getInstanceCount() { return instanceCount; }
    public boolean isUsedYesterdayAvg() { return usedYesterdayAvg; }
    public List<MonthlySnapshot> getMonthly() { return monthly; }
    public List<StatusGroup> getStatusGroups() { return statusGroups; }

    /** Check Resource 12개월 표 한 행. cpu/mem/disk null 면 셀 비움. */
    public static final class MonthlySnapshot {
        private final int month;            // 1~12
        private final Double cpuAvg;        // %
        private final Double memAvg;        // %
        private final Double diskAvg;       // %
        public MonthlySnapshot(int month, Double cpuAvg, Double memAvg, Double diskAvg) {
            this.month = month;
            this.cpuAvg = cpuAvg;
            this.memAvg = memAvg;
            this.diskAvg = diskAvg;
        }
        public int getMonth() { return month; }
        public Double getCpuAvg() { return cpuAvg; }
        public Double getMemAvg() { return memAvg; }
        public Double getDiskAvg() { return diskAvg; }
    }

    /** Check Status STATUS_GROUPS 한 그룹 (rowspan 그룹명 + 항목 N개). */
    public static final class StatusGroup {
        private final String groupName;
        private final List<StatusItem> items;
        public StatusGroup(String groupName, List<StatusItem> items) {
            this.groupName = groupName;
            this.items = items;
        }
        public String getGroupName() { return groupName; }
        public List<StatusItem> getItems() { return items; }
    }

    /** Check Status 한 항목 (제목 + default OK 여부). */
    public static final class StatusItem {
        private final String title;
        private final boolean defaultOk;
        public StatusItem(String title, boolean defaultOk) {
            this.title = title;
            this.defaultOk = defaultOk;
        }
        public String getTitle() { return title; }
        public boolean isDefaultOk() { return defaultOk; }
    }
}
