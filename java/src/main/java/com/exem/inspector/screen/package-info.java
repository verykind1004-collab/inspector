/**
 * 분석 화면 패키지 — 화면 추가 규약(CLAUDE.md I절).
 *
 * <p>새 DB 성능분석 화면 = 한 하위 패키지 =
 * [Controller + Service + Mapper(+ 동적이면 JdbcTemplate) + 화면 fragment] 한 세트.
 * 이 구조를 벗어나지 않는다.
 *
 * <ul>
 *   <li>공통 레이아웃(사이드바·탑바·도움말 셸)을 상속한다. 페이지 셸을 새로 만들지 않는다.</li>
 *   <li>UI 는 공통 컴포넌트(테이블 렌더러·차트·인스턴스 필터·배지·카드)를 조합한다.</li>
 *   <li>DB 접근은 공통 추상화 계층을 경유한다. 화면이 커넥션을 직접 열지 않는다.</li>
 *   <li>Oracle/PG 분기는 MyBatis databaseId 공통 메커니즘으로 처리한다.</li>
 *   <li>인증/보안은 Spring Security 가 일괄 적용한다. 화면별 수동 인증 체크 금지.</li>
 * </ul>
 *
 * <p>첫 실증 화면(summary 또는 session)은 공통 인프라 단계 이후 추가한다.
 */
package com.exem.inspector.screen;
