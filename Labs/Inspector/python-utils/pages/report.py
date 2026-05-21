# -*- coding: utf-8 -*-
import socket
from datetime import datetime

from service_config import load_service_config
from db_utils import _db_cfg, run_db_query, _parse_db_table
from sql_library import _get_sql
from system_utils import (
    _cpu_percent, _memory, _disk_for_overview, _tablespace_for_overview,
    _dg_info, _get_pid_by_port, _repodb_info,
)
from pages.license_check import _get_license_info
from html_helpers import _UTILS_BASE, _PLATFORMJS_PORT


def _yesterday_os_avg():
    """Query INSP_OS_HISTORY for yesterday's average CPU/Memory."""
    from datetime import timedelta
    try:
        cfg = _db_cfg()
        is_pg = "postgres" in cfg.get("db_type", "Oracle").lower()
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')

        if is_pg:
            from insp_pg import _insp_pg_connect
            conn = _insp_pg_connect()
            if not conn:
                return None
            cur = conn.cursor()
            cur.execute(
                "SELECT ROUND(AVG(cpu_percent)::numeric,1), "
                "       ROUND(AVG(cpu_user)::numeric,1), "
                "       ROUND(AVG(cpu_system)::numeric,1), "
                "       ROUND(AVG(cpu_iowait)::numeric,1), "
                "       ROUND(AVG(mem_total_gb)::numeric,1), "
                "       ROUND(AVG(mem_used_gb)::numeric,1), "
                "       ROUND(AVG(mem_free_gb)::numeric,1), "
                "       ROUND(AVG(mem_percent)::numeric,1), "
                "       COUNT(*) "
                "FROM insp_os_history "
                "WHERE collected_at >= %s AND collected_at < %s",
                (yesterday, today)
            )
        else:
            from insp_oracle import _insp_connect
            conn = _insp_connect()
            if not conn:
                return None
            cur = conn.cursor()
            cur.execute(
                "SELECT ROUND(AVG(CPU_PERCENT),1), "
                "       ROUND(AVG(CPU_USER),1), "
                "       ROUND(AVG(CPU_SYSTEM),1), "
                "       ROUND(AVG(CPU_IOWAIT),1), "
                "       ROUND(AVG(MEM_TOTAL_GB),1), "
                "       ROUND(AVG(MEM_USED_GB),1), "
                "       ROUND(AVG(MEM_FREE_GB),1), "
                "       ROUND(AVG(MEM_PERCENT),1), "
                "       COUNT(*) "
                "FROM INSP_OS_HISTORY "
                "WHERE COLLECTED_AT >= TO_TIMESTAMP(:1, 'YYYY-MM-DD') "
                "  AND COLLECTED_AT < TO_TIMESTAMP(:2, 'YYYY-MM-DD')",
                (yesterday, today)
            )

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row or not row[8] or int(row[8]) == 0:
            return None

        return {
            "cpu": {
                "percent": float(row[0] or 0),
                "user": float(row[1] or 0),
                "system": float(row[2] or 0),
                "iowait": float(row[3] or 0),
            },
            "mem": {
                "total_gb": float(row[4] or 0),
                "used_gb": float(row[5] or 0),
                "free_gb": float(row[6] or 0),
                "percent": float(row[7] or 0),
            },
            "count": int(row[8]),
            "date": yesterday,
        }
    except Exception:
        return None


def _monthly_resource_data(year):
    """Query insp_monthly_summary for the given year.
    Returns {month_int: {cpu_avg, mem_avg, mem_used_gb, mem_total_gb,
                         disk_avg, disk_used_gb, disk_total_gb}}
    Falls back to empty dict on any error.
    """
    try:
        cfg = _db_cfg()
        is_pg = "postgres" in cfg.get("db_type", "Oracle").lower()
        if is_pg:
            from insp_pg import insp_pg_query_monthly_summary
            return insp_pg_query_monthly_summary(year)
        else:
            from insp_oracle import insp_query_monthly_summary
            return insp_query_monthly_summary(year)
    except Exception:
        return {}


def _rb(status, text=None):
    t = text or status.upper()
    return '<span style="background:#fff;color:#000;border:1px solid #000;padding:2px 8px;border-radius:4px;font-size:.72rem;font-weight:700;">%s</span>' % t


def _parse_status_rows(out):
    if not out:
        return [], [], [], [], -1
    headers, rows = _parse_db_table(out)
    if not headers:
        return [], [], [], [], -1
    idx_st = -1
    for i, h in enumerate(headers):
        if 'STATUS' in h.upper():
            idx_st = i; break
    ok_rows, warn_rows, check_rows = [], [], []
    for row in rows:
        if idx_st < 0 or idx_st >= len(row):
            check_rows.append(row); continue
        s = row[idx_st].strip().upper()
        if s == 'OK': ok_rows.append(row)
        elif s == 'WAITING': warn_rows.append(row)
        else: check_rows.append(row)
    return headers, ok_rows, warn_rows, check_rows, idx_st


def _build_check_table(svc_rows, pc_out, pc_err, pd_out, pd_err, s10_out, s10_err, s1h_out, s1h_err, pc_sql, pd_sql, s10_sql, s1h_sql):
    _th = 'padding:4px 8px;font-size:.65rem;font-weight:700;text-transform:uppercase;color:#000;border:1px solid #000;text-align:center;background:#f0f0f0;'
    _td = 'padding:3px 8px;border:1px solid #000;font-size:.78rem;text-align:center;'

    _cnt = [0]

    def _radio_row(title, default_ok=True):
        n = _cnt[0]; _cnt[0] += 1
        ok_id = "ok_%d" % n
        chk_id = "chk_%d" % n
        ok_attr = " checked" if default_ok else ""
        chk_attr = "" if default_ok else " checked"
        return (
            '<tr>'
            '<td style="' + _td + 'font-weight:600;">' + title + '</td>'
            '<td style="' + _td + '"><label style="cursor:pointer;display:flex;align-items:center;justify-content:center;gap:4px;">'
            '<input type="checkbox" id="' + ok_id + '"' + ok_attr + ' onclick="_rptToggle(this)" data-pair="' + chk_id + '" style="width:14px;height:14px;accent-color:#000;"> OK</label></td>'
            '<td style="' + _td + '"><label style="cursor:pointer;display:flex;align-items:center;justify-content:center;gap:4px;">'
            '<input type="checkbox" id="' + chk_id + '"' + chk_attr + ' onclick="_rptToggle(this)" data-pair="' + ok_id + '" style="width:14px;height:14px;accent-color:#000;"> CHECK</label></td>'
            '</tr>'
        )

    def _auto_row(title, out, err, sql_ok):
        if not sql_ok:
            return _radio_row(title, default_ok=True)
        if err:
            return _radio_row(title, default_ok=False)
        _, ok, warn, check, _ = _parse_status_rows(out)
        return _radio_row(title, default_ok=True)

    def _svc_radio(name):
        ok = True
        for comp, st, _, _, _ in svc_rows:
            if name == 'DataGather' and ('DGServer' in comp or 'DG' in comp):
                if st != 'running': ok = False
            elif name == 'PlatformJS' and comp == 'PlatformJS':
                if st != 'running': ok = False
            elif name == 'Repository DB' and 'Repository' in comp:
                if st != 'running': ok = False
        return _radio_row(name, default_ok=True)

    return ''.join([
        '<table style="width:100%;border-collapse:collapse;">',
        '<thead><tr>',
        '<th style="' + _th + '">' + '점검지표' + '</th>',
        '<th style="' + _th + 'width:25%;">OK</th>',
        '<th style="' + _th + 'width:25%;">CHECK</th>',
        '</tr></thead><tbody>',
        _radio_row('RTS', default_ok=True),
        _radio_row('SNDF', default_ok=True),
        _radio_row('OBSD', default_ok=True),
        _svc_radio('DataGather'),
        _svc_radio('PlatformJS'),
        _svc_radio('Repository DB'),
        _auto_row('Partition Create / Drop', pc_out or pd_out, pc_err or pd_err, bool(pc_sql) or bool(pd_sql)),
        _auto_row('10Min / 1Hour Summary', s10_out or s1h_out, s10_err or s1h_err, bool(s10_sql) or bool(s1h_sql)),
        _radio_row('License', default_ok=True),
        '</tbody></table>',
    ])


def page_report():
    now = datetime.now()
    year = now.year
    cur_month = now.month

    svc_cfg = load_service_config()
    repo = svc_cfg.get("repository", {})
    is_pg = "postgres" in repo.get("db_type", "Oracle").lower()

    # Current resource stats
    hist = _yesterday_os_avg()
    if hist:
        cpu = hist["cpu"]
        mem = hist["mem"]
    else:
        cpu = _cpu_percent()
        mem = _memory()

    if is_pg:
        _dsk = _disk_for_overview()
        disk_used = _dsk.get("used_gb", 0)
        disk_total = _dsk.get("total_gb", 0)
        disk_pct = _dsk.get("percent", 0)
        disk_label = "Disk"
    else:
        _tbs = _tablespace_for_overview()
        if isinstance(_tbs, list) and _tbs:
            worst = max(_tbs, key=lambda t: t.get("percent", 0))
            disk_used = worst.get("used_gb", 0)
            disk_total = worst.get("total_gb", 0)
            disk_pct = worst.get("percent", 0)
        else:
            disk_used = disk_total = disk_pct = 0
        disk_label = "TBS"

    # Instances — apm_db_info 에 등록된 인스턴스 수
    inst_count = "-"
    try:
        _ic_out, _ic_err = run_db_query("SELECT COUNT(*) FROM apm_db_info")
        if not _ic_err and _ic_out:
            _hdr, _rows = _parse_db_table(_ic_out)
            if _rows and _rows[0]:
                inst_count = str(int(_rows[0][0]))
    except Exception:
        pass

    # Services (for Check Status)
    svcs = svc_cfg.get("services", {})
    svc_rows = []
    dgm_home = svcs.get("dgserver_m", "")
    if dgm_home:
        info = _dg_info(dgm_home)
        st = info.get("status", "stopped") if info.get("exists") else "stopped"
        svc_rows.append(("DGServer_M", st, info.get("port", "-"), "", ""))
    for i, dgs_home in enumerate(svcs.get("dgserver_s", [])):
        if not dgs_home:
            continue
        info = _dg_info(dgs_home)
        st = info.get("status", "stopped") if info.get("exists") else "stopped"
        svc_rows.append(("DGServer_S%d" % (i + 1), st, info.get("port", "-"), "", ""))
    pjs_pid = _get_pid_by_port(_PLATFORMJS_PORT)
    svc_rows.append(("PlatformJS", "running" if pjs_pid else "stopped", str(_PLATFORMJS_PORT), "", ""))
    rdb = _repodb_info()
    svc_rows.append(("Repository DB", rdb["status"], rdb["port"], "", ""))

    pc_sql = _get_sql("partition_create")
    pc_out, pc_err = run_db_query(pc_sql) if pc_sql else ("", None)
    pd_sql = _get_sql("partition_drop")
    pd_out, pd_err = run_db_query(pd_sql) if pd_sql else ("", None)
    s10_sql = _get_sql("summary_10min")
    s10_out, s10_err = run_db_query(s10_sql) if s10_sql else ("", None)
    s1h_sql = _get_sql("summary_1hour")
    s1h_out, s1h_err = run_db_query(s1h_sql) if s1h_sql else ("", None)

    # Monthly resource data — fill current month with live data if not yet summarised
    monthly = _monthly_resource_data(year)
    if cur_month not in monthly:
        monthly[cur_month] = {
            'cpu_avg': cpu["percent"],
            'mem_avg': mem["percent"],
            'mem_used_gb': mem["used_gb"],
            'mem_total_gb': mem["total_gb"],
            'disk_avg': disk_pct,
            'disk_used_gb': disk_used,
            'disk_total_gb': disk_total,
        }

    MONTHS = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월',
              '9월', '10월', '11월', '12월']

    def _res_cell(m_idx, key, fmt):
        m = m_idx + 1
        if m in monthly:
            val = monthly[m].get(key)
            if val is not None:
                return '<td class="editable" contenteditable="true">' + (fmt % float(val)) + '</td>'
        return '<td class="editable" contenteditable="true"></td>'

    cpu_cells  = ''.join(_res_cell(i, 'cpu_avg',  '%.1f%%') for i in range(12))
    mem_cells  = ''.join(_res_cell(i, 'mem_avg',  '%.0f%%') for i in range(12))
    disk_cells = ''.join(_res_cell(i, 'disk_avg', '%.0f%%') for i in range(12))

    month_headers = ''.join('<th>' + m + '</th>' for m in MONTHS)

    # Check Status — 그룹(항목) + 세부(점검상세) 구조
    STATUS_GROUPS = [
        ('프로세스 점검',          ['Agent 동작점검', 'DG 동작점검', 'PJS 동작점검']),
        ('수집상태 점검',          ['os stat 수집점검', 'db stat 수집점검',
                                    'session stat 수집점검', 'sql stat 수집점검']),
        ('Real-Time Monitor',     ['CPU/Memory', 'Trend Chart', 'SQL Elapsed Time',
                                    'Active Sessions', 'Script Manager']),
        ('Performance Analyzer',  ['Top-N Analysis', 'Performance Trend', 'Long-Term Trend',
                                    'Session/SQL List', 'Capacity Planning']),
    ]
    SVG_CHECK = '<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>'

    _status_rows_list = []
    _row_idx = 0
    for _group_name, _items in STATUS_GROUPS:
        for _i, _item in enumerate(_items):
            ok_id  = 'cb-ok-%d'  % _row_idx
            chk_id = 'cb-chk-%d' % _row_idx
            _tr = '<tr>'
            if _i == 0:
                _tr += ('<td class="group-cell" rowspan="' + str(len(_items)) + '">'
                        + _group_name + '</td>')
            _tr += '<td class="name-cell">' + _item + '</td>'
            _tr += ('<td><div class="cb-wrap" onclick="_rtog(' + str(_row_idx) + ',\'ok\')">'
                    '<div class="cb checked" id="' + ok_id + '">' + SVG_CHECK + '</div>OK</div></td>')
            _tr += ('<td><div class="cb-wrap" onclick="_rtog(' + str(_row_idx) + ',\'chk\')">'
                    '<div class="cb" id="' + chk_id + '">' + SVG_CHECK + '</div>CHECK</div></td>')
            _tr += '</tr>'
            _status_rows_list.append(_tr)
            _row_idx += 1
    status_rows = ''.join(_status_rows_list)

    # Stat card values (these strings use % formatting — %% becomes %)
    cpu_stat  = '<div class="stat-card"><div class="stat-lbl">CPU</div><div class="stat-val">%.1f%%</div></div>' % cpu["percent"]
    mem_stat  = ('<div class="stat-card"><div class="stat-lbl">Memory</div>'
                 '<div class="stat-val">%.0f / %.0f G (%.0f%%)</div></div>'
                 % (mem["used_gb"], mem["total_gb"], mem["percent"]))
    disk_stat = ('<div class="stat-card"><div class="stat-lbl">' + disk_label + '</div>'
                 '<div class="stat-val">%.0f / %.0f G (%.0f%%)</div></div>'
                 % (disk_used, disk_total, disk_pct))
    inst_stat = ('<div class="stat-card"><div class="stat-lbl">Instances</div>'
                 '<div class="stat-val">' + inst_count + '</div></div>')

    html = (
        '<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
        '<title>MaxGauge Report</title>'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900'
        '&family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">'
        '<style>'
        '*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}'
        ':root{--bd:#999;--bd-lt:#ccc;--txt:#000;--muted:#444;--bg-hd:#e8e8e8;}'
        'body{font-family:"Noto Sans KR","Inter",sans-serif;background:#fff;color:var(--txt);'
        'font-size:12px;padding:14px 22px;max-width:820px;margin:0 auto;'
        '-webkit-print-color-adjust:exact;print-color-adjust:exact;}'
        '.no-print{display:flex;gap:8px;margin-bottom:14px;}'
        '@media print{.no-print{display:none!important;}}'
        '.rpt-btn{padding:6px 18px;border-radius:6px;border:none;font-size:.82rem;font-weight:600;cursor:pointer;}'
        '.rpt-hd{margin-bottom:8px;}'
        '.rpt-title{font-size:22px;font-weight:900;color:var(--txt);margin-bottom:6px;letter-spacing:-.02em;}'
        '.co-info{font-size:10px;color:var(--muted);line-height:1.7;}'
        '.cust-row{display:grid;grid-template-columns:1fr 1fr;border:1px solid var(--bd);margin-bottom:8px;}'
        '.cust-cell{padding:5px 12px;border-right:1px solid var(--bd);}'
        '.cust-cell:last-child{border-right:none;}'
        '.cust-lbl{font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:5px;}'
        '.cust-val{font-size:13px;font-weight:600;color:var(--txt);min-height:22px;outline:none;'
        'border-bottom:1.5px solid var(--bd-lt);padding-bottom:2px;}'
        '.cust-val:focus{border-bottom-color:#000;}'
        '.stat-row{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--bd);margin-bottom:10px;}'
        '.stat-card{padding:5px 10px;text-align:center;border-right:1px solid var(--bd);}'
        '.stat-card:last-child{border-right:none;}'
        '.stat-lbl{font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:3px;}'
        '.stat-val{font-size:14px;font-weight:700;color:var(--txt);}'
        '.sec-title{font-size:12px;font-weight:700;color:var(--txt);margin-bottom:5px;padding-bottom:3px;border-bottom:1.5px solid var(--txt);}'
        '.res-sec{margin-bottom:10px;}'
        'table.res-tbl{width:100%;border-collapse:collapse;font-size:10px;}'
        '.res-tbl th,.res-tbl td{border:1px solid var(--bd);padding:5px 4px;text-align:center;line-height:1.4;}'
        '.res-tbl thead tr{background:var(--bg-hd);-webkit-print-color-adjust:exact;print-color-adjust:exact;}'
        '.res-tbl th{font-weight:700;font-size:10px;color:var(--txt);}'
        '.res-tbl td:first-child{font-weight:600;color:var(--txt);background:var(--bg-hd)!important;width:52px;-webkit-print-color-adjust:exact;print-color-adjust:exact;}'
        '.res-tbl td.editable{cursor:text;min-width:44px;}'
        '.res-tbl td.editable:focus{outline:2px solid #333;outline-offset:-2px;background:#ececec;}'
        '.st-sec{margin-bottom:10px;page-break-inside:avoid;}'
        'table.st-tbl{width:100%;border-collapse:collapse;font-size:10.5px;}'
        '.st-tbl th,.st-tbl td{border:1px solid var(--bd);padding:3px 6px;text-align:center;}'
        '.st-tbl thead tr{background:var(--bg-hd);-webkit-print-color-adjust:exact;print-color-adjust:exact;}'
        '.st-tbl th{font-weight:700;font-size:10px;}'
        '.st-tbl .group-cell{font-weight:600;background:#f1f1f1;font-size:11px;'
        '-webkit-print-color-adjust:exact;print-color-adjust:exact;}'
        '.name-cell{text-align:center;}'
        '.cb-wrap{display:inline-flex;align-items:center;gap:4px;cursor:pointer;user-select:none;font-size:10px;font-weight:500;}'
        '.cb{width:12px;height:12px;border:1.5px solid #888;border-radius:2px;display:grid;place-items:center;'
        'flex-shrink:0;background:#fff;transition:background .1s,border-color .1s;}'
        '.cb.checked{background:#1a1a1a!important;border-color:#1a1a1a;-webkit-print-color-adjust:exact;print-color-adjust:exact;}'
        '.cb svg{width:7px;height:7px;stroke:#fff;fill:none;stroke-width:2.5;stroke-linecap:round;}'
        '.note-sec{margin-bottom:10px;}'
        '.note-box{width:100%;min-height:70px;border:1px solid var(--bd);padding:8px 10px;'
        'font-size:11px;font-family:inherit;color:var(--muted);resize:vertical;outline:none;}'
        '.note-box:focus{border-color:#333;}'
        'table.ft-tbl{width:100%;border-collapse:collapse;font-size:11px;}'
        '.ft-tbl th,.ft-tbl td{border:1px solid var(--bd);padding:7px 10px;text-align:center;}'
        '.ft-tbl th{background:var(--bg-hd)!important;font-weight:700;width:25%;-webkit-print-color-adjust:exact;print-color-adjust:exact;}'
        '.ft-tbl td{height:38px;vertical-align:top;}'
        '.ft-tbl td.date-cell{font-weight:700;font-size:13px;padding-top:12px;}'
        '@media print{'
        'body{padding:0;color:#000;}'
        '.cb-wrap{cursor:default;}'
        'th,td{border-color:#000!important;color:#000!important;}'
        '.stat-lbl{color:#000!important;}'
        '.co-info{color:#000!important;}'
        '.cust-lbl{color:#000!important;}'
        '.sec-title{border-bottom-color:#000!important;color:#000!important;}'
        '@page{size:A4;margin:10mm 14mm;}'
        '}'
        '</style></head><body>'

        '<div class="no-print">'
        '<button class="rpt-btn" style="background:#000;color:#fff;" onclick="window.print()">Print / PDF</button>'
        '<button class="rpt-btn" style="background:#f1f5f9;color:#333;border:1px solid #999;" onclick="window.close()">Close</button>'
        '</div>'

        '<div class="rpt-hd">'
        '<div class="rpt-title">MaxGauge Report</div>'
        '<div class="co-info">(주)엑셈<br>'
        '서울시 강서구 마곡중앙8로5길 40 (마곡동 785-1) (07792)<br>'
        'T 82-2-6203-6300 &nbsp; F 82-2-6203-6301<br>'
        'www.ex-em.com</div>'
        '</div>'

        '<div class="cust-row">'
        '<div class="cust-cell">'
        '<div class="cust-lbl">고객사명</div>'
        '<div class="cust-val" contenteditable="true"></div>'
        '</div>'
        '<div class="cust-cell">'
        '<div class="cust-lbl">지원제품</div>'
        '<div class="cust-val" contenteditable="true"></div>'
        '</div>'
        '</div>'

        '<div class="stat-row">'
        + cpu_stat + mem_stat + disk_stat + inst_stat +
        '</div>'

        '<div class="res-sec">'
        '<div class="sec-title">Check Resource</div>'
        '<table class="res-tbl"><thead><tr><th></th>'
        + month_headers +
        '</tr></thead><tbody>'
        '<tr><td>CPU</td>' + cpu_cells + '</tr>'
        '<tr><td>Memory</td>' + mem_cells + '</tr>'
        '<tr><td>' + disk_label + '</td>' + disk_cells + '</tr>'
        '</tbody></table>'
        '</div>'

        '<div class="st-sec">'
        '<div class="sec-title">Check Status</div>'
        '<table class="st-tbl"><thead><tr>'
        '<th style="width:22%;">항목</th>'
        '<th style="width:38%;">점검상세</th>'
        '<th style="width:20%;">OK</th>'
        '<th style="width:20%;">CHECK</th>'
        '</tr></thead><tbody>'
        + status_rows +
        '</tbody></table>'
        '</div>'

        '<div class="note-sec">'
        '<div class="sec-title">특이사항</div>'
        '<textarea class="note-box" placeholder="점검 결과, MaxGauge 운영 중 특이사항은 확인되지 않았습니다."></textarea>'
        '</div>'

        '<table class="ft-tbl"><thead><tr>'
        '<th>점검일</th><th>지원 엔지니어</th><th>고객확인</th><th>서명</th>'
        '</tr></thead><tbody><tr>'
        '<td class="date-cell">' + now.strftime("%Y-%m-%d") + '</td>'
        '<td></td><td></td><td></td>'
        '</tr></tbody></table>'

        '<script>'
        'function _rtog(idx,side){'
        'var ok=document.getElementById("cb-ok-"+idx);'
        'var chk=document.getElementById("cb-chk-"+idx);'
        'if(!ok||!chk)return;'
        'if(side==="ok"){ok.classList.add("checked");chk.classList.remove("checked");}'
        'else{chk.classList.add("checked");ok.classList.remove("checked");}'
        '}'
        '</script>'
        '</body></html>'
    )
    return html
