package com.exem.inspector.screen.config;

import java.util.Collection;
import java.util.List;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * Config Dump / Restore 라우터 — 원본 config_dump.py 의 page_config_dump 화면용.
 *
 * <p>원본 화면은 Dump (2 profile cards) + Restore + Migration Guide 3-카드 구성.
 * - GET  /labs/api/config-dump/menus   : MENU_DEFS 노출 (tooltip 상세 데이터).
 * - POST /labs/api/config-dump         : 메뉴 선택 → dump 결과(JSON+SQL 문자열) 반환.
 * - POST /labs/api/config-restore      : 업로드된 dump 데이터로 restore.
 */
@RestController
public class ConfigDumpController {

    private final ConfigDumpService service;
    private final ConfigRestoreService restoreService;

    public ConfigDumpController(ConfigDumpService service, ConfigRestoreService restoreService) {
        this.service = service;
        this.restoreService = restoreService;
    }

    /** GET /labs/api/config-dump/menus — 5 메뉴 정의 노출(tooltip 상세 데이터). */
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

    /** POST /labs/api/config-restore — 업로드된 dump JSON 으로 Repository 복원. */
    @PostMapping("/labs/api/config-restore")
    public ResponseEntity<ApiResponse<RestoreResult>> restore(@RequestBody Map<String, Object> dumpData) {
        try {
            return ResponseEntity.ok(ApiResponse.ok(restoreService.restore(dumpData)));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }
}
