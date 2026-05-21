# PROGRESS — MaxGauge Inspector Labs (Java 재구현)

## 현재 작업
프로젝트 기반(하네스) 셋업

## 마지막 완료
- 서버 git 작업트리 확보: `release/inspector` (clone, public repo)
- git config 설정 (장기협 / kihyeop@ex-em.com)
- 작업 브랜치 `setup/foundation` 생성
- CLAUDE.md (행동 헌법 + 스택 + SSOT/진행/금지 규칙) 작성
- 환경 확인: JDK 8(1.8.0_422) / 외부망 / Gradle wrapper 가능

## 다음 액션
- `java/` Spring Boot 2.7 스켈레톤 생성 (Gradle wrapper)
- 기존 `Labs/Inspector/python-utils` 기능 목록화 → 재구현 우선순위 (GSD map-codebase)
- 미결정 ADR 작성: 프론트(Thymeleaf?) / gateway(nginx 유지?)

## 미해결 결정
- 프론트엔드 방식 (Thymeleaf SSR 후보)
- nginx gateway 유지 여부
- 빌드 도구 Gradle vs Maven (현재 Gradle wrapper 가정)

## 차단 요인
- 없음
