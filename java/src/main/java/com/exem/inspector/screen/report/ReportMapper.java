package com.exem.inspector.screen.report;

import java.util.LinkedHashMap;
import java.util.List;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * Report 화면 SQL — 원본 report.py + insp_oracle/insp_pg 의 monthly_summary 와 1:1 동등.
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

    /** apm_db_info 인스턴스 카운트 (원본 _inst_out). */
    int countInstances();

    /**
     * INSP_MONTHLY_SUMMARY 년도별 조회 — 원본 insp_query_monthly_summary / insp_pg_query_monthly_summary.
     * 반환 행: year_month, cpu_avg, mem_avg, mem_used_gb, mem_total_gb,
     *        disk_avg, disk_used_gb, disk_total_gb
     */
    List<LinkedHashMap<String, Object>> findMonthlyResourceSummary(@Param("yearPrefix") String yearPrefix);
}
