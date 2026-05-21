# PROGRESS — MaxGauge Inspector Labs (Java 재구현)

## 핵심 목표 (재정의됨)
단순 1:1 포팅이 아니라, **다양한 DB 성능분석 화면을 통일된 UI·화면구조·백엔드로 계속 추가할 수 있는 확장 플랫폼** 구축. 규약은 CLAUDE.md I절.

## 현재 작업
설계 확정 완료 → `java/` 스켈레톤 구현 착수 직전 (분기점)

## 마지막 완료
- 서버 git 작업트리 `release/inspector` (clone, public), git config, 브랜치 `setup/foundation`
- CLAUDE.md (Karpathy 헌법 + 스택 + SSOT + 금지 + **I절 분석화면 추가 규약**) / PROGRESS push
- 기존 python-utils 전수 분석 → `.planning/codebase/` 5문서 (commit d62d07b)
- ADR 방향 확정:
  - DB 접근: **MyBatis(databaseId 분기) + JdbcTemplate(동적 DDL) + HikariCP**, JPA 미사용 [잠정확정]
  - 빌드: Maven wrapper [잠정]
  - gateway: nginx 유지 [확정]
  - 프론트: MaxGauge 본체와 통일 — **정보 수신 대기 중** (SSR/SPA 보류, 표현계층이라 백엔드 코어와 분리)

## 다음 첫 액션 (새 세션에서 이어갈 때 여기부터)
1. `java/` Spring Boot 2.7 스켈레톤 생성 (Maven wrapper, JDK8)
   - 구조: 공통 레이아웃 + 화면추가 규약(Controller-Service-Mapper-fragment) + 공통 컴포넌트 + DB추상화(Oracle/PG)
   - JAVA_HOME=/home/inspector/jdk8u422-b05, 서버 release/inspector/java 에 생성
2. 공통 인프라 골격: DB 추상화 계층 + Spring Security(인증, auth.py 사양) + 공통 레이아웃
3. 실증: 가장 단순한 화면(summary 또는 session) 1개를 규약대로 재구현 → "새 화면 추가가 일관·간단한가" 검증
   - 이 시점에 프론트 SSR/SPA 정보 필요 → 그 전에 수신 권장

## 미해결 결정
- 프론트엔드 SSR vs SPA (MaxGauge 본체 정보 대기)
- char_setting 라우팅 미연결 처리 (재구현 시 반영)
- 후속 분석 필요: INSP_* 테이블 DDL, summary SQL 본문, MXG_* DB함수 (구현 직전)

## 차단 요인
- 프론트 방식은 실증(3단계)에서만 필요 — 그 전까지 차단 아님
