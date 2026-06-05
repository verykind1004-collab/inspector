package com.exem.inspector.screen.history;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * Inspector History 상세 화면용 REST 엔드포인트.
 *
 * <p>원본 history_views.py 의 api_history_os/tbs/heap/qcnt/service 1:1.
 */
@RestController
public class HistoryDetailController {

    private final HistoryDetailService service;

    public HistoryDetailController(HistoryDetailService service) {
        this.service = service;
    }

    /**
     * {@code GET /labs/api/history-os?date=YYYY-MM-DD&from=HH:MM&to=HH:MM}.
     * 원본 api_history_os 1:1 — 누락/형식 오류 시 today/00:00/23:59 으로 대체.
     */
    @GetMapping("/labs/api/history-os")
    public ResponseEntity<ApiResponse<HistoryOsPayload>> os(
            @RequestParam(name = "date", required = false) String date,
            @RequestParam(name = "from", required = false) String from,
            @RequestParam(name = "to",   required = false) String to) {
        try {
            return ResponseEntity.ok(ApiResponse.ok(service.os(date, from, to)));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(safeMessage(e)));
        }
    }

    /**
     * {@code GET /labs/api/history-tbs?from_date=YYYY-MM-DD&to_date=YYYY-MM-DD}.
     * 원본 api_history_tbs 1:1 — to_date 누락 시 from_date 와 동일.
     */
    @GetMapping("/labs/api/history-tbs")
    public ResponseEntity<ApiResponse<HistoryTbsPayload>> tbs(
            @RequestParam(name = "from_date", required = false) String fromDate,
            @RequestParam(name = "to_date",   required = false) String toDate) {
        try {
            return ResponseEntity.ok(ApiResponse.ok(service.tbs(fromDate, toDate)));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(safeMessage(e)));
        }
    }

    private static String safeMessage(RuntimeException e) {
        String msg = e.getMessage();
        if (msg == null) {
            return e.getClass().getSimpleName();
        }
        return msg.length() <= 200 ? msg : msg.substring(0, 200);
    }
}
