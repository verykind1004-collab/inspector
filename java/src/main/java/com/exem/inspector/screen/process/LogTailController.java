package com.exem.inspector.screen.process;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * 로그 tail/seek 라우터 — 원본 {@code /api/log-tail} 1:1.
 *
 * <p>URL: {@code GET /labs/api/log-tail?path=<>&offset=<long>}.
 * 응답: {@link LogTailResult} (lines/offset 또는 error).
 *
 * <p>원본 process.py 의 Follow 모드(2초 setInterval)에서 호출되는 endpoint.
 */
@RestController
public class LogTailController {

    private final LogTailService service;

    public LogTailController(LogTailService service) {
        this.service = service;
    }

    @GetMapping("/labs/api/log-tail")
    public ResponseEntity<ApiResponse<LogTailResult>> get(
            @RequestParam(name = "path") String path,
            @RequestParam(name = "offset", required = false, defaultValue = "0") long offset) {
        LogTailResult r = service.read(path, offset);
        return ResponseEntity.ok(ApiResponse.ok(r));
    }
}
