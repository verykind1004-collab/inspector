package com.exem.inspector.screen.overview;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * Overview 화면 API.
 *
 * <p>원본 {@code pages/overview.py::page_overview / api_vitals / api_services /
 * api_tablespace} 와 대응. 본 단계는 system + vitals 만 제공 (services / disk·tablespace
 * 는 후속 단계에서 추가).
 *
 * <p>모든 응답은 표준 봉투(ApiResponse) 로 감싸 일관 처리한다.
 */
@RestController
@RequestMapping("/labs/api/overview")
public class OverviewController {

    private final OverviewService service;

    public OverviewController(OverviewService service) {
        this.service = service;
    }

    /** System 카드 — Hostname/OS/Uptime/Cores. 정적 정보로 폴링 불필요. */
    @GetMapping("/system")
    public ApiResponse<Map<String, Object>> system() {
        return ApiResponse.ok(service.system());
    }

    /** Vitals — CPU + Memory. 프런트가 3초 간격 폴링 (원본 setInterval 3000ms). */
    @GetMapping("/vitals")
    public ApiResponse<Map<String, Object>> vitals() {
        return ApiResponse.ok(service.vitals());
    }
}
