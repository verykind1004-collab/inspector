package com.exem.inspector.screen.history;

import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * /labs/api/history-heap 응답 페이로드.
 *
 * <p>원본 history_views.py::api_history_heap envelope 1:1 — {services, data, date}.
 * services 는 mapper 응답에서 발견된 서비스명 정렬.
 */
public class HistoryHeapPayload {

    private final List<String> services;
    private final Map<String, List<HistoryHeapRow>> data;
    private final String date;

    public HistoryHeapPayload(List<String> services,
                               Map<String, List<HistoryHeapRow>> data,
                               String date) {
        this.services = services;
        this.data = data;
        this.date = date;
    }

    @JsonProperty("services") public List<String> getServices() { return services; }
    @JsonProperty("data")     public Map<String, List<HistoryHeapRow>> getData() { return data; }
    @JsonProperty("date")     public String getDate() { return date; }
}
