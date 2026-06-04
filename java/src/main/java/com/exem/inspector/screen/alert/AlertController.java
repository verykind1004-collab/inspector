package com.exem.inspector.screen.alert;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * Alert page COUNT/ALARM 셀 툴팁용 일별 카운트 조회.
 *
 * <p>원본 {@code page_alert::api_alert_times} (alert.py:15) 1:1 대응.
 * 최근 30일 (instance_name, alarm_name) 별 일별 발생 카운트를 반환한다.
 */
@RestController
public class AlertController {

    private final AlertService service;

    public AlertController(AlertService service) {
        this.service = service;
    }

    /**
     * {@code GET /labs/api/alert-times?inst=&alarm=}.
     *
     * <p>응답: {@code {ok, days:[{day,count}], total}} 또는 {@code {ok:false, error}}.
     * 봉투(ApiResponse) 외부 data 에 위 구조를 포함.
     */
    @GetMapping("/labs/api/alert-times")
    public ResponseEntity<ApiResponse<AlertTimesResponse>> get(
            @RequestParam(name = "inst", required = false) String inst,
            @RequestParam(name = "alarm", required = false) String alarm) {
        try {
            return ResponseEntity.ok(ApiResponse.ok(service.build(inst, alarm)));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }
}
