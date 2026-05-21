# -*- coding: utf-8 -*-
"""
Tablespace dashboard data provider (ported from labs/tablespace/tablespace_server.py).

- Uses service_config.json's repository section (same as Inspector).
- Provides JSON for: data snapshot, 365-day trend, cache refresh.
- Runs inside python-utils; no separate FastAPI server/port needed.
"""

import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from decimal import Decimal

try:
    import psycopg2
    import psycopg2.extras
    _HAS_PSYCOPG2 = True
except ImportError:
    _HAS_PSYCOPG2 = False

from service_config import load_service_config


_CACHE_TTL_SEC = 5 * 60   # 5분
_TREND_DAYS    = 365

_cache = None
_cache_time = 0.0
_build_lock = threading.Lock()


# ──────────────────────────────────────────────────────────────
# DB 연결
# ──────────────────────────────────────────────────────────────
def _get_conn():
    if not _HAS_PSYCOPG2:
        raise RuntimeError("psycopg2 not available")
    repo = load_service_config().get("repository", {}) or {}
    if not repo.get("ip") or not repo.get("sid"):
        raise RuntimeError("Repository DB not configured. Go to Labs → Configuration.")
    if "postgres" not in (repo.get("db_type") or "").lower():
        raise RuntimeError("Tablespace dashboard requires PostgreSQL repository.")
    return psycopg2.connect(
        host=repo["ip"],
        port=int(repo.get("port") or 5432),
        dbname=repo["sid"],
        user=repo.get("user", ""),
        password=repo.get("password", ""),
        connect_timeout=10,
        options="-c statement_timeout=30000",
    )


def _to_serializable(val):
    if isinstance(val, Decimal):
        return float(val)
    return val


def _run_query(sql, params=None):
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return [
                {k: _to_serializable(v) for k, v in dict(r).items()}
                for r in cur.fetchall()
            ]
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# 스키마 / 인스턴스
# ──────────────────────────────────────────────────────────────
def _find_tablespace_schemas():
    rows = _run_query("""
        SELECT table_schema
        FROM information_schema.tables
        WHERE table_name = 'ora_tablespace_info'
          AND table_schema NOT IN ('pg_catalog','information_schema','public','insp')
          AND table_name NOT SIMILAR TO '%%_p[0-9]+'
        ORDER BY table_schema
    """)
    return [r["table_schema"] for r in rows]


def _get_instances():
    return _run_query("""
        SELECT db_id, instance_name, business_name
        FROM public.apm_db_info
        ORDER BY db_id
    """)


# ──────────────────────────────────────────────────────────────
# 단위 변환 (컬럼 이름 기반 MB/Bytes → GB)
# ──────────────────────────────────────────────────────────────
def _unit_div(col):
    n = col.lower()
    if "_gb" in n:
        return col
    if "_mb" in n or "_space" in n:
        return "ROUND(%s/1024.0, 2)" % col
    return "ROUND(%s/1073741824.0, 2)" % col


# ──────────────────────────────────────────────────────────────
# 테이블스페이스 현황 (오늘 스냅샷 + 1주 전 / 1개월 전 사용률)
# ──────────────────────────────────────────────────────────────
def _get_ts_data(schema, db_id):
    full       = "%s.ora_tablespace_info" % schema
    total_expr = _unit_div("total_space")
    free_expr  = _unit_div("free_space")
    used_expr  = "(%s - %s)" % (total_expr, free_expr)

    sql = """
        WITH latest AS (
            SELECT MAX(time) AS max_time
            FROM {full} WHERE db_id = %(db_id)s
        ),
        snap AS (
            SELECT tablespace_name        AS ts_name,
                   SUM({total_expr})      AS total_gb,
                   SUM({used_expr})       AS used_gb
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
    return _run_query(sql, {"db_id": db_id})


# ──────────────────────────────────────────────────────────────
# 365일 트렌드
# ──────────────────────────────────────────────────────────────
def _get_trend(schema, db_id):
    full       = "%s.ora_tablespace_info" % schema
    total_expr = _unit_div("total_space")
    free_expr  = _unit_div("free_space")
    used_expr  = "(%s - %s)" % (total_expr, free_expr)

    sql = """
        SELECT
            tablespace_name                      AS ts_name,
            TO_CHAR(time, 'YYYY-MM-DD')          AS snap_day,
            ROUND(SUM({total_expr})::numeric, 2) AS total_gb,
            ROUND(SUM({used_expr})::numeric, 2)  AS used_gb
        FROM {full}
        WHERE db_id = %(db_id)s
          AND time >= CURRENT_DATE - INTERVAL '{days} days'
        GROUP BY tablespace_name, TO_CHAR(time, 'YYYY-MM-DD')
        ORDER BY tablespace_name, snap_day
    """.format(full=full, total_expr=total_expr, used_expr=used_expr, days=_TREND_DAYS)
    rows = _run_query(sql, {"db_id": db_id})

    trend = {}
    for r in rows:
        ts = r["ts_name"]
        total = float(r["total_gb"] or 0)
        used  = float(r["used_gb"]  or 0)
        trend.setdefault(ts, []).append({
            "date": r["snap_day"],
            "pct":  round(used / total * 100, 2) if total > 0 else 0,
            "used": used,
        })
    return trend


# ──────────────────────────────────────────────────────────────
# 통합 빌드 + 캐시
# ──────────────────────────────────────────────────────────────
def _build_data():
    global _cache, _cache_time

    with _build_lock:
        if _cache and (time.time() - _cache_time) < _CACHE_TTL_SEC:
            return _cache

        schemas   = _find_tablespace_schemas()
        instances = _get_instances()
        schema_map = {s.lower(): s for s in schemas}

        db_list = []
        ts_map  = {}

        def fetch_inst(inst):
            db_id  = inst["db_id"]
            name   = inst["instance_name"]
            biz    = inst.get("business_name") or "-"
            schema = schema_map.get(name.lower())
            if not schema:
                return None
            try:
                ts_data = _get_ts_data(schema, db_id)
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
                    "schema":      schema,
                    "total_gb":    round(total_gb, 2),
                    "used_gb":     round(used_gb,  2),
                    "used_pct_1w": round(avg_1w,   1),
                    "used_pct_1m": round(avg_1m,   1),
                })
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(fetch_inst, inst): inst for inst in instances}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    name, ts_data, row = result
                    db_list.append(row)
                    ts_map[name] = ts_data

        _cache = {
            "today":       datetime.now().strftime("%Y-%m-%d"),
            "dbs":         db_list,
            "tablespaces": ts_map,
        }
        _cache_time = time.time()
        return _cache


# ──────────────────────────────────────────────────────────────
# API 진입점 (Inspector.py routes → 이것들 호출)
# ──────────────────────────────────────────────────────────────
def api_tablespace_data():
    try:
        return json.dumps({"ok": True, "data": _build_data()})
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})


def api_tablespace_trend(path):
    """path: self.path (query string 포함). ?db=INSTANCE_NAME 필수."""
    from urllib.parse import urlparse, parse_qs
    qs = parse_qs(urlparse(path).query)
    db = (qs.get("db") or [""])[0]
    if not db:
        return json.dumps({"ok": False, "error": "missing db param"})
    try:
        schemas    = _find_tablespace_schemas()
        schema_map = {s.lower(): s for s in schemas}
        schema     = schema_map.get(db.lower())
        if not schema:
            return json.dumps({"ok": False, "error": "스키마 없음: " + db})

        instances = _get_instances()
        inst = next((i for i in instances if i["instance_name"] == db), None)
        if not inst:
            return json.dumps({"ok": False, "error": "인스턴스 없음: " + db})

        return json.dumps({
            "ok":    True,
            "db":    db,
            "trend": _get_trend(schema, inst["db_id"]),
        })
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})


def api_tablespace_refresh():
    global _cache, _cache_time
    _cache, _cache_time = None, 0.0
    try:
        return json.dumps({"ok": True, "data": _build_data()})
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})
