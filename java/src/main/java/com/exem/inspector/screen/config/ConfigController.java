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

    /** GET /labs/api/config — service_config.json 전체 노출(config_page + config_dump 의 데이터 동일). */
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

    /** GET /labs/api/config/connection-test — Repository DB TCP + 각 서비스 home 디렉토리 존재 여부. */
    @GetMapping("/labs/api/config/connection-test")
    public ResponseEntity<ApiResponse<ConnectionTestResult>> connectionTest() {
        return ResponseEntity.ok(ApiResponse.ok(service.connectionTest()));
    }
}
