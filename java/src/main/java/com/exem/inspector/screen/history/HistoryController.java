package com.exem.inspector.screen.history;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;
import com.exem.inspector.common.web.screen.ScreenResponse;

@RestController
public class HistoryController {

    private final HistoryService service;

    public HistoryController(HistoryService service) {
        this.service = service;
    }

    /** {@code GET /labs/api/history/{view:os|tbs|service|qcnt|summary}?days=7&limit=500}. */
    @GetMapping("/labs/api/history/{view:os|tbs|service|qcnt|summary}")
    public ResponseEntity<ApiResponse<ScreenResponse>> get(
            @PathVariable("view") String view,
            @RequestParam(name = "days",  defaultValue = "7")   int days,
            @RequestParam(name = "limit", defaultValue = "500") int limit) {
        try {
            return ResponseEntity.ok(ApiResponse.ok(service.find(view, days, limit)));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        } catch (RuntimeException e) {
            return ResponseEntity.ok(ApiResponse.error(e.getMessage()));
        }
    }
}
