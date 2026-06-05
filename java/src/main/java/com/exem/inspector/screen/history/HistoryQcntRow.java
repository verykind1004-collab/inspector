package com.exem.inspector.screen.history;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * /labs/api/history-qcnt 응답 내 svc_map[svc] 의 단일 row.
 *
 * <p>원본 history_views.py::api_history_qcnt 의 {ts, act, total, max, qcnt} 1:1.
 */
public class HistoryQcntRow {

    private final String ts;
    private final Double act;
    private final Double total;
    private final Double max;
    private final Double qcnt;

    public HistoryQcntRow(String ts, Double act, Double total, Double max, Double qcnt) {
        this.ts = ts;
        this.act = act;
        this.total = total;
        this.max = max;
        this.qcnt = qcnt;
    }

    @JsonProperty("ts")    public String getTs()    { return ts; }
    @JsonProperty("act")   public Double getAct()   { return act; }
    @JsonProperty("total") public Double getTotal() { return total; }
    @JsonProperty("max")   public Double getMax()   { return max; }
    @JsonProperty("qcnt")  public Double getQcnt()  { return qcnt; }
}
