# CLAUDE.md — MaxGauge Inspector Labs (Java 재구현)

> 이 파일은 에이전트의 헌법이다. 모든 작업 시작 시 먼저 읽는다.
> 행동 원칙 출처: Andrej Karpathy LLM 코딩 가이드라인 (multica-ai/andrej-karpathy-skills)

## 0. 한눈에

- 프로젝트: 기존 MaxGauge Inspector Labs를 Java로 재구현(rewrite)
- **핵심 목표: 다양한 DB 성능분석 화면을 통일된 UI·화면구조·백엔드로 계속 추가할 수 있는 확장 플랫폼을 만든다.** 단순 1:1 포팅이 아니다. (규약은 I절)
- 부차 목적: 보안 취약점 개선 + 기존 MaxGauge 제품과 개발언어(Java) 통일
- 기존 Python/HTTP/HTML 코드(`Labs/`)는 "참조 명세"이며 수정 대상이 아니다 (순수 `http.server` 기반 — README의 "FastAPI" 표기는 부정확)
- 신규 Java 코드만 작성·수정한다
- 개발은 반드시 이 서버에서 수행한다 (MaxGauge 연동 필수)

## A. 행동 원칙 (Karpathy 4원칙)

### 1. 코딩 전 사고
가정하지 말 것. 혼란을 숨기지 말 것. 트레이드오프를 표면화할 것.
- 가정은 명시한다. 불확실하면 질문한다.
- 해석이 여럿이면 임의로 고르지 말고 제시한다.
- 더 단순한 방법이 있으면 말한다. 정당하면 반박한다.
- 불명확하면 멈추고, 무엇이 혼란스러운지 짚고, 질문한다.

### 2. 단순성 우선
문제를 푸는 최소 코드. 투기적인 것 금지.
- 요청 범위 밖 기능 금지.
- 단일 사용처에 추상화 금지.
- 요청하지 않은 유연성/설정 금지.
- 일어나지 않을 시나리오의 예외처리 금지.
- 200줄이 50줄로 될 수 있으면 다시 쓴다.
- 기준: "시니어 엔지니어가 과하다고 할까?" 그렇다면 단순화한다.

### 3. 수술적 변경
필요한 곳만 건드린다. 내가 만든 것만 치운다.
- 인접 코드/주석/포맷을 "개선"하지 않는다.
- 안 망가진 것을 리팩토링하지 않는다.
- 기존 스타일을 따른다 (내 취향과 달라도).
- 무관한 dead code는 삭제하지 말고 보고한다.
- 내 변경이 만든 미사용 import/변수/함수만 제거한다.
- 기준: 모든 변경 라인은 사용자 요청으로 직접 추적 가능해야 한다.

### 4. 목표 기반 실행
성공 기준을 정의하고 검증될 때까지 loop.
- "검증 추가" → "잘못된 입력 테스트 작성 후 통과"
- "버그 수정" → "재현 테스트 작성 후 통과"
- "X 리팩토링" → "전후 테스트 통과 보장"
- 다단계 작업은 각 단계에 verify 체크를 단 계획을 먼저 제시한다.

> 트레이드오프: 위 원칙은 속도보다 신중함에 치우친다. 사소한 작업엔 판단껏 적용한다.

## B. 프로젝트 컨텍스트

- 원본(참조 명세): `Labs/` (Python 3.11 / FastAPI / nginx / 순수 HTML)
  - Inspector: `Labs/Inspector/python-utils/` (FastAPI 백엔드 + `pages/` 라우터), `Labs/Inspector/gateway/` (nginx)
  - MaxSpace: `Labs/MaxSpace/` (Tablespace 대시보드)
  - 신규 기능 명세는 이 코드에서 도출한다. 단 `Labs/`는 읽기 전용 참조이며 수정하지 않는다.
- 신규 구현: `java/` (아래 스택)

## C. 스택 (확정/잠정)

- 언어/런타임: Java, JDK 8 (`/home/inspector/jdk8u422-b05`) [확정]
- 프레임워크: Spring Boot 2.7.x (JDK 8 호환 최종 라인) [확정]
- 빌드: Maven wrapper (`./mvnw`) — 서버에 maven 미설치, wrapper 자동 다운로드 [잠정, 변경 부담 적음]
- DB 접근: MyBatis(진단 SQL, databaseId로 Oracle/PG 분기) + JdbcTemplate(동적 DDL/파티션) + HikariCP 풀. **JPA 미사용** [잠정확정 — 프론트 무관]
- DB: Oracle / PostgreSQL (기존 `db_utils.py` 동작을 사양으로)
- 프론트: **MaxGauge 본체와 통일 — 정보 수신 대기 중** (SSR/SPA 결정 보류). 표현 계층이므로 백엔드 코어와 분리 설계
- 게이트웨이: 기존 nginx 유지 (auth_request 연동) [확정]

## D. 환경

- 개발 위치(정본): `/home/inspector/release/inspector` (git 작업트리)
- 빌드/패키징 작업본: `/home/inspector/release/github` (git 아님 — 건드리지 말 것)
- 원격: `github.com/verykind1004-collab/inspector` (public)
- 연동 대상: 동일 서버의 MaxGauge (`/home/maxgauge*`)
- JDK 설정 예:
  ```
  export JAVA_HOME=/home/inspector/jdk8u422-b05
  export PATH=$JAVA_HOME/bin:$PATH
  ```

## E. 단일 정본(SSOT) 규칙

- 목표/범위 → `PROJECT.md` (없으면 본 파일 0절)
- 진행 상황 → `PROGRESS.md` (전역 요약)
- 스택/실행법/금지 → 본 파일
- 결정 기록 → `docs/decisions/` (1결정 1파일, ADR)
- 동일 정보를 두 곳에 두지 않는다. 충돌 시 즉시 통일한다.

## F. 진행 관리 규칙 (PROGRESS.md)

- 갱신 트리거: 작업 단위 완료 / 세션 종료 / 중요 결정 (커밋과 묶는다)
- 담는 것: 현재 작업 / 마지막 완료 / 다음 액션 / 미해결 결정 / 차단요인
- 담지 않는 것: 코드 구조·git 이력이 이미 기록하는 것 (중복 금지)
- 코드 변경 시 관련 문서를 동시에 갱신한다.

## G. 실행 / 검증

- 빌드: `java/` 에서 `./gradlew build`
- 테스트: `./gradlew test`
- 게이트: 컴파일 + 테스트 통과를 "변경 완료"의 기준으로 한다.

## H. 금지 사항

- `Labs/` (참조 명세) 수정 금지 — 읽기 전용.
- 빌드 작업본 `release/github` 수정 금지.
- 시크릿/인증서/실 운영값 커밋 금지 (`.gitignore` 준수, 템플릿은 빈 값 유지).
- 요청 범위 밖 자율 확장 금지 (원칙 2).
- 임의 임계값/하드코딩 회피책 금지 — 근본 해결 우선.
- 삭제 작업은 사용자 확인 필수.
- `main` 직접 작업 금지 — 작업 브랜치에서 진행한다.

## I. 분석화면 추가 규약 (확장 플랫폼의 핵심)

새 DB 성능분석 화면을 추가할 때 아래를 반드시 따른다. 일관성은 권장이 아니라 규약이다.

- 모든 화면은 **공통 레이아웃**(사이드바·탑바·도움말 셸)을 상속한다. 페이지 셸을 새로 만들지 않는다.
- 한 화면 = `[Controller + Service + Mapper(+동적이면 JdbcTemplate) + 화면 fragment]` 한 세트. 이 구조를 벗어나지 않는다.
- UI는 **공통 컴포넌트**(테이블 렌더러·차트·인스턴스 필터·배지·카드)를 조합한다. HTML/CSS를 화면마다 직접 조립하지 않는다 (기존 Python의 실패 지점 — html_helpers가 강제되지 않아 화면마다 제각각).
- DB 접근은 **공통 추상화 계층**을 경유한다. 화면이 커넥션을 직접 열지 않는다.
- 인증/보안은 Spring Security가 일괄 적용한다. 화면별 수동 인증 체크를 넣지 않는다.
- Oracle/PG 분기는 공통 메커니즘(MyBatis databaseId 등)으로 처리한다. 화면 코드에 분기를 흩뿌리지 않는다.
- 단순 SQL 점검 화면은 가능하면 메타데이터(SQL+컬럼정의) 기반 공통 템플릿으로 생성한다 (기존 `_db_page` 패턴 일반화).
