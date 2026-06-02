package com.exem.inspector.screen.alarmhistory;

/**
 * Alarm Send History 한 행 — apm_db_info + ora_alarm_history 조인 + 로그 파싱 결과(status/error).
 */
public class AlarmHistoryRow {

    private final String instanceName;
    private final String alertTime;
    private final long alertEpoch;
    private final String alertType;     // Server Alert / Stat Alert / Type N
    private final String name;
    private final String value;
    private final String status;        // success / failed / skipped
    private final String error;         // failed 일 때만

    public AlarmHistoryRow(String instanceName, String alertTime, long alertEpoch,
                           String alertType, String name, String value,
                           String status, String error) {
        this.instanceName = instanceName;
        this.alertTime = alertTime;
        this.alertEpoch = alertEpoch;
        this.alertType = alertType;
        this.name = name;
        this.value = value;
        this.status = status;
        this.error = error;
    }

    public String getInstanceName() { return instanceName; }
    public String getAlertTime() { return alertTime; }
    public long getAlertEpoch() { return alertEpoch; }
    public String getAlertType() { return alertType; }
    public String getName() { return name; }
    public String getValue() { return value; }
    public String getStatus() { return status; }
    public String getError() { return error; }
}
