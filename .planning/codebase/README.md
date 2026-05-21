# Codebase 분석 — MaxGauge Inspector Labs (기존 Python → Java 재구현 명세)

> 분석일: 2026-05-21 / 대상: `Labs/Inspector/python-utils/` (참조 명세, 읽기 전용)
> 방법: 영역별 병렬 분석. 본 디렉토리는 GSD map-codebase 산출 컨벤션을 따른다.

## 문서 구성

- [01-core-routing-auth.md](01-core-routing-auth.md) — 진입점/라우팅/인증/프로세스 제어
- [02-db-layer.md](02-db-layer.md) — DB 접근 계층/진단 SQL/시스템 수집
- [03-history-subsystem.md](03-history-subsystem.md) — 이력 수집/스케줄러/파티션
- [04-pages-and-ui.md](04-pages-and-ui.md) — 기능 페이지 + html_helpers 공통 UI(디자인시스템 기준)

## 전체 아키텍처 요약

- 규모: 약 21,500 라인 (공통 모듈 6,509 + pages 14,977).
- 런타임: **순수 Python 표준 `http.server.BaseHTTPRequestHandler`** 기반 단일 HTTP 서버. Flask/FastAPI 아님 (README의 "FastAPI" 표기는 실제 구현과 불일치 — 재구현 문서에서 정정).
- 라우팅: `Inspector.py`의 `routes` dict(GET) + `do_POST` 분기(POST)로 중앙 집중. 모든 경로에 `UTILS_BASE`(config의 base_path+check_path, 운영 예: `/MAXGAUGE/check`) prefix.
- 렌더링: 페이지 HTML을 Python 문자열로 직접 조립(`html_helpers`). 템플릿 엔진 없음.
- DB: Repository DB 타입(`db_type`에 oracle/postgres 포함 여부)으로 전 경로 분기. Oracle/PG 이원화.
- 수집: 부팅 시 daemon Thread 1개가 30초 폴링 스케줄러로 OS/프로세스/이력 수집.

## 핵심 발견 (재구현 영향)

| 발견 | 현재 | Java 재구현 방향 |
|---|---|---|
| 인증 강도 | 관리자 SHA-256 1회+고정 salt, 사용자 비번은 DGServer.jar 복호화 후 평문 비교 | Spring Security, 관리자는 BCrypt/Argon2 권장. 단 기존 DB 비번 호환 위해 검증 경로 유지 |
| 세션 | in-memory dict, 고정 TTL 1h(비슬라이딩), 쿠키 `mxg_sid_{port}` HttpOnly/SameSite=Lax (Secure 없음) | Spring Session(Redis/JDBC), 멀티 인스턴스화, Secure 플래그 추가 |
| 커넥션 | 풀 없음, 호출마다 connect→close | HikariCP. 수집 잡과 사용자 조회 풀 분리 |
| ORM | 없음(raw SQL) | **JPA 부적합** → MyBatis(진단 SQL 카탈로그) + JdbcTemplate(동적 DDL/파티션) |
| Oracle 핵심 로직 | PL/SQL 프로시저(`INSP_PARTITION_CREATE/DROP_TARGET`, `MXG_*`)에 내장 | 프로시저 유지, Java는 호출 래퍼만 |
| PG 파티션 | 자동생성 없음, 앱이 일별 파티션 선생성 | 스케줄러가 일별 파티션 선생성 유지 |
| 비동기 작업 | vacuum/drop 등 백그라운드 스레드+상태 폴링 | Spring @Async + 상태 빈/작업 테이블 |
| OS 의존 | `/proc` 파싱, ps/ss/netstat, grep, kill, java -jar 서브프로세스 다수 | OSHI 라이브러리 + ProcessBuilder. Linux 전용 전제 |
| 잠재 버그 | 일부 라우트 lambda가 내부서 `self._send` 호출 + 바깥서 또 전송 (이중 응답) | 응답 단일화 설계 |
| 미연결 | `char_setting` API가 현 라우팅 테이블에 미등록 | 라우팅 누락 여부 확인 후 결정 |

## Java 재구현 권장 순서 (goal-backward)

1. **공통 인프라 (선행, 전 페이지 의존)**
   - DB 추상화 계층 (Oracle/PG 분기, `run_db_query`/`readonly`/`exec` 대응)
   - 디자인시스템: `html_helpers` 공통 UI → Thymeleaf 레이아웃 데코레이터 + fragment(사이드바/FAB/테이블렌더러/배지/필터/도움말) + CSS 토큰셋 (상세 [04](04-pages-and-ui.md))
   - 인증/세션 (Spring Security)
2. **검증용 단순 화면**: summary(상태표) — 파이프라인 빠른 검증
3. **메인 화면**: overview(대시보드) → license(인스턴스 목록)
4. **수집 점검 공통 템플릿**: session/query/summary/partition 상태 (`_db_page` 공통화)
5. **스케줄러 + 수집기** (@Scheduled)
6. **이력 조회 API** (history_views)
7. **부가/난이도 높은 것**: disk 비동기 작업, process 로그뷰어, config_dump, **partition(최난이도 — 프로시저 호출 래퍼)**
8. FAB 도구군(report/script-run/decrypt/control/char_setting) 마지막

## 미확인/후속 분석 필요

- INSP_* 이력 테이블 정확한 컬럼 DDL (insp_oracle.py / insp_pg.py 내부)
- `sql_library`의 summary/STATUS/DELAY 계산 SQL 본문 (상태 분류가 SQL 내장)
- `MXG_GET_PARTITION_KEY_532` 등 DB측 함수 본문
- PG 서버측 함수(`insp_session_check` 등) 별도 배포 필요 여부
- `apm_user_list` 전체 스키마
