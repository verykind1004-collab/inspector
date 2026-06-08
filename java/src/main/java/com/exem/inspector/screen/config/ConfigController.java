package com.exem.inspector.screen.config;

import java.io.IOException;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;
import com.exem.inspector.screen.maxspace.MaxSpaceService;

@RestController
public class ConfigController {

    private final ConfigService service;
    private final MaxSpaceService maxSpaceService;

    public ConfigController(ConfigService service, MaxSpaceService maxSpaceService) {
        this.service = service;
        this.maxSpaceService = maxSpaceService;
    }

    /** GET /labs/api/config — service_config.json 전체 노출. */
    @GetMapping("/labs/api/config")
    public ResponseEntity<ApiResponse<ConfigPagePayload>> read() {
        return ResponseEntity.ok(ApiResponse.ok(service.read()));
    }

    /**
     * POST /labs/api/config — 본문을 service_config.json 으로 저장하고 reload.
     *
     * <p>저장 성공 후 MaxSpace 풀/캐시 즉시 무효화 (원본 Inspector.py::_trigger_maxspace_reset 대응).
     * 원본은 section in (repo, all) 분기로 호출했으나 React 가 root JSON 전체 전송하므로 무조건 호출.
     */
    @PostMapping("/labs/api/config")
    public ResponseEntity<ApiResponse<Map<String, Object>>> write(@RequestBody(required = false) Map<String, Object> body) {
        try {
            service.write(body);
            maxSpaceService.reset();
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
