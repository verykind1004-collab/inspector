package com.exem.inspector.screen.history;

import java.util.List;

/**
 * /labs/api/history-os 응답 페이로드.
 *
 * <p>원본 history_views.py::api_history_os envelope 1:1 — {data, date, from, to}.
 * envelope 의 ok/error 는 ApiResponse 표준이 담당.
 */
public class HistoryOsPayload {

    private final List<HistoryOsRow> data;
    private final String date;
    private final String from;
    private final String to;

    public HistoryOsPayload(List<HistoryOsRow> data, String date, String from, String to) {
        this.data = data;
        this.date = date;
        this.from = from;
        this.to = to;
    }

    public List<HistoryOsRow> getData() { return data; }
    public String getDate() { return date; }
    public String getFrom() { return from; }
    public String getTo()   { return to;   }
}
