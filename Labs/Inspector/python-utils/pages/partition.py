# -*- coding: utf-8 -*-
import os
import re
import json
import threading
from datetime import datetime, timedelta

from service_config import load_service_config
from db_utils import _db_cfg, run_db_query, run_db_exec, _parse_db_table, _sql_embed
from sql_library import _get_sql, _SQL_PG_PARTITION_DROP_LIST, _SQL_PARTITION_DROP_LIST
from sql_library import _SQL_PG_PARTITION_DROP_EXEC, _SQL_ORACLE_PARTITION_DROP_EXEC
from system_utils import _xml_val, _read_lines
from html_helpers import (
    _badge, _warn_box, _info_box, _page_title_html, _page,
    _HELP, _HELP_JS, _ts, _inst_filter_block, _render_db_table_html,
    _UTILS_BASE,
)


def _partition_state_badge(state):
    if state == "START":
        return ('<span style="background:rgba(52,217,123,.1);border:1px solid rgba(52,217,123,.25);color:#34d97b;'
                'padding:2px 10px;border-radius:999px;font-size:.72rem;font-weight:600;">'
                'START</span>')
    return ('<span style="background:rgba(100,116,139,.1);border:1px solid rgba(100,116,139,.25);color:#64748b;'
            'padding:2px 10px;border-radius:999px;font-size:.72rem;font-weight:600;">'
            'FINISH</span>')


def _partition_time_html():
    """Oracle DGServer_M log parser for partition timing - paired START/FINISH."""
    import glob, zipfile as _zf
    svc = load_service_config()
    dgm_home = svc.get("services", {}).get("dgserver_m", "")
    if not dgm_home:
        return _warn_box("DGServer_M 경로가 설정되지 않았습니다.")

    xmlfile  = os.path.join(dgm_home, "conf", "DGServer.xml")
    port     = _xml_val(xmlfile, "gather_port")
    port_str = str(port) if port else ""
    log_dir  = os.path.join(dgm_home, "log")
    logfile  = os.path.join(log_dir, "DGM_" + port_str + ".log")

    time_re    = re.compile(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\]')
    # 로그에 elapsed / elasped (오타) 둘 다 등장하므로 모두 인식.
    elapsed_re = re.compile(r'(?:elapsed|elasped)=(\d+)ms', re.I)

    PATTERNS = [
        ("CREATE",   "START",  re.compile(r'\[PARTITION MANAGE\]\s+Create\s+partition\s+start',    re.I)),
        ("CREATE",   "FINISH", re.compile(r'\[PARTITION MANAGE\]\s+Create\s+partition\s+finish',   re.I)),
        ("DROP",     "START",  re.compile(r'\[PARTITION MANAGE\]\s+DROP\s+PARTITION\s+start\b',    re.I)),
        ("DROP",     "FINISH", re.compile(r'\[PARTITION MANAGE\]\s+DROP\s+PARTITION\s+finished',   re.I)),
        ("COMPRESS", "START",  re.compile(r'\[PARTITION MANAGE\]\s+COMPRESS\s+PARTITION\s+start\b(?!\s*Thread)', re.I)),
        ("COMPRESS", "FINISH", re.compile(r'\[PARTITION MANAGE\]\s+COMPRESS\s+PARTITION\s+finished', re.I)),
    ]

    def _parse_lines(lines):
        result = []
        for line in lines:
            if '[PARTITION MANAGE]' not in line:
                continue
            for action, state, pat in PATTERNS:
                if pat.search(line):
                    tm = time_re.search(line)
                    t  = tm.group(1) if tm else "-"
                    em = elapsed_re.search(line)
                    elapsed = ("%.3fs" % (int(em.group(1)) / 1000.0)) if em else "-"
                    result.append((action, state, t, elapsed))
                    break
        return result

    def _find_today_zip():
        from datetime import date
        today_str = date.today().strftime('%Y%m%d')
        today_zip = os.path.join(log_dir, "DGM_%s_%s_0.log.zip" % (port_str, today_str))
        if os.path.exists(today_zip):
            return today_zip
        return None

    rows        = []
    source_tag  = ""
    raw_samples = []

    try:
        zip_path = _find_today_zip()
        if zip_path:
            with _zf.ZipFile(zip_path, 'r') as zf:
                inner = zf.namelist()
                if inner:
                    data = zf.read(inner[0]).decode('utf-8', errors='replace')
                    zip_lines = data.splitlines(keepends=True)
                    raw_samples = zip_lines[-5:] if zip_lines else []
                    rows = _parse_lines(zip_lines)
                    source_tag = os.path.basename(zip_path)
        if not rows:
            if os.path.exists(logfile):
                lines = _read_lines(logfile)
                raw_samples = lines[-5:] if lines else []
                rows = _parse_lines(lines)
                source_tag = os.path.basename(logfile)
            elif not zip_path:
                return _warn_box("로그 파일을 찾을 수 없습니다: " + logfile)
    except Exception as e:
        return _warn_box("로그 읽기 오류: " + str(e))

    if not rows:
        sample_text = "".join(raw_samples).replace("<", "&lt;").replace(">", "&gt;")
        # _info_box 가 .insp-card-body(패딩 없음) 안에 그대로 들어가면 좌우 가장자리에
        # 붙는 문제 → 안쪽 패딩 wrapper 추가해 흰 카드 안에 깔끔히 들어가도록.
        return '<div style="padding:14px 16px;">' + _info_box("일치하는 패턴이 없습니다.") + '</div>'

    # Pair START/FINISH by action type
    pairs = {}  # action -> {start_time, finish_time, elapsed}
    for action, state, t, elapsed in rows:
        if action not in pairs:
            pairs[action] = {'start': None, 'finish': None, 'elapsed': '-'}
        if state == 'START':
            pairs[action]['start'] = t[:8] if t != '-' else None
        elif state == 'FINISH':
            pairs[action]['finish'] = t[:8] if t != '-' else None
            if elapsed != '-':
                pairs[action]['elapsed'] = elapsed

    # Get all instances from apm_db_info for STATUS check
    # For Oracle partition time, we check if CREATE has both start+finish
    source_info = ""

    ACTION_COLOR = {"CREATE": "#0F172A", "DROP": "#0F172A", "COMPRESS": "#0F172A"}
    thead = "<tr><th>ACTION</th><th>TIME</th><th>ELAPSED</th><th>STATUS</th></tr>"
    tbody = ""
    for action in ["CREATE", "DROP", "COMPRESS"]:
        if action not in pairs:
            continue
        p = pairs[action]
        color = ACTION_COLOR.get(action, "#e8e8f0")
        start = p['start'] or '-'
        finish = p['finish'] or '-'
        if start != '-' and finish != '-':
            time_str = start + ' ~ ' + finish
            status = _badge('ok', 'OK')
        elif start != '-' or finish != '-':
            time_str = (start if start != '-' else '-') + ' ~ ' + (finish if finish != '-' else '-')
            status = _badge('critical', 'CHECK')
        else:
            time_str = '-'
            status = _badge('critical', 'CHECK')
        tbody += ("<tr><td style='color:%s;font-weight:600;'>%s</td>"
                  "<td>%s</td><td>%s</td><td>%s</td></tr>") % (
            color, action, time_str, p['elapsed'], status)

    return (source_info +
            "<div class='tbl-wrap'><table class='svc-table'><thead>"
            + thead + "</thead><tbody>" + tbody + "</tbody></table></div>")



def _pick_latest_log(home, is_master):
    prefix = "DGM_" if is_master else "DGS_"
    log_dir = os.path.join(home, "log")
    if not os.path.isdir(log_dir):
        return ""
    candidates = [f for f in os.listdir(log_dir) if f.startswith(prefix) and f.endswith(".log")]
    if not candidates:
        return ""
    candidates.sort(key=lambda f: os.path.getmtime(os.path.join(log_dir, f)), reverse=True)
    return os.path.join(log_dir, candidates[0])


def _partition_time_pg_cards():
    svc = load_service_config()
    dgm_home = svc.get("services", {}).get("dgserver_m", "")
    if not dgm_home:
        return '<div class="card">' + _warn_box("DGServer_M 경로가 설정되지 않았습니다.") + '</div>'

    xmlfile  = os.path.join(dgm_home, "conf", "DGServer.xml")
    port     = _xml_val(xmlfile, "gather_port")
    port_str = str(port) if port else ""
    logfile  = os.path.join(dgm_home, "log", "DGM_" + port_str + ".log")

    pg_create_re = re.compile(
        r'\[PARTITION MANAGE\]\s+Create[e]?d partition\s+(?P<state>start|finish)'
        r'[,\s]+Schema:\s*(?P<schema>\S+)', re.I)
    pg_drop_re = re.compile(
        r'\[PARTITION MANAGE\]\s+Drop Partition\s+Schema:\s*(?P<schema>\S+?)'
        r'\s+(?P<state>strat|start|finished|finish)', re.I)

    def _to_sec(t_str):
        try:
            h, m, rest = t_str.split(":")
            s, ms = rest.split(".") if "." in rest else (rest, "0")
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0
        except Exception:
            return None

    def _calc_elapsed(start_t, end_t):
        if not start_t or start_t == "-" or not end_t or end_t == "-":
            return "-"
        s = _to_sec(start_t)
        e = _to_sec(end_t)
        if s is None or e is None:
            return "-"
        diff = e - s
        if diff < 0:
            diff += 86400
        return "%.3fs" % diff

    try:
        import glob, zipfile as _zf
        log_dir = os.path.join(dgm_home, "log")
        from datetime import date as _date
        _today_str = _date.today().strftime('%Y%m%d')
        _today_zip = os.path.join(log_dir, "DGM_%s_%s_0.log.zip" % (port_str, _today_str))
        zip_path = _today_zip if os.path.exists(_today_zip) else None
        lines = []
        source_tag = ""
        if zip_path:
            with _zf.ZipFile(zip_path, 'r') as zf:
                inner = zf.namelist()
                if inner:
                    data = zf.read(inner[0]).decode('utf-8', errors='replace')
                    lines = data.splitlines(keepends=True)
                    source_tag = os.path.basename(zip_path)
        if not lines:
            if os.path.exists(logfile):
                lines = _read_lines(logfile)
                source_tag = os.path.basename(logfile)
            else:
                return '<div class="card">' + _warn_box("로그 파일을 찾을 수 없습니다: " + logfile) + '</div>'

        # Parse and pair by schema
        create_pairs = {}  # schema -> {start, finish, elapsed}
        drop_pairs = {}
        for line in lines:
            if "[PARTITION MANAGE]" not in line:
                continue
            tm = re.search(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\]', line)
            t = tm.group(1) if tm else "-"

            mc = pg_create_re.search(line)
            if mc:
                schema = mc.group("schema").rstrip(",")
                state = "FINISH" if mc.group("state").lower() in ("finish", "finished") else "START"
                if schema not in create_pairs:
                    create_pairs[schema] = {'start': None, 'finish': None, 'elapsed': '-'}
                if state == "START":
                    create_pairs[schema]['start'] = t[:8]
                else:
                    create_pairs[schema]['finish'] = t[:8]
                    create_pairs[schema]['elapsed'] = _calc_elapsed(
                        create_pairs[schema].get('start') or '', t)
                continue

            md = pg_drop_re.search(line)
            if md:
                schema = md.group("schema").rstrip(",")
                state = "FINISH" if md.group("state").lower() in ("finished", "finish") else "START"
                if schema not in drop_pairs:
                    drop_pairs[schema] = {'start': None, 'finish': None, 'elapsed': '-'}
                if state == "START":
                    drop_pairs[schema]['start'] = t[:8]
                else:
                    drop_pairs[schema]['finish'] = t[:8]
                    drop_pairs[schema]['elapsed'] = _calc_elapsed(
                        drop_pairs[schema].get('start') or '', t)

    except Exception as e:
        return '<div class="card">' + _warn_box("로그 읽기 오류: " + str(e)) + '</div>'

    # 로그에서 [PARTITION MANAGE] 패턴이 전혀 매칭되지 않은 경우: Oracle 과 같은 톤의
    # 단일 파란색 안내 박스로 표시 (흰 카드 안에 padding 으로 깔끔히 배치).
    if not create_pairs and not drop_pairs:
        return ('<div class="insp-card"><div class="insp-card-body" style="padding:14px 16px;">'
                + _info_box("일치하는 패턴이 없습니다.")
                + '</div></div>')

    # Get all instance names from apm_db_info
    all_instances = set()
    try:
        out, err = run_db_query("SELECT instance_name FROM apm_db_info ORDER BY instance_name")
        if not err:
            headers, rows = _parse_db_table(out or "")
            for row in rows:
                if row and row[0].strip():
                    all_instances.add(row[0].strip().lower())
    except Exception:
        pass

    source_info = ""

    def _build_table(pairs, action_label):
        if not pairs and not all_instances:
            return ('<div style="padding:14px 16px;">'
                    + _info_box("항목이 없습니다.")
                    + '</div>')
        thead = "<tr><th>SCHEMA</th><th>TIME</th><th>ELAPSED</th><th>STATUS</th></tr>"
        tbody = ""
        # Show schemas from pairs + missing ones from apm_db_info
        shown = set()
        for schema in sorted(pairs.keys()):
            p = pairs[schema]
            shown.add(schema.lower())
            start = p['start'] or '-'
            finish = p['finish'] or '-'
            if start != '-' and finish != '-':
                time_str = start + ' ~ ' + finish
                status = _badge('ok', 'OK')
            else:
                time_str = (start if start != '-' else '-') + ' ~ ' + (finish if finish != '-' else '-')
                status = _badge('critical', 'CHECK')
            tbody += ("<tr><td style='font-weight:500;'>%s</td><td>%s</td>"
                      "<td>%s</td><td>%s</td></tr>") % (schema, time_str, p['elapsed'], status)
        # Add missing instances
        for inst in sorted(all_instances):
            if inst not in shown:
                tbody += ("<tr><td style='font-weight:500;'>%s</td><td>-</td>"
                          "<td>-</td><td>%s</td></tr>") % (inst, _badge('critical', 'CHECK'))
        return ("<div class='tbl-wrap'><table class='svc-table'><thead>%s</thead>"
                "<tbody>%s</tbody></table></div>") % (thead, tbody)

    result = source_info
    result += (
        '<div class="insp-card">'
        '<div class="insp-card-hdr">'
        '<div class="insp-card-title">Create Partition</div>'
        '</div>'
        '<div class="insp-card-body">' + _build_table(create_pairs, 'CREATE') + '</div>'
        '</div>'
    )
    result += (
        '<div class="insp-card">'
        '<div class="insp-card-hdr">'
        '<div class="insp-card-title">Drop Partition</div>'
        '</div>'
        '<div class="insp-card-body">' + _build_table(drop_pairs, 'DROP') + '</div>'
        '</div>'
    )
    return result



def _db_page(active, title, sub, sql_key, inst_filter=False):
    h   = _HELP.get(active, (title, ''))
    hdr = _page_title_html(title, h[0], h[1], sub)
    sql = _get_sql(sql_key)
    if not sql:
        body = hdr + _warn_box('현재 DB 타입에서는 지원하지 않는 쿼리입니다.')
        return _page(active, title, body)
    out, err = run_db_query(sql)
    if inst_filter and not err:
        headers, rows = _parse_db_table(out or '')
        tbl_html = _render_db_table_html(headers, rows)
        tbl_html = tbl_html.replace('<table class="svc-table">', '<table class="svc-table" id="inst-tbl">', 1)
        fui, fscript = _inst_filter_block('inst-tbl')
        # 카드 헤더 padding(14px)만 사용 — fui 자체 외부 마진 제거
        fui = fui.replace('margin-bottom:14px;', '')
        body = ''.join([
            hdr,
            '<div class="insp-card">',
            '<div class="insp-card-hdr">', fui, '</div>',
            '<div class="insp-card-body">', tbl_html, '</div>',
            '</div>',
            _ts(), _sql_embed(sql), fscript,
        ])
    else:
        from html_helpers import _query_card
        body = hdr + _query_card('', out or '', err or '') + _ts() + _sql_embed(sql)
    return _page(active, title, body)


# ── Procedure DDL ─────────────────────────────────────────────────────────────
_PROC_DDL = """
CREATE OR REPLACE PROCEDURE INSP_PARTITION_CREATE_TARGET(
    p_db_id      NUMBER   DEFAULT NULL,
    p_table_name VARCHAR2 DEFAULT NULL,
    p_date_from  DATE     DEFAULT SYSDATE - 1,
    p_date_to    DATE     DEFAULT SYSDATE + 3
)
IS
    MOD_ELAPSE    CONSTANT NUMBER := 10;
    err_mxg       VARCHAR2(100);
    prev_partname VARCHAR2(20) DEFAULT '1ST';
    t_sleep       NUMBER DEFAULT 1;
    t_start       NUMBER DEFAULT DBMS_UTILITY.get_time;
    num1          NUMBER;
    v_curr_date   DATE;
    v_part_key    NUMBER;
    v_partname    VARCHAR2(20);
    v_sql_stmt    VARCHAR2(400);
    v_exists      NUMBER;
    v_hist        NUMBER;

    CURSOR c_targets IS
        SELECT d.db_id, p.table_name
          FROM apm_partition_manage p, apm_db_info d
         WHERE p.db_id = 0
           AND (p_db_id      IS NULL OR d.db_id      = p_db_id)
           AND (p_table_name IS NULL OR p.table_name = p_table_name);
BEGIN
    v_curr_date := TRUNC(p_date_from);

    WHILE v_curr_date <= TRUNC(p_date_to) LOOP

        FOR c_rec IN c_targets LOOP

            v_part_key := MXG_GET_PARTITION_KEY_532(c_rec.db_id, v_curr_date);
            v_partname := 'P' || TO_CHAR(v_part_key);

            -- Check actual partition existence (source of truth)
            SELECT COUNT(*) INTO v_exists
              FROM dba_tab_partitions
             WHERE table_owner = USER
               AND table_name  = c_rec.table_name
               AND partition_name = v_partname;

            -- Check history record
            SELECT COUNT(*) INTO v_hist
              FROM apm_partition_history
             WHERE db_id = c_rec.db_id
               AND table_name = c_rec.table_name
               AND partition_name = v_partname;

            -- Self-heal: history exists but partition does not → stale history
            IF v_exists = 0 AND v_hist > 0 THEN
                DELETE FROM apm_partition_history
                 WHERE db_id = c_rec.db_id
                   AND table_name = c_rec.table_name
                   AND partition_name = v_partname;
                COMMIT;
            END IF;

            -- Self-heal: partition exists but history missing → backfill
            IF v_exists > 0 AND v_hist = 0 THEN
                INSERT INTO apm_partition_history VALUES (
                    c_rec.db_id, c_rec.table_name, v_partname, '1');
                COMMIT;
            END IF;

            -- Already exists → skip
            IF v_exists > 0 THEN CONTINUE; END IF;

            IF c_rec.table_name IN ('APM_SQL_LIST', 'APM_SQL_LIST_RP') THEN
                v_sql_stmt :=
                    'ALTER TABLE ' || c_rec.table_name ||
                    ' ADD PARTITION ' || v_partname ||
                    ' VALUES LESS THAN (' ||
                    TO_CHAR(TO_NUMBER(TO_CHAR(v_curr_date,'yymmdd')) * 1000 + (c_rec.db_id + 1)) ||
                    ')';
            ELSE
                v_sql_stmt :=
                    'ALTER TABLE ' || c_rec.table_name ||
                    ' ADD PARTITION ' || v_partname ||
                    ' VALUES (''' || SUBSTR(v_partname, 2) || ''')';
            END IF;

            IF prev_partname = '1ST' THEN
                prev_partname := v_partname;
            ELSIF prev_partname != v_partname THEN
                prev_partname := v_partname;
                t_sleep := ROUND(((DBMS_UTILITY.get_time - t_start) / 100) / MOD_ELAPSE, 2);
                DBMS_LOCK.sleep(t_sleep);
                t_start := DBMS_UTILITY.get_time;
            END IF;

            BEGIN
                EXECUTE IMMEDIATE v_sql_stmt;
                -- DDL implicitly commits, so partition exists at this point.
                -- Insert history only if not already present (duplicate guard).
                SELECT COUNT(*) INTO v_hist
                  FROM apm_partition_history
                 WHERE db_id = c_rec.db_id
                   AND table_name = c_rec.table_name
                   AND partition_name = v_partname;
                IF v_hist = 0 THEN
                    INSERT INTO apm_partition_history VALUES (
                        c_rec.db_id, c_rec.table_name, v_partname, '1');
                    COMMIT;
                END IF;
            EXCEPTION WHEN OTHERS THEN
                ROLLBACK;
                err_mxg := '1#' || SUBSTR(SQLERRM, 1, 97);
                num1 := MXG_INSERT_JOB_LOG(SUBSTR(v_sql_stmt, 1, 200), err_mxg);
            END;

        END LOOP;

        v_curr_date := v_curr_date + 1;
    END LOOP;

EXCEPTION
    WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE(SQLERRM);
END;
"""


_DROP_PROC_DDL = """
CREATE OR REPLACE PROCEDURE INSP_PARTITION_DROP_TARGET(
    p_db_id NUMBER DEFAULT NULL
)
IS
    MOD_ELAPSE    CONSTANT NUMBER := 10;
    err_mxg       VARCHAR2(100);
    sql_stmt      VARCHAR2(255);
    prev_partname VARCHAR2(100) DEFAULT '1ST';
    t_sleep       NUMBER DEFAULT 1;
    t_start       NUMBER DEFAULT DBMS_UTILITY.get_time;
    num1          NUMBER;
    v_part_cnt    NUMBER;

    CURSOR partman IS
        SELECT DISTINCT
               TO_NUMBER(SUBSTR(p.partition_name, 8, 3)) AS db_id,
               p.table_name AS tabname,
               p.partition_name AS partname
          FROM dba_tab_partitions p
          LEFT JOIN apm_db_info d ON d.db_id = TO_NUMBER(SUBSTR(p.partition_name, 8, 3))
          LEFT JOIN apm_partition_manage m
               ON m.table_name = p.table_name
              AND m.db_id = TO_NUMBER(SUBSTR(p.partition_name, 8, 3))
         WHERE p.table_owner = USER
           AND REGEXP_LIKE(p.partition_name, '^P[0-9]{9}$')
           AND (p_db_id IS NULL OR TO_NUMBER(SUBSTR(p.partition_name, 8, 3)) = p_db_id)
           AND (
               d.db_id IS NULL
               OR (m.retention_days IS NOT NULL
                   AND (TRUNC(SYSDATE) - TRUNC(TO_DATE(SUBSTR(p.partition_name, 2, 6), 'RRMMDD'))) > m.retention_days)
           )
         ORDER BY 3;
BEGIN
    FOR c_rec IN partman LOOP
        IF prev_partname = '1ST' THEN
            prev_partname := c_rec.partname;
        ELSIF prev_partname != c_rec.partname THEN
            prev_partname := c_rec.partname;
            t_sleep := ROUND(((DBMS_UTILITY.get_time - t_start) / 100) / MOD_ELAPSE, 2);
            DBMS_LOCK.sleep(t_sleep);
            t_start := DBMS_UTILITY.get_time;
        END IF;

        -- Skip if this is the last partition (ORA-14083 prevention)
        SELECT COUNT(*) INTO v_part_cnt
          FROM dba_tab_partitions
         WHERE table_owner = USER
           AND table_name = c_rec.tabname;
        IF v_part_cnt <= 1 THEN
            -- Clean up orphan history even if we cannot drop the partition
            DELETE FROM apm_partition_history
             WHERE db_id = c_rec.db_id
               AND table_name = c_rec.tabname
               AND partition_name = c_rec.partname;
            COMMIT;
            CONTINUE;
        END IF;

        sql_stmt := 'ALTER TABLE ' || c_rec.tabname || ' DROP PARTITION ' || c_rec.partname;

        BEGIN
            EXECUTE IMMEDIATE sql_stmt;
            -- DDL implicitly commits; now clean up history
            DELETE FROM apm_partition_history
             WHERE db_id = c_rec.db_id
               AND table_name = c_rec.tabname
               AND partition_name = c_rec.partname;
            COMMIT;
        EXCEPTION WHEN OTHERS THEN
            ROLLBACK;
            err_mxg := SUBSTR(SQLERRM, 1, 100);
            num1 := MXG_INSERT_JOB_LOG(SUBSTR(sql_stmt, 1, 200), err_mxg);
        END;
    END LOOP;
EXCEPTION
    WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE(SQLERRM);
END;
"""




def page_partition_create():
    from db_utils import run_db_exec
    from datetime import date as _d, timedelta as _td
    sql   = _get_sql('partition_create')
    title = 'Partition Create Check'
    sub   = 'Checks D+1/D+2/D+3 partition creation status'
    h     = _HELP.get('partition_create', (title, ''))
    hdr   = _page_title_html(title, h[0], h[1], sub)

    if not sql:
        body = hdr + _warn_box('현재 DB 타입에서는 지원하지 않는 쿼리입니다.')
        return _page('partition_create', title, body)

    out, err = run_db_query(sql)
    if err:
        body = hdr + '<div class="card">' + _warn_box(err) + '</div>'
        return _page('partition_create', title, body)

    headers, rows = _parse_db_table(out or '')
    if not headers:
        body = hdr + '<div class="card">' + _warn_box('조회된 데이터가 없습니다.') + '</div>'
        return _page('partition_create', title, body)

    idx_inst = next((i for i, h in enumerate(headers) if 'INSTANCE' in h.upper()), 0)
    idx_st   = next((i for i, h in enumerate(headers) if 'STATUS' in h.upper()), len(headers) - 1)

    _def_from = (_d.today() - _td(days=1)).strftime('%Y-%m-%d')
    _def_to   = (_d.today() + _td(days=3)).strftime('%Y-%m-%d')

    th_cells = ''.join('<th class="sortable" onclick="tbSort(this)">%s<span class="sort-ic"></span></th>' % h for h in headers)
    tr_rows  = ''
    for row in rows:
        row_list = list(row)
        inst_val = row_list[idx_inst].strip() if idx_inst < len(row_list) else ''
        status   = row_list[idx_st].strip().upper() if idx_st < len(row_list) else ''

        cells = []
        for i, val in enumerate(row_list):
            if i == idx_st:
                if status == 'OK':
                    cells.append('<td>%s</td>' % _badge('ok', val))
                elif status in ('CHECK', 'ERROR'):
                    badge_html = (
                        '<span class="badge badge-crit create-hint" data-inst="%s" data-from="%s" data-to="%s"'
                        ' style="background:rgba(240,106,106,.12);color:#f06a6a;border:1px solid rgba(240,106,106,.3);'
                        'padding:2px 10px;border-radius:9999px;font-size:0.75rem;font-weight:600;'
                        'display:inline-block;line-height:1.2;text-align:center;min-width:32px;cursor:pointer;">%s</span>'
                    ) % (inst_val, _def_from, _def_to, val)
                    cells.append('<td>%s</td>' % badge_html)
                else:
                    cells.append('<td>%s</td>' % val)
            else:
                cells.append('<td>%s</td>' % val)

        tr_rows += '<tr>' + ''.join(cells) + '</tr>'

    table_html = (
        '<div class="tbl-wrap"><table class="svc-table" id="inst-tbl">'
        '<thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
    ) % (th_cells, tr_rows)

    tooltip_html = (
        '<div id="create-tt" data-ov-track style="display:none;position:fixed;z-index:9999;'
        'background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;'
        'padding:16px 20px;box-shadow:0 8px 32px rgba(0,0,0,.35);min-width:340px;'
        'pointer-events:auto;">'
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;gap:16px;">'
        '<div id="create-tt-title" style="font-size:.7rem;font-weight:700;text-transform:uppercase;'
        'letter-spacing:.07em;color:var(--c-dim);"></div>'
        '<div style="display:flex;align-items:center;gap:10px;">'
        '<button id="create-exec-btn" onclick="_doCreate()"'
        ' style="padding:5px 16px;border-radius:20px;border:1px solid #3b82f6;color:#3b82f6;'
        'background:transparent;font-size:.78rem;font-weight:600;cursor:pointer;'
        'letter-spacing:.03em;transition:all .15s;white-space:nowrap;flex-shrink:0;"'
        ' onmouseover="if(!this.disabled){this.style.background=\'#3b82f6\';this.style.color=\'#fff\'}"'
        ' onmouseout="if(!this.disabled){this.style.background=\'transparent\';this.style.color=\'#3b82f6\'}">'
        'Create</button>'
        '<button id="create-tt-close" onclick="_cclose()"'
        ' style="display:none;width:26px;height:26px;border-radius:50%;'
        'border:1px solid var(--bd);color:var(--c-muted);background:transparent;'
        'font-size:1rem;cursor:pointer;transition:all .15s;flex-shrink:0;'
        'text-align:center;line-height:24px;padding:0;"'
        ' onmouseover="this.style.background=\'var(--bg-main)\';this.style.color=\'var(--c-main)\';this.style.borderColor=\'var(--c-main)\'"'
        ' onmouseout="this.style.background=\'transparent\';this.style.color=\'var(--c-muted)\';this.style.borderColor=\'var(--bd)\'">&times;</button>'
        '</div>'
        '</div>'
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">'
        '<div>'
        '<label style="font-size:.72rem;color:var(--c-dim);display:block;margin-bottom:3px;">Date From</label>'
        '<input type="date" id="create-tt-from"'
        ' style="width:100%;padding:4px 7px;border-radius:6px;border:1px solid var(--bd);'
        'background:var(--bg-main);color:var(--c-main);font-size:.78rem;box-sizing:border-box;font-family:inherit;font-weight:600;"/>'
        '</div>'
        '<div>'
        '<label style="font-size:.72rem;color:var(--c-dim);display:block;margin-bottom:3px;">Date To</label>'
        '<input type="date" id="create-tt-to"'
        ' style="width:100%;padding:4px 7px;border-radius:6px;border:1px solid var(--bd);'
        'background:var(--bg-main);color:var(--c-main);font-size:.78rem;box-sizing:border-box;font-family:inherit;font-weight:600;"/>'
        '</div>'
        '</div>'
        '</div>'
    )

    toast_html = (
        '<div id="part-toast" style="display:none;position:fixed;bottom:24px;right:24px;'
        'z-index:9999;background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;'
        'padding:14px 20px;box-shadow:0 8px 32px rgba(0,0,0,.35);min-width:260px;">'
        '<div id="part-toast-msg" style="font-size:.85rem;"></div>'
        '</div>'
    )

    confirm_modal_html = (
        '<style>'
        '@keyframes _pmIn{from{opacity:0;transform:scale(.94) translateY(8px)}to{opacity:1;transform:scale(1) translateY(0)}}'
        '#create-confirm-ov>div{animation:_pmIn .25s cubic-bezier(.34,1.56,.64,1) both}'
        '</style>'
        '<div id="create-confirm-ov" style="display:none;position:fixed;inset:0;z-index:10000;'
        'background:rgba(15,15,30,.45);backdrop-filter:blur(6px);'
        'align-items:center;justify-content:center;padding:24px;">'
        '<div style="background:#ffffff;border-radius:16px;width:100%;max-width:400px;'
        'box-shadow:0 0 0 1px rgba(108,84,232,.12),0 24px 60px rgba(0,0,0,.18);overflow:hidden;">'
        # \u2500\u2500 Header \u2500\u2500
        '<div style="padding:22px 24px 0;display:flex;align-items:flex-start;justify-content:space-between;">'
        '<div>'
        '<div style="width:42px;height:42px;background:#ede9fd;border-radius:12px;'
        'display:grid;place-items:center;margin-bottom:14px;">'
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6c54e8" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="3" width="18" height="18" rx="2"/>'
        '<line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/>'
        '</svg></div>'
        '<div style="font-size:16px;font-weight:700;color:#1a1d2e;letter-spacing:-.01em;margin-bottom:4px;">'
        '\ud30c\ud2f0\uc158 \uc0dd\uc131 \ud655\uc778</div>'
        '<div style="font-size:12.5px;color:#9ca3af;">\uc544\ub798 \uc815\ubcf4\ub97c \ud655\uc778\ud558\uace0 \uc0dd\uc131\uc744 \uc9c4\ud589\ud558\uc138\uc694</div>'
        '</div>'
        '<button onclick="_cfrm_cancel()" '
        'style="width:28px;height:28px;border:1px solid #e4e6ed;border-radius:7px;background:#fff;'
        'display:grid;place-items:center;cursor:pointer;color:#9ca3af;font-size:14px;'
        'flex-shrink:0;margin-top:4px;transition:border-color .15s,color .15s;"'
        ' onmouseover="this.style.borderColor=\'#ef4444\';this.style.color=\'#ef4444\'"'
        ' onmouseout="this.style.borderColor=\'#e4e6ed\';this.style.color=\'#9ca3af\'">&#x2715;</button>'
        '</div>'
        # \u2500\u2500 Body \u2500\u2500
        '<div style="padding:18px 24px 0;">'
        '<div style="background:#faf9ff;border:1px solid #e8e2ff;border-radius:10px;overflow:hidden;margin-bottom:14px;">'
        '<div style="display:flex;align-items:center;padding:12px 16px;gap:12px;">'
        '<span style="font-size:11.5px;font-weight:600;color:#a993f5;letter-spacing:.03em;'
        'text-transform:uppercase;width:70px;flex-shrink:0;">Instance</span>'
        '<span id="cfrm-inst" style="font-size:14px;font-weight:700;color:#1a1d2e;letter-spacing:-.01em;"></span>'
        '</div>'
        '<div style="display:flex;align-items:center;padding:12px 16px;gap:12px;border-top:1px solid #e8e2ff;">'
        '<span style="font-size:11.5px;font-weight:600;color:#a993f5;letter-spacing:.03em;'
        'text-transform:uppercase;width:70px;flex-shrink:0;">Date</span>'
        '<span id="cfrm-date" style="font-size:14px;font-weight:700;color:#1a1d2e;letter-spacing:-.01em;"></span>'
        '</div>'
        '</div>'
        '<div style="display:flex;align-items:flex-start;gap:10px;'
        'background:#ede9fd;border:1px solid #c4b5fd;border-radius:9px;'
        'padding:12px 14px;margin-bottom:22px;">'
        '<div style="width:18px;height:18px;background:#6c54e8;border-radius:50%;'
        'display:grid;place-items:center;flex-shrink:0;margin-top:1px;">'
        '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" '
        'stroke-width="2.5" stroke-linecap="round">'
        '<line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>'
        '</svg></div>'
        '<span style="font-size:13px;color:#4c1d95;font-weight:500;line-height:1.5;">'
        '\uc704 \ubc94\uc704\uc758 \ud30c\ud2f0\uc158 \ud14c\uc774\ube14\uc744 \uc0dd\uc131\ud569\ub2c8\ub2e4.</span>'
        '</div>'
        '</div>'
        # \u2500\u2500 Footer \u2500\u2500
        '<div style="padding:0 24px 22px;display:flex;align-items:center;justify-content:flex-end;gap:8px;">'
        '<button onclick="_cfrm_cancel()" '
        'style="padding:9px 22px;border-radius:9px;font-size:13.5px;font-weight:600;cursor:pointer;'
        'transition:all .15s;border:1px solid #e4e6ed;background:#f4f5f8;color:#6b7280;"'
        ' onmouseover="this.style.background=\'#e9eaee\';this.style.color=\'#1a1d2e\'"'
        ' onmouseout="this.style.background=\'#f4f5f8\';this.style.color=\'#6b7280\'">\ucde8\uc18c</button>'
        '<button id="cfrm-ok-btn" '
        'style="padding:9px 28px;border-radius:9px;font-size:13.5px;font-weight:600;cursor:pointer;'
        'transition:all .15s;border:none;background:#6c54e8;color:#fff;'
        'box-shadow:0 2px 8px rgba(108,84,232,.35);"'
        ' onmouseover="this.style.background=\'#5a43d0\';this.style.boxShadow=\'0 4px 16px rgba(108,84,232,.45)\';this.style.transform=\'translateY(-1px)\'"'
        ' onmouseout="this.style.background=\'#6c54e8\';this.style.boxShadow=\'0 2px 8px rgba(108,84,232,.35)\';this.style.transform=\'\'">\uc0dd\uc131</button>'
        '</div>'
        '</div>'
        '</div>'
    )

    js = (
        '<script>'
        'var _curInst=null,_curEl=null,_cht=null,_cpinned=false;'
        'function _cpos(el,tt){tt.style.left="-9999px";tt.style.top="0";tt.style.display="block";var tw=tt.offsetWidth;var th=tt.offsetHeight;var r=el.getBoundingClientRect();var x=r.left;var y=r.bottom+6;if(x+tw>window.innerWidth-8)x=window.innerWidth-tw-8;if(x<8)x=8;if(y+th>window.innerHeight-8)y=r.top-th-6;if(y<8)y=8;tt.style.left=x+"px";tt.style.top=y+"px";}'
        'function _chide(){if(_cpinned)return;_cht=setTimeout(function(){document.getElementById("create-tt").style.display="none";},150);}'
        'function _cclose(){_cpinned=false;clearTimeout(_cht);document.getElementById("create-tt").style.display="none";}'
        'function _cshow(e,el){'
        '  clearTimeout(_cht);'
        '  _curInst=el.dataset.inst;_curEl=el;'
        '  var tt=document.getElementById("create-tt");'
        '  var eb=document.getElementById("create-exec-btn");'
        '  var xb=document.getElementById("create-tt-close");'
        '  eb.disabled=false;eb.textContent="Create";eb.style.opacity="1";'
        '  eb.style.borderColor="#3b82f6";eb.style.color="#3b82f6";eb.style.background="transparent";'
        '  if(xb&&!_cpinned)xb.style.display="none";'
        '  document.getElementById("create-tt-title").textContent=_curInst+" - Partition Create";'
        '  document.getElementById("create-tt-from").value=el.dataset.from;'
        '  document.getElementById("create-tt-to").value=el.dataset.to;'
        '  _cpos(el,tt);'
        '  tt.style.display="block";'
        '}'
        'function _doCreate(){'
        '  var df=document.getElementById("create-tt-from").value;'
        '  var dt=document.getElementById("create-tt-to").value;'
        '  if(!df||!dt){alert("\ub0a0\uc9dc\ub97c \uc120\ud0dd\ud574\uc8fc\uc138\uc694.");return;}'
        '  if(df>dt){alert("Date From\uc774 Date To\ubcf4\ub2e4 \ub2a6\uc744 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.");return;}'
        '  document.getElementById("cfrm-inst").textContent=_curInst;'
        '  document.getElementById("cfrm-date").textContent=df+" ~ "+dt;'
        '  document.getElementById("cfrm-ok-btn").onclick=function(){_cfrm_cancel();_execCreate(df,dt);};'
        '  document.getElementById("create-confirm-ov").style.display="flex";'
        '}'
        'function _cfrm_cancel(){'
        '  document.getElementById("create-confirm-ov").style.display="none";'
        '}'
        'function _execCreate(df,dt){'
        '  var eb=document.getElementById("create-exec-btn");'
        '  eb.disabled=true;eb.textContent="Running...";eb.style.opacity=".5";'
        '  var url="__UTILS_BASE__/api/create-partition"'
        '    +"?instance_name="+encodeURIComponent(_curInst)'
        '    +"&date_from="+df+"&date_to="+dt;'
        '  fetch(url).then(function(r){return r.json();})'
        '  .then(function(d){'
        '    if(d.ok){'
        '      eb.textContent="Done";eb.style.borderColor="#22c55e";'
        '      eb.style.color="#22c55e";eb.style.opacity="1";'
        '      alert("\ud30c\ud2f0\uc158 \uc0dd\uc131 \uc644\ub8cc: "+_curInst);'
        '      _cclose();location.reload();'
        '    }else{'
        '      eb.disabled=false;eb.textContent="Create";eb.style.opacity="1";'
        '      alert("\uc624\ub958: "+(d.error||"Unknown error"));'
        '    }'
        '  })'
        '  .catch(function(){'
        '    eb.disabled=false;eb.textContent="Create";eb.style.opacity="1";'
        '    _showToast("\uc694\uccad \uc2e4\ud328","#ef4444");'
        '  });'
        '}'
        'function _showToast(msg,color){'
        '  var t=document.getElementById("part-toast");'
        '  var m=document.getElementById("part-toast-msg");'
        '  m.style.color=color||"var(--c-main)";m.textContent=msg;'
        '  t.style.display="block";'
        '  setTimeout(function(){t.style.display="none";},3500);'
        '}'
        'document.addEventListener("DOMContentLoaded",function(){'
        '  document.querySelectorAll(".create-hint").forEach(function(el){'
        '    el.addEventListener("mouseenter",function(e){if(!_cpinned)_cshow(el,el);});'
        '    el.addEventListener("mouseleave",function(){_chide();});'
        '    el.addEventListener("click",function(e){e.stopPropagation();_cpinned=true;'
        '      document.getElementById("create-tt-close").style.display="inline-flex";document.getElementById("create-tt-close").style.alignItems="center";document.getElementById("create-tt-close").style.justifyContent="center";_cshow(el,el);});'
        '  });'
        '  var tt=document.getElementById("create-tt");'
        '  tt.addEventListener("mouseenter",function(){clearTimeout(_cht);});'
        '  tt.addEventListener("mouseleave",function(){_chide();});'
        '  document.addEventListener("click",function(e){'
        '    if(_cpinned&&window._ovOutside&&window._ovOutside(tt,e)&&!e.target.classList.contains("create-hint"))_cclose();'
        '  });'
        '  var _cfo=document.getElementById("create-confirm-ov");'
        '  _cfo.addEventListener("mousedown",function(e){this._md=(e.target===this);});'
        '  _cfo.addEventListener("click",function(e){'
        '    if(this._md&&e.target===this)_cfrm_cancel();'
        '  });'
        '});'
        '</script>'
    ).replace('__UTILS_BASE__', _UTILS_BASE)

    fui, fscript = _inst_filter_block('inst-tbl')
    # 카드 안에서는 카드 헤더 padding(14px)만 사용 — fui 자체 외부 마진 제거
    fui = fui.replace('margin-bottom:14px;', '')
    body = ''.join([
        hdr,
        '<div class="insp-card">',
        '<div class="insp-card-hdr">', fui, '</div>',
        '<div class="insp-card-body">', table_html, '</div>',
        '</div>',
        tooltip_html, toast_html, confirm_modal_html, js,
        _ts(), _sql_embed(sql),
        fscript,
    ])
    return _page('partition_create', title, body)

def _pg_create_partition(instance_name, date_from_str, date_to_str):
    """Create PG partitions via public.insp_mxg_partition_create (wraps mxg_partition_create).

    Trigger function(_insert_func) is always refreshed at the end, matching DGServer behavior.
    """
    from db_utils import _db_cfg
    from datetime import date as _d, timedelta as _td
    import psycopg2 as _pg2

    repo = _db_cfg()
    try:
        conn = _pg2.connect(
            host=repo.get("ip", ""), port=int(repo.get("port", "5432") or "5432"),
            user=repo.get("user", ""), password=repo.get("password", ""),
            dbname=repo.get("sid", ""))
        conn.autocommit = True
        cur = conn.cursor()
    except Exception as e:
        return json.dumps({"ok": False, "error": "DB connection failed: " + str(e)})

    try:
        if date_from_str and date_to_str:
            d_from = date_from_str
            d_to = date_to_str
        else:
            d_from = (_d.today() - _td(days=1)).isoformat()
            d_to = (_d.today() + _td(days=3)).isoformat()

        # 테이블이 실제로 존재하지 않는 stale apm_partition_history 레코드 제거
        # (수동 DROP 등으로 테이블이 사라졌지만 이력이 남아 재생성이 막히는 경우 방지)
        cur.execute(
            "DELETE FROM apm_partition_history "
            "WHERE db_id = (SELECT db_id FROM apm_db_info WHERE instance_name = upper(%s)) "
            "  AND NOT EXISTS ("
            "    SELECT 1 FROM pg_tables "
            "    WHERE schemaname = lower(%s) "
            "      AND tablename = LOWER(partition_name)"
            "  )",
            (instance_name, instance_name)
        )

        cur.execute(
            "SELECT public.insp_mxg_partition_create(%s, %s::date, %s::date, false, NULL)",
            (instance_name, d_from, d_to))
        created = int(cur.fetchone()[0] or 0)

        cur.close()
        conn.close()

        msg = "Created: %d (date %s ~ %s). Trigger functions refreshed." % (created, d_from, d_to)
        return json.dumps({"ok": True, "created": created, "message": msg})

    except Exception as e:
        try: cur.close(); conn.close()
        except: pass
        return json.dumps({"ok": False, "error": str(e)})


def api_create_partition(instance_name_str, date_from_str='', date_to_str=''):
    from db_utils import run_db_exec, _db_cfg
    if not instance_name_str:
        return json.dumps({"ok": False, "error": "instance_name required"})

    pg = "postgresql" in _db_cfg().get("db_type", "").lower()
    if pg:
        return _pg_create_partition(instance_name_str, date_from_str, date_to_str)

    # 1. Lookup db_id
    safe = instance_name_str.replace("'", "''")
    out, err = run_db_query(
        "SELECT db_id FROM apm_db_info WHERE instance_name = '%s'" % safe
    )
    if err:
        return json.dumps({"ok": False, "error": err})
    headers, rows = _parse_db_table(out or '')
    if not rows:
        return json.dumps({"ok": False, "error": "Instance not found: " + instance_name_str})

    db_id = rows[0][0].strip()

    # 2. Build procedure call with optional date range
    if date_from_str and date_to_str:
        exec_sql = (
            "BEGIN INSP_PARTITION_CREATE_TARGET("
            "p_db_id => %s, "
            "p_date_from => TO_DATE('%s','YYYY-MM-DD'), "
            "p_date_to   => TO_DATE('%s','YYYY-MM-DD')); END;"
            % (db_id, date_from_str, date_to_str)
        )
    else:
        exec_sql = "BEGIN INSP_PARTITION_CREATE_TARGET(p_db_id => %s); END;" % db_id
    err = run_db_exec(exec_sql)
    if err:
        return json.dumps({"ok": False, "error": err})
    return json.dumps({"ok": True, "db_id": db_id})



_PG_FUNC_SESSION = """
CREATE OR REPLACE FUNCTION insp_session_check()
RETURNS TABLE(db_id INTEGER, instance_name VARCHAR(64), last_time TIMESTAMP) AS $$
DECLARE sql_text TEXT;
BEGIN
  SELECT string_agg(
    format(
      'SELECT a.db_id::integer,
              a.instance_name::varchar(64),
              (SELECT max(b.time)
               FROM %I.ora_session_list_count b
               WHERE b.db_id = a.db_id
                 AND b.partition_key = (
                       SELECT max(c.partition_key)
                       FROM %I.ora_session_list_count c
                       WHERE c.db_id = a.db_id)
              ) AS last_time
       FROM apm_db_info a
       WHERE lower(a.instance_name) = %L',
      lower(adi.instance_name),
      lower(adi.instance_name),
      lower(adi.instance_name)
    ), ' UNION ALL '
  ) INTO sql_text FROM apm_db_info adi;
  RETURN QUERY EXECUTE sql_text;
END;
$$ LANGUAGE plpgsql
"""

_PG_FUNC_ALARM = """
CREATE OR REPLACE FUNCTION insp_alarm_history_check()
RETURNS TABLE(db_id INTEGER, instance_name VARCHAR(64), alarm_name VARCHAR(128), count BIGINT) AS $$
DECLARE sql_text TEXT;
BEGIN
  SELECT string_agg(
    format(
      'SELECT a.db_id::integer, a.instance_name::varchar(64), b.name::varchar(128), count(*) AS count
       FROM apm_db_info a
       JOIN %I.ora_alarm_history b ON a.db_id = b.db_id
       WHERE b.time >= date_trunc(''day'', NOW() - INTERVAL ''1 month'')
         AND b.name IN (''DB Down, Listener Stop'',''RTS Daemon Disconnect'',''RTS Server Down'')
       GROUP BY a.db_id, a.instance_name, b.name',
      lower(adi.instance_name)
    ), ' UNION ALL '
  ) INTO sql_text FROM apm_db_info adi;
  RETURN QUERY EXECUTE sql_text;
END;
$$ LANGUAGE plpgsql
"""

_PG_FUNC_QUERY = """
CREATE OR REPLACE FUNCTION insp_query_check()
RETURNS TABLE (
    db_id INTEGER,
    instance_name VARCHAR(64),
    plan_status VARCHAR(8),
    bind_status VARCHAR(8),
    tablespace_status VARCHAR(8),
    parameter_status VARCHAR(8)
) AS $$
DECLARE sql_text TEXT;
BEGIN
  SELECT string_agg(
    format(
      $f$SELECT a.db_id::integer,
         a.instance_name::varchar(64),
         (CASE WHEN COALESCE(lc.download_sql_plan,'N') <> 'Y' THEN 'OFF'
               WHEN EXISTS(SELECT 1 FROM %I.ora_sql_plan b WHERE b.db_id=a.db_id AND b.partition_key=%L) THEN 'OK'
               ELSE 'CHECK' END)::varchar(8),
         (CASE WHEN COALESCE(lc.download_sql_bind,'N') <> 'Y' THEN 'OFF'
               WHEN EXISTS(SELECT 1 FROM %I.ora_bind_value c WHERE c.db_id=a.db_id AND c.partition_key=%L) THEN 'OK'
               ELSE 'CHECK' END)::varchar(8),
         (CASE WHEN COALESCE(lc.download_tablespace,'N') <> 'Y' THEN 'OFF'
               WHEN EXISTS(SELECT 1 FROM %I.ora_tablespace_info d WHERE d.db_id=a.db_id AND d.partition_key=%L) THEN 'OK'
               ELSE 'CHECK' END)::varchar(8),
         (CASE WHEN COALESCE(lc.download_parameter,'N') <> 'Y' THEN 'OFF'
               WHEN EXISTS(SELECT 1 FROM %I.ora_db_parameter e WHERE e.db_id=a.db_id AND e.partition_key=%L) THEN 'OK'
               ELSE 'CHECK' END)::varchar(8)
       FROM apm_db_info a
       LEFT JOIN ora_lc_config lc ON lc.db_id = a.db_id
       WHERE lower(a.instance_name)=%L$f$,
      lower(adi.instance_name), to_char(current_date-1,'yymmdd')||lpad(adi.db_id::text,3,'0'),
      lower(adi.instance_name), to_char(current_date-1,'yymmdd')||lpad(adi.db_id::text,3,'0'),
      lower(adi.instance_name), to_char(current_date-1,'yymmdd')||lpad(adi.db_id::text,3,'0'),
      lower(adi.instance_name), to_char(current_date-1,'yymmdd')||lpad(adi.db_id::text,3,'0'),
      lower(adi.instance_name)
    ), ' UNION ALL '
  ) INTO sql_text FROM apm_db_info adi;
  RETURN QUERY EXECUTE sql_text || ' ORDER BY db_id';
END;
$$ LANGUAGE plpgsql
"""

_PG_FUNC_PARTITION_CREATE = """
CREATE OR REPLACE FUNCTION public.insp_mxg_partition_create(
    schemaname  varchar,
    d_from      date,
    d_to        date,
    is_unlogged boolean default false,
    p_tabname   varchar default NULL
) RETURNS integer
AS $$
declare
  _cur1      refcursor;
  _db_id     smallint;
  _ret       integer := 0;
  _tabname   varchar(100);
  _partname  varchar(100);
  _msg       varchar(500);
  _prev_tab  varchar(100) default 'at first';
  _t_sleep   float;
  _t_start   double precision default date_part('epoch', clock_timestamp());
  _part_cnt  integer := 0;
  _idx_cnt   integer := 0;
  unlogged_char varchar(10) default '';
  _fn_ret    integer;
begin
  if is_unlogged then
    unlogged_char := 'unlogged';
  end if;

  select db_id into _db_id
    from apm_db_info
   where instance_name = upper(schemaname);

  if _db_id is null then
    raise exception 'insp_mxg_partition_create: instance % not found in apm_db_info', schemaname;
  end if;

  open _cur1 for execute(
    'select lower(m.table_name) as tabname, '
    '       lower(m.table_name)||''_p''||to_char(d,''yymmdd'')|| '
    '       ltrim(to_char('||_db_id||',''000'')) as partname '
    '  from apm_partition_manage m '
    ' cross join generate_series($1::date, $2::date, ''1 day'') d '
    ' where m.db_id = 0 '
    '   and ($3 is null or lower(m.table_name) = lower($3)) '
    ' except '
    'select lower(table_name), lower(partition_name) '
    '  from apm_partition_history '
    ' where db_id = '||_db_id||
    ' order by 2'
  ) using d_from, d_to, p_tabname;

  loop
    fetch _cur1 into _tabname, _partname;
    exit when not found;

    if _prev_tab = 'at first' then
      _prev_tab := _tabname;
    elsif _prev_tab <> _tabname then
      _prev_tab := _tabname;
      _t_sleep := round(((date_part('epoch', clock_timestamp()) - _t_start) / 10)::numeric, 2);
      if _t_sleep > 1 then _t_sleep := 1; end if;
      perform pg_sleep(_t_sleep);
      _t_start := date_part('epoch', clock_timestamp());
    end if;

    _msg := 'create ' || unlogged_char || ' table ' || schemaname || '.' || _partname
         || ' ( check ( partition_key=' || substring(_partname, length(_tabname)+3)
         || ' ) ) inherits ( ' || schemaname || '.' || _tabname || ' )';

    begin
      execute _msg;
      _ret := _ret + 1;
      _idx_cnt := _idx_cnt + MXG_PARTITION_INDEX_CREATE(schemaname, _partname);
      insert into apm_partition_history(db_id, table_name, partition_name)
             values (_db_id, _tabname, _partname);
      _part_cnt := _part_cnt + 1;
    exception when others then
      insert into apm_job_log(time, sql_text, err)
             values (now(), substring(_msg, 0, 200), substring(sqlerrm, 0, 100));
    end;
  end loop;
  close _cur1;

  begin
    _fn_ret := MXG_PARTITION_FUNCTION_CREATE(schemaname);
  exception when others then
    insert into apm_job_log(time, sql_text, err)
           values (now(), 'mxg_partition_function_create('||schemaname||')',
                   substring(sqlerrm, 0, 100));
  end;

  begin
    _fn_ret := MXG_ANALYZE_PG_CATALOG();
  exception when others then
    insert into apm_job_log(time, sql_text, err)
           values (now(), 'mxg_analyze_pg_catalog()', substring(sqlerrm, 0, 100));
  end;

  return _ret;
end;
$$ LANGUAGE plpgsql
"""

def api_create_procedure():
    from db_utils import run_db_exec, _db_cfg
    pg = "postgresql" in _db_cfg().get("db_type", "").lower()
    if pg:
        errors = []
        for name, ddl in [("insp_session_check", _PG_FUNC_SESSION),
                           ("insp_alarm_history_check", _PG_FUNC_ALARM),
                           ("insp_query_check", _PG_FUNC_QUERY),
                           ("insp_mxg_partition_create", _PG_FUNC_PARTITION_CREATE)]:
            err = run_db_exec(ddl)
            if err:
                errors.append(name + ": " + err)
        if errors:
            return json.dumps({"ok": False, "error": "; ".join(errors)})
        return json.dumps({"ok": True, "message": "insp_session_check, insp_alarm_history_check, insp_query_check, insp_mxg_partition_create 생성 완료"})
    err1 = run_db_exec(_PROC_DDL)
    if err1:
        return json.dumps({"ok": False, "error": "CREATE_TARGET: " + err1})
    err2 = run_db_exec(_DROP_PROC_DDL)
    if err2:
        return json.dumps({"ok": False, "error": "DROP_TARGET: " + err2})
    return json.dumps({"ok": True, "message": "INSP_PARTITION_CREATE_TARGET, INSP_PARTITION_DROP_TARGET 생성 완료"})


def page_partition_drop():
    sql      = _get_sql("partition_drop")
    title    = 'Partition Drop Check'
    sub_text = 'Checks for old partitions exceeding retention policy'

    if not sql:
        body = ''.join([
            _page_title_html(title, *_HELP.get('partition_drop', (title, ''))),
            _warn_box("현재 DB 타입에서는 지원하지 않는 쿼리입니다."),
        ])
        return _page('partition_drop', title, body)

    out, err = run_db_query(sql)
    if err:
        body = ''.join([
            _page_title_html(title, *_HELP.get('partition_drop', (title, ''))),
            '<div class="card">' + _warn_box(err) + '</div>',
            _ts(),
        ])
        return _page('partition_drop', title, body)

    headers, rows = _parse_db_table(out or "")
    if not headers:
        body = ''.join([
            _page_title_html(title, *_HELP.get('partition_drop', (title, ''))),
            '<div class="card">' + _warn_box("조회된 데이터가 없습니다.") + '</div>',
            _ts(),
        ])
        return _page('partition_drop', title, body)

    idx_dbid = next((i for i, h in enumerate(headers) if 'DB ID' in h.upper()), -1)
    idx_inst = next((i for i, h in enumerate(headers) if 'INSTANCE' in h.upper()), -1)
    idx_cnt  = next((i for i, h in enumerate(headers) if 'CNT' in h.upper() or 'COUNT' in h.upper()), -1)
    _st_set  = set(i for i, h in enumerate(headers) if 'STATUS' in h.upper())

    th_cells = ''.join('<th class="sortable" onclick="tbSort(this)">%s<span class="sort-ic"></span></th>' % h.replace('_', ' ').upper() for h in headers)
    tr_rows  = ''
    for row in rows:
        row_list  = list(row)
        db_id_val = row_list[idx_dbid].strip() if 0 <= idx_dbid < len(row_list) else ""
        inst_val  = row_list[idx_inst].strip() if 0 <= idx_inst < len(row_list) else db_id_val
        cnt_str   = row_list[idx_cnt].strip()  if 0 <= idx_cnt  < len(row_list) else "0"
        has_drops = cnt_str.isdigit() and int(cnt_str) > 0
        cells = []
        for i, val in enumerate(row_list):
            if i == idx_cnt and has_drops:
                cells.append(
                    '<td class="drop-hint" data-dbid="%s" data-inst="%s" '
                    'style="cursor:pointer;font-weight:700;color:#fca5a5;">%s</td>' % (db_id_val, inst_val, val)
                )
            elif i in _st_set:
                uv = val.strip().upper()
                if uv == 'OK':
                    badge = _badge('ok', val)
                elif uv in ('CHECK', 'ERROR'):
                    badge = _badge('critical', val)
                elif uv == 'OFF':
                    badge = _badge('off', val)
                else:
                    badge = val
                cells.append('<td>%s</td>' % badge)
            else:
                cells.append('<td>%s</td>' % val)
        tr_rows += '<tr>' + ''.join(cells) + '</tr>'

    table_html = (
        '<div class="tbl-wrap">'
        '<table class="svc-table" id="inst-tbl">'
        '<thead><tr>%s</tr></thead>'
        '<tbody>%s</tbody>'
        '</table>'
        '</div>'
    ) % (th_cells, tr_rows)

    tooltip_html = (
        '<div id="drop-tt" data-ov-track style="display:none;position:fixed;z-index:9999;'
        'background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;'
        'padding:12px 16px;box-shadow:0 8px 32px rgba(0,0,0,.35);max-width:520px;'
        'min-width:220px;pointer-events:auto;">'
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
        '<div id="drop-tt-title" style="font-size:.7rem;font-weight:700;text-transform:uppercase;'
        'letter-spacing:.07em;color:var(--c-dim);"></div>'
        '<button id="drop-exec-btn" onclick="_doDrop()"'
        ' style="padding:2px 10px;border-radius:20px;border:1px solid #ef4444;color:#ef4444;'
        'background:transparent;font-size:.72rem;font-weight:600;cursor:pointer;'
        'letter-spacing:.03em;transition:all .15s;white-space:nowrap;flex-shrink:0;margin-left:10px;"'
        ' onmouseover="if(!this.disabled){this.style.background=\'#ef4444\';this.style.color=\'#fff\'}"'
        ' onmouseout="if(!this.disabled){this.style.background=\'transparent\';this.style.color=\'#ef4444\'}">'
        'Drop</button>'
        '<button id="drop-tt-close" onclick="_dclose()"'
        ' style="display:none;margin-left:8px;width:22px;height:22px;border-radius:50%;'
        'border:1px solid var(--bd);color:var(--c-muted);background:transparent;'
        'font-size:.85rem;cursor:pointer;line-height:1;transition:all .15s;flex-shrink:0;"'
        ' onmouseover="this.style.background=\'var(--bg-main)\';this.style.color=\'var(--c-main)\';this.style.borderColor=\'var(--c-main)\'"'
        ' onmouseout="this.style.background=\'transparent\';this.style.color=\'var(--c-muted)\';this.style.borderColor=\'var(--bd)\'">&times;</button>'
        '</div>'
        '<div id="drop-tt-body" style="max-height:300px;overflow-y:auto;"></div>'
        '</div>'
    )

    js = (
        '<script>'
        'var _dc={};var _dht=null;var _curDbid=null;var _curInst=null;var _pinned=false;'
        'function _dpos(el,tt){var r=el.getBoundingClientRect();var x=r.left+r.width/2-tt.offsetWidth/2;var y=r.bottom+6;if(x<8)x=8;if(x+tt.offsetWidth>window.innerWidth-8)x=window.innerWidth-tt.offsetWidth-8;if(y+tt.offsetHeight>window.innerHeight-8)y=r.top-tt.offsetHeight-6;tt.style.left=x+"px";tt.style.top=y+"px";}'
        'function _dhide(){if(_pinned)return;_dht=setTimeout(function(){document.getElementById("drop-tt").style.display="none";},150);}'
        'function _dclose(){_pinned=false;clearTimeout(_dht);document.getElementById("drop-tt").style.display="none";}'
        'function _dshow(trigEl,dbid,inst){'
        'clearTimeout(_dht);'
        '_curDbid=dbid;_curInst=inst||dbid;'
        'var tt=document.getElementById("drop-tt");'
        'var tb=document.getElementById("drop-tt-body");'
        'var eb=document.getElementById("drop-exec-btn");'
        'eb.disabled=false;eb.textContent="Drop";eb.style.opacity="1";'
        'var xb=document.getElementById("drop-tt-close");if(xb&&!_pinned)xb.style.display="none";'
        'eb.style.borderColor="#ef4444";eb.style.color="#ef4444";eb.style.background="transparent";'
        'document.getElementById("drop-tt-title").textContent="DB ID "+dbid+" - Partitions to drop";'
        'tt.style.display="block";_dpos(trigEl,tt);'
        'if(_dc[dbid]!==undefined){tb.innerHTML=_dc[dbid];tt.style.display="block";return;}'
        'tb.innerHTML=\'<span style="color:var(--c-muted)">Loading\u2026</span>\';'
        'tt.style.display="block";'
        'fetch("' + _UTILS_BASE + '/api/drop-list?db_id="+dbid)'
        '.then(function(r){return r.json();})'
        '.then(function(d){'
        'if(!d.ok){_dc[dbid]=\'<span style="color:#fca5a5">\'+d.error+\'</span>\';tb.innerHTML=_dc[dbid];return;}'
        'if(!d.groups||!d.groups.length){_dc[dbid]=\'<span style="color:var(--c-muted)">항목이 없습니다.</span>\';tb.innerHTML=_dc[dbid];return;}'
        'var html="";'
        'd.groups.forEach(function(g,gi){'
        'html+=\'<div style="\'+(gi>0?\'margin-top:10px;border-top:1px solid var(--bd);padding-top:10px;\':\'\')+\'">\';'
        'html+=\'<div style="font-size:.82rem;font-weight:700;color:var(--c-accent);letter-spacing:.02em;margin-bottom:5px;">\u25b8 \'+g.table+\'</div>\';'
        'g.partitions.forEach(function(p){'
        'html+=\'<div style="display:flex;align-items:center;padding-left:10px;margin-bottom:3px;">\';'
        'html+=\'<span style="color:var(--c-dim);margin-right:7px;font-size:.8rem;line-height:1;">\u2514\u2500</span>\';'
        'html+=\'<span style="font-size:.8rem;color:var(--c-primary);letter-spacing:.01em;">\'+p+\'</span>\';'
        'html+=\'</div>\';'
        '});'
        'html+=\'</div>\';'
        '});'
        '_dc[dbid]=html;tb.innerHTML=html;})'
        '.catch(function(){tb.innerHTML="Request failed.";});}'
        'var _dpPoll=null;'
        'function _doDrop(){'
        'if(!_curDbid)return;'
        '_dropShowModal();'
        '}'
        'function _dropShowModal(){'
        'var ov=document.getElementById("drop-confirm-ov");'
        'document.getElementById("drop-cfrm-dbid").textContent=_curInst;'
        'ov.style.display="flex";'
        'ov.onclick=function(e){if(e.target===ov)_dropCancel();};'
        '}'
        'function _dropCancel(){'
        'document.getElementById("drop-confirm-ov").style.display="none";'
        '}'
        'function _dropExec(){'
        '_dropCancel();'
        'var btn=document.getElementById("drop-exec-btn");'
        'btn.disabled=true;btn.textContent="Running...";btn.style.opacity=".5";'
        'fetch("' + _UTILS_BASE + '/api/drop-partitions?db_id="+_curDbid)'
        '.then(function(r){return r.json();})'
        '.then(function(d){'
        'if(d.ok){_dpStartPoll();}'
        'else{btn.disabled=false;btn.textContent="Drop";btn.style.opacity="1";alert(d.error||"failed");}'
        '}).catch(function(){btn.disabled=false;btn.textContent="Drop";btn.style.opacity="1";});}'
        'function _dpStartPoll(){if(_dpPoll)clearInterval(_dpPoll);_dpPoll=setInterval(_dpCheck,2000);}'
        'function _dpCheck(){'
        'fetch("' + _UTILS_BASE + '/api/drop-partitions-status")'
        '.then(function(r){return r.json();})'
        '.then(function(s){'
        'var btn=document.getElementById("drop-exec-btn");'
        'if(s.running){'
        'btn.textContent="Dropping... "+s.dropped+(s.total?"/"+s.total:"");'
        '}else{'
        'clearInterval(_dpPoll);_dpPoll=null;'
        'if(s.error){'
        'btn.textContent="Error";btn.style.opacity="1";btn.disabled=false;alert(s.error);'
        '}else{'
        'btn.textContent="Done ("+s.dropped+") "+s.elapsed+"s";'
        'btn.style.borderColor="#22c55e";btn.style.color="#22c55e";btn.style.opacity="1";'
        'delete _dc[_curDbid];'
'alert("\ud30c\ud2f0\uc158 \uc0ad\uc81c \uc644\ub8cc: "+s.dropped+"\uAC74 ("+s.elapsed+"s)");location.reload();'
        '}}});}'
        'document.addEventListener("DOMContentLoaded",function(){'
        'var tt=document.getElementById("drop-tt");'
        'tt.addEventListener("mouseenter",function(){clearTimeout(_dht);});'
        'tt.addEventListener("mouseleave",_dhide);'
        'document.querySelectorAll(".drop-hint").forEach(function(el){'
        'el.addEventListener("mouseenter",function(e){if(!_pinned)_dshow(el,el.dataset.dbid,el.dataset.inst);});'
        'el.addEventListener("mouseleave",_dhide);'
        'el.addEventListener("click",function(e){e.stopPropagation();_pinned=true;document.getElementById("drop-tt-close").style.display="inline-block";_dshow(el,el.dataset.dbid,el.dataset.inst);});'
        '});'
        'document.addEventListener("click",function(e){var tt=document.getElementById("drop-tt");if(_pinned&&tt&&window._ovOutside&&window._ovOutside(tt,e)){_dclose();}});'
        '});'
        '</script>'
    )

    drop_confirm_modal_html = (
        '<style>'
        '@keyframes _dmIn{from{opacity:0;transform:scale(.94) translateY(8px)}to{opacity:1;transform:scale(1) translateY(0)}}'
        '#drop-confirm-ov>div{animation:_dmIn .25s cubic-bezier(.34,1.56,.64,1) both}'
        '</style>'
        '<div id="drop-confirm-ov" style="display:none;position:fixed;inset:0;z-index:10000;'
        'background:rgba(15,15,30,.45);backdrop-filter:blur(6px);'
        'align-items:center;justify-content:center;padding:24px;">'
        '<div style="background:#ffffff;border-radius:16px;width:100%;max-width:400px;'
        'box-shadow:0 0 0 1px rgba(108,84,232,.12),0 24px 60px rgba(0,0,0,.18);overflow:hidden;">'
        # Header
        '<div style="padding:22px 24px 0;display:flex;align-items:flex-start;justify-content:space-between;">'
        '<div>'
        '<div style="width:42px;height:42px;background:#ede9fd;border-radius:12px;'
        'display:grid;place-items:center;margin-bottom:14px;">'
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6c54e8" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="3 6 5 6 21 6"/>'
        '<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>'
        '<path d="M10 11v6"/><path d="M14 11v6"/>'
        '<path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>'
        '</svg></div>'
        '<div style="font-size:16px;font-weight:700;color:#1a1d2e;letter-spacing:-.01em;margin-bottom:4px;">'
        '파티션 삭제 확인</div>'
        '<div style="font-size:12.5px;color:#9ca3af;">아래 정보를 확인하고 삭제를 진행하세요</div>'
        '</div>'
        '<button onclick="_dropCancel()" '
        'style="width:28px;height:28px;border:1px solid #e4e6ed;border-radius:7px;background:#fff;'
        'display:grid;place-items:center;cursor:pointer;color:#9ca3af;font-size:14px;'
        'flex-shrink:0;margin-top:4px;transition:border-color .15s,color .15s;"'
        ' onmouseover="this.style.borderColor=\'#ef4444\';this.style.color=\'#ef4444\'"'
        ' onmouseout="this.style.borderColor=\'#e4e6ed\';this.style.color=\'#9ca3af\'">&#x2715;</button>'
        '</div>'
        # Body
        '<div style="padding:18px 24px 0;">'
        '<div style="background:#faf9ff;border:1px solid #e8e2ff;border-radius:10px;overflow:hidden;margin-bottom:14px;">'
        '<div style="display:flex;align-items:center;padding:12px 16px;gap:12px;">'
        '<span style="font-size:11.5px;font-weight:600;color:#a993f5;letter-spacing:.03em;'
        'text-transform:uppercase;width:70px;flex-shrink:0;">Instance</span>'
        '<span id="drop-cfrm-dbid" style="font-size:14px;font-weight:700;color:#1a1d2e;letter-spacing:-.01em;"></span>'
        '</div>'
        '</div>'
        '<div style="display:flex;align-items:flex-start;gap:10px;'
        'background:#ede9fd;border:1px solid #c4b5fd;border-radius:9px;'
        'padding:12px 14px;margin-bottom:22px;">'
        '<div style="width:18px;height:18px;background:#6c54e8;border-radius:50%;'
        'display:grid;place-items:center;flex-shrink:0;margin-top:1px;">'
        '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" '
        'stroke-width="2.5" stroke-linecap="round">'
        '<line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>'
        '</svg></div>'
        '<span style="font-size:13px;color:#4c1d95;font-weight:500;line-height:1.5;">'
        '선택된 DB의 파티션 테이블을 모두 삭제합니다. 이 작업은 되돌릴 수 없습니다.</span>'
        '</div>'
        '</div>'
        # Footer
        '<div style="padding:0 24px 22px;display:flex;align-items:center;justify-content:flex-end;gap:8px;">'
        '<button onclick="_dropCancel()" '
        'style="padding:9px 22px;border-radius:9px;font-size:13.5px;font-weight:600;cursor:pointer;'
        'transition:all .15s;border:1px solid #e4e6ed;background:#f4f5f8;color:#6b7280;"'
        ' onmouseover="this.style.background=\'#e9eaee\';this.style.color=\'#1a1d2e\'"'
        ' onmouseout="this.style.background=\'#f4f5f8\';this.style.color=\'#6b7280\'">취소</button>'
        '<button onclick="_dropExec()" '
        'style="padding:9px 28px;border-radius:9px;font-size:13.5px;font-weight:600;cursor:pointer;'
        'transition:all .15s;border:none;background:#ef4444;color:#fff;'
        'box-shadow:0 2px 8px rgba(239,68,68,.35);"'
        ' onmouseover="this.style.background=\'#dc2626\';this.style.boxShadow=\'0 4px 16px rgba(239,68,68,.45)\';this.style.transform=\'translateY(-1px)\'"'
        ' onmouseout="this.style.background=\'#ef4444\';this.style.boxShadow=\'0 2px 8px rgba(239,68,68,.35)\';this.style.transform=\'\'">삭제</button>'
        '</div>'
        '</div>'
        '</div>'
    )

    fui, fscript = _inst_filter_block('inst-tbl')
    # 카드 안에서는 카드 헤더 padding(14px)만 사용 — fui 자체 외부 마진 제거
    fui = fui.replace('margin-bottom:14px;', '')
    body = ''.join([
        _page_title_html(title, *_HELP.get('partition_drop', (title, ''))),
        '<div class="insp-card">',
        '<div class="insp-card-hdr">', fui, '</div>',
        '<div class="insp-card-body">', table_html, '</div>',
        '</div>',
        tooltip_html,
        drop_confirm_modal_html,
        js,
        _ts(),
        _sql_embed(sql),
        fscript,
    ])
    return _page('partition_drop', title, body)


def page_partition_time():
    pg  = "postgresql" in _db_cfg().get("db_type", "").lower()
    hdr = _page_title_html('Partition Time Check', *_HELP.get('partition_time', ('Partition Time Check', '')))
    if pg:
        content = _partition_time_pg_cards()
    else:
        content = ('<div class="insp-card"><div class="insp-card-body">'
                   + _partition_time_html() + '</div></div>')
    body = hdr + content + _ts()
    return _page("partition_time", "Partition Time Check", body)


def api_drop_list(db_id_str):
    try:
        db_id = int(db_id_str)
    except (ValueError, TypeError):
        return json.dumps({"ok": False, "error": "Invalid db_id"})
    pg  = "postgresql" in _db_cfg().get("db_type", "").lower()
    sql = _SQL_PG_PARTITION_DROP_LIST.format(db_id=db_id) if pg else _SQL_PARTITION_DROP_LIST.format(db_id=db_id)
    out, err = run_db_query(sql)
    if err:
        return json.dumps({"ok": False, "error": err})
    headers, rows = _parse_db_table(out or "")
    groups = {}
    order  = []
    for row in rows:
        if not row or not row[0].strip():
            continue
        raw = row[0].strip()
        if " / " in raw:
            tbl, part = raw.split(" / ", 1)
        else:
            tbl, part = raw, ""
        if tbl not in groups:
            groups[tbl] = []
            order.append(tbl)
        if part:
            groups[tbl].append(part)
    result = [{"table": t, "partitions": groups[t]} for t in order]
    return json.dumps({"ok": True, "groups": result})


# ── Partition Drop background state ──
_pd_state = {"running": False, "started": None, "finished": None,
             "elapsed": None, "dropped": 0, "total": 0, "error": None}
_pd_lock = threading.Lock()

def _pd_worker_pg(db_id):
    import time as _time
    start = _time.time()
    try:
        import psycopg2
        repo = _db_cfg()
        conn = psycopg2.connect(
            host=repo.get("ip", ""), port=int(repo.get("port", "5432") or "5432"),
            user=repo.get("user", ""), password=repo.get("password", ""),
            dbname=repo.get("sid", ""))
        conn.autocommit = True
        cur = conn.cursor()

        # Get drop targets
        sql = _SQL_PG_PARTITION_DROP_EXEC.format(db_id=db_id)
        from db_utils import _strip_pg_directives
        sql = _strip_pg_directives(sql)
        cur.execute(sql)
        rows = cur.fetchall()
        if not rows:
            with _pd_lock:
                _pd_state["running"] = False
                _pd_state["finished"] = _time.strftime("%Y-%m-%d %H:%M:%S")
                _pd_state["elapsed"] = round(_time.time() - start, 1)
                _pd_state["dropped"] = 0
                _pd_state["total"] = 0
            cur.close(); conn.close()
            return

        with _pd_lock:
            _pd_state["total"] = len(rows)

        dropped = 0
        errors = []
        for row in rows:
            schema = row[0].strip() if row[0] else ""
            tbl = row[1].strip() if len(row) > 1 else ""
            part = row[2].strip() if len(row) > 2 else ""
            if not part:
                continue
            try:
                fqn = "%s.%s" % (schema, part) if schema else part
                cur.execute("DROP TABLE IF EXISTS %s" % fqn)
                # Clean up apm_partition_history
                if tbl:
                    cur.execute("DELETE FROM apm_partition_history "
                                "WHERE db_id = %s AND partition_name = %s",
                                (db_id, part))
                dropped += 1
                with _pd_lock:
                    _pd_state["dropped"] = dropped
            except Exception as e:
                errors.append(str(e)[:60])

        # VACUUM partition history
        try:
            cur.execute("VACUUM apm_partition_history")
        except Exception:
            pass

        elapsed = round(_time.time() - start, 1)
        with _pd_lock:
            _pd_state["running"] = False
            _pd_state["finished"] = _time.strftime("%Y-%m-%d %H:%M:%S")
            _pd_state["elapsed"] = elapsed
            _pd_state["dropped"] = dropped
            _pd_state["error"] = "; ".join(errors[:3]) if errors else None

        cur.close()
        conn.close()
    except Exception as e:
        with _pd_lock:
            _pd_state["running"] = False
            _pd_state["finished"] = __import__("time").strftime("%Y-%m-%d %H:%M:%S")
            _pd_state["elapsed"] = round(__import__("time").time() - start, 1)
            _pd_state["error"] = str(e)


def _pd_worker_oracle(db_id):
    import time as _time
    start = _time.time()
    try:
        proc_sql = "BEGIN INSP_PARTITION_DROP_TARGET(p_db_id => %d); END;" % db_id
        err = run_db_exec(proc_sql)
        elapsed = round(_time.time() - start, 1)
        with _pd_lock:
            _pd_state["running"] = False
            _pd_state["finished"] = _time.strftime("%Y-%m-%d %H:%M:%S")
            _pd_state["elapsed"] = elapsed
            _pd_state["error"] = err
    except Exception as e:
        with _pd_lock:
            _pd_state["running"] = False
            _pd_state["finished"] = __import__("time").strftime("%Y-%m-%d %H:%M:%S")
            _pd_state["error"] = str(e)


def api_drop_partitions(db_id_str):
    import time as _time
    try:
        db_id = int(db_id_str)
    except (ValueError, TypeError):
        return json.dumps({"ok": False, "error": "Invalid db_id"})
    with _pd_lock:
        if _pd_state["running"]:
            return json.dumps({"ok": False, "error": "Already running since " + (_pd_state["started"] or "")})
        _pd_state["running"] = True
        _pd_state["started"] = _time.strftime("%Y-%m-%d %H:%M:%S")
        _pd_state["finished"] = None
        _pd_state["elapsed"] = None
        _pd_state["dropped"] = 0
        _pd_state["total"] = 0
        _pd_state["error"] = None
    pg = "postgresql" in _db_cfg().get("db_type", "").lower()
    worker = _pd_worker_pg if pg else _pd_worker_oracle
    t = threading.Thread(target=worker, args=(db_id,), daemon=True)
    t.start()
    return json.dumps({"ok": True, "message": "Drop started"})


def api_drop_partitions_status():
    with _pd_lock:
        return json.dumps({
            "running": _pd_state["running"],
            "started": _pd_state["started"],
            "finished": _pd_state["finished"],
            "elapsed": _pd_state["elapsed"],
            "dropped": _pd_state["dropped"],
            "total": _pd_state["total"],
            "error": _pd_state["error"],
        })
