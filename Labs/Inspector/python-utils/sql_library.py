# __PATCH_PG_PARTITION_SCHEMA_AWARE__ applied 20260410_174845
# -*- coding: utf-8 -*-
from service_config import load_service_config

# ── Oracle SQL constants ────────────────────────────────────────────────────────

_SQL_ORACLE_PARTITION_CREATE_TMPL = """
SET LINESIZE 1000
SET PAGESIZE 100
SET FEEDBACK OFF
SET HEADING ON
SET SPACE 1
SET TAB OFF
COLUMN "DB ID"         FORMAT 999999
COLUMN "INSTANCE NAME" FORMAT A25
COLUMN "D+1 ({d1})"   FORMAT A18
COLUMN "D+2 ({d2})"   FORMAT A18
COLUMN "D+3 ({d3})"   FORMAT A18
COLUMN STATUS          FORMAT A10

WITH d AS (
  SELECT LEVEL AS day_offset,
         TO_CHAR(TRUNC(SYSDATE + LEVEL), 'YYMMDD') AS ymd
    FROM dual
  CONNECT BY LEVEL <= 3
),
cnts AS (
  SELECT b.db_id, b.instance_name,
         d.day_offset,
         COUNT(p.table_name) AS cnt
    FROM apm_db_info b, dba_tab_partitions p, d
   WHERE p.table_owner(+) = USER
     AND p.partition_name(+) LIKE 'P' || d.ymd || LPAD(b.db_id, 3, '0') || '%'
   GROUP BY b.db_id, b.instance_name, d.day_offset
)
SELECT db_id AS "DB ID",
  instance_name AS "INSTANCE NAME",
  TO_CHAR(MAX(CASE WHEN day_offset = 1 THEN NULLIF(cnt, 0) END)) AS "D+1 ({d1})",
  TO_CHAR(MAX(CASE WHEN day_offset = 2 THEN NULLIF(cnt, 0) END)) AS "D+2 ({d2})",
  TO_CHAR(MAX(CASE WHEN day_offset = 3 THEN NULLIF(cnt, 0) END)) AS "D+3 ({d3})",
  CASE
    WHEN COUNT(DISTINCT day_offset) = 3
     AND COUNT(DISTINCT cnt) = 1
     AND MAX(cnt) > 0
  THEN 'OK' ELSE 'CHECK'
  END AS STATUS
FROM cnts
GROUP BY db_id, instance_name
ORDER BY
    DECODE(STATUS, 'CHECK', 1, 'WAITING', 2, 'OK', 3, 4),
    "DB ID" ASC;
"""

_SQL_PARTITION_DROP = """

WITH part_list AS (
    SELECT
        p.table_name,
        p.partition_name,
        TO_NUMBER(SUBSTR(p.partition_name, 8, 3)) AS db_id,
        TRUNC(TO_DATE(SUBSTR(p.partition_name, 2, 6), 'RRMMDD')) AS part_dt
    FROM dba_tab_partitions p
    WHERE p.table_owner = USER
    AND REGEXP_LIKE(p.partition_name, '^P[0-9]{9}$')
),
flagged_agg AS (
    SELECT
        pl.db_id,
        COUNT(*) AS cnt
    FROM part_list pl
    LEFT JOIN apm_db_info d ON pl.db_id = d.db_id
    LEFT JOIN apm_partition_manage m ON m.table_name = pl.table_name AND m.db_id = pl.db_id
    WHERE d.db_id IS NULL
       OR (m.retention_days IS NOT NULL AND (TRUNC(SYSDATE) - pl.part_dt) > m.retention_days)
    GROUP BY pl.db_id
)
SELECT
    COALESCE(d.db_id, f.db_id) AS "DB ID",
    NVL(d.instance_name, '등록되지 않은 DB_ID 입니다.') AS "INSTANCE NAME",
    NVL(f.cnt, 0) AS "OLD PARTITION COUNT",
    CASE
        WHEN d.db_id IS NULL THEN 'CHECK'
        WHEN NVL(f.cnt, 0) > 0 THEN 'CHECK'
        ELSE 'OK'
    END AS "STATUS"
FROM apm_db_info d
FULL OUTER JOIN flagged_agg f ON d.db_id = f.db_id
WHERE COALESCE(d.db_id, f.db_id) IS NOT NULL
ORDER BY
    DECODE(STATUS, 'CHECK', 1, 'WAITING', 2, 'OK', 3, 4),
    "DB ID" ASC;
"""

_SQL_PARTITION_DROP_LIST = """

WITH part_list AS (
    SELECT
        p.table_name,
        p.partition_name,
        TO_NUMBER(SUBSTR(p.partition_name, 8, 3)) AS db_id,
        TRUNC(TO_DATE(SUBSTR(p.partition_name, 2, 6), 'RRMMDD')) AS part_dt
    FROM dba_tab_partitions p
    WHERE p.table_owner = USER
    AND REGEXP_LIKE(p.partition_name, '^P[0-9]{{9}}$')
)
SELECT pl.table_name || ' / ' || pl.partition_name AS "PARTITION TO DROP"
FROM part_list pl
LEFT JOIN apm_db_info d ON pl.db_id = d.db_id
LEFT JOIN apm_partition_manage m ON m.table_name = pl.table_name AND m.db_id = pl.db_id
WHERE pl.db_id = {db_id}
  AND (d.db_id IS NULL
       OR (m.retention_days IS NOT NULL AND (TRUNC(SYSDATE) - pl.part_dt) > m.retention_days))
ORDER BY pl.table_name, pl.partition_name;
"""

_SQL_ORACLE_PARTITION_DROP_EXEC = """

WITH part_list AS (
    SELECT
        p.table_name,
        p.partition_name,
        TO_NUMBER(SUBSTR(p.partition_name, 8, 3)) AS db_id,
        TRUNC(TO_DATE(SUBSTR(p.partition_name, 2, 6), 'RRMMDD')) AS part_dt
    FROM dba_tab_partitions p
    WHERE p.table_owner = USER
    AND REGEXP_LIKE(p.partition_name, '^P[0-9]{{9}}$')
)
SELECT pl.table_name AS "TABLE", pl.partition_name AS "PARTITION"
FROM part_list pl
LEFT JOIN apm_db_info d ON pl.db_id = d.db_id
LEFT JOIN apm_partition_manage m ON m.table_name = pl.table_name AND m.db_id = pl.db_id
WHERE pl.db_id = {db_id}
  AND (d.db_id IS NULL
       OR (m.retention_days IS NOT NULL AND (TRUNC(SYSDATE) - pl.part_dt) > m.retention_days))
ORDER BY pl.table_name, pl.partition_name;
"""

_SQL_SUMMARY_10MIN = """
SET LINESIZE 1000
SET PAGESIZE 100
SET FEEDBACK OFF
SET HEADING ON
COLUMN INSTANCE_NAME FORMAT A20
COLUMN SUMMARY_TYPE  FORMAT A25
COLUMN LAST_SUMMARY  FORMAT A20
COLUMN STATUS        FORMAT A10
COLUMN DELAY_INFO    FORMAT A15

WITH expect AS (
    SELECT TRUNC(SYSDATE,'HH24')
         + ((FLOOR(TO_NUMBER(TO_CHAR(SYSDATE,'MI'))/10)*10)-10)/1440 AS expected_time,
           TRUNC(SYSDATE) AS today FROM dual),
sum_raw AS (
    SELECT a.db_id, a.instance_name, b.summary_type, b.summary_time, e.expected_time,
           CASE WHEN b.summary_time IS NULL THEN 'CHECK'
                WHEN b.summary_time=e.expected_time THEN 'OK'
                WHEN TRUNC(b.summary_time)=e.today THEN 'WAITING'
                ELSE 'CHECK' END AS status
    FROM apm_db_info a
    LEFT JOIN ora_last_summary b ON a.db_id=b.server_id AND b.summary_type LIKE '%10Min%'
    CROSS JOIN expect e)
SELECT
    db_id AS "DB ID",
    instance_name AS INSTANCE_NAME,
    summary_type  AS SUMMARY_TYPE,
    TO_CHAR(summary_time, 'YYYY-MM-DD HH24:MI:SS') AS LAST_SUMMARY,
    status AS STATUS,
    CASE
        WHEN status = 'OK' THEN NULL
        WHEN status = 'WAITING' THEN
            '+' || FLOOR(ROUND((expected_time - summary_time) * 1440) / 60) || 'h '
                || MOD(ROUND((expected_time - summary_time) * 1440), 60) || 'm'
        WHEN status = 'CHECK' AND summary_time IS NOT NULL THEN
            '+' || CEIL(expected_time - summary_time) || 'd'
        ELSE NULL
    END AS DELAY_INFO
FROM sum_raw
ORDER BY
    summary_time ASC NULLS FIRST,
    db_id ASC;
"""

_SQL_SUMMARY_1HOUR = """
SET LINESIZE 1000
SET PAGESIZE 100
SET FEEDBACK OFF
SET HEADING ON
SET SPACE 1
SET TAB OFF
COLUMN INSTANCE_NAME FORMAT A20
COLUMN SUMMARY_TYPE  FORMAT A25
COLUMN LAST_SUMMARY  FORMAT A20
COLUMN STATUS        FORMAT A10
COLUMN DELAY_INFO    FORMAT A15

WITH expect AS (
    SELECT TRUNC(SYSDATE - INTERVAL '1' HOUR, 'HH24') AS expected_time,
           TRUNC(SYSDATE) AS today FROM dual),
sum_raw AS (
    SELECT a.db_id, a.instance_name, b.summary_type, b.summary_time, e.expected_time,
           CASE WHEN b.summary_time IS NULL THEN 'CHECK'
                WHEN b.summary_time = e.expected_time THEN 'OK'
                WHEN TRUNC(b.summary_time) = e.today THEN 'WAITING'
                ELSE 'CHECK' END AS status
    FROM apm_db_info a
    LEFT JOIN ora_last_summary b ON a.db_id = b.server_id AND b.summary_type LIKE '%Daily%'
    CROSS JOIN expect e)
SELECT
    db_id AS "DB ID",
    instance_name AS INSTANCE_NAME,
    summary_type  AS SUMMARY_TYPE,
    TO_CHAR(summary_time, 'YYYY-MM-DD HH24:MI:SS') AS LAST_SUMMARY,
    status AS STATUS,
    CASE
        WHEN status = 'OK' THEN NULL
        WHEN status = 'WAITING' THEN '+' || ROUND((expected_time - summary_time) * 24) || 'h'
        WHEN status = 'CHECK' AND summary_time IS NOT NULL THEN '+' || CEIL(expected_time - summary_time) || 'd'
        ELSE NULL
    END AS DELAY_INFO
FROM sum_raw
ORDER BY
    summary_time ASC NULLS FIRST,
    db_id ASC;
"""

_SQL_SESSION = """
COLUMN INSTANCE_NAME FORMAT A25
COLUMN LAST_TIME     FORMAT A30
WITH seg_pk AS (
  SELECT TO_NUMBER(SUBSTR(s.partition_name, 2, 9)) AS partition_key,
         TO_NUMBER(SUBSTR(s.partition_name, 8, 3)) AS db_id
    FROM dba_segments s
   WHERE s.owner        = USER
     AND s.segment_name = 'ORA_SESSION_LIST_COUNT'
     AND REGEXP_LIKE(s.partition_name, '^P[0-9]{9}$')
),
max_pk AS (
  SELECT db_id, MAX(partition_key) AS max_pk
    FROM seg_pk
   GROUP BY db_id
)
SELECT d.db_id AS "DB ID",
       d.instance_name,
       MAX(s.time) AS last_time
  FROM apm_db_info d
  LEFT JOIN max_pk m ON m.db_id = d.db_id
  LEFT JOIN ora_session_list_count s
         ON s.db_id = d.db_id
        AND s.partition_key = m.max_pk
 GROUP BY d.db_id, d.instance_name
 ORDER BY last_time ASC;
"""

_SQL_ORACLE_QUERY = """
COLUMN INSTANCE_NAME     FORMAT A25
COLUMN PLAN_STATUS       FORMAT A12
COLUMN BIND_STATUS       FORMAT A12
COLUMN TABLESPACE_STATUS FORMAT A18
COLUMN PARAMETER_STATUS  FORMAT A17
WITH base AS (
  SELECT a.db_id, a.instance_name,
         TO_NUMBER(TO_CHAR(TRUNC(SYSDATE-1),'YYMMDD') || LPAD(a.db_id,3,'0')) AS part_key
    FROM apm_db_info a)
SELECT b.db_id AS "DB ID",
       b.instance_name,
       CASE WHEN NVL(lc.download_sql_plan,'N') != 'Y' THEN 'OFF'
            WHEN EXISTS(SELECT 1 FROM ora_sql_plan p
                         WHERE p.db_id=b.db_id AND p.partition_key=b.part_key)
            THEN 'OK' ELSE 'CHECK' END AS plan_status,
       CASE WHEN NVL(lc.download_sql_bind,'N') != 'Y' THEN 'OFF'
            WHEN EXISTS(SELECT 1 FROM ora_bind_value bv
                         WHERE bv.db_id=b.db_id AND bv.partition_key=b.part_key)
            THEN 'OK' ELSE 'CHECK' END AS bind_status,
       CASE WHEN NVL(lc.download_tablespace,'N') != 'Y' THEN 'OFF'
            WHEN EXISTS(SELECT 1 FROM ora_tablespace_info tbs
                         WHERE tbs.db_id=b.db_id AND tbs.partition_key=b.part_key)
            THEN 'OK' ELSE 'CHECK' END AS tablespace_status,
       CASE WHEN NVL(lc.download_parameter,'N') != 'Y' THEN 'OFF'
            WHEN EXISTS(SELECT 1 FROM ora_db_parameter prm
                         WHERE prm.db_id=b.db_id AND prm.partition_key=b.part_key)
            THEN 'OK' ELSE 'CHECK' END AS parameter_status
  FROM base b
  LEFT JOIN ora_lc_config lc ON lc.db_id = b.db_id
  ORDER BY b.db_id;
"""

_SQL_TOP_SEGMENT = """
SET LINESIZE 1000
SET PAGESIZE 100
SET FEEDBACK OFF
COLUMN SCHEMA_NAME FORMAT A15
COLUMN TABLE_NAME FORMAT A30
COLUMN TOTAL_SIZE FORMAT A15
COLUMN TABLE_SIZE FORMAT A15
COLUMN INDEX_SIZE FORMAT A15

SELECT * FROM (
    SELECT
        USER AS SCHEMA_NAME,
        t.segment_name AS TABLE_NAME,
        CASE
            WHEN (t.bytes + NVL(i.idx_bytes, 0)) >= 1073741824 THEN ROUND((t.bytes + NVL(i.idx_bytes, 0))/1073741824, 2) || ' GB'
            WHEN (t.bytes + NVL(i.idx_bytes, 0)) >= 1048576 THEN ROUND((t.bytes + NVL(i.idx_bytes, 0))/1048576, 2) || ' MB'
            ELSE ROUND((t.bytes + NVL(i.idx_bytes, 0))/1024, 2) || ' KB'
        END AS TOTAL_SIZE,
        CASE
            WHEN t.bytes >= 1073741824 THEN ROUND(t.bytes/1073741824, 2) || ' GB'
            WHEN t.bytes >= 1048576 THEN ROUND(t.bytes/1048576, 2) || ' MB'
            ELSE ROUND(t.bytes/1024, 2) || ' KB'
        END AS TABLE_SIZE,
        CASE
            WHEN NVL(i.idx_bytes, 0) >= 1073741824 THEN ROUND(NVL(i.idx_bytes, 0)/1073741824, 2) || ' GB'
            WHEN NVL(i.idx_bytes, 0) >= 1048576 THEN ROUND(NVL(i.idx_bytes, 0)/1048576, 2) || ' MB'
            ELSE ROUND(NVL(i.idx_bytes, 0)/1024, 2) || ' KB'
        END AS INDEX_SIZE
    FROM
        (SELECT segment_name, bytes FROM user_segments WHERE segment_type = 'TABLE') t
    LEFT JOIN
        (SELECT i.table_name, SUM(s.bytes) AS idx_bytes
         FROM user_indexes i
         JOIN user_segments s ON i.index_name = s.segment_name
         GROUP BY i.table_name) i ON t.segment_name = i.table_name
    ORDER BY (t.bytes + NVL(i.idx_bytes, 0)) DESC
) WHERE ROWNUM <= 30;
"""

_SQL_CAPACITY = """
COLUMN TABLESPACE_NAME FORMAT A30
COLUMN USED            FORMAT A12
COLUMN TOTAL           FORMAT A12
COLUMN PERCENT         FORMAT A10
WITH f AS (
  SELECT a.tablespace_name, ROUND(SUM(a.bytes)/1073741824,2) AS free
    FROM dba_free_space a JOIN dba_users b ON a.tablespace_name=b.default_tablespace
   WHERE b.username=USER GROUP BY a.tablespace_name),
t AS (
  SELECT ROUND(SUM(a.bytes)/1073741824,2) AS total
    FROM dba_data_files a JOIN dba_users b ON a.tablespace_name=b.default_tablespace
   WHERE b.username=USER)
SELECT f.tablespace_name,
       (t.total-f.free)||' GB' AS "Used",
       t.total||' GB' AS "Total",
       ROUND(((t.total-f.free)/t.total)*100,2)||'%' AS "PERCENT"
  FROM f, t;
"""

_SQL_ORACLE_TABLESPACE_OVERVIEW = """
WITH f AS (
  SELECT a.tablespace_name, ROUND(SUM(a.bytes)/1073741824,2) AS free_gb
    FROM dba_free_space a JOIN dba_users b ON a.tablespace_name=b.default_tablespace
   WHERE b.username=USER GROUP BY a.tablespace_name),
t AS (
  SELECT ROUND(SUM(a.bytes)/1073741824,2) AS total_gb
    FROM dba_data_files a JOIN dba_users b ON a.tablespace_name=b.default_tablespace
   WHERE b.username=USER)
SELECT TRIM(f.tablespace_name) AS tablespace_name,
       ROUND(t.total_gb-f.free_gb,2) AS used_gb,
       t.total_gb,
       f.free_gb,
       ROUND(((t.total_gb-f.free_gb)/t.total_gb)*100,2) AS pct
  FROM f, t;
"""

_SQL_LICENSE = """
COLUMN DB_ID          FORMAT 999999
COLUMN INSTANCE_NAME  FORMAT A25
COLUMN SID            FORMAT A20
COLUMN RTS_VERSION    FORMAT A20
COLUMN HOST_IP        FORMAT A20
COLUMN OS_TYPE        FORMAT A15
COLUMN "RTS PORT"     FORMAT 99999
COLUMN LSNR_PORT      FORMAT 99999
SELECT db_id, instance_name, sid,
       rts_version,
       host_ip, os_type, port AS "RTS PORT", lsnr_port
  FROM apm_db_info
 ORDER BY db_id;
"""

_SQL_ALERT = """
COLUMN INSTANCE_NAME FORMAT A25
COLUMN ALARM_NAME    FORMAT A45
COLUMN CNT           FORMAT 99999

SELECT
    a.db_id AS "DB ID",
    a.instance_name AS "INSTANCE NAME",
    h.name AS "ALARM NAME",
    COUNT(h.name) AS "COUNT"
FROM apm_db_info a
JOIN ora_alarm_history h ON h.db_id = a.db_id
WHERE h.time > SYSDATE - 30
  AND h.name IN ('RTS Daemon Disconnect', 'RTS Server Down', 'DB Down', 'Listener Stop')
GROUP BY a.db_id, a.instance_name, h.name
ORDER BY "COUNT" DESC, a.db_id ASC;
"""

# ── PostgreSQL SQL constants ─────────────────────────────────────────────────────

_SQL_PG_PARTITION_CREATE_TMPL = """
WITH date_series AS (
    SELECT 1 AS day_offset, to_char(current_date + interval '1 day', 'yymmdd') AS ymd
    UNION ALL SELECT 2, to_char(current_date + interval '2 day', 'yymmdd')
    UNION ALL SELECT 3, to_char(current_date + interval '3 day', 'yymmdd')
),
partition_data AS (
    SELECT
        a.db_id,
        a.instance_name,
        d.day_offset,
        d.ymd,
        COUNT(t.tablename) AS cnt
    FROM apm_db_info a
    CROSS JOIN date_series d
    LEFT JOIN pg_tables t
      ON t.tablename ~ ('_p' || d.ymd || lpad(a.db_id::text, 3, '0') || '$')
     AND t.schemaname = lower(a.instance_name)
    GROUP BY a.db_id, a.instance_name, d.day_offset, d.ymd
)
SELECT
    db_id AS "DB ID",
    instance_name,
    MAX(CASE WHEN day_offset = 1 THEN cnt ELSE 0 END) AS "D+1 ({d1})",
    MAX(CASE WHEN day_offset = 2 THEN cnt ELSE 0 END) AS "D+2 ({d2})",
    MAX(CASE WHEN day_offset = 3 THEN cnt ELSE 0 END) AS "D+3 ({d3})",
    CASE
        WHEN COUNT(DISTINCT day_offset) = 3
         AND COUNT(DISTINCT cnt) = 1
         AND MAX(cnt) > 0
        THEN 'OK' ELSE 'CHECK'
    END AS status
FROM partition_data
GROUP BY db_id, instance_name
ORDER BY
    CASE
        WHEN COUNT(DISTINCT day_offset) = 3
         AND COUNT(DISTINCT cnt) = 1
         AND MAX(cnt) > 0
        THEN 2 ELSE 1
    END,
    db_id ASC;
"""

_SQL_PG_PARTITION_DROP = """

\pset footer off
WITH part_list AS (
    SELECT
        regexp_replace(t.tablename, '_p[0-9]{9}$', '') AS table_name,
        t.tablename AS partition_name,
        t.schemaname AS schema_name,
        substring(t.tablename from '_p[0-9]{6}([0-9]{3})$')::int AS db_id,
        to_date(substring(t.tablename from '_p([0-9]{6})[0-9]{3}$'), 'YYMMDD') AS part_dt
    FROM pg_tables t
    WHERE t.schemaname NOT IN ('pg_catalog','information_schema','public')
      AND t.tablename ~ '_p[0-9]{9}$'
),
flagged_agg AS (
    SELECT pl.db_id, pl.schema_name, COUNT(*) AS cnt
    FROM part_list pl
    LEFT JOIN apm_db_info d
           ON pl.db_id = d.db_id AND pl.schema_name = lower(d.instance_name)
    LEFT JOIN apm_partition_manage m ON upper(m.table_name) = upper(pl.table_name) AND m.db_id = pl.db_id
    WHERE d.db_id IS NULL
       OR (m.retention_days IS NOT NULL AND (current_date - pl.part_dt) > m.retention_days)
    GROUP BY pl.db_id, pl.schema_name
)
SELECT
    COALESCE(d.db_id, a.db_id) AS "DB ID",
    COALESCE(d.instance_name, a.schema_name || ' (등록되지 않은 schema)') AS "INSTANCE NAME",
    COALESCE(a.cnt, 0) AS "OLD PARTITION COUNT",
    CASE
        WHEN d.db_id IS NULL THEN 'CHECK'
        WHEN COALESCE(a.cnt, 0) > 0 THEN 'CHECK'
        ELSE 'OK'
    END AS "STATUS"
FROM apm_db_info d
FULL OUTER JOIN flagged_agg a
            ON d.db_id = a.db_id
           AND lower(d.instance_name) = a.schema_name
WHERE COALESCE(d.db_id, a.db_id) IS NOT NULL
ORDER BY "STATUS" ASC, "DB ID" ASC;
"""

_SQL_PG_PARTITION_DROP_LIST = """

\pset footer off
WITH part_list AS (
    SELECT
        regexp_replace(t.tablename, '_p[0-9]{{9}}$', '') AS table_name,
        t.tablename AS partition_name,
        t.schemaname AS schema_name,
        substring(t.tablename from '_p[0-9]{{6}}([0-9]{{3}})$')::int AS db_id,
        to_date(substring(t.tablename from '_p([0-9]{{6}})[0-9]{{3}}$'), 'YYMMDD') AS part_dt
    FROM pg_tables t
    WHERE t.schemaname NOT IN ('pg_catalog','information_schema','public')
      AND t.tablename ~ '_p[0-9]{{9}}$'
)
SELECT p.table_name || ' / ' || p.partition_name AS "PARTITION TO DROP"
FROM part_list p
LEFT JOIN apm_db_info d ON p.db_id = d.db_id
LEFT JOIN apm_partition_manage m ON upper(m.table_name) = upper(p.table_name) AND m.db_id = p.db_id
WHERE p.db_id = {db_id}
  AND p.schema_name = COALESCE(
        (SELECT lower(instance_name) FROM apm_db_info WHERE db_id = {db_id}),
        p.schema_name)
  AND (d.db_id IS NULL
       OR (m.retention_days IS NOT NULL AND (current_date - p.part_dt) > m.retention_days))
ORDER BY p.table_name, p.partition_name;
"""

_SQL_PG_PARTITION_DROP_EXEC = """

\pset footer off
WITH part_list AS (
    SELECT
        regexp_replace(t.tablename, '_p[0-9]{{9}}$', '') AS table_name,
        t.tablename AS partition_name,
        t.schemaname AS schema_name,
        substring(t.tablename from '_p[0-9]{{6}}([0-9]{{3}})$')::int AS db_id,
        to_date(substring(t.tablename from '_p([0-9]{{6}})[0-9]{{3}}$'), 'YYMMDD') AS part_dt
    FROM pg_tables t
    WHERE t.schemaname NOT IN ('pg_catalog','information_schema','public')
      AND t.tablename ~ '_p[0-9]{{9}}$'
)
SELECT p.schema_name AS "SCHEMA", p.table_name AS "TABLE", p.partition_name AS "PARTITION"
FROM part_list p
LEFT JOIN apm_db_info d ON p.db_id = d.db_id
LEFT JOIN apm_partition_manage m ON upper(m.table_name) = upper(p.table_name) AND m.db_id = p.db_id
WHERE p.db_id = {db_id}
  AND p.schema_name = COALESCE(
        (SELECT lower(instance_name) FROM apm_db_info WHERE db_id = {db_id}),
        p.schema_name)
  AND (d.db_id IS NULL
       OR (m.retention_days IS NOT NULL AND (current_date - p.part_dt) > m.retention_days))
ORDER BY p.table_name, p.partition_name;
"""

_SQL_PG_SUMMARY_10MIN = """
WITH expect AS (
    SELECT date_trunc('hour', localtimestamp)
           + (((extract(minute from localtimestamp)::int / 10) * 10) - 10) * interval '1 minute' AS expected_time,
           current_date AS today
),
sum_raw AS (
    SELECT a.db_id, a.instance_name, b.summary_type, b.summary_time, e.expected_time,
           CASE WHEN b.summary_time IS NULL THEN 'CHECK'
                WHEN date_trunc('minute', b.summary_time) = e.expected_time THEN 'OK'
                WHEN date_trunc('day', b.summary_time) = e.today THEN 'WAITING'
                ELSE 'CHECK' END AS status
    FROM apm_db_info a
    LEFT JOIN ora_last_summary b ON a.db_id = b.server_id AND b.summary_type LIKE '%10Min%'
    CROSS JOIN expect e
)
SELECT
    db_id AS "DB ID",
    instance_name AS INSTANCE_NAME,
    summary_type AS SUMMARY_TYPE,
    to_char(summary_time, 'YYYY-MM-DD HH24:MI:SS') AS LAST_SUMMARY,
    status AS STATUS,
    CASE
        WHEN status = 'OK' THEN NULL
        WHEN status = 'WAITING' THEN
            '+' || (round(extract(epoch from (expected_time - summary_time)) / 60)::int / 60) || 'h '
                || (round(extract(epoch from (expected_time - summary_time)) / 60)::int % 60) || 'm'
        WHEN status = 'CHECK' AND summary_time IS NOT NULL THEN
            '+' || ceil(extract(epoch from (date_trunc('day', expected_time) - date_trunc('day', summary_time))) / 86400.0)::int || 'd'
        ELSE NULL
    END AS DELAY_INFO
  FROM sum_raw
 ORDER BY
  summary_time ASC NULLS FIRST,
  db_id ASC;
"""

_SQL_PG_SUMMARY_1HOUR = """
WITH expect AS (
    SELECT date_trunc('hour', localtimestamp - interval '1 hour') AS expected_time,
           date_trunc('day', localtimestamp) AS today
),
sum_raw AS (
    SELECT a.db_id, a.instance_name, b.summary_type, b.summary_time, e.expected_time,
           CASE WHEN b.summary_time IS NULL THEN 'CHECK'
                WHEN date_trunc('minute', b.summary_time) = date_trunc('minute', e.expected_time) THEN 'OK'
                WHEN date_trunc('day', b.summary_time) = e.today THEN 'WAITING'
                ELSE 'CHECK' END AS status
    FROM apm_db_info a
    LEFT JOIN ora_last_summary b ON a.db_id = b.server_id AND b.summary_type LIKE '%Daily%'
    CROSS JOIN expect e
)
SELECT
    db_id AS "DB ID",
    instance_name AS INSTANCE_NAME,
    summary_type AS SUMMARY_TYPE,
    to_char(summary_time, 'YYYY-MM-DD HH24:MI:SS') AS LAST_SUMMARY,
    status AS STATUS,
    CASE
        WHEN status = 'OK' THEN NULL
        WHEN status = 'WAITING' THEN
            '+' || round(extract(epoch from (expected_time - summary_time)) / 3600)::int || 'h'
        WHEN status = 'CHECK' AND summary_time IS NOT NULL THEN
            '+' || ceil(extract(epoch from (date_trunc('day', expected_time) - date_trunc('day', summary_time))) / 86400.0)::int || 'd'
        ELSE NULL
    END AS DELAY_INFO
  FROM sum_raw
 ORDER BY
  summary_time ASC NULLS FIRST,
  db_id ASC;
"""

_SQL_PG_SESSION = """
SELECT * FROM insp_session_check() ORDER BY last_time ASC;
"""

_SQL_PG_CAPACITY = """
\pset footer off
WITH RawSizes AS (
    SELECT
        n.nspname AS schema_name,
        pg_total_relation_size(c.oid) AS bytes
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind IN ('r','t','m')
      AND n.nspname NOT IN ('pg_catalog','public','pg_toast','information_schema')
)
SELECT
    schema_name,
    round(SUM(bytes) / 1024.0 / 1024.0 / 1024.0, 2) || ' GB' AS size_gb
FROM RawSizes
GROUP BY schema_name
ORDER BY SUM(bytes) DESC;
"""

_SQL_PG_LICENSE = """
\\pset footer off
SELECT db_id, instance_name, sid,
       rts_version,
       host_ip, os_type, port AS "RTS PORT", lsnr_port
FROM apm_db_info
ORDER BY db_id;
"""

_SQL_PG_ALERT = """
SELECT * FROM insp_alarm_history_check() ORDER BY count DESC, db_id ASC;
"""

_SQL_PG_QUERY = """
SELECT * FROM insp_query_check() ORDER BY db_id;
"""

_SQL_PG_AGE = """
\\pset footer off
SELECT datname AS dbname,
       (SELECT to_char(setting::integer,'99,999,999,999') FROM pg_settings WHERE name='autovacuum_freeze_max_age') AS parameter_max_age,
       to_char(age(datfrozenxid),'9,999,999,999') AS max_age,
       to_char(txid_current(),'99,999,999,999') AS current_txid
FROM pg_database
WHERE datname = current_database()
ORDER BY age(datfrozenxid) DESC;
"""

_SQL_PG_TOP_SEGMENT = """
\\pset footer off
SELECT n.nspname AS schema_name,
       c.relname AS table_name,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
       pg_size_pretty(pg_relation_size(c.oid)) AS table_size,
       pg_size_pretty(pg_indexes_size(c.oid)) AS index_size
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r'
ORDER BY c.relpages DESC
LIMIT 30;
"""

_SQL_PG_TEMP_TABLE = """
\\pset footer off
SELECT schemaname AS "SCHEMA", tablename AS "TEMP TABLE"
FROM pg_tables
WHERE tablename LIKE 'tt%'
ORDER BY 1;
"""

_SQL_ORACLE_TEMP_TABLE = """
SELECT USER AS "SCHEMA", table_name AS "TEMP TABLE"
FROM user_tables
WHERE UPPER(table_name) LIKE 'TT%'
ORDER BY table_name;
"""

_SQL_PG_VACUUM_CHECK = """
\\pset footer off
WITH threshold_calc AS (
  SELECT schemaname, relname, n_live_tup, n_dead_tup, autovacuum_count, last_autovacuum,
         (current_setting('autovacuum_vacuum_threshold')::int
          + current_setting('autovacuum_vacuum_scale_factor')::numeric * n_live_tup) AS vacuum_threshold
  FROM pg_stat_user_tables
),
exceed AS (
  SELECT * FROM threshold_calc WHERE n_dead_tup > vacuum_threshold
),
not_vacuumed AS (
  SELECT * FROM exceed WHERE last_autovacuum IS NULL OR last_autovacuum < now() - interval '3 days'
)
SELECT schemaname AS schema, relname AS table_name, n_dead_tup AS dead_tuples,
       round(vacuum_threshold) AS vacuum_threshold, last_autovacuum
FROM not_vacuumed
ORDER BY (n_dead_tup - vacuum_threshold) DESC;
"""


def _get_sql(key):
    from datetime import datetime, timedelta

    repo = load_service_config().get("repository", {})
    db_type = repo.get("db_type", "Oracle").lower()
    pg = "postgres" in db_type

    d1 = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    d2 = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
    d3 = (datetime.now() + timedelta(days=3)).strftime('%Y%m%d')

    pg_create  = _SQL_PG_PARTITION_CREATE_TMPL.format(d1=d1, d2=d2, d3=d3)
    ora_create = _SQL_ORACLE_PARTITION_CREATE_TMPL.format(d1=d1, d2=d2, d3=d3)

    mapping = {
        "partition_create": pg_create if pg else ora_create,
        "partition_drop":   _SQL_PG_PARTITION_DROP      if pg else _SQL_PARTITION_DROP,
        "summary_10min":    _SQL_PG_SUMMARY_10MIN       if pg else _SQL_SUMMARY_10MIN,
        "summary_1hour":    _SQL_PG_SUMMARY_1HOUR       if pg else _SQL_SUMMARY_1HOUR,
        "session":          _SQL_PG_SESSION             if pg else _SQL_SESSION,
        "capacity":         _SQL_PG_CAPACITY            if pg else _SQL_CAPACITY,
        "license":          _SQL_PG_LICENSE             if pg else _SQL_LICENSE,
        "alert":            _SQL_PG_ALERT               if pg else _SQL_ALERT,
        "query":            _SQL_PG_QUERY               if pg else _SQL_ORACLE_QUERY,
        "vacuum":           _SQL_PG_VACUUM_CHECK        if pg else "",
        "age":              _SQL_PG_AGE                 if pg else "",
        "top_segment":      _SQL_PG_TOP_SEGMENT         if pg else _SQL_TOP_SEGMENT,
        "temp_table":       _SQL_PG_TEMP_TABLE          if pg else _SQL_ORACLE_TEMP_TABLE,
    }
    return mapping.get(key, "")
