#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MaxSpace Server
Inspector 의 service_config.json (Repository Database) 정보를 기준으로 동작.
PostgreSQL / Oracle 둘 다 지원. service_config 의 Repository 정보가 변경되면
다음 요청 때 자동으로 풀/캐시 폐기 후 새 정보로 재연결 (lazy invalidation).
"""

import logging
import logging.handlers
import os
import re
import json
import time
import threading
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Tuple

# PG 드라이버
try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
    _HAS_PSYCOPG2 = True
except ImportError:
    _HAS_PSYCOPG2 = False

# Oracle 드라이버 (lazy — 없으면 PG 만 동작)
try:
    import oracledb
    _HAS_ORACLEDB = True
except ImportError:
    _HAS_ORACLEDB = False

from fastapi import FastAPI, Query, Response, Request
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import urllib.request as _ur

# =====================================================
# 경로 / 설정
# =====================================================
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))           # MaxSpace/bin
ROOT_DIR       = os.path.dirname(BASE_DIR)                            # MaxSpace
LABS_DIR       = os.path.dirname(ROOT_DIR)                            # Labs
LABS_YAML      = os.path.join(LABS_DIR, "config.yaml")
TS_CONFIG_PATH = os.path.join(ROOT_DIR, "conf", "tablespace_config.json")


def _yaml_section_port(section: str, default: int) -> int:
    """Labs/config.yaml 의 <section>.port 정수값 읽기. 실패/누락 시 default."""
    try:
        with open(LABS_YAML, encoding="utf-8") as f:
            content = f.read()
        m = re.search(r"^" + re.escape(section) + r":\s*\n(?:.*\n)*?\s+port:\s*(\d+)",
                      content, re.MULTILINE)
        return int(m.group(1)) if m else default
    except Exception:
        return default


def load_ts_config() -> dict:
    """tablespace_config.json 을 읽되 일부 값은 config.yaml 에서 자동 추론."""
    try:
        with open(TS_CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        cfg = {}

    # port: Labs/config.yaml 의 tablespace.port 우선
    yaml_port = _yaml_section_port("tablespace", 0)
    if yaml_port:
        cfg["port"] = yaml_port
    elif not cfg.get("port"):
        cfg["port"] = 7083

    # service_config_path: 비어 있으면 Labs/Inspector/python-utils/service_config.json
    scp = cfg.get("service_config_path")
    if not (isinstance(scp, str) and scp.strip()):
        cfg["service_config_path"] = os.path.join(
            LABS_DIR, "Inspector", "python-utils", "service_config.json")

    return cfg


def load_repo_config() -> dict:
    """service_config.json 의 repository 섹션을 그대로 반환.
    Labs > Configuration > Repository Database 가 단일 source of truth."""
    cfg = load_ts_config()
    with open(cfg["service_config_path"], encoding="utf-8") as f:
        return json.load(f)["repository"]


def load_cors_origins() -> list:
    return [f"http://localhost:{_yaml_section_port('gateway', 14080)}"]


# =====================================================
# 권한 필터 — Labs 로그인 user 가 볼 수 있는 instance 만 노출
# =====================================================
#  - Inspector(/labs/api/whoami) 로 현재 cookie 의 user_id, role 조회
#  - role=='engineer' (maxgauge 계정) → 전체 허용
#  - role=='user' 인 경우 repo DB 의 apm_user_list / apm_users_db_list 직접 조회
#       * admin_role >= 2 → 전체 허용
#       * 그 외 → apm_users_db_list 의 db_id NOT IN ('0','9999')
#                + ROLE1~6 중 하나라도 ≥ 1 인 db_id 만 허용
#
#  실패 시 (전부 차단): 권한 정보 없으면 데이터도 안 보임 (안전).

def _fetch_user_dbids(cookie_header: str):
    """현재 cookie 의 user 가 볼 수 있는 instance DB_ID 집합 반환.
    Returns: (all_allowed: bool, dbids: set[int])
    """
    if not cookie_header:
        return False, set()
    # 1) Inspector whoami 로 user_id, role
    try:
        port = _yaml_section_port("python_utils", 7082)
        req = _ur.Request(
            "http://127.0.0.1:%d/labs/api/whoami" % port,
            headers={"Cookie": cookie_header},
            method="GET")
        with _ur.urlopen(req, timeout=3) as resp:
            who = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception as e:
        logger.warning("[auth] whoami 호출 실패: %s", e)
        return False, set()
    if not who.get("ok"):
        return False, set()
    user_id = (who.get("id") or "").strip()
    role    = (who.get("role") or "").strip()
    if role == "engineer":
        return True, set()
    if not user_id:
        return False, set()

    # 2) repo DB 에서 admin_role / 허용 db_id 조회
    try:
        db_type, pool = get_pool()
    except Exception as e:
        logger.warning("[auth] pool 획득 실패: %s", e)
        return False, set()

    if db_type == "postgres":
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT seq, admin_role FROM apm_user_list WHERE user_id=%s",
                            (user_id,))
                row = cur.fetchone()
                if not row:
                    return False, set()
                seq, admin_role = row[0], int(row[1] or 0)
                if admin_role >= 2:
                    return True, set()
                cur.execute(
                    "SELECT db_id FROM apm_users_db_list "
                    " WHERE seq = %s "
                    "   AND db_id NOT IN ('0','9999') "
                    "   AND (COALESCE(NULLIF(role1,'')::int,0) >= 1 "
                    "     OR COALESCE(NULLIF(role2,'')::int,0) >= 1 "
                    "     OR COALESCE(NULLIF(role3,'')::int,0) >= 1 "
                    "     OR COALESCE(NULLIF(role4,'')::int,0) >= 1 "
                    "     OR COALESCE(NULLIF(role5,'')::int,0) >= 1 "
                    "     OR COALESCE(NULLIF(role6,'')::int,0) >= 1)",
                    (seq,))
                dbids = set(int(r[0]) for r in cur.fetchall() if r[0] is not None)
                return False, dbids
        except Exception as e:
            logger.warning("[auth] PG dbid 조회 실패: %s", e)
            return False, set()
        finally:
            try: pool.putconn(conn)
            except Exception: pass

    # Oracle
    conn = pool.acquire()
    try:
        cur = conn.cursor()
        cur.execute("SELECT seq, admin_role FROM apm_user_list WHERE user_id=:1", [user_id])
        row = cur.fetchone()
        if not row:
            cur.close()
            return False, set()
        seq, admin_role = row[0], int(row[1] or 0)
        if admin_role >= 2:
            cur.close()
            return True, set()
        cur.execute(
            "SELECT db_id FROM apm_users_db_list "
            " WHERE seq = :1 "
            "   AND db_id NOT IN ('0','9999') "
            "   AND (NVL(TO_NUMBER(role1),0) >= 1 "
            "     OR NVL(TO_NUMBER(role2),0) >= 1 "
            "     OR NVL(TO_NUMBER(role3),0) >= 1 "
            "     OR NVL(TO_NUMBER(role4),0) >= 1 "
            "     OR NVL(TO_NUMBER(role5),0) >= 1 "
            "     OR NVL(TO_NUMBER(role6),0) >= 1)",
            [seq])
        dbids = set(int(r[0]) for r in cur.fetchall() if r[0] is not None)
        cur.close()
        return False, dbids
    except Exception as e:
        logger.warning("[auth] Oracle dbid 조회 실패: %s", e)
        return False, set()
    finally:
        try: pool.release(conn)
        except Exception: pass


# =====================================================
# Log Config
# =====================================================
class _DailySizeHandler(logging.handlers.TimedRotatingFileHandler):
    """일별 + 크기 초과 시 .N 시퀀스 파일 생성."""
    def __init__(self, filename: str, max_bytes: int = 0, backup_days: int = 30):
        super().__init__(filename, when='midnight', backupCount=backup_days,
                         encoding='utf-8', delay=False)
        self.max_bytes = max_bytes

    def shouldRollover(self, record) -> bool:
        if super().shouldRollover(record):
            return True
        if self.max_bytes > 0 and self.stream:
            self.stream.seek(0, 2)
            if self.stream.tell() >= self.max_bytes:
                return True
        return False

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        current_time     = int(time.time())
        is_time_rollover = (current_time >= self.rolloverAt)
        date_str  = time.strftime(self.suffix, time.localtime(self.rolloverAt - self.interval))
        base_dest = self.rotation_filename(self.baseFilename + '.' + date_str)
        dest = base_dest
        if os.path.exists(dest):
            seq = 1
            while os.path.exists(self.rotation_filename(base_dest + '.' + str(seq))):
                seq += 1
            dest = self.rotation_filename(base_dest + '.' + str(seq))
        self.rotate(self.baseFilename, dest)
        self._cleanup_old_logs()
        if is_time_rollover:
            self.rolloverAt = self.computeRollover(current_time)
        if not self.delay:
            self.stream = self._open()

    def _cleanup_old_logs(self):
        if self.backupCount <= 0:
            return
        log_dir  = os.path.dirname(os.path.abspath(self.baseFilename))
        log_name = os.path.basename(self.baseFilename)
        cutoff   = time.time() - self.backupCount * 86400
        try:
            for fname in os.listdir(log_dir):
                if fname.startswith(log_name + '.') and fname != log_name:
                    fpath = os.path.join(log_dir, fname)
                    if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                        os.remove(fpath)
        except OSError:
            pass


def setup_logging() -> logging.Logger:
    cfg         = load_ts_config()
    log_file    = os.path.join(ROOT_DIR, cfg.get("log_file", "log/server.log"))
    max_bytes   = int(cfg.get("log_max_bytes",   10 * 1024 * 1024))
    backup_days = int(cfg.get("log_backup_days", 30))
    level       = getattr(logging, cfg.get("log_level", "INFO").upper(), logging.INFO)
    fmt     = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                datefmt="%Y-%m-%d %H:%M:%S")
    handler = _DailySizeHandler(log_file, max_bytes=max_bytes, backup_days=backup_days)
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uv = logging.getLogger(name)
        uv.handlers.clear()
        uv.addHandler(handler)
        uv.propagate = False
    return logging.getLogger(__name__)


logger = setup_logging()


# =====================================================
# DB 타입 / 커넥션 시그니처
# =====================================================
def _db_type_of(repo: dict) -> str:
    """repo['db_type'] 를 'postgres' / 'oracle' 로 정규화."""
    t = (repo.get("db_type") or "").strip().lower()
    if "oracle" in t:
        return "oracle"
    return "postgres"


def _connection_signature(repo: dict) -> Tuple:
    """connection 파라미터 변경 감지용 튜플. service_config 의 repository 가 바뀌면 달라짐."""
    return (
        _db_type_of(repo),
        (repo.get("ip") or "").strip(),
        str(repo.get("port") or "").strip(),
        (repo.get("user") or "").strip(),
        (repo.get("password") or "").strip(),
        (repo.get("sid") or "").strip(),
    )


# =====================================================
# 풀 + 캐시 (lazy invalidation)
# =====================================================
_pool                 = None             # 현재 활성 풀 (psycopg2 ThreadedConnectionPool 또는 oracledb pool)
_pool_db_type: str    = ""               # 'postgres' / 'oracle'
_pool_signature: tuple = ()              # 풀이 생성될 때의 connection signature
_pool_lock            = threading.Lock()


def _close_pool_silent(pool, db_type: str) -> None:
    if pool is None:
        return
    try:
        if db_type == "postgres":
            pool.closeall()
        else:
            pool.close()
    except Exception:
        pass


def _invalidate_caches() -> None:
    """connection 정보가 바뀌면 풀과 함께 cache 도 비운다."""
    global _cache, _cache_time, _inst_map
    _cache, _cache_time = None, 0.0
    _inst_map = {}
    with _trend_lock:
        _trend_cache.clear()
        _trend_cache_time.clear()


def get_pool():
    """현재 service_config 의 Repository 정보 기반으로 풀을 가져온다.
    Repository 정보가 변경된 게 감지되면 기존 풀/캐시를 폐기하고 새로 생성.
    반환: (db_type, pool)
    """
    global _pool, _pool_db_type, _pool_signature
    repo = load_repo_config()
    if not repo.get("ip") or not repo.get("sid"):
        raise RuntimeError("Repository DB not configured. Labs → Configuration 에서 설정하세요.")
    new_sig = _connection_signature(repo)
    db_type = new_sig[0]

    with _pool_lock:
        if _pool is not None and _pool_signature == new_sig:
            return _pool_db_type, _pool

        # signature 변경 → 기존 풀/캐시 폐기
        if _pool is not None:
            logger.info("[pool] Repository 정보 변경 감지 → 기존 %s 풀/캐시 폐기", _pool_db_type)
            _close_pool_silent(_pool, _pool_db_type)
            _invalidate_caches()
            _pool = None
            _pool_db_type = ""
            _pool_signature = ()

        # 새 풀 생성
        if db_type == "postgres":
            if not _HAS_PSYCOPG2:
                raise RuntimeError("psycopg2 driver not installed")
            new_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2, maxconn=16,
                host=repo["ip"],
                port=int(repo["port"]),
                dbname=repo["sid"],
                user=repo.get("user", ""),
                password=repo.get("password", ""),
                connect_timeout=10,
                options="-c statement_timeout=30000",
            )
            logger.info("[pool] PG 풀 생성: %s:%s/%s user=%s",
                        repo["ip"], repo["port"], repo["sid"], repo.get("user", ""))
        elif db_type == "oracle":
            if not _HAS_ORACLEDB:
                raise RuntimeError("oracledb driver not installed")
            dsn = "%s:%s/%s" % (repo["ip"], int(repo["port"]), repo["sid"])
            new_pool = oracledb.create_pool(
                user=repo.get("user", ""),
                password=repo.get("password", ""),
                dsn=dsn,
                min=2, max=16, increment=1,
                getmode=oracledb.POOL_GETMODE_WAIT,
            )
            logger.info("[pool] Oracle 풀 생성: %s user=%s", dsn, repo.get("user", ""))
        else:
            raise RuntimeError("Unsupported db_type: %s" % db_type)

        _pool           = new_pool
        _pool_db_type   = db_type
        _pool_signature = new_sig
        return db_type, _pool


def _to_serializable(val):
    if isinstance(val, Decimal):
        return float(val)
    return val


def run_query(sql: str, params=None) -> list:
    """db_type 에 맞게 query 실행. 결과는 list[dict] (키 소문자)."""
    global _pool, _pool_db_type, _pool_signature
    db_type, pool = get_pool()

    if db_type == "postgres":
        conn = pool.getconn()
        conn_returned = False
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params or ())
                return [{k: _to_serializable(v) for k, v in dict(r).items()} for r in cur.fetchall()]
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            conn_returned = True
            try:
                pool.putconn(conn, close=True)
            except Exception:
                pass
            with _pool_lock:
                _close_pool_silent(_pool, _pool_db_type)
                _pool = None
                _pool_db_type = ""
                _pool_signature = ()
            logger.warning("[pool] PG 연결 오류 → 풀 폐기: %s", e)
            raise
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            if not conn_returned:
                try:
                    pool.putconn(conn)
                except Exception:
                    pass

    # Oracle
    conn = pool.acquire()
    conn_returned = False
    try:
        cur = conn.cursor()
        cur.execute(sql, params or {})
        cols = [d[0].lower() for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        cur.close()
        return [{cols[i]: _to_serializable(v) for i, v in enumerate(row)} for row in rows]
    except oracledb.DatabaseError as e:
        # 연결 종류의 에러는 풀 재구성
        msg = str(e)
        if any(c in msg for c in ("ORA-03113", "ORA-03114", "ORA-12537", "ORA-12541",
                                   "ORA-12545", "ORA-12560", "ORA-01017", "DPY-")):
            conn_returned = True
            try:
                pool.drop(conn)
            except Exception:
                pass
            with _pool_lock:
                _close_pool_silent(_pool, _pool_db_type)
                _pool = None
                _pool_db_type = ""
                _pool_signature = ()
            logger.warning("[pool] Oracle 연결 오류 → 풀 폐기: %s", e)
        raise
    finally:
        if not conn_returned:
            try:
                pool.release(conn)
            except Exception:
                pass


# =====================================================
# 스키마 이름 안전성 검증 (PG 만 — f-string SQL 삽입 방어)
# =====================================================
_SAFE_SCHEMA_RE = re.compile(r'^[a-zA-Z0-9_]+$')

def _validate_schema(schema: str) -> None:
    if not _SAFE_SCHEMA_RE.match(schema or ""):
        raise ValueError("허용되지 않은 스키마명: %r" % schema)


# =====================================================
# 스키마 / 인스턴스 / 그룹 조회 — db_type 분기
# =====================================================
def find_tablespace_schemas() -> list:
    """PG: 인스턴스별 schema 안에 ora_tablespace_info 가 있는 schema 목록.
    Oracle: 단일 user schema 안에 모든 데이터가 있으므로 USER 한 개 반환."""
    db_type, _ = get_pool()
    if db_type == "postgres":
        rows = run_query("""
            SELECT table_schema
            FROM information_schema.tables
            WHERE table_name = 'ora_tablespace_info'
              AND table_schema NOT IN ('pg_catalog','information_schema','public','insp')
              AND table_name NOT SIMILAR TO '%%_p[0-9]+'
            ORDER BY table_schema
        """)
        return [r["table_schema"] for r in rows]
    # Oracle
    rows = run_query("SELECT USER AS u FROM dual")
    return [rows[0]["u"]] if rows else []


def get_instances() -> list:
    db_type, _ = get_pool()
    table = "public.apm_db_info" if db_type == "postgres" else "apm_db_info"
    return run_query("SELECT db_id, instance_name, business_name FROM %s ORDER BY db_id" % table)


def get_service_groups() -> list:
    db_type, _ = get_pool()
    prefix = "public." if db_type == "postgres" else ""
    rows = run_query("""
        SELECT
            sn.service_id,
            sn.name        AS service_name,
            f.db_id,
            f.instance_name
        FROM %sora_service_name  sn
        JOIN %sora_service_info  si ON si.service_id = sn.service_id
        JOIN %sapm_db_info       f  ON f.db_id = si.db_id
        ORDER BY sn.service_id, f.instance_name
    """ % (prefix, prefix, prefix))
    groups: dict = {}
    for r in rows:
        sid = r["service_id"]
        if sid not in groups:
            groups[sid] = {"service_id": sid, "service_name": r["service_name"], "instances": []}
        groups[sid]["instances"].append({
            "db_id":         r["db_id"],
            "instance_name": r["instance_name"],
        })
    return list(groups.values())


# =====================================================
# 단위 변환 (MB → GB)
# =====================================================
def unit_div(col: str) -> str:
    n = col.lower()
    if "_gb" in n:
        return col
    if "_mb" in n or "_space" in n:
        return "ROUND(%s/1024.0, 2)" % col
    return "ROUND(%s/1073741824.0, 2)" % col


# =====================================================
# 테이블스페이스 현황 조회 (snapshot + 1주 / 1개월 사용률)
# =====================================================
def get_ts_data(schema: Optional[str], db_id: int) -> list:
    db_type, _ = get_pool()
    total_expr = unit_div("total_space")
    free_expr  = unit_div("free_space")
    used_expr  = "(%s - %s)" % (total_expr, free_expr)

    if db_type == "postgres":
        _validate_schema(schema)
        full = "%s.ora_tablespace_info" % schema
        sql = """
            WITH latest AS (
                SELECT MAX(time) AS max_time
                FROM {full} WHERE db_id = %(db_id)s
            ),
            snap AS (
                SELECT tablespace_name             AS ts_name,
                       SUM({total_expr})           AS total_gb,
                       SUM({used_expr})            AS used_gb
                FROM {full}, latest
                WHERE db_id = %(db_id)s AND time = latest.max_time
                GROUP BY tablespace_name
            ),
            w1 AS (
                SELECT tablespace_name AS ts_name, SUM({used_expr}) AS used_gb
                FROM {full}
                WHERE db_id = %(db_id)s
                  AND time = (
                    SELECT MAX(time) FROM {full}
                    WHERE db_id = %(db_id)s
                      AND time <= (SELECT max_time - INTERVAL '7 days' FROM latest)
                  )
                GROUP BY tablespace_name
            ),
            m1 AS (
                SELECT tablespace_name AS ts_name, SUM({used_expr}) AS used_gb
                FROM {full}
                WHERE db_id = %(db_id)s
                  AND time = (
                    SELECT MAX(time) FROM {full}
                    WHERE db_id = %(db_id)s
                      AND time <= (SELECT max_time - INTERVAL '30 days' FROM latest)
                  )
                GROUP BY tablespace_name
            )
            SELECT
                s.ts_name,
                COALESCE(s.total_gb, 0) AS total_gb,
                COALESCE(s.used_gb,  0) AS used_gb,
                CASE WHEN COALESCE(s.total_gb,0) > 0
                     THEN ROUND(COALESCE(w1.used_gb, s.used_gb) / s.total_gb * 100, 1)
                     ELSE 0 END         AS used_pct_1w,
                CASE WHEN COALESCE(s.total_gb,0) > 0
                     THEN ROUND(COALESCE(m1.used_gb, s.used_gb) / s.total_gb * 100, 1)
                     ELSE 0 END         AS used_pct_1m
            FROM snap s
            LEFT JOIN w1 ON w1.ts_name = s.ts_name
            LEFT JOIN m1 ON m1.ts_name = s.ts_name
            WHERE s.total_gb > 0
            ORDER BY s.used_gb DESC
        """.format(full=full, total_expr=total_expr, used_expr=used_expr)
        return run_query(sql, {"db_id": db_id})

    # Oracle — schema 는 USER 안이라 prefix 불필요. INTERVAL '7' DAY 형태 사용.
    full = "ora_tablespace_info"
    sql = """
        WITH latest AS (
            SELECT MAX(time) AS max_time
            FROM {full} WHERE db_id = :db_id
        ),
        snap AS (
            SELECT tablespace_name             AS ts_name,
                   SUM({total_expr})           AS total_gb,
                   SUM({used_expr})            AS used_gb
            FROM {full}, latest
            WHERE db_id = :db_id AND time = latest.max_time
            GROUP BY tablespace_name
        ),
        w1 AS (
            SELECT tablespace_name AS ts_name, SUM({used_expr}) AS used_gb
            FROM {full}
            WHERE db_id = :db_id
              AND time = (
                SELECT MAX(time) FROM {full}
                WHERE db_id = :db_id
                  AND time <= (SELECT max_time - INTERVAL '7' DAY FROM latest)
              )
            GROUP BY tablespace_name
        ),
        m1 AS (
            SELECT tablespace_name AS ts_name, SUM({used_expr}) AS used_gb
            FROM {full}
            WHERE db_id = :db_id
              AND time = (
                SELECT MAX(time) FROM {full}
                WHERE db_id = :db_id
                  AND time <= (SELECT max_time - INTERVAL '30' DAY FROM latest)
              )
            GROUP BY tablespace_name
        )
        SELECT
            s.ts_name                                                   AS ts_name,
            NVL(s.total_gb, 0)                                          AS total_gb,
            NVL(s.used_gb,  0)                                          AS used_gb,
            CASE WHEN NVL(s.total_gb,0) > 0
                 THEN ROUND(NVL(w1.used_gb, s.used_gb) / s.total_gb * 100, 1)
                 ELSE 0 END                                             AS used_pct_1w,
            CASE WHEN NVL(s.total_gb,0) > 0
                 THEN ROUND(NVL(m1.used_gb, s.used_gb) / s.total_gb * 100, 1)
                 ELSE 0 END                                             AS used_pct_1m
        FROM snap s
        LEFT JOIN w1 ON w1.ts_name = s.ts_name
        LEFT JOIN m1 ON m1.ts_name = s.ts_name
        WHERE NVL(s.total_gb, 0) > 0
        ORDER BY s.used_gb DESC
    """.format(full=full, total_expr=total_expr, used_expr=used_expr)
    return run_query(sql, {"db_id": db_id})


# =====================================================
# 트렌드 조회
# =====================================================
def get_trend(schema: Optional[str], db_id: int) -> dict:
    db_type, _ = get_pool()
    total_expr = unit_div("total_space")
    free_expr  = unit_div("free_space")
    used_expr  = "(%s - %s)" % (total_expr, free_expr)

    if db_type == "postgres":
        _validate_schema(schema)
        full = "%s.ora_tablespace_info" % schema
        sql = """
            WITH date_range AS (
                SELECT MIN(time) AS min_time, MAX(time) AS max_time
                FROM {full}
                WHERE db_id = %(db_id)s
            )
            SELECT
                tablespace_name                          AS ts_name,
                TO_CHAR(time, 'YYYY-MM-DD')              AS snap_day,
                ROUND(SUM({total_expr})::numeric, 2)     AS total_gb,
                ROUND(SUM({used_expr})::numeric, 2)      AS used_gb
            FROM {full}, date_range
            WHERE db_id = %(db_id)s
              AND time >= date_range.min_time
              AND time <= date_range.max_time
            GROUP BY tablespace_name, TO_CHAR(time, 'YYYY-MM-DD')
            ORDER BY tablespace_name, snap_day
        """.format(full=full, total_expr=total_expr, used_expr=used_expr)
        rows = run_query(sql, {"db_id": db_id})
    else:
        full = "ora_tablespace_info"
        sql = """
            WITH date_range AS (
                SELECT MIN(time) AS min_time, MAX(time) AS max_time
                FROM {full}
                WHERE db_id = :db_id
            )
            SELECT
                tablespace_name                       AS ts_name,
                TO_CHAR(time, 'YYYY-MM-DD')           AS snap_day,
                ROUND(SUM({total_expr}), 2)           AS total_gb,
                ROUND(SUM({used_expr}),  2)           AS used_gb
            FROM {full}, date_range
            WHERE db_id = :db_id
              AND time >= date_range.min_time
              AND time <= date_range.max_time
            GROUP BY tablespace_name, TO_CHAR(time, 'YYYY-MM-DD')
            ORDER BY tablespace_name, snap_day
        """.format(full=full, total_expr=total_expr, used_expr=used_expr)
        rows = run_query(sql, {"db_id": db_id})

    trend: dict = {}
    for r in rows:
        ts    = r["ts_name"]
        total = float(r["total_gb"] or 0)
        used  = float(r["used_gb"]  or 0)
        if ts not in trend:
            trend[ts] = []
        trend[ts].append({
            "date":  r["snap_day"],
            "pct":   round(used / total * 100, 2) if total > 0 else 0,
            "used":  used,
            "total": total,
        })
    return trend


# =====================================================
# 트렌드 캐시
# =====================================================
_trend_cache:      dict  = {}
_trend_cache_time: dict  = {}
_trend_lock = threading.Lock()


def get_trend_cached(name: str) -> Optional[dict]:
    cfg       = load_ts_config()
    cache_ttl = cfg.get("cache_ttl_min", 5) * 60
    with _trend_lock:
        t = _trend_cache_time.get(name, 0)
        if _trend_cache.get(name) is not None and (time.time() - t) < cache_ttl:
            return _trend_cache[name]
    return None


def fetch_and_cache_trend(name: str, schema: Optional[str], db_id: int) -> dict:
    trend = get_trend(schema, db_id)
    with _trend_lock:
        _trend_cache[name]      = trend
        _trend_cache_time[name] = time.time()
    return trend


# =====================================================
# 메인 데이터 빌드 (캐시)
# =====================================================
_cache: Optional[dict] = None
_cache_time: float = 0
_build_lock = threading.Lock()
_inst_map: dict = {}   # { instance_name: (schema_or_None, db_id) }


def build_data() -> dict:
    global _cache, _cache_time, _inst_map

    # 풀(+캐시) lazy invalidation — Repository 변경 즉시 반영
    db_type, _ = get_pool()

    cfg       = load_ts_config()
    cache_ttl = cfg.get("cache_ttl_min", 5) * 60

    with _build_lock:
        if _cache and (time.time() - _cache_time) < cache_ttl:
            return _cache

        logger.info("[data] 빌드 시작 (db_type=%s)...", db_type)
        schemas   = find_tablespace_schemas()
        instances = get_instances()

        # PG: 인스턴스별 schema 매핑 / Oracle: schema 사용 안 함 (None)
        if db_type == "postgres":
            schema_map = {s.lower(): s for s in schemas}
        else:
            schema_map = {}

        new_inst_map: dict = {}
        db_list: list  = []
        ts_map:  dict  = {}

        def fetch_inst(inst):
            db_id  = inst["db_id"]
            name   = inst["instance_name"]
            biz    = inst.get("business_name") or "-"

            if db_type == "postgres":
                schema = schema_map.get(name.lower())
                if not schema:
                    return None
            else:
                schema = None  # Oracle: 모든 인스턴스가 단일 USER 안의 같은 테이블 공유

            new_inst_map[name] = (schema, db_id)
            try:
                ts_data = get_ts_data(schema, db_id)
                if not ts_data:
                    return None
                total_gb = sum(t["total_gb"] for t in ts_data)
                used_gb  = sum(t["used_gb"]  for t in ts_data)
                avg_1w   = sum(t["used_pct_1w"] for t in ts_data) / len(ts_data)
                avg_1m   = sum(t["used_pct_1m"] for t in ts_data) / len(ts_data)
                return (name, ts_data, {
                    "product":     "ORACLE",
                    "biz_name":    biz,
                    "db_name":     name,
                    "db_id":       int(db_id) if db_id is not None else None,
                    "schema":      schema or "",
                    "total_gb":    round(total_gb, 2),
                    "used_gb":     round(used_gb,  2),
                    "used_pct_1w": round(avg_1w,   1),
                    "used_pct_1m": round(avg_1m,   1),
                })
            except Exception as e:
                logger.error("[data] %s 오류: %s", name, e)
                return None

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(fetch_inst, inst): inst for inst in instances}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    name, ts_data, row = result
                    db_list.append(row)
                    ts_map[name] = ts_data

        _inst_map   = new_inst_map
        _cache      = {"today":       datetime.now().strftime("%Y-%m-%d"),
                       "dbs":         db_list,
                       "tablespaces": ts_map}
        _cache_time = time.time()
        logger.info("[data] 완료: %d개 DB", len(db_list))
        return _cache


def warmup_trends():
    try:
        data = build_data()
    except Exception as e:
        logger.error("[warmup] build_data 실패 (Repository 미설정?): %s", e)
        return
    names_list = [d["db_name"] for d in data["dbs"]]

    def warm_one(name):
        if get_trend_cached(name) is not None:
            return
        info = _inst_map.get(name)
        if not info:
            return
        schema, db_id = info
        try:
            fetch_and_cache_trend(name, schema, db_id)
        except Exception as e:
            logger.error("[warmup] %s 오류: %s", name, e)

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(warm_one, names_list))
    logger.info("[warmup] 트렌드 pre-warm 완료: %d개", len(names_list))


def auto_refresh_loop():
    while True:
        cfg          = load_ts_config()
        refresh_hour = cfg.get("refresh_hour", 1)
        refresh_min  = cfg.get("refresh_minute", 5)
        now    = datetime.now()
        target = now.replace(hour=refresh_hour, minute=refresh_min, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        sleep_sec = (target - now).total_seconds()
        logger.info("[auto-refresh] 다음 갱신 예정: %s (%.1f시간 후)",
                    target.strftime('%Y-%m-%d %H:%M'), sleep_sec / 3600)
        time.sleep(sleep_sec)
        try:
            logger.info("[auto-refresh] 캐시 갱신 시작...")
            global _cache, _cache_time
            _cache, _cache_time = None, 0
            build_data()
            warmup_trends()
            now2 = time.time()
            ttl = load_ts_config().get("cache_ttl_min", 1440) * 60
            with _trend_lock:
                stale = [k for k, t in _trend_cache_time.items() if (now2 - t) > ttl]
                for k in stale:
                    _trend_cache.pop(k, None)
                    _trend_cache_time.pop(k, None)
            logger.info("[auto-refresh] 완료")
        except Exception as e:
            logger.error("[auto-refresh] 오류: %s", e)


# =====================================================
# FastAPI
# =====================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=warmup_trends,    daemon=True).start()
    threading.Thread(target=auto_refresh_loop, daemon=True).start()
    yield


app = FastAPI(title="MaxSpace", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=load_cors_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    ico = bytes([
        0,0,1,0,1,0,1,1,0,0,1,0,32,0,40,0,0,0,28,0,0,0,
        40,0,0,0,1,0,0,0,2,0,0,0,1,0,32,0,0,0,0,0,4,0,0,0,
        0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
        0,0,0,0
    ])
    return Response(content=ico, media_type="image/x-icon")


@app.get("/")
def serve_root():
    return RedirectResponse(url="tablespace_dashboard.html")


@app.get("/tablespace_dashboard.html")
def serve_html():
    # 같은 디렉토리(MaxSpace/) 의 dashboard 우선, 없으면 bin/ 안의 것
    candidates = [
        os.path.join(ROOT_DIR, "tablespace_dashboard.html"),
        os.path.join(BASE_DIR, "tablespace_dashboard.html"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return FileResponse(p)
    return JSONResponse({"ok": False, "error": "dashboard html not found"}, status_code=404)


@app.get("/api/data")
def api_data(request: Request):
    try:
        data = build_data()
        cookie = request.headers.get("cookie", "")
        all_allowed, dbids = _fetch_user_dbids(cookie)
        if all_allowed:
            return JSONResponse({"ok": True, "data": data})
        # filter: user 가 허용한 db_id 만
        filtered_dbs = [d for d in data.get("dbs", [])
                        if d.get("db_id") is not None and int(d["db_id"]) in dbids]
        allowed_names = set(d["db_name"] for d in filtered_dbs)
        filtered_ts = {n: v for n, v in data.get("tablespaces", {}).items()
                       if n in allowed_names}
        return JSONResponse({"ok": True, "data": {
            "today":       data.get("today", ""),
            "dbs":         filtered_dbs,
            "tablespaces": filtered_ts,
        }})
    except Exception as e:
        logger.error("[api/data] 오류: %s", e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/trend")
def api_trend(request: Request, db: str = Query(..., description="instance_name")):
    try:
        # 권한 확인 — _inst_map 에 있는 (schema, db_id) 와 user 의 허용 dbids 비교
        cookie = request.headers.get("cookie", "")
        all_allowed, dbids = _fetch_user_dbids(cookie)
        if not all_allowed:
            info = _inst_map.get(db)
            if not info:
                # 캐시에 없으면 build_data 한번 강제로 부르고 재시도
                build_data()
                info = _inst_map.get(db)
            if info is None:
                return JSONResponse({"ok": False, "error": "인스턴스 없음: %s" % db},
                                    status_code=404)
            _, _db_id = info
            if _db_id is None or int(_db_id) not in dbids:
                return JSONResponse({"ok": False, "error": "permission denied"},
                                    status_code=403)
        cached = get_trend_cached(db)
        if cached is not None:
            return JSONResponse({"ok": True, "db": db, "trend": cached})

        info = _inst_map.get(db)
        if info:
            schema, db_id = info
        else:
            db_type, _ = get_pool()
            if db_type == "postgres":
                schemas    = find_tablespace_schemas()
                schema_map = {s.lower(): s for s in schemas}
                schema     = schema_map.get(db.lower())
                if not schema:
                    return JSONResponse({"ok": False, "error": "스키마 없음: %s" % db}, status_code=404)
            else:
                schema = None
            instances = get_instances()
            inst = next((i for i in instances if i["instance_name"] == db), None)
            if not inst:
                return JSONResponse({"ok": False, "error": "인스턴스 없음: %s" % db}, status_code=404)
            db_id = inst["db_id"]

        trend = fetch_and_cache_trend(db, schema, db_id)
        return JSONResponse({"ok": True, "db": db, "trend": trend})
    except Exception as e:
        logger.error("[api/trend] 오류: %s", e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/groups")
def api_groups():
    try:
        return JSONResponse({"ok": True, "groups": get_service_groups()})
    except Exception as e:
        logger.error("[api/groups] 오류: %s", e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/health")
def api_health():
    cfg          = load_ts_config()
    refresh_hour = cfg.get("refresh_hour", 1)
    refresh_min  = cfg.get("refresh_minute", 5)
    cache_ok      = _cache is not None
    cache_age_min = round((time.time() - _cache_time) / 60, 1) if _cache_time else None
    db_count      = len(_cache["dbs"]) if cache_ok else 0
    with _trend_lock:
        trend_cached = len(_trend_cache)
    now    = datetime.now()
    target = now.replace(hour=refresh_hour, minute=refresh_min, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return JSONResponse({
        "ok":           True,
        "status":       "healthy" if cache_ok else "initializing",
        "db_type":      _pool_db_type or "unknown",
        "cache":        {"loaded": cache_ok, "age_min": cache_age_min, "db_count": db_count},
        "trend_cache":  {"count": trend_cached, "total": db_count},
        "next_refresh": target.strftime("%Y-%m-%d %H:%M"),
        "server_time":  now.strftime("%Y-%m-%d %H:%M:%S"),
    })


@app.get("/api/refresh")
def api_refresh(token: str = Query(default="")):
    cfg         = load_ts_config()
    valid_token = cfg.get("refresh_token", "")
    if not valid_token or token != valid_token:
        return JSONResponse({"ok": False, "error": "인증 실패"}, status_code=401)
    global _cache, _cache_time
    _cache, _cache_time = None, 0
    with _trend_lock:
        _trend_cache.clear()
        _trend_cache_time.clear()
    try:
        threading.Thread(target=warmup_trends, daemon=True).start()
        return JSONResponse({"ok": True, "data": build_data()})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/reset")
def api_reset(token: str = Query(default="")):
    """Inspector 가 Repository SAVE 후 호출하는 hook.
    풀과 캐시를 즉시 폐기 — 다음 요청에서 새 service_config 로 재구성."""
    global _pool, _pool_db_type, _pool_signature
    cfg         = load_ts_config()
    valid_token = cfg.get("refresh_token", "")
    if not valid_token or token != valid_token:
        return JSONResponse({"ok": False, "error": "인증 실패"}, status_code=401)
    with _pool_lock:
        _close_pool_silent(_pool, _pool_db_type)
        _pool = None
        _pool_db_type = ""
        _pool_signature = ()
        _invalidate_caches()
    logger.info("[reset] 외부 트리거로 풀/캐시 즉시 폐기")
    threading.Thread(target=warmup_trends, daemon=True).start()
    return JSONResponse({"ok": True})


# =====================================================
# 실행
# =====================================================
if __name__ == "__main__":
    import uvicorn
    cfg  = load_ts_config()
    port = cfg.get("port", 7083)
    logger.info("MaxSpace: http://localhost:%d/tablespace_dashboard.html", port)
    uvicorn.run("tablespace_server:app", host="127.0.0.1", port=port, reload=False)
