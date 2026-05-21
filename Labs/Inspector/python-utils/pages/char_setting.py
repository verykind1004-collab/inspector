# -*- coding: utf-8 -*-
"""Char Setting tool — bulk-update CHARSET for selected instances.

Updates two tables in the Repository DB:
  - apm_web_env.value where env_key='CHARSET'  (insert if missing)
  - apm_db_info.char_set

Supported NLS_CHARACTERSET → (apm_web_env.value, apm_db_info.char_set):
  KO16KSC5601 / KO16MSWIN949 → (EUCKR, CP949)
  UTF8 / AL32UTF8            → (UTF-8, UTF-8)
  JA16SJIS                   → (EUCJP, MS932)
  ZHS16GBK                   → (EUCCN, CP936)

Works against Oracle or PostgreSQL repository (selected by service_config.db_type).
"""
import json
import os
import sys
import glob

# ── bundled drivers (Labs/drivers) ───────────────────────────────────────────
_LABS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_py3_sites = glob.glob(
    os.path.join(_LABS_DIR, 'drivers', 'python3', 'lib', 'python3.*', 'site-packages'))
if _py3_sites and _py3_sites[0] not in sys.path:
    sys.path.insert(0, _py3_sites[0])

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


_NLS_MAP = {
    'KO16KSC5601':  ('EUCKR', 'CP949'),
    'KO16MSWIN949': ('EUCKR', 'CP949'),
    'UTF8':         ('UTF-8', 'UTF-8'),
    'AL32UTF8':     ('UTF-8', 'UTF-8'),
    'JA16SJIS':     ('EUCJP', 'MS932'),
    'ZHS16GBK':     ('EUCCN', 'CP936'),
}


def _repo():
    return load_service_config().get('repository', {})


def _is_oracle(repo):
    return 'oracle' in (repo.get('db_type', '') or '').lower()


def _is_pg(repo):
    return 'postgres' in (repo.get('db_type', '') or '').lower()


# ── connection helpers ──────────────────────────────────────────────────────

def _connect():
    """Open a Repository connection with autocommit OFF.
    Returns (conn, dialect, err). dialect ∈ {'oracle','pg'}."""
    repo = _repo()
    if _is_oracle(repo):
        if not _HAS_ORACLEDB:
            return None, '', 'oracledb driver not installed'
        host = repo.get('ip', ''); user = repo.get('user', '')
        passwd = repo.get('password', ''); sid = repo.get('sid', '')
        port = int(repo.get('port', '1521') or '1521')
        if not all([host, user, sid]):
            return None, '', 'Repository DB not configured'
        try:
            conn = _oracledb.connect(
                user=user, password=passwd,
                host=host, port=port, service_name=sid)
            conn.call_timeout = 30000
            conn.autocommit = False
            return conn, 'oracle', None
        except Exception as e:
            return None, '', 'Oracle connect failed: ' + str(e)
    if _is_pg(repo):
        if not _HAS_PSYCOPG2:
            return None, '', 'psycopg2 driver not installed'
        host = repo.get('ip', ''); user = repo.get('user', '')
        passwd = repo.get('password', ''); dbname = repo.get('sid', '')
        port = int(repo.get('port', '5432') or '5432')
        if not all([host, user, dbname]):
            return None, '', 'Repository DB not configured'
        try:
            conn = _psycopg2.connect(
                host=host, port=port, user=user, password=passwd, dbname=dbname,
                connect_timeout=30)
            conn.autocommit = False
            cur = conn.cursor()
            cur.execute("SET statement_timeout = '30s'")
            cur.close()
            return conn, 'pg', None
        except Exception as e:
            return None, '', 'PG connect failed: ' + str(e)
    return None, '', 'Unsupported repository db_type: ' + str(repo.get('db_type', ''))


# ── GET: instance list ──────────────────────────────────────────────────────

def api_char_setting_instances():
    conn, dialect, err = _connect()
    if err:
        return json.dumps({'ok': False, 'error': err})
    try:
        cur = conn.cursor()
        cur.execute('SELECT db_id, instance_name FROM apm_db_info ORDER BY instance_name')
        items = [{'db_id': int(r[0]), 'instance_name': r[1]} for r in cur.fetchall() if r[0] is not None]
        cur.close()
        return json.dumps({'ok': True, 'items': items})
    except Exception as e:
        return json.dumps({'ok': False, 'error': 'Query failed: ' + str(e)[:300]})
    finally:
        try: conn.close()
        except Exception: pass


# ── POST: bulk update ───────────────────────────────────────────────────────

def _parse_ids(raw):
    out = []
    for v in raw or []:
        try:
            out.append(int(v))
        except Exception:
            return None
    # dedupe, preserve order
    seen = set(); uniq = []
    for x in out:
        if x not in seen:
            seen.add(x); uniq.append(x)
    return uniq


def _in_clause_oracle(cur, ids, name='id'):
    """Build ':id0,:id1,...' placeholder + binds for Oracle IN clause."""
    binds = {}
    parts = []
    for i, v in enumerate(ids):
        k = '%s%d' % (name, i)
        binds[k] = v
        parts.append(':' + k)
    return ','.join(parts), binds


def api_char_setting_update(raw_body):
    try:
        data = json.loads(raw_body.decode('utf-8') if isinstance(raw_body, (bytes, bytearray)) else raw_body)
    except Exception:
        return json.dumps({'ok': False, 'error': 'Invalid JSON'})

    nls = (data.get('nls') or '').strip()
    if nls not in _NLS_MAP:
        return json.dumps({'ok': False, 'error': 'Invalid NLS: ' + nls})
    web_val, char_val = _NLS_MAP[nls]

    db_ids = _parse_ids(data.get('db_ids'))
    if not db_ids:
        return json.dumps({'ok': False, 'error': 'No db_ids selected'})

    conn, dialect, err = _connect()
    if err:
        return json.dumps({'ok': False, 'error': err})

    try:
        cur = conn.cursor()

        # 1) which db_ids already have a CHARSET row?
        if dialect == 'oracle':
            in_sql, binds = _in_clause_oracle(cur, db_ids)
            cur.execute(
                "SELECT db_id FROM apm_web_env WHERE env_key='CHARSET' AND db_id IN (" + in_sql + ")",
                binds)
        else:
            cur.execute(
                "SELECT db_id FROM apm_web_env WHERE env_key='CHARSET' AND db_id = ANY(%s)",
                (db_ids,))
        existing = sorted({int(r[0]) for r in cur.fetchall()})
        missing = [x for x in db_ids if x not in set(existing)]

        web_updated = 0
        web_inserted = 0
        info_updated = 0

        # 2) UPDATE existing apm_web_env rows
        if existing:
            if dialect == 'oracle':
                in_sql, binds = _in_clause_oracle(cur, existing)
                binds['v'] = web_val
                cur.execute(
                    "UPDATE apm_web_env SET value = :v "
                    "WHERE env_key = 'CHARSET' AND db_id IN (" + in_sql + ")",
                    binds)
            else:
                cur.execute(
                    "UPDATE apm_web_env SET value = %s "
                    "WHERE env_key = 'CHARSET' AND db_id = ANY(%s)",
                    (web_val, existing))
            web_updated = cur.rowcount or 0

        # 3) INSERT missing apm_web_env rows (USER_ID=NULL, CATEGORY=2)
        if missing:
            if dialect == 'oracle':
                cur.executemany(
                    "INSERT INTO apm_web_env (user_id, db_id, env_key, value, category) "
                    "VALUES (NULL, :db_id, 'CHARSET', :v, 2)",
                    [{'db_id': x, 'v': web_val} for x in missing])
                web_inserted = cur.rowcount or len(missing)
            else:
                cur.executemany(
                    "INSERT INTO apm_web_env (user_id, db_id, env_key, value, category) "
                    "VALUES (NULL, %s, 'CHARSET', %s, 2)",
                    [(x, web_val) for x in missing])
                web_inserted = len(missing)

        # 4) UPDATE apm_db_info.char_set
        if dialect == 'oracle':
            in_sql, binds = _in_clause_oracle(cur, db_ids)
            binds['c'] = char_val
            cur.execute(
                "UPDATE apm_db_info SET char_set = :c WHERE db_id IN (" + in_sql + ")",
                binds)
        else:
            cur.execute(
                "UPDATE apm_db_info SET char_set = %s WHERE db_id = ANY(%s)",
                (char_val, db_ids))
        info_updated = cur.rowcount or 0

        conn.commit()
        cur.close()
        return json.dumps({
            'ok': True,
            'nls': nls,
            'web_env_value': web_val,
            'char_set_value': char_val,
            'web_env_updated': web_updated,
            'web_env_inserted': web_inserted,
            'db_info_updated': info_updated,
            'selected_count': len(db_ids),
        })
    except Exception as e:
        try: conn.rollback()
        except Exception: pass
        return json.dumps({'ok': False, 'error': 'Update failed: ' + str(e)[:300]})
    finally:
        try: conn.close()
        except Exception: pass
