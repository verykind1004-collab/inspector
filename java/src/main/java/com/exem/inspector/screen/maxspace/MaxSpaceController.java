package com.exem.inspector.screen.maxspace;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * MaxSpace REST 컨트롤러 — 원본 tablespace_server.py 의 FastAPI endpoint 5종 1:1.
 *
 * <p>응답 shape 도 원본 1:1. {@code {ok, data:{...}}} / {@code {ok, groups:[...]}} 등을
 * 정확히 재현하기 위해 {@code Map} 직접 반환 (ApiResponse 봉투 미사용).
 *
 * <p>base path 는 {@code /labs/api/maxspace}. Inspector 전체와 일관 prefix 유지.
 * Step 3-1B 에서 권한 필터 추가, Step 3-1C 에서 trend endpoint 추가.
 */
@RestController
@RequestMapping("/labs/api/maxspace")
public class MaxSpaceController {

    private final MaxSpaceService service;
    private final MaxSpaceConfig config;

    public MaxSpaceController(MaxSpaceService service, MaxSpaceConfig config) {
        this.service = service;
        this.config = config;
    }

    /** GET /api/data — { ok, data:{today, dbs[], tablespaces{}} }. */
    @GetMapping("/data")
    public Map<String, Object> data() {
        try {
            Map<String, Object> data = service.buildData();
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("ok", true);
            out.put("data", data);
            return out;
        } catch (Exception e) {
            return err(e);
        }
    }

    /** GET /api/groups — { ok, groups:[...] }. */
    @GetMapping("/groups")
    public Map<String, Object> groups() {
        try {
            List<Map<String, Object>> g = service.getServiceGroups();
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("ok", true);
            out.put("groups", g);
            return out;
        } catch (Exception e) {
            return err(e);
        }
    }

    /** GET /api/health — { ok, status, db_type, cache, trend_cache, next_refresh, server_time }. */
    @GetMapping("/health")
    public Map<String, Object> health() {
        return service.getHealth();
    }

    /** GET /api/refresh?token=... — token 인증 후 캐시 invalidate + 즉시 재빌드. */
    @GetMapping("/refresh")
    public ResponseEntity<Map<String, Object>> refresh(@RequestParam(defaultValue = "") String token) {
        ResponseEntity<Map<String, Object>> denied = authToken(token);
        if (denied != null) {
            return denied;
        }
        try {
            Map<String, Object> data = service.refresh();
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("ok", true);
            out.put("data", data);
            return ResponseEntity.ok(out);
        } catch (Exception e) {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("ok", false);
            body.put("error", e.getMessage());
            return ResponseEntity.status(500).body(body);
        }
    }

    /** POST /api/reset?token=... — pool/캐시 폐기 hook (Inspector 가 Repository SAVE 후 호출). */
    @PostMapping("/reset")
    public ResponseEntity<Map<String, Object>> reset(@RequestParam(defaultValue = "") String token) {
        ResponseEntity<Map<String, Object>> denied = authToken(token);
        if (denied != null) {
            return denied;
        }
        service.reset();
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ok", true);
        return ResponseEntity.ok(out);
    }

    // ----- 보조 -----

    private ResponseEntity<Map<String, Object>> authToken(String token) {
        String valid = config.getRefreshToken();
        if (valid == null || valid.isEmpty() || !valid.equals(token)) {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("ok", false);
            body.put("error", "인증 실패");
            return ResponseEntity.status(401).body(body);
        }
        return null;
    }

    private static Map<String, Object> err(Exception e) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ok", false);
        out.put("error", e.getMessage());
        return out;
    }
}
