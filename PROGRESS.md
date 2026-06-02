# PROGRESS — MaxGauge Inspector Labs (Java 재구현)

## 핵심 목표 (2026-06-02 재정의 — 1:1 동등 포팅 + 2407~2604 전 버전 지원)
**기존 Inspector 의 모든 기능을 1:1 동등하게 재구현한다.** 변경 가능 = **스택·언어·디자인·보안** 만. 기능·화면 구성·SQL 본문·설정 파일 스키마·동작은 원본과 동일. **원본에 없는 새 화면/기능 추가 금지.** 풀스택(백엔드 Java + 프론트 React SPA). 규약 = CLAUDE.md 0/H/I절.

**지원 버전 = MaxGauge 2407 ~ 2604 및 이후** (2311 제외). 2407 = 2506 = 2604 SQL 동일이라 단일 SQL 셋으로 커버.

**포팅 SSOT = 정식 2604 라인**: `/home/inspector/ORACLE/2604/Inspector/python-utils/` + `/home/inspector/PG/2604/Labs/Inspector/python-utils/`. 이전에 베이스로 삼았던 `release/inspector/Labs/` 의 Labs 변형(2311+패치)은 폐기(2026-06-02 정정).

이전 "확장 플랫폼" 도그마는 폐기(2026-06-02). 공통화(표준 JSON·2층 컴포넌트)는 기존 화면을 일관 처리하기 위한 **품질 원칙**이며 신규 화면 정당화 수단이 아니다.

## 현재 작업 (2026-06-02 — 세션 종료 시점 — 다음 세션에서 일괄 재개)

**완료 누계**:
- 화면 포팅: **13 / 24** (overview 5 카드 + 기존 11: Summary 10Min/1Hour, Session, capacity, license, alert, query, top_segment, temp_table, vacuum, age + **script_manager**)
- 디자인시스템: **EXEM Design System Phase 1~4 적용 완료** (`@exem-ui/{core,react,tailwindcss4}` + Pretendard + 12 화면 시각 정렬 — script_manager 도 동일 토큰)
- 검증: BE clean test **70 PASS** / FE test **18 PASS** / build SUCCESS / lint 0 errors

**서버 git 상태 (재개 시 첫 확인)**:
- BE `release/inspector` (origin push 완료까지는 `ca0be54` / **본 세션 신규 HEAD 1 commit 은 origin 미push**, setup/foundation 브랜치 — 정확한 hash 는 재개 시 `git log -3 --oneline` 으로 확인)
- FE `release/inspector-web` (origin 미등록, **local commit 보존**): 최신 `8d6eb02`
  - FE 로컬 커밋 누적 (재시작 후 그대로 보존, 9개):
    ```
    8d6eb02 Script Manager page (FE) — 본 세션 신규
    45c5349 overview Services 카드 (FE)
    4c929b0 overview Disk/Tablespace 카드 (FE)
    0e63b82 디자인시스템 Phase 4 (ScreenTable·filters·page headers)
    08469d5 디자인시스템 Phase 3 (StatusBadge + sidebar)
    071823c 디자인시스템 Phase 2 (overview cards)
    b3ac13f 디자인시스템 Phase 1 (packages + CSS + Pretendard)
    d575972 overview UI System+Vitals (FE)
    ae2d4a1 8 simple-check screens (Phase B 3차 FE)
    ```

**미완 작업 = 12 화면 + 기능보강 + 인프라** (세션 종료 시점에서 다음 세션이 일괄 진행할 항목):

### A. 화면 포팅 (11 화면 — script_manager 완료)
| 우선 | 화면 | 원본 라인 | 복잡도 | 비고 |
|---|---|---:|---|---|
| ~~1~~ | ~~script_manager~~ | ~~115~~ | ~~medium~~ | ~~SELECT-only SQL runner~~ — **완료(Phase B 5차)** |
| 2 | **alert_svc_config** | 373 | medium | SMS/API/Mail 설정 |
| 3 | **license_check** | 407 | medium | 라이선스 + 인스턴스 정보, DGS PORT 동적 컬럼 보강 별도 |
| 4 | **report** | 475 | medium-high | Daily Report 카드(어제 OS/Mem/Disk 평균, INSP_OS_HISTORY 의존) |
| 5 | **alarm_history** | 566 | high | 로그파일 + zip 아카이브 파싱, SMS/API/Mail 송신 이력 |
| 6 | **control_process** | 574 | high | POST 액션(start/stop/restart) + 프로세스 제어 |
| 7 | **config_page** | 800 | very high | 폼 렌더 + 저장 |
| 8 | **config_dump** | 886 | very high | 전체 설정 덤프 |
| 9 | **history** | 1294 | very high | INSP_*_HISTORY 테이블 + 다중 view + 차트 |
| 10 | char_setting | (없음) | — | 원본 미존재 — 스킵 또는 정의 확정 후 |
| 11 | disk(vacuum_log) | unknown | medium~high | 정확한 원본 파일 확인 필요 |
| 12 | partition 관리 | unknown | medium~high | 정확한 원본 파일 확인 필요 |

### B. 기능 보강 (4)
- **license DGS PORT 동적 컬럼** — 원본 `_get_dgs_port_map` (DGServer.xml + log grep) Java 이식, 기존 license 화면 강화
- **alert 시계열 차트** — `api_alert_times` (인스턴스/알람별 30일 일별 카운트), echarts 도입
- **PG 전용 사이드바 조건부 표시** — 현 dbType 감지해서 vacuum/age 메뉴 토글
- **auth.py 경로B** — DB 사용자 인증(apm_user_list + DGServer.jar 복호화). **jar 분석 선행 필요**(이식 난도 높음, 보안개선 후보로 BCrypt 등 별도 트랙 검토 가치)

### C. 인프라
- **FE Storybook + Playwright** — Summary 1 시나리오 시드. 디자인시스템 컴포넌트 스토리북 추가.
- **FE remote 레포 생성** — 현 폴리레포 로컬 보존 8 commit. GitLab 또는 GitHub 레포 생성 후 origin 등록 + push.
- **번들 split** — 현 JS 573KB (>500KB 경고). `manualChunks` 로 EXEM/Tanstack/React vendor 분리.

### D. 미해결 결정
- 표준 JSON 스키마 확장 — 정렬/페이징/필터 서버위임 (대용량 화면 query/history 등 포팅 시 도입)
- INSP_* 테이블 DDL · MXG_* DB 함수 — 화면 포팅 시점 케이스별 확보
- 오픈소스/라이선스 검증 기준 — 백엔드 개발팀 확인 필요(고객사 외부 인터넷 차단)

## 세션 종료 시점 가동 상태 (2026-06-02 19:10~ 재기동)
- BE Spring Boot 2.7.18 / JDK 8 — `:8083` 가동 중 (`/tmp/inspector-be.log`, PID 11498)
- FE Vite dev — `:5173` 가동 중 (`/tmp/inspector-fe.log`, PID 6150)
- 접속: SSH 터널 `ssh -L 15173:localhost:5173 -p 22022 inspector@10.10.45.136` → `http://localhost:15173/`
- 정지: `pkill -9 -f InspectorApplication; pkill -9 -f vite`

## 재개 후 첫 액션 (다음 세션이 자율 진행)

```
세션 시작 → PROGRESS.md (정본 ca0be54) Read → A 표 우선순위 1번부터 순차
  1. script_manager (가장 작음, BE+FE 풀스택, 보안 검증 패턴 확립)
  2. alert_svc_config
  3. license_check + 기능 B-1(DGS PORT 동적 컬럼)
  4. report  
  5. alarm_history (로그+zip 파싱)
  6. control_process (POST 액션 패턴 확립)
  7. config_page / config_dump (대규모 폼)
  8. history (대규모 view + 차트)
  9. C 인프라 (Storybook + FE remote + 번들 split)
  10. D 미해결 결정 사용자 확인
```

각 화면 1:1 동등 포팅, 디자인시스템(@exem-ui) 컴포넌트 우선, 검증 = clean test + build + lint.

## 마지막 완료
- 서버 git 작업트리 `release/inspector` (clone, public), git config, 브랜치 `setup/foundation`
- CLAUDE.md (Karpathy 헌법 + 스택 + SSOT + 금지 + **I절 분석화면 추가 규약**) / PROGRESS push
- 기존 python-utils 전수 분석 → `.planning/codebase/` 5문서 (commit d62d07b)
- ADR 방향 확정:
  - DB 접근: **MyBatis(databaseId 분기) + JdbcTemplate(동적 DDL) + HikariCP**, JPA 미사용 [잠정확정]
  - 빌드: **Maven wrapper [확정]** — SB 2.7.18 / JDK8, only-script wrapper(자동 다운로드)
  - gateway: nginx 유지 [확정]
  - 프론트: **React SPA [확정]** (MaxGauge VI 표준) — Vite·TS·TanStack Router/Query·Zustand·Tailwind·Radix·FSD·Storybook·Vitest/Playwright·MSW·pnpm. EXEM UI Design System(`@exem-fe/*`) 소비. 별도 레포(폴리레포)
- **java/ 스켈레톤 생성 (1단계 완료)**:
  - Maven 프로젝트(`pom.xml`, `groupId=com.exem`/`artifactId=inspector`), SB 2.7.18, JDK8, `mvnw` wrapper
  - 패키지 골격(I절 인코딩): `config/`(DatabaseConfig — MyBatis databaseId Oracle/PG 분기), `common/db/`(DbType enum), `common/web/`(PingController `/api/ping`), `screen/`(package-info 화면추가 규약)
  - DB 추상화 골격: 접속정보는 service_config.json 런타임 로딩 → `DataSourceAutoConfiguration` 제외(DB 미연결 부팅 허용), MyBatis는 datasource 부재 시 backoff
  - **검증: `./mvnw -B -ntp clean test` BUILD SUCCESS, contextLoads PASS, JDK 1.8.0_422 부팅 확인**
- **공통 인프라 골격 (2단계 완료)**:
  - 2-A 동적 DataSource: `ServiceConfig` + `RepositoryConfig` + `DbType` + `DataSourceConfig`(HikariCP, `@Conditional(RepositoryConfiguredCondition)` — 미설정 시 빈 미등록·부팅 유지, `initializationFailTimeout=-1`)
  - 2-B Spring Security: `SecurityConfig`(공개경로 화이트리스트 + anyRequest authenticated + 401 entryPoint + 세션 IF_REQUIRED) + `AdminAuthenticationProvider`(경로A SHA256→ROLE_ENGINEER) + `AuthProperties` + `AuthController`(login/logout/check-auth/whoami)
  - **검증: `clean test` BUILD SUCCESS, 13 tests PASS**
  - 미구현/TODO: ①auth.py 경로B(DB 사용자=apm_user_list+DGServer.jar 복호화) ②세션 절대만료 ③CSRF·쿠키Secure·BCrypt 보안개선
- **1·2단계 커밋(c938e7d) + ADR 0001(프론트 SPA·풀스택·UI 공통화 2층) 커밋(1f154a7)** — `setup/foundation`. `docs/decisions/0001-frontend-spa-and-fullstack-scope.md` 추가, 헌법 0·C·D·G·I절 갱신(I절=SPA 2층 규약 재작성). `templates/` 제거 완료(SPA 확정). **두 커밋 모두 origin 미push 상태.**

- **표준 JSON 응답 스키마 + 첫 화면(Summary Check) 백엔드 + push (3단계, 2026-05-22, b20a41f)**:
  - **표준 표 응답 계약**(`common/web/screen/`): `ScreenResponse`(meta+columns+rows) + `ColumnDef`(key/label/type/role/hidden) + `ColumnType` + `ColumnRole`(PLAIN/ID/INSTANCE/GROUP/STATUS/DELAY) + `ScreenMeta`. 표준 봉투 `common/web/ApiResponse`(ok/error/data)
  - **Summary Check 화면**(`screen/summary/`): Controller(`/labs/api/summary/10min`·`/1hour`) → Service(매퍼행→표준응답, ObjectProvider 선택주입) → `@Mapper` + XML(databaseId Oracle/PG 두 벌)
  - 컬럼 계약: DB ID(ID) / Instance Name(INSTANCE·필터) / Summary Type(GROUP·칩) / Last Summary(DATETIME) / Status(STATUS·배지 OK/CHECK/WAITING/ERROR) / Delay(DELAY·hidden·툴팁)
  - **검증: clean test BUILD SUCCESS, 19 tests PASS**
  - 라이브 저장소 런타임 검증은 당시 보류로 보고했으나 **사실 환경에 접속정보 충분**(3.5 단계에서 정정)

- **버전 분기 검토 + 1:1 동등 원칙 재정렬 + SQL alias 정정 (3.5 단계, 2026-06-02, fcef342 push)**:
  - 검토 결과: 명시적 if-else 버전 분기 없음. 빌드별 sql_library.py 분리 방식. **2311 vs 2407+ 두 라인**(2407=2506=2604 동일), 주로 PG 파티션 SQL 차이.
  - **헌법 재정리**: CLAUDE.md 0절 "확장 플랫폼" 도그마 폐기 → "1:1 동등 포팅" 명문화. I절 재작성. H절에 금지 항목 추가. SummaryMapper.xml alias 원복(`"DB ID"`/INSTANCE_NAME 등)+resultMap.
  - **환경 인지 정정**: 라이브 저장소 접속정보 보유 확인(`/home/inspector/ORACLE/*/Inspector/python-utils/service_config.json`, mxg2604@10.10.45.136:1521/ORACLE19 등). TCP_OK. **실 저장소 런타임 검증 즉시 가능**.

- **베이스 정식 2604 라인 전환 + Summary SQL 재정정 (3.6 단계, 2026-06-02, edff242 push)**:
  - **사용자 결정 재정정(2026-06-02)**: "버전은 2407~2604 등등 모든 버전을 만족해야 함" → 베이스 = Labs 변형(2311+패치) → **정식 2604 라인으로 변경**. 2407=2506=2604 SQL 동일이라 단일 셋으로 2407+ 전 버전 커버.
  - **SSOT 갱신**: Oracle `/home/inspector/ORACLE/2604/Inspector/python-utils/sql_library.py` / PG `/home/inspector/PG/2604/Labs/Inspector/python-utils/sql_library.py`. CLAUDE.md 0절·I절 SSOT 표기 갱신.
  - **SummaryMapper.xml 재정정**: 정식 2604 라인 본문(md5 `b9c31c07`·`74757197`·`1baa19c1`·`cc8b50a7`)으로 4개 select 재포팅. **핵심 차이 = ORDER BY**(정식은 상태 우선순위 CHECK→WAITING→OK + 보조키, Labs 변형은 summary_time NULLS FIRST + db_id). 운영상 정식이 더 합리적. resultMap 그대로.
  - 컬럼 alias·CASE 본문 등 나머지는 동일.

- **Phase B 1차 + 실 저장소 라이브 검증 + Session 화면 포팅 (2026-06-02, ba7dc5d push)**:
  - **실 저장소 라이브 검증 완료 (mxg2604@10.10.45.136:1521/ORACLE19)**:
    - `java/config/service_config.json` 작성(ORACLE/2604 의 repository 블록 복사, .gitignore 처리)
    - `spring-boot:run` 기동 OK. DataSource 구성 로그 확인 — `리포지토리 DataSource 구성: ORACLE jdbc:oracle:thin:@//10.10.45.136:1521/ORACLE19`
    - 로그인: POST `/labs/api/login` `{"id":"maxgauge","password":"..."}` → 200 `{"role":"engineer","id":"maxgauge","ok":true}`
    - `/labs/api/summary/10min` 200 실 응답 3행(ORACLE19 OS Stat/DB Stat/DB Wait 10Min, 모두 CHECK +41d 마지막 2026-04-22)
    - `/labs/api/summary/1hour` 200 실 응답 7행(Daily 카테고리 7개, 모두 CHECK +42d)
    - 표준 봉투(ApiResponse)+표준 표(ScreenResponse, columns 6/3개+rows+meta) 구조 정확. ORDER BY CHECK→WAITING→OK 적용 확인
    - **주의/배운 점**: `-Dspring-boot.run.arguments` 와 환경변수(`SPRING_APPLICATION_JSON`/`INSPECTOR_AUTH_ADMIN_HASH`)는 spring-boot-maven-plugin 2.7 에서 forked JVM 으로 잘 전파되지 않음. 검증 시 application.yml 임시 변경 → 검증 → 원복 패턴 사용. LoginRequest 필드명은 `id`(원본 auth.py 보존, 프론트 호출 시 동일)
  - **Session Check 화면(2번째 화면) 포팅**: `screen/session/`
    - SQL 원본 = 정식 2604 _SQL_SESSION (Oracle) / _SQL_PG_SESSION (PG: `SELECT * FROM insp_session_check() ORDER BY last_time ASC`)
    - 컬럼 = DB ID(ID) / INSTANCE_NAME(INSTANCE 필터) / LAST_TIME(DATETIME). STATUS/DELAY 없음 — 2층 ScreenTable 이 자동 대응(STATUS 컬럼 부재 시 일반 td 렌더)
    - 구성: SessionMapper(@Mapper databaseId Oracle/PG) + XML + resultMap + SessionRow + SessionService(ObjectProvider 선택주입) + SessionController(GET `/labs/api/session`) + SessionServiceTest(3 tests)
  - **검증: clean test 22 PASS** (기존 19 + Session 3)

- **Phase B 3차 — 단순 점검 8 화면 일괄 포팅 (2026-06-02, 미커밋)**:
  - 대상: **capacity / license / alert / query / top_segment / temp_table / vacuum(PG) / age(PG)**. 원본 `_db_page` 패턴(SQL 한 개 → 표 렌더링).
  - **백엔드 일반화**: `SimpleScreenMapper`(8 메소드, `LinkedHashMap<String,Object>` 반환 — 원본 `_parse_db_table` 헤더-값 매핑과 동등) + XML(8 select × Oracle/PG databaseId, 단 vacuum/age 는 PG 전용). `SimpleScreenService` 가 화면 spec(컬럼 메타 + dbType 분기 + 매퍼 호출) 보유. `SimpleScreenController` 단일 — `GET /labs/api/{key:capacity|license|alert|query|top_segment|temp_table|vacuum|age}` 화이트리스트. 미지원 키 404, 미지원 dbType 은 error 봉투.
  - `ScreenResponse.Builder.rowFromMap()` 추가 — 컬럼 메타 키 순서대로 LinkedHashMap 행 매핑.
  - 컬럼 메타 화면 고정. PG 함수 호출(insp_alarm_history_check / insp_query_check) 결과 컬럼은 Oracle 메타와 동일 가정(원본 함수 정의가 그렇게 작성됨).
  - **프론트 일반화**: `features/screen/`(useScreen hook + ScreenView) + `pages/screen/SimpleScreenPage`(props: screenKey/title/sub) + 라우트 8개(`/capacity`, `/license`, `/alert`, `/query`, `/top_segment`, `/temp_table`, `/vacuum`, `/age`) + `__root.tsx` 사이드바 그룹 4개(Inventory/Health/PostgreSQL) 추가. MSW fixtures 8개(simple.ts 일괄), handlers 자동 등록.
  - SQL 본문은 정식 2604 그대로(SQL*Plus `SET/COLUMN`, psql `\pset` 만 제거). 컬럼 alias 보존(`"DB ID"`, `"INSTANCE NAME"`, `"ALARM NAME"`, `"COUNT"`, `"RTS PORT"`, `"SCHEMA"`, `"TEMP TABLE"` 등).
  - **검증: mvnw test 29 PASS** (22 + SimpleScreen 7), 프론트 build 461 modules 370KB/118KBgz · test 12 PASS · lint 0 errors.

- **Phase B 4차 1단계 — overview System + Vitals 카드 (2026-06-02, BE de5a419 push / FE 미push)**:
  - 원본 `pages/overview.py` 의 카드형 대시보드 중 System / CPU / Memory 부분을 1:1 동등 포팅 (Disk/Tablespace · Services 카드는 후속 커밋 분리).
  - **백엔드**(`screen/overview/`): ProcReader(/proc/stat·meminfo·uptime·cpuinfo 파서, CpuStat/MemoryStat 값 객체) + HostInfo(host/os) + OverviewService(_pct_status 임계 60/80, 80/90 보존) + OverviewController(GET `/labs/api/overview/system` static + `/vitals` 폴링 대상).
  - **프런트**(`features/overview/`): useOverviewSystem(60s cache) + useOverviewVitals(3s 폴링, 원본 _fetchVitals setInterval 등가) + SystemCard + VitalsCards(CPU+Mem) + VitalBadge(ok/warning/critical 톤 emerald/amber/rose) + VitalBar(_bar_dyn 등가). `routes/index.tsx` 가 placeholder → OverviewView 교체.
  - **MSW 픽스처**: System(inspector-mock host/16 cores) + Vitals(CPU 42% ok, Mem 67% ok) 추가, handlers 등록.
  - **검증: BE clean test 37 PASS** (29 + 신규 8: ProcReaderTest 3 + OverviewServiceTest 5). **FE test 15 PASS** (12 + VitalBadge 3), build 469 modules 374KB/119KBgz, lint 0 errors.

- **EXEM 디자인시스템 풀스택 미러 — Phase 1~3 적용 (2026-06-02, FE local 3 commits, push 없음)**:
  - **출처**: `gitlab.exem.xyz/fe1/design-studio-temp` (PAT 클론) + 서브모듈 `external/maxgauge-vi`(참조 구현) + `external/exem-table`. 메인 패키지 `@exem-ui/{core,react,tailwindcss4}` 는 공개 npmjs.org 에 있음.
  - **Phase 1 — 인프라**: `package.json` 에 `@exem-ui/core@^0.3.3` + `@exem-ui/react@^0.3.4` + `@exem-ui/tailwindcss4@^0.3.2` 추가. Pretendard 4 weight woff2 (`src/assets/font/pretendard/`) 복사 (출처 maxgauge-vi, SIL OFL 1.1). `src/index.css` 디자인시스템 진입 정렬 (`@import @exem-ui/core/css` + `@exem-ui/tailwindcss4` + `@exem-ui/react/styles` + Pretendard `@font-face` × 4 + `font-pretendard` utility + `*` base `@apply`).
  - **Phase 2 — overview 컴포넌트 교체**: `VitalBadge` → `@exem-ui/react` `Tag` (ok=green / warning=amber / critical=red, type=fill). `VitalBar` → `Progress` (size=small, `gaugeClassName=bg-{green/amber/red}-05`). `SystemCard / VitalsCards / OverviewView` 토큰화 (`bg-gray-00 / border-gray-02 / text-gray-{05,06,10} / text-body-{2,3} / rounded-strong / text-header-2`). 테스트 갱신.
  - **Phase 3 — 공통 표면 교체**: `StatusBadge` (기존 11 화면 영향) → `Tag` 위임 (OK→green, CHECK/ERROR→red, WAITING→amber, 그외→mono). 툴팁 내부 토큰화. `__root.tsx` 사이드바 토큰화 (sky-06 active, sky-01 hover, gray-{00..07,10}). `GroupHeading` 분리.
  - **검증 (각 Phase 별)**: pnpm test 15 PASS / pnpm build SUCCESS (CSS 22KB→85KB w/디자인시스템 / JS 374KB→573KB w/@exem-ui/react / Pretendard 4종 3.1MB 자동 번들) / pnpm lint 0 errors.
  - **미반영 / Phase 4+ 후속**: `@exem-fe/react-table` (npm 비공개, 서브모듈+link 필요), `ScreenTable / InstanceFilter / GroupChips` 토큰화, 페이지 헤더 토큰화, Storybook+Playwright.

- **Phase B 4차 2단계 — overview Disk/Tablespace + Services 카드 (2026-06-02, BE f8a7976+6c4c0bd push / FE local 4c929b0+45c5349 미push)**:
  - **Disk/Tablespace** (BE f8a7976): Oracle = `_SQL_ORACLE_TABLESPACE_OVERVIEW` 다중 테이블스페이스 + overall 상태, PG = `pg_data_dir`(미설정 시 "/") `Files.getFileStore` stat. `RepositoryConfig.pgDataDir` 추가. `OverviewDiskMapper` + xml(Oracle/PG databaseId 분기) + `OverviewDiskService` + `TablespaceRow`. 테스트 5건.
  - **Services** (BE 6c4c0bd): DGServer_M/S* + PlatformJS + Client + Repo DB 행 구성. `ServicesBlock`(service_config services 블록), `PortChecker`(TCP listen), `DgServerXmlReader`(정규식 단일 태그), `VersionReader`(home/version 파일). 본 단계는 TCP listen 만(원본 ss/netstat+ps DG_NAME 폴백 미적용). 테스트 5건.
  - **FE**: `useOverviewDisk`(60s cache) + `DiskCard`(Tablespace 다중/PG 단일 분기) + `useOverviewServices`(3초 폴링) + `ServicesCard`(Tag 상태배지 표). MSW 픽스처 + 핸들러 갱신. `OverviewView` 4열 그리드 + Services 카드 col-span-full.
  - **검증**: BE clean test 47 PASS (37→42→47). FE test 15 PASS, build SUCCESS, lint 0 errors.

- **Phase B 4차 3단계 — 디자인시스템 Phase 4 적용 (2026-06-02, FE local 0e63b82 미push)**:
  - `ScreenTable` 토큰화 (bg-gray-{00,01,03} / border-gray-{02,03} / text-gray-{05..10} / text-body-3 + text-caption / hover sky-{01,07} / rounded-strong)
  - `InstanceFilter` 토큰화 (bg-gray-01 + focus sky-05 / rounded-medium)
  - `GroupChips` 토큰화 (활성 sky-06, 비활성 gray-00+border-gray-02)
  - 페이지 헤더 6개(SimpleScreenPage / Summary{10Min,1Hour} / SessionPage) — `text-header-2` + `text-body-3`
  - 검증: pnpm test 15 PASS / build SUCCESS / lint 0 errors.

- **Phase B 5차 — script_manager 화면 포팅 (2026-06-02, BE 미push / FE 미push)**:
  - 원본 `pages/script_manager.py` (Oracle/PG 동일 115 라인) → SELECT-only SQL runner, 첫 POST 액션 화면 + 첫 동적 컬럼 화면.
  - **백엔드** (`screen/script/` — 8 파일): `ScriptValidator`(주석 strip + ';' 분할 prefix 검사 + schema [A-Za-z0-9_]+ sanitize, 원본 _validate_select_only + _strip_sql_comments 동등) + `ScriptExecutor`(인터페이스 + inner Result/ColumnInfo) + `JdbcScriptExecutor`(Oracle: NLS_DATE_FORMAT → SET TRANSACTION READ ONLY → execute → rollback; PG: SET statement_timeout '30s' → SET search_path → SET TRANSACTION READ ONLY → _split_pg_stmts 분리 → 마지막 ResultSet → rollback; fetchmany(max+1) 동등으로 truncated 판정) + `ScriptService`(검증 → 실행 → 표준 ScreenResponse 조립, ColumnType 매핑 NUMBER/DATETIME/STRING 보강) + `ScriptController`(GET `/labs/api/script/schemas`, POST `/labs/api/script/run`, 검증/실행 오류는 200+ok=false 봉투 — 원본 동등) + `ScriptRunRequest/Result` + `ScriptSchemasResult`.
  - **프런트**(5 파일 추가 / 2 파일 수정): `features/script/api/useScriptRun`(POST mutation) + `useScriptSchemas`(GET 60s cache) + `pages/screen/ScriptManagerPage`(SQL textarea + schema selector(PG 만) + Run 버튼 + truncated 배너 + 결과 ScreenTable, 디자인시스템 토큰 — `rounded-strong`/`bg-gray-00`/`text-body-3`/`font-mono`/`bg-sky-06 hover sky-07`/`border-rose-03 bg-rose-01`/`border-amber-04 bg-amber-01`) + `routes/script_manager.tsx`(파일 라우터 `/script_manager`) + `mocks/fixtures/script.ts`(schemas 빈 + demo NUM/USR + 차단 fixture). `__root.tsx` 사이드바 **Tools** 그룹 + Script Manager 메뉴 추가. `handlers.ts` script POST/GET 등록(차단 prefix 동적 응답).
  - **검증**:
    - BE clean test **70 PASS** (47 + 신규 23: ScriptValidatorTest 13 + ScriptServiceTest 10), build SUCCESS.
    - 라이브 BE 검증: 로그인 OK / **DROP 차단 라이브 PASS**(`"Only SELECT is allowed. Blocked statement starts with: DROP"` 원본 동일 문구) / **/labs/api/script/schemas 라이브 PASS**(ORACLE 환경 빈 리스트). SELECT 실행 라이브는 **Oracle 인스턴스 다운(ORA-01034)** 으로 미검증 — 다른 화면들도 동일 영향, 우리 코드 영향 없음. 환경 복구 시점에 재검증.
    - 임시 hash(test1!) 패턴 사용 후 application.yml 원복 + BE 재기동 완료(test1! 로그인 거부 확인).
    - FE test **18 PASS** (15 + ScriptManagerPage 3: 초기 안내 / SELECT 실행 표 렌더 / 차단 응답 오류 노출), build 1484 modules **582KB**/176KBgz, lint 0 errors.
  - **신규 패턴 확립**: ① POST 액션 화면 골격 + 표준 봉투 일관성 ② 동적 컬럼 화면(ScreenResponse.builder 의 동적 column/row API 활용) ③ READ ONLY 트랜잭션 2중 방어 ④ 오류 200+ok=false 통일.

## 진행 누계
- **포팅 완료 화면: 13 / 24** (overview + Summary 10Min/1Hour + Session + capacity + license + alert + query + top_segment + temp_table + vacuum + age + **script_manager**)
- **남은 화면 (11)**: history · report · alarm_history · alert_svc_config · config_page · config_dump · control_process · char_setting · license_check · disk(vacuum_log) · partition 관리

## 다음 첫 액션
1. **A 표 2번 alert_svc_config(373)** 또는 **3번 license_check(407)** — 폼 + 검증 + 저장 패턴 확립(POST 액션 두 번째 사례)
2. **A 표 4번 report(475)** · **5번 alarm_history(566)** — Daily Report 카드 + 로그/zip 파싱
3. **A 표 6번 control_process(574)** · **7~8번 config_page/dump(800/886)** — POST 액션 본격
4. **A 표 9번 history(1294)** — 대규모 view + 차트
5. **기능 보강** — license DGS PORT 동적 컬럼 / alert 시계열 차트 / PG 사이드바 / auth.py 경로B
6. **FE Storybook + Playwright** — 1 시나리오 시드

## 미해결 결정
- 표준 JSON 스키마 확장 — 정렬/페이징/필터 서버위임은 대용량 화면(query·history 등) 포팅 시 필요 시 도입(현 시점 1:1 원칙상 원본 미지원이면 미도입)
- INSP_* 테이블 DDL, MXG_* DB함수 — 화면 포팅 시점에 케이스별 확보
- **오픈소스/라이선스 검증 기준 — 백엔드 개발팀 확인 필요**: 고객사 외부 인터넷 차단 + 검증 오픈소스만 허용. ①Oracle ojdbc8(OTN) ②Spring Boot 전이의존성 SBOM ③폐쇄망 사내 미러(Nexus)

## 차단 요인
- **(2026-06-02 해소) EXEM UI 디자인시스템 미수령** — `gitlab.exem.xyz/fe1/design-studio-temp` 클론 후 Phase 1~3 적용으로 해소.
- 라이브 저장소 검증은 차단 요인 아님(해소).
- **(2026-06-02 신규) Oracle 인스턴스 다운(ORA-01034)** — mxg2604@10.10.45.136:1521/ORACLE19 listener 다운. script_manager SELECT 실행 라이브 검증 미수행. 다른 화면도 동일 영향. 환경 복구 시 일괄 재검증 필요(BE 코드 영향 없음).
- 잔여: `@exem-fe/react-table` 공개 npm 미공개 — 서브모듈+link 필요(테이블 화면 마이그 시점에 검토).

## 재개 후 첫 액션 체크리스트
1. Oracle 인스턴스 가용성 확인(`TCP localhost:1521`) → 다운 시 DBA 에 startup 요청.
2. A 표 2번 alert_svc_config(373) 또는 3번 license_check(407) 포팅 — 폼 + 검증 + 저장(POST 액션 두 번째 사례).
3. (선택) `@exem-fe/react-table` 서브모듈 + link 도입 검토 — 대용량 화면(history) 가상화 필요 시.
4. history / report / alarm_history 복잡 화면 포팅.
