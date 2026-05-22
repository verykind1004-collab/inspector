package com.exem.inspector.screen.summary;

/**
 * Summary Check 화면의 한 행. 매퍼가 채운다(map-underscore-to-camel-case 로 컬럼 alias → 필드).
 *
 * <p>컬럼: db_id, instance_name, summary_type, last_summary, status, delay_info.
 */
public class SummaryRow {

    private Integer dbId;
    private String instanceName;
    private String summaryType;
    private String lastSummary;   // 'YYYY-MM-DD HH24:MI:SS' (수집 이력 없으면 null)
    private String status;        // OK / CHECK / WAITING / ERROR
    private String delayInfo;     // 예: '+1h 30m', '+2d' (OK 면 null)

    public Integer getDbId() {
        return dbId;
    }

    public void setDbId(Integer dbId) {
        this.dbId = dbId;
    }

    public String getInstanceName() {
        return instanceName;
    }

    public void setInstanceName(String instanceName) {
        this.instanceName = instanceName;
    }

    public String getSummaryType() {
        return summaryType;
    }

    public void setSummaryType(String summaryType) {
        this.summaryType = summaryType;
    }

    public String getLastSummary() {
        return lastSummary;
    }

    public void setLastSummary(String lastSummary) {
        this.lastSummary = lastSummary;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getDelayInfo() {
        return delayInfo;
    }

    public void setDelayInfo(String delayInfo) {
        this.delayInfo = delayInfo;
    }
}
