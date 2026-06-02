package com.exem.inspector.screen.overview;

import java.util.List;

import org.apache.ibatis.annotations.Mapper;

/**
 * Overview Disk/Tablespace 매퍼 — Oracle 전용.
 *
 * <p>PG 는 SQL 미사용(`Files.getFileStore` 로 파일 시스템 stat 직접 조회).
 * databaseId 분기로 PG 빈 결과 반환.
 */
@Mapper
public interface OverviewDiskMapper {

    /**
     * Oracle: 현 user 의 default tablespace 들에 대해 used/total/free/pct.
     * 원본 _SQL_ORACLE_TABLESPACE_OVERVIEW 와 동일.
     */
    List<TablespaceRow> findOracleTablespaces();
}
