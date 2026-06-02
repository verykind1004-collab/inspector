package com.exem.inspector.screen.history;

import java.util.LinkedHashMap;
import java.util.List;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * History 화면용 매퍼 — INSP_OS_HISTORY / INSP_TBS_HISTORY / INSP_SERVICE_HISTORY /
 * INSP_QCNT_HISTORY / INSP_SUMMARY_HISTORY 5종. days 파라미터로 최근 N일 제한.
 */
@Mapper
public interface HistoryMapper {

    List<LinkedHashMap<String, Object>> findOsHistory(@Param("days") int days, @Param("limit") int limit);

    List<LinkedHashMap<String, Object>> findTbsHistory(@Param("days") int days, @Param("limit") int limit);

    List<LinkedHashMap<String, Object>> findServiceHistory(@Param("days") int days, @Param("limit") int limit);

    List<LinkedHashMap<String, Object>> findQcntHistory(@Param("days") int days, @Param("limit") int limit);

    List<LinkedHashMap<String, Object>> findSummaryHistory(@Param("days") int days, @Param("limit") int limit);
}
