# 03. 이력(History) 서브시스템 — 수집 / 스케줄러 / 파티션

대상: `history.py`, `pages/history_page.py`, `pages/history_views.py`, `pages/partition.py`, `pages/summary.py`

## 파이프라인 흐름

```
[Inspector.py 부팅] → daemon Thread → history._scheduler_loop() (30초 폴링, 시각 키 비교로 멱등)
  ├ 수집: :05,:15…→10min요약 / :30→1hour요약 / 1분→OS·Proc·Qcnt·Heap / 매시→Service / 23:50→TBS / 매월1일 00:10→월요약
  ├ 파티션: 23:50→PG 일별 선생성(내일·모레) / 00:05→retention cleanup
  └ 로그: 00:01 nginx rotate(USR1) / 00:02 IH rotate(zip)
[저장] PG public.summary_history(일별 파티션, 하드코딩 127.0.0.1/MI/postgres) + INSP_*_HISTORY(Oracle/PG 분기) + APM_*(partition.py)
[조회] /summary/* (summary.py) · /history?type=, /api/history-data·instances·range · /history/os·disk·process/*, /api/history-* (history_views) · /config, /api/insp-* (history_page) · /partition/* (partition.py)
```

## history.py (816줄) — 엔진
- HTTP 엔드포인트 없음. 진입점: `_scheduler_loop`(daemon Thread), `_ensure_partition`.
- **스케줄러**: while+sleep(30). 분/시/일 키 문자열 비교로 중복 실행 방지(cron 아님).
- `_collect_summary_history`: `_get_sql`→run_db_query→`_parse_db_table`→헤더 키워드(INSTANCE/SUMMARY TYPE/STATUS/LAST/DELAY/DB ID)로 컬럼 인덱스 동적 매핑→PG summary_history 항상 INSERT, INSP enabled 시 추가.
- OS/Proc/Service/TBS: system_utils 취득 → insp_*.insert_*.
- **Qcnt/Heap**: DGServer_S 로그를 grep(subprocess)+정규식(`[HH:MM:SS.mmm]`, Heap used/alloc, conn_info) 파싱. 분 단위 dedup(전역 `_last_*_ts`), 최근 1440줄. "성공할 때까지 같은 분 재시도".
- 월요약: 전월 INSP_OS/TBS AVG → upsert.
- 설정: `insp_config.json`{enabled, tables_initialized, retention_days(31), log_retention_days(10), pg_db}. 10초 캐시.
- **Java**: @Scheduled 분해(작업별 cron). Qcnt/Heap 재시도 상태 추적 별도. PG 하드코딩(127.0.0.1/MI/postgres) 외부화 필수. 로그 grep→파일스트림+정규식, USR1→nginx reopen 재설계. 헤더 키워드 컬럼매핑 유지(컬럼 순서 비고정).

## pages/summary.py (364줄) — 요약 상태표 (가장 단순, 선행 재구현 권장)
- `page_summary_10min/1hour` → `/summary/10min`·`/1hour`. 내부 `_summary_filter_page`.
- `_get_sql`→run_db_query→`_parse_db_table`→`_build_summary_table`. STATUS(OK/CHECK/ERROR/WAITING) 배지, DELAY는 툴팁. 저장 없음(순수 조회/표시). STATUS/DELAY 분류는 SQL에 내장.

## pages/history_page.py (1339줄) — 설정/DDL 관리 + 요약 페이지
- `page_history(path)` `/history?type=`, `page_history_config()` `/config`.
- INSP 라이프사이클 API: insp-create-schema(PG), insp-init-tables/drop-tables(db_type 분기, tables_initialized 토글), insp-table-status, insp-create-one-table, insp-config-save/load.
- 설정은 insp_config.json read/write. 거대 인라인 HTML/CSS/JS.
- **Java**: 템플릿 엔진 전환. 설정은 단일 빈+파일 동기화. DDL API는 권한/트랜잭션 강화.

## pages/history_views.py (2547줄, 대부분 차트 JS) — 조회 뷰/데이터 API
- 데이터 API(GET JSON, `?date=&from=&to=` 또는 `?at=`): api_history_proc(`at`+sort, 분단위 Top20), os, tbs, heap, qcnt, service, + 요약(instances/data/range, Oracle/PG 분기).
- 페이지: history_os_cpu/memory, disk_tbs, process_status/qcnt/heap.
- `_insp_conn()`이 repo 타입별 연결. `INSP_*_HISTORY` 직접 SELECT(PG 소문자/`to_timestamp`, Oracle 대문자/`TO_TIMESTAMP(:1)`). 없으면 `_table_missing_html`. `_safe()` 직렬화.
- **Java**: PG/Oracle 쿼리 이원화 유지 또는 통합. 컬럼 대소문자/바인드 형식 차이. `at`은 분단위(:00) — 수집측과 정합 유지.

## pages/partition.py (1650줄) — APM 파티션 운영 (최난이도)
- 대상: 모니터링 본체 **APM_ 테이블 파티션**(INSP 이력 아님). 또한 session/query 페이지의 공통 `_db_page` 본체 보유.
- 페이지: partition/create·drop·time. API: create-partition(instance,from,to), drop-list, drop-partitions(비동기), drop-partitions-status, create-procedure.
- **Oracle 생성**: apm_db_info로 db_id 조회 → 저장 프로시저 `INSP_PARTITION_CREATE_TARGET(db_id,from,to)` 호출. 프로시저 DDL이 파일 상수(`_PROC_DDL`): apm_partition_manage 템플릿 순회 → `MXG_GET_PARTITION_KEY_532`로 키 → `P+키` → dba_tab_partitions 실존 확인 → apm_partition_history self-heal → ALTER TABLE ADD PARTITION. `DBMS_LOCK.sleep` 부하분산.
- **Oracle 삭제**: `INSP_PARTITION_DROP_TARGET(db_id)`.
- **PG**: 직접 CREATE/DROP TABLE PARTITION + apm_partition_history DELETE + VACUUM. plpgsql 동적 함수(insp_session_check 등, string_agg UNION ALL) 파일 상수 내장.
- **비동기 drop**: `_pd_state` dict+Lock+daemon Thread, running 플래그, status 폴링(dropped/total/elapsed/error).
- 파티션 시간 뷰: DGServer_M 로그 `[PARTITION MANAGE] ... start/finish` 정규식 매칭→소요시간.
- **Java**: 최난이도. Oracle 핵심이 PL/SQL → **프로시저 유지, 호출 래퍼만**. 비동기 상태머신→@Async+상태빈/작업테이블. PG plpgsql 함수 유지 vs 포팅 결정. 로그 정규식 OS 의존. **instance_name 인젝션**(현재 수동 `replace("'","''")`) → PreparedStatement 필수.

## 재구현 우선순위/난이도
| 영역 | 우선 | 난이도 | 사유 |
|---|---|---|---|
| summary | 1 | 하 | 조회/렌더만, 빠른 검증 |
| 스케줄러(history) | 2 | 중 | @Scheduled 분해, Qcnt/Heap 재시도·로그 grep 주의 |
| history_views | 3 | 중 | 쿼리 이원화+직렬화, 반복적 |
| history_page | 4 | 중 | 설정 동기화·DDL 권한·템플릿화 |
| partition | 5 | 상 | PL/SQL·plpgsql·비동기·self-heal·로그파싱 |

권장: DB 추상화 확립 → summary로 파이프라인 검증 → @Scheduled 스케줄러 → 조회 API → 파티션은 프로시저 호출 얇은 래퍼.
