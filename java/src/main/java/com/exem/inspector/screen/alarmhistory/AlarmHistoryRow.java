package com.exem.inspector.screen.alarmhistory;

/**
 * Alarm Send History 한 행 — apm_db_info + ora_alarm_history 조인 + 로그 파싱 결과(status/error).
 *
 * <p>원본 1:1: 한 알람(같은 epoch)에 sms/api/mail 중 여러 jar 의 send 로그가 있으면
 * Send Type 별 sub-row 로 분리. 어느 type 도 매칭 안 되면 sendType=null + status=skipped 1행.
 */
public class AlarmHistoryRow {

    private final String instanceName;
    private final String alertTime;
    private final long alertEpoch;
    private final String alertType;     // Server Alert / Stat Alert / Type N
    private final String name;
    private final String value;
    private final String sendType;      // "sms" / "api" / "mail" / null(=Skipped 행)
    private final String status;        // success / failed / skipped
    private final String error;         // failed 일 때만

    public AlarmHistoryRow(String instanceName, String alertTime, long alertEpoch,
                           String alertType, String name, String value,
                           String sendType, String status, String error) {
        this.instanceName = instanceName;
        this.alertTime = alertTime;
        this.alertEpoch = alertEpoch;
        this.alertType = alertType;
        this.name = name;
        this.value = value;
        this.sendType = sendType;
        this.status = status;
        this.error = error;
    }

    public String getInstanceName() { return instanceName; }
    public String getAlertTime() { return alertTime; }
    public long getAlertEpoch() { return alertEpoch; }
    public String getAlertType() { return alertType; }
    public String getName() { return name; }
    public String getValue() { return value; }
    public String getSendType() { return sendType; }
    public String getStatus() { return status; }
    public String getError() { return error; }
}
