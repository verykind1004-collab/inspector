package com.exem.inspector.screen.session;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;
import com.exem.inspector.common.web.screen.ScreenResponse;

/**
 * Session Check 화면 API. 원본 page_session 에 대응.
 */
@RestController
public class SessionController {

    private final SessionService service;

    public SessionController(SessionService service) {
        this.service = service;
    }

    @GetMapping("/labs/api/session")
    public ApiResponse<ScreenResponse> session() {
        try {
            return ApiResponse.ok(service.find());
        } catch (IllegalStateException e) {
            return ApiResponse.error(e.getMessage());
        }
    }
}
