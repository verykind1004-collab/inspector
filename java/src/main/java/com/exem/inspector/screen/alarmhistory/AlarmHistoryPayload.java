package com.exem.inspector.screen.alarmhistory;

import java.util.List;
import java.util.Map;

/**
 * Alarm Send History 통합 응답 — 원본 page_alarm_history 의 데이터 부분.
 */
public class AlarmHistoryPayload {

    private final String date;                 // 조회 일자 yyyy-MM-dd
    private final Map<String, Boolean> jarActive;  // {sms, api, mail} active
    private final int success;
    private final int failed;
    private final int skipped;
    private final List<AlarmHistoryRow> rows;

    public AlarmHistoryPayload(String date, Map<String, Boolean> jarActive,
                               int success, int failed, int skipped,
                               List<AlarmHistoryRow> rows) {
        this.date = date;
        this.jarActive = jarActive;
        this.success = success;
        this.failed = failed;
        this.skipped = skipped;
        this.rows = rows;
    }

    public String getDate() { return date; }
    public Map<String, Boolean> getJarActive() { return jarActive; }
    public int getSuccess() { return success; }
    public int getFailed() { return failed; }
    public int getSkipped() { return skipped; }
    public List<AlarmHistoryRow> getRows() { return rows; }
}
