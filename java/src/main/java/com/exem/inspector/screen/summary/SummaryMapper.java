package com.exem.inspector.screen.summary;

import java.util.List;

import org.apache.ibatis.annotations.Mapper;

/**
 * Summary Check 진단 SQL 매퍼. databaseId 로 Oracle/PG 를 분기한다(매퍼 XML — I절 규약).
 *
 * <p>DataSource 미설정 시 SqlSessionFactory 가 backoff 하여 이 매퍼 빈은 등록되지 않는다.
 * 따라서 주입측({@code SummaryService})은 선택적(ObjectProvider)으로 다뤄 부팅을 막지 않는다.
 */
@Mapper
public interface SummaryMapper {

    /** 최근 10분 요약 수집 상태(apm_db_info LEFT JOIN ora_last_summary '%10Min%'). */
    List<SummaryRow> findSummary10Min();

    /** 최근 1시간(Daily) 요약 수집 상태('%Daily%'). */
    List<SummaryRow> findSummary1Hour();
}
