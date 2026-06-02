package com.exem.inspector.screen.simple;

import java.util.LinkedHashMap;
import java.util.List;

import org.apache.ibatis.annotations.Mapper;

/**
 * 원본 _db_page 패턴 단순 SQL 점검 화면 매퍼.
 *
 * <p>모든 결과는 {@code LinkedHashMap<컬럼라벨, 값>} 으로 받는다(원본 _parse_db_table 의 헤더-값 매핑과 동등).
 * 컬럼 메타·필터·제목은 화면별 Service 에서 고정 정의한다(I절 — 화면이 SQL/커넥션 직접 미취급).
 *
 * <p>databaseId 분기는 mapper XML 에서 처리. PG 미지원 화면(Oracle 전용)은 PG 변형 미존재.
 */
@Mapper
public interface SimpleScreenMapper {

    /** Capacity Check — 저장소 스키마 디스크 사용량. */
    List<LinkedHashMap<String, Object>> findCapacity();

    /** Instance List — apm_db_info 등록 인스턴스. */
    List<LinkedHashMap<String, Object>> findLicense();

    /** Alert Check — 최근 30일 알람 이력. */
    List<LinkedHashMap<String, Object>> findAlert();

    /** Query Check — 인스턴스별 query base 수집 상태. */
    List<LinkedHashMap<String, Object>> findQuery();

    /** Top Segment — 용량 상위 30개 세그먼트. */
    List<LinkedHashMap<String, Object>> findTopSegment();

    /** Temp Table — TT* / tt* 임시 테이블 목록. */
    List<LinkedHashMap<String, Object>> findTempTable();

    /** Vacuum Check (PG 전용) — autovacuum 임계 초과 + 3일 미실행. */
    List<LinkedHashMap<String, Object>> findVacuum();

    /** Age Check (PG 전용) — datfrozenxid 노화 확인. */
    List<LinkedHashMap<String, Object>> findAge();
}
