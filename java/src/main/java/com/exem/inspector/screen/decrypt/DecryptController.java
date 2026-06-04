package com.exem.inspector.screen.decrypt;

import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * Decrypt/Encrypt 도구 (/decrypt) — 원본 pages/decrypt.py 의 api_decrypt 1:1.
 */
@RestController
public class DecryptController {

    private final DecryptService service;

    public DecryptController(DecryptService service) {
        this.service = service;
    }

    /** POST /labs/api/decrypt — body {text, action: encrypt|decrypt}. */
    @PostMapping("/labs/api/decrypt")
    public ResponseEntity<ApiResponse<Map<String, Object>>> run(@RequestBody DecryptRequest body) {
        if (body == null) {
            return ResponseEntity.ok(ApiResponse.error("Invalid request"));
        }
        return ResponseEntity.ok(ApiResponse.ok(service.run(body.getText(), body.getAction())));
    }

    public static class DecryptRequest {
        private String text;
        private String action;
        public String getText() { return text; }
        public void setText(String v) { text = v; }
        public String getAction() { return action; }
        public void setAction(String v) { action = v; }
    }
}
