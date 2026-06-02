package com.exem.inspector.screen.alertsvc;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * Alert Service Config 라우터(원본 api_alert_svc_read/save/copy 1:1 동등).
 *
 * <p>응답 봉투는 표준 {@link ApiResponse}. 입력 차단/검증/실행 오류는 200 + {@code ok=false + error}
 * 로 통일(원본 동일 패턴 — UI 에 토스트/배너로 표시).
 */
@RestController
public class AlertSvcConfigController {

    private final AlertSvcConfigService service;

    public AlertSvcConfigController(AlertSvcConfigService service) {
        this.service = service;
    }

    /** {@code GET /labs/api/alert-svc/{kind:sms|api|mail}}. */
    @GetMapping("/labs/api/alert-svc/{kind:sms|api|mail}")
    public ResponseEntity<ApiResponse<AlertSvcReadResult>> read(@PathVariable("kind") String kind) {
        try {
            AlertSvcKind k = AlertSvcKind.fromString(kind);
            if (k == null) {
                return ResponseEntity.ok(ApiResponse.error("Invalid kind: " + kind));
            }
            return ResponseEntity.ok(ApiResponse.ok(service.read(k)));
        } catch (IllegalArgumentException | IllegalStateException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }

    /** {@code POST /labs/api/alert-svc/save}. */
    @PostMapping("/labs/api/alert-svc/save")
    public ResponseEntity<ApiResponse<AlertSvcSaveResult>> save(
            @RequestBody(required = false) AlertSvcSaveRequest req) {
        try {
            return ResponseEntity.ok(ApiResponse.ok(service.save(req)));
        } catch (IllegalArgumentException | IllegalStateException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }

    /** {@code POST /labs/api/alert-svc/copy}. */
    @PostMapping("/labs/api/alert-svc/copy")
    public ResponseEntity<ApiResponse<AlertSvcCopyResult>> copy(
            @RequestBody(required = false) AlertSvcCopyRequest req) {
        try {
            return ResponseEntity.ok(ApiResponse.ok(service.copy(req)));
        } catch (IllegalArgumentException | IllegalStateException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }
}
