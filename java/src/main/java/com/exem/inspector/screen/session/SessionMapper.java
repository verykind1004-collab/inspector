package com.exem.inspector.screen.session;

import java.util.List;
import org.apache.ibatis.annotations.Mapper;

/**
 * Session Check 진단 SQL 매퍼(원본 _SQL_SESSION / _SQL_PG_SESSION).
 *
 * <p>databaseId 로 Oracle/PG 분기(원본의 db_type 분기와 동등).
 * 리포지토리 미설정 시 선택적 주입(미설정 = 빈 미등록).
 */
@Mapper
public interface SessionMapper {

    /** 인스턴스별 마지막 세션 수집 시각. */
    List<SessionRow> findSession();
}
