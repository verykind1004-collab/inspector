package com.exem.inspector.screen.config;

import java.io.IOException;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

@RestController
public class ConfigController {

    private final ConfigService service;

    public ConfigController(ConfigService service) {
        this.service = service;
    }

    /** GET /labs/api/config — service_config.json 전체 노출. */
    @GetMapping("/labs/api/config")
    public ResponseEntity<ApiResponse<ConfigPagePayload>> read() {
        return ResponseEntity.ok(ApiResponse.ok(service.read()));
    }

    /** POST /labs/api/config — 본문을 service_config.json 으로 저장하고 reload. */
    @PostMapping("/labs/api/config")
    public ResponseEntity<ApiResponse<Map<String, Object>>> write(@RequestBody(required = false) Map<String, Object> body) {
        try {
            service.write(body);
            return ResponseEntity.ok(ApiResponse.ok(java.util.Collections.<String, Object>singletonMap("saved", true)));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        } catch (IOException e) {
            return ResponseEntity.ok(ApiResponse.error("Write failed: " + e.getMessage()));
        }
    }

    /** GET /labs/api/config/connection-test — Repository DB TCP + 서비스 home 점검. */
    @GetMapping("/labs/api/config/connection-test")
    public ResponseEntity<ApiResponse<ConnectionTestResult>> connectionTest() {
        return ResponseEntity.ok(ApiResponse.ok(service.connectionTest()));
    }

    // ── Inspector History config (insp_config.json) ──────────────────────

    /** GET /labs/api/config/insp-history — 원본 history.py::_load_insp_config 와 동등. */
    @GetMapping("/labs/api/config/insp-history")
    public ResponseEntity<ApiResponse<InspHistoryConfig>> readInspHistory() {
        return ResponseEntity.ok(ApiResponse.ok(service.readInspHistory()));
    }

    /** POST /labs/api/config/insp-history — insp_config.json 저장. */
    @PostMapping("/labs/api/config/insp-history")
    public ResponseEntity<ApiResponse<InspHistoryConfig>> saveInspHistory(@RequestBody(required = false) InspHistoryConfig body) {
        try {
            return ResponseEntity.ok(ApiResponse.ok(service.saveInspHistory(body)));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        } catch (IOException e) {
            return ResponseEntity.ok(ApiResponse.error("Write failed: " + e.getMessage()));
        }
    }
}
