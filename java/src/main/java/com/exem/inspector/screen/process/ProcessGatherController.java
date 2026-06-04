package com.exem.inspector.screen.process;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * Process Gather 라우터 — 원본 {@code /process/gather} 1:1.
 *
 * <ul>
 *   <li>GET /labs/api/process/gather         → {@link ProcessGatherPayload} (Overview 탭)</li>
 *   <li>GET /labs/api/process/gather/obsd    → {@link ObsdPayload} (OBSD 탭 카드 메타)</li>
 *   <li>GET /labs/api/process/gather/log-server?tabId=&file=&search=&timeFrom=&timeTo=
 *       → {@link LogServerPayload} (DGM/DGS_n 탭 통합)</li>
 * </ul>
 *
 * <p>OBSD/log-server 의 실제 본문(전체 라인)은 별도 {@code /labs/api/log-tail}
 * (Follow 폴링/On-demand)와 함께 사용된다.
 */
@RestController
public class ProcessGatherController {

    private final ProcessGatherService service;
    private final ObsdService obsdService;
    private final LogServerService logServerService;

    public ProcessGatherController(ProcessGatherService service,
                                    ObsdService obsdService,
                                    LogServerService logServerService) {
        this.service = service;
        this.obsdService = obsdService;
        this.logServerService = logServerService;
    }

    @GetMapping("/labs/api/process/gather")
    public ResponseEntity<ApiResponse<ProcessGatherPayload>> get() {
        try {
            return ResponseEntity.ok(ApiResponse.ok(service.overview()));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }

    @GetMapping("/labs/api/process/gather/obsd")
    public ResponseEntity<ApiResponse<ObsdPayload>> obsd() {
        try {
            return ResponseEntity.ok(ApiResponse.ok(obsdService.listProcs()));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }

    @GetMapping("/labs/api/process/gather/log-server")
    public ResponseEntity<ApiResponse<LogServerPayload>> logServer(
            @RequestParam(name = "tabId",    required = false) String tabId,
            @RequestParam(name = "file",     required = false) String file,
            @RequestParam(name = "search",   required = false) String search,
            @RequestParam(name = "timeFrom", required = false) String timeFrom,
            @RequestParam(name = "timeTo",   required = false) String timeTo) {
        try {
            return ResponseEntity.ok(ApiResponse.ok(
                    logServerService.build(tabId, file, search, timeFrom, timeTo)));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }
}
