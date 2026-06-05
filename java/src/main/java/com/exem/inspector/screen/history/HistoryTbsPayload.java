package com.exem.inspector.screen.history;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * /labs/api/history-tbs 응답 페이로드.
 *
 * <p>원본 history_views.py::api_history_tbs envelope 1:1 — {data}.
 * <p>{@code isPg} 는 FE 가 페이지 타이틀(Disk vs Tablespace) 결정을 위해 사용한다(원본 _is_pg_repo() 1:1).
 */
public class HistoryTbsPayload {

    private final List<HistoryTbsRow> data;
    private final boolean isPg;

    public HistoryTbsPayload(List<HistoryTbsRow> data, boolean isPg) {
        this.data = data;
        this.isPg = isPg;
    }

    @JsonProperty("data") public List<HistoryTbsRow> getData() { return data; }
    @JsonProperty("is_pg") public boolean isPg() { return isPg; }
}
