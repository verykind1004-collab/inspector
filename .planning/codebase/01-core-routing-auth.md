# 01. 코어 — 진입점 / 라우팅 / 인증 / 프로세스 제어

대상: `Inspector.py`, `config_loader.py`, `service_config.py`, `auth.py`, `pages/control_process.py`

## Inspector.py (진입점, 536줄)

- 순수 `http.server.BaseHTTPRequestHandler` 단일 HTTP 서버. `0.0.0.0:UTILS_PORT`(기본 8083) 바인드.
- 시작 시: `html_helpers.set_globals()`, `auth.set_utils_base/cookie_name()` 주입 → history 파티션 보장 + scheduler daemon Thread 기동.
- `UTILS_BASE = base_path + check_path`. 응답 헬퍼 `_send(code, ctype, body)`, `_redirect(url)`, 쿼리 `_qs(key)`.
- **do_GET 처리 순서**: (1) fresh-navigation 가드 → (2) `/login`/`/logout` → (3) public(`/labs/api/whoami`,`/labs/api/check-auth`) → (4) `/api/ping` 외 인증 검사 → (5) Repository 미설정 게이트 → (6) `routes` dict.
- **fresh-navigation 가드**: `Sec-Fetch-*` 헤더(폴백 Referer)로 top-level navigation(주소창/새탭) 판별 → 문서 요청이면서 in-app(iframe) 내비게이션이 아니면 **404**(redirect 아님). iframe(같은 origin) 안에서만 화면 노출 정책.
- **Repository 미설정 게이트**: service_config.repository.ip/sid 비면 화이트리스트(`/labs/api/config`,`/api/config`,`/api/connection-test`,`/api/ping`,`/logout`) 외 GET은 "Configuration 필요" HTML, POST는 `/labs/api/config` 외 403.

### 라우팅 맵 (GET routes dict — 인증 필요)

| URL | 함수 |
|---|---|
| `/` | page_overview |
| `/services` | page_services |
| `/partition/create`·`/drop`·`/time` | page_partition_* |
| `/summary/10min`·`/1hour` | page_summary_* |
| `/process/gather`·`/param` | page_process_* |
| `/api/log-tail` | api_log_tail |
| `/disk/capacity`·`/vacuum-age`·`/top-segment`·`/temp-table` | page_disk_* |
| `/session`·`/query` | page_session·page_query |
| `/license`·`/license-check` | page_license·page_license_check |
| `/report` | page_report |
| `/alert` | page_alert |
| `/labs/api/config`·`/api/config` | load_service_config (JSON) |
| `/labs/api/tablespace/data`·`/trend`·`/refresh` | api_tablespace_* |
| `/config-dump` | page_config_dump |
| `/api/control-status` | api_control_status |
| `/history/os/cpu`·`/os/memory`·`/disk/tbs`·`/process/status`·`/qcnt`·`/heap` | page_history_* |
| `/api/history-os`·`-tbs`·`-service`·`-heap`·`-qcnt`·`-proc`·`-data`·`-instances`·`-range` | api_history_* |
| `/history` | type= 있으면 page_history, 없으면 302→/history/os/cpu |
| `/history/configuration` | page_config_in_history |
| `/history/alarm` | page_alarm_history |
| `/api/tablespace`·`/vitals`·`/services`·`/svc-uptimes` | overview API |
| `/api/drop-list`·`/drop-partitions`·`/drop-partitions-status`·`/create-partition`·`/create-procedure` | partition API |
| `/api/vacuum-freeze`(+status)·`/vacuum-table`(+status)·`/age-card`·`/temp-table-drop-all`(+status) | disk API |
| `/api/alert-times`·`/connection-test`·`/dgxml-param-search`·`/alert-svc-read`·`/insp-config`·`/insp-table-status`·`/script-schemas` | 기타 API |

### 라우팅 맵 (POST — do_POST 분기)

| URL | 함수 | 인증 |
|---|---|---|
| `/login`·`/labs/api/login`·`/labs/api/logout` | 인증 | 불필요 |
| `/api/decrypt`·`/alert-svc-save`·`/alert-svc-copy`·`/dgxml-param-save`·`/script-run`·`/control-action` | 각 핸들러 | 필요 |
| `/api/insp-create-schema`·`/insp-init-tables`·`/insp-drop-tables`·`/insp-config-save`·`/insp-create-one-table` | INSP 관리 | 필요 |
| `/api/config-dump`·`/config-restore` | 덤프/복원 | 필요 |
| `/config`·`/labs/api/config` | service_config 저장(_section=repo/paths/all), repo/all이면 MaxSpace reset 트리거 | 필요 |

### Java 재구현 주의
- 세션 저장소(in-memory dict) → 공유 빈. 정확한 경로 문자열 매칭(`path.split("?")[0]`).
- **이중 응답 잠재 버그**: `/api/log-tail`,`/report`,`/labs/api/tablespace/*` lambda가 내부 `self._send` + 바깥 `_send` 중복 → 응답 단일화 필요.
- fresh-navigation 404 정책(SPA iframe 가정) 게이트웨이 정합 확인.

## config_loader.py (90줄)
- `config.yaml` 로딩 + 타입안전 getter. PyYAML 없으면 2-depth 자체 파서 폴백.
- 탐색 우선순위: Labs/ → Inspector/ → python-utils/. getter 기본값: gateway 8080, platformjs 3000, base_path `/MAXGAUGE`, utils 8083, check_path `/check`, ssl 8443, tablespace 8084.
- Java: SnakeYAML, 동일 탐색순위/기본값 유지.

## service_config.py (26줄)
- `service_config.json` load/save. 스키마: repository{db_type, sid, ip, port, user, password, pg_home, pg_data_dir}, services{platformjs, dgserver_m, dgserver_s[]}, log_paths{...}.
- 비번 평문/암호문 저장. dgserver_s/log_paths.dgserver_s는 리스트(인덱스 동기화).

## auth.py (260줄) — 인증/세션
- 상수: `_AUTH_USER='maxgauge'`, `_AUTH_SALT='mxg_inspector_salt_v1'`, `_AUTH_HASH`(SHA-256), `_SESSION_TTL=3600`, `_SESSIONS={}`(in-memory+Lock), 쿠키 `mxg_sid_{port}`.
- **로그인(POST /labs/api/login)**:
  1. body에서 id/password 추출.
  2. `verify_credential`:
     - 경로 A(관리자): id==maxgauge AND SHA256(salt+pw)==_AUTH_HASH → role=engineer.
     - 경로 B(사용자): Repository `apm_user_list`(user_id, password, is_locked) 조회 → DB 암호문을 **DGServer.jar decrypt** 서브프로세스로 복호화 → 입력 pw와 평문 비교 → role=user. (미설정/없음/locked 별 에러)
  3. 성공: token=`secrets.token_hex(32)`, Set-Cookie HttpOnly/SameSite=Lax(Secure 없음), {ok,role,id}.
- 세션 검증: 쿠키 토큰→dict 조회→만료 시 삭제. 슬라이딩 없음(절대 만료).
- 게이트웨이: `/labs/api/check-auth`(nginx auth_request, 204/401), `/labs/api/whoami`(항상 200).
- **Spring Security 매핑**: AuthenticationProvider 2경로(admin/DB+복호화), role→ROLE_ENGINEER/ROLE_USER. 세션 절대만료 동등성 주의. 보안개선: BCrypt, 복호화 in-process 이식(jar 의존/`Decrypt:` 정규식 제거), 쿠키 Secure.

## pages/control_process.py (574줄) — 프로세스 제어
- `api_control_status()` GET `/api/control-status`, `api_control_action(body)` POST `/api/control-action`.
- 대상: DGServer_M/S(1..N), PlatformJS, PostgreSQL + 각 Observer(mxg_obsd). **Oracle은 원격 제어 미지원**.
- 동작: `.mxgrc` 파서(DG_NAME/XMS/XMX/MXG_HOME/JAVA_HOME), `nohup java -Xms..-Xmx.. -{DG_NAME} -jar DGServer.jar &` 기동 후 ps|grep PID 폴링(5회). Observer: `mxg_obsd -c {DG_NAME} -f {conf} -OTHERD -i 10 -D`. PlatformJS: `platformjs.start.sh -r` / stop.sh(Jetty graceful). PG: pg_home start.sh/stop.sh + 연결 폴링(20초). 중지는 Observer 먼저(재기동 방지)→kill→5초→kill -9. restart=stop→5s→start.
- 상태 필드: id,name,status,port,pid,uptime,dg_name,heap,obsd_pid,obsd_status.
- **Java 주의**: 전부 셸 의존(ps/grep/awk/kill/nohup/bash) → ProcessBuilder. **shell injection 표면**(DG_NAME 보간) → 검증 필수. 고정 경로(`bin/mxg_obsd/{os_type}/`, linux64 하드코딩), 타임아웃/폴링 횟수 동일 재현, Observer keyword 식별 규약 유지.
