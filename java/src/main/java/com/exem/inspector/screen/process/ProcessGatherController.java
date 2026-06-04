package com.exem.inspector.screen.process;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * Process Gather 라우터 — 원본 {@code /process/gather} 1:1 (Phase 2: Overview).
 *
 * <p>URL: {@code GET /labs/api/process/gather} → {@link ProcessGatherPayload}.
 * 화면 측은 이 응답을 받아 각 DGServer 섹션에 ERROR/WARN 마지막 500 라인 표시.
 * Follow 모드(2초 폴링)는 별도 {@link LogTailController} 엔드포인트 사용.
 */
@RestController
public class ProcessGatherController {

    private final ProcessGatherService service;

    public ProcessGatherController(ProcessGatherService service) {
        this.service = service;
    }

    @GetMapping("/labs/api/process/gather")
    public ResponseEntity<ApiResponse<ProcessGatherPayload>> get() {
        try {
            return ResponseEntity.ok(ApiResponse.ok(service.overview()));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }
}
