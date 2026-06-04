package com.exem.inspector.screen.disk;

import java.util.LinkedHashMap;
import java.util.List;

import org.apache.ibatis.annotations.Mapper;

/**
 * Disk(Vacuum/Age/Temp Table) 화면 SQL — 원본 sql_library 의
 * _SQL_PG_VACUUM_CHECK / _SQL_PG_AGE / _SQL_PG_TEMP_TABLE / _SQL_ORACLE_TEMP_TABLE 1:1.
 *
 * <p>vacuum / age 는 PostgreSQL 전용 (Oracle 미지원). temp_table 은 PG/Oracle 모두 지원.
 * <p>실제 VACUUM FREEZE / VACUUM TABLE / DROP TABLE 등 DML 은 DiskService 에서 JdbcTemplate 직접 사용.
 */
@Mapper
public interface DiskMapper {

    /** _SQL_PG_VACUUM_CHECK — 수동 vacuum 필요한 테이블 (PG 전용). */
    List<LinkedHashMap<String, Object>> findAutoVacuumTargets();

    /** _SQL_PG_AGE — datfrozenxid age 진단 (PG 전용). */
    List<LinkedHashMap<String, Object>> findAge();

    /** _SQL_PG_TEMP_TABLE / _SQL_ORACLE_TEMP_TABLE — tt% prefix 미삭제 테이블. */
    List<LinkedHashMap<String, Object>> findTempTables();
}
