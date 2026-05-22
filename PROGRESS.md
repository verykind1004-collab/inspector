# PROGRESS — MaxGauge Inspector Labs (Java 재구현)

## 핵심 목표 (재정의됨)
단순 1:1 포팅이 아니라, **다양한 DB 성능분석 화면을 통일된 UI·화면구조·백엔드로 계속 추가할 수 있는 확장 플랫폼** 구축. **풀스택(백엔드 Java + 프론트 React SPA, 둘 다 우리가 구축).** 규약은 CLAUDE.md I절.

## 현재 작업
3단계 첫 화면(Summary Check) 백엔드 + **표준 JSON 응답 스키마** 구현 완료(미커밋) → 다음은 프론트 레포 부트스트랩 + 실 저장소 런타임 검증.

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

- **표준 JSON 응답 스키마 + 첫 화면(Summary Check) 백엔드 (3단계, 2026-05-22, 미커밋)**:
  - **표준 표 응답 계약**(`common/web/screen/`): `ScreenResponse`(meta+columns+rows) + `ColumnDef`(key/label/type/role/hidden) + `ColumnType`(STRING/NUMBER/DATETIME) + `ColumnRole`(PLAIN/ID/INSTANCE/GROUP/STATUS/DELAY) + `ScreenMeta`. 행=컬럼 key 맵. 2층 공통 테이블 렌더러가 이 스키마만 보고 렌더(I절 — 화면마다 제각각 금지). 표준 봉투 `common/web/ApiResponse`(ok/error/data — 기존 _warn_box 분기 통일)
  - **Summary Check 화면 1세트**(`screen/summary/`): `SummaryController`(`/labs/api/summary/10min`·`/1hour`) → `SummaryService`(매퍼행→표준응답, 컬럼메타 화면고정, 미설정 시 IllegalStateException) → `SummaryMapper`(@Mapper, ObjectProvider 선택주입) + `mapper/summary/SummaryMapper.xml`(databaseId Oracle/PG 두 벌, sql_library.py 충실 포팅, SQL*Plus/psql 지시어 제거). `SummaryRow`(db_id/instance_name/summary_type/last_summary/status/delay_info)
  - 컬럼 계약 확정: DB ID(ID) / Instance Name(INSTANCE·필터) / Summary Type(GROUP·칩) / Last Summary(DATETIME) / Status(STATUS·배지 OK/CHECK/WAITING/ERROR) / Delay(DELAY·hidden·툴팁)
  - **검증: `clean test` BUILD SUCCESS, 19 tests PASS** (기존 13 + ScreenResponseTest 3[빌더·검증·JSON직렬화형태고정] + SummaryServiceTest 3[행변환·미설정예외·빈결과])
  - **런타임 검증 보류(환경)**: 라이브 MaxGauge 저장소 접속정보 부재(service_config.json repository 블록 공란). 내부 테스트 Oracle(ORA19)에는 apm_db_info/ora_last_summary 미존재 → 실 매퍼 런타임 검증은 저장소 접속정보 확보 후

## 다음 첫 액션 (새 세션에서 이어갈 때 여기부터)
1. 3단계 결과 커밋(표준 JSON 스키마 + Summary 화면) → setup/foundation, 누적 3커밋 origin push 결정
2. **실 저장소 런타임 검증**: MaxGauge 저장소 접속정보(service_config.json repository) 확보 → `spring-boot:run` + 로그인 후 `/labs/api/summary/10min` 응답 확인(DataSource→SqlSessionFactory→매퍼 활성 + 표준 JSON 실측). 불가 시 ORA19에 apm_db_info/ora_last_summary 최소 시드
3. 프론트 레포 부트스트랩(Vite+React+FSD, 위치 TBD) — 2층 공통 테이블 렌더러(ScreenResponse 소비) + Summary feature 첫 화면
4. 두 번째 화면(session) 동일 규약으로 추가 — 표준 스키마 일반성 검증(컬럼 가변)
5. 병행: auth.py 경로B(DB 사용자 인증) — DGServer.jar 복호화 분석 후

## 미해결 결정
- 프론트 레포 위치/원격 (TBD)
- 표준 JSON 스키마 1차 확정(3단계). 정렬/페이징/필터 서버위임 여부는 대용량 화면 실증 시 재검토
- char_setting 라우팅 미연결 처리 (재구현 시 반영)
- 후속 분석 필요: INSP_* 테이블 DDL, MXG_* DB함수 (구현 직전). summary SQL 본문은 3단계에서 확보·포팅 완료
- **오픈소스/라이선스 검증 기준 — 백엔드 개발팀 확인 필요**: 고객사 외부 인터넷 차단 + 검증 오픈소스만 허용. 최종 jar 포함 의존성이 검증 대상. ①Oracle ojdbc8 라이선스(OTN) ②Spring Boot 전이의존성 CVE/SBOM ③폐쇄망 사내 미러(Nexus/Artifactory) 필요 여부

## 차단 요인
- 실 저장소 런타임 검증: MaxGauge 저장소 접속정보 부재(환경) — 접속정보 확보 또는 테스트 DB 시드 필요
