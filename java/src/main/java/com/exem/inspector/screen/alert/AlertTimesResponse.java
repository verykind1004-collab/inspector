package com.exem.inspector.screen.alert;

import java.util.List;

/**
 * Alert 일별 카운트 응답 페이로드.
 *
 * <p>원본 {@code api_alert_times} 의 {@code {ok, days, total}} 구조와 1:1.
 * {@link com.exem.inspector.common.web.ApiResponse} 봉투 {@code data} 에 포함된다.
 */
public class AlertTimesResponse {

    private final List<Day> days;
    private final int total;

    public AlertTimesResponse(List<Day> days, int total) {
        this.days = days;
        this.total = total;
    }

    public List<Day> getDays() { return days; }
    public int getTotal() { return total; }

    /** 일자 + 카운트 한 줄. */
    public static class Day {
        private final String day;
        private final int count;

        public Day(String day, int count) {
            this.day = day;
            this.count = count;
        }

        public String getDay() { return day; }
        public int getCount() { return count; }
    }
}
