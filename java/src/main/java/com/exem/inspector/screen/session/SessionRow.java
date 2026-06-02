package com.exem.inspector.screen.session;

/** Session Check 화면의 한 행. 원본 컬럼: DB ID / INSTANCE_NAME / LAST_TIME. */
public class SessionRow {

    private Integer dbId;
    private String instanceName;
    private String lastTime;   // 인스턴스별 마지막 세션 수집 시각

    public Integer getDbId() { return dbId; }
    public void setDbId(Integer dbId) { this.dbId = dbId; }
    public String getInstanceName() { return instanceName; }
    public void setInstanceName(String instanceName) { this.instanceName = instanceName; }
    public String getLastTime() { return lastTime; }
    public void setLastTime(String lastTime) { this.lastTime = lastTime; }
}
