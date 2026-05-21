# -*- coding: utf-8 -*-
import os
import sys
import re
import json

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
    _HAS_ORACLEDB = True
except Exception:
    _oracledb = None
    _HAS_ORACLEDB = False

try:
    import psycopg2 as _psycopg2
    _HAS_PSYCOPG2 = True
except Exception:
    _psycopg2 = None
    _HAS_PSYCOPG2 = False

from service_config import load_service_config


def _db_cfg():
    return load_service_config().get("repository", {})


# ── SQL directive stripping ──────────────────────────────────────────────────────

def _strip_oracle_directives(sql):
    """Strip sqlplus-specific directives (SET, COLUMN, WHENEVER, PROMPT, SPOOL)."""
    out = []
    for line in sql.split("\n"):
        s = line.strip().upper()
        if re.match(r"^(SET|COLUMN|WHENEVER|PROMPT|SPOOL|TTITLE|BTITLE)\s", s) or re.match(r"^EXIT[\s;]*$", s):
            continue
        out.append(line)
    return "\n".join(out)


def _strip_pg_directives(sql):
    """Strip psql meta-commands (\\pset, \\set, etc.)."""
    out = []
    for line in sql.split("\n"):
        if line.strip().startswith("\\"):
            continue
        out.append(line)
    return "\n".join(out)


def _split_pg_stmts(sql):
    """Split PostgreSQL SQL with PL/pgSQL function bodies into individual statements."""
    sql = _strip_pg_directives(sql)
    if "$$" not in sql:
        return [sql.strip()]
    m = re.search(r"\$\$\s+LANGUAGE\s+plpgsql\s*;", sql, re.IGNORECASE | re.DOTALL)
    if m:
        func_stmt = sql[:m.end()].strip()
        rest      = sql[m.end():].strip()
        stmts     = [func_stmt]
        if rest:
            stmts.append(rest)
        return stmts
    return [sql.strip()]


def _cursor_to_table_text(desc, rows):
    """Format cursor description + rows as psql border=1 style text."""
    if not desc:
        return ""
    headers  = [d[0] for d in desc]
    str_rows = [[str(v) if v is not None else "" for v in row] for row in rows]
    widths   = [len(h) for h in headers]
    for row in str_rows:
        for i, v in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(v))

    def fmt(vals):
        return " " + " | ".join(
            (str(v) if v is not None else "").ljust(widths[i])
            for i, v in enumerate(vals)
        ) + " "

    sep   = "+".join("-" * (w + 2) for w in widths)
    lines = [fmt(headers), sep]
    for row in str_rows:
        lines.append(fmt(row))
    return "\n".join(lines)


def _parse_db_table(text):
    """Parse psql (border=1) or sqlplus text output into (headers, rows)."""
    import re as _re
    lines   = text.splitlines()
    headers = []
    rows    = []
    sep_i   = None
    is_psql = False

    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        if _re.match(r'^[-+][-+ ]*$', s) and '+' in s:
            sep_i   = i
            is_psql = True
            break
        if _re.match(r'^[- ]+$', s) and s.count('-') >= 5:
            sep_i   = i
            is_psql = False
            break

    if sep_i is None or sep_i == 0:
        return headers, rows

    hdr_line = lines[sep_i - 1]

    if is_psql:
        raw_hdrs = hdr_line.split('|')
        headers  = [h.strip() for h in raw_hdrs if h.strip()]
        for line in lines[sep_i + 1:]:
            s = line.strip()
            if not s or s.startswith('('):
                continue
            cols = line.split('|')
            cols = [c.strip() for c in cols if c.strip() != '' or True]
            if cols and cols[0] == '':
                cols = cols[1:]
            if cols and cols[-1] == '':
                cols = cols[:-1]
            cols = [c.strip() for c in cols]
            if any(c for c in cols):
                rows.append(cols)
    else:
        sep       = lines[sep_i]
        positions = []
        start     = None
        for j, ch in enumerate(sep + ' '):
            if ch == '-' and start is None:
                start = j
            elif ch != '-' and start is not None:
                positions.append((start, j))
                start = None
        headers = [hdr_line[s:e].strip() if s < len(hdr_line) else '' for s, e in positions]
        for line in lines[sep_i + 1:]:
            if not line.strip():
                continue
            row = [line[s:e].strip() if s < len(line) else '' for s, e in positions]
            if any(row):
                rows.append(row)

    return headers, rows


# ── Oracle driver ────────────────────────────────────────────────────────────────

def _run_oracle(sql_body):
    if not _HAS_ORACLEDB:
        return None, "oracledb driver not installed. Run python-utils/drivers/install.sh"
    repo   = _db_cfg()
    user   = repo.get("user", "")
    passwd = repo.get("password", "")
    host   = repo.get("ip", "")
    port   = int(repo.get("port", "1521") or "1521")
    sid    = repo.get("sid", "")
    if not all([user, passwd, host, sid]):
        return None, "Repository DB not configured. Go to Configuration."
    try:
        conn = _oracledb.connect(
            user=user, password=passwd,
            host=host, port=port, service_name=sid)
        conn.call_timeout = 30000
        cur  = conn.cursor()
        cur.execute("ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD HH24:MI:SS'")
        _tmp = _strip_oracle_directives(sql_body).strip()
        clean = _tmp if _tmp.upper().startswith("BEGIN") or _tmp.upper().startswith("CREATE") else _tmp.rstrip(";").strip()
        cur.execute(clean)
        rows = cur.fetchall()
        text = _cursor_to_table_text(cur.description, rows)
        cur.close()
        conn.close()
        return text, None
    except Exception as e:
        return None, "Oracle error: " + str(e)


# ── PostgreSQL driver ─────────────────────────────────────────────────────────────

def _run_pg(sql_body):
    if not _HAS_PSYCOPG2:
        return None, "psycopg2 driver not installed. Run python-utils/drivers/install.sh"
    repo   = _db_cfg()
    user   = repo.get("user", "")
    passwd = repo.get("password", "")
    host   = repo.get("ip", "")
    port   = int(repo.get("port", "5432") or "5432")
    dbname = repo.get("sid", "")
    if not all([user, host, dbname]):
        return None, "Repository DB not configured. Go to Configuration."
    try:
        conn = _psycopg2.connect(
            host=host, port=port, user=user, password=passwd, dbname=dbname,
            connect_timeout=30)
        conn.autocommit = True
        cur        = conn.cursor()
        cur.execute("SET statement_timeout = '30s'")
        last_desc  = None
        last_rows  = []
        for stmt in _split_pg_stmts(sql_body):
            if stmt.strip():
                cur.execute(stmt)
                if cur.description:
                    last_desc = cur.description
                    last_rows = cur.fetchall()
        text = _cursor_to_table_text(last_desc, last_rows) if last_desc else ""
        cur.close()
        conn.close()
        return text, None
    except Exception as e:
        return None, "PG error: " + str(e)


def run_db_query(sql_body):
    db_type = _db_cfg().get("db_type", "Oracle").lower()
    if "oracle" in db_type:
        return _run_oracle(sql_body)
    elif "postgres" in db_type:
        return _run_pg(sql_body)
    return None, "Unsupported DB type: " + _db_cfg().get("db_type", "")


# ── Read-only executor (Script Manager) ─────────────────────────────────────────

def run_db_query_readonly(sql_body, max_rows=None, search_path=None):
    """Execute SQL inside a READ ONLY transaction. Used by Script Manager.
    DB itself rejects any write statement (DML/DDL).

    Returns (text, err, truncated) — truncated is True when the result was
    capped at max_rows. When max_rows is None, no cap (legacy behavior).
    search_path (PG only): if set, executes SET search_path TO <schema>."""
    db_type = _db_cfg().get("db_type", "Oracle").lower()
    if "oracle" in db_type:
        return _run_oracle_readonly(sql_body, max_rows)
    elif "postgres" in db_type:
        return _run_pg_readonly(sql_body, max_rows, search_path=search_path)
    return None, "Unsupported DB type: " + _db_cfg().get("db_type", ""), False


def _fetch_capped(cur, max_rows):
    """fetchmany(max_rows+1) so we know whether more rows existed.
    Returns (rows, truncated). max_rows=None means no cap."""
    if max_rows is None:
        return cur.fetchall(), False
    rows = cur.fetchmany(max_rows + 1)
    if len(rows) > max_rows:
        return rows[:max_rows], True
    return rows, False


def _run_oracle_readonly(sql_body, max_rows=None):
    if not _HAS_ORACLEDB:
        return None, "oracledb driver not installed. Run python-utils/drivers/install.sh", False
    repo   = _db_cfg()
    user   = repo.get("user", "")
    passwd = repo.get("password", "")
    host   = repo.get("ip", "")
    port   = int(repo.get("port", "1521") or "1521")
    sid    = repo.get("sid", "")
    if not all([user, passwd, host, sid]):
        return None, "Repository DB not configured. Go to Configuration.", False
    conn = None
    try:
        conn = _oracledb.connect(
            user=user, password=passwd,
            host=host, port=port, service_name=sid)
        conn.call_timeout = 30000
        cur = conn.cursor()
        if max_rows is not None:
            cur.arraysize = min(max_rows + 1, 1000)
        cur.execute("ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD HH24:MI:SS'")
        cur.execute("SET TRANSACTION READ ONLY")
        _tmp  = _strip_oracle_directives(sql_body).strip()
        clean = _tmp.rstrip(";").strip()
        cur.execute(clean)
        if cur.description is None:
            cur.close(); conn.rollback(); conn.close()
            return None, "Only SELECT statements are allowed.", False
        rows, truncated = _fetch_capped(cur, max_rows)
        text = _cursor_to_table_text(cur.description, rows)
        cur.close()
        conn.rollback()
        conn.close()
        return text, None, truncated
    except Exception as e:
        try:
            if conn is not None:
                conn.rollback(); conn.close()
        except Exception:
            pass
        msg = str(e)
        if "ORA-01456" in msg or "ORA-01453" in msg:
            return None, "Only SELECT statements are allowed (read-only transaction).", False
        return None, "Oracle error: " + msg, False


def _run_pg_readonly(sql_body, max_rows=None, search_path=None):
    if not _HAS_PSYCOPG2:
        return None, "psycopg2 driver not installed. Run python-utils/drivers/install.sh", False
    repo   = _db_cfg()
    user   = repo.get("user", "")
    passwd = repo.get("password", "")
    host   = repo.get("ip", "")
    port   = int(repo.get("port", "5432") or "5432")
    dbname = repo.get("sid", "")
    if not all([user, host, dbname]):
        return None, "Repository DB not configured. Go to Configuration.", False
    conn = None
    try:
        conn = _psycopg2.connect(
            host=host, port=port, user=user, password=passwd, dbname=dbname,
            connect_timeout=30)
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '30s'")
        if search_path:
            cur.execute("SET search_path TO %s, public" % search_path)
        cur.execute("SET TRANSACTION READ ONLY")
        last_desc = None
        last_rows = []
        truncated = False
        for stmt in _split_pg_stmts(sql_body):
            if stmt.strip():
                cur.execute(stmt)
                if cur.description:
                    last_desc = cur.description
                    last_rows, truncated = _fetch_capped(cur, max_rows)
        text = _cursor_to_table_text(last_desc, last_rows) if last_desc else ""
        cur.close()
        conn.rollback()
        conn.close()
        return text, None, truncated
    except Exception as e:
        try:
            if conn is not None:
                conn.rollback(); conn.close()
        except Exception:
            pass
        msg = str(e)
        if "read-only transaction" in msg.lower():
            return None, "Only SELECT statements are allowed (read-only transaction).", False
        return None, "PG error: " + msg, False


# ── DDL / anonymous block executor (no result set) ──────────────────────────────

def run_db_exec(sql_body):
    """Execute SQL/PL-SQL without expecting a result set (DDL, anonymous blocks)."""
    db_type = _db_cfg().get("db_type", "Oracle").lower()
    if "oracle" in db_type:
        return _exec_oracle(sql_body)
    elif "postgres" in db_type:
        return _exec_pg(sql_body)
    return "Unsupported DB type: " + _db_cfg().get("db_type", "")


def _exec_oracle(sql_body):
    if not _HAS_ORACLEDB:
        return "oracledb driver not installed. Run python-utils/drivers/install.sh"
    repo   = _db_cfg()
    user   = repo.get("user", "")
    passwd = repo.get("password", "")
    host   = repo.get("ip", "")
    port   = int(repo.get("port", "1521") or "1521")
    sid    = repo.get("sid", "")
    if not all([user, passwd, host, sid]):
        return "Repository DB not configured. Go to Configuration."
    try:
        conn  = _oracledb.connect(user=user, password=passwd,
                                   host=host, port=port, service_name=sid)
        conn.call_timeout = 30000
        cur   = conn.cursor()
        _tmp = _strip_oracle_directives(sql_body).strip()
        clean = _tmp if _tmp.upper().startswith("BEGIN") or _tmp.upper().startswith("CREATE") else _tmp.rstrip(";").strip()
        cur.execute(clean)
        conn.commit()
        cur.close()
        conn.close()
        return None  # None = success
    except Exception as e:
        return "Oracle error: " + str(e)


def _exec_pg(sql_body):
    if not _HAS_PSYCOPG2:
        return "psycopg2 driver not installed. Run python-utils/drivers/install.sh"
    repo   = _db_cfg()
    user   = repo.get("user", "")
    passwd = repo.get("password", "")
    host   = repo.get("ip", "")
    port   = int(repo.get("port", "5432") or "5432")
    dbname = repo.get("sid", "")
    if not all([user, host, dbname]):
        return "Repository DB not configured. Go to Configuration."
    try:
        conn = _psycopg2.connect(host=host, port=port, user=user,
                                  password=passwd, dbname=dbname,
                                  connect_timeout=30)
        conn.autocommit = True
        cur  = conn.cursor()
        cur.execute("SET statement_timeout = '30s'")
        for stmt in _split_pg_stmts(sql_body):
            if stmt.strip():
                cur.execute(stmt)
        cur.close()
        conn.close()
        return None
    except Exception as e:
        return "PG error: " + str(e)





# ── PG: insp_xxx() function definition lookup for Ctrl+Shift+S popup ─────────
# 페이지에서 SELECT * FROM insp_session_check() 같이 함수를 호출할 때, 팝업에
# 함수 본문 정의도 같이 보여주기 위한 헬퍼. 함수 정의는 거의 안 바뀌므로
# 프로세스 메모리에 캐싱(없음도 캐싱하여 반복 DB hit 방지).
_PG_FN_DEF_CACHE = {}  # fn_name(lower) -> list[(schema, definition)] or []

def _pg_function_defs(fn_name):
    """Return [(schema, pg_get_functiondef), ...] for matching function name.
    Cached in-process. Returns [] when DB is not PG, on error, or no match."""
    key = fn_name.lower()
    if key in _PG_FN_DEF_CACHE:
        return _PG_FN_DEF_CACHE[key]
    result = []
    if not _HAS_PSYCOPG2:
        _PG_FN_DEF_CACHE[key] = result
        return result
    repo = _db_cfg()
    if 'postgres' not in repo.get('db_type', '').lower():
        _PG_FN_DEF_CACHE[key] = result
        return result
    try:
        conn = _psycopg2.connect(
            host=repo.get('ip', ''),
            port=int(repo.get('port', '5432') or '5432'),
            user=repo.get('user', ''),
            password=repo.get('password', ''),
            dbname=repo.get('sid', ''),
            connect_timeout=5)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '5s'")
        cur.execute(
            "SELECT n.nspname, pg_get_functiondef(p.oid) "
            "  FROM pg_proc p "
            "  JOIN pg_namespace n ON n.oid = p.pronamespace "
            " WHERE lower(p.proname) = %s "
            "   AND n.nspname NOT IN ('pg_catalog','information_schema') "
            " ORDER BY n.nspname LIMIT 5",
            (key,))
        for sch, defn in cur.fetchall():
            if defn:
                result.append((sch, defn))
        cur.close()
        conn.close()
    except Exception:
        pass
    _PG_FN_DEF_CACHE[key] = result
    return result


def _sql_embed(sql, sections=None):
    """Embed SQL for the Ctrl+Shift+S popup (directives stripped).

    sql : main SQL text shown without a chip header.
    sections : optional list of {'title': str, 'body': str} — 각 항목은 QUERY 칩
               헤더와 함께 별도 블록으로 렌더(라이선스 확인 탭처럼 여러 SQL 을
               동시에 보여줄 때 사용). function 정의 표시 방식과 동일한 톤.

    Emits three globals:
      window.__PAGE_SQL__         : str   (main SQL)
      window.__PAGE_SQL_SECTIONS__: list  ({title, body})
      window.__PAGE_SQL_FNS__     : list  ({schema, name, def}) — PG insp_xxx() 자동 첨부
    """
    def _clean(s):
        return _strip_pg_directives(_strip_oracle_directives(s or '')).strip()

    clean      = _clean(sql)
    sections   = sections or []
    sec_clean  = [{'title': str(s.get('title', '')), 'body': _clean(s.get('body', ''))} for s in sections]

    if not clean and not sec_clean:
        return ''

    # PG insp_xxx() 함수 탐지 (메인 SQL + 모든 section body 통합)
    fns = []
    if 'postgres' in _db_cfg().get('db_type', '').lower():
        all_text = '\n'.join([clean] + [s['body'] for s in sec_clean])
        seen = set()
        for m in re.finditer(r'\b(insp_\w+)\s*\(', all_text, re.IGNORECASE):
            n = m.group(1).lower()
            if n in seen:
                continue
            seen.add(n)
            for sch, defn in _pg_function_defs(n):
                fns.append({'schema': sch, 'name': n, 'def': defn})

    return (
        '<script>'
        'window.__PAGE_SQL__='          + json.dumps(clean)     + ';'
        'window.__PAGE_SQL_SECTIONS__=' + json.dumps(sec_clean) + ';'
        'window.__PAGE_SQL_FNS__='      + json.dumps(fns)       + ';'
        '</script>'
    )
