package com.exem.inspector.screen.maxspace;

import java.util.List;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import com.exem.inspector.screen.maxspace.dto.InstanceRow;
import com.exem.inspector.screen.maxspace.dto.ServiceGroupRow;
import com.exem.inspector.screen.maxspace.dto.TablespaceRow;
import com.exem.inspector.screen.maxspace.dto.TrendPoint;
import com.exem.inspector.screen.maxspace.dto.UserAdminRow;

/**
 * MaxSpace 데이터 조회 매퍼.
 *
 * <p>databaseId 분기로 PG / Oracle 두 쿼리 동시 정의. 원본 tablespace_server.py 의
 * {@code find_tablespace_schemas} / {@code get_instances} / {@code get_service_groups} /
 * {@code get_ts_data} / {@code get_trend} / {@code _fetch_user_dbids} 와 SQL 1:1.
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
     * @param schema PG 의 경우 인스턴스 스키마명. Oracle 은 무시.
     * @param dbId   apm_db_info.db_id
     */
    List<TablespaceRow> findTablespaceData(@Param("schema") String schema,
                                           @Param("dbId") int dbId);

    /**
     * 인스턴스 1개의 시계열 트렌드 — (ts_name, snap_day) 단위의 total/used.
     * 원본 get_trend 1:1.
     */
    List<TrendPoint> findTrend(@Param("schema") String schema,
                               @Param("dbId") int dbId);

    /**
     * apm_user_list 에서 user_id 로 seq + admin_role 한 행. 원본 _fetch_user_dbids 첫 조회 1:1.
     * 없으면 null.
     */
    UserAdminRow findUserSeqAndAdminRole(@Param("userId") String userId);

    /**
     * apm_users_db_list 에서 seq 의 허용 db_id 목록.
     * db_id NOT IN ('0','9999') AND role1~6 중 하나 ≥ 1. 원본 1:1.
     */
    List<Integer> findUserAllowedDbIds(@Param("seq") Long seq);
}
