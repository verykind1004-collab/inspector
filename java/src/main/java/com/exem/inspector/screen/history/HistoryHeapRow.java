package com.exem.inspector.screen.history;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * /labs/api/history-heap 응답 내 svc_map[svc] 의 단일 row.
 *
 * <p>원본 history_views.py::api_history_heap 의 {ts, used, alloc, max} 1:1.
 */
public class HistoryHeapRow {

    private final String ts;
    private final Double used;
    private final Double alloc;
    private final Double max;

    public HistoryHeapRow(String ts, Double used, Double alloc, Double max) {
        this.ts = ts;
        this.used = used;
        this.alloc = alloc;
        this.max = max;
    }

    @JsonProperty("ts")    public String getTs()    { return ts; }
    @JsonProperty("used")  public Double getUsed()  { return used; }
    @JsonProperty("alloc") public Double getAlloc() { return alloc; }
    @JsonProperty("max")   public Double getMax()   { return max; }
}
