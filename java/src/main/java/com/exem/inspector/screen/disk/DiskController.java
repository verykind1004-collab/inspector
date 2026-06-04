package com.exem.inspector.screen.disk;

import java.util.List;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * Disk(Vacuum/Age + Temp Table) 라우터 — 원본 pages/disk.py 의 API 9개 1:1 동등.
 *
 * <p>원본 URL prefix 는 {@code /utils} (UTILS_BASE) — Java BE 는 다른 화면과 일관성을 위해
 * {@code /labs/api} prefix 채택 (partition / config / overview / process 등과 동일 규칙).
 * 라우트 변경은 컨트롤러 어노테이션 만 다르고 핸들러 동작은 1:1.
 *
 * <ul>
 *   <li>GET  /labs/api/vacuum-log           — 신규 (SPA 1:1 적응: 원본은 page 조립 시 server-side 렌더)</li>
 *   <li>GET  /labs/api/auto-vacuum          — 신규 (SPA 1:1 적응: 원본은 _auto_vacuum_card 렌더)</li>
 *   <li>GET  /labs/api/age-card             — 원본 api_age_card 1:1</li>
 *   <li>GET  /labs/api/temp-table-list      — 신규 (SPA 1:1 적응: 원본은 page_disk_temp_table 렌더)</li>
 *   <li>POST /labs/api/vacuum-freeze        — 원본 api_vacuum_freeze 1:1 (원본 method 무지정=GET, Java POST 채택)</li>
 *   <li>GET  /labs/api/vacuum-freeze-status — 원본 api_vacuum_freeze_status 1:1</li>
 *   <li>POST /labs/api/vacuum-table         — 원본 api_vacuum_table 1:1</li>
 *   <li>GET  /labs/api/vacuum-table-status  — 원본 api_vacuum_table_status 1:1</li>
 *   <li>POST /labs/api/temp-table-drop-all  — 원본 api_temp_table_drop_all 1:1</li>
 *   <li>GET  /labs/api/temp-table-drop-status — 원본 api_temp_table_drop_status 1:1</li>
 * </ul>
 */
@RestController
public class DiskController {

    private final DiskService service;

    public DiskController(DiskService service) {
        this.service = service;
    }

    // ── Cards ────────────────────────────────────────────────────────

    @GetMapping("/labs/api/vacuum-log")
    public ResponseEntity<ApiResponse<Map<String, Object>>> vacuumLog() {
        return ResponseEntity.ok(ApiResponse.ok(service.vacuumLog()));
    }

    @GetMapping("/labs/api/auto-vacuum")
    public ResponseEntity<ApiResponse<List<Map<String, Object>>>> autoVacuum() {
        return ResponseEntity.ok(ApiResponse.ok(service.autoVacuumCard()));
    }

    @GetMapping("/labs/api/age-card")
    public ResponseEntity<ApiResponse<List<Map<String, Object>>>> ageCard() {
        return ResponseEntity.ok(ApiResponse.ok(service.ageCard()));
    }

    @GetMapping("/labs/api/temp-table-list")
    public ResponseEntity<ApiResponse<List<Map<String, Object>>>> tempTableList() {
        return ResponseEntity.ok(ApiResponse.ok(service.tempTableList()));
    }

    // ── VACUUM FREEZE ────────────────────────────────────────────────

    @PostMapping("/labs/api/vacuum-freeze")
    public ResponseEntity<ApiResponse<Map<String, Object>>> vacuumFreeze() {
        return ResponseEntity.ok(ApiResponse.ok(service.startVacuumFreeze()));
    }

    @GetMapping("/labs/api/vacuum-freeze-status")
    public ResponseEntity<ApiResponse<DiskService.VacuumFreezeState>> vacuumFreezeStatus() {
        return ResponseEntity.ok(ApiResponse.ok(service.vacuumFreezeStatus()));
    }

    // ── VACUUM TABLE ─────────────────────────────────────────────────

    @PostMapping("/labs/api/vacuum-table")
    public ResponseEntity<ApiResponse<Map<String, Object>>> vacuumTable() {
        return ResponseEntity.ok(ApiResponse.ok(service.startVacuumTable()));
    }

    @GetMapping("/labs/api/vacuum-table-status")
    public ResponseEntity<ApiResponse<DiskService.VacuumTableState>> vacuumTableStatus() {
        return ResponseEntity.ok(ApiResponse.ok(service.vacuumTableStatus()));
    }

    // ── TEMP TABLE DROP ──────────────────────────────────────────────

    @PostMapping("/labs/api/temp-table-drop-all")
    public ResponseEntity<ApiResponse<Map<String, Object>>> tempTableDropAll() {
        return ResponseEntity.ok(ApiResponse.ok(service.startTempTableDropAll()));
    }

    @GetMapping("/labs/api/temp-table-drop-status")
    public ResponseEntity<ApiResponse<DiskService.TempTableDropState>> tempTableDropStatus() {
        return ResponseEntity.ok(ApiResponse.ok(service.tempTableDropStatus()));
    }
}
