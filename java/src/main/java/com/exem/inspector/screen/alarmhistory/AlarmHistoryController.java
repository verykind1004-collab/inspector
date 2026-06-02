package com.exem.inspector.screen.alarmhistory;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

@RestController
public class AlarmHistoryController {

    private final AlarmHistoryService service;

    public AlarmHistoryController(AlarmHistoryService service) {
        this.service = service;
    }

    /**
     * {@code GET /labs/api/alarm-history?date=YYYY-MM-DD}.
     * date 미지정 시 오늘.
     */
    @GetMapping("/labs/api/alarm-history")
    public ResponseEntity<ApiResponse<AlarmHistoryPayload>> get(
            @RequestParam(name = "date", required = false) String date) {
        try {
            return ResponseEntity.ok(ApiResponse.ok(service.build(date)));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }
}
