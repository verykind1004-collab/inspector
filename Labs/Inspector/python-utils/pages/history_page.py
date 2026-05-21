# -*- coding: utf-8 -*-
import json
from datetime import datetime, timedelta
from urllib.parse import unquote

from db_utils import _db_cfg, _HAS_ORACLEDB, _HAS_PSYCOPG2, _oracledb, _psycopg2
from history import _hist_connect, _load_insp_config
from insp_pg import _insp_pg_connect
from pages.history_views import _view_css, _cpu_chart_css
from html_helpers import _CSS, _HELP_JS, _ts, _UTILS_BASE, _page_title_html, _HELP, _tools_fab_block


def _is_oracle_repo():
    cfg = _db_cfg()
    return 'oracle' in cfg.get('db_type', 'Oracle').lower()


def _oracle_connect():
    cfg = _db_cfg()
    return _oracledb.connect(
        user=cfg.get('user', ''), password=cfg.get('password', ''),
        host=cfg.get('ip', ''), port=int(cfg.get('port', '1521') or '1521'),
        service_name=cfg.get('sid', ''))


def api_history_instances():
    """Return instance list from apm_db_info (repo DB) with history DB fallback."""
    try:
        cfg = _db_cfg()
        db_type = cfg.get('db_type', 'Oracle').lower()
        instances = []
        if 'postgres' in db_type:
            if _HAS_PSYCOPG2:
                conn = _psycopg2.connect(
                    host=cfg.get('ip', ''), port=int(cfg.get('port', '5432') or '5432'),
                    user=cfg.get('user', ''), password=cfg.get('password', ''),
                    dbname=cfg.get('sid', ''))
                cur = conn.cursor()
                cur.execute('SELECT instance_name FROM apm_db_info ORDER BY instance_name')
                instances = [r[0] for r in cur.fetchall() if r[0]]
                cur.close(); conn.close()
        else:
            if _HAS_ORACLEDB:
                conn = _oracledb.connect(
                    user=cfg.get('user', ''), password=cfg.get('password', ''),
                    host=cfg.get('ip', ''), port=int(cfg.get('port', '1521') or '1521'),
                    service_name=cfg.get('sid', ''))
                cur = conn.cursor()
                cur.execute('SELECT instance_name FROM apm_db_info ORDER BY instance_name')
                instances = [r[0] for r in cur.fetchall() if r[0]]
                cur.close(); conn.close()
        return json.dumps({'ok': True, 'instances': instances, 'source': 'repodb'})
    except Exception as e:
        return json.dumps({'ok': False, 'instances': [], 'error': str(e)})


def api_history_data(path):
    qs = path.split('?', 1)[1] if '?' in path else ''
    params = {}
    for p in qs.split('&'):
        if '=' in p:
            k, v = p.split('=', 1)
            params[k] = v
    check_type = params.get('type', '10min')
    if check_type not in ('10min', '1hour'):
        check_type = '10min'
    sel_date = params.get('date', '')
    try:
        if sel_date:
            datetime.strptime(sel_date, '%Y-%m-%d')
        else:
            sel_date = datetime.now().strftime('%Y-%m-%d')
    except Exception:
        sel_date = datetime.now().strftime('%Y-%m-%d')
    since = sel_date + ' 00:00:00'
    until = sel_date + ' 23:59:59'
    try:
        if _is_oracle_repo():
            return _api_history_data_oracle(check_type, since, until, sel_date)
        else:
            return _api_history_data_pg(check_type, since, until, sel_date)
    except Exception as e:
        msg = str(e)
        if 'does not exist' in msg or 'not exist' in msg or 'ORA-00942' in msg or '릴레이션' in msg:
            return json.dumps({'ok': False, 'error': 'TABLE_NOT_EXIST',
                'detail': 'INSP_SUMMARY_HISTORY 테이블이 생성되지 않았습니다.'})
        return json.dumps({'ok': False, 'error': msg})


def _api_history_data_oracle(check_type, since, until, sel_date):
    valid_instances = _get_valid_instances()
    conn = _oracle_connect()
    cur = conn.cursor()
    if valid_instances:
        bind = {('b%d' % i): v for i, v in enumerate(valid_instances)}
        in_clause = ','.join(':' + k for k in bind.keys())
        bind['ct'] = check_type
        bind['s'] = since
        bind['u'] = until
        cur.execute(
            "SELECT DISTINCT INSTANCE_NAME, SUMMARY_TYPE "
            "FROM INSP_SUMMARY_HISTORY "
            "WHERE CHECK_TYPE=:ct "
            "AND COLLECTED_AT>=TO_TIMESTAMP(:s,'YYYY-MM-DD HH24:MI:SS') "
            "AND COLLECTED_AT<=TO_TIMESTAMP(:u,'YYYY-MM-DD HH24:MI:SS') "
            "AND SUMMARY_TYPE IS NOT NULL "
            "AND INSTANCE_NAME IN (" + in_clause + ") "
            "ORDER BY INSTANCE_NAME, SUMMARY_TYPE",
            bind)
    else:
        cur.execute(
            "SELECT DISTINCT INSTANCE_NAME, SUMMARY_TYPE "
            "FROM INSP_SUMMARY_HISTORY "
            "WHERE CHECK_TYPE=:1 "
            "AND COLLECTED_AT>=TO_TIMESTAMP(:2,'YYYY-MM-DD HH24:MI:SS') "
            "AND COLLECTED_AT<=TO_TIMESTAMP(:3,'YYYY-MM-DD HH24:MI:SS') "
            "AND SUMMARY_TYPE IS NOT NULL "
            "ORDER BY INSTANCE_NAME, SUMMARY_TYPE",
            (check_type, since, until))
    groups = [{'inst': r[0], 'stype': r[1].strip()} for r in cur.fetchall()]
    seen = set(); stypes = []
    for g in groups:
        if g['stype'] not in seen:
            seen.add(g['stype']); stypes.append(g['stype'])
    result = {}
    for g in groups:
        key = g['inst'] + '|||' + g['stype']
        cur.execute(
            "SELECT TO_CHAR(COLLECTED_AT,'YYYY-MM-DD HH24:MI:SS'), STATUS "
            "FROM INSP_SUMMARY_HISTORY "
            "WHERE CHECK_TYPE=:1 AND INSTANCE_NAME=:2 AND NVL(SUMMARY_TYPE,' ')=:3 "
            "AND COLLECTED_AT>=TO_TIMESTAMP(:4,'YYYY-MM-DD HH24:MI:SS') "
            "AND COLLECTED_AT<=TO_TIMESTAMP(:5,'YYYY-MM-DD HH24:MI:SS') "
            "ORDER BY COLLECTED_AT",
            (check_type, g['inst'], g['stype'] or ' ', since, until))
        result[key] = [{'t': r[0], 's': r[1]} for r in cur.fetchall()]
    cur.close(); conn.close()
    instances = sorted(set(g['inst'] for g in groups))
    return json.dumps({'ok': True, 'instances': instances, 'stypes': stypes,
                       'groups': groups, 'data': result, 'date': sel_date, 'type': check_type})


def _get_valid_instances():
    """Get instance list from apm_db_info in Repository DB."""
    try:
        cfg = _db_cfg()
        db_type = cfg.get('db_type', 'Oracle').lower()
        if 'postgres' in db_type:
            if not _HAS_PSYCOPG2:
                return []
            conn = _psycopg2.connect(
                host=cfg.get('ip', ''), port=int(cfg.get('port', '5432') or '5432'),
                user=cfg.get('user', ''), password=cfg.get('password', ''),
                dbname=cfg.get('sid', ''))
        else:
            if not _HAS_ORACLEDB:
                return []
            conn = _oracledb.connect(
                user=cfg.get('user', ''), password=cfg.get('password', ''),
                host=cfg.get('ip', ''), port=int(cfg.get('port', '1521') or '1521'),
                service_name=cfg.get('sid', ''))
        cur = conn.cursor()
        cur.execute('SELECT instance_name FROM apm_db_info ORDER BY instance_name')
        result = [r[0] for r in cur.fetchall() if r[0]]
        cur.close(); conn.close()
        return result
    except Exception:
        return []


def _api_history_data_pg(check_type, since, until, sel_date):
    # Get valid instances from apm_db_info
    valid_instances = _get_valid_instances()
    conn = _insp_pg_connect()
    if not conn:
        return json.dumps({'ok': False, 'error': 'Cannot connect to Inspector History DB. Check Configuration.'})
    cur = conn.cursor()
    if valid_instances:
        cur.execute(
            "SELECT DISTINCT instance_name, summary_type FROM insp_summary_history "
            "WHERE check_type=%s AND collected_at>=%s AND collected_at<=%s "
            "AND summary_type IS NOT NULL AND summary_type <> '' "
            "AND instance_name IN %s "
            "ORDER BY instance_name, summary_type",
            (check_type, since, until, tuple(valid_instances)))
    else:
        cur.execute(
            "SELECT DISTINCT instance_name, summary_type FROM insp_summary_history "
            "WHERE check_type=%s AND collected_at>=%s AND collected_at<=%s "
            "AND summary_type IS NOT NULL AND summary_type <> '' "
            "ORDER BY instance_name, summary_type",
            (check_type, since, until))
    groups = [{'inst': r[0], 'stype': r[1]} for r in cur.fetchall()]
    seen = set(); stypes = []
    for g in groups:
        if g['stype'] not in seen:
            seen.add(g['stype']); stypes.append(g['stype'])
    result = {}
    for g in groups:
        key = g['inst'] + '|||' + g['stype']
        cur.execute(
            "SELECT TO_CHAR(collected_at,'YYYY-MM-DD HH24:MI:SS'), status "
            "FROM insp_summary_history "
            "WHERE check_type=%s AND instance_name=%s AND COALESCE(summary_type,'')=%s "
            "AND collected_at>=%s AND collected_at<=%s ORDER BY collected_at",
            (check_type, g['inst'], g['stype'], since, until))
        result[key] = [{'t': r[0], 's': r[1]} for r in cur.fetchall()]
    cur.close(); conn.close()
    instances = sorted(set(g['inst'] for g in groups))
    return json.dumps({'ok': True, 'instances': instances, 'stypes': stypes,
                       'groups': groups, 'data': result, 'date': sel_date, 'type': check_type})


def api_history_range(path):
    qs = path.split('?', 1)[1] if '?' in path else ''
    raw = {}
    for p in qs.split('&'):
        if '=' in p:
            k, v = p.split('=', 1)
            raw[unquote(k)] = unquote(v)
    check_type = raw.get('type', '10min')
    if check_type not in ('10min', '1hour'):
        check_type = '10min'
    inst = raw.get('inst', '')
    stype = raw.get('stype', '')
    try:
        days = int(raw.get('days', '7'))
        if days not in (7, 30):
            days = 7
    except Exception:
        days = 7
    if not inst or not stype:
        return json.dumps({'ok': False, 'error': 'inst and stype required'})
    today = datetime.now().date()
    start_date = today - timedelta(days=days - 1)
    since = start_date.strftime('%Y-%m-%d') + ' 00:00:00'
    until = today.strftime('%Y-%m-%d') + ' 23:59:59'
    try:
        if _is_oracle_repo():
            conn = _oracle_connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT TO_CHAR(COLLECTED_AT,'YYYY-MM-DD HH24:MI:SS'), STATUS "
                "FROM INSP_SUMMARY_HISTORY "
                "WHERE CHECK_TYPE=:1 AND INSTANCE_NAME=:2 AND NVL(SUMMARY_TYPE,' ')=:3 "
                "AND COLLECTED_AT>=TO_TIMESTAMP(:4,'YYYY-MM-DD HH24:MI:SS') "
                "AND COLLECTED_AT<=TO_TIMESTAMP(:5,'YYYY-MM-DD HH24:MI:SS') "
                "ORDER BY COLLECTED_AT",
                (check_type, inst, stype or ' ', since, until))
        else:
            conn = _insp_pg_connect()
            if not conn:
                return json.dumps({'ok': False, 'error': 'Cannot connect to Inspector History DB.'})
            cur = conn.cursor()
            cur.execute(
                "SELECT TO_CHAR(collected_at,'YYYY-MM-DD HH24:MI:SS'), status "
                "FROM insp_summary_history "
                "WHERE check_type=%s AND instance_name=%s AND COALESCE(summary_type,'')=%s "
                "AND collected_at>=%s AND collected_at<=%s ORDER BY collected_at",
                (check_type, inst, stype, since, until))
        rows = cur.fetchall()
        cur.close(); conn.close()
        data = {}
        for row in rows:
            dt_str = row[0]
            day_key = dt_str[:10]
            if day_key not in data:
                data[day_key] = []
            data[day_key].append({'t': row[0], 's': row[1]})
        day_list = []
        cur_day = start_date
        while cur_day <= today:
            day_list.append(cur_day.strftime('%Y-%m-%d'))
            cur_day += timedelta(days=1)
        interval_ms = 600000 if check_type == '10min' else 3600000
        return json.dumps({'ok': True, 'days': day_list, 'data': data,
                           'interval_ms': interval_ms, 'inst': inst, 'stype': stype})
    except Exception as e:
        return json.dumps({'ok': False, 'error': str(e)})



def _history_sidebar(active='summary'):
    b = _UTILS_BASE

    def _hitem(path, label, key):
        cls = 'nav-item active' if active == key else 'nav-item'
        return '<a href="%s%s" class="%s">%s</a>' % (b, path, cls, label)

    def _hsub(path, label, key):
        cls = 'nav-sub active' if active == key else 'nav-sub'
        return '<a href="%s%s" class="%s">%s</a>' % (b, path, cls, label)

    def _hgrp(gid, label, children, first=False):
        arrow = ('<span class="nav-arrow" id="arrow-h-' + gid + '"'
                 ' style="font-size:.55rem;transition:transform .2s;display:inline-block;">&#9660;</span>')
        parts = []
        if not first:
            parts.append('<hr class="nav-divider">')
        parts += [
            '<div class="nav-lbl nav-toggle" onclick="hToggleNav(\'' + gid + '\')" '
            'style="cursor:pointer;display:flex;justify-content:space-between;align-items:center;'
            'user-select:none;">',
            '<span>' + label + '</span>' + arrow,
            '</div>',
            '<div class="nav-grp" id="grp-h-' + gid + '">',
            children,
            '</div>',
        ]
        return ''.join(parts)

    os_children = ''.join([
        _hsub('/history/os/cpu',    'CPU',    'os_cpu'),
        _hsub('/history/os/memory', 'Memory', 'os_memory'),
    ])
    from db_utils import _db_cfg as _hp_db_cfg
    _hp_is_pg = 'postgres' in _hp_db_cfg().get('db_type', 'Oracle').lower()
    disk_children = ''.join([
        _hsub('/history/disk/tbs', 'Disk' if _hp_is_pg else 'Tablespace', 'disk_tbs'),
    ])
    process_children = ''.join([
        _hsub('/history/process/status', 'Service Status', 'process_status'),
        _hsub('/history/process/qcnt',   'Qcnt Trend',     'process_qcnt'),
        _hsub('/history/process/heap',   'Heap Trend',     'process_heap'),
    ])
    summary_children = ''.join([
        _hsub('/history?type=10min', '10Min Summary', 'summary_10min'),
        _hsub('/history?type=1hour', '1Hour Summary', 'summary_1hour'),
    ])

    nav_js = (
        '<script>'
        'function _hNavHL(gid,open){'
        'var lbl=document.getElementById("arrow-h-"+gid);'
        'if(lbl)lbl=lbl.closest(".nav-lbl");'
        'if(lbl){if(open)lbl.classList.add("nav-open");else lbl.classList.remove("nav-open");}'
        '}'
        'function hToggleNav(gid){'
        'var g=document.getElementById("grp-h-"+gid);'
        'var a=document.getElementById("arrow-h-"+gid);'
        'if(g.style.display==="none"){'
        'g.style.display="";a.style.transform="rotate(0deg)";'
        'localStorage.setItem("hnav_"+gid,"1");_hNavHL(gid,true);'
        '}else{'
        'g.style.display="none";a.style.transform="rotate(-90deg)";'
        'localStorage.setItem("hnav_"+gid,"0");_hNavHL(gid,false);'
        '}}'
        '(function(){'
        '["os","disk","process","summary"].forEach(function(gid){'
        'var g=document.getElementById("grp-h-"+gid);if(!g)return;'
        'var a=document.getElementById("arrow-h-"+gid);'
        'var v=localStorage.getItem("hnav_"+gid);'
        'if(v==="0"){g.style.display="none";if(a)a.style.transform="rotate(-90deg)";_hNavHL(gid,false);}'
        'else{_hNavHL(gid,true);}'
        '});'
        'var _sb=document.querySelector(".sidebar");'
        'if(_sb){'
        '  var _sv=sessionStorage.getItem("hsb_scroll");'
        '  if(_sv)_sb.scrollTop=parseInt(_sv,10);'
        '  _sb.addEventListener("scroll",function(){sessionStorage.setItem("hsb_scroll",_sb.scrollTop);});'
        '}'
        '})();'
        '</script>'
    )

    return ''.join([
        '<aside class="sidebar">',
        '<div class="sb-brand">'
        '<div class="sb-brand-icon">'
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" '
        'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>'
        '</div>'
        '<div class="sb-brand-text"><span>Inspector</span><span>History</span></div>'
        '</div>',
        _hgrp('os',      'OS',      os_children, first=True),
        _hgrp('disk',    'Disk',    disk_children),
        _hgrp('process', 'Process', process_children),
        _hgrp('summary', 'Summary', summary_children),
        '<div class="nav-bottom">',
        '</div>',
        '</aside>',
        nav_js,
    ])


def _history_page(body, active='summary'):
    from html_helpers import _help_icon as _hicon
    theme_js = ''
    # topbar 좌측: 제목 + 회색 ⓘ (active 또는 'history_'+active 로 _HELP 매핑)
    help_key = active if active in _HELP else (
        ('history_' + active) if ('history_' + active) in _HELP else None)
    page_title = _HELP[help_key][0] if help_key else 'Inspector History'
    info_icon = _hicon(*_HELP[help_key], gray=True) if help_key else ''
    topbar_html = (
        '<div class="topbar" style="display:flex;align-items:center;justify-content:space-between;'
        'height:52px;padding:0 36px;background:#ffffff;border-bottom:1px solid #E2E8F0;'
        'position:sticky;top:0;z-index:50;">'
        '<div style="display:flex;align-items:center;gap:10px;">'
        '<span style="font-size:1.05rem;font-weight:700;color:#0F172A;letter-spacing:-.01em;'
        "font-family:Inter,Pretendard,sans-serif;\">" + page_title + '</span>'
        + info_icon +
        '</div>'
        '<div style="display:flex;gap:8px;align-items:center;">'
        # Inspector 본체와 동일한 indigo chip 스타일 (기본 indigo-50, hover 시 solid indigo).
        '<a href="' + _UTILS_BASE + '/" '
        'style="display:inline-flex;align-items:center;gap:6px;padding:6px 16px;'
        'background:#EEF2FF;border:1px solid #C7D2FE;'
        'color:#4F46E5;border-radius:8px;font-size:.78rem;font-weight:600;'
        'text-decoration:none;letter-spacing:.02em;transition:all .15s;'
        'font-family:Inter,Pretendard,sans-serif;" '
        'onmouseover="this.style.background=\'#6366F1\';this.style.borderColor=\'#6366F1\';this.style.color=\'#ffffff\';" '
        'onmouseout="this.style.background=\'#EEF2FF\';this.style.borderColor=\'#C7D2FE\';this.style.color=\'#4F46E5\';">'
        '&#8592; Back to Inspector</a>'
        '<a href="/MAXGAUGE/labs/" target="_top" '
        'style="display:inline-flex;align-items:center;gap:6px;padding:6px 16px;'
        'background:#EEF2FF;border:1px solid #C7D2FE;'
        'color:#4F46E5;border-radius:8px;font-size:.78rem;font-weight:600;'
        'text-decoration:none;letter-spacing:.02em;transition:all .15s;'
        'font-family:Inter,Pretendard,sans-serif;" '
        'onmouseover="this.style.background=\'#6366F1\';this.style.borderColor=\'#6366F1\';this.style.color=\'#ffffff\';" '
        'onmouseout="this.style.background=\'#EEF2FF\';this.style.borderColor=\'#C7D2FE\';this.style.color=\'#4F46E5\';">'
        '&#8592; Labs</a>'
        '</div>'
        '</div>'
    )
    return ''.join([
        '<!DOCTYPE html><html lang="en"><head>',
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,'
        '%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 32 32%27%3E'
        '%3Cdefs%3E%3ClinearGradient id=%27g%27 x1=%270%27 y1=%270%27 x2=%271%27 y2=%271%27%3E'
        '%3Cstop offset=%270%25%27 stop-color=%27%236366F1%27/%3E'
        '%3Cstop offset=%27100%25%27 stop-color=%27%238B5CF6%27/%3E'
        '%3C/linearGradient%3E%3C/defs%3E'
        '%3Crect width=%2732%27 height=%2732%27 rx=%278%27 fill=%27url(%23g)%27/%3E'
        '%3Cpolyline points=%2726 16 22 16 19 25 13 7 10 16 6 16%27 '
        'fill=%27none%27 stroke=%27white%27 stroke-width=%272.5%27 '
        'stroke-linecap=%27round%27 stroke-linejoin=%27round%27/%3E'
        '%3C/svg%3E">',
        '<title>Inspector History - MaxGauge Inspector</title>',
        # Inspector 본체와 동일한 Pretendard / Inter 웹폰트 로드 — 누락 시 시스템 fallback 으로 글꼴이 달라 보임.
        '<link rel="preconnect" href="https://fonts.googleapis.com">',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        '<link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css" rel="stylesheet">',
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">',
        '<style>', _CSS, '</style>',
        theme_js,
        '</head><body>',
        '<div class="layout">',
        _history_sidebar(active),
        '<main class="main">',
        topbar_html,
        _HELP_JS,
        '<div class="content-wrap">', body, '</div>',
        _tools_fab_block(),
        '</main>',
        '</div></body></html>',
    ])


def page_history(path=''):
    qs = path.split('?', 1)[1] if '?' in path else ''
    params = {}
    for p in qs.split('&'):
        if '=' in p:
            k, v = p.split('=', 1)
            params[k] = v
    check_type = params.get('type', '10min')
    if check_type not in ('10min', '1hour'):
        check_type = '10min'
    b = _UTILS_BASE + '/history'
    TAB_ON  = ('display:inline-block;padding:7px 20px;border-radius:8px;font-size:.82rem;'
               'font-weight:600;text-decoration:none;background:var(--c-accent);color:#fff;margin-right:6px;')
    TAB_OFF = ('display:inline-block;padding:7px 20px;border-radius:8px;font-size:.82rem;'
               'font-weight:600;text-decoration:none;background:var(--bg-card);'
               'color:var(--c-muted);border:1px solid var(--bd);margin-right:6px;')
    if check_type == '10min':
        _title = '10Min Summary History'
        _sub   = '10-minute interval collection from INSP_SUMMARY_HISTORY'
    else:
        _title = '1Hour Summary History'
        _sub   = '1-hour interval collection from INSP_SUMMARY_HISTORY'
    body = ''.join([
        _page_title_html(_title, *_HELP.get('history_summary_' + check_type, (_title, ''))),
        '<div id="hist-card" class="card">',
        '<div id="hist-search-bar" class="cpu-search-bar" style="padding:0;border:none;background:transparent;margin-bottom:16px;">'
        '<button type="button" class="sb-arrow" onclick="_shiftDateInput(\'hist-sel-date\',-1)">&#8249;</button>'
        '<div class="sb-group">'
        '<label>Date</label>'
        '<input type="date" id="hist-sel-date">'
        '<button type="button" class="sb-cal-btn" onclick="document.getElementById(\'hist-sel-date\').showPicker()">'
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">'
        '<rect x="2" y="3" width="12" height="11" rx="2"/><path d="M2 7h12M5 1v3M11 1v3"/></svg></button>'
        '</div>'
        '<button type="button" class="sb-arrow" onclick="_shiftDateInput(\'hist-sel-date\',1)">&#8250;</button>'
        '<button class="sb-qbtn hist-qbtn" id="hqb-yesterday" onclick="_histQuick(\'yesterday\')">Yesterday</button>'
        '<button class="sb-qbtn hist-qbtn active" id="hqb-today" onclick="_histQuick(\'today\')">Today</button>'
        '</div>',
        '<div id="hist-controls" style="margin-bottom:8px;"></div>',
        '<div id="hist-chart-area"><div style="color:var(--c-muted);font-size:.85rem;padding:30px 0;text-align:center;">Loading...</div></div>',
        '<div id="hist-legend" style="display:flex;justify-content:flex-end;gap:14px;align-items:center;font-size:.72rem;color:var(--c-muted);margin-top:12px;">',
        '<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#22c55e;margin-right:4px;vertical-align:middle;"></span>OK</span>',
        '<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#f59e0b;margin-right:4px;vertical-align:middle;"></span>WAITING</span>',
        '<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#ef4444;margin-right:4px;vertical-align:middle;"></span>CHECK</span>',
        '<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#CBD5E1;margin-right:4px;vertical-align:middle;"></span>No Data</span>',
        '</div>',
        '</div>',
        _view_css(), _cpu_chart_css(),
        _history_js(check_type),
        _ts(),
    ])
    return _history_page(body, active="summary_" + check_type)


def _history_js(check_type):
    api_base = _UTILS_BASE + '/api/history-data?type=' + check_type
    interval_ms = "600000" if check_type == "10min" else "3600000"
    js = """
<div id="hist-tooltip" style="display:none;position:fixed;z-index:9999;
     background:#ffffff;border:1px solid #E2E8F0;border-radius:8px;
     padding:8px 14px;font-size:.78rem;pointer-events:none;
     box-shadow:0 8px 24px rgba(0,0,0,.12);min-width:140px;"></div>
<script>
(function(){
var INTERVAL = __INTERVAL_MS__;
var CELL_H        = 30;
var HOUR_GAP      = 2;
var CELL_INNER_GAP= 0;
var LABEL_W       = 160;
var RULER_H  = 28;
var R        = 3;
var SC       = {OK:'#3ecf82', WAITING:'#e8a020', CHECK:'#e05555'};
var API_BASE = '__API_BASE__';
var _base = API_BASE.split('/api/')[0];
var INST_URL = API_BASE.split('/api/history-data')[0]+'/api/history-instances';

var gData=null, curDate=todayStr(), curInst=null, curStype=null, curRange=null;
var allInstances=[], slots=[];
var cvsList=[], rulerTop=null, rulerBot=null;
var hoverCol=null, ddActive=null;
var areaEl=document.getElementById('hist-chart-area');
var ctrlEl=document.getElementById('hist-controls');
var tt=document.getElementById('hist-tooltip');
document.addEventListener('click',function(){if(ddActive){ddActive.style.display='none';ddActive=null;}},true);

function pad(n){return n<10?'0'+n:''+n;}
function todayStr(){var d=new Date();return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate());}
function shiftDate(d,n){var dt=new Date(d+'T00:00:00');dt.setDate(dt.getDate()+n);return dt.getFullYear()+'-'+pad(dt.getMonth()+1)+'-'+pad(dt.getDate());}
function parseMs(s){return new Date(s.replace(' ','T')).getTime();}
function isDark(){return false;}

function _cellW(W){
  var sph=Math.round(3600000/INTERVAL);
  return (W - 23*HOUR_GAP - 24*(sph>1?(sph-1)*CELL_INNER_GAP:0)) / (24*sph);
}
function slotPos(i, W){
  var sph=Math.round(3600000/INTERVAL);
  var hourIdx=Math.floor(i/sph), slotInHour=i%sph;
  var cw=_cellW(W);
  var hourW=sph*cw+(sph>1?(sph-1)*CELL_INNER_GAP:0);
  var rx=hourIdx*(hourW+HOUR_GAP)+slotInHour*(cw+CELL_INNER_GAP);
  return {x:Math.round(rx), w:Math.max(1,Math.round(rx+cw)-Math.round(rx))};
}
function xToSlot(mx, W){
  var sph=Math.round(3600000/INTERVAL);
  var cw=_cellW(W);
  var hourW=sph*cw+(sph>1?(sph-1)*CELL_INNER_GAP:0);
  var hourIdx=Math.max(0,Math.min(23,Math.floor(mx/(hourW+HOUR_GAP))));
  var xInHour=mx-hourIdx*(hourW+HOUR_GAP);
  var si=hourIdx*sph+Math.max(0,Math.min(sph-1,Math.floor(xInHour/(cw+CELL_INNER_GAP))));
  return Math.max(0,Math.min(slots.length-1,si));
}
function buildSlots(dateStr){
  slots=[];
  var sph=Math.round(3600000/INTERVAL);
  var base=new Date(dateStr+'T00:00:00').getTime();
  for(var i=0;i<24*sph;i++) slots.push(base+i*INTERVAL);
}
function matchSlots(pts){
  var map={};
  pts.forEach(function(p){
    var ts=parseMs(p.t);
    var si=Math.floor((ts-slots[0])/INTERVAL);
    if(si>=0&&si<slots.length) map[si]=p.s;
  });
  var out=[];
  for(var i=0;i<slots.length;i++) out.push(map[i]||null);
  return out;
}

function drawRow(ent){
  var cv=ent.canvas; var W=cv.width; if(!W) return;
  var ctx=cv.getContext('2d'); var dark=isDark();
  ctx.clearRect(0,0,W,CELL_H);
  var emptyCol=dark?'#132240':'#dde8f4';
  ent.cells.forEach(function(s,i){
    var pos=slotPos(i,W); var x=pos.x; var w=pos.w;
    var col=s?(SC[s]||'#64748b'):emptyCol;
    if(i===hoverCol){
      ctx.fillStyle=s?lightenHex(SC[s]||'#64748b',30):(dark?'#1e3a5f':'#b8d0e8');
    } else {
      ctx.fillStyle=col;
    }
    ctx.fillRect(x,2,w,CELL_H-4);
  });
}
function lightenHex(hex,a){
  var r=parseInt(hex.slice(1,3),16),g=parseInt(hex.slice(3,5),16),b=parseInt(hex.slice(5,7),16);
  return 'rgb('+Math.min(255,r+a)+','+Math.min(255,g+a)+','+Math.min(255,b+a)+')';}

function drawRuler(cv, pos){
  if(!cv||!cv.width) return;
  var W=cv.width; var ctx=cv.getContext('2d'); var dark=isDark();
  ctx.clearRect(0,0,W,RULER_H);
  var sph=Math.round(3600000/INTERVAL);
  for(var h=0;h<24;h++){
    var hIdx=h*sph;
    var x0=slotPos(hIdx,W).x;
    var x1=hIdx+sph-1<slots.length?slotPos(hIdx+sph-1,W).x+slotPos(hIdx+sph-1,W).w:W;
    var cx=(x0+x1)/2;
    ctx.fillStyle=dark?'rgba(148,163,184,0.4)':'rgba(30,41,59,0.3)';
    ctx.fillRect(x0,pos==='top'?RULER_H-8:0,1,8);
    ctx.font='bold 10px monospace';
    ctx.textAlign='center';
    ctx.textBaseline='middle';
    ctx.fillStyle=dark?'#64748b':'#64748b';
    ctx.fillText(pad(h),cx,RULER_H/2);
  }
  if(hoverCol!==null&&hoverCol<slots.length){
    var hp=slotPos(hoverCol,W);
    ctx.fillStyle=dark?'rgba(124,159,255,0.18)':'rgba(60,100,200,0.12)';
    ctx.fillRect(hp.x,0,hp.w,RULER_H);
  }
}

function showErr(msg,detail){
  var hc=document.getElementById('hist-card');if(hc){hc.style.border='none';hc.style.boxShadow='none';}
  var sb=document.getElementById('hist-search-bar');if(sb)sb.style.display='none';
  var ct=document.getElementById('hist-controls');if(ct)ct.style.display='none';
  var lg=document.getElementById('hist-legend');if(lg)lg.style.display='none';
  if(msg==='TABLE_NOT_EXIST'){
    areaEl.innerHTML='<div style="text-align:center;padding:60px 20px;">'
      +'<div style="font-size:2rem;margin-bottom:16px;">&#9888;</div>'
      +'<div style="font-size:1rem;font-weight:700;color:#0F172A;margin-bottom:8px;">'
      +'테이블이 존재하지 않습니다</div>'
      +'<div style="font-size:.85rem;color:#64748B;margin-bottom:20px;">'
      +'<code style="background:#F1F5F9;padding:2px 8px;border-radius:4px;font-size:.82rem;">'
      +'INSP_SUMMARY_HISTORY</code> 테이블이 생성되지 않았습니다.</div>'
      +'<div style="font-size:.85rem;color:#64748B;">'
      +'<a href="'+_base+'/config" style="color:#6366F1;font-weight:600;text-decoration:none;">'
      +'Configuration</a> 에서 테이블을 생성해 주세요.</div></div>';
  }else if(msg==='Network error'){
    areaEl.innerHTML='<div style="text-align:center;color:#94A3B8;padding:40px;">네트워크 오류</div>';
  }else{
    areaEl.innerHTML='<div style="text-align:center;color:#94A3B8;padding:40px;">'+msg+'</div>';
  }
}

function refresh(){
  areaEl.innerHTML='';
  if(!gData||!gData.ok){showErr(gData?gData.error:'데이터 없음',gData?gData.detail:null);return;}
  buildSlots(curDate);
  var groups=gData.groups.filter(function(g){
    return (!curInst||g.inst===curInst)&&(!curStype||g.stype===curStype);
  }).map(function(g){
    var key=g.inst+'|||'+g.stype;
    return {inst:g.inst,stype:g.stype,pts:gData.data[key]||[]};
  });
  cvsList=[]; rulerTop=null; rulerBot=null;
  if(!groups.length){
    areaEl.innerHTML='<div style="color:var(--c-muted);font-size:.85rem;padding:40px 0;text-align:center;">데이터 없음 for selected filter.</div>';
    return;
  }
  var outer=document.createElement('div');
  var trObj=makeRulerRow(); outer.appendChild(trObj.row);
  var prevInst=null;
  groups.forEach(function(g){
    if(g.inst!==prevInst&&prevInst!==null){
      var sep=document.createElement('div');
      sep.style.cssText='display:flex;align-items:center;margin:5px 0 3px;';
      var s1=document.createElement('div'); s1.style.cssText='width:'+LABEL_W+'px;flex-shrink:0;';
      var s2=document.createElement('div'); s2.style.cssText='flex:1;height:1px;background:var(--bd);opacity:0.5;';
      sep.appendChild(s1); sep.appendChild(s2); outer.appendChild(sep);
    }
    prevInst=g.inst;
    var row=document.createElement('div'); row.style.cssText='display:flex;align-items:center;margin-bottom:2px;';
    var lbl=document.createElement('div'); lbl.style.cssText='width:'+LABEL_W+'px;flex-shrink:0;padding-right:14px;box-sizing:border-box;';
    var nm=document.createElement('div'); nm.style.cssText='font-size:.73rem;font-weight:700;color:var(--c-main);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.4;';
    nm.title=g.inst; nm.textContent=g.inst;
    var stDiv=document.createElement('div'); stDiv.style.cssText='font-size:.6rem;color:var(--c-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:1px;';
    stDiv.textContent=g.stype||'--';
    lbl.appendChild(nm); lbl.appendChild(stDiv); row.appendChild(lbl);
    var cvWrap=document.createElement('div'); cvWrap.style.cssText='flex:1;min-width:0;border-radius:4px;overflow:hidden;';
    var cv=document.createElement('canvas'); cv.height=CELL_H; cv.style.cssText='width:100%;display:block;cursor:crosshair;';
    cvWrap.appendChild(cv); row.appendChild(cvWrap); outer.appendChild(row);
    var cells=matchSlots(g.pts);
    var entry={canvas:cv,cells:cells,inst:g.inst,stype:g.stype};
    cvsList.push(entry);
    (function(ent){
      ent.canvas.addEventListener('mousemove',function(e){
        var W=ent.canvas.width; if(!W) return;
        var rect=ent.canvas.getBoundingClientRect();
        var mx=(e.clientX-rect.left)*(W/rect.width);
        var si=xToSlot(mx,W);
        if(si!==hoverCol){hoverCol=si;redrawAll();}
        var slotDate=new Date(slots[si]);
        var tstr=pad(slotDate.getHours())+':'+pad(slotDate.getMinutes());
        var stat=ent.cells[si];
        var scol=stat?(SC[stat]||'#94a3b8'):'#64748b';
        tt.style.display='block';
        var tx=e.clientX+14,ty=e.clientY-50;
        if(tx+200>window.innerWidth)tx=e.clientX-210;
        if(ty<10)ty=e.clientY+20;
        tt.style.left=tx+'px'; tt.style.top=ty+'px';
        tt.innerHTML='<div style="font-weight:700;color:#0F172A;margin-bottom:4px;">'+ent.inst+'</div>'
          +(ent.stype?'<div style="font-size:.68rem;color:#64748B;margin-bottom:6px;">'+ent.stype+'</div>':'')
          +'<div style="display:flex;align-items:center;gap:6px;">'
          +'<div style="width:8px;height:8px;border-radius:2px;background:'+scol+';"></div>'
          +'<span style="color:#64748B;">'+tstr+'</span>'
          +'<span style="font-weight:700;color:'+scol+';">'+(stat||'No Data')+'</span></div>';
      });
      ent.canvas.addEventListener('mouseleave',function(){hoverCol=null;tt.style.display='none';redrawAll();});
    })(entry);
  });
  var brObj=makeRulerRow(); outer.appendChild(brObj.row);
  areaEl.appendChild(outer);
  requestAnimationFrame(function(){
    var W=0;
    cvsList.forEach(function(e){
      e.canvas.width=e.canvas.parentElement.offsetWidth;
      if(!W) W=e.canvas.width;
      drawRow(e);
    });
    trObj.cv.width=trObj.cv.parentElement.offsetWidth||W;
    brObj.cv.width=brObj.cv.parentElement.offsetWidth||W;
    rulerTop=trObj.cv; rulerBot=brObj.cv;
    drawRuler(rulerTop,'top'); drawRuler(rulerBot,'bottom');
  });
}

function makeRulerRow(){
  var row=document.createElement('div'); row.style.cssText='display:flex;align-items:center;margin-bottom:3px;';
  var lbl=document.createElement('div'); lbl.style.cssText='width:'+LABEL_W+'px;flex-shrink:0;';
  row.appendChild(lbl);
  var cvWrap=document.createElement('div'); cvWrap.style.cssText='flex:1;min-width:0;';
  var cv=document.createElement('canvas'); cv.height=RULER_H; cv.style.cssText='width:100%;display:block;';
  cvWrap.appendChild(cv); row.appendChild(cvWrap);
  return {row:row,cv:cv};
}

function redrawAll(){
  cvsList.forEach(function(e){drawRow(e);});
  drawRuler(rulerTop,'top'); drawRuler(rulerBot,'bottom');
}

function mkBtn(html){
  var b=document.createElement('button');
  b.innerHTML=html;
  b.style.cssText='background:var(--bg-input);border:1px solid var(--bd);color:var(--c-main);border-radius:6px;padding:3px 10px;font-size:1rem;cursor:pointer;line-height:1.5;';
  return b;
}

function makeInstDD(){
  var wrap=document.createElement('div'); wrap.style.position='relative';
  var box=document.createElement('div');
  box.style.cssText='display:flex;align-items:center;background:var(--bg-input);border:1px solid var(--bd);border-radius:6px;overflow:hidden;';
  var inp=document.createElement('input'); inp.type='text'; inp.readOnly=true;
  inp.value=curInst||''; inp.placeholder='All Instances';
  inp.style.cssText='background:transparent;border:none;outline:none;color:var(--c-main);font-size:.78rem;font-weight:600;padding:4px 8px;width:140px;cursor:pointer;';
  var arr=document.createElement('button'); arr.innerHTML='&#9660;';
  arr.style.cssText='background:transparent;border:none;border-left:1px solid var(--bd);color:var(--c-muted);padding:4px 8px;font-size:.6rem;cursor:pointer;';
  box.appendChild(inp); box.appendChild(arr);
  var list=document.createElement('div');
  list.style.cssText='display:none;position:absolute;top:calc(100% + 4px);left:0;z-index:300;min-width:190px;background:var(--bg-card);border:1px solid var(--bd);border-radius:8px;box-shadow:0 8px 32px rgba(0,0,0,.25);overflow:hidden;';
  var srch=document.createElement('input'); srch.type='text'; srch.placeholder='Search...';
  srch.style.cssText='display:block;width:100%;box-sizing:border-box;background:var(--bg-input);border:none;border-bottom:1px solid var(--bd);outline:none;color:var(--c-main);font-size:.75rem;padding:7px 10px;';
  var items=document.createElement('div'); items.style.maxHeight='220px'; items.style.overflowY='auto';
  function fill(q){
    items.innerHTML='';
    [''].concat(allInstances).forEach(function(v){
      if(q&&v&&v.toLowerCase().indexOf(q.toLowerCase())===-1) return;
      var d=document.createElement('div');
      var act=(curInst===null&&v==='')||(curInst===v);
      d.style.cssText='padding:7px 12px;font-size:.78rem;cursor:pointer;'+(act?'background:var(--c-accent);color:#fff;':'color:var(--c-main);');
      d.textContent=v||'All Instances';
      d.onmouseenter=function(){if(!act)this.style.background='var(--bg-input)';};
      d.onmouseleave=function(){if(!act)this.style.background='';};
      d.onclick=function(){curInst=v||null;inp.value=curInst||'';inp.placeholder=curInst?'':'All Instances';list.style.display='none';ddActive=null;curRange=null;updateRangeButtons();refresh();};
      items.appendChild(d);
    });
  }
  fill(''); srch.oninput=function(){fill(this.value);};
  list.appendChild(srch); list.appendChild(items);
  wrap.appendChild(box); wrap.appendChild(list);
  function toggle(e){e.stopPropagation();var open=ddActive===list;if(ddActive){ddActive.style.display='none';ddActive=null;}if(!open){list.style.display='block';ddActive=list;srch.value='';fill('');srch.focus();}}
  inp.onclick=toggle; arr.onclick=toggle;
  list.addEventListener('click',function(e){e.stopPropagation();});
  return wrap;
}

function buildStypeButtons(){
  var sw=document.getElementById('hist-stype-wrap');
  if(!sw||!gData) return;
  var stypes=[],sSet={};
  gData.groups.forEach(function(g){
    if(g.stype&&!sSet[g.stype]){sSet[g.stype]=1;stypes.push(g.stype);}
  });
  stypes.sort();
  sw.innerHTML='';
  if(!stypes.length) return;
  function mkSBtn(label,val){
    var act=(val===null&&curStype===null)||(val!==null&&val===curStype);
    var b=document.createElement('button');
    b.textContent=label;
    b.style.cssText=(act?'background:var(--c-accent);border:1px solid var(--c-accent);color:#fff;':'background:transparent;border:1px solid var(--bd);color:var(--c-muted);')+'padding:4px 12px;border-radius:999px;font-size:.73rem;font-weight:600;cursor:pointer;white-space:nowrap;transition:all .15s;font-family:Inter,Pretendard,sans-serif;';
    b.onclick=function(){curStype=val;curRange=null;buildStypeButtons();updateRangeButtons();refresh();};
    return b;
  }
  sw.appendChild(mkSBtn('ALL',null));
  stypes.forEach(function(st){sw.appendChild(mkSBtn(st,st));});
}

function updateRangeButtons(){
  var rw=document.getElementById('hist-range-wrap');
  if(!rw) return;
  var show=(curInst!==null&&curStype!==null);
  rw.style.display=show?'flex':'none';
  if(!show){curRange=null;return;}
  rw.innerHTML='';
  function mkRBtn(label,days){
    var act=(curRange===days);
    var b=document.createElement('button');
    b.textContent=label;
    b.style.cssText=(act?'background:var(--c-accent);border:1px solid var(--c-accent);color:#fff;':'background:transparent;border:1px solid var(--bd);color:var(--c-muted);')+'padding:4px 12px;border-radius:999px;font-size:.73rem;font-weight:600;cursor:pointer;white-space:nowrap;font-family:Inter,Pretendard,sans-serif;';
    b.onclick=function(){
      if(curRange===days){curRange=null;updateRangeButtons();refresh();}
      else{curRange=days;updateRangeButtons();loadRangeData(days);}
    };
    return b;
  }
  rw.appendChild(mkRBtn('Last Week',7));
  rw.appendChild(mkRBtn('Last Month',30));
}

function loadRangeData(days){
  var rangeApiBase=API_BASE.split('/api/history-data')[0]+'/api/history-range';
  var url=rangeApiBase+'?type='+API_BASE.split('type=')[1].split('&')[0]+'&inst='+encodeURIComponent(curInst)+'&stype='+encodeURIComponent(curStype)+'&days='+days;
  areaEl.innerHTML='<div style="color:var(--c-muted);font-size:.85rem;padding:40px 0;text-align:center;">Loading '+days+'-day view...</div>';
  fetch(url).then(function(r){return r.json();}).then(function(d){if(d.ok){refreshRange(d);}else{showErr(d.error);}}).catch(function(){showErr('Network error');});
}

function drawRangeRow(cv,smap,totalSlots,INTERVAL_R,sph){
  var CW=cv.width; var cw=_cellW(CW); var dark=isDark();
  var ctx=cv.getContext('2d'); ctx.clearRect(0,0,CW,CELL_H);
  var emptyCol=dark?'#132240':'#dde8f4';
  for(var si=0;si<totalSlots;si++){
    var pos=slotPos(si,CW); var s=smap[si];
    ctx.fillStyle=s?(SC[s]||'#64748b'):emptyCol;
    ctx.fillRect(pos.x,2,pos.w,CELL_H-4);
  }
}

function refreshRange(rd){
  var INTERVAL_R=rd.interval_ms; var sph=Math.round(3600000/INTERVAL_R); var totalSlots=24*sph;
  areaEl.innerHTML='';
  var titleEl=document.createElement('div');
  titleEl.style.cssText='font-size:.75rem;color:var(--c-muted);margin-bottom:8px;font-weight:600;letter-spacing:.04em;';
  titleEl.textContent=(curRange===7?'Last 7 Days':'Last 30 Days')+' -- '+curInst+' / '+curStype;
  areaEl.appendChild(titleEl);
  var outer=document.createElement('div'); outer.style.cssText='display:flex;flex-direction:column;gap:2px;';
  var hRow=document.createElement('div'); hRow.style.cssText='display:flex;align-items:center;';
  var hLbl=document.createElement('div'); hLbl.style.cssText='width:'+LABEL_W+'px;flex-shrink:0;font-size:.65rem;color:var(--c-muted);text-align:right;padding-right:10px;';
  hLbl.textContent='Date / Hour'; hRow.appendChild(hLbl);
  var hWrap=document.createElement('div'); hWrap.style.cssText='flex:1;min-width:0;';
  var hcv=document.createElement('canvas'); hcv.height=RULER_H; hcv.style.cssText='width:100%;display:block;';
  hWrap.appendChild(hcv); hRow.appendChild(hWrap); outer.appendChild(hRow);
  var rangeCvs=[];
  rd.days.forEach(function(dayStr){
    var dayData=rd.data[dayStr]||[];
    var smap={};
    dayData.forEach(function(pt){
      var ts=parseMs(pt.t);
      var dayStart=new Date(dayStr+'T00:00:00').getTime();
      var si=Math.floor((ts-dayStart)/INTERVAL_R);
      if(si>=0&&si<totalSlots) smap[si]=pt.s;
    });
    var row=document.createElement('div'); row.style.cssText='display:flex;align-items:center;';
    var lbl=document.createElement('div'); lbl.style.cssText='width:'+LABEL_W+'px;flex-shrink:0;font-size:.68rem;color:var(--c-muted);text-align:right;padding-right:10px;font-weight:600;';
    lbl.textContent=dayStr; row.appendChild(lbl);
    var cvWrap=document.createElement('div'); cvWrap.style.cssText='flex:1;min-width:0;border-radius:3px;overflow:hidden;';
    var cv=document.createElement('canvas'); cv.height=CELL_H; cv.style.cssText='width:100%;display:block;cursor:crosshair;';
    cvWrap.appendChild(cv); row.appendChild(cvWrap); outer.appendChild(row);
    rangeCvs.push({cv:cv,smap:smap,dayStr:dayStr});
    (function(cv2,smap2,dayStr2){
      cv2.addEventListener('mousemove',function(e){
        var W2=cv2.width; if(!W2) return;
        var rect=cv2.getBoundingClientRect();
        var mx=(e.clientX-rect.left)*(W2/rect.width);
        var si2=xToSlot(mx,W2); si2=Math.max(0,Math.min(totalSlots-1,si2));
        var s2=smap2[si2]; var h2=Math.floor(si2/sph); var m2=(si2%sph)*(60/sph);
        var ts2=dayStr2+'T'+pad(h2)+':'+pad(m2)+':00';
        tt.style.display='block'; tt.style.left=(e.clientX+12)+'px'; tt.style.top=(e.clientY-50)+'px';
        tt.innerHTML='<div style="font-size:.68rem;color:#475569;margin-bottom:4px;">'+ts2.replace('T',' ')+'</div>'+
          '<div style="font-weight:700;color:'+(s2?(SC[s2]||'#94a3b8'):'#64748b')+';font-size:.88rem;">'+(s2||'No Data')+'</div>';
      });
      cv2.addEventListener('mouseleave',function(){tt.style.display='none';});
    })(cv,smap,dayStr);
  });
  areaEl.appendChild(outer);
  requestAnimationFrame(function(){
    var W=hcv.parentElement?hcv.parentElement.offsetWidth:0;
    if(!W) W=areaEl.offsetWidth-LABEL_W;
    if(W<100) W=900-LABEL_W;
    hcv.width=W;
    rangeCvs.forEach(function(rc){
      rc.cv.width=rc.cv.parentElement?rc.cv.parentElement.offsetWidth:W;
      drawRangeRow(rc.cv,rc.smap,totalSlots,INTERVAL_R,sph);
    });
  });
}

function buildControls(){
  if(!ctrlEl) return;
  ctrlEl.innerHTML='';
  var wrap=document.createElement('div');
  wrap.style.cssText='display:flex;align-items:center;gap:10px;flex-wrap:wrap;';
  if(allInstances.length>0){
    wrap.appendChild(makeInstDD());
  }
  var sw=document.createElement('div'); sw.id='hist-stype-wrap'; sw.style.cssText='display:flex;align-items:center;gap:6px;flex-wrap:wrap;';
  wrap.appendChild(sw);
  var rw=document.createElement('div'); rw.id='hist-range-wrap'; rw.style.cssText='display:none;align-items:center;gap:6px;';
  wrap.appendChild(rw);
  ctrlEl.appendChild(wrap);
}

document.getElementById('hist-sel-date').value=todayStr();
function _histQuick(mode){
  document.querySelectorAll('.hist-qbtn').forEach(function(b){b.classList.remove('active');});
  var now=new Date();
  if(mode==='yesterday'){
    now.setDate(now.getDate()-1);
    document.getElementById('hqb-yesterday').classList.add('active');
  }else{
    document.getElementById('hqb-today').classList.add('active');
  }
  var ds=now.getFullYear()+'-'+pad(now.getMonth()+1)+'-'+pad(now.getDate());
  document.getElementById('hist-sel-date').value=ds;
  curDate=ds;loadData();
}
window._histQuick=_histQuick;
document.getElementById('hist-sel-date').addEventListener('change',function(){
  document.querySelectorAll('.hist-qbtn').forEach(function(b){b.classList.remove('active');});
  curDate=this.value;loadData();
});
function loadData(){
  curRange=null;
  areaEl.innerHTML='<div style="color:var(--c-muted);font-size:.85rem;padding:40px 0;text-align:center;">Loading...</div>';
  fetch(API_BASE+'&date='+curDate)
    .then(function(r){return r.json();})
    .then(function(d){gData=d;if(d.ok){buildStypeButtons();updateRangeButtons();refresh();}else{showErr(d.error,d.detail);}})
    .catch(function(){showErr('Network error');});
}

var _resizeTimer=null;
window.addEventListener('resize',function(){
  clearTimeout(_resizeTimer);
  _resizeTimer=setTimeout(function(){if(curRange!==null){loadRangeData(curRange);}else{refresh();}},200);
});

fetch(INST_URL)
  .then(function(r){return r.json();})
  .then(function(d){if(d.ok&&d.instances)allInstances=d.instances;})
  .catch(function(){})
  .then(function(){buildControls();loadData();});
})();
</script>
"""
    return js.replace('__API_BASE__', api_base).replace('__INTERVAL_MS__', interval_ms)


# ── Inspector History Configuration ──────────────────────────────────────────────

import os as _os

_INSP_CFG_PATH = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'insp_config.json')



def _save_insp_config(cfg):
    with open(_INSP_CFG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2)


def api_insp_create_schema():
    """Create the INSP schema in PG."""
    from db_utils import _db_cfg
    db_type = _db_cfg().get("db_type", "Oracle").lower()
    if "postgres" not in db_type:
        return json.dumps({"ok": False, "error": "PostgreSQL only"})
    from insp_pg import insp_pg_create_schema
    ok, msg = insp_pg_create_schema()
    return json.dumps({"ok": ok, "message": msg})


def api_insp_init_tables():
    from db_utils import _db_cfg
    db_type = _db_cfg().get("db_type", "Oracle").lower()
    if "postgres" in db_type:
        from insp_pg import insp_pg_create_schema, insp_pg_create_tables
        # Create schema first
        insp_pg_create_schema()
        ok, msg = insp_pg_create_tables()
    else:
        from insp_oracle import insp_create_tables
        ok, msg = insp_create_tables()
    if ok:
        cfg = _load_insp_config()
        cfg["tables_initialized"] = True
        _save_insp_config(cfg)
    elif "already exist" in msg:
        cfg = _load_insp_config()
        cfg["tables_initialized"] = True
        _save_insp_config(cfg)
        return json.dumps({"ok": True, "message": "INSP_ tables already exist. Config updated."})
    return json.dumps({"ok": ok, "message": msg})


def api_insp_drop_tables():
    from db_utils import _db_cfg
    db_type = _db_cfg().get("db_type", "Oracle").lower()
    if "postgres" in db_type:
        from insp_pg import insp_pg_drop_tables
        ok, msg = insp_pg_drop_tables()
    else:
        from insp_oracle import insp_drop_tables
        ok, msg = insp_drop_tables()
    if ok:
        cfg = _load_insp_config()
        cfg["tables_initialized"] = False
        cfg["enabled"] = False
        _save_insp_config(cfg)
    return json.dumps({"ok": ok, "message": msg})


def api_insp_table_status():
    """Return existence status of each INSP table."""
    from db_utils import _db_cfg
    db_type = _db_cfg().get("db_type", "Oracle").lower()
    try:
        if "postgres" in db_type:
            from insp_pg import insp_pg_check_each_table
            status = insp_pg_check_each_table()
        else:
            from insp_oracle import insp_check_each_table
            status = insp_check_each_table()
        # normalize keys to uppercase
        result = {k.upper(): v for k, v in status.items()}
        return json.dumps({"ok": True, "tables": result})
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)[:200]})


def api_insp_create_one_table(raw):
    """Create a single missing INSP table."""
    from db_utils import _db_cfg
    try:
        data = json.loads(raw)
        table_name = data.get("table", "")
        if not table_name:
            return json.dumps({"ok": False, "message": "No table specified."})
        db_type = _db_cfg().get("db_type", "Oracle").lower()
        if "postgres" in db_type:
            from insp_pg import insp_pg_create_one_table
            ok, msg = insp_pg_create_one_table(table_name)
        else:
            from insp_oracle import insp_create_one_table
            ok, msg = insp_create_one_table(table_name)
        return json.dumps({"ok": ok, "message": msg})
    except Exception as e:
        return json.dumps({"ok": False, "message": str(e)[:200]})


def api_insp_config_save(raw):
    try:
        data = json.loads(raw)
        cfg = _load_insp_config()
        if "enabled" in data:
            cfg["enabled"] = bool(data["enabled"])
        if "log_retention_days" in data:
            cfg["log_retention_days"] = max(1, int(data["log_retention_days"]))
        if "retention_days" in data:
            cfg["retention_days"] = max(1, int(data["retention_days"]))
        if "pg_db" in data:
            pg = data["pg_db"]
            if "pg_db" not in cfg:
                cfg["pg_db"] = {}
            for k in ("ip", "port", "sid", "user", "password"):
                if k in pg:
                    cfg["pg_db"][k] = str(pg[k])
        _save_insp_config(cfg)
        return json.dumps({"ok": True})
    except Exception as e:
        return json.dumps({"ok": False, "message": str(e)})


def api_insp_config_load():
    return json.dumps(_load_insp_config())


def page_history_config():
    from db_utils import _db_cfg as _cfg_db
    _is_pg_repo = 'postgres' in _cfg_db().get('db_type', 'Oracle').lower()
    cfg = _load_insp_config()
    b = _UTILS_BASE

    tbl_init = cfg.get("tables_initialized", False)
    enabled  = cfg.get("enabled", False)
    ret_days = cfg.get("retention_days", 31)
    log_ret_days = cfg.get("log_retention_days", 10)
    pg_db    = cfg.get("pg_db", {})

    body = ''.join([
        '<p class="page-title" style="margin-bottom:24px;">History Configuration</p>',

        # Card 1: Table Initialization
        '<div class="card" style="border:1px solid #E2E8F0;">',
        '<div class="card-title" style="background:#ECF0F7;margin:-24px -24px 20px;'
        'padding:14px 24px;border-radius:14px 14px 0 0;border-bottom:1px solid #D8DEE8;">'
        'Table Initialization</div>',
        '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">',
        '<span id="init-result" style="font-size:.82rem;margin-right:8px;"></span>',
        '<button id="btn-init" onclick="initTables()" style="padding:8px 20px;border-radius:8px;border:1px solid #6366F1;background:transparent;color:#6366F1;font-size:.82rem;font-weight:600;cursor:pointer;">Create Tables</button>',
        '<button id="btn-drop" onclick="dropTables()" style="padding:8px 20px;border-radius:8px;border:1px solid #EF4444;background:transparent;color:#EF4444;font-size:.82rem;font-weight:600;cursor:pointer;">Drop Tables</button>',

        '</div></div>',

        # Card 2: Collection Settings
        '<div class="card" style="border:1px solid #E2E8F0;">',
        '<div class="card-title" style="background:#ECF0F7;margin:-24px -24px 20px;'
        'padding:14px 24px;border-radius:14px 14px 0 0;border-bottom:1px solid #D8DEE8;">'
        'Collection Settings</div>',

        # Scheduler toggle
        '<div style="display:flex;align-items:center;gap:14px;margin-bottom:20px;">',
        '<span style="font-size:.85rem;font-weight:600;color:#475569;">Data Collection</span>',
        '<label style="position:relative;display:inline-block;width:48px;height:26px;cursor:pointer;">',
        '<input type="checkbox" id="chk-enabled"',
        ' checked' if enabled else '',
        ' onchange="updateToggleLabel()"'
        ' style="opacity:0;width:0;height:0;">',
        '<span id="toggle-track" style="position:absolute;inset:0;border-radius:13px;transition:all .2s;',
        'background:#6366F1;"' if enabled else 'background:#CBD5E1;"',
        '></span>',
        '<span id="toggle-knob" style="position:absolute;top:3px;width:20px;height:20px;'
        'border-radius:50%;background:#fff;transition:all .2s;box-shadow:0 1px 3px rgba(0,0,0,.2);',
        'left:25px;"' if enabled else 'left:3px;"',
        '></span>',
        '</label>',
        '<span id="toggle-label" style="font-size:.82rem;font-weight:600;',
        'color:#6366F1;"' if enabled else 'color:#94A3B8;"',
        '>' + ('ON' if enabled else 'OFF') + '</span>',
        '</div>',

        # Retention days
        '<div style="display:flex;align-items:center;gap:14px;margin-bottom:20px;">',
        '<span style="font-size:.85rem;font-weight:600;color:#475569;">Retention Period</span>',
        '<input type="number" id="inp-retention" value="%d"' % ret_days,
        ' min="1" max="365" style="width:80px;padding:8px 12px;border-radius:8px;'
        'border:1px solid #B0BAC9;background:#fff;color:#0F172A;font-size:.88rem;text-align:center;">',
        '<span style="font-size:.82rem;color:#64748B;">days</span>',
        '</div>',
        '<div style="display:flex;align-items:center;gap:14px;margin-bottom:0;">',
        '<span style="font-size:.85rem;font-weight:600;color:#475569;">Log Retention Period</span>',
        '<input type="number" id="inp-log-retention" value="%d"' % log_ret_days,
        ' min="1" max="365" style="width:80px;padding:8px 12px;border-radius:8px;'
        'border:1px solid #B0BAC9;background:#fff;color:#0F172A;font-size:.88rem;text-align:center;">',
        '<span style="font-size:.82rem;color:#64748B;">days (IH log files)</span>',
        '</div>',

        # Save button
        '<div style="display:flex;justify-content:flex-end;gap:10px;">',
        '<button onclick="saveConfig()" style="padding:10px 32px;border-radius:10px;'
        'border:none;background:#6366F1;color:#fff;font-size:.92rem;font-weight:600;'
        'cursor:pointer;box-shadow:0 4px 14px rgba(99,102,241,.35);transition:all .15s;"'
        '>Save</button>',
        '</div>',
        '<span id="save-result" style="font-size:.82rem;display:block;margin-top:10px;text-align:right;"></span>',
        '</div>',

        # Card 3: Collection Schedule Info
        '<div class="card" style="border:1px solid #E2E8F0;">',
        '<div class="card-title" style="background:#ECF0F7;margin:-24px -24px 20px;'
        'padding:14px 24px;border-radius:14px 14px 0 0;border-bottom:1px solid #D8DEE8;">'
        'Collection Schedule</div>',
        '<div style="overflow-x:auto;border:1px solid #E5E7EB;border-radius:10px;">',
        '<table style="width:100%;border-collapse:collapse;font-size:.84rem;" id="sched-tbl">',
        '<thead><tr style="background:#ECF0F7;">'
        '<th style="text-align:center;padding:10px 14px;color:#5F6B80;font-size:.72rem;'
        'font-weight:700;text-transform:uppercase;border-bottom:1px solid #D8DEE8;">수집지표</th>'
        '<th style="text-align:center;padding:10px 14px;color:#5F6B80;font-size:.72rem;'
        'font-weight:700;text-transform:uppercase;border-bottom:1px solid #D8DEE8;">수집주기</th>'
        '<th style="text-align:center;padding:10px 14px;color:#5F6B80;font-size:.72rem;'
        'font-weight:700;text-transform:uppercase;border-bottom:1px solid #D8DEE8;">수집테이블</th>'
        '<th style="text-align:center;padding:10px 14px;color:#5F6B80;font-size:.72rem;'
        'font-weight:700;text-transform:uppercase;border-bottom:1px solid #D8DEE8;">생성상태</th>'
        '</tr></thead><tbody id="sched-body">',
        '</tbody></table></div></div>',

        # JS
'<script>',
        'var _base="' + b + '";',
        'var _schedRows=['
        '["CPU / Memory","1분마다","INSP_OS_HISTORY"],'
        '["Qcnt (Connection)","1분마다","INSP_QCNT_HISTORY"],'
        '["Heap (JVM)","1분마다","INSP_HEAP_HISTORY"],'
        '["Service Status","1시간마다 (:00)","INSP_SERVICE_HISTORY"],'
        '["' + ('Disk' if _is_pg_repo else 'Tablespace') + '","매일 23:50","INSP_TBS_HISTORY"],'
        '["Summary (10Min)","10분마다 (:05, :15, ...)","INSP_SUMMARY_HISTORY"],'
        '["Summary (1Hour)","1시간마다 (:30)","INSP_SUMMARY_HISTORY"]'
        '];',
        """function loadScheduleStatus(){
  fetch(_base+'/api/insp-table-status').then(function(r){return r.json();}).then(function(d){
    if(!d.ok)return;
    var tb=document.getElementById('sched-body');tb.innerHTML='';
    _schedRows.forEach(function(row){
      var tbl=row[2];var exists=d.tables[tbl]||false;
      var stHtml;
      if(exists){stHtml='<span style="padding:4px 14px;border-radius:6px;border:1px solid #22c55e;background:rgba(34,197,94,.08);color:#22c55e;font-size:.75rem;font-weight:600;display:inline-block;">OK</span>';}
      else{stHtml='<button onclick="createOneTable(this,\\''+tbl+'\\')" style="padding:4px 14px;border-radius:6px;border:1px solid #6366F1;background:rgba(99,102,241,.08);color:#6366F1;font-size:.75rem;font-weight:600;cursor:pointer;">Create</button>';}
      tb.innerHTML+='<tr style="border-bottom:1px solid #F1F5F9;">'
        +'<td style="text-align:center;padding:10px 14px;">'+row[0]+'</td>'
        +'<td style="text-align:center;padding:10px 14px;">'+row[1]+'</td>'
        +'<td style="text-align:center;padding:10px 14px;font-size:.78rem;">'+tbl+'</td>'
        +'<td style="text-align:center;padding:10px 14px;">'+stHtml+'</td></tr>';
    });
  });
}
function createOneTable(btn,tbl){
  btn.disabled=true;btn.textContent='Creating...';
  fetch(_base+'/api/insp-create-one-table',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({table:tbl})})
  .then(function(r){return r.json();}).then(function(d){
    if(d.ok){btn.outerHTML='<span style="padding:4px 14px;border-radius:6px;border:1px solid #22c55e;background:rgba(34,197,94,.08);color:#22c55e;font-size:.75rem;font-weight:600;display:inline-block;">OK</span>';loadScheduleStatus();}
    else{btn.textContent='Error';btn.style.borderColor='#ef4444';btn.style.color='#ef4444';
      alert(d.message);setTimeout(function(){btn.textContent='Create';btn.disabled=false;
      btn.style.borderColor='#6366F1';btn.style.color='#6366F1';},2000);}
  });
}
loadScheduleStatus();
function updateToggleLabel(){
  var c=document.getElementById('chk-enabled').checked;
  document.getElementById('toggle-track').style.background=c?'#6366F1':'#CBD5E1';
  document.getElementById('toggle-knob').style.left=c?'25px':'3px';
  var lbl=document.getElementById('toggle-label');
  lbl.textContent=c?'ON':'OFF';lbl.style.color=c?'#6366F1':'#94A3B8';
}
function _getPgDb(){
  var f=document.getElementById('pg-db-form');
  if(!f)return null;
  return {
    ip:document.getElementById('pg-ip').value,
    port:document.getElementById('pg-port').value,
    sid:document.getElementById('pg-sid').value,
    user:document.getElementById('pg-user').value,
    password:document.getElementById('pg-pass').value
  };
}
function savePgDb(){
  var pgdb=_getPgDb();if(!pgdb)return;
  var btn=document.getElementById('btn-pgdb');
  var res=document.getElementById('pgdb-result');
  btn.textContent='Saving...';
  fetch(_base+'/api/insp-config-save',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({pg_db:pgdb,pg_schema:document.getElementById('pg-schema')?document.getElementById('pg-schema').value:'insp'})})
  .then(function(r){return r.json();})
  .then(function(d){
    btn.textContent='Save DB Info';
    if(d.ok){res.style.color='#15803D';res.textContent='Saved.';loadScheduleStatus();}
    else{res.style.color='#EF4444';res.textContent=d.message||'Failed.';}
    setTimeout(function(){res.textContent='';},3000);
  }).catch(function(){btn.textContent='Save DB Info';res.style.color='#EF4444';res.textContent='Request failed';});
}
function _savePgDbThen(callback){
  var pgdb=_getPgDb();
  if(!pgdb){callback();return;}
  fetch(_base+'/api/insp-config-save',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({pg_db:pgdb,pg_schema:document.getElementById('pg-schema')?document.getElementById('pg-schema').value:'insp'})})
  .then(function(){callback();})
  .catch(function(){callback();});
}
function initTables(){
  var btn=document.getElementById('btn-init');
  var res=document.getElementById('init-result');
  btn.textContent='Creating...';btn.style.opacity='.6';
  fetch(_base+'/api/insp-init-tables',{method:'POST'})
  .then(function(r){return r.json();})
  .then(function(d){
    btn.style.opacity='1';
    if(d.ok){loadScheduleStatus();alert('INSP_ \ud14c\uc774\ube14 \uc0dd\uc131 \uc644\ub8cc\\n\\n'+d.message);location.reload();}
    else{btn.textContent='Create Tables';btn.style.opacity='1';alert('\uc624\ub958: '+(d.message||'Failed'));}
  }).catch(function(){btn.textContent='Create Tables';btn.style.opacity='1';});
}
function dropTables(){
  if(!confirm('INSP_ 테이블을 모두 삭제하시겠습니까?\\n수집된 모든 히스토리 데이터가 삭제됩니다.'))return;
  var res=document.getElementById('init-result');
  fetch(_base+'/api/insp-drop-tables',{method:'POST'})
  .then(function(r){return r.json();})
  .then(function(d){
    if(d.ok){
      document.getElementById('chk-enabled').checked=false;updateToggleLabel();
      loadScheduleStatus();
      alert('INSP_ \ud14c\uc774\ube14 \uc0ad\uc81c \uc644\ub8cc\\n\\n'+d.message);
      location.reload();
    }else{alert('\uc624\ub958: '+(d.message||'Failed'));}
  }).catch(function(){res.style.color='#EF4444';res.textContent='Request failed';});
}
function saveConfig(){
  var res=document.getElementById('save-result');
  var data={enabled:document.getElementById('chk-enabled').checked,
    retention_days:parseInt(document.getElementById('inp-retention').value)||31,
    log_retention_days:parseInt(document.getElementById('inp-log-retention').value)||10};
  fetch(_base+'/api/insp-config-save',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})
  .then(function(r){return r.json();})
  .then(function(d){
    if(d.ok){res.style.color='#15803D';res.textContent='Settings saved.';}
    else{res.style.color='#EF4444';res.textContent=d.message||'Save failed.';}
    setTimeout(function(){res.textContent='';},3000);
  }).catch(function(){res.style.color='#EF4444';res.textContent='Request failed';});
}""",
        '</script>',
    ])
    return _history_page(body, active="history_config")
