# PROGRESS — MaxGauge Inspector Labs (Java 재구현)

## 현재 작업
기존 코드베이스 분석 완료 → Java 재구현 범위/방침 확정 단계

## 마지막 완료
- 서버 git 작업트리 확보: `release/inspector` (clone, public repo), git config
- 작업 브랜치 `setup/foundation`
- CLAUDE.md (Karpathy 헌법 + 스택/SSOT/금지) + PROGRESS push (commit 950999f)
- 환경 확인: JDK 8(1.8.0_422) / 외부망 / Gradle wrapper
- **기존 python-utils 전수 분석 완료** → `.planning/codebase/` 5개 문서 작성
  - 총 ~21.5K 라인, 순수 http.server(README의 FastAPI 표기 오류), Oracle/PG 이원화
  - 재구현 권장 순서: 공통인프라(디자인시스템+DB추상화+인증) → summary → overview → 수집점검 → 스케줄러 → 조회API → 부가/파티션
  - 핵심: JPA 부적합(MyBatis+JdbcTemplate), HikariCP, 인증 BCrypt 개선여지, PL/SQL 프로시저 유지, PG 일별 파티션 수동생성, 비동기는 @Async

## 다음 액션
- 미결정 ADR 작성: 프론트(Thymeleaf SSR 유력) / gateway(nginx 유지?) / 빌드(Gradle vs Maven) / 빌드도구·DB접근(MyBatis 확정?)
- `java/` Spring Boot 2.7 스켈레톤 생성 (Gradle wrapper)
- 공통 인프라부터 착수: 디자인시스템(html_helpers→Thymeleaf 레이아웃/fragment/CSS토큰) + DB 추상화 계층
- 후속 분석: INSP_* 테이블 DDL, summary SQL 본문, MXG_* DB함수 (재구현 직전 필요시)

## 미해결 결정
- 프론트엔드 방식 (Thymeleaf SSR 후보 — 기존이 서버사이드 HTML이므로 자연스러움)
- nginx gateway 유지 여부 (현재 auth_request 연동)
- 빌드 도구 Gradle vs Maven (현재 Gradle wrapper 가정)
- DB 접근: MyBatis(진단SQL) + JdbcTemplate(동적DDL) 조합 확정 여부
- char_setting 라우팅 미연결 처리

## 차단 요인
- 없음
