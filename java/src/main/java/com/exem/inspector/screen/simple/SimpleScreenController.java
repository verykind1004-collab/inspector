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
 * <p>URL 화이트리스트 = 등록된 화면 키만 허용. license 응답에는 DGS PORT 컬럼 동적 추가(B-1).
 */
@RestController
public class SimpleScreenController {

    private final SimpleScreenService service;
    private final LicenseDgsPortEnricher licenseEnricher;

    public SimpleScreenController(SimpleScreenService service, LicenseDgsPortEnricher licenseEnricher) {
        this.service = service;
        this.licenseEnricher = licenseEnricher;
    }

    @GetMapping("/labs/api/{key:capacity|license|alert|query|top_segment|temp_table|vacuum|age}")
    public ResponseEntity<ApiResponse<ScreenResponse>> get(@PathVariable("key") String key) {
        try {
            ScreenResponse r = service.find(key);
            if ("license".equals(key)) {
                r = licenseEnricher.enrich(r);
            }
            return ResponseEntity.ok(ApiResponse.ok(r));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(ApiResponse.error(e.getMessage()));
        } catch (IllegalStateException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }
}
