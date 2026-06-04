package com.exem.inspector.screen.config;

import java.util.Collection;
import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * Config Dump 라우터 — screen 5. screen 4(config_page) 와 별도 화면 분리(Session 2).
 *
 * <p>D-2(Session 5) — /labs/api/config-dump/sql 추가.
 */
@RestController
public class ConfigDumpController {

    private final ConfigDumpService service;
    private final SqlDumpService sqlService;

    public ConfigDumpController(ConfigDumpService service, SqlDumpService sqlService) {
        this.service = service;
        this.sqlService = sqlService;
    }

    /** GET /labs/api/config-dump/menus — 5 메뉴 정의 노출. */
    @GetMapping("/labs/api/config-dump/menus")
    public ResponseEntity<ApiResponse<Collection<ConfigDumpMenu>>> menus() {
        return ResponseEntity.ok(ApiResponse.ok(service.menus()));
    }

    /** POST /labs/api/config-dump — 선택 메뉴 dump. 빈 body 면 모든 메뉴. */
    @PostMapping("/labs/api/config-dump")
    public ResponseEntity<ApiResponse<ConfigDumpPayload>> dump(@RequestBody(required = false) List<String> menuKeys) {
        try {
            return ResponseEntity.ok(ApiResponse.ok(service.dump(menuKeys)));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }

    /** POST /labs/api/config-dump/sql — dump → SQL 텍스트(원본 _generate_sql). */
    @PostMapping("/labs/api/config-dump/sql")
    public ResponseEntity<ApiResponse<SqlDumpResult>> sql(@RequestBody(required = false) List<String> menuKeys) {
        try {
            return ResponseEntity.ok(ApiResponse.ok(sqlService.generate(menuKeys)));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }
}
