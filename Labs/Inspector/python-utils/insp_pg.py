# -*- coding: utf-8 -*-
"""
PostgreSQL INSP_ table DDL, INSERT, partition management, and cleanup.
PG equivalent of insp_oracle.py — uses Range Partitioning with manual partition creation.
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
    import psycopg2 as _psycopg2
except Exception:
    _psycopg2 = None

from service_config import load_service_config


def _load_insp_pg_db():
    """Get PG DB connection info: IP/port/user/password from service_config, database from insp_config."""
    import json as _json
    repo = load_service_config().get("repository", {})
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "insp_config.json")
    try:
        with open(cfg_path, "r") as f:
            cfg = _json.load(f)
        pg_db = cfg.get("pg_db", {})
    except Exception:
        pg_db = {}
    return {
        "ip": repo.get("ip", "127.0.0.1"),
        "port": repo.get("port", "5432"),
        "user": repo.get("user", "postgres"),
        "password": repo.get("password", "postgres"),
        "sid": pg_db.get("sid", "") or repo.get("sid", ""),
    }


def insp_pg_create_schema():
    """Create the INSP schema if not exists. Returns (ok, message)."""
    try:
        conn = _insp_pg_connect()
        if not conn:
            return False, "Cannot connect to PostgreSQL."
        conn.autocommit = True
        cur = conn.cursor()
        schema = _get_insp_schema()
        cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = %s", (schema,))
        if cur.fetchone():
            cur.close(); conn.close()
            return True, "Schema '%s' already exists." % schema
        cur.execute("CREATE SCHEMA %s" % schema)
        cur.close(); conn.close()
        return True, "Schema '%s' created." % schema
    except Exception as e:
        return False, "Error: " + str(e)


def _get_insp_schema():
    """INSP schema name (fixed)."""
    return "insp"


def _insp_pg_connect():
    """Connect to PostgreSQL using insp_config.json pg_db settings."""
    if not _psycopg2:
        return None
    pg = _load_insp_pg_db()
    conn = _psycopg2.connect(
        host=pg.get("ip", "127.0.0.1"),
        port=int(pg.get("port", "5432") or "5432"),
        user=pg.get("user", "postgres"),
        password=pg.get("password", "postgres"),
        dbname=pg.get("sid", "MI")
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET search_path TO %s, public" % _get_insp_schema())
    cur.close()
    conn.autocommit = False
    return conn


# ── DDL ──────────────────────────────────────────────────────────────────────────

_TABLES_DDL = [
    # 1. OS History (CPU / Memory, 1min)
    """CREATE TABLE insp_os_history (
        collected_at  TIMESTAMP DEFAULT NOW() NOT NULL,
        cpu_percent   NUMERIC(5,1),
        cpu_user      NUMERIC(5,1),
        cpu_system    NUMERIC(5,1),
        cpu_iowait    NUMERIC(5,1),
        mem_total_gb  NUMERIC(10,1),
        mem_used_gb   NUMERIC(10,1),
        mem_free_gb   NUMERIC(10,1),
        mem_percent   NUMERIC(5,1)
    ) PARTITION BY RANGE (collected_at)""",

    # 2. Tablespace / Disk History (daily 23:50)
    """CREATE TABLE insp_tbs_history (
        collected_at    TIMESTAMP DEFAULT NOW() NOT NULL,
        tbs_name        VARCHAR(128),
        used_gb         NUMERIC(12,2),
        total_gb        NUMERIC(12,2),
        free_gb         NUMERIC(12,2),
        used_percent    NUMERIC(5,2),
        status          VARCHAR(20)
    ) PARTITION BY RANGE (collected_at)""",

    # 3. Service History (hourly)
    """CREATE TABLE insp_service_history (
        collected_at    TIMESTAMP DEFAULT NOW() NOT NULL,
        service_name    VARCHAR(128),
        status          VARCHAR(20),
        pid             VARCHAR(20),
        port            VARCHAR(10),
        uptime          VARCHAR(50)
    ) PARTITION BY RANGE (collected_at)""",

    # 4. Partition History (daily 23:50),

    # 5.4 Heap History (1min, from DGS log DG MANAGER)
    """CREATE TABLE insp_heap_history (
        collected_at    TIMESTAMP DEFAULT NOW() NOT NULL,
        service_name    VARCHAR(128),
        heap_used_mb    INTEGER,
        heap_alloc_mb   INTEGER,
        heap_max_mb     INTEGER
    ) PARTITION BY RANGE (collected_at)""",

    # 5.5 Qcnt History (1min, from DGS log)
    """CREATE TABLE insp_qcnt_history (
        collected_at    TIMESTAMP DEFAULT NOW() NOT NULL,
        service_name    VARCHAR(128),
        act             INTEGER,
        total           INTEGER,
        max_conn        INTEGER,
        qcnt            INTEGER
    ) PARTITION BY RANGE (collected_at)""",

    # 5. Summary History (10min / 1hour)
    """CREATE TABLE insp_summary_history (
        collected_at    TIMESTAMP DEFAULT NOW() NOT NULL,
        check_type      VARCHAR(10),
        db_id           INTEGER,
        instance_name   VARCHAR(128),
        summary_type    VARCHAR(128),
        status          VARCHAR(20),
        last_summary    VARCHAR(30),
        delay_info      VARCHAR(30)
    ) PARTITION BY RANGE (collected_at)""",

    # 6. Process Snapshot History (1min, top 20 by max(cpu, mem))
    # 추후 'Inspector History > CPU/Memory 화면에서 시점 클릭 시 하단 프로세스 목록'
    # 표출 목적. 현재는 수집만, 화면/API 없음.
    """CREATE TABLE insp_proc_history (
        collected_at    TIMESTAMP DEFAULT NOW() NOT NULL,
        pid             BIGINT NOT NULL,
        os_user         VARCHAR(64),
        cpu_pct         NUMERIC(5,1) DEFAULT 0,
        mem_pct         NUMERIC(5,1) DEFAULT 0,
        rss_kb          BIGINT DEFAULT 0,
        vsz_kb          BIGINT DEFAULT 0,
        threads         INTEGER DEFAULT 0,
        etime           VARCHAR(32),
        comm            VARCHAR(64),
        args            VARCHAR(256)
    ) PARTITION BY RANGE (collected_at)""",
]

_PARENT_TABLES = [
    'insp_os_history',
    'insp_tbs_history',
    'insp_service_history',

    'insp_heap_history',
    'insp_qcnt_history',
    'insp_summary_history',
    'insp_proc_history',
]

_INDEXES_DDL = [
    "CREATE INDEX insp_os_idx_at ON insp_os_history (collected_at)",
    "CREATE INDEX insp_tbs_idx_at ON insp_tbs_history (collected_at)",
    "CREATE INDEX insp_svc_idx_at ON insp_service_history (collected_at)",
    "CREATE INDEX insp_heap_idx_at ON insp_heap_history (collected_at)",
    "CREATE INDEX insp_heap_idx_svc ON insp_heap_history (service_name, collected_at)",
    "CREATE INDEX insp_qcnt_idx_at ON insp_qcnt_history (collected_at)",
    "CREATE INDEX insp_qcnt_idx_svc ON insp_qcnt_history (service_name, collected_at)",
    "CREATE INDEX insp_sum_idx_at ON insp_summary_history (collected_at, check_type)",
    "CREATE INDEX insp_sum_idx_dbid ON insp_summary_history (db_id, collected_at)",
    "CREATE INDEX insp_proc_idx_at ON insp_proc_history (collected_at)",
]


def insp_pg_check_each_table():
    """Return dict {table_name: True/False} for each INSP table."""
    result = {t: False for t in _PARENT_TABLES}
    try:
        conn = _insp_pg_connect()
        if not conn:
            return result
        cur = conn.cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema=%s AND table_name LIKE 'insp_%%'",
            (_get_insp_schema(),)
        )
        for r in cur.fetchall():
            if r[0] in result:
                result[r[0]] = True
        cur.close(); conn.close()
    except Exception:
        pass
    return result


def insp_pg_create_one_table(table_name):
    """Create a single INSP table + its indexes + partitions. Returns (ok, message)."""
    from datetime import date, timedelta
    table_name = table_name.lower()
    if table_name not in _PARENT_TABLES:
        return False, "Unknown table: " + table_name
    try:
        conn = _insp_pg_connect()
        if not conn:
            return False, "Cannot connect to PostgreSQL."
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET search_path TO %s" % _get_insp_schema())
        cur.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema=%s AND table_name=%s", (_get_insp_schema(), table_name))
        if cur.fetchone():
            cur.close(); conn.close()
            return False, table_name + " already exists."
        # Find DDL
        ddl_found = None
        for ddl in _TABLES_DDL:
            if table_name in ddl.lower():
                ddl_found = ddl; break
        if not ddl_found:
            cur.close(); conn.close()
            return False, "DDL not found for " + table_name
        cur.execute(ddl_found)
        # Create partitions for today + tomorrow
        today = date.today()
        for offset in range(2):
            _create_one_partition(cur, table_name, today + timedelta(days=offset))
        # Create related indexes
        for idx_ddl in _INDEXES_DDL:
            if table_name in idx_ddl.lower():
                try:
                    cur.execute(idx_ddl)
                except Exception:
                    pass
        cur.close(); conn.close()
        return True, table_name + " created successfully."
    except Exception as e:
        return False, "Error: " + str(e)


def insp_pg_tables_exist():
    """Check if INSP_ tables already exist."""
    try:
        conn = _insp_pg_connect()
        if not conn:
            return False
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = %s AND table_name LIKE 'insp_%%'",
            (_get_insp_schema(),)
        )
        cnt = cur.fetchone()[0]
        cur.close()
        conn.close()
        return cnt >= 7
    except Exception:
        return False


def insp_pg_create_tables():
    """Create all INSP_ tables, initial partition, and indexes. Returns (ok, message)."""
    from datetime import date, timedelta
    try:
        conn = _insp_pg_connect()
        if not conn:
            return False, "Cannot connect to PostgreSQL."
        conn.autocommit = True
        cur = conn.cursor()

        # Check if already exist
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = %s AND table_name LIKE 'insp_%%'",
            (_get_insp_schema(),)
        )
        if cur.fetchone()[0] > 0:
            cur.close()
            conn.close()
            return False, "INSP_ tables already exist."

        # Set search_path to target schema
        cur.execute("CREATE SCHEMA IF NOT EXISTS %s" % _get_insp_schema())
        cur.execute("SET search_path TO %s" % _get_insp_schema())
        created = []
        for ddl in _TABLES_DDL:
            tbl_name = ddl.split("TABLE")[1].split("(")[0].strip()
            cur.execute(ddl)
            created.append(tbl_name)

        # Create today + tomorrow partitions
        today = date.today()
        for tbl in _PARENT_TABLES:
            for offset in range(2):
                d = today + timedelta(days=offset)
                _create_one_partition(cur, tbl, d)

        # Create indexes (on parent — PG auto-propagates to partitions)
        for ddl in _INDEXES_DDL:
            try:
                cur.execute(ddl)
            except Exception:
                pass

        # Create insp_monthly_summary (non-partitioned)
        cur.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema=%s AND table_name='insp_monthly_summary'",
            (_get_insp_schema(),)
        )
        if not cur.fetchone():
            cur.execute(_MONTHLY_DDL)
            created.append('insp_monthly_summary')

        cur.close()
        conn.close()
        return True, "Created %d tables: %s" % (len(created), ", ".join(created))
    except Exception as e:
        return False, "Error: " + str(e)


def insp_pg_drop_tables():
    """Drop all INSP_ tables. Returns (ok, message)."""
    try:
        conn = _insp_pg_connect()
        if not conn:
            return False, "Cannot connect to PostgreSQL."
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = %s AND table_name LIKE 'insp_%%' "
            "ORDER BY table_name",
            (_get_insp_schema(),)
        )
        tables = [r[0] for r in cur.fetchall()]
        if not tables:
            cur.close()
            conn.close()
            return False, "No INSP_ tables found."
        # Drop parent tables (CASCADE drops partitions too)
        dropped = []
        for t in _PARENT_TABLES:
            if t in tables:
                cur.execute("DROP TABLE %s.%s CASCADE" % (_get_insp_schema(), t))
                dropped.append(t)
        # Drop insp_monthly_summary (non-partitioned)
        if 'insp_monthly_summary' in tables:
            try:
                cur.execute("DROP TABLE IF EXISTS %s.insp_monthly_summary" % _get_insp_schema())
                dropped.append('insp_monthly_summary')
            except Exception:
                pass

        # Drop any remaining insp_ tables
        for t in tables:
            if t not in _PARENT_TABLES and t != 'insp_monthly_summary':
                try:
                    cur.execute("DROP TABLE IF EXISTS %s.%s CASCADE" % (_get_insp_schema(), t))
                    dropped.append(t)
                except Exception:
                    pass
        cur.close()
        conn.close()
        return True, "Dropped %d tables: %s" % (len(dropped), ", ".join(dropped))
    except Exception as e:
        return False, "Error: " + str(e)


# ── Partition management ─────────────────────────────────────────────────────────

def _create_one_partition(cur, parent_table, target_date):
    """Create a single daily partition for target_date if not exists."""
    from datetime import timedelta
    d0 = target_date.strftime('%Y-%m-%d')
    d1 = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')
    part_name = "%s_%s" % (parent_table, target_date.strftime('%Y%m%d'))
    try:
        cur.execute(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE c.relname=%s AND n.nspname=%s", (part_name, _get_insp_schema())
        )
        if not cur.fetchone():
            _s = _get_insp_schema()
            cur.execute(
                "CREATE TABLE %s.%s PARTITION OF %s.%s FOR VALUES FROM ('%s') TO ('%s')"
                % (_s, part_name, _s, parent_table, d0, d1)
            )
    except Exception:
        pass


def insp_pg_ensure_partitions(target_date):
    """Ensure daily partitions exist for all INSP_ tables for the given date."""
    try:
        conn = _insp_pg_connect()
        if not conn:
            return
        conn.autocommit = True
        cur = conn.cursor()
        for tbl in _PARENT_TABLES:
            _create_one_partition(cur, tbl, target_date)
        cur.close()
        conn.close()
    except Exception:
        pass


# ── INSERT helpers ───────────────────────────────────────────────────────────────

def insp_pg_insert_os(cpu, mem):
    """Insert one OS history row."""
    try:
        conn = _insp_pg_connect()
        if not conn:
            return
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO insp_os_history "
            "(collected_at, cpu_percent, cpu_user, cpu_system, cpu_iowait, "
            "mem_total_gb, mem_used_gb, mem_free_gb, mem_percent) "
            "VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s)",
            (cpu["percent"], cpu["user"], cpu["system"], cpu["iowait"],
             mem["total_gb"], mem["used_gb"], mem["free_gb"], mem["percent"])
        )
        cur.close()
        conn.close()
    except Exception:
        pass


def insp_pg_insert_tbs(tbs_list):
    """Insert tablespace/disk history rows."""
    try:
        conn = _insp_pg_connect()
        if not conn:
            return
        conn.autocommit = True
        cur = conn.cursor()
        for ts in tbs_list:
            cur.execute(
                "INSERT INTO insp_tbs_history "
                "(collected_at, tbs_name, used_gb, total_gb, free_gb, used_percent, status) "
                "VALUES (NOW(), %s, %s, %s, %s, %s, %s)",
                (ts["name"], ts["used_gb"], ts["total_gb"], ts["free_gb"],
                 ts["percent"], ts["status"])
            )
        cur.close()
        conn.close()
    except Exception:
        pass


def insp_pg_insert_services(rows):
    """Insert service history rows. rows = list of (name, status, pid, port, uptime)."""
    try:
        conn = _insp_pg_connect()
        if not conn:
            return
        conn.autocommit = True
        cur = conn.cursor()
        for name, status, pid, port, uptime in rows:
            cur.execute(
                "INSERT INTO insp_service_history "
                "(collected_at, service_name, status, pid, port, uptime) "
                "VALUES (NOW(), %s, %s, %s, %s, %s)",
                (name, status, pid, port, uptime)
            )
        cur.close()
        conn.close()
    except Exception:
        pass


def insp_pg_insert_heap(rows):
    """Insert heap history rows.
    rows = list of (service_name, collected_at_str, used, alloc, max_mb).
    collected_at_str: 'YYYY-MM-DD HH:MM:SS' from log timestamp.
    """
    try:
        conn = _insp_pg_connect()
        if not conn:
            return
        conn.autocommit = True
        cur = conn.cursor()
        for svc, collected_at, used, alloc, max_mb in rows:
            cur.execute(
                "INSERT INTO insp_heap_history "
                "(collected_at, service_name, heap_used_mb, heap_alloc_mb, heap_max_mb) "
                "VALUES (to_timestamp(%s,'YYYY-MM-DD HH24:MI:SS'), %s, %s, %s, %s)",
                (collected_at, svc, used, alloc, max_mb)
            )
        cur.close()
        conn.close()
    except Exception:
        pass


def insp_pg_insert_qcnt(rows):
    """Insert qcnt history rows.
    rows = list of (service_name, collected_at_str, act, total, max_conn, qcnt).
    collected_at_str: 'YYYY-MM-DD HH:MM:SS' from log timestamp.
    """
    try:
        conn = _insp_pg_connect()
        if not conn:
            return
        conn.autocommit = True
        cur = conn.cursor()
        for svc, collected_at, act, total, max_conn, qcnt in rows:
            cur.execute(
                "INSERT INTO insp_qcnt_history "
                "(collected_at, service_name, act, total, max_conn, qcnt) "
                "VALUES (to_timestamp(%s,'YYYY-MM-DD HH24:MI:SS'), %s, %s, %s, %s, %s)",
                (collected_at, svc, act, total, max_conn, qcnt)
            )
        cur.close()
        conn.close()
    except Exception:
        pass



def insp_pg_insert_proc(rows):
    """Insert process snapshot rows. rows = list of dict from system_utils._proc_snapshot_top.
    collected_at 은 분 단위로 통일 (시점 클릭 시 같은 분의 행이 묶임)."""
    if not rows:
        return
    try:
        conn = _insp_pg_connect()
        if not conn:
            return
        cur = conn.cursor()
        from datetime import datetime as _dt
        ts = _dt.now().strftime('%Y-%m-%d %H:%M:00')
        params = [
            (ts, r['pid'], r.get('user', ''), r['cpu_pct'], r['mem_pct'],
             r['rss_kb'], r['vsz_kb'], r['threads'], r.get('etime', ''),
             r.get('comm', ''), r.get('args', ''))
            for r in rows
        ]
        cur.executemany(
            "INSERT INTO insp_proc_history "
            "(collected_at, pid, os_user, cpu_pct, mem_pct, rss_kb, vsz_kb, "
            " threads, etime, comm, args) "
            "VALUES (to_timestamp(%s,'YYYY-MM-DD HH24:MI:SS'), %s, %s, %s, %s, "
            " %s, %s, %s, %s, %s, %s)",
            params
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


def insp_pg_insert_summary(check_type, rows_data):
    """Insert summary history rows.
    rows_data = list of (db_id, instance, stype, status, last_summary, delay)."""
    try:
        conn = _insp_pg_connect()
        if not conn:
            return
        conn.autocommit = True
        cur = conn.cursor()
        for db_id, inst, stype, status, last_sum, delay in rows_data:
            cur.execute(
                "INSERT INTO insp_summary_history "
                "(collected_at, check_type, db_id, instance_name, summary_type, "
                "status, last_summary, delay_info) "
                "VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s)",
                (check_type, db_id, inst, stype, status, last_sum, delay)
            )
        cur.close()
        conn.close()
    except Exception:
        pass


# ── Monthly Summary (non-partitioned) ───────────────────────────────────────────

_MONTHLY_DDL = """CREATE TABLE insp_monthly_summary (
    year_month    CHAR(7)        NOT NULL,
    cpu_avg       NUMERIC(5,1),
    mem_avg       NUMERIC(5,1),
    mem_used_gb   NUMERIC(10,1),
    mem_total_gb  NUMERIC(10,1),
    disk_avg      NUMERIC(5,1),
    disk_used_gb  NUMERIC(12,1),
    disk_total_gb NUMERIC(12,1),
    sample_count  INTEGER,
    created_at    TIMESTAMP      DEFAULT NOW(),
    CONSTRAINT insp_monthly_pk PRIMARY KEY (year_month)
)"""


def insp_pg_create_monthly_table():
    """Create insp_monthly_summary if it does not exist. Returns (ok, message)."""
    try:
        conn = _insp_pg_connect()
        if not conn:
            return False, "Cannot connect to PostgreSQL."
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema=%s AND table_name='insp_monthly_summary'",
            (_get_insp_schema(),)
        )
        if cur.fetchone():
            cur.close(); conn.close()
            return False, "insp_monthly_summary already exists."
        cur.execute(_MONTHLY_DDL)
        cur.close(); conn.close()
        return True, "insp_monthly_summary created."
    except Exception as e:
        return False, "Error: " + str(e)


def insp_pg_upsert_monthly_summary(year_month, cpu_avg, mem_avg,
                                    mem_used_gb, mem_total_gb,
                                    disk_avg, disk_used_gb, disk_total_gb,
                                    sample_count):
    """INSERT or UPDATE one row in insp_monthly_summary."""
    try:
        conn = _insp_pg_connect()
        if not conn:
            return
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO insp_monthly_summary "
            "(year_month,cpu_avg,mem_avg,mem_used_gb,mem_total_gb,"
            " disk_avg,disk_used_gb,disk_total_gb,sample_count,created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW()) "
            "ON CONFLICT (year_month) DO UPDATE SET "
            "cpu_avg=EXCLUDED.cpu_avg, mem_avg=EXCLUDED.mem_avg, "
            "mem_used_gb=EXCLUDED.mem_used_gb, mem_total_gb=EXCLUDED.mem_total_gb, "
            "disk_avg=EXCLUDED.disk_avg, disk_used_gb=EXCLUDED.disk_used_gb, "
            "disk_total_gb=EXCLUDED.disk_total_gb, sample_count=EXCLUDED.sample_count, "
            "created_at=NOW()",
            (year_month, cpu_avg, mem_avg, mem_used_gb, mem_total_gb,
             disk_avg, disk_used_gb, disk_total_gb, sample_count)
        )
        cur.close(); conn.close()
    except Exception:
        pass


def insp_pg_query_monthly_summary(year):
    """Return {month_int: {cpu_avg, mem_avg, mem_used_gb, mem_total_gb,
                           disk_avg, disk_used_gb, disk_total_gb}} for the given year."""
    result = {}
    try:
        conn = _insp_pg_connect()
        if not conn:
            return result
        cur = conn.cursor()
        cur.execute(
            "SELECT year_month, cpu_avg, mem_avg, mem_used_gb, mem_total_gb, "
            "       disk_avg, disk_used_gb, disk_total_gb "
            "FROM insp_monthly_summary "
            "WHERE year_month LIKE %s ORDER BY year_month",
            (str(year) + '-%',)
        )
        for row in cur.fetchall():
            ym = str(row[0]).strip()
            try:
                month = int(ym.split('-')[1])
            except Exception:
                continue
            result[month] = {
                'cpu_avg':      float(row[1]) if row[1] is not None else None,
                'mem_avg':      float(row[2]) if row[2] is not None else None,
                'mem_used_gb':  float(row[3]) if row[3] is not None else None,
                'mem_total_gb': float(row[4]) if row[4] is not None else None,
                'disk_avg':     float(row[5]) if row[5] is not None else None,
                'disk_used_gb': float(row[6]) if row[6] is not None else None,
                'disk_total_gb':float(row[7]) if row[7] is not None else None,
            }
        cur.close(); conn.close()
    except Exception:
        pass
    return result


# ── Retention cleanup ────────────────────────────────────────────────────────────

def insp_pg_cleanup_old_partitions(retention_days):
    """Drop partitions older than retention_days from all INSP_ tables."""
    from datetime import date, timedelta
    try:
        conn = _insp_pg_connect()
        if not conn:
            return
        conn.autocommit = True
        cur = conn.cursor()
        cutoff = (date.today() - timedelta(days=retention_days)).strftime('%Y%m%d')

        for parent in _PARENT_TABLES:
            cur.execute(
                "SELECT c.relname FROM pg_inherits i "
                "JOIN pg_class c ON c.oid = i.inhrelid "
                "JOIN pg_class p ON p.oid = i.inhparent "
                "WHERE p.relname = %s ORDER BY c.relname", (parent,)
            )
            for (part_name,) in cur.fetchall():
                # partition name format: insp_xxx_history_YYYYMMDD
                suffix = part_name.rsplit('_', 1)[-1]
                if suffix.isdigit() and len(suffix) == 8 and suffix < cutoff:
                    try:
                        cur.execute("DROP TABLE %s.%s" % (_get_insp_schema(), part_name))
                    except Exception:
                        pass

        cur.close()
        conn.close()
    except Exception:
        pass
