package com.exem.inspector.screen.simple;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;
import com.exem.inspector.common.web.screen.ScreenResponse;

/**
 * 원본 _db_page 패턴 단순 점검 화면 라우터.
 *
 * <p>URL 화이트리스트 = 등록된 화면 키만 허용(SimpleScreenService.screenKeys() 참고).
 * 미등록 키는 404 로 거부한다(공개 인터페이스 안정).
 */
@RestController
public class SimpleScreenController {

    private final SimpleScreenService service;

    public SimpleScreenController(SimpleScreenService service) {
        this.service = service;
    }

    @GetMapping("/labs/api/{key:capacity|license|alert|query|top_segment|temp_table|vacuum|age}")
    public ResponseEntity<ApiResponse<ScreenResponse>> get(@PathVariable("key") String key) {
        try {
            return ResponseEntity.ok(ApiResponse.ok(service.find(key)));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(ApiResponse.error(e.getMessage()));
        } catch (IllegalStateException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }
}
