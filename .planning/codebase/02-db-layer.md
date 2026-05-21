# 02. DB 접근 계층 / 진단 SQL / 시스템 수집

대상: `db_utils.py`, `insp_oracle.py`, `insp_pg.py`, `sql_library.py`, `system_utils.py`

## db_utils.py (526줄) — 범용 SQL 실행 계층
- `run_db_query(sql)` — db_type 분기 SELECT, 텍스트 표 반환 (Oracle call_timeout=30s, PG autocommit+statement_timeout 30s).
- `run_db_query_readonly(sql, max_rows, search_path)` — Script Manager용. READ ONLY 트랜잭션, 쓰기 거부, `(text, err, truncated)`. max_rows+1 fetch로 잘림 판단.
- `run_db_exec(sql)` — 결과셋 없는 DDL/익명블록 (commit).
- `_strip_oracle_directives`(SET/COLUMN/WHENEVER/PROMPT/SPOOL/...), `_strip_pg_directives`(psql `\` 메타), `_split_pg_stmts`(`$$ LANGUAGE plpgsql;` 기준 분리).
- `_cursor_to_table_text`/`_parse_db_table`(psql `|`/`+`, sqlplus 고정폭 역파싱), `_pg_function_defs`(pg_get_functiondef 캐싱), `_sql_embed`(화면 팝업 JS 글로벌).
- 드라이버: `oracledb`, `psycopg2` (번들 sys.path 동적 추가). 설정: service_config.repository.
- **Java**: JDBC 직매핑. setQueryTimeout(30). SELECT 여부=`Statement.execute()` boolean. READ ONLY=`setReadOnly(true)`+SET TRANSACTION READ ONLY (ORA-01456/01453, "read-only transaction" 매핑). `$$` 분리 유지(JDBC 다중문 미지원). 텍스트 표 파싱은 ResultSet 직접처리로 제거 가능(단 화면이 기대하는 포맷은 포맷터 유지).

## sql_library.py (741줄) — 진단 SQL 카탈로그
- `_get_sql(key)` — db_type 분기 + partition_create는 D+1~D+3 날짜 치환. key: partition_create/drop, summary_10min/1hour, session, capacity, license, alert, query, vacuum, age, top_segment, temp_table (vacuum/age는 PG 전용).
- 수집 대상:
  - **MaxGauge Repository 메타**: `apm_db_info`(대상DB 목록·db_id·instance_name·rts_version·host_ip·port), `apm_partition_manage`(retention), `ora_*`/PG 함수(summary 지연/알람/세션/플랜/바인드/TBS/파라미터).
  - **Oracle 딕셔너리**: dba_tab_partitions, dba_segments, dba_free_space, dba_data_files, dba_users, user_*, V$.
  - **PG 카탈로그**: pg_tables, pg_class, pg_namespace, pg_stat_user_tables, pg_settings, pg_database, pg_*_size, txid_current(), age(datfrozenxid).
  - 파티션 이름: Oracle `P+YYMMDD+LPAD(db_id,3)`(`^P[0-9]{9}$`), PG `<table>_pYYMMDD<db_id3>`.
- **Java**: SQL을 MyBatis mapper XML(databaseId 분기) 또는 외부 .sql 리소스로. **db_id 문자열 보간 → 정수검증 후 바인딩**(인젝션). SQL*Plus/psql 지시어 포팅 시 제거. Oracle/PG 두 벌 유지가 안전. 일부 PG 점검은 서버측 함수(`insp_session_check` 등) 호출 → DB 별도 배포 필요.

## insp_oracle.py (605줄) — Oracle 이력 저장
- `_insp_connect`, create/drop/check(`user_tables`), INSERT(`insp_insert_os/_tbs/_services/_heap/_qcnt/_proc/_summary`, bind `:1..`, executemany for proc), `insp_cleanup_old_partitions`(`user_tab_partitions` high_value vs SYSTIMESTAMP-INTERVAL), 월요약 MERGE(`INSP_MONTHLY_SUMMARY`).
- INTERVAL RANGE 파티셔닝(`INTERVAL (NUMTODSINTERVAL(1,'DAY'))`) — Oracle 자동생성. LOCAL 인덱스.
- **Java**: HikariCP. bind→PreparedStatement, executemany→addBatch/executeBatch. MERGE 유지. high_value 비교 동적SQL 필요. 수집 INSERT는 silent 실패 정책 유지.

## insp_pg.py (750줄) — PG 이력 저장
- 접속 dbname=insp_config.json.pg_db.sid(없으면 repo.sid), 스키마 고정 `insp`, `SET search_path TO insp,public`.
- create/drop(`information_schema.tables`), **수동 일별 RANGE 파티션**(`_create_one_partition`/`insp_pg_ensure_partitions` — today+tomorrow 선생성, `pg_class`/`pg_namespace` 확인), INSERT(`%s`), cleanup(`pg_inherits` 자식 나열→이름 접미사 비교 DROP), 월요약 `ON CONFLICT DO UPDATE`.
- **핵심 차이**: PG는 자동 파티션 생성 없음 → 앱이 일별 선생성. Java 스케줄러도 동일 필요. dbname 출처가 Oracle과 다름. ON CONFLICT vs MERGE 분기. DB별 DAO 분리 필수.

## system_utils.py (700줄) — OS/시스템 수집
- OS: `_proc_snapshot_top`(ps top N), `_cpu_percent`(/proc/stat 2회 차분), `_memory`(/proc/meminfo), `_disk*`(os.statvfs), `_uptime`, `_cpu_cores`.
- 프로세스/포트: ss/netstat/ps로 PID·포트, `_dg_info`(DGServer.xml gather_port/database, PID/상태), `_proc_uptime_html`(ps lstart/etime), `_check_tcp`(socket).
- DB 보강: `_repodb_info`/`_get_repodb_version`/`_uptime`(Oracle V$INSTANCE, PG current_setting/pg_postmaster_start_time), `_tablespace_for_overview`(Oracle TBS SQL, 5분 TTL 캐시).
- java/jar: `_find_java`(config→JAVA_HOME→`bash -lc command -v java`→`~/jdk*` glob), `_run_jar`(버전 추출), pjs/client 버전.
- **Java**: OSHI 라이브러리(CPU%/메모리/디스크) + ProcessBuilder(ps/ss). 캐시 Caffeine. java 버전 탐지는 단순화 가능(자기 자신이 Java).

## DB 접근 패턴 종합
- **풀 없음** → HikariCP 도입 필수(수집/조회 풀 분리 권장).
- 트랜잭션: 조회는 readonly+rollback, 쓰기/DDL은 명시 commit, PG INSERT 대부분 autocommit. 타임아웃 30s(수집 INSERT는 무제한).
- 분기: `db_type` 문자열 포함 여부. 진입점 db_utils + sql_library `_get_sql` + 파일 분리(insp_oracle/insp_pg). 접속정보 출처도 다름.
- **권장**: JPA 부적합(딕셔너리/벤더SQL/DDL 중심). **MyBatis(진단SQL, databaseId 분기) + JdbcTemplate(동적 DDL/파티션) + raw Statement(Script Manager readonly)**. db_id 바인딩 전환, PL/pgSQL `$$` 분리 유지, 지시어 제거, PG 서버측 함수 배포, 수집 silent 정책 한정 유지.
