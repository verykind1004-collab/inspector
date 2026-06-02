# PROGRESS — MaxGauge Inspector Labs (Java 재구현)

## 핵심 목표 (2026-06-02 재정의 — 1:1 동등 포팅 + 2407~2604 전 버전 지원)
**기존 Inspector 의 모든 기능을 1:1 동등하게 재구현한다.** 변경 가능 = **스택·언어·디자인·보안** 만. 기능·화면 구성·SQL 본문·설정 파일 스키마·동작은 원본과 동일. **원본에 없는 새 화면/기능 추가 금지.** 풀스택(백엔드 Java + 프론트 React SPA). 규약 = CLAUDE.md 0/H/I절.

**지원 버전 = MaxGauge 2407 ~ 2604 및 이후** (2311 제외). 2407 = 2506 = 2604 SQL 동일이라 단일 SQL 셋으로 커버.

**포팅 SSOT = 정식 2604 라인**: `/home/inspector/ORACLE/2604/Inspector/python-utils/` + `/home/inspector/PG/2604/Labs/Inspector/python-utils/`. 이전에 베이스로 삼았던 `release/inspector/Labs/` 의 Labs 변형(2311+패치)은 폐기(2026-06-02 정정).

이전 "확장 플랫폼" 도그마는 폐기(2026-06-02). 공통화(표준 JSON·2층 컴포넌트)는 기존 화면을 일관 처리하기 위한 **품질 원칙**이며 신규 화면 정당화 수단이 아니다.

## 현재 작업 (일시 정지 — 디자인시스템 대기, 2026-06-02)
Phase B 4차 1단계 — overview 화면 첫 컷(System + CPU + Memory 카드, BE+FE 동시) 완료. 누계 11/24 + overview 부분 포팅.

**재개 조건**: EXEM UI 디자인시스템(`@exem-fe/*`, GitLab 모노레포) 을 사용자가 받아와 프런트 `shared/ui` 어댑터로 1층 교체한 뒤 재개.
- 현 FE 컴포넌트(`VitalBadge / VitalBar / SystemCard / VitalsCards / OverviewView`) 는 임시 Tailwind 직조립 — 디자인시스템 도입 시 시각 디테일 일괄 재정렬 예정(구조는 1:1 보존).
- 디자인시스템 적용 후 다음 = overview Services + Disk/Tablespace 카드 → history / report / alarm_history.

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

## 진행 누계
- 포팅 완료 화면: **11 / 24** (Summary 10Min/1Hour + Session + capacity + license + alert + query + top_segment + temp_table + vacuum + age)
- 부분 포팅 화면: **overview** (System + CPU + Memory 카드 BE+FE 완료, Services·Disk/Tablespace 카드 잔여)
- 남은 화면: overview(잔여 카드) · history · report · alarm_history · alert_svc_config · config_page · config_dump · control_process · script_manager · char_setting · license_check · disk(vacuum_log) · partition 관리

## 다음 첫 액션 (Phase B 4차)
1. **overview 잔여 카드**(우선) = Services(DGServer_M/S, PlatformJS, Client, Repo DB 상태) + Disk/Tablespace(PG 면 OS 디스크, Oracle 이면 Tablespace SQL 카드). `_dg_info / _repodb_info / _tablespace_for_overview` 등 원본 system_utils 포팅.
2. history / report / alarm_history 복잡 화면 포팅
3. 액션 페이지(control_process / script_manager / config_page / config_dump) — POST 액션 포함
4. license 의 DGS PORT 동적 컬럼 추가(원본 _get_dgs_port_map 로직 — DGServer.xml + log grep)
5. alert 의 시계열 차트(api_alert_times — 인스턴스/알람별 30일 일별 카운트)
6. PG 전용 화면 사이드바 조건부 표시(현 dbType 인식)
7. 프론트 Storybook + Playwright(Summary 1 시나리오)
8. 병행: auth.py 경로B(DGServer.jar)

## 미해결 결정
- 표준 JSON 스키마 확장 — 정렬/페이징/필터 서버위임은 대용량 화면(query·history 등) 포팅 시 필요 시 도입(현 시점 1:1 원칙상 원본 미지원이면 미도입)
- INSP_* 테이블 DDL, MXG_* DB함수 — 화면 포팅 시점에 케이스별 확보
- **오픈소스/라이선스 검증 기준 — 백엔드 개발팀 확인 필요**: 고객사 외부 인터넷 차단 + 검증 오픈소스만 허용. ①Oracle ojdbc8(OTN) ②Spring Boot 전이의존성 SBOM ③폐쇄망 사내 미러(Nexus)

## 차단 요인
- **(2026-06-02 활성) EXEM UI 디자인시스템(`@exem-fe/*`) 미수령** — 사용자가 GitLab 모노레포에서 받아와 적용 예정. 적용 전까지 본 Phase 일시 정지.
- 라이브 저장소 검증은 차단 요인 아님(해소됨).
- 임시 FE 컴포넌트(`VitalBadge` 등 Tailwind 직조립)는 디자인시스템 도입 시 어댑터 통한 1층 교체 예정. 구조는 변경 없음.

## 재개 후 첫 액션 체크리스트
1. EXEM 디자인시스템 패키지 `@exem-fe/*` 수령 후 `shared/ui` 에 어댑터 신설 (ADR 0001 §UI 공통화 2층).
2. 본 세션의 임시 컴포넌트(VitalBadge/VitalBar/SystemCard/VitalsCards) 어댑터 경유로 교체 — 외부 인터페이스(props) 보존, 시각만 디자인시스템 토큰 반영.
3. FE local 커밋 `d575972` (overview UI BE+FE) 확인 (FE remote 미등록 — 폴리레포 + 디자인시스템 정렬 대기 상태).
4. overview 잔여 카드(Services + Disk/Tablespace) 포팅 재개.
