# -*- coding: utf-8 -*-
"""History detail views: OS (CPU/Memory), Disk (TBS), Process (Service Status)."""
import json
import os
import sys
from datetime import datetime
from decimal import Decimal

# bundled drivers (Labs/drivers, Labs 공용)
_LABS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import glob as _glob
_py3_sites = _glob.glob(os.path.join(_LABS_DIR, 'drivers', 'python3', 'lib', 'python3.*', 'site-packages'))
if _py3_sites and _py3_sites[0] not in sys.path:
    sys.path.insert(0, _py3_sites[0])
del _glob, _py3_sites, _LABS_DIR

from html_helpers import _ts, _UTILS_BASE, _page_title_html, _HELP, _HELP_JS


def _insp_table_exists(table_name):
    """Check if a specific INSP table exists in the DB."""
    try:
        if _is_pg_repo():
            from insp_pg import insp_pg_check_each_table
            status = insp_pg_check_each_table()
            return status.get(table_name.lower(), False)
        else:
            from insp_oracle import insp_check_each_table
            status = insp_check_each_table()
            return status.get(table_name.upper(), False)
    except Exception:
        return False


def _table_missing_html(table_name):
    """Return HTML warning when INSP table doesn't exist."""
    return (
        '<div style="text-align:center;padding:60px 20px;">'
        '<div style="font-size:2rem;margin-bottom:16px;">&#9888;</div>'
        '<div style="font-size:1rem;font-weight:700;color:#0F172A;margin-bottom:8px;">'
        '테이블이 존재하지 않습니다</div>'
        '<div style="font-size:.85rem;color:#64748B;margin-bottom:20px;">'
        '<code style="background:#F1F5F9;padding:2px 8px;border-radius:4px;font-size:.82rem;">'
        + table_name.upper() + '</code> 테이블이 생성되지 않았습니다.</div>'
        '<div style="font-size:.85rem;color:#64748B;">'
        '<a href="' + _UTILS_BASE + '/config" '
        'style="color:#6366F1;font-weight:600;text-decoration:none;">'
        'Configuration</a> 에서 테이블을 생성해 주세요.</div>'
        '</div>'
    )


def _is_pg_repo():
    from db_utils import _db_cfg
    return 'postgres' in _db_cfg().get('db_type', 'Oracle').lower()


def _insp_conn():
    if _is_pg_repo():
        from insp_pg import _insp_pg_connect
        return _insp_pg_connect()
    from insp_oracle import _insp_connect
    return _insp_connect()


def _safe(v):
    if v is None: return None
    if isinstance(v, Decimal): return float(v)
    if isinstance(v, datetime): return v.strftime('%Y-%m-%d %H:%M:%S')
    return v


def _qs(path):
    params = {}
    if '?' in path:
        for p in path.split('?', 1)[1].split('&'):
            if '=' in p:
                k, v = p.split('=', 1)
                params[k] = v
    return params


# ── APIs ──────────────────────────────────────────────────────────────────────

def _proc_panel_html():
    """CPU/Memory 페이지 하단 공용 패널. 차트 클릭 시 그 분의 Top 20 프로세스 표시.
    제목 우측 좌/우 화살표 버튼으로 1분 단위 이동 (클릭 후 활성화)."""
    return (
        '<div class="proc-panel" id="proc-panel">'
        '<div class="proc-panel-hdr">'
        '<div class="proc-panel-title">Top 20 Processes</div>'
        '<div class="proc-panel-nav">'
        '<button id="proc-prev" type="button" onclick="_procShift(-1)" title="1분 이전" disabled>&#9664;</button>'
        '<div class="proc-panel-ts" id="proc-panel-ts">차트의 한 시점을 <b>클릭</b>하세요</div>'
        '<button id="proc-next" type="button" onclick="_procShift(1)" title="1분 이후" disabled>&#9654;</button>'
        '</div>'
        '</div>'
        '<div class="proc-panel-body" id="proc-panel-body">'
        '<div class="proc-panel-empty">'
        '클릭한 시점의 Top 20 프로세스 (cpu% / mem% 중 큰 쪽 기준) 가 여기에 표시됩니다.'
        '</div>'
        '</div>'
        '</div>'
    )


def _proc_panel_css():
    return ('<style>'
        '.proc-panel{margin-top:16px;border:1px solid #E2E8F0;border-radius:0;background:#fff;}'
        '.proc-panel-hdr{display:flex;align-items:center;justify-content:space-between;padding:10px 16px;'
        'border-bottom:1px solid #E2E8F0;background:#F8FAFC;}'
        '.proc-panel-title{font-size:.78rem;font-weight:700;color:#0F172A;letter-spacing:.02em;}'
        '.proc-panel-nav{display:flex;align-items:center;gap:8px;}'
        '.proc-panel-nav button{padding:3px 9px;border:1px solid #E2E8F0;border-radius:6px;'
        'background:#fff;color:#6366F1;font-size:.7rem;line-height:1;cursor:pointer;font-weight:700;'
        'transition:background .12s,border-color .12s,color .12s;}'
        '.proc-panel-nav button:hover:not(:disabled){background:#EEF2FF;border-color:#C7D2FE;}'
        '.proc-panel-nav button:disabled{opacity:.4;cursor:not-allowed;color:#94A3B8;}'
        '.proc-panel-ts{font-size:.76rem;color:#64748B;min-width:140px;text-align:center;}'
        '.proc-panel-ts b{font-weight:600;color:inherit;}'
        '.proc-panel-body{overflow-x:auto;}'
        '.proc-panel-empty{padding:36px 20px;text-align:center;color:#94A3B8;font-size:.82rem;}'
        '.proc-panel-loading{padding:24px;text-align:center;color:#6366F1;font-size:.82rem;}'
        '.proc-tbl{width:100%;border-collapse:collapse;font-size:.78rem;}'
        '.proc-tbl thead th{position:sticky;top:0;background:#F1F5F9;color:#475569;font-weight:600;'
        'text-align:left;padding:8px 10px;border-bottom:1px solid #E2E8F0;font-size:.72rem;'
        'text-transform:uppercase;letter-spacing:.04em;white-space:nowrap;}'
        '.proc-tbl tbody td{padding:6px 10px;border-bottom:1px solid #F1F5F9;color:#334155;'
        'white-space:nowrap;}'
        '.proc-tbl tbody tr:hover{background:#F8FAFC;}'
        '.proc-tbl .num{text-align:right;font-variant-numeric:tabular-nums;}'
        '.proc-tbl .pct-hi{color:#DC2626;font-weight:600;}'
        '.proc-tbl .pct-mid{color:#D97706;font-weight:600;}'
        '.proc-tbl .args{max-width:380px;overflow:hidden;text-overflow:ellipsis;'
        'font-family:"Geist Mono","Consolas",monospace;font-size:.72rem;color:#64748B;}'
        '</style>')


def _proc_panel_js():
    """CPU/Memory 페이지에서 _loadProcAt(ts) 를 차트 단순 클릭(i1===i2) 시 호출."""
    return ('<script>'
        'function _procFmtKB(kb){'
        '  if(kb>=1048576)return (kb/1048576).toFixed(1)+" GB";'
        '  if(kb>=1024)return (kb/1024).toFixed(1)+" MB";'
        '  return kb+" KB";'
        '}'
        'function _procEsc(s){return String(s==null?"":s).replace(/[&<>\\"\\\']/g,function(c){'
        '  return ({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","\\\'":"&#39;"})[c];});}'
        'function _procPctCls(p){if(p>=50)return "pct-hi";if(p>=20)return "pct-mid";return "";}'
        'window._procCurrentAt=null;'
        'window._procShift=function(delta){'
        '  if(!window._procCurrentAt)return;'
        '  var m=window._procCurrentAt.match(/^(\\d{4})-(\\d{2})-(\\d{2}) (\\d{2}):(\\d{2})$/);'
        '  if(!m)return;'
        '  var d=new Date(+m[1],+m[2]-1,+m[3],+m[4],+m[5]);'
        '  d.setMinutes(d.getMinutes()+delta);'
        '  var pad=function(n){return String(n).padStart(2,"0");};'
        '  var ts=d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate())+" "+pad(d.getHours())+":"+pad(d.getMinutes());'
        '  window._loadProcAt(ts);'
        '};'
        'window._loadProcAt=function(ts){'
        '  var tsEl=document.getElementById("proc-panel-ts");'
        '  var bodyEl=document.getElementById("proc-panel-body");'
        '  if(!tsEl||!bodyEl)return;'
        '  var atKey=ts.substr(0,16);'  # YYYY-MM-DD HH:MM
        '  window._procCurrentAt=atKey;'
        '  var prevBtn=document.getElementById("proc-prev");'
        '  var nextBtn=document.getElementById("proc-next");'
        '  if(prevBtn)prevBtn.disabled=false;'
        '  if(nextBtn)nextBtn.disabled=false;'
        # 차트의 lock-line 갱신 (현재 페이지에 해당하는 draw 함수만 정의됨)
        '  try{ if(typeof _cpuDraw==="function") _cpuDraw(-1); }catch(e){}'
        '  try{ if(typeof _memDraw==="function") _memDraw(-1); }catch(e){}'
        '  tsEl.innerHTML="<b>"+_procEsc(atKey)+"</b>";'
        '  bodyEl.innerHTML="<div class=\\"proc-panel-loading\\">불러오는 중...</div>";'
        '  fetch(_apiBase+"/api/history-proc?at="+encodeURIComponent(atKey)+(window._procSortBy?"&sort="+encodeURIComponent(window._procSortBy):""))'
        '  .then(function(r){return r.json();})'
        '  .then(function(d){'
        '    if(!d.ok){bodyEl.innerHTML="<div class=\\"proc-panel-empty\\">"+_procEsc(d.error||"오류")+"</div>";return;}'
        '    if(!d.rows||!d.rows.length){bodyEl.innerHTML="<div class=\\"proc-panel-empty\\">해당 시점 데이터 없음 (수집 전이거나 분 단위 미일치)</div>";return;}'
        '    var html="<table class=\\"proc-tbl\\"><thead><tr>"+'
        '      "<th>PID</th><th>USER</th>"+'
        '      "<th class=\\"num\\">CPU%</th><th class=\\"num\\">MEM%</th>"+'
        '      "<th class=\\"num\\">RSS</th><th class=\\"num\\">VSZ</th>"+'
        '      "<th class=\\"num\\">THR</th><th>ETIME</th>"+'
        '      "<th>COMM</th><th>ARGS</th>"+'
        '      "</tr></thead><tbody>";'
        '    d.rows.forEach(function(r){'
        '      html+="<tr>"+'
        '        "<td class=\\"num\\">"+_procEsc(r.pid)+"</td>"+'
        '        "<td>"+_procEsc(r.user)+"</td>"+'
        '        "<td class=\\"num "+_procPctCls(r.cpu_pct)+"\\">"+r.cpu_pct.toFixed(1)+"</td>"+'
        '        "<td class=\\"num "+_procPctCls(r.mem_pct)+"\\">"+r.mem_pct.toFixed(1)+"</td>"+'
        '        "<td class=\\"num\\">"+_procFmtKB(r.rss_kb)+"</td>"+'
        '        "<td class=\\"num\\">"+_procFmtKB(r.vsz_kb)+"</td>"+'
        '        "<td class=\\"num\\">"+r.threads+"</td>"+'
        '        "<td>"+_procEsc(r.etime)+"</td>"+'
        '        "<td>"+_procEsc(r.comm)+"</td>"+'
        '        "<td class=\\"args\\" title=\\""+_procEsc(r.args)+"\\">"+_procEsc(r.args)+"</td>"+'
        '      "</tr>";'
        '    });'
        '    html+="</tbody></table>";'
        '    bodyEl.innerHTML=html;'
        '  }).catch(function(e){bodyEl.innerHTML="<div class=\\"proc-panel-empty\\">요청 실패</div>";});'
        '};'
        '</script>')


def api_history_proc(path):
    """INSP_PROC_HISTORY 에서 특정 분의 top 20 프로세스 반환.
    query: ?at=YYYY-MM-DD%20HH:MM (URL-encoded space) 또는 +
           &sort=cpu  → cpu_pct DESC
           &sort=mem  → mem_pct DESC
           (default = cpu)
    응답 ok=true, rows = [{pid,user,cpu_pct,mem_pct,rss_kb,vsz_kb,threads,etime,comm,args}, ...]"""
    p = _qs(path)
    raw = p.get('at', '')
    try:
        from urllib.parse import unquote_plus
        raw = unquote_plus(raw)
    except Exception:
        raw = raw.replace('+', ' ').replace('%20', ' ')
    if len(raw) < 16:
        return json.dumps({"ok": False, "error": "missing 'at' (YYYY-MM-DD HH:MM)"})
    at_min = raw[:16] + ':00'  # 분 단위 — 초는 00 으로 통일 (수집측도 :00 으로 저장)

    sort = (p.get('sort', 'cpu') or 'cpu').lower()
    if sort == 'mem':
        order_pg  = "ORDER BY mem_pct DESC, cpu_pct DESC"
        order_ora = "ORDER BY MEM_PCT DESC, CPU_PCT DESC"
    else:
        order_pg  = "ORDER BY cpu_pct DESC, mem_pct DESC"
        order_ora = "ORDER BY CPU_PCT DESC, MEM_PCT DESC"

    if not _insp_table_exists('insp_proc_history'):
        return json.dumps({"ok": False, "error": "INSP_PROC_HISTORY 미생성"})

    is_pg = _is_pg_repo()
    conn = _insp_conn()
    if not conn:
        return json.dumps({"ok": False, "error": "DB 연결 실패"})
    try:
        cur = conn.cursor()
        if is_pg:
            cur.execute(
                "SELECT pid, os_user, cpu_pct, mem_pct, rss_kb, vsz_kb, threads, etime, comm, args "
                "FROM insp_proc_history "
                "WHERE collected_at = to_timestamp(%s, 'YYYY-MM-DD HH24:MI:SS') "
                + order_pg,
                (at_min,))
        else:
            cur.execute(
                "SELECT PID, OS_USER, CPU_PCT, MEM_PCT, RSS_KB, VSZ_KB, THREADS, ETIME, COMM, ARGS "
                "FROM INSP_PROC_HISTORY "
                "WHERE COLLECTED_AT = TO_TIMESTAMP(:1, 'YYYY-MM-DD HH24:MI:SS') "
                + order_ora,
                (at_min,))
        rows = []
        for r in cur.fetchall():
            rows.append({
                "pid":     _safe(r[0]),
                "user":    _safe(r[1]) or '',
                "cpu_pct": float(r[2] or 0),
                "mem_pct": float(r[3] or 0),
                "rss_kb":  int(r[4] or 0),
                "vsz_kb":  int(r[5] or 0),
                "threads": int(r[6] or 0),
                "etime":   _safe(r[7]) or '',
                "comm":    _safe(r[8]) or '',
                "args":    _safe(r[9]) or '',
            })
        cur.close(); conn.close()
        return json.dumps({"ok": True, "at": raw[:16], "rows": rows})
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return json.dumps({"ok": False, "error": str(e)})


def api_history_os(path):
    p = _qs(path)
    d = p.get('date', datetime.now().strftime('%Y-%m-%d'))
    t1 = p.get('from', '00:00')
    t2 = p.get('to', '23:59')
    start = d + ' ' + t1 + ':00'
    end = d + ' ' + t2 + ':59'
    try:
        conn = _insp_conn()
        cur = conn.cursor()
        if _is_pg_repo():
            cur.execute(
                "SELECT to_char(collected_at,'YYYY-MM-DD HH24:MI:SS'),"
                "cpu_percent,cpu_user,cpu_system,cpu_iowait,"
                "mem_total_gb,mem_used_gb,mem_free_gb,mem_percent "
                "FROM insp_os_history "
                "WHERE collected_at>=to_timestamp(%s,'YYYY-MM-DD HH24:MI:SS') "
                "AND collected_at<=to_timestamp(%s,'YYYY-MM-DD HH24:MI:SS') "
                "ORDER BY collected_at", (start, end))
        else:
            cur.execute(
                "SELECT TO_CHAR(COLLECTED_AT,'YYYY-MM-DD HH24:MI:SS'),"
                "CPU_PERCENT,CPU_USER,CPU_SYSTEM,CPU_IOWAIT,"
                "MEM_TOTAL_GB,MEM_USED_GB,MEM_FREE_GB,MEM_PERCENT "
                "FROM INSP_OS_HISTORY "
                "WHERE COLLECTED_AT>=TO_TIMESTAMP(:1,'YYYY-MM-DD HH24:MI:SS') "
                "AND COLLECTED_AT<=TO_TIMESTAMP(:2,'YYYY-MM-DD HH24:MI:SS') "
                "ORDER BY COLLECTED_AT", (start, end))
        rows = []
        for r in cur.fetchall():
            rows.append({
                'ts': r[0], 'cpu_pct': _safe(r[1]), 'cpu_user': _safe(r[2]),
                'cpu_sys': _safe(r[3]), 'cpu_io': _safe(r[4]),
                'mem_total': _safe(r[5]), 'mem_used': _safe(r[6]),
                'mem_free': _safe(r[7]), 'mem_pct': _safe(r[8]),
            })
        cur.close(); conn.close()
        return json.dumps({'ok': True, 'data': rows, 'date': d, 'from': t1, 'to': t2})
    except Exception as e:
        return json.dumps({'ok': False, 'error': str(e)[:200]})


def api_history_tbs(path):
    p = _qs(path)
    d_from = p.get('from_date', datetime.now().strftime('%Y-%m-%d'))
    d_to = p.get('to_date', d_from)
    start = d_from + ' 00:00:00'
    end = d_to + ' 23:59:59'
    try:
        conn = _insp_conn()
        cur = conn.cursor()
        if _is_pg_repo():
            cur.execute(
                "SELECT to_char(collected_at,'YYYY-MM-DD HH24:MI:SS'),"
                "tbs_name,used_gb,total_gb,free_gb,used_percent,status "
                "FROM insp_tbs_history "
                "WHERE collected_at>=to_timestamp(%s,'YYYY-MM-DD HH24:MI:SS') "
                "AND collected_at<=to_timestamp(%s,'YYYY-MM-DD HH24:MI:SS') "
                "ORDER BY collected_at,tbs_name", (start, end))
        else:
            cur.execute(
                "SELECT TO_CHAR(COLLECTED_AT,'YYYY-MM-DD HH24:MI:SS'),"
                "TBS_NAME,USED_GB,TOTAL_GB,FREE_GB,USED_PERCENT,STATUS "
                "FROM INSP_TBS_HISTORY "
                "WHERE COLLECTED_AT>=TO_TIMESTAMP(:1,'YYYY-MM-DD HH24:MI:SS') "
                "AND COLLECTED_AT<=TO_TIMESTAMP(:2,'YYYY-MM-DD HH24:MI:SS') "
                "ORDER BY COLLECTED_AT,TBS_NAME", (start, end))
        rows = []
        for r in cur.fetchall():
            rows.append({
                'ts': r[0], 'name': r[1], 'used': _safe(r[2]),
                'total': _safe(r[3]), 'free': _safe(r[4]),
                'pct': _safe(r[5]), 'status': r[6],
            })
        cur.close(); conn.close()
        return json.dumps({'ok': True, 'data': rows})
    except Exception as e:
        return json.dumps({'ok': False, 'error': str(e)[:200]})


def api_history_heap(path):
    p = _qs(path)
    d = p.get('date', datetime.now().strftime('%Y-%m-%d'))
    t1 = p.get('from', '00:00')
    t2 = p.get('to', '23:59')
    start = d + ' ' + t1 + ':00'
    end = d + ' ' + t2 + ':59'
    try:
        conn = _insp_conn()
        cur = conn.cursor()
        if _is_pg_repo():
            cur.execute(
                "SELECT to_char(collected_at,'YYYY-MM-DD HH24:MI:SS'),"
                "service_name,heap_used_mb,heap_alloc_mb,heap_max_mb "
                "FROM insp_heap_history "
                "WHERE collected_at>=to_timestamp(%s,'YYYY-MM-DD HH24:MI:SS') "
                "AND collected_at<=to_timestamp(%s,'YYYY-MM-DD HH24:MI:SS') "
                "ORDER BY collected_at,service_name", (start, end))
        else:
            cur.execute(
                "SELECT TO_CHAR(COLLECTED_AT,'YYYY-MM-DD HH24:MI:SS'),"
                "SERVICE_NAME,HEAP_USED_MB,HEAP_ALLOC_MB,HEAP_MAX_MB "
                "FROM INSP_HEAP_HISTORY "
                "WHERE COLLECTED_AT>=TO_TIMESTAMP(:1,'YYYY-MM-DD HH24:MI:SS') "
                "AND COLLECTED_AT<=TO_TIMESTAMP(:2,'YYYY-MM-DD HH24:MI:SS') "
                "ORDER BY COLLECTED_AT,SERVICE_NAME", (start, end))
        svc_map = {}
        for r in cur.fetchall():
            sname = r[1]
            if sname not in svc_map:
                svc_map[sname] = []
            svc_map[sname].append({
                'ts': r[0], 'used': _safe(r[2]), 'alloc': _safe(r[3]), 'max': _safe(r[4]),
            })
        cur.close(); conn.close()
        services = sorted(svc_map.keys())
        return json.dumps({'ok': True, 'services': services, 'data': svc_map, 'date': d})
    except Exception as e:
        return json.dumps({'ok': False, 'error': str(e)[:200]})


def api_history_qcnt(path):
    p = _qs(path)
    d = p.get('date', datetime.now().strftime('%Y-%m-%d'))
    t1 = p.get('from', '00:00')
    t2 = p.get('to', '23:59')
    start = d + ' ' + t1 + ':00'
    end = d + ' ' + t2 + ':59'
    try:
        conn = _insp_conn()
        cur = conn.cursor()
        if _is_pg_repo():
            cur.execute(
                "SELECT to_char(collected_at,'YYYY-MM-DD HH24:MI:SS'),"
                "service_name,act,total,max_conn,qcnt "
                "FROM insp_qcnt_history "
                "WHERE collected_at>=to_timestamp(%s,'YYYY-MM-DD HH24:MI:SS') "
                "AND collected_at<=to_timestamp(%s,'YYYY-MM-DD HH24:MI:SS') "
                "ORDER BY collected_at,service_name", (start, end))
        else:
            cur.execute(
                "SELECT TO_CHAR(COLLECTED_AT,'YYYY-MM-DD HH24:MI:SS'),"
                "SERVICE_NAME,ACT,TOTAL,MAX_CONN,QCNT "
                "FROM INSP_QCNT_HISTORY "
                "WHERE COLLECTED_AT>=TO_TIMESTAMP(:1,'YYYY-MM-DD HH24:MI:SS') "
                "AND COLLECTED_AT<=TO_TIMESTAMP(:2,'YYYY-MM-DD HH24:MI:SS') "
                "ORDER BY COLLECTED_AT,SERVICE_NAME", (start, end))
        svc_map = {}
        for r in cur.fetchall():
            sname = r[1]
            if sname not in svc_map:
                svc_map[sname] = []
            svc_map[sname].append({
                'ts': r[0], 'act': _safe(r[2]), 'total': _safe(r[3]),
                'max': _safe(r[4]), 'qcnt': _safe(r[5]),
            })
        cur.close(); conn.close()
        services = sorted(svc_map.keys())
        return json.dumps({'ok': True, 'services': services, 'data': svc_map, 'date': d})
    except Exception as e:
        return json.dumps({'ok': False, 'error': str(e)[:200]})


def _configured_service_names():
    """Return ordered list of service names based on current configuration."""
    from service_config import load_service_config
    svc = load_service_config()
    svcs = svc.get("services", {})
    names = []
    if svcs.get("dgserver_m", ""):
        names.append("DGServer_M")
    for i, dgs_home in enumerate(svcs.get("dgserver_s", [])):
        if dgs_home:
            names.append("DGServer_S%d" % (i + 1))
    names.append("PlatformJS")
    names.append("Repository DB")
    return names


def api_history_service(path):
    p = _qs(path)
    d = p.get('date', datetime.now().strftime('%Y-%m-%d'))
    start = d + ' 00:00:00'
    end = d + ' 23:59:59'
    try:
        conn = _insp_conn()
        cur = conn.cursor()
        if _is_pg_repo():
            cur.execute(
                "SELECT to_char(collected_at,'YYYY-MM-DD HH24:MI:SS'),"
                "service_name,status "
                "FROM insp_service_history "
                "WHERE collected_at>=to_timestamp(%s,'YYYY-MM-DD HH24:MI:SS') "
                "AND collected_at<=to_timestamp(%s,'YYYY-MM-DD HH24:MI:SS') "
                "ORDER BY collected_at,service_name", (start, end))
        else:
            cur.execute(
                "SELECT TO_CHAR(COLLECTED_AT,'YYYY-MM-DD HH24:MI:SS'),"
                "SERVICE_NAME,STATUS "
                "FROM INSP_SERVICE_HISTORY "
                "WHERE COLLECTED_AT>=TO_TIMESTAMP(:1,'YYYY-MM-DD HH24:MI:SS') "
                "AND COLLECTED_AT<=TO_TIMESTAMP(:2,'YYYY-MM-DD HH24:MI:SS') "
                "ORDER BY COLLECTED_AT,SERVICE_NAME", (start, end))
        svc_map = {}
        for r in cur.fetchall():
            sname = r[1]
            if sname not in svc_map:
                svc_map[sname] = []
            svc_map[sname].append({'ts': r[0], 's': r[2]})
        cur.close(); conn.close()
        cfg_names = _configured_service_names()
        services = [s for s in cfg_names if s in svc_map]
        filtered_data = {s: svc_map[s] for s in services}
        return json.dumps({'ok': True, 'services': services, 'data': filtered_data, 'date': d})
    except Exception as e:
        return json.dumps({'ok': False, 'error': str(e)[:200]})


# ── Page helpers ──────────────────────────────────────────────────────────────

def _controls_bar(date_only=False, default_date=''):
    dd = default_date or "'+new Date().toISOString().slice(0,10)+'"
    if date_only:
        return (
            '<div class="ctrl-bar">'
            '<label class="ctrl-lbl">Date</label>'
            '<input type="date" id="sel-date" class="ctrl-inp" value="' + dd + '">'
            '<button id="btn-query" class="ctrl-btn" onclick="doQuery()">Retrieve</button>'
            '</div>'
        )
    return (
        '<div class="ctrl-bar">'
        '<label class="ctrl-lbl">Date</label>'
        '<input type="date" id="sel-date" class="ctrl-inp">'
        '<label class="ctrl-lbl">From</label>'
        '<input type="time" id="sel-from" class="ctrl-inp" value="00:00">'
        '<label class="ctrl-lbl">To</label>'
        '<input type="time" id="sel-to" class="ctrl-inp" value="23:59">'
        '<button id="btn-query" class="ctrl-btn" onclick="doQuery()">Retrieve</button>'
        '</div>'
    )


def _controls_bar_range():
    return (
        '<div class="ctrl-bar">'
        '<label class="ctrl-lbl">From</label>'
        '<input type="date" id="sel-from-date" class="ctrl-inp">'
        '<label class="ctrl-lbl">To</label>'
        '<input type="date" id="sel-to-date" class="ctrl-inp">'
        '<button id="btn-query" class="ctrl-btn" onclick="doQuery()">Retrieve</button>'
        '</div>'
    )


def _view_css():
    return (
        '<script>'
        'function _shiftDateInput(id,dir){'
        '  var el=document.getElementById(id);if(!el)return;'
        '  var d=new Date(el.value+"T00:00:00");'
        '  d.setDate(d.getDate()+dir);'
        '  var p=function(n){return n<10?"0"+n:""+n;};'
        '  el.value=d.getFullYear()+"-"+p(d.getMonth()+1)+"-"+p(d.getDate());'
        '  el.dispatchEvent(new Event("change"));'
        '}'
        '</script>'
        '<style>'
        '.ctrl-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:20px;}'
        '.ctrl-lbl{font-size:.78rem;font-weight:600;color:var(--c-muted);}'
        '.ctrl-inp{background:var(--bg-card);border:1px solid var(--bd);border-radius:8px;'
        'padding:7px 12px;font-size:.82rem;color:var(--c-main);outline:none;}'
        '.ctrl-inp:focus{border-color:var(--c-accent);}'
        '.ctrl-btn{padding:8px 22px;background:#6366F1;border:none;border-radius:8px;'
        'color:#fff;font-size:.82rem;font-weight:600;cursor:pointer;transition:all .18s;}'
        '.ctrl-btn:hover{background:#4F46E5;}'
        # [DESIGN-A] border-radius:14px → 0, border var(--bd)(#E5E7EB) → #CBD5E1.
        '.chart-wrap{position:relative;background:var(--bg-card);border:1px solid #CBD5E1;'
        'border-radius:0;padding:20px;min-height:340px;}'
        '.chart-empty{text-align:center;color:var(--c-muted);font-size:.85rem;padding:60px 0;}'
        '.chart-legend{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:14px;}'
        '.legend-item{display:flex;align-items:center;gap:5px;font-size:.75rem;color:var(--c-muted);}'
        '.legend-dot{width:10px;height:10px;border-radius:3px;}'
        '.tbs-bar-wrap{margin-bottom:12px;}'
        '.tbs-label{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;}'
        '.tbs-name{font-size:.82rem;font-weight:600;color:var(--c-main);}'
        '.tbs-info{font-size:.72rem;color:var(--c-muted);}'
        '.tbs-track{height:22px;background:var(--bd);border-radius:6px;overflow:hidden;position:relative;}'
        '.tbs-fill{height:100%;border-radius:6px;transition:width .4s ease;}'
        '.tbs-pct{position:absolute;right:8px;top:50%;transform:translateY(-50%);'
        'font-size:.7rem;font-weight:700;color:var(--c-main);}'
        '.hm-grid{overflow-x:auto;}'
        '.hm-table{border-collapse:separate;border-spacing:0 4px;width:100%;}'
        '.hm-table th{font-size:.70rem;font-weight:700;color:#475569;padding:4px 1px;'
        'text-align:center;white-space:nowrap;border-bottom:1px solid var(--bd);}'
        '.hm-table td{padding:1px 1px;}'
        '.hm-cell{width:100%;height:26px;border-radius:4px;cursor:default;transition:opacity .12s;}'
        '.hm-cell:hover{opacity:.75;}'
        '.hm-svc{font-size:.8rem;font-weight:600;color:var(--c-main);padding:4px 6px 4px 4px;'
        'white-space:nowrap;text-align:left;}'
        '#svc-tt{display:none;position:fixed;z-index:9999;background:#ffffff;'
        'border:1px solid #E2E8F0;border-radius:10px;padding:10px 14px;'
        'box-shadow:0 8px 24px rgba(0,0,0,.12);pointer-events:none;min-width:160px;}'
        '#svc-tt .stt-svc{font-size:.82rem;font-weight:700;color:#0F172A;margin-bottom:6px;'
        'padding-bottom:6px;border-bottom:1px solid #F1F5F9;}'
        '#svc-tt .stt-row{display:flex;align-items:center;gap:8px;}'
        '#svc-tt .stt-dot{width:9px;height:9px;border-radius:2px;flex-shrink:0;}'
        '#svc-tt .stt-label{font-size:.78rem;color:#64748B;}'
        '#svc-tt .stt-val{margin-left:auto;font-size:.78rem;font-weight:700;}'
        '#chart-tooltip{display:none;position:fixed;z-index:999;background:var(--bg-card);'
        'border:1px solid var(--bd);border-radius:10px;padding:10px 14px;'
        'box-shadow:0 8px 24px rgba(0,0,0,.15);font-size:.78rem;pointer-events:none;'
        'max-width:240px;}'
        '</style>'
    )


# ── CPU Page (monitoring dashboard style — stacked area) ──────────────────────

def _cpu_chart_css():
    return '''<style>
/* [DESIGN-A] border-radius:14px → 0, border #E2E8F0 → #CBD5E1 (Inspector 톤). */
.cpu-panel{background:#ffffff;border:1px solid #CBD5E1;border-radius:0;overflow:hidden;}
.cpu-header{display:flex;align-items:center;justify-content:space-between;
  padding:14px 22px 10px;border-bottom:1px solid #F1F5F9;}
.cpu-header-left{display:flex;align-items:center;gap:12px;}
.cpu-title{font-size:.95rem;font-weight:700;color:#0F172A;letter-spacing:.01em;}
.cpu-range-info{display:flex;align-items:center;gap:6px;font-size:.78rem;color:#475569;
  font-weight:600;font-variant-numeric:tabular-nums;}
.cpu-range-info .ri-date{color:#0F172A;font-weight:700;}
.cpu-range-info .ri-time{color:#6366F1;font-weight:700;}
.cpu-range-info .ri-sep{color:#CBD5E1;margin:0 1px;}
.cpu-zoom-btn{display:inline-flex;align-items:center;gap:5px;padding:7px 16px;
  border-radius:8px;border:1px solid #E2E8F0;background:#F8FAFC;color:#64748B;
  font-size:.78rem;font-weight:600;cursor:pointer;transition:all .15s;user-select:none;}
.cpu-zoom-btn:hover{border-color:#6366F1;color:#6366F1;background:#EEF2FF;}
.cpu-search-bar{display:flex;align-items:center;
  gap:6px;padding:10px 22px;border-bottom:1px solid #F1F5F9;background:#FAFBFC;flex-wrap:wrap;}
.sb-group{display:flex;align-items:center;background:#fff;border:1px solid #E2E8F0;
  border-radius:8px;overflow:hidden;height:36px;transition:border-color .15s;}
.sb-group:focus-within{border-color:#6366F1;box-shadow:0 0 0 2px rgba(99,102,241,.08);}
.sb-group label{font-size:.72rem;font-weight:600;color:#94A3B8;padding:0 10px;
  white-space:nowrap;border-right:1px solid #F1F5F9;background:#FAFBFC;
  height:100%;display:flex;align-items:center;letter-spacing:.03em;}
.sb-group input{border:none;outline:none;padding:0 12px;font-size:.84rem;color:#0F172A;
  height:100%;background:transparent;min-width:0;font-variant-numeric:tabular-nums;
  font-family:inherit;font-weight:600;letter-spacing:.01em;cursor:pointer;}
.sb-group input[type=date]{width:140px;text-align:center;}
.sb-group input[type=date]::-webkit-calendar-picker-indicator{display:none;-webkit-appearance:none;}
.sb-group input[type=date]::-webkit-inner-spin-button{display:none;}
.sb-group input[type=date]::-webkit-clear-button{display:none;}
.sb-group input[type=time]{width:90px;}
.sb-group .sb-cal-btn{display:flex;align-items:center;justify-content:center;
  width:34px;height:100%;border:none;border-left:1px solid #F1F5F9;background:#FAFBFC;
  color:#94A3B8;cursor:pointer;transition:all .15s;flex-shrink:0;}
.sb-group .sb-cal-btn:hover{background:#EEF2FF;color:#6366F1;}
.sb-group .sb-cal-btn svg{width:15px;height:15px;}
.sb-sep{color:#CBD5E1;font-size:.8rem;font-weight:300;margin:0 2px;}
.sb-quick{display:flex;align-items:center;gap:4px;margin-left:4px;}
.sb-qbtn{padding:5px 10px;border-radius:6px;border:1px solid #E2E8F0;background:#fff;
  color:#64748B;font-size:.72rem;font-weight:600;cursor:pointer;transition:all .12s;
  white-space:nowrap;height:36px;display:flex;align-items:center;}
.sb-qbtn:hover{border-color:#6366F1;color:#6366F1;background:#EEF2FF;}
.sb-qbtn.active{border-color:#6366F1;background:#6366F1;color:#fff;}
.sb-go{padding:0 20px;background:#6366F1;border:none;border-radius:8px;
  color:#fff;font-size:.82rem;font-weight:700;cursor:pointer;transition:all .15s;
  height:36px;display:flex;align-items:center;gap:5px;margin-left:4px;letter-spacing:.02em;}
.sb-go:hover{background:#4F46E5;}
.sb-arrow{display:inline-flex;align-items:center;justify-content:center;
  width:36px;height:36px;border:1px solid #E2E8F0;background:#fff;border-radius:8px;
  color:#475569;cursor:pointer;transition:all .15s;font-size:1.2rem;font-weight:600;padding:0;
  line-height:1;}
.sb-arrow:hover{background:#EEF2FF;color:#6366F1;border-color:#C7D2FE;}
.sb-arrow:active{background:#E0E7FF;}
.sb-go svg{width:14px;height:14px;}
.cpu-body{display:flex;min-height:340px;}
.cpu-canvas-area{flex:1;padding:14px 8px 14px 14px;position:relative;min-width:0;}
.cpu-legend-panel{width:172px;flex-shrink:0;border-left:1px solid #F1F5F9;
  padding:18px 16px;display:flex;flex-direction:column;gap:6px;}
.cpu-leg-section{margin-bottom:6px;}
.cpu-leg-title{font-size:.63rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.1em;color:#94A3B8;margin-bottom:8px;}
.cpu-leg-item{display:flex;align-items:center;gap:8px;margin-bottom:5px;
  cursor:pointer;user-select:none;border-radius:4px;padding:2px 4px;margin-left:-4px;
  transition:opacity .15s;}
.cpu-leg-item:hover{background:rgba(99,102,241,.05);}
.cpu-leg-item.disabled{opacity:.35;}
.cpu-leg-item.disabled .cpu-leg-swatch{background:#CBD5E1!important;border-color:#CBD5E1!important;}
.cpu-leg-swatch{width:14px;height:10px;border-radius:2px;flex-shrink:0;transition:all .15s;}
.cpu-leg-label{font-size:.76rem;color:#475569;font-weight:500;}
.cpu-leg-value{margin-left:auto;font-size:.76rem;font-weight:700;color:#0F172A;
  font-variant-numeric:tabular-nums;min-width:44px;text-align:right;}
.cpu-leg-divider{border:none;border-top:1px solid #F1F5F9;margin:10px 0;}
.cpu-leg-total{display:flex;align-items:center;justify-content:space-between;
  margin-top:2px;padding:6px 0;}
.cpu-leg-total-label{font-size:.76rem;font-weight:700;color:#334155;}
.cpu-leg-total-val{font-size:.82rem;font-weight:800;color:#0F172A;
  font-variant-numeric:tabular-nums;}
#cpu-tooltip{display:none;position:fixed;z-index:9999;background:#ffffff;
  border:1px solid #E2E8F0;border-radius:10px;padding:12px 16px;
  box-shadow:0 12px 32px rgba(0,0,0,.14);font-size:.78rem;pointer-events:none;
  min-width:185px;}
#cpu-tooltip .tt-time{font-size:.82rem;font-weight:700;color:#0F172A;margin-bottom:6px;
  padding-bottom:6px;border-bottom:1px solid #F1F5F9;}
#cpu-tooltip .tt-row{display:flex;align-items:center;gap:6px;margin-bottom:3px;}
#cpu-tooltip .tt-dot{width:8px;height:8px;border-radius:2px;flex-shrink:0;}
#cpu-tooltip .tt-label{font-size:.75rem;color:#64748B;}
#cpu-tooltip .tt-val{margin-left:auto;font-size:.75rem;font-weight:700;color:#0F172A;
  font-variant-numeric:tabular-nums;}
#cpu-tooltip .tt-total{display:flex;justify-content:space-between;margin-top:4px;
  padding-top:5px;border-top:1px solid #F1F5F9;font-weight:700;font-size:.76rem;color:#334155;}
.cpu-leg-pin{font-size:.65rem;color:#6366F1;font-weight:700;margin-bottom:2px;
  display:flex;align-items:center;gap:4px;}
.cpu-leg-pin .pin-time{font-variant-numeric:tabular-nums;}
.cpu-leg-pin .pin-clear{cursor:pointer;color:#94A3B8;font-size:.7rem;margin-left:auto;
  padding:1px 4px;border-radius:3px;transition:all .12s;}
.cpu-leg-pin .pin-clear:hover{color:#EF4444;background:rgba(239,68,68,.08);}
</style>'''


def _cpu_chart_js():
    return r'''
var _cpuData=[];
var _cpuPad={top:8,right:12,bottom:34,left:40};
var _cpuZoom=null;
var _dragState=null;
var _cpuHidden={cpu_sys:false, cpu_user:false, cpu_io:false};
var _cpuPin=null;

function _tsToMin(ts){
  return parseInt(ts.slice(11,13))*60+parseInt(ts.slice(14,16));
}
function _cpuFullRange(){
  var f=document.getElementById("csel-from").value||"00:00";
  var t=document.getElementById("csel-to").value||"23:59";
  var mn=parseInt(f.slice(0,2))*60+parseInt(f.slice(3,5));
  var mx=parseInt(t.slice(0,2))*60+parseInt(t.slice(3,5));
  if(mx<=mn) mx=mn+10;
  return {min:mn,max:mx};
}
function _cpuXRange(){
  return _cpuZoom||_cpuFullRange();
}
function _minToLabel(m){
  return String(Math.floor(m/60)).padStart(2,"0")+":"+String(m%60).padStart(2,"0");
}
function _cpuUpdateHeader(){
  var xr=_cpuXRange();
  var el=document.getElementById("cpu-range-time");
  if(el) el.textContent=_minToLabel(xr.min)+" ~ "+_minToLabel(xr.max);
}
function _cpuResetZoom(){
  _cpuZoom=null;
  _cpuDraw(-1);_cpuUpdateHeader();
  var _zb=document.getElementById('cpu-zoom-badge');if(_zb)_zb.style.display='none';
}
function _toggleSeries(key){
  _cpuHidden[key]=!_cpuHidden[key];
  var el=document.getElementById("leg-"+key);
  if(el){
    if(_cpuHidden[key])el.classList.add("disabled");
    else el.classList.remove("disabled");
  }
  _cpuDraw(-1);
}

/* ── stacked area draw ────────────────────────────────────────────── */
function _cpuDraw(hoverIdx){
  var canvas=document.getElementById("cpu-canvas");
  if(!canvas)return;
  var dpr=window.devicePixelRatio||1;
  var rect=canvas.getBoundingClientRect();
  var W=rect.width, H=rect.height;
  if(W<10||H<10)return; // not rendered yet
  canvas.width=W*dpr; canvas.height=H*dpr;
  var ctx=canvas.getContext("2d");
  ctx.scale(dpr,dpr);
  var pad=_cpuPad;
  var cW=W-pad.left-pad.right, cH=H-pad.top-pad.bottom;
  var n=_cpuData.length;
  var xr=_cpuXRange();
  var span=xr.max-xr.min||1;

  ctx.clearRect(0,0,W,H);
  ctx.fillStyle="#FAFBFC"; ctx.fillRect(pad.left,pad.top,cW,cH);

  // Y grid
  [0,20,40,60,80,100].forEach(function(v){
    var y=pad.top+cH-(v/100)*cH;
    ctx.strokeStyle="rgba(226,232,240,.7)";ctx.lineWidth=1;
    ctx.beginPath();ctx.moveTo(pad.left,y);ctx.lineTo(pad.left+cW,y);ctx.stroke();
    ctx.fillStyle="#334155";ctx.font="600 11px 'Segoe UI',system-ui,sans-serif";
    ctx.textAlign="right";ctx.textBaseline="middle";
    ctx.fillText(v+"%",pad.left-6,y);
  });

  // X ticks
  ctx.textAlign="center";ctx.textBaseline="top";
  ctx.fillStyle="#334155";ctx.font="600 11px 'Segoe UI',system-ui,sans-serif";
  var tickStep=span<=60?5:span<=120?10:span<=360?30:span<=720?60:120;
  var maxTicks=Math.floor(cW/50);if(maxTicks<4)maxTicks=4;
  while(span/tickStep>maxTicks)tickStep*=2;
  for(var m=Math.ceil(xr.min/tickStep)*tickStep;m<=xr.max;m+=tickStep){
    var x=pad.left+((m-xr.min)/span)*cW;
    ctx.strokeStyle="#CBD5E1";ctx.lineWidth=1;
    ctx.beginPath();ctx.moveTo(x,pad.top+cH);ctx.lineTo(x,pad.top+cH+4);ctx.stroke();
    var hh=Math.floor(m/60),mm=m%60;
    var lbl=tickStep>=60?String(hh).padStart(2,"0")+":00":String(hh).padStart(2,"0")+":"+String(mm).padStart(2,"0");
    ctx.fillText(lbl,x,pad.top+cH+8);
  }

  if(n<2){
    ctx.fillStyle="#94A3B8";ctx.font="13px sans-serif";ctx.textAlign="center";
    ctx.fillText("데이터 없음",W/2,H/2); return;
  }

  function xOf(i){return pad.left+((_tsToMin(_cpuData[i].ts)-xr.min)/span)*cW;}
  function yOf(v){return pad.top+cH-((v||0)/100)*cH;}
  var baseline=pad.top+cH;

  // filter to visible range
  var vis=[];
  for(var i=0;i<n;i++){
    var m=_tsToMin(_cpuData[i].ts);
    if(m>=xr.min&&m<=xr.max) vis.push(i);
  }
  if(!vis.length) vis=[0];

  // stacking
  var stacked=[];
  for(var i=0;i<n;i++){
    var d=_cpuData[i];
    var io =_cpuHidden.cpu_io?0:(d.cpu_io||0);
    var user=_cpuHidden.cpu_user?0:(d.cpu_user||0);
    var sys =_cpuHidden.cpu_sys?0:(d.cpu_sys||0);
    stacked.push({y0:0, y1:io, y2:io+user, y3:io+user+sys});
  }

  // clip to chart area so lines don't overflow
  ctx.save();
  ctx.beginPath();ctx.rect(pad.left,pad.top,cW,cH);ctx.clip();

  var layers=[
    {from:"y0",to:"y1",color:"rgba(245,158,11,.35)",hide:_cpuHidden.cpu_io},
    {from:"y1",to:"y2",color:"rgba(34,197,94,.30)", hide:_cpuHidden.cpu_user},
    {from:"y2",to:"y3",color:"rgba(99,102,241,.30)", hide:_cpuHidden.cpu_sys}
  ];
  var GAP=2.5;
  function _segs(arr){var s=[],c=[];for(var j=0;j<arr.length;j++){if(c.length>0){var prev=arr[j-1];var gap=_tsToMin(_cpuData[arr[j]].ts)-_tsToMin(_cpuData[prev].ts);if(gap>GAP){s.push(c);c=[];}}c.push(arr[j]);}if(c.length)s.push(c);return s;}
  var viSegs=_segs(vis);
  layers.forEach(function(L){
    if(L.hide)return;
    ctx.fillStyle=L.color;
    viSegs.forEach(function(seg){
      ctx.beginPath();
      ctx.moveTo(xOf(seg[0]),yOf(stacked[seg[0]][L.from]));
      for(var j=0;j<seg.length;j++){ctx.lineTo(xOf(seg[j]),yOf(stacked[seg[j]][L.to]));}
      for(var j=seg.length-1;j>=0;j--){ctx.lineTo(xOf(seg[j]),yOf(stacked[seg[j]][L.from]));}
      ctx.closePath();ctx.fill();
    });
  });

  var bLines=[
    {key:"y1",color:"#F59E0B",hide:_cpuHidden.cpu_io},
    {key:"y2",color:"#22C55E",hide:_cpuHidden.cpu_user},
    {key:"y3",color:"#6366F1",hide:_cpuHidden.cpu_sys}
  ];
  bLines.forEach(function(L){
    if(L.hide)return;
    ctx.strokeStyle=L.color;ctx.lineWidth=L.key==="y3"&&!_cpuHidden.cpu_sys?1.8:1.0;
    ctx.lineJoin="round";
    viSegs.forEach(function(seg){
      ctx.beginPath();
      for(var j=0;j<seg.length;j++){
        var i=seg[j],x=xOf(i),y=yOf(stacked[i][L.key]);
        if(j===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
      }
      ctx.stroke();
    });
  });

  ctx.restore(); // remove clip

  // ── Heap-style crosshair + drag-to-zoom (DOM overlays) ──────────
  var wPadTop=14, wPadLeft=14;
  var cross=document.getElementById("cpu-cross");
  cross.style.top=(wPadTop+pad.top)+"px";cross.style.height=cH+"px";
  var sel=document.getElementById("cpu-sel");
  sel.style.top=(wPadTop+pad.top)+"px";sel.style.height=cH+"px";
  var tt=document.getElementById("cpu-tooltip");

  function mx2idx(e){
    var br=canvas.getBoundingClientRect();var mx=e.clientX-br.left;
    if(mx<pad.left)mx=pad.left;if(mx>pad.left+cW)mx=pad.left+cW;
    var hovMin=xr.min+((mx-pad.left)/cW)*span;
    var best=0,bestD=99999;
    for(var k=0;k<vis.length;k++){var idx=vis[k];var d=Math.abs(_tsToMin(_cpuData[idx].ts)-hovMin);if(d<bestD){bestD=d;best=idx;}}
    return best;
  }
  function idx2x(idx){
    if(idx<0||idx>=n)return wPadLeft+pad.left;
    return wPadLeft+pad.left+((_tsToMin(_cpuData[idx].ts)-xr.min)/span)*cW;
  }

  canvas.onmousedown=function(e){
    if(e.button!==0||!_cpuData.length)return;
    _dragState={startIdx:mx2idx(e),curIdx:mx2idx(e)};
    sel.style.display="block";sel.style.left=idx2x(_dragState.startIdx)+"px";sel.style.width="0px";
    sel.style.borderLeft="1px solid rgba(99,102,241,.5)";sel.style.borderRight="1px solid rgba(99,102,241,.5)";
    tt.style.display="none";
  };
  canvas.onmousemove=function(e){
    var idx=mx2idx(e);
    if(_dragState){
      _dragState.curIdx=idx;
      var x1=idx2x(Math.min(_dragState.startIdx,_dragState.curIdx));
      var x2=idx2x(Math.max(_dragState.startIdx,_dragState.curIdx));
      sel.style.left=x1+"px";sel.style.width=(x2-x1)+"px";
      cross.style.display="none";
      return;
    }
    var br=canvas.getBoundingClientRect();var mx=e.clientX-br.left;
    if(mx<pad.left||mx>pad.left+cW){cross.style.display="none";tt.style.display="none";return;}
    cross.style.left=idx2x(idx)+"px";cross.style.display="block";
    _cpuShowTT(_cpuData[idx],e.clientX,e.clientY);
  };
  canvas.onmouseup=function(e){
    if(!_dragState)return;
    sel.style.display="none";
    var i1=Math.min(_dragState.startIdx,_dragState.curIdx);
    var i2=Math.max(_dragState.startIdx,_dragState.curIdx);
    _dragState=null;
    if(i1===i2){
      // 단순 클릭 — 해당 시점 Top 20 프로세스 로드 (CPU/Memory 페이지 하단 패널)
      var _ts0=_cpuData[i1]?_cpuData[i1].ts:"";
      if(_ts0 && typeof window._loadProcAt==="function") window._loadProcAt(_ts0);
      return;
    }
    var m1=_tsToMin(_cpuData[i1].ts),m2=_tsToMin(_cpuData[i2].ts);
    if(m2-m1<2)return;
    _cpuZoom={min:m1,max:m2};
    _cpuDraw(-1);_cpuUpdateHeader();
    var _zb=document.getElementById('cpu-zoom-badge');
    if(_zb){var _t1=_cpuData[i1]?_cpuData[i1].ts.substr(11,5):'',_t2=_cpuData[i2]?_cpuData[i2].ts.substr(11,5):'';
    document.getElementById('cpu-zoom-range').textContent=_t1+' ~ '+_t2;_zb.style.display='inline-flex';}
  };
  canvas.onmouseleave=function(){
    cross.style.display="none";tt.style.display="none";
    if(_dragState){sel.style.display="none";_dragState=null;}
  };
  canvas.ondblclick=function(){if(_cpuZoom){_cpuResetZoom();}};

  // locked-line — 사용자가 클릭/이동한 시점(window._procCurrentAt) 을 차트에 표시
  var _locked=document.getElementById("cpu-locked");
  if(_locked){
    var key=window._procCurrentAt||"";
    var lockedMin=null;
    if(key){
      for(var _li=0;_li<n;_li++){
        var t=_cpuData[_li]&&_cpuData[_li].ts;
        if(t&&t.substr(0,16)===key){lockedMin=_tsToMin(t);break;}
      }
    }
    if(lockedMin!=null&&lockedMin>=xr.min&&lockedMin<=xr.max){
      var _lx=wPadLeft+pad.left+((lockedMin-xr.min)/span)*cW;
      _locked.style.left=_lx+"px";
      _locked.style.top=(wPadTop+pad.top)+"px";
      _locked.style.height=cH+"px";
      _locked.style.display="block";
    }else{
      _locked.style.display="none";
    }
  }
}

function _roundRect(ctx,x,y,w,h,r){
  ctx.beginPath();
  ctx.moveTo(x+r,y);ctx.lineTo(x+w-r,y);ctx.quadraticCurveTo(x+w,y,x+w,y+r);
  ctx.lineTo(x+w,y+h-r);ctx.quadraticCurveTo(x+w,y+h,x+w-r,y+h);
  ctx.lineTo(x+r,y+h);ctx.quadraticCurveTo(x,y+h,x,y+h-r);
  ctx.lineTo(x,y+r);ctx.quadraticCurveTo(x,y,x+r,y);ctx.closePath();
}

function _cpuShowTT(d,anchorX,anchorY){
  var total=((d.cpu_sys||0)+(d.cpu_user||0)+(d.cpu_io||0));
  var tt=document.getElementById("cpu-tooltip");
  var html='<div class="tt-time">'+d.ts.slice(11,16)+'</div>';
  [{l:"Sys CPU",c:"#6366F1",v:d.cpu_sys},{l:"User CPU",c:"#22C55E",v:d.cpu_user},
   {l:"IO Wait",c:"#F59E0B",v:d.cpu_io}].forEach(function(it){
    var v=(it.v!=null)?it.v.toFixed(1)+"%":"-";
    html+='<div class="tt-row"><div class="tt-dot" style="background:'+it.c+'"></div>'
      +'<span class="tt-label">'+it.l+'</span><span class="tt-val">'+v+'</span></div>';
  });
  html+='<div class="tt-total"><span>Total</span><span>'+total.toFixed(1)+'%</span></div>';
  tt.innerHTML=html;tt.style.display="block";
  var tx=anchorX+16,ty=anchorY-10;
  if(tx+210>window.innerWidth)tx=anchorX-220;
  if(ty+150>window.innerHeight)ty=anchorY-160;
  tt.style.left=tx+"px";tt.style.top=ty+"px";
}



function _updateLegendValues(d){
  var map=[["leg-val-sys","cpu_sys"],["leg-val-user","cpu_user"],["leg-val-io","cpu_io"]];
  var total=0,hasVal=false;
  map.forEach(function(pair){
    var el=document.getElementById(pair[0]);if(!el)return;
    if(!d){el.textContent="-";return;}
    var v=d[pair[1]];
    if(v!=null){el.textContent=v.toFixed(1)+"%";total+=v;hasVal=true;}
    else el.textContent="-";
  });
  var te=document.getElementById("leg-val-total");
  if(te) te.textContent=(d&&hasVal)?total.toFixed(1)+"%":"-";
}

function _cSbQuick(mode){
  var btns=document.querySelectorAll(".csb-qbtn");
  btns.forEach(function(b){b.classList.remove("active");});
  var btn=document.getElementById("cqb-"+mode);if(btn)btn.classList.add("active");
  if(mode==='today'){
    document.getElementById("csel-date").value=new Date().toISOString().slice(0,10);
    document.getElementById("csel-from").value="00:00";document.getElementById("csel-to").value="23:59";
  }else if(mode==='am'){
    document.getElementById("csel-from").value="00:00";document.getElementById("csel-to").value="11:59";
  }else if(mode==='pm'){
    document.getElementById("csel-from").value="12:00";document.getElementById("csel-to").value="23:59";
  }
  cDoQuery();
}

function cDoQuery(){
  var d=document.getElementById("csel-date").value;
  var f=document.getElementById("csel-from").value;
  var t=document.getElementById("csel-to").value;
  
  _cpuZoom=null;
  fetch(_apiBase+"/api/history-os?date="+d+"&from="+f+"&to="+t)
  .then(function(r){return r.json();})
  .then(function(res){
    if(!res.ok){alert(res.error);return;}
    _cpuData=res.data||[];
    _cpuDraw(-1);
    var _c=document.getElementById("cpu-canvas");
    if(_c&&_c.getBoundingClientRect().width<10)setTimeout(function(){_cpuDraw(-1);},100);
    _cpuUpdateHeader();
  });
}

window.addEventListener("resize",function(){_cpuDraw(-1);});
'''


def page_history_os_cpu():
    from pages.history_page import _history_page
    if not _insp_table_exists('insp_os_history'):
        body = '<p class="page-title">CPU Usage History</p>' + _table_missing_html('INSP_OS_HISTORY')
        return _history_page(body, active='os_cpu')
    b = _UTILS_BASE
    body = ''.join([
        _page_title_html('CPU Usage History', *_HELP.get('history_os_cpu', ('CPU Usage History', ''))),
        '<div class="cpu-panel">',
        '<div class="cpu-search-bar">'
        '<button type="button" class="sb-arrow" onclick="_shiftDateInput(\'csel-date\',-1)">&#8249;</button>'
        '<div class="sb-group">'
        '<label>Date</label>'
        '<input type="date" id="csel-date">'
        '<button type="button" class="sb-cal-btn" onclick="document.getElementById(\'csel-date\').showPicker()">'
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">'
        '<rect x="2" y="3" width="12" height="11" rx="2"/><path d="M2 7h12M5 1v3M11 1v3"/></svg></button>'
        '</div>'
        '<button type="button" class="sb-arrow" onclick="_shiftDateInput(\'csel-date\',1)">&#8250;</button>'
        '<input type="hidden" id="csel-from" value="00:00">'
        '<input type="hidden" id="csel-to" value="23:59">'
        '<button class="sb-qbtn csb-qbtn" id="cqb-am" onclick="_cSbQuick(\'am\')">AM</button>'
        '<button class="sb-qbtn csb-qbtn" id="cqb-pm" onclick="_cSbQuick(\'pm\')">PM</button>'
        '<button class="sb-qbtn csb-qbtn active" id="cqb-today" onclick="_cSbQuick(\'today\')">Today</button>'
        '</div>',
        '<div class="cpu-body">',
        '<div class="cpu-canvas-area" style="position:relative;">',
        '<div id="cpu-zoom-badge" style="display:none;position:absolute;top:10px;left:14px;z-index:11;'
        'align-items:center;gap:5px;padding:3px 10px;border-radius:6px;'
        'background:#EEF2FF;border:1px solid #C7D2FE;color:#6366F1;font-size:.72rem;font-weight:600;'
        'cursor:pointer;" onclick="_cpuResetZoom()">'
        '<span id="cpu-zoom-range"></span> &times;</div>'
        '<canvas id="cpu-canvas" style="width:100%;height:310px;display:block;cursor:crosshair;"></canvas>',
        '<div id="cpu-cross" style="display:none;position:absolute;top:0;width:1px;background:rgba(99,102,241,.5);pointer-events:none;z-index:10;"></div>',
        '<div id="cpu-locked" style="display:none;position:absolute;top:0;width:1px;background:rgba(99,102,241,.5);pointer-events:none;z-index:11;"></div>',
        '<div id="cpu-sel" style="display:none;position:absolute;top:0;background:rgba(99,102,241,.12);pointer-events:none;z-index:5;"></div>',
        '</div>',
        '<div class="cpu-legend-panel">',
        '<div class="cpu-leg-section">',
        '<div class="cpu-leg-title">Legend</div>',
        '<div class="cpu-leg-item" id="leg-cpu_sys" onclick="_toggleSeries(\'cpu_sys\')">'
        '<div class="cpu-leg-swatch" style="background:rgba(99,102,241,.35);border:1.5px solid #6366F1;"></div>'
        '<span class="cpu-leg-label">Sys CPU (%)</span></div>',
        '<div class="cpu-leg-item" id="leg-cpu_user" onclick="_toggleSeries(\'cpu_user\')">'
        '<div class="cpu-leg-swatch" style="background:rgba(34,197,94,.35);border:1.5px solid #22C55E;"></div>'
        '<span class="cpu-leg-label">User CPU (%)</span></div>',
        '<div class="cpu-leg-item" id="leg-cpu_io" onclick="_toggleSeries(\'cpu_io\')">'
        '<div class="cpu-leg-swatch" style="background:rgba(245,158,11,.40);border:1.5px solid #F59E0B;"></div>'
        '<span class="cpu-leg-label">IO Wait (%)</span></div>',
        '</div>',
        '</div>',
        '<div id="cpu-tooltip"></div>',
        '</div>',
        '</div>',
        _proc_panel_html(),
        _ts(), _view_css(), _cpu_chart_css(), _proc_panel_css(),
        '<script>',
        'var _apiBase="' + b + '";',
        'window._procSortBy="cpu";',
        'document.getElementById("csel-date").value=new Date().toISOString().slice(0,10);',
        _cpu_chart_js(),
        '_cpuDraw(-1);',
        'document.getElementById("csel-date").addEventListener("change",function(){'
        'document.querySelectorAll(".csb-qbtn").forEach(function(b){b.classList.remove("active");});'
        'document.getElementById("csel-from").value="00:00";'
        'document.getElementById("csel-to").value="23:59";'
        'cDoQuery();});',
        'cDoQuery();',
        '</script>',
        _proc_panel_js(),
    ])
    return _history_page(body, active='os_cpu')


# ── Memory Page (same structure as CPU) ────────────────────────────────────────

def _mem_chart_css():
    return '''<style>
/* [DESIGN-A] border-radius:14px → 0, border #E2E8F0 → #CBD5E1 (Inspector 톤). */
.mem-panel{background:#ffffff;border:1px solid #CBD5E1;border-radius:0;overflow:hidden;}
.mem-header{display:flex;align-items:center;justify-content:space-between;
  padding:14px 22px 10px;border-bottom:1px solid #F1F5F9;}
.mem-header-left{display:flex;align-items:center;gap:12px;}
.mem-title{font-size:.95rem;font-weight:700;color:#0F172A;letter-spacing:.01em;}
.mem-range-info{display:flex;align-items:center;gap:6px;font-size:.78rem;color:#475569;
  font-weight:600;font-variant-numeric:tabular-nums;}
.mem-range-info .ri-date{color:#0F172A;font-weight:700;}
.mem-range-info .ri-time{color:#8B5CF6;font-weight:700;}
.mem-range-info .ri-sep{color:#CBD5E1;margin:0 1px;}
.mem-body{display:flex;min-height:340px;}
.mem-canvas-area{flex:1;padding:14px 8px 14px 14px;position:relative;min-width:0;}
.mem-legend-panel{width:172px;flex-shrink:0;border-left:1px solid #F1F5F9;
  padding:18px 16px;display:flex;flex-direction:column;gap:6px;}
#mem-tooltip{display:none;position:fixed;z-index:9999;background:#ffffff;
  border:1px solid #E2E8F0;border-radius:10px;padding:12px 16px;
  box-shadow:0 12px 32px rgba(0,0,0,.14);font-size:.78rem;pointer-events:none;
  min-width:185px;}
#mem-tooltip .tt-time{font-size:.82rem;font-weight:700;color:#0F172A;margin-bottom:6px;
  padding-bottom:6px;border-bottom:1px solid #F1F5F9;}
#mem-tooltip .tt-row{display:flex;align-items:center;gap:6px;margin-bottom:3px;}
#mem-tooltip .tt-dot{width:8px;height:8px;border-radius:2px;flex-shrink:0;}
#mem-tooltip .tt-label{font-size:.75rem;color:#64748B;}
#mem-tooltip .tt-val{margin-left:auto;font-size:.75rem;font-weight:700;color:#0F172A;
  font-variant-numeric:tabular-nums;}
</style>'''


def _mem_chart_js():
    return r'''
var _memData=[];
var _memPad={top:8,right:12,bottom:34,left:40};
var _memZoom=null;
var _memDrag=null;
var _memHidden={mem_used:false};
var _memPin=null;

function _mtsToMin(ts){return parseInt(ts.slice(11,13))*60+parseInt(ts.slice(14,16));}
function _memFullRange(){
  var f=document.getElementById("msel-from").value||"00:00";
  var t=document.getElementById("msel-to").value||"23:59";
  var mn=parseInt(f.slice(0,2))*60+parseInt(f.slice(3,5));
  var mx=parseInt(t.slice(0,2))*60+parseInt(t.slice(3,5));
  if(mx<=mn) mx=mn+10;
  return {min:mn,max:mx};
}
function _memXRange(){return _memZoom||_memFullRange();}
function _mMinToLabel(m){return String(Math.floor(m/60)).padStart(2,"0")+":"+String(m%60).padStart(2,"0");}
function _memUpdateHeader(){
  var xr=_memXRange();
  var el=document.getElementById("mem-range-time");
  if(el) el.textContent=_mMinToLabel(xr.min)+" ~ "+_mMinToLabel(xr.max);
}
function _memResetZoom(){
  _memZoom=null;
  _memDraw(-1);_memUpdateHeader();
  var _zb=document.getElementById('mem-zoom-badge');if(_zb)_zb.style.display='none';
}
function _memToggle(key){
  _memHidden[key]=!_memHidden[key];
  var el=document.getElementById("mleg-"+key);
  if(el){if(_memHidden[key])el.classList.add("disabled");else el.classList.remove("disabled");}
  _memDraw(-1);
}

function _memDraw(hoverIdx){
  var canvas=document.getElementById("mem-canvas");
  if(!canvas)return;
  var dpr=window.devicePixelRatio||1;
  var rect=canvas.getBoundingClientRect();
  var W=rect.width, H=rect.height;
  if(W<10||H<10)return;
  canvas.width=W*dpr; canvas.height=H*dpr;
  var ctx=canvas.getContext("2d");
  ctx.scale(dpr,dpr);
  var pad=_memPad;
  var cW=W-pad.left-pad.right, cH=H-pad.top-pad.bottom;
  var n=_memData.length;
  var xr=_memXRange(), span=xr.max-xr.min||1;

  ctx.clearRect(0,0,W,H);
  ctx.fillStyle="#FAFBFC";ctx.fillRect(pad.left,pad.top,cW,cH);

  // find max total GB for Y scale
  var maxGB=0;
  for(var i=0;i<n;i++){var t=_memData[i].mem_total||0;if(t>maxGB)maxGB=t;}
  if(maxGB<1)maxGB=16;
  var yTop=Math.ceil(maxGB/4)*4; // round up to nice number

  // Y grid (GB)
  var yStepCount=4;
  var yStep=yTop/yStepCount;
  ctx.textAlign="right";ctx.textBaseline="middle";
  for(var s=0;s<=yStepCount;s++){
    var v=s*yStep;
    var y=pad.top+cH-(v/yTop)*cH;
    ctx.strokeStyle="rgba(226,232,240,.7)";ctx.lineWidth=1;
    ctx.beginPath();ctx.moveTo(pad.left,y);ctx.lineTo(pad.left+cW,y);ctx.stroke();
    ctx.fillStyle="#334155";ctx.font="600 11px 'Segoe UI',system-ui,sans-serif";
    ctx.fillText(v.toFixed(0)+"G",pad.left-6,y);
  }

  // X ticks
  ctx.textAlign="center";ctx.textBaseline="top";
  ctx.fillStyle="#334155";ctx.font="600 11px 'Segoe UI',system-ui,sans-serif";
  var tickStep=span<=60?5:span<=120?10:span<=360?30:span<=720?60:120;
  var maxTicks=Math.floor(cW/50);if(maxTicks<4)maxTicks=4;
  while(span/tickStep>maxTicks)tickStep*=2;
  for(var m=Math.ceil(xr.min/tickStep)*tickStep;m<=xr.max;m+=tickStep){
    var x=pad.left+((m-xr.min)/span)*cW;
    ctx.strokeStyle="#CBD5E1";ctx.lineWidth=1;
    ctx.beginPath();ctx.moveTo(x,pad.top+cH);ctx.lineTo(x,pad.top+cH+4);ctx.stroke();
    var hh=Math.floor(m/60),mm=m%60;
    var lbl=tickStep>=60?String(hh).padStart(2,"0")+":00":String(hh).padStart(2,"0")+":"+String(mm).padStart(2,"0");
    ctx.fillText(lbl,x,pad.top+cH+8);
  }

  if(n<2){
    ctx.fillStyle="#94A3B8";ctx.font="13px sans-serif";ctx.textAlign="center";
    ctx.fillText("데이터 없음",W/2,H/2);return;
  }

  function xOf(i){return pad.left+((_mtsToMin(_memData[i].ts)-xr.min)/span)*cW;}
  function yOf(v){return pad.top+cH-((v||0)/yTop)*cH;}
  var baseline=pad.top+cH;

  var vis=[];
  for(var i=0;i<n;i++){var m=_mtsToMin(_memData[i].ts);if(m>=xr.min&&m<=xr.max)vis.push(i);}
  if(!vis.length)vis=[0];

  ctx.save();
  ctx.beginPath();ctx.rect(pad.left,pad.top,cW,cH);ctx.clip();

  // stacked: Used (bottom) + Free (top) = Total
  var MGAP=2.5;
  function _mSegs(arr){var s=[],c=[];for(var j=0;j<arr.length;j++){if(c.length>0){var prev=arr[j-1];var gap=_mtsToMin(_memData[arr[j]].ts)-_mtsToMin(_memData[prev].ts);if(gap>MGAP){s.push(c);c=[];}}c.push(arr[j]);}if(c.length)s.push(c);return s;}
  var mSegs=_mSegs(vis);
  if(!_memHidden.mem_used){
    ctx.fillStyle="rgba(139,92,246,.25)";
    mSegs.forEach(function(seg){
      ctx.beginPath();ctx.moveTo(xOf(seg[0]),baseline);
      for(var j=0;j<seg.length;j++){ctx.lineTo(xOf(seg[j]),yOf(_memData[seg[j]].mem_used||0));}
      ctx.lineTo(xOf(seg[seg.length-1]),baseline);ctx.closePath();ctx.fill();
    });
    ctx.strokeStyle="#8B5CF6";ctx.lineWidth=1.5;ctx.lineJoin="round";
    mSegs.forEach(function(seg){
      ctx.beginPath();
      for(var j=0;j<seg.length;j++){var i=seg[j],x=xOf(i),y=yOf(_memData[i].mem_used||0);
        if(j===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);}
      ctx.stroke();
    });
  }

  ctx.restore();

  // ── Heap-style crosshair + drag-to-zoom (DOM overlays) ──────────
  var wPadTop=14, wPadLeft=14;
  var cross=document.getElementById("mem-cross");
  cross.style.top=(wPadTop+pad.top)+"px";cross.style.height=cH+"px";
  var sel=document.getElementById("mem-sel");
  sel.style.top=(wPadTop+pad.top)+"px";sel.style.height=cH+"px";
  var tt=document.getElementById("mem-tooltip");

  function mx2idx(e){
    var br=canvas.getBoundingClientRect();var mx=e.clientX-br.left;
    if(mx<pad.left)mx=pad.left;if(mx>pad.left+cW)mx=pad.left+cW;
    var hovMin=xr.min+((mx-pad.left)/cW)*span;
    var best=0,bestD=99999;
    for(var k=0;k<vis.length;k++){var idx=vis[k];var d=Math.abs(_mtsToMin(_memData[idx].ts)-hovMin);if(d<bestD){bestD=d;best=idx;}}
    return best;
  }
  function idx2x(idx){
    if(idx<0||idx>=n)return wPadLeft+pad.left;
    return wPadLeft+pad.left+((_mtsToMin(_memData[idx].ts)-xr.min)/span)*cW;
  }

  canvas.onmousedown=function(e){
    if(e.button!==0||!_memData.length)return;
    _memDrag={startIdx:mx2idx(e),curIdx:mx2idx(e)};
    sel.style.display="block";sel.style.left=idx2x(_memDrag.startIdx)+"px";sel.style.width="0px";
    sel.style.borderLeft="1px solid rgba(139,92,246,.5)";sel.style.borderRight="1px solid rgba(139,92,246,.5)";
    tt.style.display="none";
  };
  canvas.onmousemove=function(e){
    var idx=mx2idx(e);
    if(_memDrag){
      _memDrag.curIdx=idx;
      var x1=idx2x(Math.min(_memDrag.startIdx,_memDrag.curIdx));
      var x2=idx2x(Math.max(_memDrag.startIdx,_memDrag.curIdx));
      sel.style.left=x1+"px";sel.style.width=(x2-x1)+"px";
      cross.style.display="none";
      return;
    }
    var br=canvas.getBoundingClientRect();var mx=e.clientX-br.left;
    if(mx<pad.left||mx>pad.left+cW){cross.style.display="none";tt.style.display="none";return;}
    cross.style.left=idx2x(idx)+"px";cross.style.display="block";
    _memShowTT(_memData[idx],e.clientX,e.clientY);
  };
  canvas.onmouseup=function(e){
    if(!_memDrag)return;
    sel.style.display="none";
    var i1=Math.min(_memDrag.startIdx,_memDrag.curIdx);
    var i2=Math.max(_memDrag.startIdx,_memDrag.curIdx);
    _memDrag=null;
    if(i1===i2){
      // 단순 클릭 — 해당 시점 Top 20 프로세스 로드
      var _ts0=_memData[i1]?_memData[i1].ts:"";
      if(_ts0 && typeof window._loadProcAt==="function") window._loadProcAt(_ts0);
      return;
    }
    var m1=_mtsToMin(_memData[i1].ts),m2=_mtsToMin(_memData[i2].ts);
    if(m2-m1<2)return;
    _memZoom={min:m1,max:m2};
    _memDraw(-1);_memUpdateHeader();
    var _zb=document.getElementById('mem-zoom-badge');
    if(_zb){var _t1=_memData[i1]?_memData[i1].ts.substr(11,5):'',_t2=_memData[i2]?_memData[i2].ts.substr(11,5):'';
    document.getElementById('mem-zoom-range').textContent=_t1+' ~ '+_t2;_zb.style.display='inline-flex';}
  };
  canvas.onmouseleave=function(){
    cross.style.display="none";tt.style.display="none";
    if(_memDrag){sel.style.display="none";_memDrag=null;}
  };
  canvas.ondblclick=function(){if(_memZoom){_memResetZoom();}};

  // locked-line — 사용자가 클릭/이동한 시점(window._procCurrentAt) 을 차트에 표시
  var _locked=document.getElementById("mem-locked");
  if(_locked){
    var key=window._procCurrentAt||"";
    var lockedMin=null;
    if(key){
      for(var _li=0;_li<n;_li++){
        var t=_memData[_li]&&_memData[_li].ts;
        if(t&&t.substr(0,16)===key){lockedMin=_mtsToMin(t);break;}
      }
    }
    if(lockedMin!=null&&lockedMin>=xr.min&&lockedMin<=xr.max){
      var _lx=wPadLeft+pad.left+((lockedMin-xr.min)/span)*cW;
      _locked.style.left=_lx+"px";
      _locked.style.top=(wPadTop+pad.top)+"px";
      _locked.style.height=cH+"px";
      _locked.style.display="block";
    }else{
      _locked.style.display="none";
    }
  }
}

function _mRoundRect(ctx,x,y,w,h,r){
  ctx.beginPath();ctx.moveTo(x+r,y);ctx.lineTo(x+w-r,y);ctx.quadraticCurveTo(x+w,y,x+w,y+r);
  ctx.lineTo(x+w,y+h-r);ctx.quadraticCurveTo(x+w,y+h,x+w-r,y+h);
  ctx.lineTo(x+r,y+h);ctx.quadraticCurveTo(x,y+h,x,y+h-r);
  ctx.lineTo(x,y+r);ctx.quadraticCurveTo(x,y,x+r,y);ctx.closePath();
}

function _memShowTT(d,ax,ay){
  var tt=document.getElementById("mem-tooltip");
  var html='<div class="tt-time">'+d.ts.slice(11,16)+'</div>';
  [{l:"Used",c:"#8B5CF6",v:d.mem_used,u:" GB"},{l:"Usage",c:"#6366F1",v:d.mem_pct,u:"%"}
  ].forEach(function(it){
    var v=(it.v!=null)?(typeof it.v==="number"?it.v.toFixed(1):it.v)+it.u:"-";
    html+='<div class="tt-row"><div class="tt-dot" style="background:'+it.c+'"></div>'
      +'<span class="tt-label">'+it.l+'</span><span class="tt-val">'+v+'</span></div>';});
  tt.innerHTML=html;tt.style.display="block";
  var tx=ax+16,ty=ay-10;
  if(tx+210>window.innerWidth)tx=ax-220;
  if(ty+150>window.innerHeight)ty=ay-160;
  tt.style.left=tx+"px";tt.style.top=ty+"px";
}

function _memUpdateLegend(d){
  var map=[["mleg-val-used","mem_used"," GB"],["mleg-val-pct","mem_pct","%"]];
  map.forEach(function(p){
    var el=document.getElementById(p[0]);if(!el)return;
    if(!d){el.textContent="-";return;}
    var v=d[p[1]];el.textContent=(v!=null)?v.toFixed(1)+p[2]:"-";
  });
}

function _mSbQuick(mode){
  var btns=document.querySelectorAll(".msb-qbtn");
  btns.forEach(function(b){b.classList.remove("active");});
  var btn=document.getElementById("mqb-"+mode);if(btn)btn.classList.add("active");
  if(mode==='today'){
    document.getElementById("msel-date").value=new Date().toISOString().slice(0,10);
    document.getElementById("msel-from").value="00:00";document.getElementById("msel-to").value="23:59";
  }else if(mode==='am'){
    document.getElementById("msel-from").value="00:00";document.getElementById("msel-to").value="11:59";
  }else if(mode==='pm'){
    document.getElementById("msel-from").value="12:00";document.getElementById("msel-to").value="23:59";
  }
  mDoQuery();
}

function mDoQuery(){
  var d=document.getElementById("msel-date").value;
  var f=document.getElementById("msel-from").value;
  var t=document.getElementById("msel-to").value;
  
  _memZoom=null;
  fetch(_apiBase+"/api/history-os?date="+d+"&from="+f+"&to="+t)
  .then(function(r){return r.json();})
  .then(function(res){
    if(!res.ok){alert(res.error);return;}
    _memData=res.data||[];
    _memDraw(-1);
    var _c=document.getElementById("mem-canvas");
    if(_c&&_c.getBoundingClientRect().width<10)setTimeout(function(){_memDraw(-1);},100);
    _memUpdateLegend(null);_memUpdateHeader();
  });
}

window.addEventListener("resize",function(){_memDraw(-1);});
'''


def page_history_os_memory():
    from pages.history_page import _history_page
    if not _insp_table_exists('insp_os_history'):
        body = '<p class="page-title">Memory Usage History</p>' + _table_missing_html('INSP_OS_HISTORY')
        return _history_page(body, active='os_memory')
    b = _UTILS_BASE
    body = ''.join([
        _page_title_html('Memory Usage History', *_HELP.get('history_os_memory', ('Memory Usage History', ''))),
        '<div class="mem-panel">',
        # Search bar
        '<div class="cpu-search-bar">'
        '<button type="button" class="sb-arrow" onclick="_shiftDateInput(\'msel-date\',-1)">&#8249;</button>'
        '<div class="sb-group">'
        '<label>Date</label>'
        '<input type="date" id="msel-date">'
        '<button type="button" class="sb-cal-btn" onclick="document.getElementById(\'msel-date\').showPicker()">'
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">'
        '<rect x="2" y="3" width="12" height="11" rx="2"/><path d="M2 7h12M5 1v3M11 1v3"/></svg></button>'
        '</div>'
        '<button type="button" class="sb-arrow" onclick="_shiftDateInput(\'msel-date\',1)">&#8250;</button>'
        '<input type="hidden" id="msel-from" value="00:00">'
        '<input type="hidden" id="msel-to" value="23:59">'
        '<button class="sb-qbtn msb-qbtn" id="mqb-am" onclick="_mSbQuick(\'am\')">AM</button>'
        '<button class="sb-qbtn msb-qbtn" id="mqb-pm" onclick="_mSbQuick(\'pm\')">PM</button>'
        '<button class="sb-qbtn msb-qbtn active" id="mqb-today" onclick="_mSbQuick(\'today\')">Today</button>'
        '</div>',
        # Body
        '<div class="mem-body">',
        '<div class="mem-canvas-area" style="position:relative;">',
        '<div id="mem-zoom-badge" style="display:none;position:absolute;top:10px;left:14px;z-index:11;'
        'align-items:center;gap:5px;padding:3px 10px;border-radius:6px;'
        'background:#EEF2FF;border:1px solid #C7D2FE;color:#6366F1;font-size:.72rem;font-weight:600;'
        'cursor:pointer;" onclick="_memResetZoom()">'
        '<span id="mem-zoom-range"></span> &times;</div>'
        '<canvas id="mem-canvas" style="width:100%;height:310px;display:block;cursor:crosshair;"></canvas>',
        '<div id="mem-cross" style="display:none;position:absolute;top:0;width:1px;background:rgba(139,92,246,.5);pointer-events:none;z-index:10;"></div>',
        '<div id="mem-locked" style="display:none;position:absolute;top:0;width:1px;background:rgba(139,92,246,.5);pointer-events:none;z-index:11;"></div>',
        '<div id="mem-sel" style="display:none;position:absolute;top:0;background:rgba(139,92,246,.12);pointer-events:none;z-index:5;"></div>',
        '</div>',
        # Legend
        '<div class="mem-legend-panel">',
        '<div class="cpu-leg-section">',
        '<div class="cpu-leg-title">Legend</div>',
        '<div class="cpu-leg-item" id="mleg-mem_used" onclick="_memToggle(\'mem_used\')">'
        '<div class="cpu-leg-swatch" style="background:rgba(139,92,246,.30);border:1.5px solid #8B5CF6;"></div>'
        '<span class="cpu-leg-label">Used (GB)</span></div>',
        '</div>',
        '</div>',  # legend
        '</div>',  # body
        '<div id="mem-tooltip"></div>',
        '</div>',  # panel
        _proc_panel_html(),
        _ts(), _view_css(), _cpu_chart_css(), _mem_chart_css(), _proc_panel_css(),
        '<script>',
        'var _apiBase="' + b + '";',
        'window._procSortBy="mem";',
        'document.getElementById("msel-date").value=new Date().toISOString().slice(0,10);',
        _mem_chart_js(),
        '_memDraw(-1);',
        'document.getElementById("msel-date").addEventListener("change",function(){'
        'document.querySelectorAll(".msb-qbtn").forEach(function(b){b.classList.remove("active");});'
        'document.getElementById("msel-from").value="00:00";'
        'document.getElementById("msel-to").value="23:59";'
        'mDoQuery();});',
        'mDoQuery();',
        '</script>',
        _proc_panel_js(),
    ])
    return _history_page(body, active='os_memory')


# ── TBS Page (single tablespace trend bar chart) ─────────────────────────────


def _history_page_or_embed(body, embed, active):
    if embed:
        from html_helpers import _CSS
        return ''.join([
            '<!DOCTYPE html><html><head><meta charset="UTF-8"><style>',
            _CSS,
            'body{margin:0;padding:10px;background:#fff;}.cpu-search-bar{display:none!important;}.page-hdr{display:none!important;}.page-title{display:none!important;}</style></head><body>',
            body,
            '</body></html>',
        ])
    from pages.history_page import _history_page
    return _history_page(body, active=active)
def page_history_disk_tbs(path=""):
    embed = "embed=1" in path
    from pages.history_page import _history_page
    if not _insp_table_exists('insp_tbs_history'):
        body = '<p class="page-title">Disk / TBS History</p>' + _table_missing_html('INSP_TBS_HISTORY')
        return _history_page_or_embed(body, embed, active='disk_tbs')
    b = _UTILS_BASE
    tbs_js = r'''
var _tbsData=null;

function tbsQuery(){
  var fd=document.getElementById("tbs-from").value;
  var td=document.getElementById("tbs-to").value;
  fetch(_apiBase+"/api/history-tbs?from_date="+fd+"&to_date="+td)
  .then(function(r){return r.json();})
  .then(function(res){
    if(!res.ok){document.getElementById("tbs-nodata").style.display="block";
      document.getElementById("tbs-nodata").textContent=res.error;return;}
    if(!res.data.length){document.getElementById("tbs-nodata").style.display="block";
      document.getElementById("tbs-nodata").textContent="데이터 없음";return;}
    document.getElementById("tbs-nodata").style.display="none";
    _tbsData=res.data;
    tbsDraw();
  });
}

function tbsDraw(){
  if(!_tbsData||!_tbsData.length)return;
  var canvas=document.getElementById("tbs-canvas");
  if(!canvas)return;
  var dpr=window.devicePixelRatio||1;
  var rect=canvas.getBoundingClientRect();
  var W=rect.width,H=rect.height;
  if(W<10)return;
  canvas.width=W*dpr;canvas.height=H*dpr;
  var ctx=canvas.getContext("2d");ctx.scale(dpr,dpr);

  // group by date (take last entry per date)
  var byDate={};
  _tbsData.forEach(function(r){ byDate[r.ts.slice(0,10)]=r; });
  var fd=document.getElementById("tbs-from").value,td=document.getElementById("tbs-to").value;
  var dates=[],cur=new Date(fd);
  var end=new Date(td);
  while(cur<=end){dates.push(cur.toISOString().slice(0,10));cur.setDate(cur.getDate()+1);}
  var n=dates.length;
  if(!n)return;

  // find TBS name + max total for Y scale
  var tbsName=_tbsData[0].name||"TABLESPACE";
  var maxTotal=0;
  dates.forEach(function(d){var r=byDate[d];if(r&&r.total>maxTotal)maxTotal=r.total;});
  var yTop=Math.ceil(maxTotal*1.15);if(yTop<1)yTop=10;

  // update header
  var hdr=document.getElementById("tbs-title-name");
  if(hdr)hdr.textContent=tbsName;

  var pad={top:14,right:20,bottom:36,left:50};
  var cW=W-pad.left-pad.right, cH=H-pad.top-pad.bottom;

  ctx.clearRect(0,0,W,H);
  ctx.fillStyle="#FAFBFC";ctx.fillRect(pad.left,pad.top,cW,cH);

  // Y grid (GB)
  var ySteps=5;
  ctx.textAlign="right";ctx.textBaseline="middle";
  for(var s=0;s<=ySteps;s++){
    var v=yTop/ySteps*s;
    var y=pad.top+cH-(v/yTop)*cH;
    ctx.strokeStyle="rgba(226,232,240,.7)";ctx.lineWidth=1;
    ctx.beginPath();ctx.moveTo(pad.left,y);ctx.lineTo(pad.left+cW,y);ctx.stroke();
    ctx.fillStyle="#334155";ctx.font="600 11px 'Segoe UI',system-ui,sans-serif";
    ctx.fillText(v.toFixed(1)+" GB",pad.left-6,y);
  }

  // bar layout
  var barGap=Math.max(1, Math.min(4, cW/n*0.1));
  var barW=(cW-barGap*(n-1))/n;
  if(barW<2)barW=2;
  var totalBarArea=cW;
  var offsetX=pad.left;
  var offsetX=pad.left+(cW-totalBarArea)/2;

  // draw bars
  for(var i=0;i<n;i++){
    var r=byDate[dates[i]];
    if(!r){bx=offsetX+i*(barW+barGap);ctx.fillStyle="#334155";ctx.font="600 10px 'Segoe UI',system-ui,sans-serif";ctx.textAlign="center";ctx.textBaseline="top";ctx.fillText(dates[i].slice(5),bx+barW/2,pad.top+cH+10);continue;}
    var used=r.used||0, total=r.total||0, pct=r.pct||0;
    var bx=offsetX+i*(barW+barGap);
    var usedH=(used/yTop)*cH;
    var totalH=(total/yTop)*cH;

    // total capacity (light outline)
    ctx.fillStyle="rgba(99,102,241,.06)";
    ctx.fillRect(bx,pad.top+cH-totalH,barW,totalH);
    ctx.strokeStyle="rgba(99,102,241,.2)";ctx.lineWidth=0.5;
    ctx.strokeRect(bx,pad.top+cH-totalH,barW,totalH);

    // used (gradient by %)
    var clr=pct>=90?"#EF4444":pct>=80?"#F59E0B":"#6366F1";
    ctx.fillStyle=clr;
    ctx.globalAlpha=0.7;
    ctx.fillRect(bx,pad.top+cH-usedH,barW,usedH);
    ctx.globalAlpha=1;

    // X label (date)
    if(n<=35||(i%Math.ceil(n/20)===0)){
      ctx.fillStyle="#334155";ctx.font="600 10px 'Segoe UI',system-ui,sans-serif";
      ctx.textAlign="center";ctx.textBaseline="top";
      var lbl=n<=14?dates[i].slice(5):dates[i].slice(5);
      ctx.fillText(lbl,bx+barW/2, pad.top+cH+10);
    }
  }

  // tooltip
  canvas.onmousemove=function(e){
    var br=canvas.getBoundingClientRect();
    var mx=e.clientX-br.left,my=e.clientY-br.top;
    if(mx<pad.left||mx>pad.left+cW||my<pad.top||my>pad.top+cH){
      document.getElementById("tbs-tooltip").style.display="none";return;}
    // find which bar
    var relX=mx-offsetX;
    var idx=Math.floor(relX/(barW+barGap));
    if(idx<0)idx=0;if(idx>=n)idx=n-1;
    var r=byDate[dates[idx]];
    if(!r){document.getElementById("tbs-tooltip").innerHTML='<div style="font-weight:700;">'+dates[idx]+'</div><div style="color:#94A3B8;padding:8px 0;">데이터 없음</div>';document.getElementById("tbs-tooltip").style.display="block";document.getElementById("tbs-tooltip").style.left=(e.clientX+14)+"px";document.getElementById("tbs-tooltip").style.top=(e.clientY+14)+"px";return;}
    var tt=document.getElementById("tbs-tooltip");
    var pct=r.pct!=null?r.pct.toFixed(1):"-";
    var clr=r.pct>=90?"#EF4444":r.pct>=80?"#F59E0B":"#6366F1";
    tt.innerHTML='<div style="font-weight:700;margin-bottom:6px;">'+dates[idx]+'</div>'
      +'<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">'
      +'<div style="width:10px;height:10px;border-radius:2px;background:'+clr+';"></div>'
      +'<span style="color:#64748B;">Used</span>'
      +'<span style="margin-left:auto;font-weight:700;">'+r.used+' GB</span></div>'
      +'<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">'
      +'<div style="width:10px;height:10px;border-radius:2px;background:rgba(99,102,241,.15);border:1px solid rgba(99,102,241,.3);"></div>'
      +'<span style="color:#64748B;">Total</span>'
      +'<span style="margin-left:auto;font-weight:700;">'+r.total+' GB</span></div>'
      +'<div style="border-top:1px solid #F1F5F9;margin-top:4px;padding-top:4px;display:flex;justify-content:space-between;font-weight:700;">'
      +'<span>Usage</span><span style="color:'+clr+';">'+pct+'%</span></div>';
    tt.style.display="block";
    var tx=e.clientX+14,ty=e.clientY+14;
    if(tx+200>window.innerWidth)tx=e.clientX-210;
    if(ty+130>window.innerHeight)ty=e.clientY-140;
    tt.style.left=tx+"px";tt.style.top=ty+"px";
  };
  canvas.onmouseleave=function(){document.getElementById("tbs-tooltip").style.display="none";};
}
window.addEventListener("resize",function(){if(_tbsData)tbsDraw();});
'''
    body = ''.join([
        _page_title_html('Disk Usage History' if _is_pg_repo() else 'Tablespace Usage History', *_HELP.get('history_disk_tbs', ('Disk / TBS History', ''))),
        '<div class="cpu-panel">',
        '<div class="cpu-search-bar">'
        '<div class="sb-group"><label>From</label>'
        '<input type="date" id="tbs-from">'
        '<button type="button" class="sb-cal-btn" onclick="document.getElementById(\'tbs-from\').showPicker()">'
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">'
        '<rect x="2" y="3" width="12" height="11" rx="2"/><path d="M2 7h12M5 1v3M11 1v3"/></svg></button>'
        '</div>'
        '<div class="sb-group"><label>To</label>'
        '<input type="date" id="tbs-to">'
        '<button type="button" class="sb-cal-btn" onclick="document.getElementById(\'tbs-to\').showPicker()">'
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">'
        '<rect x="2" y="3" width="12" height="11" rx="2"/><path d="M2 7h12M5 1v3M11 1v3"/></svg></button>'
        '</div>'
        '</div>',
        '<div class="cpu-header">',
        '<div class="cpu-header-left">',
        '<div class="cpu-range-info">'
        '<span class="ri-date" id="tbs-title-name" style="color:#6366F1;font-weight:700;"></span>'
        '</div></div></div>',
        '<div style="padding:14px 22px;">',
        '<div id="tbs-nodata" style="display:none;text-align:center;color:#94A3B8;padding:60px 0;font-size:.85rem;"></div>',
        '<canvas id="tbs-canvas" style="width:100%;height:360px;display:block;"></canvas>',
        '</div></div>',
        '<div id="tbs-tooltip" style="display:none;position:fixed;z-index:9999;background:#fff;'
        'border:1px solid #E2E8F0;border-radius:10px;padding:12px 16px;'
        'box-shadow:0 12px 32px rgba(0,0,0,.14);font-size:.78rem;pointer-events:none;min-width:180px;"></div>',
        _ts(), _view_css(), _cpu_chart_css(),
        '<script>',
        'var _apiBase="' + b + '";',
        '(function(){var now=new Date();'
        'var f=new Date(now.getTime()-29*86400000);'
        'document.getElementById("tbs-from").value=f.toISOString().slice(0,10);'
        'document.getElementById("tbs-to").value=now.toISOString().slice(0,10);})();',
        tbs_js,
        'function _tbsDateChange(){'
        '  var fd=document.getElementById("tbs-from").value;'
        '  var td=document.getElementById("tbs-to").value;'
        '  if(fd&&td){'
        '    var d1=new Date(fd),d2=new Date(td);'
        '    var diff=Math.round((d2-d1)/(86400000));'
        '    if(diff<0){document.getElementById("tbs-to").value=fd;}'
        '    else if(diff>31){'
        '      var max=new Date(d1.getTime()+31*86400000);'
        '      document.getElementById("tbs-to").value=max.toISOString().slice(0,10);'
        '    }'
        '  }'
        '  tbsQuery();'
        '}',
        'document.getElementById("tbs-from").addEventListener("change",_tbsDateChange);',
        'document.getElementById("tbs-to").addEventListener("change",_tbsDateChange);',
        'tbsQuery();',
        '</script>',
    ])
    return _history_page_or_embed(body, embed, active='disk_tbs')


# ── Service Status Page ───────────────────────────────────────────────────────

def page_history_process_status():
    from pages.history_page import _history_page
    if not _insp_table_exists('insp_service_history'):
        body = '<p class="page-title">Service Status History</p>' + _table_missing_html('INSP_SERVICE_HISTORY')
        return _history_page(body, active='process_status')
    b = _UTILS_BASE
    body = ''.join([
        _page_title_html('Service Status History', *_HELP.get('history_process_status', ('Service Status History', ''))),
        '<div class="card">',

        '<div class="cpu-search-bar" style="padding:0;border:none;background:transparent;margin-bottom:16px;">'
        '<button type="button" class="sb-arrow" onclick="_shiftDateInput(\'svc-sel-date\',-1)">&#8249;</button>'
        '<div class="sb-group">'
        '<label>Date</label>'
        '<input type="date" id="svc-sel-date">'
        '<button type="button" class="sb-cal-btn" onclick="document.getElementById(\'svc-sel-date\').showPicker()">'
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">'
        '<rect x="2" y="3" width="12" height="11" rx="2"/><path d="M2 7h12M5 1v3M11 1v3"/></svg></button>'
        '</div>'
        '<button type="button" class="sb-arrow" onclick="_shiftDateInput(\'svc-sel-date\',1)">&#8250;</button>'
        '<button class="sb-qbtn svc-qbtn" id="sqb-yesterday" onclick="_svcQuick(\'yesterday\')">Yesterday</button>'
        '<button class="sb-qbtn svc-qbtn active" id="sqb-today" onclick="_svcQuick(\'today\')">Today</button>'
        '</div>',
        '<div id="svc-area"><div style="color:var(--c-muted);font-size:.85rem;padding:30px 0;text-align:center;">Loading...</div></div>',
        '<div style="display:flex;justify-content:flex-end;gap:14px;align-items:center;font-size:.72rem;color:var(--c-muted);margin-top:12px;">',
        '<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#3ecf82;margin-right:4px;vertical-align:middle;"></span>RUNNING</span>',
        '<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#e05555;margin-right:4px;vertical-align:middle;"></span>STOPPED</span>',
        '<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#CBD5E1;margin-right:4px;vertical-align:middle;"></span>No Data</span>',
        '</div>',
        '</div>',
        '<div id="svc-tt" style="display:none;position:fixed;z-index:9999;background:#ffffff;'
        'border:1px solid #E2E8F0;border-radius:8px;padding:8px 14px;'
        'box-shadow:0 8px 24px rgba(0,0,0,.12);font-size:.78rem;pointer-events:none;min-width:140px;"></div>',
        _ts(), _view_css(), _cpu_chart_css(),
        '<script>',
        'var _apiBase="' + b + '";',
        'var LABEL_W=140,CELL_H=28,RULER_H=24,HOUR_GAP=2,R=3;',
        'var SC={RUNNING:"#3ecf82",OK:"#3ecf82",STOPPED:"#e05555",FAIL:"#e05555"};',
        'var _svcs=[],_svcData={},_cvsList=[],_hoverCol=null;',
        'document.getElementById("svc-sel-date").value=new Date().toISOString().slice(0,10);',
        """
function _svcQuick(mode){
  document.querySelectorAll(".svc-qbtn").forEach(function(b){b.classList.remove("active");});
  var now=new Date();
  if(mode==="yesterday"){
    now.setDate(now.getDate()-1);
    document.getElementById("sqb-yesterday").classList.add("active");
  }else{
    document.getElementById("sqb-today").classList.add("active");
  }
  document.getElementById("svc-sel-date").value=now.toISOString().slice(0,10);
  doQuery();
}
document.getElementById("svc-sel-date").addEventListener("change",function(){
  document.querySelectorAll(".svc-qbtn").forEach(function(b){b.classList.remove("active");});
  doQuery();
});
function pad(n){return n<10?'0'+n:''+n;}
function slotPos(i,W){
  var cw=(W-23*HOUR_GAP)/24;
  var x=i*(cw+HOUR_GAP);
  return {x:Math.round(x),w:Math.max(1,Math.round(x+cw)-Math.round(x))};
}
function xToSlot(mx,W){
  var cw=(W-23*HOUR_GAP)/24;
  var idx=Math.floor(mx/(cw+HOUR_GAP));
  return Math.max(0,Math.min(23,idx));
}
function lighten(hex,a){
  var r=parseInt(hex.slice(1,3),16),g=parseInt(hex.slice(3,5),16),b=parseInt(hex.slice(5,7),16);
  return 'rgb('+Math.min(255,r+a)+','+Math.min(255,g+a)+','+Math.min(255,b+a)+')';
}
function drawRow(ent){
  var cv=ent.canvas;var W=cv.width;if(!W)return;
  var ctx=cv.getContext('2d');
  ctx.clearRect(0,0,W,CELL_H);
  var emptyCol='#dde8f4';
  ent.cells.forEach(function(s,i){
    var pos=slotPos(i,W);
    var col=s?(SC[s]||'#64748b'):emptyCol;
    if(i===_hoverCol){
      ctx.fillStyle=s?lighten(SC[s]||'#64748b',30):'#b8d0e8';
    }else{
      ctx.fillStyle=col;
    }
    ctx.fillRect(pos.x,2,pos.w,CELL_H-4);
  });
}
function drawRuler(cv,pos){
  if(!cv||!cv.width)return;
  var W=cv.width;var ctx=cv.getContext('2d');
  ctx.clearRect(0,0,W,RULER_H);
  for(var h=0;h<24;h++){
    var sp=slotPos(h,W);
    var cx=sp.x+sp.w/2;
    ctx.fillStyle='rgba(30,41,59,0.3)';
    ctx.fillRect(sp.x,pos==='top'?RULER_H-6:0,1,6);
    ctx.font='bold 10px monospace';
    ctx.textAlign='center';ctx.textBaseline='middle';
    ctx.fillStyle='#334155';
    ctx.fillText(pad(h),cx,RULER_H/2);
  }
  if(_hoverCol!==null){
    var hp=slotPos(_hoverCol,W);
    ctx.fillStyle='rgba(60,100,200,0.12)';
    ctx.fillRect(hp.x,0,hp.w,RULER_H);
  }
}
function redrawAll(){
  _cvsList.forEach(function(ent){drawRow(ent);});
  if(_rulerTop)drawRuler(_rulerTop,'top');
  if(_rulerBot)drawRuler(_rulerBot,'bottom');
}
var _rulerTop=null,_rulerBot=null;
function initCanvasWidth(){
  _cvsList.forEach(function(ent){
    ent.canvas.width=ent.canvas.parentElement.offsetWidth;
  });
  if(_rulerTop)_rulerTop.width=_rulerTop.parentElement.offsetWidth;
  if(_rulerBot)_rulerBot.width=_rulerBot.parentElement.offsetWidth;
}
function makeRulerRow(pos){
  var row=document.createElement('div');row.style.cssText='display:flex;align-items:center;';
  var sp=document.createElement('div');sp.style.cssText='width:'+LABEL_W+'px;flex-shrink:0;';
  var wrap=document.createElement('div');wrap.style.cssText='flex:1;min-width:0;';
  var cv=document.createElement('canvas');cv.height=RULER_H;cv.style.cssText='width:100%;display:block;';
  wrap.appendChild(cv);row.appendChild(sp);row.appendChild(wrap);
  return {row:row,canvas:cv};
}
function doQuery(){
  var d=document.getElementById("svc-sel-date").value||new Date().toISOString().slice(0,10);
  fetch(_apiBase+"/api/history-service?date="+d)
  .then(function(r){return r.json();})
  .then(function(res){
    if(!res.ok){document.getElementById("svc-area").innerHTML='<div style="color:#94A3B8;text-align:center;padding:40px;">'+res.error+'</div>';return;}
    _svcs=res.services;_svcData=res.data;
    if(!_svcs.length){document.getElementById("svc-area").innerHTML='<div style="color:#94A3B8;text-align:center;padding:40px;">데이터 없음</div>';return;}
    buildChart();
  });
}
function buildChart(){
  var area=document.getElementById("svc-area");
  area.innerHTML='';
  _cvsList=[];_hoverCol=null;_rulerTop=null;_rulerBot=null;
  var outer=document.createElement('div');
  // Top ruler
  var tr=makeRulerRow('top');outer.appendChild(tr.row);_rulerTop=tr.canvas;
  // Rows
  _svcs.forEach(function(svc){
    var row=document.createElement('div');row.style.cssText='display:flex;align-items:center;margin-bottom:2px;';
    var lbl=document.createElement('div');
    lbl.style.cssText='width:'+LABEL_W+'px;flex-shrink:0;padding-right:14px;box-sizing:border-box;';
    var nm=document.createElement('div');
    nm.style.cssText='font-size:.78rem;font-weight:700;color:#0F172A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.3;';
    nm.title=svc;nm.textContent=svc;
    lbl.appendChild(nm);row.appendChild(lbl);
    var cvWrap=document.createElement('div');cvWrap.style.cssText='flex:1;min-width:0;border-radius:4px;overflow:hidden;';
    var cv=document.createElement('canvas');cv.height=CELL_H;cv.style.cssText='width:100%;display:block;cursor:crosshair;';
    cvWrap.appendChild(cv);row.appendChild(cvWrap);outer.appendChild(row);
    // Build hourly cells
    var hourMap={};
    (_svcData[svc]||[]).forEach(function(r){hourMap[parseInt(r.ts.slice(11,13))]=r.s;});
    var cells=[];for(var h=0;h<24;h++)cells.push(hourMap[h]||null);
    var ent={canvas:cv,cells:cells,svc:svc};
    _cvsList.push(ent);
    (function(ent){
      cv.addEventListener('mousemove',function(e){
        var W=ent.canvas.width;if(!W)return;
        var rect=ent.canvas.getBoundingClientRect();
        var mx=(e.clientX-rect.left)*(W/rect.width);
        var si=xToSlot(mx,W);
        if(si!==_hoverCol){_hoverCol=si;redrawAll();}
        var st=ent.cells[si];
        var stLabel=!st?'No Data':st;
        var stClr=st?(SC[st]||'#64748b'):'#CBD5E1';
        var tt=document.getElementById("svc-tt");
        tt.innerHTML='<div style="font-weight:700;color:#0F172A;margin-bottom:4px;">'+ent.svc+'</div>'
          +'<div style="display:flex;align-items:center;gap:6px;">'
          +'<div style="width:8px;height:8px;border-radius:2px;background:'+stClr+';"></div>'
          +'<span style="color:#64748B;">'+pad(si)+':00</span>'
          +'<span style="font-weight:700;color:'+stClr+';">'+stLabel+'</span></div>';
        tt.style.display='block';
        var tx=e.clientX+14,ty=e.clientY-50;
        if(tx+200>window.innerWidth)tx=e.clientX-210;
        if(ty<10)ty=e.clientY+20;
        tt.style.left=tx+'px';tt.style.top=ty+'px';
      });
      cv.addEventListener('mouseleave',function(){
        _hoverCol=null;redrawAll();
        document.getElementById("svc-tt").style.display='none';
      });
    })(ent);
  });
  // Bottom ruler
  var br=makeRulerRow('bottom');outer.appendChild(br.row);_rulerBot=br.canvas;
  area.appendChild(outer);
  initCanvasWidth();
  redrawAll();
}
window.addEventListener('resize',function(){initCanvasWidth();redrawAll();});
doQuery();
""",
        '</script>',
    ])
    return _history_page(body, active='process_status')


def page_history_process_qcnt():
    from pages.history_page import _history_page
    if not _insp_table_exists('insp_qcnt_history'):
        body = '<p class="page-title">Qcnt Trend</p>' + _table_missing_html('INSP_QCNT_HISTORY')
        return _history_page(body, active='process_qcnt')
    b = _UTILS_BASE
    body = ''.join([
        _page_title_html('Qcnt Trend', *_HELP.get('history_process_qcnt', ('Qcnt Trend', ''))),
        _view_css(), _cpu_chart_css(),
        '<style>'
        # [DESIGN-A] border-radius:12px → 0, border #E2E8F0 → #CBD5E1 (Inspector 톤).
        '.qc-panel{background:#ffffff;border:1px solid #CBD5E1;border-radius:0;'
        'overflow:hidden;margin-bottom:16px;}'
        '.qc-header{display:flex;align-items:center;justify-content:space-between;'
        'padding:10px 18px;border-bottom:1px solid #F1F5F9;background:#FAFBFC;}'
        '.qc-svc{font-size:.82rem;font-weight:700;color:#0F172A;display:flex;align-items:center;gap:8px;}'
        '.qc-svc-dot{width:12px;height:8px;border-radius:2px;}'
        '.qc-info{display:flex;align-items:center;gap:10px;}'
        '.qc-val{font-size:.78rem;font-weight:700;color:#64748B;font-variant-numeric:tabular-nums;}'
        '.qc-zoom-badge{display:none;align-items:center;gap:5px;padding:3px 10px;border-radius:6px;'
        'background:#EEF2FF;border:1px solid #C7D2FE;font-size:.7rem;font-weight:600;color:#4338CA;cursor:pointer;'
        'transition:all .15s;}'
        '.qc-zoom-badge:hover{background:#4338CA;color:#fff;}'
        '.qc-wrap{position:relative;padding:10px 12px 6px 12px;}'
        '.qc-cross{position:absolute;width:1px;border-left:1px dashed rgba(100,116,139,.4);'
        'pointer-events:none;z-index:2;display:none;}'
        '.qc-sel{position:absolute;background:rgba(99,102,241,.12);border-left:1px solid rgba(99,102,241,.4);'
        'border-right:1px solid rgba(99,102,241,.4);pointer-events:none;z-index:1;display:none;}'
        '#qc-tt{display:none;position:fixed;z-index:9999;background:#ffffff;'
        'border:1px solid #E2E8F0;border-radius:8px;padding:8px 12px;'
        'box-shadow:0 8px 24px rgba(0,0,0,.12);font-size:.76rem;pointer-events:none;}'
        '</style>',
        '<div class="cpu-panel" style="margin-bottom:16px;">',
        '<div class="cpu-search-bar">'
        '<button type="button" class="sb-arrow" onclick="_shiftDateInput(\'qcnt-date\',-1)">&#8249;</button>'
        '<div class="sb-group">'
        '<label>Date</label>'
        '<input type="date" id="qcnt-date">'
        '<button type="button" class="sb-cal-btn" onclick="document.getElementById(\'qcnt-date\').showPicker()">'
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">'
        '<rect x="2" y="3" width="12" height="11" rx="2"/><path d="M2 7h12M5 1v3M11 1v3"/></svg></button>'
        '</div>'
        '<button type="button" class="sb-arrow" onclick="_shiftDateInput(\'qcnt-date\',1)">&#8250;</button>'
        '<input type="hidden" id="qcnt-from" value="00:00">'
        '<input type="hidden" id="qcnt-to" value="23:59">'
        '<button class="sb-qbtn qcnt-qbtn" id="qb-am" onclick="_qQ(\'am\')">AM</button>'
        '<button class="sb-qbtn qcnt-qbtn" id="qb-pm" onclick="_qQ(\'pm\')">PM</button>'
        '<button class="sb-qbtn qcnt-qbtn active" id="qb-today" onclick="_qQ(\'today\')">Today</button>'
        '</div></div>',
        '<div id="qc-charts"></div>',
        '<div id="qc-tt"></div>',
        _ts(),
        '<script>',
        'var _qData={},_qSvcs=[],_apiBase="' + b + '";',
        'var QC=["#6366F1","#F59E0B","#10B981","#EF4444","#8B5CF6","#EC4899","#14B8A6","#F97316"];',
        'var _qZoomMap={},_qDrag=null,_qSync=[];',
        'document.getElementById("qcnt-date").value=new Date().toISOString().slice(0,10);',
        """
function _qQ(mode){
  document.querySelectorAll(".qcnt-qbtn").forEach(function(b){b.classList.remove("active");});
  var now=new Date();
  if(mode==="am"){
    document.getElementById("qcnt-from").value="00:00";
    document.getElementById("qcnt-to").value="11:59";
    document.getElementById("qb-am").classList.add("active");
  }else if(mode==="pm"){
    document.getElementById("qcnt-from").value="12:00";
    document.getElementById("qcnt-to").value="23:59";
    document.getElementById("qb-pm").classList.add("active");
  }else{
    document.getElementById("qcnt-from").value="00:00";
    document.getElementById("qcnt-to").value="23:59";
    document.getElementById("qb-today").classList.add("active");
  }
  document.getElementById("qcnt-date").value=now.toISOString().slice(0,10);
  doQuery();
}
document.getElementById("qcnt-date").addEventListener("change",function(){
  document.querySelectorAll(".qcnt-qbtn").forEach(function(b){b.classList.remove("active");});
  document.getElementById("qcnt-from").value="00:00";
  document.getElementById("qcnt-to").value="23:59";
  doQuery();
});
function doQuery(){
  _qZoomMap={};
  var d=document.getElementById("qcnt-date").value||new Date().toISOString().slice(0,10);
  var f=document.getElementById("qcnt-from").value||"00:00";
  var t=document.getElementById("qcnt-to").value||"23:59";
  fetch(_apiBase+"/api/history-qcnt?date="+d+"&from="+f+"&to="+t)
  .then(function(r){return r.json();})
  .then(function(res){
    if(!res.ok){document.getElementById("qc-charts").innerHTML='<div style="text-align:center;color:#94A3B8;padding:40px;">Error</div>';return;}
    _qSvcs=res.services;_qData=res.data;
    _buildCharts();
  });
}
function _buildCharts(){
  var wrap=document.getElementById("qc-charts");
  if(!_qSvcs.length){wrap.innerHTML='<div style="text-align:center;color:#94A3B8;padding:40px;">데이터 없음</div>';return;}
  var html='';
  _qSvcs.forEach(function(svc,si){
    var clr=QC[si%QC.length];
    html+='<div class="qc-panel" id="qcp-'+si+'">'
      +'<div class="qc-header">'
      +'<div class="qc-svc"><div class="qc-svc-dot" style="background:'+clr+';"></div>'+svc+'</div>'
      +'<div class="qc-info">'
      +'<div class="qc-zoom-badge" id="qcz-'+si+'" onclick="_qResetOne('+si+')">'
      +'<span id="qczr-'+si+'"></span> &times;</div>'
      +'<div class="qc-val" id="qcv-'+si+'">-</div>'
      +'</div></div>'
      +'<div class="qc-wrap" id="qcw-'+si+'">'
      +'<canvas id="qcc-'+si+'" style="width:100%;height:120px;display:block;cursor:crosshair;"></canvas>'
      +'<div class="qc-cross" id="qcx-'+si+'"></div>'
      +'<div class="qc-sel" id="qcs-'+si+'"></div>'
      +'</div></div>';
  });
  wrap.innerHTML=html;
  _qSvcs.forEach(function(svc,si){_drawOne(si);});
}
function _qResetOne(si){_qZoomMap[si]=null;_drawOne(si);var b=document.getElementById("qcz-"+si);if(b)b.style.display="none";}
function _drawOne(si){
  var svc=_qSvcs[si];
  var allPts=_qData[svc]||[];
  var zoom=_qZoomMap[si]||null;
  var pts=zoom?allPts.slice(zoom[0],zoom[1]+1):allPts;
  var canvas=document.getElementById("qcc-"+si);
  if(!canvas)return;
  var dpr=window.devicePixelRatio||1;
  var rect=canvas.getBoundingClientRect();
  var W=rect.width,H=rect.height;
  if(W<10||H<10)return;
  canvas.width=W*dpr;canvas.height=H*dpr;
  var ctx=canvas.getContext("2d");
  ctx.scale(dpr,dpr);
  var pad={top:6,right:12,bottom:22,left:36};
  var cW=W-pad.left-pad.right,cH=H-pad.top-pad.bottom;
  var clr=QC[si%QC.length];
  var wPadTop=10,wPadLeft=12;
  ctx.clearRect(0,0,W,H);
  var valEl=document.getElementById("qcv-"+si);
  if(pts.length&&valEl){var last=pts[pts.length-1];valEl.textContent="qcnt: "+last.qcnt+"  act: "+last.act+"  total: "+last.total;}
  if(!pts.length){ctx.fillStyle="#CBD5E1";ctx.font="12px sans-serif";ctx.textAlign="center";ctx.fillText("데이터 없음",W/2,H/2);return;}
  var n=pts.length;
  var yMax=1;pts.forEach(function(p){if(p.qcnt>yMax)yMax=p.qcnt;});
  yMax=Math.ceil(yMax*1.3)||10;
  ctx.strokeStyle="rgba(148,163,184,.12)";ctx.lineWidth=1;
  for(var yi=0;yi<=4;yi++){var yv=Math.round(yMax*yi/4);var yy=pad.top+cH-(yv/yMax)*cH;ctx.beginPath();ctx.moveTo(pad.left,yy);ctx.lineTo(pad.left+cW,yy);ctx.stroke();ctx.fillStyle="#334155";ctx.font="600 11px sans-serif";ctx.textAlign="right";ctx.fillText(yv,pad.left-4,yy+3);}
  function _qt2m(ts){return parseInt(ts.slice(11,13))*60+parseInt(ts.slice(14,16));}
  var qf=document.getElementById("qcnt-from"),qt=document.getElementById("qcnt-to");
  var qRMin=0,qRMax=1439;
  if(qf&&qt){qRMin=parseInt(qf.value.slice(0,2))*60+parseInt(qf.value.slice(3,5));qRMax=parseInt(qt.value.slice(0,2))*60+parseInt(qt.value.slice(3,5));}
  if(_qZoomMap[si]&&n>1){qRMin=_qt2m(pts[0].ts);qRMax=_qt2m(pts[n-1].ts);}
  var qSpan=qRMax-qRMin||1;
  function _qx(ts){return pad.left+((_qt2m(ts)-qRMin)/qSpan)*cW;}
  ctx.fillStyle="#334155";ctx.font="600 10px sans-serif";ctx.textAlign="center";
  var qTick=qSpan<=60?5:qSpan<=120?10:qSpan<=360?30:60;
  var qMaxT=Math.floor(cW/42);if(qMaxT<4)qMaxT=4;
  while(qSpan/qTick>qMaxT)qTick*=2;
  for(var m=Math.ceil(qRMin/qTick)*qTick;m<=qRMax;m+=qTick){var lx=pad.left+((m-qRMin)/qSpan)*cW;var lbl=qTick>=60?String(Math.floor(m/60)).padStart(2,"0")+":00":String(Math.floor(m/60)).padStart(2,"0")+":"+String(m%60).padStart(2,"0");ctx.fillText(lbl,lx,H-2);}
  if(n>0){
  var QGAP=2.5;
  var qSegs=[];var qc=[];for(var i=0;i<n;i++){if(qc.length&&_qt2m(pts[i].ts)-_qt2m(pts[qc[qc.length-1]].ts)>QGAP){qSegs.push(qc);qc=[];}qc.push(i);}if(qc.length)qSegs.push(qc);
  ctx.strokeStyle=clr;ctx.lineWidth=1.5;
  qSegs.forEach(function(seg){ctx.beginPath();for(var j=0;j<seg.length;j++){var k=seg[j],x=_qx(pts[k].ts),y=pad.top+cH-(pts[k].qcnt/yMax)*cH;if(j===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);}ctx.stroke();});
  ctx.globalAlpha=0.08;ctx.fillStyle=clr;
  qSegs.forEach(function(seg){ctx.beginPath();ctx.moveTo(_qx(pts[seg[0]].ts),pad.top+cH);for(var j=0;j<seg.length;j++){var k=seg[j];ctx.lineTo(_qx(pts[k].ts),pad.top+cH-(pts[k].qcnt/yMax)*cH);}ctx.lineTo(_qx(pts[seg[seg.length-1]].ts),pad.top+cH);ctx.closePath();ctx.fill();});
  ctx.globalAlpha=1.0;
  }
  var cross=document.getElementById("qcx-"+si);
  cross.style.top=(wPadTop+pad.top)+"px";cross.style.height=cH+"px";
  var sel=document.getElementById("qcs-"+si);
  sel.style.top=(wPadTop+pad.top)+"px";sel.style.height=cH+"px";
  var tt=document.getElementById("qc-tt");
  function mx2idx(e){var br=canvas.getBoundingClientRect();var mx=e.clientX-br.left;if(mx<pad.left)mx=pad.left;if(mx>pad.left+cW)mx=pad.left+cW;var hovMin=qRMin+((mx-pad.left)/cW)*qSpan;var best=0,bestD=99999;for(var k=0;k<n;k++){var d=Math.abs(_qt2m(pts[k].ts)-hovMin);if(d<bestD){bestD=d;best=k;}}return best;}
  function idx2x(idx){if(idx<0||idx>=n)return wPadLeft+pad.left;return wPadLeft+pad.left+((_qt2m(pts[idx].ts)-qRMin)/qSpan)*cW;}
  function time2x(m){return wPadLeft+pad.left+((m-qRMin)/qSpan)*cW;}
  _qSync[si]={cross:cross,time2x:time2x,rMin:qRMin,rMax:qRMax};
  function _qSyncOthers(timeMin){
    _qSync.forEach(function(s,j){if(j===si||!s)return;if(timeMin>=s.rMin&&timeMin<=s.rMax){s.cross.style.left=s.time2x(timeMin)+"px";s.cross.style.display="block";}else{s.cross.style.display="none";}});
  }
  function _qSyncHide(){
    _qSync.forEach(function(s,j){if(j===si||!s)return;s.cross.style.display="none";});
  }
  canvas.onmousedown=function(e){
    if(e.button!==0)return;
    _qDrag={si:si,startIdx:mx2idx(e),curIdx:mx2idx(e)};
    sel.style.display="block";
    var sx=idx2x(_qDrag.startIdx);
    sel.style.left=sx+"px";sel.style.width="0px";
  };
  canvas.onmousemove=function(e){
    var idx=mx2idx(e);
    if(_qDrag&&_qDrag.si===si){
      _qDrag.curIdx=idx;
      var x1=idx2x(Math.min(_qDrag.startIdx,_qDrag.curIdx));
      var x2=idx2x(Math.max(_qDrag.startIdx,_qDrag.curIdx));
      sel.style.left=x1+"px";sel.style.width=(x2-x1)+"px";
    }
    var br=canvas.getBoundingClientRect();
    var mx=e.clientX-br.left;
    if(mx<pad.left||mx>pad.left+cW){cross.style.display="none";tt.style.display="none";_qSyncHide();return;}
    cross.style.left=idx2x(idx)+"px";cross.style.display="block";
    _qSyncOthers(_qt2m(pts[idx].ts));
    var p=pts[idx];
    if(valEl)valEl.textContent="qcnt: "+p.qcnt+"  act: "+p.act+"  total: "+p.total;
    tt.innerHTML='<div style="font-weight:700;color:#0F172A;margin-bottom:4px;">'+p.ts.slice(11,16)+'</div>'
      +'<div style="display:flex;gap:12px;">'
      +'<span style="color:#64748B;">qcnt</span><span style="font-weight:700;color:'+clr+';">'+p.qcnt+'</span>'
      +'<span style="color:#64748B;">act</span><span style="font-weight:700;">'+p.act+'</span>'
      +'<span style="color:#64748B;">total</span><span style="font-weight:700;">'+p.total+'</span></div>';
    tt.style.display="block";
    var tx=e.clientX+14,ty=e.clientY-50;
    if(tx+220>window.innerWidth)tx=e.clientX-230;
    if(ty<10)ty=e.clientY+20;
    tt.style.left=tx+"px";tt.style.top=ty+"px";
  };
  canvas.onmouseup=function(e){
    if(!_qDrag||_qDrag.si!==si)return;
    sel.style.display="none";
    var i1=Math.min(_qDrag.startIdx,_qDrag.curIdx);
    var i2=Math.max(_qDrag.startIdx,_qDrag.curIdx);
    _qDrag=null;
    if(i2-i1<2)return;
    // Map visible indices back to allPts indices
    var ts1=pts[i1].ts,ts2=pts[i2].ts;
    var gi1=-1,gi2=-1;
    for(var k=0;k<allPts.length;k++){if(allPts[k].ts===ts1&&gi1<0)gi1=k;if(allPts[k].ts===ts2)gi2=k;}
    if(gi1<0)gi1=0;if(gi2<0)gi2=allPts.length-1;
    _qZoomMap[si]=[gi1,gi2];
    var badge=document.getElementById("qcz-"+si);
    var rangeEl=document.getElementById("qczr-"+si);
    if(badge){badge.style.display="inline-flex";}
    if(rangeEl){rangeEl.textContent=ts1.slice(11,16)+"~"+ts2.slice(11,16);}
    _drawOne(si);
  };
  canvas.onmouseleave=function(){
    cross.style.display="none";tt.style.display="none";_qSyncHide();
    if(_qDrag&&_qDrag.si===si){sel.style.display="none";_qDrag=null;}
    if(pts.length&&valEl){var last=pts[pts.length-1];valEl.textContent="qcnt: "+last.qcnt+"  act: "+last.act+"  total: "+last.total;}
  };
  canvas.ondblclick=function(){if(_qZoomMap[si]){_qResetOne(si);}};
}
window.addEventListener("resize",function(){_qSvcs.forEach(function(svc,si){_drawOne(si);});});
doQuery();
""",
        '</script>',
    ])
    return _history_page(body, active='process_qcnt')



# ── Heap Trend Page (placeholder) ────────────────────────────────────────────

def page_history_process_heap():
    from pages.history_page import _history_page
    if not _insp_table_exists('insp_heap_history'):
        body = '<p class="page-title">Heap Trend</p>' + _table_missing_html('INSP_HEAP_HISTORY')
        return _history_page(body, active='process_heap')
    b = _UTILS_BASE
    body = ''.join([
        _page_title_html('Heap Trend', *_HELP.get('history_process_heap', ('Heap Trend', ''))),
        _view_css(), _cpu_chart_css(),
        '<style>'
        # [DESIGN-A] border-radius:12px → 0, border #E2E8F0 → #CBD5E1 (Inspector 톤).
        '.hp-panel{background:#ffffff;border:1px solid #CBD5E1;border-radius:0;'
        'overflow:hidden;margin-bottom:16px;}'
        '.hp-header{display:flex;align-items:center;justify-content:space-between;'
        'padding:10px 18px;border-bottom:1px solid #F1F5F9;background:#FAFBFC;}'
        '.hp-svc{font-size:.82rem;font-weight:700;color:#0F172A;display:flex;align-items:center;gap:8px;}'
        '.hp-svc-dot{width:12px;height:8px;border-radius:2px;}'
        '.hp-info{display:flex;align-items:center;gap:10px;}'
        '.hp-val{font-size:.78rem;font-weight:700;color:#64748B;font-variant-numeric:tabular-nums;}'
        '.hp-zoom-badge{display:none;align-items:center;gap:5px;padding:3px 10px;border-radius:6px;'
        'background:#EEF2FF;border:1px solid #C7D2FE;font-size:.7rem;font-weight:600;color:#4338CA;cursor:pointer;'
        'transition:all .15s;}'
        '.hp-zoom-badge:hover{background:#4338CA;color:#fff;}'
        '.hp-wrap{position:relative;padding:10px 12px 6px 12px;}'
        '.hp-cross{position:absolute;width:1px;border-left:1px dashed rgba(100,116,139,.4);'
        'pointer-events:none;z-index:2;display:none;}'
        '.hp-sel{position:absolute;background:rgba(99,102,241,.12);border-left:1px solid rgba(99,102,241,.4);'
        'border-right:1px solid rgba(99,102,241,.4);pointer-events:none;z-index:1;display:none;}'
        '#hp-tt{display:none;position:fixed;z-index:9999;background:#ffffff;'
        'border:1px solid #E2E8F0;border-radius:8px;padding:8px 12px;'
        'box-shadow:0 8px 24px rgba(0,0,0,.12);font-size:.76rem;pointer-events:none;}'
        '</style>',
        '<div class="cpu-panel" style="margin-bottom:16px;">',
        '<div class="cpu-search-bar">'
        '<button type="button" class="sb-arrow" onclick="_shiftDateInput(\'hp-date\',-1)">&#8249;</button>'
        '<div class="sb-group">'
        '<label>Date</label>'
        '<input type="date" id="hp-date">'
        '<button type="button" class="sb-cal-btn" onclick="document.getElementById(\'hp-date\').showPicker()">'
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">'
        '<rect x="2" y="3" width="12" height="11" rx="2"/><path d="M2 7h12M5 1v3M11 1v3"/></svg></button>'
        '</div>'
        '<button type="button" class="sb-arrow" onclick="_shiftDateInput(\'hp-date\',1)">&#8250;</button>'
        '<input type="hidden" id="hp-from" value="00:00">'
        '<input type="hidden" id="hp-to" value="23:59">'
        '<button class="sb-qbtn hp-qbtn" id="hqb-am" onclick="_hQ(\'am\')">AM</button>'
        '<button class="sb-qbtn hp-qbtn" id="hqb-pm" onclick="_hQ(\'pm\')">PM</button>'
        '<button class="sb-qbtn hp-qbtn active" id="hqb-today" onclick="_hQ(\'today\')">Today</button>'
        '</div></div>',
        '<div id="hp-charts"></div>',
        '<div id="hp-tt"></div>',
        _ts(),
        '<script>',
        'var _hData={},_hSvcs=[],_hApiBase="' + b + '";',
        'var HC=["#8B5CF6","#06B6D4","#F97316","#10B981","#EF4444","#EC4899","#6366F1","#F59E0B"];',
        'var _hZoomMap={},_hDrag=null,_hSync=[];',
        'document.getElementById("hp-date").value=new Date().toISOString().slice(0,10);',
        """
function _hQ(mode){
  document.querySelectorAll(".hp-qbtn").forEach(function(b){b.classList.remove("active");});
  var now=new Date();
  if(mode==="am"){
    document.getElementById("hp-from").value="00:00";
    document.getElementById("hp-to").value="11:59";
    document.getElementById("hqb-am").classList.add("active");
  }else if(mode==="pm"){
    document.getElementById("hp-from").value="12:00";
    document.getElementById("hp-to").value="23:59";
    document.getElementById("hqb-pm").classList.add("active");
  }else{
    document.getElementById("hp-from").value="00:00";
    document.getElementById("hp-to").value="23:59";
    document.getElementById("hqb-today").classList.add("active");
  }
  document.getElementById("hp-date").value=now.toISOString().slice(0,10);
  hDoQuery();
}
document.getElementById("hp-date").addEventListener("change",function(){
  document.querySelectorAll(".hp-qbtn").forEach(function(b){b.classList.remove("active");});
  document.getElementById("hp-from").value="00:00";
  document.getElementById("hp-to").value="23:59";
  hDoQuery();
});
function hDoQuery(){
  _hZoomMap={};
  var d=document.getElementById("hp-date").value||new Date().toISOString().slice(0,10);
  var f=document.getElementById("hp-from").value||"00:00";
  var t=document.getElementById("hp-to").value||"23:59";
  fetch(_hApiBase+"/api/history-heap?date="+d+"&from="+f+"&to="+t)
  .then(function(r){return r.json();})
  .then(function(res){
    if(!res.ok){document.getElementById("hp-charts").innerHTML='<div style="text-align:center;color:#94A3B8;padding:40px;">Error</div>';return;}
    _hSvcs=res.services;_hData=res.data;
    _hBuild();
  });
}
function _hBuild(){
  var wrap=document.getElementById("hp-charts");
  if(!_hSvcs.length){wrap.innerHTML='<div style="text-align:center;color:#94A3B8;padding:40px;">데이터 없음</div>';return;}
  var html='';
  _hSvcs.forEach(function(svc,si){
    var clr=HC[si%HC.length];
    html+='<div class="hp-panel" id="hpp-'+si+'">'
      +'<div class="hp-header">'
      +'<div class="hp-svc"><div class="hp-svc-dot" style="background:'+clr+';"></div>'+svc+'</div>'
      +'<div class="hp-info">'
      +'<div class="hp-zoom-badge" id="hpz-'+si+'" onclick="_hResetOne('+si+')">'
      +'<span id="hpzr-'+si+'"></span> &times;</div>'
      +'<div class="hp-val" id="hpv-'+si+'">-</div>'
      +'</div></div>'
      +'<div class="hp-wrap" id="hpw-'+si+'">'
      +'<canvas id="hpc-'+si+'" style="width:100%;height:160px;display:block;cursor:crosshair;"></canvas>'
      +'<div class="hp-cross" id="hpx-'+si+'"></div>'
      +'<div class="hp-sel" id="hps-'+si+'"></div>'
      +'</div></div>';
  });
  wrap.innerHTML=html;
  _hSvcs.forEach(function(svc,si){_hDrawOne(si);});
}
function _hResetOne(si){_hZoomMap[si]=null;_hDrawOne(si);var b=document.getElementById("hpz-"+si);if(b)b.style.display="none";}
function _hDrawOne(si){
  var svc=_hSvcs[si];
  var allPts=_hData[svc]||[];
  var zoom=_hZoomMap[si]||null;
  var pts=zoom?allPts.slice(zoom[0],zoom[1]+1):allPts;
  var canvas=document.getElementById("hpc-"+si);
  if(!canvas)return;
  var dpr=window.devicePixelRatio||1;
  var rect=canvas.getBoundingClientRect();
  var W=rect.width,H=rect.height;
  if(W<10||H<10)return;
  canvas.width=W*dpr;canvas.height=H*dpr;
  var ctx=canvas.getContext("2d");
  ctx.scale(dpr,dpr);
  var pad={top:6,right:12,bottom:22,left:58};
  var cW=W-pad.left-pad.right,cH=H-pad.top-pad.bottom;
  var clr=HC[si%HC.length];
  var wPadTop=10,wPadLeft=12;
  ctx.clearRect(0,0,W,H);
  var valEl=document.getElementById("hpv-"+si);
  if(pts.length&&valEl){var _hSum=0;pts.forEach(function(p){_hSum+=p.used;});var _hAvg=Math.round(_hSum/pts.length);valEl.textContent="Heap: "+pts[pts.length-1].used+"/"+pts[pts.length-1].alloc+" MB (avg "+_hAvg+")";}
  if(!pts.length){ctx.fillStyle="#CBD5E1";ctx.font="12px sans-serif";ctx.textAlign="center";ctx.fillText("데이터 없음",W/2,H/2);return;}
  var n=pts.length;
  // Y: max alloc across all points
  var yMax=1;pts.forEach(function(p){var v=Math.max(p.used,p.alloc);if(v>yMax)yMax=v;});
  yMax=Math.ceil(yMax*1.15)||100;
  // Grid
  ctx.strokeStyle="rgba(148,163,184,.12)";ctx.lineWidth=1;
  for(var yi=0;yi<=4;yi++){var yv=Math.round(yMax*yi/4);var yy=pad.top+cH-(yv/yMax)*cH;ctx.beginPath();ctx.moveTo(pad.left,yy);ctx.lineTo(pad.left+cW,yy);ctx.stroke();ctx.fillStyle="#334155";ctx.font="600 11px sans-serif";ctx.textAlign="right";ctx.fillText(yv+"MB",pad.left-4,yy+3);}
  // X labels
  function _ht2m(ts){return parseInt(ts.slice(11,13))*60+parseInt(ts.slice(14,16));}
  var hpf=document.getElementById("hp-from"),hpt=document.getElementById("hp-to");
  var hRMin=0,hRMax=1439;
  if(hpf&&hpt){hRMin=parseInt(hpf.value.slice(0,2))*60+parseInt(hpf.value.slice(3,5));hRMax=parseInt(hpt.value.slice(0,2))*60+parseInt(hpt.value.slice(3,5));}
  if(_hZoomMap[si]&&n>1){hRMin=_ht2m(pts[0].ts);hRMax=_ht2m(pts[n-1].ts);}
  var hSpan=hRMax-hRMin||1;
  function _hx(ts){return pad.left+((_ht2m(ts)-hRMin)/hSpan)*cW;}
  ctx.fillStyle="#334155";ctx.font="600 10px sans-serif";ctx.textAlign="center";
  var hTick=hSpan<=60?5:hSpan<=120?10:hSpan<=360?30:60;
  var hMaxT=Math.floor(cW/42);if(hMaxT<4)hMaxT=4;
  while(hSpan/hTick>hMaxT)hTick*=2;
  for(var m=Math.ceil(hRMin/hTick)*hTick;m<=hRMax;m+=hTick){var lx=pad.left+((m-hRMin)/hSpan)*cW;var lbl=hTick>=60?String(Math.floor(m/60)).padStart(2,"0")+":00":String(Math.floor(m/60)).padStart(2,"0")+":"+String(m%60).padStart(2,"0");ctx.fillText(lbl,lx,H-2);}
  // Alloc line (dashed, lighter) + Used line — gap-aware
  if(n>0){
  var HGAP=2.5;
  var hSegs=[];var hc=[];for(var i=0;i<n;i++){if(hc.length&&_ht2m(pts[i].ts)-_ht2m(pts[hc[hc.length-1]].ts)>HGAP){hSegs.push(hc);hc=[];}hc.push(i);}if(hc.length)hSegs.push(hc);
  ctx.strokeStyle="rgba(239,68,68,.5)";ctx.lineWidth=1;ctx.setLineDash([4,3]);
  hSegs.forEach(function(seg){ctx.beginPath();for(var j=0;j<seg.length;j++){var k=seg[j],x=_hx(pts[k].ts),y=pad.top+cH-(pts[k].alloc/yMax)*cH;if(j===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);}ctx.stroke();});
  ctx.setLineDash([]);
  ctx.strokeStyle=clr;ctx.lineWidth=1.5;
  hSegs.forEach(function(seg){ctx.beginPath();for(var j=0;j<seg.length;j++){var k=seg[j],x=_hx(pts[k].ts),y=pad.top+cH-(pts[k].used/yMax)*cH;if(j===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);}ctx.stroke();});
  ctx.globalAlpha=0.08;ctx.fillStyle=clr;
  hSegs.forEach(function(seg){ctx.beginPath();ctx.moveTo(_hx(pts[seg[0]].ts),pad.top+cH);for(var j=0;j<seg.length;j++){var k=seg[j];ctx.lineTo(_hx(pts[k].ts),pad.top+cH-(pts[k].used/yMax)*cH);}ctx.lineTo(_hx(pts[seg[seg.length-1]].ts),pad.top+cH);ctx.closePath();ctx.fill();});
  ctx.globalAlpha=1.0;
  }
  // Crosshair + selection
  var cross=document.getElementById("hpx-"+si);
  cross.style.top=(wPadTop+pad.top)+"px";cross.style.height=cH+"px";
  var sel=document.getElementById("hps-"+si);
  sel.style.top=(wPadTop+pad.top)+"px";sel.style.height=cH+"px";
  var tt=document.getElementById("hp-tt");
  function mx2idx(e){var br=canvas.getBoundingClientRect();var mx=e.clientX-br.left;if(mx<pad.left)mx=pad.left;if(mx>pad.left+cW)mx=pad.left+cW;var hovMin=hRMin+((mx-pad.left)/cW)*hSpan;var best=0,bestD=99999;for(var k=0;k<n;k++){var d=Math.abs(_ht2m(pts[k].ts)-hovMin);if(d<bestD){bestD=d;best=k;}}return best;}
  function idx2x(idx){if(idx<0||idx>=n)return wPadLeft+pad.left;return wPadLeft+pad.left+((_ht2m(pts[idx].ts)-hRMin)/hSpan)*cW;}
  function hTime2x(m){return wPadLeft+pad.left+((m-hRMin)/hSpan)*cW;}
  _hSync[si]={cross:cross,time2x:hTime2x,rMin:hRMin,rMax:hRMax};
  function _hSyncOthers(timeMin){
    _hSync.forEach(function(s,j){if(j===si||!s)return;if(timeMin>=s.rMin&&timeMin<=s.rMax){s.cross.style.left=s.time2x(timeMin)+"px";s.cross.style.display="block";}else{s.cross.style.display="none";}});
  }
  function _hSyncHide(){
    _hSync.forEach(function(s,j){if(j===si||!s)return;s.cross.style.display="none";});
  }
  canvas.onmousedown=function(e){
    if(e.button!==0)return;
    _hDrag={si:si,startIdx:mx2idx(e),curIdx:mx2idx(e)};
    sel.style.display="block";sel.style.left=idx2x(_hDrag.startIdx)+"px";sel.style.width="0px";
  };
  canvas.onmousemove=function(e){
    var idx=mx2idx(e);
    if(_hDrag&&_hDrag.si===si){
      _hDrag.curIdx=idx;
      var x1=idx2x(Math.min(_hDrag.startIdx,_hDrag.curIdx));
      var x2=idx2x(Math.max(_hDrag.startIdx,_hDrag.curIdx));
      sel.style.left=x1+"px";sel.style.width=(x2-x1)+"px";
    }
    var br=canvas.getBoundingClientRect();
    var mx=e.clientX-br.left;
    if(mx<pad.left||mx>pad.left+cW){cross.style.display="none";tt.style.display="none";_hSyncHide();return;}
    cross.style.left=idx2x(idx)+"px";cross.style.display="block";
    _hSyncOthers(_ht2m(pts[idx].ts));
    var p=pts[idx];
    if(valEl){var _hS2=0;pts.forEach(function(q){_hS2+=q.used;});var _hA2=Math.round(_hS2/pts.length);valEl.textContent="Heap: "+p.used+"/"+p.alloc+" MB (avg "+_hA2+")";}
    tt.innerHTML='<div style="font-weight:700;color:#0F172A;margin-bottom:4px;">'+p.ts.slice(11,16)+'</div>'
      +'<div style="display:flex;gap:12px;">'
      +'<span style="color:#64748B;">used</span><span style="font-weight:700;color:'+clr+';">'+p.used+' MB</span>'
      +'<span style="color:#64748B;">alloc</span><span style="font-weight:700;">'+p.alloc+'</span>'
      +'<span style="color:#64748B;">max</span><span style="font-weight:700;">'+p.max+'</span></div>';
    tt.style.display="block";
    var tx=e.clientX+14,ty=e.clientY-50;
    if(tx+240>window.innerWidth)tx=e.clientX-250;
    if(ty<10)ty=e.clientY+20;
    tt.style.left=tx+"px";tt.style.top=ty+"px";
  };
  canvas.onmouseup=function(e){
    if(!_hDrag||_hDrag.si!==si)return;
    sel.style.display="none";
    var i1=Math.min(_hDrag.startIdx,_hDrag.curIdx);
    var i2=Math.max(_hDrag.startIdx,_hDrag.curIdx);
    _hDrag=null;
    if(i2-i1<2)return;
    var ts1=pts[i1].ts,ts2=pts[i2].ts;
    var gi1=-1,gi2=-1;
    for(var k=0;k<allPts.length;k++){if(allPts[k].ts===ts1&&gi1<0)gi1=k;if(allPts[k].ts===ts2)gi2=k;}
    if(gi1<0)gi1=0;if(gi2<0)gi2=allPts.length-1;
    _hZoomMap[si]=[gi1,gi2];
    var badge=document.getElementById("hpz-"+si);
    var rangeEl=document.getElementById("hpzr-"+si);
    if(badge)badge.style.display="inline-flex";
    if(rangeEl)rangeEl.textContent=ts1.slice(11,16)+"~"+ts2.slice(11,16);
    _hDrawOne(si);
  };
  canvas.onmouseleave=function(){
    cross.style.display="none";tt.style.display="none";_hSyncHide();
    if(_hDrag&&_hDrag.si===si){sel.style.display="none";_hDrag=null;}
    if(pts.length&&valEl){var _hS3=0;pts.forEach(function(q){_hS3+=q.used;});var _hA3=Math.round(_hS3/pts.length);valEl.textContent="Heap: "+pts[pts.length-1].used+"/"+pts[pts.length-1].alloc+" MB (avg "+_hA3+")";}
  };
  canvas.ondblclick=function(){if(_hZoomMap[si]){_hResetOne(si);}};
}
window.addEventListener("resize",function(){_hSvcs.forEach(function(svc,si){_hDrawOne(si);});});
hDoQuery();
""",
        '</script>',
    ])
    return _history_page(body, active='process_heap')



# ── Line Chart JS (used by Memory page) ──────────────────────────────────────

def _line_chart_js():
    return '''
function drawLineChart(canvasId,legendId,data,series,unit,yMin,yMax){
  var canvas=document.getElementById(canvasId);
  var dpr=window.devicePixelRatio||1;
  var rect=canvas.getBoundingClientRect();
  canvas.width=rect.width*dpr;
  canvas.height=rect.height*dpr;
  var ctx=canvas.getContext("2d");
  ctx.scale(dpr,dpr);
  var W=rect.width,H=rect.height;
  var pad={top:10,right:20,bottom:32,left:42};
  var cW=W-pad.left-pad.right, cH=H-pad.top-pad.bottom;

  var lg=document.getElementById(legendId);
  lg.innerHTML="";
  series.forEach(function(s){
    lg.innerHTML+='<div class="legend-item"><div class="legend-dot" style="background:'+s.color+';"></div>'+s.label+'</div>';
  });

  ctx.clearRect(0,0,W,H);

  ctx.strokeStyle="rgba(148,163,184,.15)";ctx.lineWidth=1;
  var ySteps=[0,25,50,75,100];
  ySteps.forEach(function(v){
    var y=pad.top+cH-(v-yMin)/(yMax-yMin)*cH;
    ctx.beginPath();ctx.moveTo(pad.left,y);ctx.lineTo(pad.left+cW,y);ctx.stroke();
    ctx.fillStyle="#334155";ctx.font="600 11px sans-serif";ctx.textAlign="right";
    ctx.fillText(v+unit,pad.left-6,y+4);
  });

  var n=data.length;
  var mf=document.getElementById("msel-from"),mt=document.getElementById("msel-to");
  var rMin=0,rMax=1439;
  if(mf&&mt){rMin=parseInt(mf.value.slice(0,2))*60+parseInt(mf.value.slice(3,5));rMax=parseInt(mt.value.slice(0,2))*60+parseInt(mt.value.slice(3,5));}
  var rSpan=rMax-rMin||1;
  function _lc_t2m(ts){return parseInt(ts.slice(11,13))*60+parseInt(ts.slice(14,16));}
  function _lc_x(ts){return pad.left+((_lc_t2m(ts)-rMin)/rSpan)*cW;}
  // X labels: hourly
  ctx.fillStyle="#334155";ctx.font="600 10px sans-serif";ctx.textAlign="center";
  var lcTick=rSpan<=60?5:rSpan<=120?10:rSpan<=360?30:60;
  var lcMaxT=Math.floor(cW/50);if(lcMaxT<4)lcMaxT=4;
  while(rSpan/lcTick>lcMaxT)lcTick*=2;
  for(var m=Math.ceil(rMin/lcTick)*lcTick;m<=rMax;m+=lcTick){
    var x=pad.left+((m-rMin)/rSpan)*cW;
    var lbl=lcTick>=60?String(Math.floor(m/60)).padStart(2,"0")+":00":String(Math.floor(m/60)).padStart(2,"0")+":"+String(m%60).padStart(2,"0");
    ctx.fillText(lbl,x,H-pad.bottom+16);
  }
  if(n<1)return;

  series.forEach(function(s){
    if(s.yAxis==="right")return;
    ctx.strokeStyle=s.color;ctx.lineWidth=1.5;
    ctx.beginPath();
    var first=true;
    for(var i=0;i<n;i++){
      var v=data[i][s.key];
      if(v===null||v===undefined)continue;
      var x=_lc_x(data[i].ts);
      var y=pad.top+cH-(v-yMin)/(yMax-yMin)*cH;
      if(first){ctx.moveTo(x,y);first=false;}
      else ctx.lineTo(x,y);
    }
    ctx.stroke();
  });

  var wrap=canvas.parentNode;
  var crossId=canvasId+"-cross";
  var cross=document.getElementById(crossId);
  var cTop=canvas.offsetTop+pad.top;
  if(!cross){
    cross=document.createElement("div");cross.id=crossId;
    cross.style.cssText="position:absolute;width:1px;"
      +"border-left:1px dashed rgba(148,163,184,.35);pointer-events:none;z-index:1;display:none;";
    wrap.style.position="relative";wrap.appendChild(cross);
  }
  cross.style.top=cTop+"px";cross.style.height=cH+"px";

  var tt=document.getElementById("chart-tooltip");
  canvas.onmousemove=function(e){
    var br=canvas.getBoundingClientRect();
    var mx=e.clientX-br.left;
    if(mx<pad.left||mx>pad.left+cW){tt.style.display="none";cross.style.display="none";return;}
    var hovMin=rMin+((mx-pad.left)/cW)*rSpan;
    var idx=0,bestD=99999;for(var ii=0;ii<n;ii++){var dd=Math.abs(_lc_t2m(data[ii].ts)-hovMin);if(dd<bestD){bestD=dd;idx=ii;}}
    var d=data[idx];
    var html="<div style='font-weight:700;margin-bottom:4px;'>"+d.ts.slice(11,16)+"</div>";
    series.forEach(function(s){
      var v=d[s.key];
      if(v===null||v===undefined)v="-";
      else v=typeof v==="number"?v.toFixed(1):""+v;
      html+="<div style='color:"+s.color+";'>"+s.label+": <b>"+v+unit+"</b></div>";
    });
    tt.innerHTML=html;
    tt.style.display="block";
    tt.style.left=(e.clientX+14)+"px";
    tt.style.top=(e.clientY+14)+"px";
    var cx=canvas.offsetLeft+pad.left+((_lc_t2m(data[idx].ts)-rMin)/rSpan)*cW;
    cross.style.left=cx+"px";cross.style.display="block";
  };
  canvas.onmouseleave=function(){tt.style.display="none";cross.style.display="none";};
}
'''


