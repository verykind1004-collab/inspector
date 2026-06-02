package com.exem.inspector.screen.overview;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.exem.inspector.common.web.ApiResponse;

/**
 * Overview 화면 API.
 *
 * <p>원본 {@code pages/overview.py::page_overview / api_vitals / api_tablespace /
 * api_services} 와 대응.
 *
 * <p>모든 응답은 표준 봉투(ApiResponse) 로 감싸 일관 처리한다.
 */
@RestController
@RequestMapping("/labs/api/overview")
public class OverviewController {

    private final OverviewService service;
    private final OverviewDiskService diskService;
    private final OverviewServicesService servicesService;

    public OverviewController(OverviewService service,
                              OverviewDiskService diskService,
                              OverviewServicesService servicesService) {
        this.service = service;
        this.diskService = diskService;
        this.servicesService = servicesService;
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

    /**
     * Disk/Tablespace 카드.
     * Oracle 이면 default tablespace 목록, PG 면 pg_data_dir 의 OS 디스크 stat.
     */
    @GetMapping("/disk")
    public ApiResponse<Map<String, Object>> disk() {
        try {
            return ApiResponse.ok(diskService.disk());
        } catch (IllegalStateException e) {
            return ApiResponse.error(e.getMessage());
        }
    }

    /**
     * Services 카드 — DGServer_M/S, PlatformJS, Client, Repo DB 상태/포트/버전.
     * 원본 api_services 등가. 3초 간격 폴링 대상.
     */
    @GetMapping("/services")
    public ApiResponse<Map<String, Object>> services() {
        return ApiResponse.ok(servicesService.services());
    }
}
