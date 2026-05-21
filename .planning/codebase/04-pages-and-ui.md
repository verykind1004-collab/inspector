# 04. 기능 페이지 + html_helpers 공통 UI (디자인시스템 기준)

대상: `html_helpers.py` + 기능 페이지 모듈 전체

## html_helpers.py — 공통 렌더링 (Java 디자인시스템의 기준점)

전 페이지가 이 모듈로 조립된다. Thymeleaf 레이아웃/프래그먼트 + 정적 CSS로 이식.

### 레이아웃 / 셸
- `_page(active, title, body, refresh, topbar, ...)` — **최상위 페이지 셸**(`<!DOCTYPE>`~`</html>`): SVG favicon, Pretendard+Inter 폰트, 인라인 `<style>`(`_CSS`), 테이블 정렬 JS(`tbSort`), fetch 401 인터셉터, 사이드바+main+topbar+content-wrap+FAB 조립. → **Thymeleaf layout 데코레이터**(active=현재 메뉴, body=슬롯).
- `set_globals(utils_base, platformjs_port)` — base URL/포트 주입 → context-path.
- `_sidebar(active)` — **좌측 네비**. DB타입(Oracle/PG)별 가변 메뉴. 브랜드→OverView/Instance List→접이식 그룹(Partition·Summary·Process·Disk·Others). localStorage 펼침/스크롤 유지. → **fragment(sidebar)** + 활성화 변수.
- `_tools_fab_block()` — **우하단 FAB 도구메뉴**: Control Process / Daily Report / Script Manager / Encrypt-Decrypt / Alert Service(SMS·API·Mail) / Config Dump. 모달·핸들러 JS 포함. → 전역 도구바 fragment.
- topbar + Inspector History 버튼 + "← Labs"(target=_top, iframe 탈출).

### 상태 표시 컴포넌트
- `_badge(status, text)` — pill 배지. ok/running=녹, warning/waiting=황, critical/stopped=적, unconfigured/off=회. 클래스 `badge-ok|warn|crit|muted`.
- `_svc_icon(status)` — 체크/대시/엑스. `_bar_dyn(pct, status)` — 사용률 진행바(data-bar-pct 클라이언트 임계치). `_warn_box`/`_info_box` — 알림 박스.

### 테이블 렌더링 (핵심)
- `_render_db_table_html(headers, rows)` — **DB 결과셋→정렬가능 테이블**. STATUS 컬럼 자동감지→배지(OK/RUNNING=ok, ERROR/INVALID/FAIL/DOWN/STOPPED=critical, WARNING/VALID=warning). `DELAY_INFO` 숨김+보조표시. 헤더 클릭 정렬(`tbSort`, 숫자/문자 자동).
- `_query_card(title, out, err)`, `_inst_filter_block(tbl_id)` — **인스턴스 검색 필터 UI+JS**(자동완성, X초기화). session/query/partition 공용.

### 제목 / 도움말
- `_page_title_html`, `_help_icon`(호버 툴팁), `_HELP` dict(페이지키→리치HTML 도움말 20+개), `_kr_title`/`_KR_TITLE`(영→한 제목).

### CSS (`_CSS`) — 디자인 토큰
- CSS 변수: `--bg-main/--bg-card/--bd/--c-main/--c-muted/--c-accent/--err-*/--ok-*/--tab-*`.
- 컴포넌트 클래스: `.layout .sidebar .main .content-wrap`, `.nav-*`, `.card`, `.svc-table .tbl-wrap .sortable`, `.badge-*`, `.bar`, `.metric-ok|warning|critical`, `.field .inp .lbl`, `.btn-*`, `.help-tip*`, `.log-err/.log-warn`, `.insp-card*`, `.status-dot`, `@keyframes spinning`.
- → **정적 CSS 1개로 추출해 디자인시스템화**.

### Java 재현 필수 공통요소
① 레이아웃 데코레이터(_page) ② 사이드바 fragment(DB타입 조건부) ③ 전역 FAB 도구바 ④ DB테이블 렌더러(배지+정렬+DELAY) ⑤ 배지/진행바/알림박스 ⑥ 인스턴스 검색필터 ⑦ 도움말 툴팁+_HELP ⑧ CSS 토큰셋 ⑨ 영한 제목 매핑.

## 기능 페이지 목록

| 카테고리 | URL | 기능 | 대상 | 우선 |
|---|---|---|---|---|
| 대시보드 | `/` `/services` + api/vitals·tablespace·svc-uptimes | 리소스·서비스·TBS 메인 | OS+DB+프로세스 | 상 |
| 인스턴스 | `/license`(Instance List), `/license-check` | 인스턴스 목록·라이선스 | DB+로그 | 상 |
| 수집점검 | `/session` `/query` | 마지막 수집시각·수집현황 | DB | 상(_db_page 위임, 7~8줄) |
| Disk | `/disk/capacity·vacuum-age·top-segment·temp-table` + vacuum/temp API | 용량·VACUUM·정리(쓰기) | PG/Oracle | 중(비동기) |
| 로그/파라미터 | `/process/gather·param`, api/log-tail, dgxml | 로그뷰어(tail+zip)·XML 파라미터 | 파일 | 중 |
| 알람 | `/alert`, `/history/alarm`, alert-svc | 알람집계·발송검증·서비스설정 | DB+로그+XML | 중 |
| 설정/이관 | `/config` `/history/configuration` `/config-dump`+restore | 설정편집·연결테스트·덤프복원 | JSON+DB | 중 |
| 도구(FAB) | `/report`, script-run, decrypt, control-action, char_setting | 리포트·SQL실행·암복호·프로세스제어·CHARSET | DB+jar+OS | 하 |

### 페이지별 비고
- **overview(631)**: OS 메트릭(/proc)+프로세스 상태+Oracle TBS. system_utils 집중.
- **process(872)**: DGServer 로그뷰어(tail-follow + .log.zip grep) + DGServer.xml 파라미터. RandomAccessFile+ZipInputStream.
- **disk(1028)**: PG VACUUM FREEZE/TABLE, age, top segment, temp table. **비동기 worker+상태폴링**.
- **tablespace(317)**: API 전용(data/trend/refresh), Overview 차트 데이터소스.
- **session(7)/query(8)**: partition._db_page 위임 얇은 래퍼 → "공통 SQL 점검 페이지 템플릿"의 파라미터 인스턴스.
- **dgxml_modify(579)**: 전 DGServer.xml 파라미터 검색/수정(enable/disable 토글 쓰기). process/param Search 탭이 호출.
- **alert(208)**: 최근 30일 DB Down/Listener/RTS 알람 집계. ORA_ALARM_HISTORY.
- **alarm_history(582)**: 발송대상 알람(SMS_FLAG=1) + SMS/API/Mail **발송 성공여부 로그 파싱 검증**(SUCCESS/FAILED/SKIPPED).
- **alert_svc_config(796)**: SMS/API/Mail XML 설정 읽기/저장/복사. FAB 모달.
- **license(369)**: APM_DB_INFO 인스턴스 목록 + DGS_PORT 매핑(slave 로그).
- **license_check(446)**: 라이선스 정보+인스턴스 상태+금일 이벤트(DGServer_M 로그).
- **report(494)**: 데일리 리포트(독립 인쇄 페이지). 어제 OS평균+월별+점검결과 종합.
- **config_page(800)**: Repository/서비스/로그/History 설정 편집 + 연결테스트(socket). service_config.json.
- **config_dump(888)**: 설정테이블 JSON 덤프/복원(서버 이관). Oracle/PG 리터럴 분기+시퀀스 보존.
- **script_manager(115)**: 읽기전용 SQL 실행기. **보안가드**: SELECT/WITH/EXPLAIN/SHOW/VALUES/DESC만, 1000행 절단, schema 영숫자+`_`. 이식 필수.
- **decrypt(102)**: DGServer.jar encrypt/decrypt 호출. Java는 자기 기능 직접호출로 단순화.
- **char_setting(260)**: 인스턴스 CHARSET 일괄변경(apm_web_env+apm_db_info). **현 라우팅 미연결 — 확인 요망**.

## 재구현 주의 (UI/페이지 공통)
1. HTML 코드 하드코딩 → Thymeleaf 전환 시 인라인 스타일/JS 분리.
2. 다수 페이지가 OS/로그파일/외부 jar 직접 의존(subprocess/proc/zip) → 서비스 계층 분리.
3. Oracle/PG 분기가 사이드바·SQL·config_dump 곳곳 → DB타입 추상화.
4. script_manager read-only 가드, decrypt java.path 등 보안/환경 로직 보존.
5. disk/vacuum 백그라운드+폴링 패턴.
6. char_setting 라우팅 누락 확인.
