package com.exem.inspector.screen.partition;

import java.util.LinkedHashMap;
import java.util.List;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * Partition 화면 SQL — 원본 pages/partition.py + sql_library 의 partition SQL 1:1.
 *
 * <p>Drop List / Drop Exec(targets) / Drop Worker (실제 DROP)는 백그라운드 스레드에서 처리하므로
 * 본 Mapper 는 SELECT 만 — DROP/UPDATE 는 PartitionService 에서 JdbcTemplate 직접 사용.
 */
@Mapper
public interface PartitionMapper {

    /** apm_db_info 등록 인스턴스 목록 — Partition 화면 인스턴스 셀렉터용. */
    List<LinkedHashMap<String, Object>> findInstances();

    /** Drop 대상 파티션 목록 — _SQL_PARTITION_DROP_LIST / _SQL_PG_PARTITION_DROP_LIST 1:1. */
    List<LinkedHashMap<String, Object>> findDropList(@Param("dbId") int dbId);

    /** Drop 실행용 target 목록 — _SQL_PG_PARTITION_DROP_EXEC (PG). 한 행: schema, table, partition. */
    List<LinkedHashMap<String, Object>> findDropTargetsPg(@Param("dbId") int dbId);

    /** apm_db_info 에서 instance_name → db_id 룩업 — create-partition 진입 검증. */
    Integer findDbIdByInstance(@Param("instanceName") String instanceName);
}
