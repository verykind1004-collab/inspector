package com.exem.inspector.screen.history;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * /labs/api/history-tbs 응답의 단일 row.
 *
 * <p>원본 history_views.py::api_history_tbs 의 row 1:1 (ts, name, used, total, free, pct, status).
 */
public class HistoryTbsRow {

    private final String ts;
    private final String name;
    private final Double used;
    private final Double total;
    private final Double free;
    private final Double pct;
    private final String status;

    public HistoryTbsRow(String ts, String name,
                         Double used, Double total, Double free, Double pct, String status) {
        this.ts = ts;
        this.name = name;
        this.used = used;
        this.total = total;
        this.free = free;
        this.pct = pct;
        this.status = status;
    }

    @JsonProperty("ts")     public String getTs()    { return ts; }
    @JsonProperty("name")   public String getName()  { return name; }
    @JsonProperty("used")   public Double getUsed()  { return used; }
    @JsonProperty("total")  public Double getTotal() { return total; }
    @JsonProperty("free")   public Double getFree()  { return free; }
    @JsonProperty("pct")    public Double getPct()   { return pct; }
    @JsonProperty("status") public String getStatus(){ return status; }
}
