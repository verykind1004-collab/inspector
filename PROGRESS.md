# PROGRESS — MaxGauge Inspector Labs (Java 재구현)

## 핵심 목표 (2026-06-02 재정의 — 1:1 동등 포팅)
**기존 Inspector Labs(release/inspector/Labs/, Labs 변형 2311+PG패치)의 모든 기능을 1:1 동등하게 재구현한다.** 변경 가능 = **스택·언어·디자인·보안** 만. 기능·화면 구성·SQL 본문·설정 파일 스키마·동작은 원본과 동일. **원본에 없는 새 화면/기능 추가 금지.** 풀스택(백엔드 Java + 프론트 React SPA). 규약 = CLAUDE.md 0/H/I절.

이전 "확장 플랫폼" 도그마는 폐기(2026-06-02). 공통화(표준 JSON·2층 컴포넌트)는 24개 기존 화면을 일관 처리하기 위한 **품질 원칙**이며 신규 화면 정당화 수단이 아니다.

## 현재 작업
3.5 단계(원칙 재정렬 + SQL alias 정정) 완료 직후 → Phase B(ADR 0001 스택 풀세트 + 24개 화면 단계 포팅).

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

- **버전 분기 검토 + 1:1 동등 원칙 재정렬 + SQL alias 정정 (3.5 단계, 2026-06-02, 미커밋)**:
  - 검토 결과: 명시적 if-else 버전 분기 없음. 빌드별 sql_library.py 분리 방식. **2311 vs 2407+ 두 라인**(2407=2506=2604 동일), 주로 PG 파티션 SQL 차이.
  - 우리 베이스(`release/inspector/Labs/`)는 **Labs 변형 = 2311 라인 + 2026-04 PG 스키마 인식 패치**. 정식 빌드 어느 것과도 다름. Summary SQL md5 확인 결과 정식 라인은 동일·우리 베이스는 별개. → **베이스 = Labs 변형 확정**(사용자 결정).
  - **헌법 재정리**: CLAUDE.md 0절 "확장 플랫폼" 도그마 폐기 → "1:1 동등 포팅" 명문화. I절 제목·본문 재작성("화면 포팅 규약 1:1 동등 + 공통화 강제", SQL 충실 이식 원칙, 원본 24개 화면 인벤토리 명시). H절에 신규 화면·기능 추가 금지/SQL 본문 임의 변경 금지/설정 스키마 변경 금지 추가.
  - **SQL alias 정정**: SummaryMapper.xml 4개 select 의 컬럼 alias 를 소문자 통일 → 원본(`"DB ID"`/INSTANCE_NAME/SUMMARY_TYPE/LAST_SUMMARY/STATUS/DELAY_INFO) 그대로. resultMap 도입으로 alias→필드 명시 매핑(map-underscore-to-camel-case 우회 의존 제거). SQL 의미는 본래도 동일이었고 alias만 정정.
  - **환경 인지 정정**: 라이브 저장소 접속정보 공란이라 보고했던 것은 잘못. `/home/inspector/ORACLE/{2311,2407,2506,2604}/Inspector/python-utils/service_config.json` 등에 mxg2604@10.10.45.136:1521/ORACLE19 등 전 버전 접속정보(비번 평문) 보유. 리스너 TCP_OK 확인. apm_db_info·ora_last_summary 는 실 운영 저장소에 존재 → **실 저장소 런타임 검증 즉시 가능**.

## 다음 첫 액션 (새 세션에서 이어갈 때 여기부터)
**Phase A (3.5 단계 정리 — 즉시 처리)**
1. mapper alias 정정 + 헌법·PROGRESS 재정리 정정 커밋 + push (브랜치 `setup/foundation`)
2. clean test 19 PASS 유지 확인

**Phase B (1:1 동등 원칙 하 풀세트 구현)**
3. 백엔드 실 저장소 런타임 검증 — mxg2604(또는 2311 가동 중 라인) service_config.json 작성 → `spring-boot:run` + 로그인 → `/labs/api/summary/10min` 표준 JSON 실측
4. 프론트 풀세트(ADR 0001 스택 전부) — TanStack Router(파일 기반) + MSW(dev+test) + Radix(2층 atom 보강) + Storybook + Playwright(1 시나리오: Summary 로딩→필터→정렬) + dev 프록시(:8083) + 2층 ScreenTable 렌더러 + Summary feature/page
5. 두 번째 화면 포팅(session) — 동일 규약 검증
6. 나머지 22 화면 단계 포팅(원본 인벤토리 따라 — capacity/license/alert/query/top_segment/temp_table/vacuum/age/overview/history/report/alarm_history/alert_svc_config/config_page/config_dump/control_process/script_manager/char_setting 등)
7. 병행: auth.py 경로B(DB 사용자 인증) — DGServer.jar 복호화 분석

## 미해결 결정
- 표준 JSON 스키마 확장 — 정렬/페이징/필터 서버위임은 대용량 화면(query·history 등) 포팅 시 필요 시 도입(현 시점 1:1 원칙상 원본 미지원이면 미도입)
- INSP_* 테이블 DDL, MXG_* DB함수 — 화면 포팅 시점에 케이스별 확보
- **오픈소스/라이선스 검증 기준 — 백엔드 개발팀 확인 필요**: 고객사 외부 인터넷 차단 + 검증 오픈소스만 허용. ①Oracle ojdbc8(OTN) ②Spring Boot 전이의존성 SBOM ③폐쇄망 사내 미러(Nexus)

## 차단 요인
- 없음(라이브 저장소 검증 차단 요인 해소). `@exem-fe/*` 레지스트리만 프론트 1층 교체 시점에 필요(개발팀 대기, 임시 컴포넌트로 진행 가능)
