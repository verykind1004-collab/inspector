package com.exem.inspector.screen.summary;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;
import com.exem.inspector.common.web.screen.ScreenResponse;

/**
 * Summary Check 화면 API. 기존 Python page_summary_10min / page_summary_1hour 에 대응한다.
 *
 * <p>표준 표 응답(ScreenResponse)을 표준 봉투(ApiResponse)로 반환한다(I절 — 백엔드 공통화).
 * 리포지토리 미설정 등 운영 실패는 ApiResponse.error 로 변환한다(기존 _warn_box 대체).
 */
@RestController
@RequestMapping("/labs/api/summary")
public class SummaryController {

    private final SummaryService service;

    public SummaryController(SummaryService service) {
        this.service = service;
    }

    @GetMapping("/10min")
    public ApiResponse<ScreenResponse> summary10Min() {
        try {
            return ApiResponse.ok(service.summary10Min());
        } catch (IllegalStateException e) {
            return ApiResponse.error(e.getMessage());
        }
    }

    @GetMapping("/1hour")
    public ApiResponse<ScreenResponse> summary1Hour() {
        try {
            return ApiResponse.ok(service.summary1Hour());
        } catch (IllegalStateException e) {
            return ApiResponse.error(e.getMessage());
        }
    }
}
