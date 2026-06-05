package com.exem.inspector.screen.history;

import java.util.LinkedHashMap;
import java.util.List;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * History 화면용 매퍼 — INSP_OS_HISTORY / INSP_TBS_HISTORY / INSP_SERVICE_HISTORY /
 * INSP_HEAP_HISTORY / INSP_QCNT_HISTORY / INSP_SUMMARY_HISTORY 6종.
 *
 * <p>days 파라미터로 최근 N일 제한(통합 표용). Session 2 보강: HEAP view 추가.
 * <p>findOsRange/findTbsRange/findHeapRange/findQcntRange/findServiceRange 는
 * 페이지별 차트용 — 원본 api_history_* 와 동일하게 start/end timestamp(YYYY-MM-DD HH24:MI:SS) 범위 조회.
 */
@Mapper
public interface HistoryMapper {

    List<LinkedHashMap<String, Object>> findOsHistory(@Param("days") int days, @Param("limit") int limit);

    List<LinkedHashMap<String, Object>> findTbsHistory(@Param("days") int days, @Param("limit") int limit);

    List<LinkedHashMap<String, Object>> findServiceHistory(@Param("days") int days, @Param("limit") int limit);

    List<LinkedHashMap<String, Object>> findHeapHistory(@Param("days") int days, @Param("limit") int limit);

    List<LinkedHashMap<String, Object>> findQcntHistory(@Param("days") int days, @Param("limit") int limit);

    List<LinkedHashMap<String, Object>> findSummaryHistory(@Param("days") int days, @Param("limit") int limit);

    /** /labs/api/history-os 1:1 — INSP_OS_HISTORY 시계열(start/end timestamp). */
    List<LinkedHashMap<String, Object>> findOsRange(@Param("start") String start, @Param("end") String end);

    /** /labs/api/history-tbs 1:1 — INSP_TBS_HISTORY 시계열(start/end timestamp). */
    List<LinkedHashMap<String, Object>> findTbsRange(@Param("start") String start, @Param("end") String end);

    /** /labs/api/history-service 1:1 — INSP_SERVICE_HISTORY 시계열(start/end timestamp). */
    List<LinkedHashMap<String, Object>> findServiceRange(@Param("start") String start, @Param("end") String end);
}
