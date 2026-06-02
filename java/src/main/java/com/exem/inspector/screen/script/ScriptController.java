package com.exem.inspector.screen.script;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * Script Manager 라우터(원본 api_script_schemas / api_script_run 1:1 동등).
 *
 * <p>응답 봉투는 표준 {@link ApiResponse}. 입력 차단/검증 오류와 실행 실패는
 * 모두 200 + {@code ok=false + error} 로 통일한다(원본 동일 패턴 — UI 가 오류 박스를 렌더).
 */
@RestController
public class ScriptController {

    private final ScriptService service;

    public ScriptController(ScriptService service) {
        this.service = service;
    }

    @GetMapping("/labs/api/script/schemas")
    public ResponseEntity<ApiResponse<ScriptSchemasResult>> schemas() {
        return ResponseEntity.ok(ApiResponse.ok(service.schemas()));
    }

    @PostMapping("/labs/api/script/run")
    public ResponseEntity<ApiResponse<ScriptRunResult>> run(@RequestBody(required = false) ScriptRunRequest req) {
        try {
            return ResponseEntity.ok(ApiResponse.ok(service.run(req)));
        } catch (IllegalArgumentException | IllegalStateException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }
}
