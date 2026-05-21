# -*- coding: utf-8 -*-
"""Alarm Send History - shows SMS/API/Mail alert send status."""
import os
import re
import json
import time as _time

from service_config import load_service_config
from db_utils import run_db_query, _parse_db_table
from html_helpers import (
    _page_title_html, _page, _badge, _warn_box, _ts,
    _HELP, _UTILS_BASE,
)


# ── Log parsing ──────────────────────────────────────────────────────────

def _find_alert_logs(sel_date=None):
    """Collect current + rolled (zipped) send logs.

    Log rotation produces files like `sms_YYYYMMDD_N.log.zip`. When a
    `sel_date` (YYYY-MM-DD) is provided we include only zip archives whose
    date tag matches — the current `.log` is always appended too (covers
    today's live data and is skipped by date filtering inside the parser
    when the user picks an older day)."""
    svc = load_service_config()
    services = svc.get("services", {})
    result = {"sms": [], "api": [], "mail": []}
    active = {"sms": False, "api": False, "mail": False}

    dgs_homes = []
    for i, dgs in enumerate(services.get("dgserver_s", [])):
        if dgs:
            dgs_homes.append(dgs)

    date_tag = sel_date.replace('-', '') if sel_date else None

    for home in dgs_homes:
        svc_dir = os.path.join(home, "svc")
        log_dir = os.path.join(home, "log")
        for kind in ("sms", "api", "mail"):
            jar = os.path.join(svc_dir, kind + ".jar") if os.path.isdir(svc_dir) else ""
            if jar and os.path.exists(jar):
                active[kind] = True
            for d in (svc_dir, log_dir):
                if not os.path.isdir(d):
                    continue
                live = os.path.join(d, kind + ".log")
                if os.path.exists(live) and live not in result[kind]:
                    result[kind].append(live)
                # Rolled archives: <kind>_YYYYMMDD_<seq>.log.zip
                try:
                    zip_re = re.compile(r'^' + re.escape(kind) + r'_(\d{8})_\d+\.log\.zip$')
                    for name in os.listdir(d):
                        m = zip_re.match(name)
                        if not m:
                            continue
                        if date_tag and m.group(1) != date_tag:
                            continue
                        p = os.path.join(d, name)
                        if p not in result[kind]:
                            result[kind].append(p)
                except OSError:
                    pass

    return result, active


def _parse_send_logs(log_paths):
    """Parse sms.log/api.log and build status dict.
    Returns: {epoch_ms_str: {'status': 'success'|'failed', 'error': str}}
    """
    status_map = {}
    # SMS pattern: #N @1 :[..., ..., ..., N, EPOCH, ...]
    epoch_re = re.compile(r'@1\s*:\[.*?,\s*.*?,\s*.*?,\s*\d+,\s*(\d{13}),')
    thread_re = re.compile(r'#(\d+)\s+@1')
    # API pattern: #N [ALARM PARAM] alarm param [...time=EPOCH...]
    epoch_re_api = re.compile(r'\[ALARM PARAM\].*time=(\d{13})')
    thread_re_api = re.compile(r'#(\d+)\s+\[ALARM PARAM\]')
    finish_re = re.compile(r'#(\d+)\s+Finish')
    failed_re = re.compile(r'#(\d+)\s+.*(?:Failed|Exception|\bError\b)')
    error_level_re = re.compile(r'\[ERROR\s*\]\s*#(\d+)\b')
    error_msg_re = re.compile(r'(java\.\S+Exception:\s*.+|ORA-\d+.+|연결이 거부됨.*|The Network Adapter.+|Listener refused.+)')

    def _read_log_sources(p):
        """Yield (source_name, content_str) for a given path. Supports plain
        text log files and rolled `*.log.zip` archives — the archive is read
        into memory without extracting to disk."""
        if p.lower().endswith('.zip'):
            try:
                import zipfile
                with zipfile.ZipFile(p, 'r') as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        with zf.open(info) as ef:
                            raw = ef.read()
                        yield info.filename, raw.decode('utf-8', errors='replace')
            except Exception:
                return
        else:
            try:
                with open(p, 'r', encoding='utf-8', errors='replace') as f:
                    yield p, f.read()
            except Exception:
                return

    for log_path in log_paths:
      for src_name, content in _read_log_sources(log_path):
        try:
            thread_epoch = {}
            thread_error = {}

            for line in content.split('\n'):
                # Map thread -> epoch (SMS pattern)
                tm = thread_re.search(line)
                em = epoch_re.search(line)
                if tm and em:
                    tid = tm.group(1)
                    ems = em.group(1)
                    thread_epoch[tid] = ems
                    thread_error[tid] = ''
                # Map thread -> epoch (API pattern)
                if not (tm and em):
                    tm2 = thread_re_api.search(line)
                    em2 = epoch_re_api.search(line)
                    if tm2 and em2:
                        tid = tm2.group(1)
                        ems = em2.group(1)
                        thread_epoch[tid] = ems
                        thread_error[tid] = ''

                # Capture error message
                err = error_msg_re.search(line)
                if err:
                    # Find which thread this belongs to
                    tmatch = re.search(r'#(\d+)\s', line)
                    if tmatch and tmatch.group(1) in thread_epoch:
                        thread_error[tmatch.group(1)] = err.group(1).strip()[:200]

                # [ERROR] level for the thread → mark failed (sticky)
                elm = error_level_re.search(line)
                if elm:
                    tid = elm.group(1)
                    if tid in thread_epoch:
                        ems = thread_epoch[tid]
                        err_msg = thread_error.get(tid, '') or line.strip()[:200]
                        status_map[ems] = {'status': 'failed', 'error': err_msg}

                # Retry success → clear prior [ERROR] for this thread
                if 'Connection success' in line:
                    tmatch = re.search(r'#(\d+)\s', line)
                    if tmatch and tmatch.group(1) in thread_epoch:
                        ems = thread_epoch[tmatch.group(1)]
                        status_map[ems] = {'status': 'success', 'error': ''}

                # Check finish (success) — but never override a prior failure
                fm = finish_re.search(line)
                if fm:
                    tid = fm.group(1)
                    if tid in thread_epoch:
                        ems = thread_epoch[tid]
                        existing = status_map.get(ems, {})
                        if existing.get('status') != 'failed':
                            status_map[ems] = {'status': 'success', 'error': ''}

                # Check failed (textual Failed/Exception/Error keywords)
                flm = failed_re.search(line)
                if flm:
                    tid = flm.group(1)
                    if tid in thread_epoch:
                        ems = thread_epoch[tid]
                        err_msg = thread_error.get(tid, 'Connection failed')
                        status_map[ems] = {'status': 'failed', 'error': err_msg}

            # Second pass: capture error messages that come AFTER the Failed line
            lines = content.split('\n')
            for i, line in enumerate(lines):
                flm = failed_re.search(line)
                if flm:
                    tid = flm.group(1)
                    if tid in thread_epoch:
                        ems = thread_epoch[tid]
                        # Look ahead for Caused by or exception details
                        err_detail = ''
                        for j in range(i, min(i + 15, len(lines))):
                            em2 = error_msg_re.search(lines[j])
                            if em2:
                                err_detail = em2.group(1).strip()[:200]
                                break
                            if 'Caused by:' in lines[j]:
                                err_detail = lines[j].strip()[:200]
                                break
                        if err_detail and ems in status_map:
                            status_map[ems]['error'] = err_detail

        except Exception:
            pass

    return status_map


def _get_latest_log_status(send_logs_status):
    """Check if the most recent log entries show failure."""
    if not send_logs_status:
        return None, ''
    # Get the latest epoch entry
    latest_epoch = max(send_logs_status.keys())
    info = send_logs_status[latest_epoch]
    return info.get('status', ''), info.get('error', '')


def _get_alarm_send_status(epoch_ms_str, send_logs_status, jar_active, latest_status=None, latest_error=''):
    # Log evidence takes priority over current jar state. Even if sms.jar
    # has been renamed/removed (.bak), the historical logs (including
    # rolled zips) still exist and should be trusted for past alarms.
    info = send_logs_status.get(epoch_ms_str, {})
    status = info.get('status', '')
    error = info.get('error', '')
    if status == 'success':
        return 'success', ''
    if status == 'failed':
        return 'failed', error or latest_error
    return 'skipped', ''


# ── SQL ──────────────────────────────────────────────────────────────────

_SQL_PG_ALARM_SEND = """
CREATE OR REPLACE FUNCTION insp_alarm_send_check()
RETURNS TABLE(
    instance_name VARCHAR(64),
    alert_time TIMESTAMP,
    alert_epoch BIGINT,
    alert_type_name VARCHAR(32),
    alert_name VARCHAR(128),
    alert_value VARCHAR(64)
) AS $$
DECLARE sql_text TEXT;
BEGIN
  SELECT string_agg(
    format(
      $f$SELECT a.instance_name::varchar(64),
              b.time AS alert_time,
              (EXTRACT(EPOCH FROM b.time AT TIME ZONE 'Asia/Seoul') * 1000)::bigint AS alert_epoch,
              CASE WHEN b.type=1 THEN 'Server Alert'
                   WHEN b.type=2 THEN 'Stat Alert'
                   ELSE 'Type '||b.type END::varchar(32) AS alert_type_name,
              b.name::varchar(128) AS alert_name,
              b.value::varchar(64) AS alert_value
       FROM apm_db_info a
       JOIN %I.ora_alarm_history b ON a.db_id = b.db_id
       WHERE b.sms_flag = '1'
         AND b.time >= '{sel_date}'::date AND b.time < '{sel_date}'::date + INTERVAL '1 day'$f$,
      lower(adi.instance_name)
    ), ' UNION ALL '
  ) INTO sql_text FROM apm_db_info adi;
  IF sql_text IS NULL THEN RETURN; END IF;
  RETURN QUERY EXECUTE sql_text || ' ORDER BY alert_time DESC LIMIT 500';
END;
$$ LANGUAGE plpgsql;
SELECT * FROM insp_alarm_send_check();
"""

_SQL_ORACLE_ALARM_SEND = """
SET LINESIZE 1000
SET PAGESIZE 500
SET FEEDBACK OFF
COLUMN INSTANCE_NAME FORMAT A25
COLUMN ALERT_TYPE FORMAT A15
COLUMN NAME FORMAT A30
SELECT a.instance_name,
       TO_CHAR(h.time, 'YYYY-MM-DD HH24:MI:SS') AS alert_time,
       /* h.time is stored in server local time (DATE has no TZ);
          convert to UTC epoch-ms by subtracting session TZ offset so it
          aligns with System.currentTimeMillis() in the SMS/API/Mail jar. */
       ((h.time - TO_DATE('1970-01-01','YYYY-MM-DD')) * 86400
        - (EXTRACT(TIMEZONE_HOUR FROM SYSTIMESTAMP) * 3600
           + EXTRACT(TIMEZONE_MINUTE FROM SYSTIMESTAMP) * 60)
       ) * 1000 AS alert_epoch,
       DECODE(h.type, 1, 'Server Alert', 2, 'Stat Alert', 'Type '||h.type) AS alert_type,
       h.name,
       TO_CHAR(h.value) AS value
FROM apm_db_info a
JOIN ora_alarm_history h ON a.db_id = h.db_id
WHERE h.sms_flag = '1'
  AND h.time >= TO_DATE('{sel_date}','YYYY-MM-DD') AND h.time < TO_DATE('{sel_date}','YYYY-MM-DD') + 1
ORDER BY h.time DESC
FETCH FIRST 500 ROWS ONLY
"""


# ── Page ─────────────────────────────────────────────────────────────────

def _status_badge(status, error='', idx=0):
    if status == 'success':
        return ('<span style="color:#10b981;border:1px solid #10b981;padding:3px 10px;'
                'border-radius:6px;font-size:0.72rem;font-weight:700;text-transform:uppercase;'
                'background:rgba(16,185,129,0.1);">Success</span>')
    elif status == 'failed':
        esc_err = (error or 'Unknown error').replace("'", "\\'").replace('"', '&quot;').replace('<', '&lt;')
        return ('<span onclick="_showErr(this)" data-err="' + esc_err + '" '
                'style="color:#EF4444;border:1px solid #EF4444;padding:3px 10px;'
                'border-radius:6px;font-size:0.72rem;font-weight:700;text-transform:uppercase;'
                'background:rgba(239,68,68,0.1);cursor:pointer;" '
                'title="Click for details">Failed</span>')
    else:
        return ('<span style="color:#94A3B8;border:1px solid #CBD5E1;padding:3px 10px;'
                'border-radius:6px;font-size:0.72rem;font-weight:600;text-transform:uppercase;'
                '">Skipped</span>')


def page_alarm_history(path=''):
    # Parse date from query string (default: today)
    import time as _t
    sel_date = _t.strftime('%Y-%m-%d')
    if '?' in path:
        for part in path.split('?', 1)[1].split('&'):
            if part.startswith('date=') and len(part) > 5:
                sel_date = part[5:].strip()[:10]

    repo = load_service_config().get("repository", {})
    db_type = repo.get("db_type", "Oracle").lower()
    pg = "postgres" in db_type

    sql = (_SQL_PG_ALARM_SEND if pg else _SQL_ORACLE_ALARM_SEND).replace('{sel_date}', sel_date)
    out, err = run_db_query(sql)

    _ctrl_css = (
        '<style>'
        '.sb-group{display:flex;align-items:center;background:#fff;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;height:36px;transition:border-color .15s;}'
        '.sb-group:focus-within{border-color:#6366F1;box-shadow:0 0 0 2px rgba(99,102,241,.08);}'
        '.sb-group label{font-size:.72rem;font-weight:600;color:#94A3B8;padding:0 10px;white-space:nowrap;border-right:1px solid #F1F5F9;background:#FAFBFC;height:100%;display:flex;align-items:center;letter-spacing:.03em;}'
        '.sb-group input{border:none;outline:none;padding:0 12px;font-size:.84rem;color:#0F172A;height:100%;background:transparent;min-width:0;font-variant-numeric:tabular-nums;font-family:Segoe UI,sans-serif;font-weight:600;letter-spacing:.01em;cursor:pointer;}'
        '.sb-group input[type=date]{width:140px;text-align:center;}'
        '.sb-group input[type=date]::-webkit-calendar-picker-indicator{display:none;-webkit-appearance:none;}'
        '.sb-group input[type=date]::-webkit-inner-spin-button{display:none;}'
        '.sb-group input[type=date]::-webkit-clear-button{display:none;}'
        '.sb-group .sb-cal-btn{display:flex;align-items:center;justify-content:center;width:34px;height:100%;border:none;border-left:1px solid #F1F5F9;background:#FAFBFC;color:#94A3B8;cursor:pointer;transition:all .15s;flex-shrink:0;}'
        '.sb-group .sb-cal-btn:hover{background:#EEF2FF;color:#6366F1;}'
        '.sb-group .sb-cal-btn svg{width:15px;height:15px;}'
        '.sb-arrow{display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border:1px solid #E2E8F0;background:#fff;border-radius:8px;color:#475569;cursor:pointer;transition:all .15s;font-size:1.2rem;font-weight:600;padding:0;line-height:1;}'
        '.sb-arrow:hover{background:#EEF2FF;color:#6366F1;border-color:#C7D2FE;}'
        '</style>'
        '<script>'
        'function _shiftAlarmDate(dir){'
        '  var el=document.getElementById("alarm-date");if(!el)return;'
        '  var d=new Date(el.value+"T00:00:00");'
        '  d.setDate(d.getDate()+dir);'
        '  var p=function(n){return n<10?"0"+n:""+n;};'
        '  el.value=d.getFullYear()+"-"+p(d.getMonth()+1)+"-"+p(d.getDate());'
        '  el.dispatchEvent(new Event("change"));'
        '}'
        '</script>'
    )

    if err:
        body = ''.join([
            _ctrl_css,
            _page_title_html('Alarm Send History', *_HELP.get('alarm_history', ('Alarm Send History', ''))),
            '<div class="insp-card"><div class="insp-card-body" style="padding:14px 16px;">',
            _warn_box(err),
            '</div></div>',
            _ts(),
        ])
        return _page('alarm_history', 'Alarm Send History', body)

    headers, rows = _parse_db_table(out or "")

    log_paths, jar_active = _find_alert_logs(sel_date=sel_date)
    any_jar_active = jar_active.get("sms") or jar_active.get("api") or jar_active.get("mail")

    # Parse each send type separately to track which type fired per alarm
    _kind_status = {
        kind: (_parse_send_logs(log_paths.get(kind, [])) if log_paths.get(kind) else {})
        for kind in ('sms', 'api', 'mail')
    }
    # Merged map for overall status (failure in any type wins)
    send_status = {}
    for d in _kind_status.values():
        for k, v in d.items():
            if k not in send_status or v.get('status') == 'failed':
                send_status[k] = v

    h = [x.upper().strip() for x in headers] if headers else []
    idx_inst = next((i for i, x in enumerate(h) if 'INSTANCE' in x), -1)
    idx_time = next((i for i, x in enumerate(h) if 'ALERT_TIME' in x or x == 'ALERT_TIME'), -1)
    idx_epoch = next((i for i, x in enumerate(h) if 'EPOCH' in x), -1)
    idx_type = next((i for i, x in enumerate(h) if 'TYPE' in x and 'ALERT' in x), -1)
    idx_name = next((i for i, x in enumerate(h) if x == 'ALERT_NAME' or x == 'NAME'), -1)
    idx_val = next((i for i, x in enumerate(h) if 'VALUE' in x or x == 'VALUE'), -1)

    # Info bar
    info_parts = []
    for kind in ('sms', 'api', 'mail'):
        active = jar_active.get(kind, False)
        color = '#10b981' if active else '#94A3B8'
        label = kind.upper()
        st = 'Active' if active else 'Inactive'
        info_parts.append(
            '<span style="font-size:.75rem;color:%s;font-weight:600;'
            'border:1px solid %s;padding:2px 8px;border-radius:6px;'
            'margin-right:8px;">%s: %s</span>' % (color, color, label, st)
        )

    _KIND_COLOR = {'sms': '#6366F1', 'api': '#F97316', 'mail': '#3B82F6'}

    stat_html = ''

    _refresh_btn = (
        '<style>@keyframes alarm-spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}</style>'
        '<button id="alarm-refresh-btn" onclick="_alarmRefresh()" style="margin-left:auto;padding:4px 10px;border-radius:6px;'
        'border:1px solid #CBD5E1;background:transparent;color:#64748B;font-size:.78rem;cursor:pointer;'
        'transition:all .15s;display:inline-flex;align-items:center;gap:5px;" '
        'onmouseover="this.style.background=\'#F1F5F9\'" onmouseout="this.style.background=\'transparent\'">'
        '<span id="alarm-refresh-icon" style="display:inline-block;font-size:.92rem;line-height:1;">&#8635;</span> Refresh</button>'
    )
    info_bar = (
        '<div style="margin-bottom:16px;display:flex;align-items:center;gap:4px;flex-wrap:wrap;">'
        ''
        + ''.join(info_parts) + stat_html
        + _refresh_btn
        + '</div>'
    )

    if not rows:
        table_html = (
            '<div style="text-align:center;padding:40px;color:#94A3B8;font-size:.85rem;">'
            'No alarm send records found (sms_flag=1) for ' + sel_date + '.</div>'
        )
    else:
        _hs = ('text-align:center;padding:10px 8px;font-size:.72rem;font-weight:700;'
               'text-transform:uppercase;letter-spacing:.03em;color:#5F6B80;'
               'border-bottom:1px solid #D8DEE8;cursor:pointer;user-select:none;')

        t = ['<div style="max-height:calc(100vh - 280px);overflow-y:auto;">']
        t.append('<table class="svc-table" style="width:100%;border-collapse:collapse;table-layout:fixed;">')
        t.append('<thead style="position:sticky;top:0;z-index:3;background:#F8FAFC;"><tr>')
        t.append('<th class="sortable" onclick="tbSort(this)" style="width:14%%;%s">Instance<span class="sort-ic"></span></th>' % _hs)
        t.append('<th class="sortable" onclick="tbSort(this)" style="width:16%%;%s">Time<span class="sort-ic"></span></th>' % _hs)
        t.append('<th class="sortable" onclick="tbSort(this)" style="width:13%%;%s">Alert Type<span class="sort-ic"></span></th>' % _hs)
        t.append('<th class="sortable" onclick="tbSort(this)" style="width:20%%;%s">Name<span class="sort-ic"></span></th>' % _hs)
        t.append('<th class="sortable" onclick="tbSort(this)" style="width:12%%;%s">Value<span class="sort-ic"></span></th>' % _hs)
        t.append('<th class="sortable" onclick="tbSort(this)" style="width:12%%;%s">Send Type<span class="sort-ic"></span></th>' % _hs)
        t.append('<th class="sortable" onclick="tbSort(this)" style="width:10%%;%s">Status<span class="sort-ic"></span></th>' % _hs)
        t.append('</tr></thead><tbody>')

        _KIND_RGB = {'sms': '99,102,241', 'api': '249,115,22', 'mail': '59,130,246'}

        for row in rows:
            inst  = row[idx_inst].strip()  if 0 <= idx_inst  < len(row) else '-'
            atime = row[idx_time].strip()  if 0 <= idx_time  < len(row) else '-'
            atype = row[idx_type].strip()  if 0 <= idx_type  < len(row) else '-'
            name  = row[idx_name].strip()  if 0 <= idx_name  < len(row) else '-'
            val   = row[idx_val].strip()   if 0 <= idx_val   < len(row) else '-'
            epoch = row[idx_epoch].strip() if 0 <= idx_epoch < len(row) else ''
            epoch_key = epoch.split('.')[0] if epoch else ''

            # Expand: one sub-row per send type that has a log entry for this epoch
            send_types = [k for k in ('sms', 'api', 'mail') if epoch_key in _kind_status[k]]
            if not send_types:
                # No log entry at all — single Skipped row
                send_types_iter = [None]
            else:
                send_types_iter = send_types

            # Alternate background for grouping multi-type rows belonging to same alarm
            group_bg = 'background:#FAFBFE;' if len(send_types) > 1 else ''

            for k in send_types_iter:
                if k is None:
                    type_cell = '<span style="color:#CBD5E1;font-size:.78rem;">—</span>'
                    status_html = _status_badge('skipped')
                else:
                    c = _KIND_COLOR[k]; rgb = _KIND_RGB[k]
                    type_cell = (
                        '<span style="color:%s;border:1px solid %s;padding:2px 8px;'
                        'border-radius:5px;font-size:.7rem;font-weight:700;'
                        'background:rgba(%s,.1);display:inline-block;">%s</span>'
                        % (c, c, rgb, k.upper())
                    )
                    k_info  = _kind_status[k].get(epoch_key, {})
                    k_st    = k_info.get('status', 'skipped')
                    k_err   = k_info.get('error', '')
                    status_html = _status_badge(k_st, k_err)

                rs = 'border-bottom:1px solid #F1F5F9;' + group_bg
                t.append('<tr style="%s">' % rs)
                t.append('<td style="padding:10px 8px;text-align:center;font-weight:500;color:#1E293B;font-size:.82rem;">%s</td>' % inst)
                t.append('<td style="padding:10px 8px;text-align:center;font-size:.82rem;color:#4B5563;">%s</td>' % atime)
                t.append('<td style="padding:10px 8px;text-align:center;font-size:.82rem;color:#334155;">%s</td>' % atype)
                t.append('<td style="padding:10px 8px;text-align:center;font-size:.82rem;color:#334155;">%s</td>' % name)
                t.append('<td style="padding:10px 8px;text-align:center;font-size:.82rem;color:#4B5563;">%s</td>' % val)
                t.append('<td style="padding:10px 8px;text-align:center;">%s</td>' % type_cell)
                t.append('<td style="padding:10px 8px;text-align:center;">%s</td>' % status_html)
                t.append('</tr>')

        t.append('</tbody></table></div>')
        table_html = ''.join(t)

    # Error detail popup + filter JS
    extra_js = """<script>
function _showErr(el){
  var err=el.getAttribute("data-err");
  if(!err)return;
  var popup=document.getElementById("err-popup");
  var body=document.getElementById("err-popup-body");
  body.textContent=err;
  popup.style.display="flex";
}
function _closeErr(){document.getElementById("err-popup").style.display="none";}
function filterAlarm(){
  var v=document.getElementById("alarm-filter").value.toUpperCase().trim();
  var rows=document.querySelectorAll(".svc-table tbody tr");
  rows.forEach(function(r){
    r.style.display=(!v||r.textContent.toUpperCase().indexOf(v)>-1)?"":"none";
  });
}
function _alarmRefresh(){
  var btn=document.getElementById("alarm-refresh-btn");
  var ico=document.getElementById("alarm-refresh-icon");
  if(ico)ico.style.animation="alarm-spin .6s linear infinite";
  if(btn)btn.disabled=true;
  location.reload();
}
</script>"""

    error_popup = (
        '<div id="err-popup" onmousedown="_ovMd(event)" onclick="_ovClick(event,_closeErr)" '
        'style="display:none;position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.4);'
        'align-items:center;justify-content:center;">'
        '<div style="background:#fff;border-radius:12px;padding:0;max-width:min(1200px,95vw);width:95%;'
        'box-shadow:0 20px 60px rgba(0,0,0,.2);">'
        '<div style="display:flex;justify-content:space-between;align-items:center;'
        'padding:14px 20px;border-bottom:1px solid #E2E8F0;">'
        '<span style="font-size:.82rem;font-weight:700;color:#EF4444;">'
        '&#9888; Send Failed - Error Detail</span>'
        '<span onclick="_closeErr()" style="cursor:pointer;color:#94A3B8;font-size:1.1rem;'
        'padding:2px 6px;" onmouseover="this.style.color=\'#334155\'" '
        'onmouseout="this.style.color=\'#94A3B8\'">&times;</span>'
        '</div>'
        '<div id="err-popup-body" style="padding:18px 20px;font-size:.82rem;color:#334155;'
        'line-height:1.55;white-space:pre;overflow-x:auto;max-height:60vh;overflow-y:auto;'
        'font-family:JetBrains Mono,Consolas,monospace;background:#FAFAFA;'
        'border-radius:0 0 12px 12px;"></div>'
        '</div></div>'
    )

    _ub = _UTILS_BASE
    # 카드 헤더 안 — outer margin-bottom 제거 (헤더 padding으로 충분)
    search_bar = (
        '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;width:100%;">'
        '<button type="button" class="sb-arrow" onclick="_shiftAlarmDate(-1)">&#8249;</button>'
        '<div class="sb-group">'
        '<label>Date</label>'
        '<input type="date" id="alarm-date" value="' + sel_date + '" '
        'onchange="location.href=\'' + _ub + '/history/alarm?date=\'+this.value">'
        '<button type="button" class="sb-cal-btn" onclick="document.getElementById(\'alarm-date\').showPicker()">'
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">'
        '<rect x="2" y="3" width="12" height="11" rx="2"/><path d="M2 7h12M5 1v3M11 1v3"/></svg>'
        '</button></div>'
        '<button type="button" class="sb-arrow" onclick="_shiftAlarmDate(1)">&#8250;</button>'
        '<input type="text" id="alarm-filter" oninput="filterAlarm()" '
        'placeholder="Filter..." '
        'style="flex:1;padding:7px 12px;border-radius:8px;border:1px solid #E2E8F0;'
        'background:#fff;font-size:.82rem;color:#0F172A;outline:none;height:36px;box-sizing:border-box;">'
        '</div>'
    )

    body = ''.join([
        _ctrl_css,
        _page_title_html('Alarm Send History', *_HELP.get('alarm_history', ('Alarm Send History', ''))),
        info_bar,
        '<div class="insp-card">',
        '<div class="insp-card-hdr">', search_bar, '</div>',
        '<div class="insp-card-body">', table_html, '</div>',
        '</div>',
        error_popup,
        extra_js,
        _ts(),
    ])
    return _page('alarm_history', 'Alarm Send History', body)
