package com.exem.inspector.common.web.screen;

/**
 * 컬럼의 도메인 역할. 2층 공통 테이블 렌더러가 역할별 렌더링을 강제한다(I절 — 화면마다 제각각 금지).
 *
 * <ul>
 *   <li>{@code PLAIN} 일반 값(특별 처리 없음)</li>
 *   <li>{@code ID} 식별자(예: DB ID)</li>
 *   <li>{@code INSTANCE} 인스턴스명 — 인스턴스 검색 필터 대상</li>
 *   <li>{@code GROUP} 그룹 필터 칩 대상(예: SUMMARY_TYPE)</li>
 *   <li>{@code STATUS} 상태 배지(OK/CHECK/WAITING/ERROR)</li>
 *   <li>{@code DELAY} 지연 정보 — 보통 hidden, STATUS 툴팁에 부속 표시</li>
 * </ul>
 */
public enum ColumnRole {
    PLAIN,
    ID,
    INSTANCE,
    GROUP,
    STATUS,
    DELAY
}
