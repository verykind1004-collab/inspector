package com.exem.inspector.screen.controlprocess;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * Control Process 라우터.
 *
 * <p>{@code POST /labs/api/control-process/{action:start|stop|restart}} body: {@code {"name":"DGServer_S1"}}.
 * list 는 별도 endpoint 없이 기존 GET /labs/api/overview/services 재사용(상태/PID/포트 동일 정보).
 */
@RestController
public class ControlProcessController {

    private final ControlProcessService service;

    public ControlProcessController(ControlProcessService service) {
        this.service = service;
    }

    @PostMapping("/labs/api/control-process/{action:start|stop|restart}")
    public ResponseEntity<ApiResponse<ControlProcessResult>> act(
            @PathVariable("action") String action,
            @RequestBody(required = false) ControlProcessRequest req) {
        String name = req == null ? null : req.getName();
        if (name == null || name.isEmpty()) {
            return ResponseEntity.ok(ApiResponse.error("name is required"));
        }
        ControlProcessResult res;
        switch (action) {
            case "start":   res = service.start(name);   break;
            case "stop":    res = service.stop(name);    break;
            case "restart": res = service.restart(name); break;
            default: return ResponseEntity.ok(ApiResponse.error("Invalid action: " + action));
        }
        return ResponseEntity.ok(ApiResponse.ok(res));
    }
}
