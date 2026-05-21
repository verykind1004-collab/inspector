# PROGRESS — MaxGauge Inspector Labs (Java 재구현)

## 핵심 목표 (재정의됨)
단순 1:1 포팅이 아니라, **다양한 DB 성능분석 화면을 통일된 UI·화면구조·백엔드로 계속 추가할 수 있는 확장 플랫폼** 구축. 규약은 CLAUDE.md I절.

## 현재 작업
1단계(스켈레톤)·2단계(공통 인프라 골격) 완료 → 3단계(첫 화면 실증) 착수 직전. 모두 미커밋(커밋은 사용자 지시 대기)

## 마지막 완료
- 서버 git 작업트리 `release/inspector` (clone, public), git config, 브랜치 `setup/foundation`
- CLAUDE.md (Karpathy 헌법 + 스택 + SSOT + 금지 + **I절 분석화면 추가 규약**) / PROGRESS push
- 기존 python-utils 전수 분석 → `.planning/codebase/` 5문서 (commit d62d07b)
- ADR 방향 확정:
  - DB 접근: **MyBatis(databaseId 분기) + JdbcTemplate(동적 DDL) + HikariCP**, JPA 미사용 [잠정확정]
  - 빌드: **Maven wrapper [확정]** — SB 2.7.18 / JDK8, only-script wrapper(자동 다운로드)
  - gateway: nginx 유지 [확정]
  - 프론트: MaxGauge 본체와 통일 — **정보 수신 대기 중** (SSR/SPA 보류, 표현계층이라 백엔드 코어와 분리)
- **java/ 스켈레톤 생성 (1단계 완료)**:
  - Maven 프로젝트(`pom.xml`, `groupId=com.exem`/`artifactId=inspector`), SB 2.7.18, JDK8, `mvnw` wrapper
  - 패키지 골격(I절 인코딩): `config/`(DatabaseConfig — MyBatis databaseId Oracle/PG 분기), `common/db/`(DbType enum), `common/web/`(PingController `/api/ping`), `screen/`(package-info 화면추가 규약)
  - DB 추상화 골격: 접속정보는 service_config.json 런타임 로딩 → `DataSourceAutoConfiguration` 제외(DB 미연결 부팅 허용), MyBatis는 datasource 부재 시 backoff
  - 표현계층(templates/)은 디렉토리만 — 프론트 SSR/SPA 결정 대기(C절 분리)
  - **검증: `./mvnw -B -ntp clean test` BUILD SUCCESS, contextLoads PASS, JDK 1.8.0_422 부팅 확인**
  - CLAUDE.md G절 빌드 명령 gradle→maven 정정(SSOT 충돌 해소)
- **공통 인프라 골격 (2단계 완료)**:
  - 2-A 동적 DataSource: `ServiceConfig`(service_config.json 로딩·reload) + `RepositoryConfig`(repository 매핑) + `DbType`(Oracle service_name / PG dbname URL·기본포트·드라이버) + `DataSourceConfig`(HikariCP, `@Conditional(RepositoryConfiguredCondition)` — 미설정 시 빈 미등록·부팅 유지, `initializationFailTimeout=-1`로 DB 미가동 허용). 단일 풀(수집/조회 분리는 부하검증 시)
  - 2-B Spring Security: `SecurityConfig`(공개경로 화이트리스트 + anyRequest authenticated + 미인증 401 entryPoint=nginx auth_request용 + 세션 IF_REQUIRED) + `AdminAuthenticationProvider`(경로A: SHA256(salt+pw)==hash → ROLE_ENGINEER) + `AuthProperties`(auth.py 상수 외부화) + `AuthController`(/labs/api/login·logout·check-auth·whoami, JSON 로그인)
  - **검증: `clean test` BUILD SUCCESS, 13 tests PASS (DbType URL빌더 5 + 관리자인증 3 + 보안웹 4 + contextLoads 1)**
  - 미구현/TODO (트레이드오프 표면화): ①auth.py 경로B(DB 사용자 = apm_user_list + DGServer.jar 복호화) — 복호화 in-process 이식은 jar 알고리즘 분석 선행, DataSource 필요라 별도 provider로 추후 ②세션 절대만료(auth.py)는 현재 idle 타임아웃 — 절대만료 커스텀 필터 TODO ③CSRF disabled(JSON+nginx 구조, 프론트 확정 후 재검토) ④쿠키 Secure·BCrypt 보안개선

## 다음 첫 액션 (새 세션에서 이어갈 때 여기부터)
1. 3단계 실증: 가장 단순한 화면(summary 또는 session) 1개를 I절 규약대로 재구현(Controller+Service+Mapper) → "새 화면 추가가 일관·간단한가" 검증
   - 이 시점에 프론트 SSR/SPA 정보 필요 → 그 전에 수신 권장. 공통 레이아웃도 이때 함께
   - 실 DataSource 연결(첫 매퍼)도 이때 런타임 검증
2. 병행 가능: auth.py 경로B(DB 사용자 인증) provider — DGServer.jar 복호화 분석 후

## 미해결 결정
- 프론트엔드 SSR vs SPA (MaxGauge 본체 정보 대기)
- char_setting 라우팅 미연결 처리 (재구현 시 반영)
- 후속 분석 필요: INSP_* 테이블 DDL, summary SQL 본문, MXG_* DB함수 (구현 직전)
- **오픈소스/라이선스 검증 기준 — 백엔드 개발팀 확인 필요**: 고객사는 외부 인터넷 차단 + 검증된 오픈소스만 허용. Maven 도구 자체는 고객사 미설치(빌드 전용)라 무관하나, **최종 jar 에 포함되는 의존성이 검증 대상**. 점검 항목 ①Oracle ojdbc8 라이선스(OTN, 오픈소스 아님) ②Spring Boot 전이 의존성 CVE/SBOM 스캔 ③폐쇄망 빌드 정책 시 사내 미러(Nexus/Artifactory) 필요 여부. 기준 확정 후 의존성 선정 — 재작업 방지

## 차단 요인
- 프론트 방식은 실증(3단계)에서만 필요 — 그 전까지 차단 아님
