# -*- coding: utf-8 -*-
import json
import re
from html_helpers import _page, _page_title_html, _ts, _UTILS_BASE, _HELP
from db_utils import run_db_query_readonly, _parse_db_table
from html_helpers import _render_db_table_html


_ALLOWED_PREFIXES = ('SELECT', 'WITH', 'EXPLAIN', 'SHOW', 'VALUES', 'DESC', 'DESCRIBE')

# Hard cap on rows returned to the browser. Large result sets freeze the
# DOM/page; surface a truncation banner and let the operator add LIMIT.
MAX_SCRIPT_ROWS = 1000


def _strip_sql_comments(sql):
    """Remove /* ... */ block comments and -- line comments so the prefix
    check cannot be bypassed by a leading comment."""
    sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
    sql = re.sub(r'--[^\n]*', ' ', sql)
    return sql


def _validate_select_only(sql):
    """Return None if OK, else an error message. Every ';'-separated
    statement must start with an allowed read-only keyword."""
    cleaned = _strip_sql_comments(sql).strip()
    if not cleaned:
        return 'SQL이 입력되지 않았습니다.'
    for stmt in cleaned.split(';'):
        s = stmt.strip()
        if not s:
            continue
        first = s.split(None, 1)[0].upper()
        if first not in _ALLOWED_PREFIXES:
            return ('조회(SELECT) 전용 도구입니다. 허용되지 않는 명령어가 포함되어 있습니다: %s'
                    % first)
    return None


# ── API ───────────────────────────────────────────────────────────────────────────

def api_script_schemas():
    """Return available PG schemas (for search_path selector). Oracle returns empty."""
    from db_utils import _db_cfg, run_db_query
    if "postgres" not in _db_cfg().get("db_type", "").lower():
        return json.dumps({"ok": False, "schemas": []})
    sql = ("SELECT nspname FROM pg_namespace "
           "WHERE nspname NOT IN ('pg_catalog','information_schema','pg_toast','public') "
           "AND nspname NOT LIKE 'pg_temp%' AND nspname NOT LIKE 'pg_toast_temp%' "
           "ORDER BY nspname")
    out, err = run_db_query(sql)
    if err:
        return json.dumps({"ok": False, "error": err[:120], "schemas": []})
    from db_utils import _parse_db_table
    _, rows = _parse_db_table(out or "")
    schemas = [r[0].strip() for r in rows if r and r[0] and r[0].strip()]
    return json.dumps({"ok": True, "schemas": schemas})


def api_script_run(body_bytes):
    try:
        data = json.loads(body_bytes)
        sql  = (data.get('sql') or '').strip()
        schema = (data.get('schema') or '').strip()
    except Exception:
        return json.dumps({'ok': False, 'html': _err_card('잘못된 요청입니다.'), 'rows': 0})
    if not sql:
        return json.dumps({'ok': False, 'html': _err_card('SQL이 입력되지 않았습니다.'), 'rows': 0})
    verr = _validate_select_only(sql)
    if verr:
        return json.dumps({'ok': False, 'html': _err_card(verr), 'rows': 0})
    # Sanitize schema name (alphanumeric + underscore only)
    search_path = None
    if schema and not re.search(r'[^a-zA-Z0-9_]', schema):
        search_path = schema
    out, err, truncated = run_db_query_readonly(sql, max_rows=MAX_SCRIPT_ROWS,
                                                 search_path=search_path)
    if err:
        return json.dumps({'ok': False, 'html': _err_card(err), 'rows': 0})
    headers, rows = _parse_db_table(out or '')
    row_count = len(rows)
    tbl = _render_db_table_html(headers, rows)
    tbl = tbl.replace('<div class="tbl-wrap">', '', 1)
    if tbl.endswith('</div>'):
        tbl = tbl[:-6]
    banner = ''
    if truncated:
        banner = (
            '<div style="background:#FEF3C7;border:1px solid #FCD34D;color:#92400E;'
            'border-radius:6px;padding:8px 12px;margin-bottom:8px;font-size:.78rem;'
            'font-weight:500;">'
            '&#9888; 결과가 %d 행으로 잘렸습니다 (전체 행은 더 많음). '
            '브라우저 보호를 위해 서버에서 자동 절단합니다. '
            'LIMIT / WHERE 를 추가해 조회 범위를 좁혀주세요.'
            '</div>'
        ) % MAX_SCRIPT_ROWS
    rows_label = ('%d 행 (잘림)' % row_count) if truncated else ('%d 행' % row_count)
    html = (
        '%s'
        '<div style="font-size:.75rem;color:var(--c-muted);margin-bottom:8px;">%s</div>'
        '<div style="border:1px solid var(--bd);border-radius:8px;">%s</div>'
    ) % (banner, rows_label, tbl)
    return json.dumps({'ok': True, 'html': html, 'rows': row_count, 'truncated': truncated})




def _err_card(msg):
    return (
        '<div class="card">'
        '<div style="color:var(--err-c);background:var(--err-bg);border:1px solid var(--err-bd);'
        'border-radius:6px;padding:12px;font-size:.85rem;font-family:monospace;white-space:pre-wrap;">%s</div>'
        '</div>'
    ) % msg.replace('<', '&lt;').replace('>', '&gt;')
