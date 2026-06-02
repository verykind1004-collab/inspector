package com.exem.inspector.screen.license;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * License Check 화면 라우터 — 원본 page_license_check() 의 3 카드 데이터를 단일 호출로 반환.
 *
 * <p>{@code GET /labs/api/license-check} → {@link LicenseCheckResult} (info / instances / events + 카드별 error).
 */
@RestController
public class LicenseController {

    private final LicenseService service;

    public LicenseController(LicenseService service) {
        this.service = service;
    }

    @GetMapping("/labs/api/license-check")
    public ResponseEntity<ApiResponse<LicenseCheckResult>> get() {
        try {
            return ResponseEntity.ok(ApiResponse.ok(service.build()));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }
}
