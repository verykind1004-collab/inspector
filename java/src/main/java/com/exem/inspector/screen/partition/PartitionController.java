package com.exem.inspector.screen.partition;

import java.util.List;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * Partition 라우터 — 원본 partition.py 의 5 API 1:1 동등.
 *
 * <ul>
 *   <li>GET  /labs/api/partition/instances — 인스턴스 셀렉터</li>
 *   <li>GET  /labs/api/partition/drop-list?db_id= — Drop 후보 목록 (groups)</li>
 *   <li>POST /labs/api/partition/drop?db_id= — 백그라운드 Drop 시작</li>
 *   <li>GET  /labs/api/partition/drop-status — 진행 상태</li>
 *   <li>POST /labs/api/partition/create?instance_name=&date_from=&date_to= — 파티션 생성</li>
 *   <li>POST /labs/api/partition/create-procedure — Oracle 프로시저 재생성</li>
 * </ul>
 */
@RestController
public class PartitionController {

    private final PartitionService service;

    public PartitionController(PartitionService service) {
        this.service = service;
    }

    @GetMapping("/labs/api/partition/instances")
    public ResponseEntity<ApiResponse<List<Map<String, Object>>>> instances() {
        return ResponseEntity.ok(ApiResponse.ok(service.instances()));
    }

    @GetMapping("/labs/api/partition/drop-list")
    public ResponseEntity<ApiResponse<PartitionService.DropListResult>> dropList(
            @RequestParam(name = "db_id") int dbId) {
        return ResponseEntity.ok(ApiResponse.ok(service.dropList(dbId)));
    }

    @PostMapping("/labs/api/partition/drop")
    public ResponseEntity<ApiResponse<Map<String, Object>>> drop(
            @RequestParam(name = "db_id") int dbId) {
        return ResponseEntity.ok(ApiResponse.ok(service.startDropPartitions(dbId)));
    }

    @GetMapping("/labs/api/partition/drop-status")
    public ResponseEntity<ApiResponse<PartitionService.DropState>> dropStatus() {
        return ResponseEntity.ok(ApiResponse.ok(service.dropStatus()));
    }

    @PostMapping("/labs/api/partition/create")
    public ResponseEntity<ApiResponse<Map<String, Object>>> create(
            @RequestParam(name = "instance_name") String instanceName,
            @RequestParam(name = "date_from", required = false, defaultValue = "") String dateFrom,
            @RequestParam(name = "date_to", required = false, defaultValue = "") String dateTo) {
        return ResponseEntity.ok(ApiResponse.ok(service.createPartition(instanceName, dateFrom, dateTo)));
    }

    @PostMapping("/labs/api/partition/create-procedure")
    public ResponseEntity<ApiResponse<Map<String, Object>>> createProcedure() {
        return ResponseEntity.ok(ApiResponse.ok(service.createProcedure()));
    }
}
