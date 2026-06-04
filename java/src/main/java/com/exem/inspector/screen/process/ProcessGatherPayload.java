package com.exem.inspector.screen.process;

import java.util.List;

/**
 * Process Gather Overview 응답 — 원본 page_process_gather() Overview 탭 1:1.
 *
 * <p>현재 Phase 2: overview 탭(다중 DGServer 로그 ERROR/WARN 마지막 500) 만.
 * Phase 3: OBSD 탭, 개별 DGM/DGSn 탭(검색 + time filter + Follow).
 */
public class ProcessGatherPayload {

    private final List<ProcessGatherSection> sections;
    private final int errLimitPerSection;   // 원본 OVERVIEW_LIMIT = 500
    private final String configError;       // service_config 미설정 시 사유

    public ProcessGatherPayload(List<ProcessGatherSection> sections, int errLimitPerSection, String configError) {
        this.sections = sections;
        this.errLimitPerSection = errLimitPerSection;
        this.configError = configError;
    }

    public List<ProcessGatherSection> getSections() { return sections; }
    public int getErrLimitPerSection() { return errLimitPerSection; }
    public String getConfigError() { return configError; }
}
