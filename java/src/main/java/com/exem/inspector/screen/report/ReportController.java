package com.exem.inspector.screen.report;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * Daily Report 라우터. 단일 통합 페이로드.
 */
@RestController
public class ReportController {

    private final ReportService service;

    public ReportController(ReportService service) {
        this.service = service;
    }

    @GetMapping("/labs/api/report")
    public ResponseEntity<ApiResponse<ReportPayload>> get() {
        try {
            return ResponseEntity.ok(ApiResponse.ok(service.build()));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }
}
