package com.exem.inspector.screen.maxspace;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * MaxSpace REST 컨트롤러 — 원본 tablespace_server.py 의 FastAPI endpoint 6 종 1:1.
 *
 * <p>응답 shape 도 원본 1:1. {@code {ok, data:{...}}} / {@code {ok, groups:[...]}} 등을
 * 정확히 재현하기 위해 {@code Map} 직접 반환 (ApiResponse 봉투 미사용).
 *
 * <p>base path: {@code /labs/api/maxspace}.
 *
 * <p>권한 필터 (Step 3-1B):
 * <ul>
 *   <li>/data — engineer 전체 / user 는 허용 db_id 만 dbs[]/tablespaces{} 필터</li>
 *   <li>/trend — 인스턴스의 db_id 가 허용 dbid 가 아니면 403</li>
 *   <li>/groups, /health — 권한 미적용 (원본도 동일)</li>
 * </ul>
 */
@RestController
@RequestMapping("/labs/api/maxspace")
public class MaxSpaceController {

    private final MaxSpaceService service;
    private final MaxSpacePermissionService permissionService;
    private final MaxSpaceConfig config;

    public MaxSpaceController(MaxSpaceService service,
                              MaxSpacePermissionService permissionService,
                              MaxSpaceConfig config) {
        this.service = service;
        this.permissionService = permissionService;
        this.config = config;
    }

    /** GET /api/data — 권한 필터 적용. */
    @GetMapping("/data")
    public Map<String, Object> data() {
        try {
            Map<String, Object> raw = service.buildData();
            MaxSpacePermissionService.Permission perm = permissionService.resolveCurrent();
            Map<String, Object> filtered = perm.allAllowed ? raw : filterByDbIds(raw, perm.dbIds);
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("ok", true);
            out.put("data", filtered);
            return out;
        } catch (Exception e) {
            return err(e);
        }
    }

    /** GET /api/trend?db=instance_name — 인스턴스의 db_id 권한 검증 후 캐시된 트렌드 반환. */
    @GetMapping("/trend")
    public ResponseEntity<Map<String, Object>> trend(@RequestParam("db") String db) {
        try {
            MaxSpacePermissionService.Permission perm = permissionService.resolveCurrent();
            if (!perm.allAllowed) {
                MaxSpaceService.InstanceInfo info = service.lookupInstance(db);
                if (info == null) {
                    Map<String, Object> body = new LinkedHashMap<>();
                    body.put("ok", false);
                    body.put("error", "인스턴스 없음: " + db);
                    return ResponseEntity.status(404).body(body);
                }
                if (!perm.dbIds.contains(info.dbId)) {
                    Map<String, Object> body = new LinkedHashMap<>();
                    body.put("ok", false);
                    body.put("error", "permission denied");
                    return ResponseEntity.status(403).body(body);
                }
            }
            Map<String, List<Map<String, Object>>> trend = service.getTrend(db);
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("ok", true);
            out.put("db", db);
            out.put("trend", trend);
            return ResponseEntity.ok(out);
        } catch (MaxSpaceService.NoSuchInstanceException e) {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("ok", false);
            body.put("error", e.getMessage());
            return ResponseEntity.status(404).body(body);
        } catch (Exception e) {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("ok", false);
            body.put("error", e.getMessage());
            return ResponseEntity.status(500).body(body);
        }
    }

    /** GET /api/groups — 권한 미적용. */
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

    /** GET /api/health — 권한 미적용. */
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

    /** POST /api/reset?token=... — pool/캐시 폐기 hook. */
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

    /**
     * 권한 dbid 집합으로 dbs[] / tablespaces{} 필터.
     * 원본 api_data 의 filter 분기 1:1.
     */
    private static Map<String, Object> filterByDbIds(Map<String, Object> raw, Set<Integer> dbIds) {
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> dbs = (List<Map<String, Object>>) raw.getOrDefault("dbs", java.util.Collections.emptyList());
        @SuppressWarnings("unchecked")
        Map<String, Object> tablespaces = (Map<String, Object>) raw.getOrDefault("tablespaces", java.util.Collections.emptyMap());

        List<Map<String, Object>> filteredDbs = new ArrayList<>();
        Set<String> allowedNames = new HashSet<>();
        for (Map<String, Object> d : dbs) {
            Object dbId = d.get("db_id");
            if (dbId instanceof Number && dbIds.contains(((Number) dbId).intValue())) {
                filteredDbs.add(d);
                Object name = d.get("db_name");
                if (name != null) {
                    allowedNames.add(name.toString());
                }
            }
        }
        Map<String, Object> filteredTs = new LinkedHashMap<>();
        for (Map.Entry<String, Object> e : tablespaces.entrySet()) {
            if (allowedNames.contains(e.getKey())) {
                filteredTs.put(e.getKey(), e.getValue());
            }
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("today", raw.getOrDefault("today", ""));
        out.put("dbs", filteredDbs);
        out.put("tablespaces", filteredTs);
        return out;
    }

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
