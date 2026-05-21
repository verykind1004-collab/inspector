# -*- coding: utf-8 -*-
"""Config Dump - Export MaxGauge configuration tables as JSON + SQL."""
import json
import sys
import os
from datetime import datetime, date
from decimal import Decimal

# bundled drivers (Labs/drivers, Labs 공용)
import glob as _glob
_LABS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_py3_sites = _glob.glob(
    os.path.join(_LABS_DIR, 'drivers', 'python3', 'lib', 'python3.*', 'site-packages'))
if _py3_sites and _py3_sites[0] not in sys.path:
    sys.path.insert(0, _py3_sites[0])
del _glob, _py3_sites, _LABS_DIR

from service_config import load_service_config
from html_helpers import _page, _page_title_html, _ts, _UTILS_BASE, _HELP


# ── Menu definitions ──────────────────────────────────────────────────────────

MENU_DEFS = {
    "instance": {
        "label": "Instance Management",
        "tables": [
            "ora_service_name", "apm_db_info", "ora_service_info",
            "ora_lc_config", "ora_rac_group_name", "ora_exa_info",
            "ora_rule_base_config", "apm_license_db_info", "apm_license_trial_db",
        ],
        "sequences": ["apm_db_seq", "ora_service_name_seq"],
    },
    "account": {
        "label": "Account Management",
        "tables": [
            "apm_user_list", "apm_users_db_list", "apm_users_ip_list",
            "apm_web_env", "ora_user_pwd_policy",
        ],
        "sequences": [],
    },
    "alert": {
        "label": "Alert Management",
        "tables": [
            "apm_alert_server_set", "apm_alert_server_tag_value",
            "apm_custom_alert_value", "apm_cell_alert_set",
            "apm_cell_alert_tag_value", "apm_health_set",
            "apm_health_tag_value", "apm_smart_alert_server_set",
            "apm_alert_user_sql", "apm_alert_user_script", "ora_alertlog_info",
        ],
        "sequences": ["apm_alert_user_sql_seq", "apm_alert_user_script_seq"],
    },
    "sms": {
        "label": "SMS Management",
        "tables": [
            "sms_group_name", "sms_group_info", "sms_user_info",
            "sms_group_alert_list", "sms_cell_group_alert_list",
            "apm_alert_sms_schedule", "apm_smart_alert_schedule",
        ],
        "sequences": [],
    },
    "repository": {
        "label": "Repository Configuration",
        "tables": [
            "apm_partition_manage", "apm_string_data_use_list",
            "apm_string_data", "ora_app_call_tree_info", "apm_product_option",
        ],
        "sequences": [],
    },
}

SEQ_TABLE_MAP = {
    "apm_db_seq":                ("apm_db_info",           "db_id"),
    "ora_service_name_seq":      ("ora_service_name",      "service_id"),
    "apm_alert_user_sql_seq":    ("apm_alert_user_sql",    "id"),
    "apm_alert_user_script_seq": ("apm_alert_user_script", "id"),
}


# ── DB helpers ────────────────────────────────────────────────────────────────

def _connect():
    cfg = load_service_config().get("repository", {})
    db_type = "pg" if "postgres" in cfg.get("db_type", "Oracle").lower() else "oracle"
    if db_type == "pg":
        import psycopg2
        conn = psycopg2.connect(
            host=cfg.get("ip", ""), port=int(cfg.get("port", "5432") or "5432"),
            user=cfg.get("user", ""), password=cfg.get("password", ""),
            dbname=cfg.get("sid", ""))
        conn.autocommit = True
        return conn, "pg"
    else:
        import oracledb
        conn = oracledb.connect(
            user=cfg.get("user", ""), password=cfg.get("password", ""),
            host=cfg.get("ip", ""), port=int(cfg.get("port", "1521") or "1521"),
            service_name=cfg.get("sid", ""))
        return conn, "oracle"


def _json_safe(val):
    if val is None:
        return None
    if isinstance(val, (int, float, bool)):
        return val
    if isinstance(val, Decimal):
        return float(val) if val % 1 else int(val)
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, memoryview):
        return bytes(val).decode("utf-8", errors="replace")
    if hasattr(val, 'read'):
        return val.read()
    return str(val)


def _sql_literal(val, db_type):
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return ("TRUE" if val else "FALSE") if db_type == "pg" else ("1" if val else "0")
    if isinstance(val, (int, float, Decimal)):
        return str(val)
    if isinstance(val, datetime):
        s = val.strftime("%Y-%m-%d %H:%M:%S")
        return "TO_TIMESTAMP('%s','YYYY-MM-DD HH24:MI:SS')" % s if db_type == "oracle" else "'%s'" % s
    if isinstance(val, date):
        s = val.strftime("%Y-%m-%d")
        return "TO_DATE('%s','YYYY-MM-DD')" % s if db_type == "oracle" else "'%s'" % s
    if isinstance(val, (bytes, memoryview)):
        val = bytes(val).decode("utf-8", errors="replace")
    if hasattr(val, 'read'):
        val = val.read()
    s = str(val).replace("'", "''")
    if db_type == "oracle":
        import re
        if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', s):
            return "TO_TIMESTAMP('%s','YYYY-MM-DD HH24:MI:SS')" % s
        if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
            return "TO_DATE('%s','YYYY-MM-DD')" % s
    return "'%s'" % s


def _table_exists(cur, table_name, db_type):
    if db_type == "pg":
        cur.execute("SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name=%s", (table_name,))
    else:
        cur.execute("SELECT 1 FROM user_tables WHERE table_name=:1",
                    (table_name.upper(),))
    return cur.fetchone() is not None


def _dump_table(cur, table_name, db_type):
    if not _table_exists(cur, table_name, db_type):
        return None
    if db_type == "oracle":
        cur.execute("ALTER SESSION SET NLS_DATE_FORMAT='YYYY-MM-DD HH24:MI:SS'")
        cur.execute("SELECT * FROM %s" % table_name.upper())
    else:
        cur.execute("SELECT * FROM public.%s" % table_name)
    columns = [d[0].lower() for d in cur.description]
    rows = [[_json_safe(v) for v in row] for row in cur.fetchall()]
    return {"columns": columns, "rows": rows, "count": len(rows)}


def _get_seq_value(cur, seq_name, db_type):
    info = SEQ_TABLE_MAP.get(seq_name)
    if not info:
        return 0
    table, col = info
    try:
        if db_type == "pg":
            cur.execute("SELECT COALESCE(MAX(%s),0) FROM public.%s" % (col, table))
        else:
            cur.execute("SELECT NVL(MAX(%s),0) FROM %s" % (col, table.upper()))
        row = cur.fetchone()
        return int(row[0]) if row and row[0] else 0
    except Exception:
        return 0


# ── SQL generation ────────────────────────────────────────────────────────────

def _generate_sql(dump_data, db_type):
    lines = []
    info = dump_data.get("dump_info", {})
    lines.append("-- MaxGauge Config Dump")
    lines.append("-- Generated: %s" % info.get("created_at", ""))
    lines.append("-- Source: %s" % info.get("source_db", ""))
    lines.append("-- Menus: %s" % ", ".join(info.get("menu_labels", [])))
    lines.append("--")
    lines.append("-- WARNING: This SQL assumes the target has the SAME schema version.")
    lines.append("-- For cross-version migration, use the JSON file instead.")
    lines.append("")
    lines.append("BEGIN;" if db_type == "pg" else "-- Transaction Start")
    if db_type == "oracle":
        lines.append("ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD HH24:MI:SS';")
        lines.append("ALTER SESSION SET NLS_TIMESTAMP_FORMAT = 'YYYY-MM-DD HH24:MI:SS';")
    lines.append("")

    # Collect tables with data
    table_items = []
    for tname, tdata in dump_data.get("tables", {}).items():
        if not tdata or not tdata.get("rows"):
            lines.append("-- %s: 0 rows (skip)" % tname)
            lines.append("")
            continue
        table_items.append((tname, tdata))

    # Phase 1: DELETE in REVERSE order (children first, avoids FK violations)
    lines.append("-- DELETE (reverse order for FK safety)")
    for tname, tdata in reversed(table_items):
        tbl = ("public.%s" % tname) if db_type == "pg" else tname.upper()
        lines.append("DELETE FROM %s;" % tbl)
    lines.append("")

    # Phase 2: INSERT in FORWARD order (parents first)
    for tname, tdata in table_items:
        cols = tdata["columns"]
        tbl = ("public.%s" % tname) if db_type == "pg" else tname.upper()
        col_list = ", ".join(cols) if db_type == "pg" else ", ".join(c.upper() for c in cols)
        lines.append("-- %s: %d rows" % (tname, len(tdata["rows"])))
        for row in tdata["rows"]:
            vals = ", ".join(_sql_literal(v, db_type) for v in row)
            lines.append("INSERT INTO %s (%s) VALUES (%s);" % (tbl, col_list, vals))
        lines.append("")

    seqs = dump_data.get("sequences", {})
    if seqs:
        lines.append("-- Sequence reset")
        for sname, sval in seqs.items():
            if db_type == "pg":
                lines.append("SELECT setval('%s', %d);" % (sname, max(sval, 1)))
            else:
                lines.append("-- Oracle: ALTER SEQUENCE %s or verify current value >= %d"
                             % (sname.upper(), sval))
        lines.append("")

    lines.append("COMMIT;")
    return "\n".join(lines)


# ── API ───────────────────────────────────────────────────────────────────────

def api_config_dump(raw_body):
    try:
        body = json.loads(raw_body.decode("utf-8", errors="ignore"))
    except Exception:
        return json.dumps({"ok": False, "error": "Invalid request body"})

    menus = [m for m in body.get("menus", []) if m in MENU_DEFS]
    if not menus:
        return json.dumps({"ok": False, "error": "No valid menus selected"})

    try:
        conn, db_type = _connect()
    except Exception as e:
        return json.dumps({"ok": False, "error": "DB connection failed: %s" % str(e)[:200]})

    try:
        cur = conn.cursor()
        all_tables, all_seqs, menu_labels = [], [], []
        seen_t, seen_s = set(), set()
        for m in menus:
            d = MENU_DEFS[m]
            menu_labels.append(d["label"])
            for t in d["tables"]:
                if t not in seen_t:
                    seen_t.add(t); all_tables.append(t)
            for s in d["sequences"]:
                if s not in seen_s:
                    seen_s.add(s); all_seqs.append(s)

        tables_data = {}
        stats = {"tables": 0, "rows": 0, "skipped": []}
        for tname in all_tables:
            result = _dump_table(cur, tname, db_type)
            if result is None:
                stats["skipped"].append(tname)
            else:
                tables_data[tname] = result
                stats["tables"] += 1
                stats["rows"] += result["count"]

        seqs_data = {}
        for sname in all_seqs:
            seqs_data[sname] = _get_seq_value(cur, sname, db_type)

        cur.close()
        conn.close()

        cfg = load_service_config().get("repository", {})
        dump_data = {
            "dump_info": {
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source_db": "%s:%s/%s (%s)" % (
                    cfg.get("ip", ""), cfg.get("port", ""),
                    cfg.get("sid", ""), cfg.get("db_type", "")),
                "db_type": db_type,
                "menus": menus,
                "menu_labels": menu_labels,
                "version": "1.0",
            },
            "tables": tables_data,
            "sequences": seqs_data,
        }

        json_content = json.dumps(dump_data, ensure_ascii=False, indent=2)
        sql_content = _generate_sql(dump_data, db_type)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        return json.dumps({
            "ok": True, "stats": stats,
            "json_content": json_content, "sql_content": sql_content,
            "filename_base": "config_dump_%s" % ts, "db_type": db_type,
        }, ensure_ascii=False)
    except Exception as e:
        import traceback
        return json.dumps({"ok": False, "error": str(e)[:300],
                           "trace": traceback.format_exc()[:500]})
    finally:
        try:
            conn.close()
        except Exception:
            pass




def _get_target_columns(cur, table_name, db_type):
    """Get column list from target DB for a table."""
    if db_type == "pg":
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s "
            "ORDER BY ordinal_position", (table_name,))
    else:
        cur.execute(
            "SELECT COLUMN_NAME FROM USER_TAB_COLUMNS "
            "WHERE TABLE_NAME=:1 ORDER BY COLUMN_ID", (table_name.upper(),))
    return [r[0].lower() for r in cur.fetchall()]


def _get_target_column_types(cur, table_name, db_type):
    """Get column name -> data_type map from target DB."""
    if db_type == "pg":
        cur.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s", (table_name,))
    else:
        cur.execute(
            "SELECT COLUMN_NAME, DATA_TYPE FROM USER_TAB_COLUMNS "
            "WHERE TABLE_NAME=:1", (table_name.upper(),))
    return {r[0].lower(): r[1].upper() for r in cur.fetchall()}


def api_config_restore(raw_body):
    import re
    """Restore config from uploaded JSON dump file.
    Phase 1: DELETE all tables in reverse order (children first) to avoid FK violations.
    Phase 2: INSERT all tables in forward order (parents first).
    All within a single transaction — rollback on any error.
    """
    try:
        dump_data = json.loads(raw_body.decode("utf-8", errors="ignore"))
    except Exception:
        return json.dumps({"ok": False, "error": "Invalid JSON file"})

    if "tables" not in dump_data or "dump_info" not in dump_data:
        return json.dumps({"ok": False, "error": "Invalid dump format: missing tables or dump_info"})

    try:
        conn, db_type = _connect()
    except Exception as e:
        return json.dumps({"ok": False, "error": "DB connection failed: %s" % str(e)[:200]})

    results = []
    total_inserted = 0
    total_skipped_cols = {}

    try:
        # Oracle: disable autocommit for transactional restore
        if db_type == "pg":
            conn.autocommit = False

        cur = conn.cursor()
        if db_type == "oracle":
            cur.execute("ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD HH24:MI:SS'")
            cur.execute("ALTER SESSION SET NLS_TIMESTAMP_FORMAT = 'YYYY-MM-DD HH24:MI:SS'")

        # ── Pre-scan: build table metadata in forward order ──────────────
        table_order = []  # (tname, tdata, tbl, col_list, common, common_idx, col_types, src_only, tgt_only)
        for tname, tdata in dump_data.get("tables", {}).items():
            if not tdata or not tdata.get("rows"):
                results.append({"table": tname, "status": "skip", "reason": "no rows", "inserted": 0})
                continue

            src_cols = [c.lower() for c in tdata["columns"]]
            tgt_cols = _get_target_columns(cur, tname, db_type)
            col_types = _get_target_column_types(cur, tname, db_type)

            if not tgt_cols:
                results.append({"table": tname, "status": "skip", "reason": "table not found in target", "inserted": 0})
                continue

            common = [c for c in src_cols if c in tgt_cols]
            src_only = [c for c in src_cols if c not in tgt_cols]
            tgt_only = [c for c in tgt_cols if c not in src_cols]

            if not common:
                results.append({"table": tname, "status": "skip", "reason": "no common columns", "inserted": 0})
                continue

            if src_only:
                total_skipped_cols[tname] = src_only

            common_idx = [src_cols.index(c) for c in common]
            tbl = ("public.%s" % tname) if db_type == "pg" else tname.upper()
            col_list = ", ".join(common) if db_type == "pg" else ", ".join(c.upper() for c in common)

            table_order.append((tname, tdata, tbl, col_list, common, common_idx, col_types, src_only, tgt_only))

        # __PATCH_INSP_RESTORE_ORDER__
        # Force ora_app_call_tree_info to be inserted BEFORE apm_db_info,
        # because apm_db_info has a trigger that auto-inserts (db_id, 0)
        # rows into ora_app_call_tree_info. If apm_db_info is inserted first,
        # the dump rows for ora_app_call_tree_info would conflict with those
        # auto-inserted rows. Inserting ora_app_call_tree_info first lets
        # the trigger's EXCEPTION WHEN OTHERS handler swallow the duplicates.
        def _restore_priority(name):
            if name == "ora_app_call_tree_info":
                return 0
            if name == "apm_db_info":
                return 1
            return 2
        table_order.sort(key=lambda x: _restore_priority(x[0]))

        # ── Phase 1: DELETE all tables in REVERSE order (children first) ─
        for tname, tdata, tbl, col_list, common, common_idx, col_types, src_only, tgt_only in reversed(table_order):
            cur.execute("DELETE FROM %s" % tbl)

        # ── Phase 2: INSERT all tables in FORWARD order (parents first) ──
        from datetime import datetime as _dt
        for tname, tdata, tbl, col_list, common, common_idx, col_types, src_only, tgt_only in table_order:
            inserted = 0
            for row in tdata["rows"]:
                vals = [row[i] for i in common_idx]
                if db_type == "pg":
                    placeholders = ", ".join(["%s"] * len(vals))
                    cur.execute("INSERT INTO %s (%s) VALUES (%s)" % (tbl, col_list, placeholders), vals)
                else:
                    placeholders = ", ".join([":%d" % (i+1) for i in range(len(vals))])
                    processed = []
                    for ci, v in enumerate(vals):
                        ctype = col_types.get(common[ci], '')
                        if isinstance(v, str) and ('DATE' in ctype or 'TIMESTAMP' in ctype):
                            if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', v):
                                processed.append(_dt.strptime(v, "%Y-%m-%d %H:%M:%S"))
                            elif re.match(r'^\d{4}-\d{2}-\d{2}$', v):
                                processed.append(_dt.strptime(v, "%Y-%m-%d"))
                            else:
                                processed.append(v)
                        else:
                            processed.append(v)
                    cur.execute("INSERT INTO %s (%s) VALUES (%s)" % (tbl, col_list, placeholders), processed)
                inserted += 1

            total_inserted += inserted
            res = {"table": tname, "status": "ok", "inserted": inserted,
                   "columns": len(common), "total_columns": len(tdata["columns"])}
            if src_only:
                res["skipped_columns"] = src_only
            if tgt_only:
                res["new_columns"] = tgt_only
            results.append(res)

        # ── Phase 3: Sequence reset ──────────────────────────────────────
        seq_results = []
        for sname, sval in dump_data.get("sequences", {}).items():
            if sval is None:
                continue
            try:
                if db_type == "pg":
                    cur.execute("SELECT setval('%s', %d)" % (sname, max(sval, 1)))
                    seq_results.append({"sequence": sname, "value": sval, "status": "ok"})
                else:
                    seq_results.append({"sequence": sname, "value": sval, "status": "manual",
                                        "note": "Oracle sequence requires manual verification"})
            except Exception as e:
                seq_results.append({"sequence": sname, "status": "error", "error": str(e)[:100]})

        # ── COMMIT entire transaction ────────────────────────────────────
        conn.commit()

        cur.close()
        conn.close()

        return json.dumps({
            "ok": True,
            "total_inserted": total_inserted,
            "tables": results,
            "sequences": seq_results,
            "source": dump_data.get("dump_info", {}).get("source_db", "unknown"),
        }, ensure_ascii=False)

    except Exception as e:
        import traceback
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return json.dumps({"ok": False, "error": str(e)[:300],
                           "trace": traceback.format_exc()[:500]})


# ── Page ──────────────────────────────────────────────────────────────────────

_DUMP_PROFILES = {
    "instance": {
        "label": "Instance Dump",
        "file_prefix": "Instance_dump_",
        "menus": ["instance", "account"],
        "desc": "Instance / Account Management 설정을 Dump 합니다.",
    },
    "others": {
        "label": "Others Dump",
        "file_prefix": "Others_dump_",
        "menus": ["alert", "sms", "repository"],
        "desc": "Alert / SMS / Repository 설정을 Dump 합니다.",
    },
}


def page_config_dump():
    # Build profile cards with detail tooltips
    profile_cards = ""
    for pkey, prof in _DUMP_PROFILES.items():
        detail_items = ""
        total_tbl = 0
        total_seq = 0
        for mkey in prof["menus"]:
            md = MENU_DEFS.get(mkey, {})
            tbl_rows = ""
            for t in md.get("tables", []):
                tbl_rows += '<tr><td style="padding:3px 8px;color:#E2E8F0;font-family:JetBrains Mono,Consolas,monospace;font-size:.74rem;">%s</td><td style="padding:3px 8px;color:#94A3B8;font-size:.7rem;">TABLE</td></tr>' % t
                total_tbl += 1
            for s in md.get("sequences", []):
                tbl_rows += '<tr><td style="padding:3px 8px;color:#E2E8F0;font-family:JetBrains Mono,Consolas,monospace;font-size:.74rem;">%s</td><td style="padding:3px 8px;color:#F59E0B;font-size:.7rem;">SEQ</td></tr>' % s
                total_seq += 1
            detail_items += (
                '<div style="margin-top:8px;">'
                '<div style="font-size:.7rem;font-weight:700;color:#818CF8;letter-spacing:.04em;'
                'text-transform:uppercase;margin-bottom:4px;padding-bottom:4px;'
                'border-bottom:1px solid #334155;">%s</div>'
                '<table style="width:100%%;border-collapse:collapse;">%s</table>'
                '</div>'
            ) % (md.get("label", mkey), tbl_rows)
        sub = "%d tables" % total_tbl
        if total_seq:
            sub += " + %d seq" % total_seq
        profile_cards += (
            '<div class="dump-profile" style="position:relative;">'
            '<div style="display:flex;align-items:center;gap:14px;margin-bottom:10px;">'
            '<span style="font-size:.92rem;font-weight:700;color:var(--c-main);">%s</span>'
            '<span style="font-size:.72rem;color:var(--c-muted);">%s</span>'
            '</div>'
            '<div style="font-size:.82rem;color:var(--c-muted);margin-bottom:14px;">%s</div>'
            '<div style="display:flex;gap:10px;align-items:center;">'
            '<button onclick="_doDump(\'%s\')" class="dump-action-btn" id="dump-btn-%s">'
            '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
            '<polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>'
            ' Dump</button>'
            '<span id="dump-st-%s" style="font-size:.82rem;color:var(--c-muted);"></span>'
            '</div>'
            '<div class="dump-tip">%s</div>'
            '</div>'
        ) % (prof["label"], sub, prof["desc"], pkey, pkey, pkey, detail_items)

    body = ''.join([
        _page_title_html('Config Dump', *_HELP.get('config_dump', ('Config Dump', ''))),

        # ── Dump Profiles ─────────────────────────────────────────────
        # 카드들이 .card 애니메이션의 transform 때문에 각자 stacking context를
        # 만들어, 뒤따르는 Restore 카드가 .dump-tip 을 가리는 문제 회피용 z-index.
        '<div class="card" style="position:relative;z-index:5;">',
        '<h3 style="margin:0 0 16px;font-size:.95rem;color:var(--c-main);">Dump</h3>',
        '<style>'
        '.dump-profile:hover .dump-tip{display:block;}'
        '.dump-tip{display:none;position:absolute;left:0;top:100%;margin-top:6px;z-index:999;'
        'background:#1E293B;border:1px solid #334155;border-radius:10px;padding:12px 16px;'
        'min-width:280px;max-width:360px;box-shadow:0 12px 32px rgba(0,0,0,.4);pointer-events:none;}'
        '</style>',
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">', profile_cards, '</div>',
        '</div>',

        # ── Restore ───────────────────────────────────────────────────
        '<div class="card">',
        '<h3 style="margin:0 0 16px;font-size:.95rem;color:var(--c-main);">Restore</h3>',
        '<div style="font-size:.82rem;color:var(--c-muted);margin-bottom:14px;">'
        'Dump 된 JSON 파일을 선택하여 Restore 합니다. 각 테이블을 DELETE 후 교집합 컬럼만 INSERT 합니다.</div>',
        _restore_json_block(),
        '</div>',

        # ── Migration Guide ───────────────────────────────────────────
        '<div class="card">',
        '<h3 style="margin:0 0 18px;font-size:.95rem;color:var(--c-main);display:flex;align-items:center;gap:8px;">'
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/>'
        '<line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
        ' Migration Guide (AS-IS \u2192 TO-BE)</h3>',

        '<div class="mig-group">'
        '<div class="mig-group-title">1. \uC900\uBE44 \uBC0F \uBC31\uC5C5</div>'
        '<div class="mig-step"><span class="mig-num">1</span>'
        '<span class="mig-tag mig-tag-db">DB \uC11C\uBC84</span>'
        '<div class="mig-body">RTS \uC804\uCCB4 \uC911\uC9C0 \uBC0F rts.conf\uC5D0 TO-BE \uC11C\uBC84 \uC815\uBCF4 \uC785\uB825</div></div>'
        '<div class="mig-step"><span class="mig-num">2</span>'
        '<span class="mig-tag mig-tag-asis">AS-IS Inspector</span>'
        '<div class="mig-body">Config Dump > Instance Dump, Others Dump \uC218\uD589</div></div>'
        '</div>',

        '<div class="mig-group">'
        '<div class="mig-group-title">2. \uC124\uC815\uAC12 \uC774\uAD00</div>'
        '<div class="mig-step"><span class="mig-num">3</span>'
        '<span class="mig-tag mig-tag-tobe">TO-BE \uC218\uC9D1\uC11C\uBC84</span>'
        '<div class="mig-body">Install Repository \uC218\uD589 (\uCD08\uAE30 \uAD6C\uCD95)</div></div>'
        '<div class="mig-step"><span class="mig-num">4</span>'
        '<span class="mig-tag mig-tag-tobe">TO-BE Inspector</span>'
        '<div class="mig-body">Config Dump > Instance_dump_YYMMDD.json Restore \uC218\uD589</div></div>'
        '<div class="mig-step"><span class="mig-num">5</span>'
        '<span class="mig-tag mig-tag-tobe">TO-BE MaxGauge</span>'
        '<div class="mig-body">Configuration > License \uB4F1\uB85D</div></div>'
        '<div class="mig-step"><span class="mig-num">6</span>'
        '<span class="mig-tag mig-tag-db">DB \uC11C\uBC84</span>'
        '<div class="mig-body">RTS \uC804\uCCB4 \uAE30\uB3D9<br>'
        '- License Valid \uD655\uC778<br>'
        '- Connection Manager RTS Status \uD30C\uB780\uBD88 \uD655\uC778<br>'
        '- DGServer_Sn/bin \uB514\uB809\uD1A0\uB9AC\uC5D0\uC11C list.conf \uC0DD\uC131 \uD655\uC778</div></div>'
        '<div class="mig-step"><span class="mig-num">7</span>'
        '<span class="mig-tag mig-tag-tobe">TO-BE \uC218\uC9D1\uC11C\uBC84</span>'
        '<div class="mig-body">Install Repository \uC7AC\uC218\uD589 (\uD30C\uD2F0\uC158 \uD14C\uC774\uBE14 \uC0DD\uC131)</div></div>'
        '<div class="mig-step"><span class="mig-num">8</span>'
        '<span class="mig-tag mig-tag-tobe">TO-BE Inspector</span>'
        '<div class="mig-body">Config Dump > Others_dump_YYMMDD.json Restore \uC218\uD589</div></div>'
        '</div>',
        '</div>',  # card end

        _ts(),
        _dump_css(),
        _dump_js(),
    ])
    return _page('config-dump', 'Config Dump', body)


# ── HTML fragments ────────────────────────────────────────────────────────────

def _restore_sql_block():
    return ''.join([
        '<div class="restore-steps">',
        '<div class="restore-step"><span class="sn">1</span>'
        'DGServer_M &gt; dginstall&#xC744; &#xC218;&#xD589;&#xD569;&#xB2C8;&#xB2E4;.</div>',
        '<div class="restore-step"><span class="sn">2</span>'
        'TO-BE &#xC11C;&#xBC84;&#xC5D0; SQL &#xD30C;&#xC77C;&#xC744; &#xBCF5;&#xC0AC;&#xD569;&#xB2C8;&#xB2E4;.</div>',
        '<div class="restore-step"><span class="sn">3</span>'
        'psql / sqlplus &#xB85C; &#xC2E4;&#xD589;&#xD569;&#xB2C8;&#xB2E4;:</div>',
        '</div>',
        '<pre class="code-block">'
        '# PostgreSQL\n'
        'psql -h [HOST] -p [PORT] -U [USER] -d [DBNAME] -f config_dump_YYYYMMDD.sql\n\n'
        '# Oracle (sqlplus)\n'
        'sqlplus [USER]/[PASS]@[SID] @config_dump_YYYYMMDD.sql</pre>',
        '<div class="restore-warn">'
        '⚠ SQL 파일은 각 테이블을 DELETE 후 INSERT합니다. '
        'TO-BE에 기존 Config 데이터가 있으면 덮어쓰기 됩니다.</div>',
        '</div>',
    ])


def _restore_json_block():
    from html_helpers import _UTILS_BASE
    return ''.join([
        '<div style="margin-top:12px;">',
        '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;">',
        '<label style="display:inline-flex;align-items:center;gap:8px;padding:8px 20px;'
        'border-radius:8px;border:1px dashed #CBD5E1;cursor:pointer;font-size:.82rem;'
        'color:#64748B;font-weight:600;transition:all .15s;" '
        'onmouseover="this.style.borderColor=\'#6366F1\';this.style.color=\'#6366F1\'" '
        'onmouseout="this.style.borderColor=\'#CBD5E1\';this.style.color=\'#64748B\'">',
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
        ' Select JSON File',
        '<input type="file" id="restore-file" accept=".json" style="display:none" onchange="onRestoreFileSelect(this)">',
        '</label>',
        '<span id="restore-filename" style="font-size:.82rem;color:#64748B;"></span>',
        '</div>',
        '<div style="display:flex;align-items:center;gap:12px;">',
        '<button id="restore-btn" onclick="doRestore()" disabled '
        'style="padding:8px 20px;border-radius:8px;border:1px solid #6366F1;'
        'background:transparent;color:#6366F1;font-size:.82rem;font-weight:600;'
        'cursor:pointer;opacity:.5;">Restore</button>',
        '<span id="restore-status" style="font-size:.82rem;"></span>',
        '</div>',
        '<div id="restore-result" style="display:none;margin-top:16px;"></div>',
        '</div>',
        '<div style="margin-top:12px;font-size:.78rem;color:#DC2626;background:rgba(220,38,38,.05);'
        'border:1px solid rgba(220,38,38,.15);border-radius:8px;padding:10px 14px;">'
        '\u26a0 Restore\ub294 \uac01 \ud14c\uc774\ube14\uc744 DELETE \ud6c4 INSERT\ud569\ub2c8\ub2e4. '
        'TO-BE\uc640 \uc2a4\ud0a4\ub9c8 \ubc84\uc804\uc774 \ub2ec\ub77c\ub3c4 '
        '\uad50\uc9d1\ud569 \uceec\ub7fc\ub9cc \uc801\uc6a9\ub429\ub2c8\ub2e4.</div>',
    ])


def _dump_css():
    return (
        '<style>'

        '.dump-profile{padding:18px 20px;border:1.5px solid var(--bd);border-radius:14px;'
        'transition:all .22s;background:var(--bg-card);}'
        '.dump-profile:hover{border-color:rgba(99,102,241,.35);'
        'background:linear-gradient(135deg,rgba(99,102,241,.04),rgba(139,92,246,.04));}'

        '.dump-action-btn{display:inline-flex;align-items:center;gap:7px;padding:9px 22px;'
        'background:#6366F1;border:none;border-radius:10px;color:#fff;'
        'font-size:.82rem;font-weight:600;cursor:pointer;transition:all .2s ease;'
        'box-shadow:0 1px 2px rgba(0,0,0,.06),0 4px 12px rgba(99,102,241,.18);}'
        '.dump-action-btn:hover{background:#4F46E5;transform:translateY(-1px);}'
        '.dump-action-btn:active{transform:translateY(0);}'
        '.dump-action-btn:disabled{opacity:.35;cursor:not-allowed;background:#94A3B8;}'

        '.dump-stat-row{display:flex;align-items:center;gap:8px;font-size:.82rem;margin-bottom:6px;}'
        '.dump-stat-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;}'

        '.mig-group{margin-bottom:20px;}'
        '.mig-group:last-child{margin-bottom:0;}'
        '.mig-group-title{font-size:.82rem;font-weight:700;color:var(--c-main);'
        'padding:8px 0;margin-bottom:4px;border-bottom:2px solid var(--c-accent);}'
        '.mig-steps{display:flex;flex-direction:column;gap:0;}'
        '.mig-step{display:flex;align-items:flex-start;gap:14px;padding:12px 0;border-bottom:1px solid var(--bd);font-size:.84rem;}'
        '.mig-step:last-child{border-bottom:none;}'
        '.mig-num{flex-shrink:0;width:26px;height:26px;border-radius:50%;background:#6366F1;color:#fff;'
        'display:flex;align-items:center;justify-content:center;font-size:.78rem;font-weight:700;}'
        '.mig-body{flex:1;line-height:1.6;color:var(--c-text);}'
        '.mig-tag{flex-shrink:0;font-size:.68rem;font-weight:700;padding:3px 10px;border-radius:6px;'
        'letter-spacing:.02em;white-space:nowrap;min-width:110px;text-align:center;}'
        '.mig-tag-db{background:rgba(245,158,11,.12);color:#92400E;border:1px solid rgba(245,158,11,.3);}'
        '.mig-tag-asis{background:rgba(148,163,184,.12);color:#475569;border:1px solid rgba(148,163,184,.3);}'
        '.mig-tag-tobe{background:rgba(99,102,241,.1);color:#4338CA;border:1px solid rgba(99,102,241,.25);}'

        '.restore-section{padding:18px 20px;background:var(--bg-main);'
        'border-radius:14px;border:1px solid var(--bd);}'
        '.restore-title{font-size:.85rem;font-weight:700;color:var(--c-main);'
        'margin-bottom:12px;display:flex;align-items:center;gap:8px;}'
        '.restore-badge{font-size:.62rem;padding:3px 10px;border-radius:999px;'
        'font-weight:700;letter-spacing:.06em;text-transform:uppercase;}'
        '.restore-badge-green{background:rgba(16,185,129,.1);color:#059669;'
        'border:1px solid rgba(16,185,129,.2);}'
        '.restore-badge-yellow{background:rgba(245,158,11,.1);color:#B45309;'
        'border:1px solid rgba(245,158,11,.2);}'
        '.restore-desc{font-size:.8rem;color:var(--c-muted);margin-bottom:14px;line-height:1.65;}'
        '.restore-steps{margin-bottom:8px;}'
        '.restore-step{font-size:.8rem;color:var(--c-text);margin-bottom:8px;'
        'display:flex;align-items:flex-start;gap:10px;line-height:1.5;}'
        '.sn{display:inline-flex;align-items:center;justify-content:center;'
        'min-width:22px;height:22px;border-radius:8px;background:var(--c-accent);'
        'color:#fff;font-size:.68rem;font-weight:700;flex-shrink:0;}'
        '.code-block{background:#1E293B;border:1px solid rgba(148,163,184,.1);'
        'border-radius:12px;padding:16px 18px;font-family:"SF Mono",Consolas,monospace;font-size:.78rem;'
        'color:#E2E8F0;line-height:1.7;overflow-x:auto;margin:12px 0;white-space:pre;}'
        '.restore-warn{font-size:.78rem;color:#DC2626;background:rgba(220,38,38,.05);'
        'border:1px solid rgba(220,38,38,.12);border-radius:10px;padding:11px 14px;margin-top:12px;'
        'line-height:1.5;}'
        '.restore-notes{font-size:.8rem;color:var(--c-text);line-height:1.75;padding-left:20px;margin:0;}'
        '.restore-notes li{margin-bottom:10px;}'
        '</style>'
    )


def _dump_js():
    import json as _j
    profiles_json = _j.dumps({k: v["menus"] for k, v in _DUMP_PROFILES.items()})
    prefixes_json = _j.dumps({k: v["file_prefix"] for k, v in _DUMP_PROFILES.items()})
    return (
        '<script>'
        'var _dumpProfiles=' + profiles_json + ';'
        'var _dumpPrefixes=' + prefixes_json + ';'
        'function _dl(c,f,m){var b=new Blob([c],{type:m}),'
        'a=document.createElement("a");a.href=URL.createObjectURL(b);a.download=f;'
        'document.body.appendChild(a);a.click();'
        'setTimeout(function(){document.body.removeChild(a);URL.revokeObjectURL(a.href);},100);}'
        'function _doDump(profile){'
        '  var menus=_dumpProfiles[profile];if(!menus)return;'
        '  var btn=document.getElementById("dump-btn-"+profile);'
        '  var st=document.getElementById("dump-st-"+profile);'
        '  btn.disabled=true;st.textContent="Dumping...";'
        '  fetch("' + _UTILS_BASE + '/api/config-dump",'
        '    {method:"POST",headers:{"Content-Type":"application/json"},'
        '    body:JSON.stringify({menus:menus})})'
        '  .then(function(r){return r.json();})'
        '  .then(function(d){'
        '    btn.disabled=false;'
        '    if(!d.ok){st.innerHTML="<span style=\\"color:#EF4444\\">"+d.error+"</span>";return;}'
        '    var now=new Date(),yy=String(now.getFullYear()).slice(2),'
        '        mm=String(now.getMonth()+1).padStart(2,"0"),dd=String(now.getDate()).padStart(2,"0");'
        '    var fname=_dumpPrefixes[profile]+yy+mm+dd+".json";'
        '    _dl(d.json_content,fname,"application/json");'
        '    var s=d.stats;'
        '    st.innerHTML="<span style=\\"color:#22c55e\\">\\u2713 "+s.tables+" tables / "+s.rows+" rows \\u2192 "+fname+"</span>";'
        '  }).catch(function(e){btn.disabled=false;st.innerHTML="<span style=\\"color:#EF4444\\">"+e+"</span>";});'
        '}'
        'var _restoreData=null;'
        'function onRestoreFileSelect(inp){'
        '  var f=inp.files[0];if(!f)return;'
        '  document.getElementById("restore-filename").textContent=f.name;'
        '  var r=new FileReader();'
        '  r.onload=function(e){'
        '    try{_restoreData=JSON.parse(e.target.result);'
        '      var btn=document.getElementById("restore-btn");'
        '      btn.disabled=false;btn.style.opacity="1";'
        '      var info=_restoreData.dump_info||{};'
        '      document.getElementById("restore-status").innerHTML='
        '        "<span style=\\"color:#64748B\\">Source: "+'
        '        (info.source_db||"unknown")+"</span>";'
        '    }catch(ex){'
        '      document.getElementById("restore-status").innerHTML='
        '        "<span style=\\"color:#EF4444\\">Invalid JSON</span>";'
        '      _restoreData=null;'
        '    }'
        '  };r.readAsText(f);'
        '}'
        'function doRestore(){'
        '  if(!_restoreData){alert("Select a JSON file first.");return;}'
        '  if(!confirm("Restore will DELETE and re-INSERT config data. Continue?"))return;'
        '  var btn=document.getElementById("restore-btn");'
        '  var st=document.getElementById("restore-status");'
        '  btn.disabled=true;btn.style.opacity=".5";st.innerHTML="Restoring...";'
        '  fetch("' + _UTILS_BASE + '/api/config-restore",{method:"POST",'
        '    headers:{"Content-Type":"application/json"},'
        '    body:JSON.stringify(_restoreData)})'
        '  .then(function(r){return r.json();})'
        '  .then(function(d){'
        '    btn.disabled=false;btn.style.opacity="1";'
        '    var res=document.getElementById("restore-result");'
        '    if(!d.ok){st.innerHTML="<span style=\\"color:#EF4444\\">Error</span>";'
        '      res.style.display="block";'
        '      res.innerHTML="<div style=\\"padding:12px;border:1px solid #fecaca;border-radius:8px;background:#fef2f2;color:#dc2626;font-size:.82rem;\\">"+d.error+"</div>";'
        '      return;}'
        '    st.innerHTML="<span style=\\"color:#15803D\\">Done! "+d.total_inserted+" rows inserted</span>";'
        '    var h="<div style=\\"border:1px solid #E5E7EB;border-radius:10px;overflow:hidden;\\">";'
        '    h+="<table style=\\"width:100%%;border-collapse:collapse;font-size:.82rem;\\">";'
        '    h+="<thead><tr style=\\"background:#ECF0F7;\\">";'
        '    h+="<th style=\\"padding:8px 12px;text-align:left;font-size:.72rem;font-weight:700;text-transform:uppercase;color:#5F6B80;\\">Table</th>";'
        '    h+="<th style=\\"padding:8px 12px;text-align:center;font-size:.72rem;font-weight:700;text-transform:uppercase;color:#5F6B80;\\">Rows</th>";'
        '    h+="<th style=\\"padding:8px 12px;text-align:center;font-size:.72rem;font-weight:700;text-transform:uppercase;color:#5F6B80;\\">Columns</th>";'
        '    h+="<th style=\\"padding:8px 12px;text-align:left;font-size:.72rem;font-weight:700;text-transform:uppercase;color:#5F6B80;\\">Status</th>";'
        '    h+="</tr></thead><tbody>";'
        '    d.tables.forEach(function(t){'
        '      var sc=t.status==="ok"?"#15803D":"#B45309";'
        '      h+="<tr style=\\"border-bottom:1px solid #F1F5F9;\\">";'
        '      h+="<td style=\\"padding:8px 12px;font-family:monospace;font-size:.78rem;\\">"+t.table+"</td>";'
        '      h+="<td style=\\"padding:8px 12px;text-align:center;\\">"+t.inserted+"</td>";'
        '      h+="<td style=\\"padding:8px 12px;text-align:center;\\">"+(t.columns||"-")+"</td>";'
        '      h+="<td style=\\"padding:8px 12px;color:"+sc+";font-weight:600;\\">"+t.status;'
        '      if(t.reason)h+=" ("+t.reason+")";'
        '      if(t.skipped_columns)h+=" <span style=\\"color:#94A3B8;font-weight:400;font-size:.75rem;\\">skip: "+t.skipped_columns.join(", ")+"</span>";'
        '      h+="</td></tr>";'
        '    });'
        '    h+="</tbody></table></div>";'
        '    res.style.display="block";res.innerHTML=h;'
        '  }).catch(function(e){btn.disabled=false;btn.style.opacity="1";'
        '    st.innerHTML="<span style=\\"color:#EF4444\\">Request failed</span>";});'
        '}'
        '</script>'
    )
