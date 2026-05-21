# -*- coding: utf-8 -*-
"""
Oracle INSP_ table DDL, INSERT, and cleanup operations.
All INSP_ objects are independent from existing MaxGauge objects.
"""
import os
import sys

# ── bundled drivers (Labs/drivers, Labs 공용) ─────────────────────────────────
import glob as _glob
_LABS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_py3_sites = _glob.glob(
    os.path.join(_LABS_DIR, 'drivers', 'python3', 'lib', 'python3.*', 'site-packages'))
if _py3_sites and _py3_sites[0] not in sys.path:
    sys.path.insert(0, _py3_sites[0])
del _glob, _py3_sites, _LABS_DIR

try:
    import oracledb as _oracledb
except Exception:
    _oracledb = None

from service_config import load_service_config


def _db_cfg():
    return load_service_config().get("repository", {})


def _insp_connect():
    """Connect to Oracle Repository DB."""
    if not _oracledb:
        return None
    repo = _db_cfg()
    return _oracledb.connect(
        user=repo.get("user", ""),
        password=repo.get("password", ""),
        host=repo.get("ip", ""),
        port=int(repo.get("port", "1521") or "1521"),
        service_name=repo.get("sid", "")
    )


# ── DDL ──────────────────────────────────────────────────────────────────────────

_TABLES_DDL = [
    # 1. OS History (CPU / Memory, 1min)
    """CREATE TABLE INSP_OS_HISTORY (
        COLLECTED_AT  TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
        CPU_PERCENT   NUMBER(5,1),
        CPU_USER      NUMBER(5,1),
        CPU_SYSTEM    NUMBER(5,1),
        CPU_IOWAIT    NUMBER(5,1),
        MEM_TOTAL_GB  NUMBER(10,1),
        MEM_USED_GB   NUMBER(10,1),
        MEM_FREE_GB   NUMBER(10,1),
        MEM_PERCENT   NUMBER(5,1)
    ) PARTITION BY RANGE (COLLECTED_AT)
    INTERVAL (NUMTODSINTERVAL(1,'DAY'))
    (PARTITION INSP_OS_P_INIT VALUES LESS THAN (TIMESTAMP '2025-01-01 00:00:00'))""",

    # 2. Tablespace History (daily 23:50)
    """CREATE TABLE INSP_TBS_HISTORY (
        COLLECTED_AT    TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
        TBS_NAME        VARCHAR2(128),
        USED_GB         NUMBER(12,2),
        TOTAL_GB        NUMBER(12,2),
        FREE_GB         NUMBER(12,2),
        USED_PERCENT    NUMBER(5,2),
        STATUS          VARCHAR2(20)
    ) PARTITION BY RANGE (COLLECTED_AT)
    INTERVAL (NUMTODSINTERVAL(1,'DAY'))
    (PARTITION INSP_TBS_P_INIT VALUES LESS THAN (TIMESTAMP '2025-01-01 00:00:00'))""",

    # 3. Service History (hourly)
    """CREATE TABLE INSP_SERVICE_HISTORY (
        COLLECTED_AT    TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
        SERVICE_NAME    VARCHAR2(128),
        STATUS          VARCHAR2(20),
        PID             VARCHAR2(20),
        PORT            VARCHAR2(10),
        UPTIME          VARCHAR2(50)
    ) PARTITION BY RANGE (COLLECTED_AT)
    INTERVAL (NUMTODSINTERVAL(1,'DAY'))
    (PARTITION INSP_SVC_P_INIT VALUES LESS THAN (TIMESTAMP '2025-01-01 00:00:00'))""",

    # 4. Partition History (daily 23:50, with log path),

    # 5.4 Heap History (1min, from DGS log DG MANAGER)
    """CREATE TABLE INSP_HEAP_HISTORY (
        COLLECTED_AT    TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
        SERVICE_NAME    VARCHAR2(128),
        HEAP_USED_MB    NUMBER,
        HEAP_ALLOC_MB   NUMBER,
        HEAP_MAX_MB     NUMBER
    ) PARTITION BY RANGE (COLLECTED_AT)
    INTERVAL (NUMTODSINTERVAL(1,'DAY'))
    (PARTITION INSP_HEAP_P_INIT VALUES LESS THAN (TIMESTAMP '2025-01-01 00:00:00'))""",

    # 5.5 Qcnt History (1min, from DGS log)
    """CREATE TABLE INSP_QCNT_HISTORY (
        COLLECTED_AT    TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
        SERVICE_NAME    VARCHAR2(128),
        ACT             NUMBER,
        TOTAL           NUMBER,
        MAX_CONN        NUMBER,
        QCNT            NUMBER
    ) PARTITION BY RANGE (COLLECTED_AT)
    INTERVAL (NUMTODSINTERVAL(1,'DAY'))
    (PARTITION INSP_QCNT_P_INIT VALUES LESS THAN (TIMESTAMP '2025-01-01 00:00:00'))""",

    # 5. Summary History (10min / 1hour)
    """CREATE TABLE INSP_SUMMARY_HISTORY (
        COLLECTED_AT    TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
        CHECK_TYPE      VARCHAR2(10),
        DB_ID           NUMBER,
        INSTANCE_NAME   VARCHAR2(128),
        SUMMARY_TYPE    VARCHAR2(128),
        STATUS          VARCHAR2(20),
        LAST_SUMMARY    VARCHAR2(30),
        DELAY_INFO      VARCHAR2(30)
    ) PARTITION BY RANGE (COLLECTED_AT)
    INTERVAL (NUMTODSINTERVAL(1,'DAY'))
    (PARTITION INSP_SUM_P_INIT VALUES LESS THAN (TIMESTAMP '2025-01-01 00:00:00'))""",

    # 6. Process Snapshot History (1min, top 20 by max(cpu, mem))
    # 추후 'Inspector History > CPU/Memory 화면에서 시점 클릭 시 하단 프로세스 목록'
    # 표출 목적. 현재는 수집만, 화면/API 없음.
    """CREATE TABLE INSP_PROC_HISTORY (
        COLLECTED_AT    TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
        PID             NUMBER(10) NOT NULL,
        OS_USER         VARCHAR2(64),
        CPU_PCT         NUMBER(5,1) DEFAULT 0,
        MEM_PCT         NUMBER(5,1) DEFAULT 0,
        RSS_KB          NUMBER(15)  DEFAULT 0,
        VSZ_KB          NUMBER(15)  DEFAULT 0,
        THREADS         NUMBER(10)  DEFAULT 0,
        ETIME           VARCHAR2(32),
        COMM            VARCHAR2(64),
        ARGS            VARCHAR2(256)
    ) PARTITION BY RANGE (COLLECTED_AT)
    INTERVAL (NUMTODSINTERVAL(1,'DAY'))
    (PARTITION INSP_PROC_P_INIT VALUES LESS THAN (TIMESTAMP '2025-01-01 00:00:00'))""",
]

_INDEXES_DDL = [
    "CREATE INDEX INSP_OS_IDX_AT ON INSP_OS_HISTORY (COLLECTED_AT) LOCAL",
    "CREATE INDEX INSP_TBS_IDX_AT ON INSP_TBS_HISTORY (COLLECTED_AT) LOCAL",
    "CREATE INDEX INSP_SVC_IDX_AT ON INSP_SERVICE_HISTORY (COLLECTED_AT) LOCAL",
    "CREATE INDEX INSP_HEAP_IDX_AT ON INSP_HEAP_HISTORY (COLLECTED_AT) LOCAL",
    "CREATE INDEX INSP_HEAP_IDX_SVC ON INSP_HEAP_HISTORY (SERVICE_NAME, COLLECTED_AT) LOCAL",
    "CREATE INDEX INSP_QCNT_IDX_AT ON INSP_QCNT_HISTORY (COLLECTED_AT) LOCAL",
    "CREATE INDEX INSP_QCNT_IDX_SVC ON INSP_QCNT_HISTORY (SERVICE_NAME, COLLECTED_AT) LOCAL",
    "CREATE INDEX INSP_SUM_IDX_AT ON INSP_SUMMARY_HISTORY (COLLECTED_AT, CHECK_TYPE) LOCAL",
    "CREATE INDEX INSP_SUM_IDX_DBID ON INSP_SUMMARY_HISTORY (DB_ID, COLLECTED_AT) LOCAL",
    "CREATE INDEX INSP_PROC_IDX_AT ON INSP_PROC_HISTORY (COLLECTED_AT) LOCAL",
]


_ALL_INSP_TABLES = [
    'INSP_OS_HISTORY', 'INSP_TBS_HISTORY', 'INSP_SERVICE_HISTORY',
    'INSP_HEAP_HISTORY', 'INSP_QCNT_HISTORY',
    'INSP_SUMMARY_HISTORY', 'INSP_PROC_HISTORY',
]

def insp_check_each_table():
    """Return dict {table_name: True/False} for each INSP table."""
    result = {t: False for t in _ALL_INSP_TABLES}
    try:
        conn = _insp_connect()
        if not conn:
            return result
        cur = conn.cursor()
        cur.execute("SELECT table_name FROM user_tables WHERE table_name LIKE 'INSP_%'")
        for r in cur.fetchall():
            if r[0] in result:
                result[r[0]] = True
        cur.close(); conn.close()
    except Exception:
        pass
    return result


def insp_create_one_table(table_name):
    """Create a single INSP table + its indexes. Returns (ok, message)."""
    table_name = table_name.upper()
    if table_name not in _ALL_INSP_TABLES:
        return False, "Unknown table: " + table_name
    try:
        conn = _insp_connect()
        if not conn:
            return False, "Cannot connect to Oracle."
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM user_tables WHERE table_name=:1", (table_name,))
        if cur.fetchone():
            cur.close(); conn.close()
            return False, table_name + " already exists."
        # Find DDL
        ddl_found = None
        for ddl in _TABLES_DDL:
            if table_name in ddl.upper():
                ddl_found = ddl; break
        if not ddl_found:
            cur.close(); conn.close()
            return False, "DDL not found for " + table_name
        cur.execute(ddl_found)
        # Create related indexes
        for idx_ddl in _INDEXES_DDL:
            if table_name in idx_ddl.upper():
                try:
                    cur.execute(idx_ddl)
                except Exception:
                    pass
        conn.commit()
        cur.close(); conn.close()
        return True, table_name + " created successfully."
    except Exception as e:
        return False, "Error: " + str(e)


def insp_tables_exist():
    """Check if INSP_ tables already exist."""
    try:
        conn = _insp_connect()
        if not conn:
            return False
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM user_tables WHERE table_name LIKE 'INSP_%'")
        cnt = cur.fetchone()[0]
        cur.close()
        conn.close()
        return cnt >= 7
    except Exception:
        return False


def insp_create_tables():
    """Create all INSP_ tables and indexes. Returns (ok, message)."""
    try:
        conn = _insp_connect()
        if not conn:
            return False, "Cannot connect to Oracle."
        cur = conn.cursor()

        # Check if already exist
        cur.execute("SELECT COUNT(*) FROM user_tables WHERE table_name LIKE 'INSP_%'")
        if cur.fetchone()[0] > 0:
            cur.close()
            conn.close()
            return False, "INSP_ tables already exist."

        created = []
        for ddl in _TABLES_DDL:
            tbl_name = ddl.split("TABLE")[1].split("(")[0].strip()
            cur.execute(ddl)
            created.append(tbl_name)

        for ddl in _INDEXES_DDL:
            try:
                cur.execute(ddl)
            except Exception:
                pass  # index may fail if table empty, skip

        conn.commit()
        cur.close()
        conn.close()
        return True, "Created %d tables: %s" % (len(created), ", ".join(created))
    except Exception as e:
        return False, "Error: " + str(e)


def insp_drop_tables():
    """Drop all INSP_ tables. Returns (ok, message)."""
    try:
        conn = _insp_connect()
        if not conn:
            return False, "Cannot connect to Oracle."
        cur = conn.cursor()
        cur.execute("SELECT table_name FROM user_tables WHERE table_name LIKE 'INSP_%' ORDER BY table_name")
        tables = [r[0] for r in cur.fetchall()]
        if not tables:
            cur.close()
            conn.close()
            return False, "No INSP_ tables found."
        for t in tables:
            cur.execute("DROP TABLE %s PURGE" % t)
        conn.commit()
        cur.close()
        conn.close()
        return True, "Dropped %d tables: %s" % (len(tables), ", ".join(tables))
    except Exception as e:
        return False, "Error: " + str(e)


# ── INSERT helpers ───────────────────────────────────────────────────────────────

def insp_insert_os(cpu, mem):
    """Insert one OS history row."""
    try:
        conn = _insp_connect()
        if not conn:
            return
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO INSP_OS_HISTORY "
            "(COLLECTED_AT, CPU_PERCENT, CPU_USER, CPU_SYSTEM, CPU_IOWAIT, "
            "MEM_TOTAL_GB, MEM_USED_GB, MEM_FREE_GB, MEM_PERCENT) "
            "VALUES (SYSTIMESTAMP, :1, :2, :3, :4, :5, :6, :7, :8)",
            (cpu["percent"], cpu["user"], cpu["system"], cpu["iowait"],
             mem["total_gb"], mem["used_gb"], mem["free_gb"], mem["percent"])
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


def insp_insert_tbs(tbs_list):
    """Insert tablespace history rows. tbs_list = list of dicts from _tablespace_for_overview."""
    try:
        conn = _insp_connect()
        if not conn:
            return
        cur = conn.cursor()
        for ts in tbs_list:
            cur.execute(
                "INSERT INTO INSP_TBS_HISTORY "
                "(COLLECTED_AT, TBS_NAME, USED_GB, TOTAL_GB, FREE_GB, USED_PERCENT, STATUS) "
                "VALUES (SYSTIMESTAMP, :1, :2, :3, :4, :5, :6)",
                (ts["name"], ts["used_gb"], ts["total_gb"], ts["free_gb"],
                 ts["percent"], ts["status"])
            )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


def insp_insert_services(rows):
    """Insert service history rows. rows = list of (name, status, pid, port, uptime)."""
    try:
        conn = _insp_connect()
        if not conn:
            return
        cur = conn.cursor()
        for name, status, pid, port, uptime in rows:
            cur.execute(
                "INSERT INTO INSP_SERVICE_HISTORY "
                "(COLLECTED_AT, SERVICE_NAME, STATUS, PID, PORT, UPTIME) "
                "VALUES (SYSTIMESTAMP, :1, :2, :3, :4, :5)",
                (name, status, pid, port, uptime)
            )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


def insp_insert_heap(rows):
    """Insert heap history rows.
    rows = list of (service_name, collected_at_str, used, alloc, max_mb).
    collected_at_str: 'YYYY-MM-DD HH:MM:SS' from log timestamp.
    """
    try:
        conn = _insp_connect()
        if not conn:
            return
        cur = conn.cursor()
        for svc, collected_at, used, alloc, max_mb in rows:
            cur.execute(
                "INSERT INTO INSP_HEAP_HISTORY "
                "(COLLECTED_AT, SERVICE_NAME, HEAP_USED_MB, HEAP_ALLOC_MB, HEAP_MAX_MB) "
                "VALUES (TO_TIMESTAMP(:1,'YYYY-MM-DD HH24:MI:SS'), :2, :3, :4, :5)",
                (collected_at, svc, used, alloc, max_mb)
            )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


def insp_insert_qcnt(rows):
    """Insert qcnt history rows.
    rows = list of (service_name, collected_at_str, act, total, max_conn, qcnt).
    collected_at_str: 'YYYY-MM-DD HH:MM:SS' from log timestamp.
    """
    try:
        conn = _insp_connect()
        if not conn:
            return
        cur = conn.cursor()
        for svc, collected_at, act, total, max_conn, qcnt in rows:
            cur.execute(
                "INSERT INTO INSP_QCNT_HISTORY "
                "(COLLECTED_AT, SERVICE_NAME, ACT, TOTAL, MAX_CONN, QCNT) "
                "VALUES (TO_TIMESTAMP(:1,'YYYY-MM-DD HH24:MI:SS'), :2, :3, :4, :5, :6)",
                (collected_at, svc, act, total, max_conn, qcnt)
            )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass



def insp_insert_proc(rows):
    """Insert process snapshot rows. rows = list of dict from system_utils._proc_snapshot_top.
    collected_at 은 현재 시각으로 단일 timestamp 사용 (분 단위 그룹핑 용)."""
    if not rows:
        return
    try:
        conn = _insp_connect()
        if not conn:
            return
        cur = conn.cursor()
        # 분 단위로 collected_at 통일 — 화면에서 시점 클릭 시 같은 분의 행이 묶임
        from datetime import datetime as _dt
        ts = _dt.now().strftime('%Y-%m-%d %H:%M:00')
        params = [
            (ts, r['pid'], r.get('user', ''), r['cpu_pct'], r['mem_pct'],
             r['rss_kb'], r['vsz_kb'], r['threads'], r.get('etime', ''),
             r.get('comm', ''), r.get('args', ''))
            for r in rows
        ]
        cur.executemany(
            "INSERT INTO INSP_PROC_HISTORY "
            "(COLLECTED_AT, PID, OS_USER, CPU_PCT, MEM_PCT, RSS_KB, VSZ_KB, "
            " THREADS, ETIME, COMM, ARGS) "
            "VALUES (TO_TIMESTAMP(:1,'YYYY-MM-DD HH24:MI:SS'), :2, :3, :4, :5, "
            " :6, :7, :8, :9, :10, :11)",
            params
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


def insp_insert_summary(check_type, rows_data):
    """Insert summary history rows.
    rows_data = list of (db_id, instance, stype, status, last_summary, delay)."""
    try:
        conn = _insp_connect()
        if not conn:
            return
        cur = conn.cursor()
        for db_id, inst, stype, status, last_sum, delay in rows_data:
            cur.execute(
                "INSERT INTO INSP_SUMMARY_HISTORY "
                "(COLLECTED_AT, CHECK_TYPE, DB_ID, INSTANCE_NAME, SUMMARY_TYPE, "
                "STATUS, LAST_SUMMARY, DELAY_INFO) "
                "VALUES (SYSTIMESTAMP, :1, :2, :3, :4, :5, :6, :7)",
                (check_type, db_id, inst, stype, status, last_sum, delay)
            )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


# ── Retention cleanup ────────────────────────────────────────────────────────────

def insp_cleanup_old_partitions(retention_days):
    """Drop partitions older than retention_days from all INSP_ tables."""
    try:
        conn = _insp_connect()
        if not conn:
            return
        cur = conn.cursor()
        cur.execute(
            "SELECT table_name, partition_name, high_value "
            "FROM user_tab_partitions "
            "WHERE table_name LIKE 'INSP_%' "
            "AND partition_name NOT LIKE '%P_INIT%' "
            "ORDER BY table_name, partition_name"
        )
        partitions = cur.fetchall()

        cutoff_sql = "SYSTIMESTAMP - INTERVAL '%d' DAY" % retention_days
        for tbl, pname, high_val in partitions:
            try:
                cur.execute(
                    "SELECT CASE WHEN %s < %s THEN 1 ELSE 0 END FROM dual"
                    % (high_val, cutoff_sql)
                )
                is_old = cur.fetchone()[0]
                if is_old == 1:
                    cur.execute("ALTER TABLE %s DROP PARTITION %s" % (tbl, pname))
            except Exception:
                pass

        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


# ── Monthly Summary (non-partitioned) ───────────────────────────────────────────

_MONTHLY_DDL = """CREATE TABLE INSP_MONTHLY_SUMMARY (
    YEAR_MONTH    CHAR(7)        NOT NULL,
    CPU_AVG       NUMBER(5,1),
    MEM_AVG       NUMBER(5,1),
    MEM_USED_GB   NUMBER(10,1),
    MEM_TOTAL_GB  NUMBER(10,1),
    DISK_AVG      NUMBER(5,1),
    DISK_USED_GB  NUMBER(12,1),
    DISK_TOTAL_GB NUMBER(12,1),
    SAMPLE_COUNT  NUMBER,
    CREATED_AT    TIMESTAMP      DEFAULT SYSTIMESTAMP,
    CONSTRAINT INSP_MONTHLY_PK PRIMARY KEY (YEAR_MONTH)
)"""


def insp_create_monthly_table():
    """Create INSP_MONTHLY_SUMMARY if it does not exist. Returns (ok, message)."""
    try:
        conn = _insp_connect()
        if not conn:
            return False, "Cannot connect to Oracle."
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM user_tables WHERE table_name='INSP_MONTHLY_SUMMARY'")
        if cur.fetchone()[0] > 0:
            cur.close(); conn.close()
            return False, "INSP_MONTHLY_SUMMARY already exists."
        cur.execute(_MONTHLY_DDL)
        conn.commit()
        cur.close(); conn.close()
        return True, "INSP_MONTHLY_SUMMARY created."
    except Exception as e:
        return False, "Error: " + str(e)


def insp_upsert_monthly_summary(year_month, cpu_avg, mem_avg,
                                 mem_used_gb, mem_total_gb,
                                 disk_avg, disk_used_gb, disk_total_gb,
                                 sample_count):
    """MERGE one row into INSP_MONTHLY_SUMMARY."""
    try:
        conn = _insp_connect()
        if not conn:
            return
        cur = conn.cursor()
        cur.execute(
            "MERGE INTO INSP_MONTHLY_SUMMARY t "
            "USING (SELECT :1 AS ym FROM dual) s ON (t.YEAR_MONTH = s.ym) "
            "WHEN MATCHED THEN UPDATE SET "
            "  CPU_AVG=:2, MEM_AVG=:3, MEM_USED_GB=:4, MEM_TOTAL_GB=:5, "
            "  DISK_AVG=:6, DISK_USED_GB=:7, DISK_TOTAL_GB=:8, "
            "  SAMPLE_COUNT=:9, CREATED_AT=SYSTIMESTAMP "
            "WHEN NOT MATCHED THEN INSERT "
            "(YEAR_MONTH,CPU_AVG,MEM_AVG,MEM_USED_GB,MEM_TOTAL_GB,"
            " DISK_AVG,DISK_USED_GB,DISK_TOTAL_GB,SAMPLE_COUNT,CREATED_AT) "
            "VALUES (:1,:2,:3,:4,:5,:6,:7,:8,:9,SYSTIMESTAMP)",
            (year_month, cpu_avg, mem_avg, mem_used_gb, mem_total_gb,
             disk_avg, disk_used_gb, disk_total_gb, sample_count)
        )
        conn.commit()
        cur.close(); conn.close()
    except Exception:
        pass


def insp_query_monthly_summary(year):
    """Return {month_int: {cpu_avg, mem_avg, ...}} for the given year."""
    result = {}
    try:
        conn = _insp_connect()
        if not conn:
            return result
        cur = conn.cursor()
        cur.execute(
            "SELECT YEAR_MONTH, CPU_AVG, MEM_AVG, MEM_USED_GB, MEM_TOTAL_GB, "
            "       DISK_AVG, DISK_USED_GB, DISK_TOTAL_GB "
            "FROM INSP_MONTHLY_SUMMARY "
            "WHERE YEAR_MONTH LIKE :1 ORDER BY YEAR_MONTH",
            (str(year) + '-%',)
        )
        for row in cur.fetchall():
            ym = str(row[0]).strip()
            try:
                month = int(ym.split('-')[1])
            except Exception:
                continue
            result[month] = {
                'cpu_avg':       float(row[1]) if row[1] is not None else None,
                'mem_avg':       float(row[2]) if row[2] is not None else None,
                'mem_used_gb':   float(row[3]) if row[3] is not None else None,
                'mem_total_gb':  float(row[4]) if row[4] is not None else None,
                'disk_avg':      float(row[5]) if row[5] is not None else None,
                'disk_used_gb':  float(row[6]) if row[6] is not None else None,
                'disk_total_gb': float(row[7]) if row[7] is not None else None,
            }
        cur.close(); conn.close()
    except Exception:
        pass
    return result
