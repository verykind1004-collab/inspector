package com.exem.inspector.screen.history;

import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * /labs/api/history-service 응답 페이로드.
 *
 * <p>원본 history_views.py::api_history_service envelope 1:1 — {services, data, date}.
 * services 는 config 순서(DGServer_M → DGServer_Sn → PlatformJS → Repository DB).
 */
public class HistoryServicePayload {

    private final List<String> services;
    private final Map<String, List<HistoryServiceRow>> data;
    private final String date;

    public HistoryServicePayload(List<String> services,
                                  Map<String, List<HistoryServiceRow>> data,
                                  String date) {
        this.services = services;
        this.data = data;
        this.date = date;
    }

    @JsonProperty("services") public List<String> getServices() { return services; }
    @JsonProperty("data")     public Map<String, List<HistoryServiceRow>> getData() { return data; }
    @JsonProperty("date")     public String getDate() { return date; }
}
