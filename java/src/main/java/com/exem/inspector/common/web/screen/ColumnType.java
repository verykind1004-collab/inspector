package com.exem.inspector.common.web.screen;

/**
 * 표준 표 응답에서 컬럼 값의 표현 타입.
 *
 * <p>2층 공통 테이블 렌더러의 정렬·정렬방향·포맷 기준이 된다(I절 — 화면마다 제각각 금지).
 */
public enum ColumnType {
    /** 문자열(사전식 정렬). */
    STRING,
    /** 숫자(수치 정렬, 우측 정렬). */
    NUMBER,
    /** 일시(문자열로 전달, 시간순 정렬). */
    DATETIME
}
