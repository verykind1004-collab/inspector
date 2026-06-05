# CLAUDE.md — MaxGauge Inspector Labs (Java 재구현)

> 이 파일은 에이전트의 헌법이다. 모든 작업 시작 시 먼저 읽는다.
> 행동 원칙 출처: Andrej Karpathy LLM 코딩 가이드라인 (multica-ai/andrej-karpathy-skills)

## 0. 한눈에

- 프로젝트: 기존 MaxGauge Inspector Labs를 재구현(rewrite). **풀스택 — 백엔드(Java) + 프론트(React SPA)를 모두 우리가 구축한다.**
- **핵심 목표: 기존 Inspector 의 모든 기능을 1:1 동등하게 재구현한다.** 변경 가능한 것 = **개발 스택·언어·디자인·보안요소** 뿐. 기능·화면 구성·SQL·설정 파일·동작은 원본과 동일. **원본에 없는 새 화면/기능 추가 금지.** (포팅 규약은 I절)
- **지원 버전: MaxGauge 2407 ~ 2604 및 이후**. 2311 은 지원 대상 아님(EOL). 2407 = 2506 = 2604 SQL 동일이라 **단일 SQL 셋으로 2407+ 전 버전 커버**. 미래 버전이 SQL 분기를 요구하면 그 시점에 신규 분기 도입(현 시점 미도입).
- **포팅 베이스(SSOT, 정식 2604 라인)**:
  - Oracle: `/home/inspector/ORACLE/2604/Inspector/python-utils/sql_library.py` 등(2407/2506/2604 동일)
  - PG    : `/home/inspector/PG/2604/Labs/Inspector/python-utils/sql_library.py`
  - 기타 모듈(`db_utils.py`, `system_utils.py`, `auth.py`, `pages/*.py`): 동일 정식 트리(2604) 기준
  - `release/inspector/Labs/` 의 변형 트리는 **삭제 완료(2026-06-05)**. SSOT 는 `/home/inspector/PG/2604/Labs/`. 정식 2604 사본을 git 트리에 두는 방안은 별도 ADR 검토.
- 부차 목적: 보안 취약점 개선(SHA256 → 강한 알고리즘 등) + 기존 MaxGauge 제품과 스택 통일(백엔드 Java, 프론트는 MaxGauge VI 표준)
- 신규 코드: 백엔드 `java/`(Spring Boot REST API) + 프론트(React SPA, 별도 레포). 정식 2604 트리는 참조만.
- 백엔드 개발은 반드시 이 서버에서 수행한다 (MaxGauge 연동 필수). 프론트는 API 모킹(MSW)으로 분리 개발 가능.

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
- 빌드: Maven wrapper (`./mvnw`) — 서버에 maven 미설치, wrapper 자동 다운로드(only-script) [확정]
- DB 접근: MyBatis(진단 SQL, databaseId로 Oracle/PG 분기) + JdbcTemplate(동적 DDL/파티션) + HikariCP 풀. **JPA 미사용** [잠정확정]
- DB: Oracle / PostgreSQL (기존 `db_utils.py` 동작을 사양으로)
- 프론트: **React SPA [확정]** (MaxGauge VI 표준과 통일). 별도 레포(폴리레포). 표현 계층이므로 백엔드(REST API)와 분리.
  - 스택: Vite · TypeScript · TanStack Router/Query · Zustand · Tailwind CSS · Radix UI(헤드리스) · **FSD 아키텍처** · Storybook · Vitest/Playwright · MSW · pnpm
  - 디자인시스템: **EXEM UI Design System**(`@exem-fe/*` npm — stylesheet/design-token/react/icon/tailwindcss-plugin) 소비. 토큰 SSOT = `global.css`
- 백엔드 ↔ 프론트 접점: REST API(표준 JSON 응답 스키마) · 쿠키 세션 인증 · CORS · 정적 산출물 nginx 서빙
- 게이트웨이: 기존 nginx 유지 (auth_request 연동) [확정]

## D. 환경

- 개발 위치(정본): `/home/inspector/release/inspector` (git 작업트리)
- 빌드/패키징 작업본: `/home/inspector/release/github` (git 아님 — 건드리지 말 것)
- 원격: `github.com/verykind1004-collab/inspector` (public) — 백엔드
- 프론트 레포: 별도(폴리레포). 위치/원격 **미정(TBD)**. EXEM UI Design System은 프론트팀이 운영하는 별도 GitLab 모노레포에서 npm으로 소비
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

- 빌드: `java/` 에서 `./mvnw -B -ntp package`
- 테스트: `java/` 에서 `./mvnw -B -ntp test`
- 게이트: 컴파일 + 테스트 통과를 "변경 완료"의 기준으로 한다.
- 빌드 환경: `JAVA_HOME=/home/inspector/jdk8u422-b05`. 서버에 maven 미설치 — wrapper(`./mvnw`)가 자동 다운로드(only-script). 최초 부트스트랩에 `/tmp/apache-maven-3.9.9` 사용.
- 프론트(별도 레포): `pnpm install` → `pnpm dev`(Vite) / `pnpm build` / `pnpm test`(Vitest) / `pnpm storybook`. 게이트 = lint+typecheck+test 통과.

## H. 금지 사항

- `Labs/` (참조 명세) 수정 금지 — 읽기 전용.
- 빌드 작업본 `release/github` 수정 금지.
- 시크릿/인증서/실 운영값 커밋 금지 (`.gitignore` 준수, 템플릿은 빈 값 유지).
- 요청 범위 밖 자율 확장 금지 (원칙 2).
- 임의 임계값/하드코딩 회피책 금지 — 근본 해결 우선.
- 삭제 작업은 사용자 확인 필수.
- `main` 직접 작업 금지 — 작업 브랜치에서 진행한다.
- **원본(Labs/pages/, sql_library.py 등)에 없는 새 화면·새 기능 추가 금지**(0절 핵심 목표).
- **SQL 본문 임의 변경 금지** — JDBC 무관 부분(SQL*Plus `SET/COLUMN`, psql `\` 메타) 외에는 원본 그대로(컬럼 alias·공백·세미콜론 제외 토큰 보존). 결과 매핑은 MyBatis `resultMap` 으로.
- **설정 파일 스키마 임의 변경 금지** — `service_config.json`, `insp_config.json`, nginx conf 등 키 셋·의미를 원본과 동일하게 유지(보안값/포맷 강화는 허용).
- **인증/세션/OS 수집/파티션 정책 등 동작 임의 변경 금지** — 단 보안 요소(SHA256→BCrypt 등)는 허용.

## I. 화면 포팅 규약 (1:1 동등 + 공통화 강제)

원본 화면(`Labs/Inspector/python-utils/pages/`)을 Java(백엔드) + React(프론트)로 옮길 때 따른다. **신규 화면 추가가 아니라 기존 화면의 충실 이식**임을 명심한다.

기존 Python의 약점 = 공통화 미강제(`html_helpers`를 안 거쳐 화면마다 제각각). 재구현에선 이를 **구조로 강제**해 동일 기능을 더 일관되게 제공한다. 공통화는 **품질 원칙**이며 **새 화면 추가의 정당화로 쓰지 않는다**.

**한 원본 화면 = 백엔드 1세트 + 프론트 1세트**
- 백엔드: `[Controller + Service + Mapper(+동적이면 JdbcTemplate)] → 표준 JSON 응답`. 화면이 SQL/커넥션을 직접 다루지 않는다.
- 프론트: `feature`(FSD) 하나가 **공통 컴포넌트를 조합**한다. 화면이 UI를 직접 조립하지 않는다.

**SQL 충실 이식 (백엔드)**
- 베이스 = 정식 2604 라인 sql_library.py (0절 SSOT). 2407 = 2506 = 2604 동일이라 단일 셋으로 2407+ 커버.
- 원본 `_SQL_*` 상수 본문을 **문자 그대로** mapper XML 에 옮긴다. 컬럼 alias("DB ID", INSTANCE_NAME, …) 보존.
- 허용 변경: SQL*Plus 지시어 제거(`SET LINESIZE`, `COLUMN ... FORMAT`), psql `\` 메타 제거, 다중문 `$$ LANGUAGE plpgsql;` 분리(JDBC 단일문). 그 외 토큰 변경 금지.
- 결과 매핑: 원본 alias → Java 필드는 `resultMap` 명시. `map-underscore-to-camel-case` 우회 의존 금지.
- `db_type` 분기(Oracle/PG) → MyBatis `databaseId` 분기. 두 벌 다 유지.
- `db_id` 등 정수 인자: 원본의 문자열 보간 → PreparedStatement 바인딩 + 정수 검증(SQL 인젝션 방어, 보안 요소).

**UI 공통화 2층 (프론트, React SPA)**
- 1층 = **EXEM UI Design System**(`@exem-fe/*`): 토큰·기본 컴포넌트. 범용, 그대로 소비.
- 2층 = **Inspector 전용 공통 컴포넌트** = 프론트 레포 **FSD `shared`/`entities` 레이어**: DB 결과 테이블 렌더러(STATUS 배지·DELAY·정렬), 인스턴스 필터, 사이드바 메뉴(Oracle/PG 조건부), 도움말, FAB 도구바, 영한 제목.
- 화면(feature)은 1·2층을 **조합만** 한다. 새 페이지 셸/디자인 토큰을 화면마다 만들지 않는다.

**백엔드 공통화**
- 응답은 **표준 JSON 스키마**를 따른다(컬럼 메타 + 행 + STATUS/DELAY 등 도메인 필드) → 2층 테이블 렌더러가 일관 소비.
- DB 접근은 공통 추상화 계층(MyBatis databaseId)을 경유. Oracle/PG 분기를 화면 코드에 흩뿌리지 않는다.
- 인증/보안은 Spring Security가 일괄 적용. 화면별 수동 인증 체크 금지.
- 단순 SQL 점검 화면은 메타데이터(SQL+컬럼정의) 기반 공통 처리로 일반화한다 (기존 `_db_page` 패턴 — 원본에 이미 있는 방식).

**원본 화면 인벤토리(목표 = 전부 포팅)**
- `Labs/Inspector/python-utils/pages/` 의 라우터 24개(summary·session·capacity·license·alert·query·top_segment·temp_table·vacuum·age·overview·history·report·alarm_history·alert_svc_config·config_page·config_dump·control_process·script_manager·char_setting 등). 누락 없이 모두.
- 누락·차이 발견 시 `PROGRESS.md` 차단 요인 / 미해결 결정에 기록.
