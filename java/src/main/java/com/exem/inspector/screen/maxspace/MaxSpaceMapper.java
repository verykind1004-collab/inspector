package com.exem.inspector.screen.maxspace;

import java.util.List;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import com.exem.inspector.screen.maxspace.dto.InstanceRow;
import com.exem.inspector.screen.maxspace.dto.ServiceGroupRow;
import com.exem.inspector.screen.maxspace.dto.TablespaceRow;

/**
 * MaxSpace 데이터 조회 매퍼.
 *
 * <p>databaseId 분기로 PG / Oracle 두 쿼리 동시 정의. 원본 tablespace_server.py 의
 * {@code find_tablespace_schemas} / {@code get_instances} / {@code get_service_groups} /
 * {@code get_ts_data} 와 SQL 1:1.
 *
 * <p>PG 의 schema 동적 치환은 ${} 으로 직접 삽입 (Service 단에서 _validate_schema 와
 * 동등한 정규식 검증을 수행한 뒤 호출).
 */
@Mapper
public interface MaxSpaceMapper {

    /**
     * PG: information_schema 에서 ora_tablespace_info 를 보유한 스키마 목록.
     * Oracle: USER 1 개.
     */
    List<String> findTablespaceSchemas();

    /** apm_db_info 의 db_id / instance_name / business_name 목록. */
    List<InstanceRow> findInstances();

    /** ora_service_name × ora_service_info × apm_db_info join 의 row 목록. */
    List<ServiceGroupRow> findServiceGroupRows();

    /**
     * 인스턴스 1개의 ora_tablespace_info latest snapshot + 1주/1개월 사용률.
     *
     * @param schema PG 의 경우 인스턴스 스키마명 (예: "p_inst01"). 정규식 검증 후 전달.
     *               Oracle 은 무시 (XML 의 SQL 이 schema 미사용).
     * @param dbId   apm_db_info.db_id
     */
    List<TablespaceRow> findTablespaceData(@Param("schema") String schema,
                                           @Param("dbId") int dbId);
}
