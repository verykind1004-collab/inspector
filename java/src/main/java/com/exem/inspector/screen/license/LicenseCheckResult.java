package com.exem.inspector.screen.license;

import java.util.List;

import com.exem.inspector.common.web.screen.ScreenResponse;

/**
 * License Check 화면 통합 응답 — 원본 page_license_check() 3 카드와 1:1 동등.
 *
 * <ul>
 *   <li>{@code info}: License Info 카드 — apm_license 표 + 파일명 파싱(TRIAL/TERM, D-Day).</li>
 *   <li>{@code instances}: Instance License Status 카드 — 표준 표 응답(2층 ScreenTable 소비).</li>
 *   <li>{@code events}: Recent License Events 카드 — DGM 로그 파싱.</li>
 *   <li>{@code *Error}: 카드별 오류(원본 _warn_box 등가). null 이면 정상.</li>
 * </ul>
 */
public class LicenseCheckResult {

    private final List<LicenseInfoRow> info;
    private final String infoError;
    private final ScreenResponse instances;
    private final String instancesError;
    private final List<LicenseEventRow> events;
    private final String eventsError;

    public LicenseCheckResult(List<LicenseInfoRow> info, String infoError,
                              ScreenResponse instances, String instancesError,
                              List<LicenseEventRow> events, String eventsError) {
        this.info = info;
        this.infoError = infoError;
        this.instances = instances;
        this.instancesError = instancesError;
        this.events = events;
        this.eventsError = eventsError;
    }

    public List<LicenseInfoRow> getInfo() { return info; }
    public String getInfoError() { return infoError; }
    public ScreenResponse getInstances() { return instances; }
    public String getInstancesError() { return instancesError; }
    public List<LicenseEventRow> getEvents() { return events; }
    public String getEventsError() { return eventsError; }
}
