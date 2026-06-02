package com.exem.inspector.screen.report;

import java.util.LinkedHashMap;
import java.util.Map;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * Report 화면 SQL — INSP_OS_HISTORY 어제 평균 + apm_db_info 인스턴스 카운트.
 */
@Mapper
public interface ReportMapper {

    /**
     * INSP_OS_HISTORY 의 어제 평균 — CPU/Memory 컬럼.
     * 반환 키: cpu_percent / cpu_user / cpu_system / cpu_iowait / mem_total_gb /
     *         mem_used_gb / mem_free_gb / mem_percent / cnt
     */
    LinkedHashMap<String, Object> findYesterdayOsAvg(
            @Param("yesterday") String yesterday,
            @Param("today") String today);

    /** apm_db_info 인스턴스 카운트(원본 _inst_out). */
    int countInstances();

    /** apm_license_db_info 의 valid 카운트(VALID / NONE 등 그룹) — Check Status License 행 결정용. */
    Map<String, Object> countValidLicenseDbInfo();
}
