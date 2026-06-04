package com.exem.inspector.screen.alert;

import java.util.LinkedHashMap;
import java.util.List;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * Alert 일별 카운트 매퍼.
 *
 * <p>Oracle/PG 분기는 매퍼 XML 의 {@code databaseId}.
 * 결과는 {@code DAY (YYYY-MM-DD), CNT (int)} 두 컬럼.
 * PG 는 schema 이름(인스턴스명 정규화)을 SQL 식별자로 직접 치환해야 하므로 {@code ${schema}} 사용 — 호출 전 strict 검증 필수.
 */
@Mapper
public interface AlertMapper {

    /**
     * 원본 {@code api_alert_times} 의 Oracle/PG SQL 과 1:1 동등.
     *
     * @param schema PG 전용 schema 이름(영문 소문자/숫자/언더스코어만 허용된 안전한 식별자). Oracle 에서는 무시.
     * @param inst   인스턴스명(따옴표 이스케이프된 상태로 전달 필요 없음 — MyBatis 가 처리)
     * @param alarm  알람명
     */
    List<LinkedHashMap<String, Object>> findDailyCounts(
            @Param("schema") String schema,
            @Param("inst") String inst,
            @Param("alarm") String alarm);
}
