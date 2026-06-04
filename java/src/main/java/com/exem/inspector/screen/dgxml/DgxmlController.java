package com.exem.inspector.screen.dgxml;

import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * DGServer.xml Parameter Modify 라우터 — 원본 pages/dgxml_modify.py 1:1.
 *
 * <ul>
 *   <li>GET  /labs/api/dgxml/parse — DGServer_M/S* 의 모든 파라미터 노출</li>
 *   <li>GET  /labs/api/dgxml/search?param= — 파라미터 검색</li>
 *   <li>POST /labs/api/dgxml/save — 일괄 변경 + .bak 백업</li>
 * </ul>
 */
@RestController
public class DgxmlController {

    private final DgxmlService service;

    public DgxmlController(DgxmlService service) {
        this.service = service;
    }

    @GetMapping("/labs/api/dgxml/parse")
    public ResponseEntity<ApiResponse<List<DgxmlService.DgxmlFile>>> parse() {
        return ResponseEntity.ok(ApiResponse.ok(service.parseAll()));
    }

    @GetMapping("/labs/api/dgxml/search")
    public ResponseEntity<ApiResponse<DgxmlService.SearchResult>> search(
            @RequestParam(name = "param") String paramName) {
        return ResponseEntity.ok(ApiResponse.ok(service.search(paramName)));
    }

    @PostMapping("/labs/api/dgxml/save")
    public ResponseEntity<ApiResponse<DgxmlService.SaveResult>> save(
            @RequestBody(required = false) DgxmlService.SaveRequest body) {
        return ResponseEntity.ok(ApiResponse.ok(service.save(body)));
    }
}
