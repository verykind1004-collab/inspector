package com.exem.inspector.screen.history;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * /labs/api/history-service 응답 내 svc_map[svc] 의 단일 row.
 *
 * <p>원본 history_views.py::api_history_service 의 {ts, s} 1:1.
 */
public class HistoryServiceRow {

    private final String ts;
    private final String s;

    public HistoryServiceRow(String ts, String s) {
        this.ts = ts;
        this.s = s;
    }

    @JsonProperty("ts") public String getTs() { return ts; }
    @JsonProperty("s")  public String getS()  { return s; }
}
