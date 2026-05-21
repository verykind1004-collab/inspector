# -*- coding: utf-8 -*-
import os
import re
import json
from datetime import datetime, date

from service_config import load_service_config
from db_utils import _db_cfg, run_db_query, _parse_db_table, _sql_embed
from system_utils import _xml_val
from html_helpers import (
    _badge, _warn_box, _page_title_html, _page,
    _HELP, _HELP_JS, _ts, _UTILS_BASE,
)




_LICENSE_INFO_SQL_PG = """\
SELECT a.license_id,
       a.license_name,
       to_char(a.last_modified, 'YYYY-MM-DD HH24:MI:SS') AS last_modified
  FROM apm_license a
 ORDER BY a.license_id;"""

_LICENSE_INFO_SQL_ORACLE = """\
SELECT a.license_id,
       a.license_name,
       TO_CHAR(a.last_modified, 'YYYY-MM-DD HH24:MI:SS') AS last_modified
  FROM apm_license a
 ORDER BY a.license_id;"""

_INSTANCE_LICENSE_SQL_PG = """\
SELECT d.db_id,
       d.instance_name,
       d.host_ip,
       d.port,
       COALESCE(l.valid,                                                    'N/A') AS valid,
       COALESCE(l.license_type,                                             '-')   AS license_type,
       COALESCE(l.license_status,                                           '-')   AS license_status,
       COALESCE(l.core::text,                                               '-')   AS core,
       COALESCE(to_char(l.last_modified, 'YYYY-MM-DD HH24:MI:SS'),          '-')   AS last_check
  FROM apm_db_info d
  LEFT JOIN apm_license_db_info l ON d.db_id = l.db_id
 ORDER BY d.db_id;"""

_INSTANCE_LICENSE_SQL_ORACLE = """\
SELECT d.db_id,
       d.instance_name,
       d.host_ip,
       d.port,
       NVL(l.valid,                                                    'N/A') AS valid,
       NVL(l.license_type,                                             '-')   AS license_type,
       NVL(l.license_status,                                           '-')   AS license_status,
       NVL(TO_CHAR(l.core),                                            '-')   AS core,
       NVL(TO_CHAR(l.last_modified, 'YYYY-MM-DD HH24:MI:SS'),          '-')   AS last_check
  FROM apm_db_info d
  LEFT JOIN apm_license_db_info l ON d.db_id = l.db_id
 ORDER BY d.db_id;"""


def _license_info_sql():
    pg = "postgres" in _db_cfg().get("db_type", "Oracle").lower()
    return _LICENSE_INFO_SQL_PG if pg else _LICENSE_INFO_SQL_ORACLE


def _instance_license_sql():
    pg = "postgres" in _db_cfg().get("db_type", "Oracle").lower()
    return _INSTANCE_LICENSE_SQL_PG if pg else _INSTANCE_LICENSE_SQL_ORACLE


def _get_license_info():
    """Get license file info from apm_license. Returns list of dicts."""
    try:
        sql = _license_info_sql()
        out, err = run_db_query(sql)
        if err:
            return None, err
        headers, rows = _parse_db_table(out or "")
        if not rows:
            return None, "No license registered"
        result = []
        for row in rows:
            lic_id = row[0].strip() if len(row) > 0 else ""
            name = row[1].strip() if len(row) > 1 else ""
            modified = row[2].strip() if len(row) > 2 else ""
            expiry = None
            product = None
            parts = name.split(".")
            for p in parts:
                if len(p) == 8 and p.isdigit():
                    try:
                        expiry = datetime.strptime(p, "%Y%m%d").date()
                    except ValueError:
                        pass
                if p.upper() in ("MFO", "MXG", "MAXGAUGE"):
                    product = p.upper()
            # Type is determined by filename: date in name → TRIAL, otherwise → TERM
            lic_type = "TRIAL" if expiry else "TERM"
            is_perpetual = (lic_type == "TERM")
            d_day = None if is_perpetual else (expiry - date.today()).days
            result.append({
                "id": lic_id,
                "name": name,
                "modified": modified,
                "expiry": expiry.strftime("%Y-%m-%d") if expiry else None,
                "product": product,
                "d_day": d_day,
                "is_perpetual": is_perpetual,
                "license_type": lic_type,
            })
        return result, None
    except Exception as e:
        return None, str(e)


def _get_instance_license_status():
    """Get per-instance license status."""
    try:
        sql = _instance_license_sql()
        out, err = run_db_query(sql)
        if err:
            return None, err
        headers, rows = _parse_db_table(out or "")
        return (headers, rows), None
    except Exception as e:
        return None, str(e)


def _get_license_events():
    """Parse DGM logs for today's LICENSE events (excluding [LICENSE MANAGER])."""
    import glob, subprocess, zipfile
    try:
        svc = load_service_config()
        dgm_home = svc.get("services", {}).get("dgserver_m", "")
        if not dgm_home:
            return [], "DGServer_M이 설정되지 않았습니다."
        log_dir = os.path.join(dgm_home, "log")
        if not os.path.isdir(log_dir):
            return [], "로그 디렉토리를 찾을 수 없습니다."

        today_str = datetime.now().strftime('%Y%m%d')
        today_date = datetime.now().strftime('%Y-%m-%d')

        events = []

        # 1. Current DGM_*.log files (not zip)
        logs = sorted(glob.glob(os.path.join(log_dir, "DGM_*.log")),
                       key=os.path.getmtime, reverse=True)
        for logfile in logs:
            fname = os.path.basename(logfile)
            # Skip zip files
            if fname.endswith('.zip'):
                continue
            # Determine date
            dm = re.search(r'(\d{8})', fname)
            if dm:
                log_date = dm.group(1)
                # Skip if not today
                if log_date != today_str:
                    continue
                log_date_fmt = log_date[:4] + '-' + log_date[4:6] + '-' + log_date[6:]
            else:
                # DGM_port.log = today's active log
                log_date_fmt = today_date
            try:
                proc = subprocess.Popen(
                    ['grep', '-i', 'LICENSE', logfile],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, _ = proc.communicate(timeout=10)
                for line in out.decode('utf-8', errors='replace').splitlines():
                    if '[LICENSE MANAGER]' in line:
                        continue
                    if 'SEND ALARM HISTORY to WEBSOCKET' in line:
                        continue
                    if 'LICENSE ALERT DAO' in line:
                        continue
                    if 'SEND LAST ALARM' in line:
                        continue
                    if 'LICENSE DB INFO DAO' in line:
                        continue
                    events.append(_parse_license_line(line, log_date_fmt))
            except Exception:
                continue

        # 2. Today's zip files: DGM_*_yyyymmdd_*.log.zip
        zips = glob.glob(os.path.join(log_dir, "DGM_*_" + today_str + "_*.log.zip"))
        for zpath in sorted(zips):
            try:
                # Read zip without extracting - use zipgrep or read via ZipFile
                with zipfile.ZipFile(zpath, 'r') as zf:
                    for inner_name in zf.namelist():
                        data = zf.read(inner_name).decode('utf-8', errors='replace')
                        for line in data.splitlines():
                            if 'LICENSE' not in line.upper():
                                continue
                            if '[LICENSE MANAGER]' in line:
                                continue
                            if 'SEND ALARM HISTORY to WEBSOCKET' in line:
                                continue
                            if 'LICENSE ALERT DAO' in line:
                                continue
                            if 'SEND LAST ALARM' in line:
                                continue
                            if 'LICENSE DB INFO DAO' in line:
                                continue
                            events.append(_parse_license_line(line, today_date))
            except Exception:
                continue

        # Filter out None entries and sort
        events = [e for e in events if e is not None]
        events.sort(key=lambda e: e['ts'], reverse=True)
        return events, None
    except Exception as e:
        return [], str(e)


def _parse_license_line(line, log_date):
    """Parse a single license log line into event dict."""
    # Extract time
    tm = re.search(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\]', line)
    time_str = tm.group(1)[:8] if tm else ''
    if not time_str:
        return None

    ts = log_date + ' ' + time_str

    # Try to extract server_id
    sid_m = re.search(r'server_id=(\d+)', line)
    server_id = sid_m.group(1) if sid_m else ''

    # Try to extract valid= info
    valid_m = re.search(r'valid=(\d+|\w+)', line)
    valid_str = valid_m.group(1) if valid_m else ''

    # Determine result
    result = ''
    if valid_str:
        if valid_str in ('1', 'true', 'VALID'):
            result = 'VALID'
        elif valid_str in ('0', 'false', 'INVALID'):
            result = 'INVALID'
        else:
            result = valid_str.upper()

    # Extract event type from brackets
    evt_m = re.search(r'\[([^\]]*LICENSE[^\]]*)\]', line, re.IGNORECASE)
    event_type = evt_m.group(1).strip() if evt_m else 'LICENSE'

    # Detail: everything after the last ] or the desc= part
    desc_m = re.search(r'desc=([^\]]*)', line)
    detail = desc_m.group(1).strip() if desc_m else ''
    if not detail:
        # Use the tail of the line as detail
        last_bracket = line.rfind(']')
        if last_bracket >= 0 and last_bracket < len(line) - 1:
            detail = line[last_bracket+1:].strip()

    return {
        'ts': ts,
        'instance': server_id if server_id else '-',
        'event': event_type,
        'result': result,
        'desc': detail,
    }



def page_license_check():
    # 2. License Info
    lic_info, lic_err = _get_license_info()

    # 3. Instance License Status
    inst_data, inst_err = _get_instance_license_status()

    # 4. Recent License Events
    events, events_err = _get_license_events()

    # ── Build HTML ──

    def _color_cell(val, green_vals, red_vals):
        v = str(val).strip().upper()
        for g in green_vals:
            if v == g.upper():
                return _badge('ok', str(val))
        for r in red_vals:
            if v == r.upper():
                return _badge('critical', str(val))
        return str(val)

    # License Info section
    lic_html = ''
    if lic_info and isinstance(lic_info, list):
        _ths = 'text-align:center;padding:10px 8px;font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.03em;color:var(--c-muted);border-bottom:2px solid var(--bd);'
        _tds = 'text-align:center;padding:10px 8px;border-bottom:1px solid var(--bd);font-size:.84rem;'
        lic_rows = ''
        for li in lic_info:
            fname = li.get('name', '-')
            exp   = li.get('expiry', '-')
            dday  = li.get('d_day', '-')
            ltype = li.get('license_type', '-')
            # Type: TRIAL=red, TERM=green
            type_cell = _color_cell(ltype, ['TERM'], ['TRIAL'])
            lic_rows += (
                '<tr>'
                '<td style="' + _tds + '">' + str(fname) + '</td>'
                '<td style="' + _tds + '">' + type_cell + '</td>'
                '<td style="' + _tds + '">' + str(exp) + '</td>'
                '<td style="' + _tds + '">' + (_badge('critical', str(dday)) if isinstance(dday, (int,float)) and dday <= 10 else ('<span class="badge" style="background:rgba(59,130,246,.1);color:#3b82f6;border:1px solid rgba(59,130,246,.25);padding:2px 10px;border-radius:9999px;font-size:0.75rem;font-weight:600;display:inline-block;line-height:1.2;text-align:center;min-width:32px;">' + str(dday) + '</span>') if isinstance(dday, (int,float)) else str(dday)) + '</td>'
                '</tr>'
            )
        lic_html = ''.join([
            '<div class="insp-card">',
            '<div class="insp-card-hdr"><div class="insp-card-title">License Info</div></div>',
            '<div class="insp-card-body">',
            '<table class="svc-table" style="width:100%;">',
            '<thead><tr>',
            '<th style="' + _ths + '">File</th>',
            '<th style="' + _ths + '">Type</th>',
            '<th style="' + _ths + '">Expire</th>',
            '<th style="' + _ths + '">D-Day</th>',
            '</tr></thead>',
            '<tbody>' + lic_rows + '</tbody>',
            '</table></div></div>',
        ])
    elif lic_err:
        lic_html = ('<div class="insp-card">'
                    '<div class="insp-card-hdr"><div class="insp-card-title">License Info</div></div>'
                    '<div class="insp-card-body" style="padding:14px 16px;">' + _warn_box(lic_err) + '</div>'
                    '</div>')

    # Instance License Status section
    inst_html = ''
    if inst_data and isinstance(inst_data, tuple) and len(inst_data) == 2:
        headers, rows = inst_data
        if headers and rows:
            _iths = 'text-align:center;padding:10px 8px;font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.03em;color:var(--c-muted);border-bottom:2px solid var(--bd);'
            _itds = 'text-align:center;padding:10px 8px;border-bottom:1px solid var(--bd);font-size:.84rem;'
            h_upper = [h.upper() for h in headers]
            idx_valid = next((i for i, h in enumerate(h_upper) if h == 'VALID'), -1)
            idx_type  = next((i for i, h in enumerate(h_upper) if h == 'LICENSE_TYPE'), -1)
            idx_lstatus = next((i for i, h in enumerate(h_upper) if h == 'LICENSE_STATUS'), -1)

            thead = '<tr>' + ''.join('<th style="' + _iths + '">' + h.replace('_', ' ') + '</th>' for h in headers) + '</tr>'
            tbody = ''
            for row in rows:
                cells = ''
                for i, val in enumerate(row):
                    v = str(val).strip()
                    if i == idx_valid:
                        # VALID=green, else=red
                        cell_html = _color_cell(v, ['VALID'], ['NONE', 'INVALID', 'EXPIRED'])
                    elif i == idx_type:
                        # TRIAL=red, TERM=green
                        cell_html = _color_cell(v, ['TERM'], ['TRIAL'])
                    elif i == idx_lstatus:
                        # valid=green, disconnected=red
                        cell_html = _color_cell(v, ['valid', 'VALID'], ['disconnected', 'DISCONNECTED'])
                    else:
                        cell_html = v
                    cells += '<td style="' + _itds + '">' + cell_html + '</td>'
                tbody += '<tr>' + cells + '</tr>'

            inst_html = ''.join([
                '<div class="insp-card">',
                '<div class="insp-card-hdr"><div class="insp-card-title">Instance License Status</div></div>',
                '<div class="insp-card-body">',
                '<table class="svc-table" style="width:100%;">',
                '<thead>' + thead + '</thead>',
                '<tbody>' + tbody + '</tbody>',
                '</table></div></div>',
            ])
    if inst_err and not inst_html:
        inst_html = ('<div class="insp-card">'
                     '<div class="insp-card-hdr"><div class="insp-card-title">Instance License Status</div></div>'
                     '<div class="insp-card-body" style="padding:14px 16px;">' + _warn_box(inst_err) + '</div>'
                     '</div>')

    # Recent License Events section
    events_html = ''
    if events:
        _eths = 'text-align:center;padding:8px 10px;font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.03em;color:var(--c-muted);border-bottom:2px solid var(--bd);'
        _etds = 'padding:8px 10px;border-bottom:1px solid var(--bd);font-size:.84rem;'
        evt_rows = ''
        for ev in events:
            r = ev.get('result', '').upper()
            if r == 'VALID':
                res_cell = _badge('ok', 'VALID')
            elif r in ('INVALID', ''):
                res_cell = _badge('critical', r) if r else ''
            else:
                res_cell = _badge('critical', r)
            evt_name = ev.get('event', '')
            if evt_name == 'Key Reloaded':
                evt_cell = '<span style="color:#6366F1;font-weight:600;font-size:.82rem;">' + evt_name + '</span>'
            else:
                evt_cell = evt_name
            evt_rows += (
                '<tr>'
                '<td style="' + _etds + 'text-align:center;font-variant-numeric:tabular-nums;white-space:nowrap;">' + ev.get('ts', '') + '</td>'
                '<td style="' + _etds + 'text-align:center;font-weight:600;">' + ev.get('instance', '-') + '</td>'
                '<td style="' + _etds + 'text-align:center;">' + evt_cell + '</td>'
                '<td style="' + _etds + 'text-align:center;">' + res_cell + '</td>'
                '<td style="' + _etds + '">' + (ev.get('desc', '') or '-') + '</td>'
                '</tr>'
            )
        events_html = ''.join([
            '<div class="insp-card">',
            '<div class="insp-card-hdr"><div class="insp-card-title">Recent License Events</div></div>',
            '<div class="insp-card-body" style="max-height:400px;overflow-y:auto;">',
            '<table class="svc-table" style="width:100%;border-collapse:collapse;">',
            '<thead style="position:sticky;top:0;background:var(--bg-card);"><tr>',
            '<th style="' + _eths + '">Time</th>',
            '<th style="' + _eths + '">Instance</th>',
            '<th style="' + _eths + '">Event</th>',
            '<th style="' + _eths + '">Result</th>',
            '<th style="' + _eths + '">Detail</th>',
            '</tr></thead>',
            '<tbody>' + evt_rows + '</tbody>',
            '</table></div></div>',
        ])
    elif events_err:
        events_html = ('<div class="insp-card">'
                       '<div class="insp-card-hdr"><div class="insp-card-title">Recent License Events</div></div>'
                       '<div class="insp-card-body" style="padding:14px 16px;">' + _warn_box(events_err) + '</div>'
                       '</div>')
    else:
        events_html = (u'<div class="insp-card">'
                       u'<div class="insp-card-hdr"><div class="insp-card-title">Recent License Events</div></div>'
                       u'<div class="insp-card-body" style="color:var(--c-muted);font-size:.85rem;padding:20px 0;text-align:center;">'
                       u'DGServer_M \ub85c\uadf8\uc5d0\uc11c \ub77c\uc774\uc120\uc2a4 \uc774\ubca4\ud2b8\ub97c \ucc3e\uc744 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.'
                       u'</div></div>')

    body = ''.join([
        _page_title_html('License Check', *_HELP.get('license_check', ('License Check', ''))),
        lic_html,
        inst_html,
        events_html,
        _ts(),
        # 두 SQL 을 QUERY 칩 헤더 + 본문 블록 두 개로 노출 (function 정의 표시와 동일 스타일).
        _sql_embed('', sections=[
            {'title': 'License Info',             'body': _license_info_sql()},
            {'title': 'Instance License Status',  'body': _instance_license_sql()},
        ]),
    ])
    return _page('license_check', 'License Check', body)
