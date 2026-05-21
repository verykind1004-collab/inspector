# -*- coding: utf-8 -*-
import os
import re

from service_config import load_service_config
from db_utils import run_db_query, _parse_db_table, _sql_embed
from sql_library import _get_sql
from system_utils import _xml_val
from html_helpers import (
    _warn_box, _page_title_html, _page, _HELP, _HELP_JS, _ts,
    _render_db_table_html,
)


# [DB 10MIN SUMMARY] server_id=N 라인 매처. 라인 앞 시각 HH:MM:SS.xxx 가 group(1),
# server_id 가 group(2). 활성 .log 1개만 보면 그 안의 시각은 모두 같은 날짜라
# HH:MM:SS 문자열 비교로 정렬 가능.
_DGS_SUMMARY_LINE_RE = re.compile(
    r'^\[(\d{2}:\d{2}:\d{2}\.\d+)\].*?\[DB 10MIN SUMMARY\] server_id=(\d+)'
)


def _get_dgs_port_map():
    """Return {db_id_str: gather_port_str} by scanning DGServer_S active log files.

    꼬임 방지: server_id 가 여러 DGS_S 로그에 나타나면, 라인 시각이 가장 늦은
    DGS_S 의 gather_port 를 채택 (현재 어디 붙어있는지 반영).

    - DGServer_M 은 스캔하지 않음.
    - zip 회전된 일자별 과거 로그도 보지 않음 (활성 .log 만).
    - 로그 디렉터리 source: service_config.json `log_paths.dgserver_s[]`.
    - DGServer.xml(gather_port) 추출 source: services.dgserver_s[i]/conf/DGServer.xml.
    """
    svc       = load_service_config()
    services  = svc.get('services', {})
    log_paths = svc.get('log_paths', {})

    s_homes = services.get('dgserver_s', []) or []
    s_logs  = log_paths.get('dgserver_s', []) or []
    entries = []
    for i, dgs_home in enumerate(s_homes):
        if not dgs_home:
            continue
        dgs_log = s_logs[i] if i < len(s_logs) else ''
        if not dgs_log:
            continue
        entries.append((dgs_home, dgs_log))

    # per_sid_latest[sid] = (last_seen_HHMMSS, port)
    per_sid_latest = {}

    for home, log_dir in entries:
        try:
            xmlfile = os.path.join(home, 'conf', 'DGServer.xml')
            port    = _xml_val(xmlfile, 'gather_port')
            if not port:
                continue
            logfile = os.path.join(log_dir, 'DGS_' + port + '.log')
            if not os.path.exists(logfile):
                candidates = [f for f in os.listdir(log_dir)
                              if f.startswith('DGS_') and f.endswith('.log')] if os.path.isdir(log_dir) else []
                if not candidates:
                    continue
                candidates.sort(key=lambda f: os.path.getmtime(os.path.join(log_dir, f)), reverse=True)
                logfile = os.path.join(log_dir, candidates[0])

            # 이 DGS_S 활성 로그 안에서 sid -> 마지막 등장 시각(파일 끝쪽 = 더 늦은 시각)
            last_by_sid = {}
            try:
                with open(logfile, 'r', errors='replace') as lf:
                    for line in lf:
                        m = _DGS_SUMMARY_LINE_RE.match(line)
                        if m:
                            last_by_sid[m.group(2)] = m.group(1)
            except Exception:
                continue

            for sid, t in last_by_sid.items():
                prev = per_sid_latest.get(sid)
                if prev is None or t > prev[0]:
                    per_sid_latest[sid] = (t, port)
        except Exception:
            continue

    return {sid: tup[1] for sid, tup in per_sid_latest.items()}


def page_license():
    title = 'Instance List'
    sub   = 'Registered instances from apm_db_info'
    sql   = _get_sql('license')
    if not sql:
        body = _page_title_html(title, *_HELP.get('license', (title, ''))) + _warn_box('쿼리를 사용할 수 없습니다.')
        return _page('license', title, body)
    out, err = run_db_query(sql)
    if err:
        body = _page_title_html(title, *_HELP.get('license', (title, ''))) + _warn_box(err)
        return _page('license', title, body)
    headers, rows = _parse_db_table(out or '')

    dgs_map = {}
    try:
        dgs_map = _get_dgs_port_map()
    except Exception:
        pass

    idx_dbid = next((i for i, h in enumerate(headers) if h.upper().replace(' ', '_') in ('DB_ID', 'DB ID')), 0)
    idx_sid  = next((i for i, h in enumerate(headers) if h.upper() == 'SID'), 2)
    insert_at    = idx_sid + 1
    new_headers  = list(headers[:insert_at]) + ['DGS PORT'] + list(headers[insert_at:])
    new_rows     = []
    for row in rows:
        row_list   = list(row)
        db_id_val  = row_list[idx_dbid].strip() if 0 <= idx_dbid < len(row_list) else ''
        dgs_port   = dgs_map.get(db_id_val, '-')
        new_rows.append(row_list[:insert_at] + [dgs_port] + row_list[insert_at:])

    idx_dgs_in_new  = insert_at
    idx_dbid_in_new = idx_dbid

    def _sort_key(r):
        # db_id 오름차순 (정수 변환 실패 시 맨 뒤로).
        d = r[idx_dbid_in_new] if idx_dbid_in_new < len(r) else ''
        try:
            return int(d)
        except Exception:
            return 10 ** 9

    new_rows.sort(key=_sort_key)
    content_html = _render_db_table_html(new_headers, new_rows)
    content_html = content_html.replace('<table class="svc-table">', '<table class="svc-table" id="inst-tbl">', 1)

    _SVG_LAYERS = (
        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
        ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polygon points="12 2 2 7 12 12 22 7 12 2"/>'
        '<polyline points="2 17 12 22 22 17"/>'
        '<polyline points="2 12 12 17 22 12"/>'
        '</svg>'
    )
    _SVG_CHEVRON = (
        '<svg id="dgs-chv" width="11" height="11" viewBox="0 0 24 24" fill="none"'
        ' stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"'
        ' style="transition:transform .2s;flex-shrink:0;">'
        '<polyline points="6 9 12 15 18 9"/>'
        '</svg>'
    )

    filter_ui = (
        '<div style="display:flex;justify-content:space-between;align-items:center;'
        'margin-bottom:14px;gap:12px;flex-wrap:wrap;">'
        '<div style="position:relative;display:inline-block;">'
        '<input id="inst-srch" type="text" placeholder="Search instance name..."'
        ' autocomplete="off" oninput="instFilter();_instXToggle();"'
        ' style="background:#ffffff;border:1px solid var(--bd);color:var(--c-main);'
        'border-radius:8px;padding:7px 28px 7px 12px;font-size:.82rem;width:240px;outline:none;'
        'transition:border-color .15s;"'
        ' onfocus="this.style.borderColor=\'var(--c-accent)\'"'
        ' onblur="this.style.borderColor=\'var(--bd)\'">'
        '<span id="inst-x" onclick="document.getElementById(\'inst-srch\').value=\'\';instFilter();_instXToggle();"'
        ' style="display:none;position:absolute;right:8px;top:50%;transform:translateY(-50%);'
        'cursor:pointer;color:#94A3B8;font-size:.85rem;line-height:1;padding:2px;"'
        ' onmouseover="this.style.color=\'#334155\'" onmouseout="this.style.color=\'#94A3B8\'"'
        '>&#x2715;</span>'
        '<div id="inst-sugg" style="display:none;position:absolute;top:calc(100%% + 4px);left:0;'
        'background:var(--bg-card);border:1px solid var(--bd);border-radius:8px;'
        'min-width:240px;max-height:200px;overflow-y:auto;z-index:200;'
        'box-shadow:0 6px 24px rgba(0,0,0,.4);padding:4px 0;"></div>'
        '</div>'
        '<div style="position:relative;">'
        '<button id="dgs-btn" onclick="toggleDgsMenu(event)"'
        ' style="display:inline-flex;align-items:center;gap:5px;'
        'padding:5px 11px;background:transparent;'
        'border:1px solid var(--bd);border-radius:999px;'
        'color:var(--c-muted);font-size:.75rem;font-weight:600;cursor:pointer;'
        'transition:all .18s;white-space:nowrap;letter-spacing:.04em;"'
        ' onmouseover="if(!_dgsOn)this.style.borderColor=\'rgba(124,159,255,.4)\'"'
        ' onmouseout="if(!_dgsOn)this.style.borderColor=\'var(--bd)\'">'
        + _SVG_LAYERS +
        '<span>DGS PORT</span>'
        '<span id="dgs-cur" style="font-weight:700;letter-spacing:.02em;"></span>'
        + _SVG_CHEVRON +
        '</button>'
        '<div id="dgs-menu" style="display:none;position:absolute;right:0;'
        'top:calc(100%% + 8px);background:var(--bg-card);'
        'border:1px solid rgba(255,255,255,.07);'
        'border-radius:14px;min-width:210px;z-index:300;'
        'box-shadow:0 12px 40px rgba(0,0,0,.55);overflow:hidden;">'
        '</div>'
        '</div>'
        '</div>'
        '<div id="inst-no-res" style="display:none;color:var(--c-muted);font-size:.85rem;'
        'padding:16px 0;text-align:center;letter-spacing:.02em;">일치하는 결과가 없습니다.</div>'
    )

    _SVG_CHECK = (
        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
        ' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="20 6 9 17 4 12"/></svg>'
    )

    filter_script = (
        '<style>'
        '.inst-chip{padding:7px 15px;font-size:.8rem;color:var(--c-muted);cursor:pointer;'
        'transition:background .12s,color .12s;white-space:nowrap;}'
        '.inst-chip:hover{background:var(--bg-main);color:var(--c-main);}'
        '.inst-chip b{color:var(--c-accent);font-style:normal;font-weight:700;}'
        '.dgs-hdr{padding:10px 16px 8px;font-size:.68rem;font-weight:700;letter-spacing:.1em;'
        'text-transform:uppercase;color:var(--c-dim);pointer-events:none;}'
        '.dgs-sep{height:1px;background:rgba(255,255,255,.06);margin:4px 0;}'
        '.dgs-row{display:flex;align-items:center;justify-content:space-between;'
        'padding:9px 14px;cursor:pointer;gap:10px;transition:background .12s;}'
        '.dgs-row:hover{background:rgba(255,255,255,.04);}'
        '.dgs-row.sel{background:rgba(124,159,255,.08);}'
        '.dgs-chk{width:16px;flex-shrink:0;color:var(--c-accent);opacity:0;transition:opacity .15s;}'
        '.dgs-row.sel .dgs-chk{opacity:1;}'
        '.dgs-lbl{font-size:.82rem;font-weight:500;color:var(--c-main);flex:1;}'
        '.dgs-row.sel .dgs-lbl{color:var(--c-accent);font-weight:600;}'
        '.dgs-cnt{font-size:.7rem;padding:2px 8px;border-radius:999px;font-weight:600;'
        'background:rgba(255,255,255,.06);color:var(--c-dim);}'
        '.dgs-row.sel .dgs-cnt{background:rgba(124,159,255,.15);color:var(--c-accent);}'
        '.dgs-all-lbl{font-size:.82rem;color:var(--c-muted);flex:1;}'
        '.dgs-row.sel .dgs-all-lbl{color:var(--c-accent);font-weight:600;}'
        '</style>'
        '<script>'
        '(function(){'
        'var tbl=document.getElementById("inst-tbl");'
        'if(!tbl)return;'
        'var ths=tbl.querySelectorAll("thead th");'
        'var instIdx=-1,dgsIdx=-1;'
        'ths.forEach(function(th,i){'
        'var t=th.textContent.trim().toUpperCase();'
        'if(t.indexOf("INSTANCE")!==-1)instIdx=i;'
        'if(t.indexOf("DGS")!==-1&&t.indexOf("PORT")!==-1)dgsIdx=i;'
        '});'
        'var rows=Array.prototype.slice.call(tbl.querySelectorAll("tbody tr"));'
        'var instances=[],iSet={},ports=[],pSet={},portCnt={},total=rows.length;'
        'rows.forEach(function(tr){'
        'var cells=tr.querySelectorAll("td");'
        'if(instIdx>=0&&cells[instIdx]){'
        'var v=cells[instIdx].textContent.trim();'
        'tr.dataset.inst=v.toLowerCase();'
        'if(v&&!iSet[v]){iSet[v]=1;instances.push(v);}}'
        'if(dgsIdx>=0&&cells[dgsIdx]){'
        'var p=cells[dgsIdx].textContent.trim();'
        'tr.dataset.dgs=p;'
        'if(p&&p!=="-"){portCnt[p]=(portCnt[p]||0)+1;'
        'if(!pSet[p]){pSet[p]=1;ports.push(p);}}}'
        '});'
        'ports.sort(function(a,b){'
        'var na=parseInt(a),nb=parseInt(b);'
        'return(isNaN(na)?99999:na)-(isNaN(nb)?99999:nb);});'
        'var activeDgs="ALL";'
        'window._dgsOn=false;'
        'var menu=document.getElementById("dgs-menu");'
        'var _SVG_CHECK=\'<svg width="13" height="13" viewBox="0 0 24 24" fill="none"'
        ' stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="20 6 9 17 4 12"/></svg>\';'
        'function buildMenu(){'
        'menu.innerHTML="";'
        'var hdr=document.createElement("div");hdr.className="dgs-hdr";'
        'hdr.textContent="Group by DGS PORT";menu.appendChild(hdr);'
        'var sep=document.createElement("div");sep.className="dgs-sep";menu.appendChild(sep);'
        'var allRow=document.createElement("div");'
        'allRow.className="dgs-row"+(activeDgs==="ALL"?" sel":"");'
        'allRow.innerHTML=\'<span class="dgs-chk">\'+_SVG_CHECK+\'</span>\''
        '+\'<span class="dgs-all-lbl">All instances</span>\''
        '+\'<span class="dgs-cnt">\'+total+\'</span>\';'
        'allRow.onclick=function(e){e.stopPropagation();selectDgs("ALL");};'
        'menu.appendChild(allRow);'
        'var sep2=document.createElement("div");sep2.className="dgs-sep";'
        'sep2.style.margin="4px 0 2px";menu.appendChild(sep2);'
        'ports.forEach(function(p){'
        'var row=document.createElement("div");'
        'row.className="dgs-row"+(activeDgs===p?" sel":"");'
        'row.innerHTML=\'<span class="dgs-chk">\'+_SVG_CHECK+\'</span>\''
        '+\'<span class="dgs-lbl">\'+p+\'</span>\''
        '+\'<span class="dgs-cnt">\'+(portCnt[p]||0)+\'</span>\';'
        'row.onclick=function(e){e.stopPropagation();selectDgs(p);};'
        'menu.appendChild(row);});}'
        'function selectDgs(p){'
        'activeDgs=p;window._dgsOn=(p!=="ALL");'
        'var cur=document.getElementById("dgs-cur");'
        'var btn=document.getElementById("dgs-btn");'
        'if(p!=="ALL"){'
        'cur.textContent=" \u00b7 "+p;'
        'btn.style.borderColor="var(--c-accent)";'
        'btn.style.color="var(--c-accent)";'
        'btn.style.background="rgba(124,159,255,.1)";'
        'btn.style.boxShadow="0 0 0 3px rgba(124,159,255,.1)";'
        '}else{'
        'cur.textContent="";'
        'btn.style.borderColor="var(--bd)";'
        'btn.style.color="var(--c-muted)";'
        'btn.style.background="transparent";'
        'btn.style.boxShadow="none";}'
        'var chv=document.getElementById("dgs-chv");'
        'if(chv)chv.style.transform="";'
        'buildMenu();menu.style.display="none";applyFilter();}'
        'buildMenu();'
        'window.toggleDgsMenu=function(e){'
        'e.stopPropagation();'
        'var open=menu.style.display!=="none";'
        'menu.style.display=open?"none":"block";'
        'var chv=document.getElementById("dgs-chv");'
        'if(chv)chv.style.transform=open?"":"rotate(180deg)";};'
        'function _e(s){return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}'
        'function hl(s,q){'
        'if(!q)return _e(s);'
        'var idx=s.toLowerCase().indexOf(q);'
        'if(idx===-1)return _e(s);'
        'return _e(s.slice(0,idx))+"<b>"+_e(s.slice(idx,idx+q.length))+"</b>"+_e(s.slice(idx+q.length));}'
        'function updateSugg(q){'
        'var sg=document.getElementById("inst-sugg");'
        'sg.innerHTML="";'
        'if(!q){sg.style.display="none";return;}'
        'var m=instances.filter(function(n){return n.toLowerCase().indexOf(q)!==-1;});'
        'if(!m.length){sg.style.display="none";return;}'
        'm.slice(0,10).forEach(function(name){'
        'var d=document.createElement("div");d.className="inst-chip";'
        'd.innerHTML=hl(name,q);'
        'd.onclick=function(){document.getElementById("inst-srch").value=name;'
        'sg.style.display="none";instFilter();};'
        'sg.appendChild(d);});'
        'sg.style.display="block";}'
        'function applyFilter(){'
        'var q=document.getElementById("inst-srch").value.trim().toLowerCase();'
        'var vis=0;'
        'rows.forEach(function(tr){'
        'var im=!q||(tr.dataset.inst||"").indexOf(q)!==-1;'
        'var dm=activeDgs==="ALL"||(tr.dataset.dgs||"")===activeDgs;'
        'var show=im&&dm;'
        'tr.style.display=show?"":"none";if(show)vis++;'
        '});'
        'document.getElementById("inst-no-res").style.display=vis?"none":"";'
        'tbl.style.display=vis?"":"none";'
        'updateSugg(q);}'
        'window.instFilter=applyFilter;'
        'document.addEventListener("click",function(e){'
        'var sg=document.getElementById("inst-sugg");'
        'if(sg&&!sg.contains(e.target)&&e.target.id!=="inst-srch")sg.style.display="none";'
        'var btn=document.getElementById("dgs-btn");'
        'if(btn&&!btn.contains(e.target)&&!menu.contains(e.target)){'
        'menu.style.display="none";'
        'var chv=document.getElementById("dgs-chv");'
        'if(chv)chv.style.transform="";}'
        '});'
        '})();'
        'function _instXToggle(){'
        'var x=document.getElementById("inst-x");if(!x)return;'
        'x.style.display=document.getElementById("inst-srch").value?"":"none";'
        '}'
        '</script>'
    )

    # 카드 안에서는 카드 헤더 padding(14px)만 사용 — filter_ui 자체 외부 마진 제거
    # 동시에 헤더 가로폭 채우기 위해 width:100% 추가
    filter_ui_card = filter_ui.replace('margin-bottom:14px;', 'width:100%;')
    body = ''.join([
        _page_title_html(title, *_HELP.get('license', (title, ''))),
        '<div class="insp-card">',
        '<div class="insp-card-hdr">', filter_ui_card, '</div>',
        '<div class="insp-card-body">', content_html, '</div>',
        '</div>',
        _ts(),
        _sql_embed(sql),
        filter_script,
    ])
    return _page('license', title, body)
