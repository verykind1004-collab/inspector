# -*- coding: utf-8 -*-
import json
import os
import re
import threading
import time as _time

from service_config import load_service_config
from db_utils import _db_cfg, run_db_query, _parse_db_table, _sql_embed
from sql_library import _get_sql
from system_utils import _xml_val, _read_lines
from html_helpers import (
    _warn_box, _info_box, _page_title_html, _page,
    _HELP, _HELP_JS, _ts, _render_db_table_html, _query_card,
    _UTILS_BASE,
)


def page_disk_capacity():
    title = 'Capacity Check'
    sql   = _get_sql('capacity')
    if not sql:
        body = (_page_title_html(title, *_HELP.get('disk_capacity', (title, '')))
                + _warn_box('현재 DB 타입에서는 지원하지 않는 쿼리입니다.'))
        return _page('disk_capacity', title, body)
    out, err = run_db_query(sql)
    if err:
        body = ''.join([
            _page_title_html(title, *_HELP.get('disk_capacity', (title, ''))),
            '<div class="insp-card"><div class="insp-card-body" style="padding:14px 16px;">',
            _warn_box(err),
            '</div></div>',
            _ts(),
        ])
        return _page('disk_capacity', title, body)
    headers, rows = _parse_db_table(out or '')
    table_html = _render_db_table_html(headers, rows)
    table_html = table_html.replace('<table class="svc-table">', '<table class="svc-table" id="cap-tbl">', 1)

    filter_ui = (
        '<div style="position:relative;">'
        '<input id="cap-srch" type="text" placeholder="Search..."'
        ' autocomplete="off" oninput="capFilter();_capXToggle();"'
        ' style="background:#ffffff;border:1px solid var(--bd);color:var(--c-main);'
        'border-radius:8px;padding:7px 28px 7px 12px;font-size:.82rem;width:240px;outline:none;'
        'transition:border-color .15s;"'
        ' onfocus="this.style.borderColor=\'var(--c-accent)\'"'
        ' onblur="this.style.borderColor=\'var(--bd)\'">'
        '<span id="cap-x" onclick="document.getElementById(\'cap-srch\').value=\'\';capFilter();_capXToggle();"'
        ' style="display:none;position:absolute;right:8px;top:50%;transform:translateY(-50%);'
        'cursor:pointer;color:#94A3B8;font-size:.85rem;line-height:1;padding:2px;"'
        ' onmouseover="this.style.color=\'#334155\'" onmouseout="this.style.color=\'#94A3B8\'"'
        '>&#x2715;</span>'
        '</div>'
    )
    no_res = ('<div id="cap-no-res" style="display:none;color:var(--c-muted);font-size:.85rem;'
              'padding:14px 0;text-align:center;">일치하는 결과가 없습니다.</div>')
    js = (
        '<script>'
        '(function(){'
        'var tbl=document.getElementById("cap-tbl");'
        'if(!tbl)return;'
        'var rows=Array.prototype.slice.call(tbl.querySelectorAll("tbody tr"));'
        'rows.forEach(function(tr){'
        'var t="";tr.querySelectorAll("td").forEach(function(td){t+=" "+td.textContent;});'
        'tr.dataset.txt=t.toLowerCase();'
        '});'
        'window.capFilter=function(){'
        'var q=document.getElementById("cap-srch").value.trim().toLowerCase();'
        'var vis=0;'
        'rows.forEach(function(tr){'
        'var show=!q||(tr.dataset.txt||"").indexOf(q)>=0;'
        'tr.style.display=show?"":"none";if(show)vis++;'
        '});'
        'document.getElementById("cap-no-res").style.display=vis?"none":"";'
        'tbl.style.display=vis?"":"none";'
        '};'
        '})();'
        'function _capXToggle(){'
        'var x=document.getElementById("cap-x");if(!x)return;'
        'x.style.display=document.getElementById("cap-srch").value?"":"none";'
        '}'
        '</script>'
    )

    body = ''.join([
        _page_title_html(title, *_HELP.get('disk_capacity', (title, ''))),
        '<div class="insp-card">',
        '<div class="insp-card-hdr">', filter_ui, '</div>',
        '<div class="insp-card-body">', no_res, table_html, '</div>',
        '</div>',
        _ts(),
        _sql_embed(sql),
        js,
    ])
    return _page('disk_capacity', title, body)


def _vacuum_log_html():
    """Parse POSTGRESQL VACUUM entries from DGM log."""
    import zipfile as _zf
    svc     = load_service_config()
    dgm_home = svc.get("services", {}).get("dgserver_m", "")
    if not dgm_home:
        return _warn_box("DGServer_M 경로가 설정되지 않았습니다.. Go to Configuration.")
    xmlfile  = os.path.join(dgm_home, "conf", "DGServer.xml")
    port     = _xml_val(xmlfile, "gather_port")
    port_str = str(port) if port else ""
    log_dir  = os.path.join(dgm_home, "log")
    logfile  = os.path.join(log_dir, "DGM_" + port_str + ".log")

    def _parse_vacuum_lines(lines):
        rows   = []
        starts = {}
        for line in lines:
            if 'POSTGRESQL VACUUM' not in line:
                continue
            tm  = re.search(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\]', line)
            t   = tm.group(1) if tm else '-'
            sm  = re.search(r'schema_name=([^, \n]+)', line)
            sch = sm.group(1) if sm else '-'
            if 'start' in line:
                starts[sch] = t
            elif 'end' in line:
                elm = re.search(r'el=(\d+)ms', line)
                el  = ("%.3fs" % (int(elm.group(1)) / 1000.0)) if elm else '-'
                st  = starts.get(sch, '-')
                rows.append((sch, st, t, el))
        return rows

    def _find_today_zip():
        from datetime import date
        today_str = date.today().strftime('%Y%m%d')
        today_zip = os.path.join(log_dir, "DGM_%s_%s_0.log.zip" % (port_str, today_str))
        if os.path.exists(today_zip):
            return today_zip
        return None

    rows       = []
    source_tag = ""

    try:
        # 1. 오늘 날짜 _0.log.zip 먼저 시도
        zip_path = _find_today_zip()
        if zip_path:
            with _zf.ZipFile(zip_path, 'r') as zf:
                inner = zf.namelist()
                if inner:
                    data = zf.read(inner[0]).decode('utf-8', errors='replace')
                    zip_lines = data.splitlines(keepends=True)
                    rows = _parse_vacuum_lines(zip_lines)
                    source_tag = os.path.basename(zip_path)

        # 2. zip 없거나 결과 없으면 현재 로그 fallback
        if not rows:
            if os.path.exists(logfile):
                lines = _read_lines(logfile)
                rows = _parse_vacuum_lines(lines)
                source_tag = os.path.basename(logfile)
            elif not zip_path:
                return _warn_box("로그 파일을 찾을 수 없습니다: " + logfile)

    except Exception as e:
        return _warn_box("로그 읽기 오류: " + str(e))

    parts = []
    if rows:
        def _sth(t): return '<th class="sortable" onclick="tbSort(this)">' + t + '<span class="sort-ic"></span></th>'
        thead = '<tr>' + _sth('Schema') + _sth('Start Time') + _sth('End Time') + _sth('Duration') + '</tr>'
        tbody = ''.join('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % r for r in rows[-100:])
        parts.append('<div class="tbl-wrap"><table class="svc-table"><thead>' + thead + '</thead><tbody>' + tbody + '</tbody></table></div>')
    else:
        parts.append('<div style="display:flex;align-items:center;gap:10px;padding:12px 16px;background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.3);border-radius:8px;font-size:.85rem;color:#ef4444;">&#9888; Vacuum Log 가 발견되지 않았습니다.</div>')
    return ''.join(parts)


def _auto_vacuum_card(out, err):
    title = "Auto-Vacuum Check (tables pending manual vacuum)"
    if err:
        return ('<div class="insp-card">'
                '<div class="insp-card-hdr"><div class="insp-card-title">' + title + '</div></div>'
                '<div class="insp-card-body" style="padding:14px 16px;">' + _warn_box(err) + '</div>'
                '</div>')
    headers, rows = _parse_db_table(out or "")
    if rows:
        content = _render_db_table_html(headers, rows)
        # VACUUM TABLE 버튼 (insp-card-hdr는 flex이므로 float 무효, gap으로 자연 정렬)
        vac_btn = (
            '<div style="display:flex;align-items:center;gap:10px;">'
            '<span id="vt-status" style="font-size:.78rem;color:#64748B;"></span>'
            '<button id="vt-btn" onclick="doVacuumTable()" class="btn-freeze">'
            'VACUUM TABLE</button>'
            '</div>'
        )
        vac_js = (
            '<script>'
            'var _vtPoll=null;'
            'function doVacuumTable(){'
            'if(!confirm("Run VACUUM on all listed tables?\\n\\nBackground execution."))return;'
            'var btn=document.getElementById("vt-btn");'
            'btn.disabled=true;btn.textContent="Running...";btn.classList.add("btn-freeze-running");'
            'document.getElementById("vt-status").textContent="Started...";'
            'fetch("' + _UTILS_BASE + '/api/vacuum-table")'
            '.then(function(r){return r.json();})'
            '.then(function(d){'
            'if(d.ok){_vtStartPoll();}'
            'else{btn.textContent="Error";btn.classList.remove("btn-freeze-running");btn.disabled=false;'
            'document.getElementById("vt-status").textContent=d.error||"error";}'
            '}).catch(function(){btn.disabled=false;btn.textContent="VACUUM TABLE";});'
            '}'
            'function _vtStartPoll(){'
            'if(_vtPoll)clearInterval(_vtPoll);'
            '_vtPoll=setInterval(_vtCheck,3000);'
            '}'
            'function _vtCheck(){'
            'fetch("' + _UTILS_BASE + '/api/vacuum-table-status")'
            '.then(function(r){return r.json();})'
            '.then(function(s){'
            'var btn=document.getElementById("vt-btn");'
            'var st=document.getElementById("vt-status");'
            'if(s.running){'
            'btn.disabled=true;btn.textContent="Running...";btn.classList.add("btn-freeze-running");'
            'st.textContent=(s.current||"")+" ("+(s.done||0)+"/"+(s.total||0)+")";'
            '}else if(s.elapsed!==null){'
            'clearInterval(_vtPoll);_vtPoll=null;'
            'if(s.error){btn.textContent="Error";btn.classList.remove("btn-freeze-running");btn.classList.add("btn-freeze-err");'
            'btn.disabled=false;st.textContent=s.error;'
            '}else{'
            'btn.innerHTML="\u2713 Done";btn.classList.remove("btn-freeze-running");btn.classList.add("btn-freeze-done");'
            'st.textContent="Completed in "+s.elapsed+"s ("+s.done+" tables)";'
            'setTimeout(function(){location.reload();},2000);'
            '}'
            '}'
            '});'
            '}'
            '</script>'
        )
    else:
        content = (
            '<div style="display:flex;align-items:center;gap:12px;padding:14px 18px;margin:14px 16px;'
            'background:var(--ok-bg);border:1px solid var(--ok-bd);border-radius:8px;">'
            '<span style=\'color:var(--ok-c);font-size:1.3rem;line-height:1;\'>&#10003;</span>'
            '<span style=\'color:var(--ok-c);font-size:.88rem;letter-spacing:.02em;\'>'
            '모든 테이블이 최신 상태입니다 &mdash; 수동 Vacuum 이 필요하지 않습니다.'
            '</span>'
            '</div>'
        )
        vac_btn = ''
        vac_js = ''
    return (
        '<div class="insp-card">'
        '<div class="insp-card-hdr" style="justify-content:space-between;">'
        '<div class="insp-card-title">' + title + '</div>'
        + vac_btn +
        '</div>'
        '<div class="insp-card-body">' + content + '</div>'
        + vac_js +
        '</div>'
    )


def _age_card(out, err):
    title = "Age Check"
    freeze_btn = (
        '<div style="display:flex;align-items:center;gap:10px;">'
        '<span id="vf-status" style="font-size:.78rem;color:#64748B;"></span>'
        '<button id="vf-btn" onclick="doVacuumFreeze()" class="btn-freeze">'
        'VACUUM FREEZE</button>'
        '</div>'
        '<script>'
        'var _vfPoll=null;'
        'function doVacuumFreeze(){_vfShowModal();}'
        'function _vfShowModal(){'
        'var ov=document.getElementById("vf-confirm-modal");'
        'ov.style.display="flex";'
        'ov.onclick=function(e){if(e.target===ov)_vfCancel();};'
        '}'
        'function _vfCancel(){'
        'document.getElementById("vf-confirm-modal").style.display="none";'
        '}'
        'function _vfConfirm(){_vfCancel();_vfRun();}'
        'function _vfRun(){'
        'var btn=document.getElementById("vf-btn");'
        'btn.disabled=true;btn.textContent="Running...";btn.classList.add("btn-freeze-running");'
        'document.getElementById("vf-status").textContent="Started...";'
        'fetch("' + _UTILS_BASE + '/api/vacuum-freeze")'
        '.then(function(r){return r.json();})'
        '.then(function(d){'
        'if(d.ok){_vfStartPoll();}'
        'else{btn.textContent="Error";btn.classList.remove("btn-freeze-running");btn.disabled=false;'
        'document.getElementById("vf-status").textContent=d.error||"error";}'
        '}).catch(function(){btn.disabled=false;btn.textContent="VACUUM FREEZE";});'
        '}'
        'function _vfStartPoll(){'
        'if(_vfPoll)clearInterval(_vfPoll);'
        '_vfPoll=setInterval(_vfCheck,3000);'
        '}'
        'function _vfCheck(){'
        'fetch("' + _UTILS_BASE + '/api/vacuum-freeze-status")'
        '.then(function(r){return r.json();})'
        '.then(function(s){'
        'var btn=document.getElementById("vf-btn");'
        'var st=document.getElementById("vf-status");'
        'if(s.running){'
        'btn.disabled=true;btn.textContent="Running...";btn.classList.add("btn-freeze-running");'
        'st.textContent="Started: "+s.started;'
        '}else if(s.elapsed!==null){'
        'clearInterval(_vfPoll);_vfPoll=null;'
        'if(s.error){btn.textContent="Error";btn.classList.remove("btn-freeze-running");btn.classList.add("btn-freeze-err");'
        'btn.disabled=false;st.textContent=s.error;'
        '}else{'
        'btn.innerHTML="\u2713 Done";btn.classList.remove("btn-freeze-running");btn.classList.add("btn-freeze-done");'
        'st.textContent="Completed in "+s.elapsed+"s";'
        'setTimeout(function(){btn.textContent="VACUUM FREEZE";btn.disabled=false;'
        'btn.classList.remove("btn-freeze-done");st.textContent="";},5000);'
        'fetch("' + _UTILS_BASE + '/api/age-card")'
        '.then(function(r){return r.json();})'
        '.then(function(d){var w=document.getElementById("age-tbl-wrap");if(w)w.innerHTML=d.html;});'
        '}'
        '}'
        '});'
        '}'
        '_vfCheck();'
        '</script>'
    )
    vf_modal_html = (
        '<style>'
        '@keyframes _vfmIn{from{opacity:0;transform:scale(.94) translateY(8px)}to{opacity:1;transform:scale(1) translateY(0)}}'
        '#vf-confirm-modal>div{animation:_vfmIn .25s cubic-bezier(.34,1.56,.64,1) both}'
        '</style>'
        '<div id="vf-confirm-modal" style="display:none;position:fixed;inset:0;z-index:10000;'
        'background:rgba(15,15,30,.45);backdrop-filter:blur(6px);'
        'align-items:center;justify-content:center;padding:24px;">'
        '<div style="background:#ffffff;border-radius:16px;width:100%;max-width:420px;'
        'box-shadow:0 0 0 1px rgba(108,84,232,.12),0 24px 60px rgba(0,0,0,.18);overflow:hidden;">'
        # ── Header ──
        '<div style="padding:22px 24px 0;display:flex;align-items:flex-start;justify-content:space-between;">'
        '<div>'
        '<div style="width:42px;height:42px;background:#ede9fd;border-radius:12px;'
        'display:grid;place-items:center;margin-bottom:14px;">'
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6c54e8" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 2v4"/><path d="M12 18v4"/>'
        '<path d="M4.93 4.93l2.83 2.83"/><path d="M16.24 16.24l2.83 2.83"/>'
        '<path d="M2 12h4"/><path d="M18 12h4"/>'
        '<path d="M4.93 19.07l2.83-2.83"/><path d="M16.24 7.76l2.83-2.83"/>'
        '</svg></div>'
        '<div style="font-size:16px;font-weight:700;color:#1a1d2e;letter-spacing:-.01em;margin-bottom:4px;">'
        'VACUUM FREEZE 실행</div>'
        '<div style="font-size:12.5px;color:#9ca3af;">Repository DB 전체 테이블에 대해 실행합니다</div>'
        '</div>'
        '<button onclick="_vfCancel()" '
        'style="width:28px;height:28px;border:1px solid #e4e6ed;border-radius:7px;background:#fff;'
        'display:grid;place-items:center;cursor:pointer;color:#9ca3af;font-size:14px;'
        'flex-shrink:0;margin-top:4px;transition:border-color .15s,color .15s;"'
        ' onmouseover="this.style.borderColor=\'#ef4444\';this.style.color=\'#ef4444\'"'
        ' onmouseout="this.style.borderColor=\'#e4e6ed\';this.style.color=\'#9ca3af\'">&#x2715;</button>'
        '</div>'
        # ── Body ──
        '<div style="padding:18px 24px 0;">'
        '<div style="background:#faf9ff;border:1px solid #e8e2ff;border-radius:10px;overflow:hidden;margin-bottom:14px;">'
        '<div style="padding:12px 16px;font-size:13.5px;color:#374151;line-height:1.65;">'
        'Repository DB의 모든 테이블에 대해 <b>VACUUM FREEZE</b>를 수행합니다.'
        '</div>'
        '<div style="padding:12px 16px;border-top:1px solid #e8e2ff;font-size:13.5px;color:#374151;line-height:1.65;">'
        '데이터가 많은 DB에서는 시간이 걸릴 수 있으며, <b>백그라운드</b>로 진행되므로 다른 페이지로 이동하셔도 됩니다.'
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
        '이 작업은 백그라운드로 실행되며 진행 중 취소할 수 없습니다.</span>'
        '</div>'
        '</div>'
        # ── Footer ──
        '<div style="padding:0 24px 22px;display:flex;align-items:center;justify-content:flex-end;gap:8px;">'
        '<button onclick="_vfCancel()" '
        'style="padding:9px 22px;border-radius:9px;font-size:13.5px;font-weight:600;cursor:pointer;'
        'transition:all .15s;border:1px solid #e4e6ed;background:#f4f5f8;color:#6b7280;"'
        ' onmouseover="this.style.background=\'#e9eaee\';this.style.color=\'#1a1d2e\'"'
        ' onmouseout="this.style.background=\'#f4f5f8\';this.style.color=\'#6b7280\'">취소</button>'
        '<button onclick="_vfConfirm()" '
        'style="padding:9px 28px;border-radius:9px;font-size:13.5px;font-weight:600;cursor:pointer;'
        'transition:all .15s;border:none;background:#6c54e8;color:#fff;'
        'box-shadow:0 2px 8px rgba(108,84,232,.35);"'
        ' onmouseover="this.style.background=\'#5a43d0\';this.style.boxShadow=\'0 4px 16px rgba(108,84,232,.45)\';this.style.transform=\'translateY(-1px)\'"'
        ' onmouseout="this.style.background=\'#6c54e8\';this.style.boxShadow=\'0 2px 8px rgba(108,84,232,.35)\';this.style.transform=\'\'">실행</button>'
        '</div>'
        '</div>'
        '</div>'
    )

    if err:
        return (
            '<div class="insp-card" id="age-card-wrap">'
            '<div class="insp-card-hdr" style="justify-content:space-between;">'
            '<div class="insp-card-title">' + title + '</div>'
            + freeze_btn +
            '</div>'
            '<div class="insp-card-body" style="padding:14px 16px;" id="age-tbl-wrap">' + _warn_box(err) + '</div>'
            '</div>'
            + vf_modal_html
        )
    headers, rows = _parse_db_table(out or "")
    content = _render_db_table_html(headers, rows)
    return (
        '<div class="insp-card" id="age-card-wrap">'
        '<div class="insp-card-hdr" style="justify-content:space-between;">'
        '<div class="insp-card-title">' + title + '</div>'
        + freeze_btn +
        '</div>'
        '<div class="insp-card-body" id="age-tbl-wrap">' + content + '</div>'
        '</div>'
        + vf_modal_html
    )


def page_disk_vacuum_age():
    sql_vac = _get_sql("vacuum")
    sql_age = _get_sql("age")
    if not sql_vac:
        body = ''.join([
            _page_title_html('Vacuum/Age Check', *_HELP.get('vacuum', ('Vacuum/Age Check', ''))),
            _warn_box("Vacuum/Age Check is only available for PostgreSQL."),
        ])
        return _page('disk_vacuum_age', 'Vacuum/Age Check', body)
    out_vac, err_vac = run_db_query(sql_vac)
    out_age, err_age = run_db_query(sql_age) if sql_age else ("", "Age SQL을 사용할 수 없습니다.")
    body = ''.join([
        _page_title_html('Vacuum/Age Check', *_HELP.get('vacuum', ('Vacuum/Age Check', ''))),
        '<div class="insp-card">',
        '<div class="insp-card-hdr"><div class="insp-card-title">Vacuum Log (DGServer_M)</div></div>',
        '<div class="insp-card-body">',
        _vacuum_log_html(),
        '</div>',
        '</div>',
        _auto_vacuum_card(out_vac or "", err_vac or ""),
        _age_card(out_age or "", err_age or ""),
        _ts(),
        _sql_embed((sql_vac or '') + ('\n\n-- Age\n' + sql_age if sql_age else '')),
    ])
    return _page('disk_vacuum_age', 'Vacuum/Age Check', body)


def page_disk_top_segment():
    title = 'Top Segment'
    sql   = _get_sql('top_segment')
    if not sql:
        body = ''.join([
            _page_title_html(title, *_HELP.get('disk_top_segment', (title, ''))),
            _warn_box('현재 DB 타입에서는 지원하지 않는 쿼리입니다.'),
        ])
        return _page('disk_top_segment', title, body)
    out, err = run_db_query(sql)
    if err:
        body = ''.join([
            _page_title_html(title, *_HELP.get('disk_top_segment', (title, ''))),
            '<div class="insp-card"><div class="insp-card-body" style="padding:14px 16px;">',
            _warn_box(err),
            '</div></div>',
            _ts(),
        ])
        return _page('disk_top_segment', title, body)
    headers, rows = _parse_db_table(out or '')
    table_html = _render_db_table_html(headers, rows)
    table_html = table_html.replace('<table class="svc-table">', '<table class="svc-table" id="ts-tbl">', 1)

    filter_ui = (
        '<div style="position:relative;">'
        '<input id="ts-srch" type="text" placeholder="Search by schema or table name..."'
        ' autocomplete="off" oninput="tsFilter();_tsXToggle();"'
        ' style="background:#ffffff;border:1px solid var(--bd);color:var(--c-main);'
        'border-radius:8px;padding:7px 28px 7px 12px;font-size:.82rem;width:280px;outline:none;'
        'transition:border-color .15s;"'
        ' onfocus="this.style.borderColor=\'var(--c-accent)\'"'
        ' onblur="this.style.borderColor=\'var(--bd)\'">'
        '<span id="ts-x" onclick="document.getElementById(\'ts-srch\').value=\'\';tsFilter();_tsXToggle();"'
        ' style="display:none;position:absolute;right:8px;top:50%;transform:translateY(-50%);'
        'cursor:pointer;color:#94A3B8;font-size:.85rem;line-height:1;padding:2px;"'
        ' onmouseover="this.style.color=\'#334155\'" onmouseout="this.style.color=\'#94A3B8\'"'
        '>&#x2715;</span>'
        '</div>'
    )
    no_res = ('<div id="ts-no-res" style="display:none;color:var(--c-muted);font-size:.85rem;'
              'padding:14px 0;text-align:center;">일치하는 결과가 없습니다.</div>')
    js = (
        '<script>'
        '(function(){'
        'var tbl=document.getElementById("ts-tbl");'
        'if(!tbl)return;'
        'var ths=tbl.querySelectorAll("thead th");'
        'var schIdx=-1,tblIdx=-1;'
        'ths.forEach(function(th,i){'
        'var t=th.textContent.trim().toUpperCase();'
        'if(t.indexOf("SCHEMA")!==-1)schIdx=i;'
        'else if(t.indexOf("TABLE")!==-1&&tblIdx<0)tblIdx=i;'
        '});'
        'var rows=Array.prototype.slice.call(tbl.querySelectorAll("tbody tr"));'
        'rows.forEach(function(tr){'
        'var cells=tr.querySelectorAll("td");'
        'var s=schIdx>=0&&cells[schIdx]?cells[schIdx].textContent.trim():"";'
        'var t=tblIdx>=0&&cells[tblIdx]?cells[tblIdx].textContent.trim():"";'
        'tr.dataset.txt=(s+" "+t).toLowerCase();'
        '});'
        'window.tsFilter=function(){'
        'var q=document.getElementById("ts-srch").value.trim().toLowerCase();'
        'var vis=0;'
        'rows.forEach(function(tr){'
        'var show=!q||(tr.dataset.txt||"").indexOf(q)>=0;'
        'tr.style.display=show?"":"none";if(show)vis++;'
        '});'
        'document.getElementById("ts-no-res").style.display=vis?"none":"";'
        'tbl.style.display=vis?"":"none";'
        '};'
        '})();'
        'function _tsXToggle(){'
        'var x=document.getElementById("ts-x");if(!x)return;'
        'x.style.display=document.getElementById("ts-srch").value?"":"none";'
        '}'
        '</script>'
    )

    body = ''.join([
        '<style>.main{max-height:100vh!important;overflow:hidden!important;}</style>',
        _page_title_html(title, *_HELP.get('disk_top_segment', (title, ''))),
        '<div class="insp-card" style="max-height:calc(100vh - 130px);">',
        '<div class="insp-card-hdr">', filter_ui, '</div>',
        '<div class="insp-card-body" style="overflow:auto;">', no_res, table_html, '</div>',
        '</div>',
        _ts(),
        _sql_embed(sql),
        js,
    ])
    return _page('disk_top_segment', title, body)


def page_disk_temp_table():
    sql      = _get_sql("temp_table")
    title    = 'Temp Table'
    sub_text = 'Tables with tt% prefix that have not been dropped'
    if not sql:
        body = ''.join([
            _page_title_html(title, *_HELP.get('disk_temp_table', (title, ''))),
            _warn_box("현재 DB 타입에서는 지원하지 않는 쿼리입니다."),
        ])
        return _page('disk_temp_table', title, body)
    out, err = run_db_query(sql)
    headers, rows = _parse_db_table(out or "")
    if not err and headers is not None and len(rows) == 0:
        # 파티션 시간 확인 탭의 no-match 박스와 동일한 위/아래 간격으로 맞춤
        # (insp-card-body 자체엔 패딩 없음, wrapper 가 14px 패딩 + 내부 박스가 10px 마진).
        content = (
            '<div class="insp-card">'
            '<div class="insp-card-body">'
            '<div style="padding:14px 16px;">'
            '<div style="display:flex;align-items:center;gap:12px;'
            'padding:12px 16px;margin:10px 0;border-radius:8px;'
            'background:var(--ok-bg);border:1px solid var(--ok-bd);">'
            '<span style="color:var(--ok-c);font-size:1.3rem;line-height:1;">&#10003;</span>'
            '<span style="color:var(--ok-c);font-size:.88rem;letter-spacing:.02em;">'
            '조회되는 Temp Table이 없습니다.'
            '</span></div></div></div></div>'
        )
        body = ''.join([
            _page_title_html(title, *_HELP.get('disk_temp_table', (title, ''))),
            content,
            _ts(),
            _sql_embed(sql),
        ])
        return _page('disk_temp_table', title, body)

    # Has rows - build table with DROP ALL button
    table_html = _render_db_table_html(headers, rows)

    # Collect schema.table pairs for bulk drop
    h_upper = [h.upper() for h in headers]
    idx_schema = next((i for i, h in enumerate(h_upper) if 'SCHEMA' in h), 0)
    idx_table  = next((i for i, h in enumerate(h_upper) if 'TABLE' in h and 'SCHEMA' not in h), 1)
    pairs = []
    for row in rows:
        schema = row[idx_schema].strip() if idx_schema < len(row) else ''
        table  = row[idx_table].strip()  if idx_table  < len(row) else ''
        if schema and table:
            pairs.append(schema + '.' + table)

    import json as _json
    pairs_js = _json.dumps(pairs)

    drop_btn = (
        '<div style="display:flex;align-items:center;gap:10px;">'
        '<span id="tt-drop-status" style="font-size:.78rem;color:#64748B;"></span>'
        '<button id="tt-drop-all" onclick="_ttDropAll()" class="btn-freeze">'
        'DROP ALL (' + str(len(pairs)) + ')</button>'
        '</div>'
    )

    drop_js = (
        '<script>'
        'var _ttTables=' + pairs_js + ';'
        'var _ttPoll=null;'
        'function _ttDropAll(){'
        '  var listHtml=_ttTables.map(function(t){return "<div style=\\"padding:3px 0;\\">"+_ttEsc(t)+"</div>";}).join("");'
        '  _ttConfirmDrop({'
        '    title:_ttTables.length+"개 Temp Table 삭제",'
        '    bodyHtml:"<p style=\\"margin:0 0 12px;\\">아래 "+_ttTables.length+"개 Temp Table 을 삭제합니다.</p>"'
        '            +"<div style=\\"max-height:220px;overflow-y:auto;padding:10px 14px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;font-family:\'JetBrains Mono\',\'Consolas\',monospace;font-size:.78rem;color:#0F172A;\\">"+listHtml+"</div>"'
        '            +"<p style=\\"margin:12px 0 0;font-size:.78rem;color:#DC2626;\\">&#9888; 이 작업은 되돌릴 수 없습니다.</p>",'
        '    confirmText:"삭제",'
        '    onConfirm:function(){'
        '      var btn=document.getElementById("tt-drop-all");'
        '      btn.disabled=true;btn.textContent="Dropping...";btn.classList.add("btn-freeze-running");'
        '      document.getElementById("tt-drop-status").textContent="Started...";'
        '      fetch("' + _UTILS_BASE + '/api/temp-table-drop-all")'
        '      .then(function(r){return r.json();})'
        '      .then(function(d){'
        '        if(d.ok){_ttStartPoll();}'
        '        else{btn.textContent="Error";btn.classList.remove("btn-freeze-running");btn.disabled=false;'
        '             document.getElementById("tt-drop-status").textContent=d.error||"error";}'
        '      }).catch(function(){btn.disabled=false;btn.textContent="DROP ALL";'
        '        btn.classList.remove("btn-freeze-running");});'
        '    }'
        '  });'
        '}'
        'function _ttCloseConfirm(){var o=document.getElementById("tt-confirm-modal");if(o)o.remove();}'
        'function _ttConfirmDrop(opts){'
        '  var accent="#F59E0B";var accentBg="rgba(245,158,11,.12)";'
        '  var icon=\'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>\';'
        '  var html=""'
        '   +"<link href=\\"https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap\\" rel=\\"stylesheet\\">"'
        '   +"<div id=\\"tt-confirm-modal\\" style=\\"position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;font-family:\'Noto Sans KR\',\'Segoe UI\',system-ui,sans-serif;letter-spacing:-.01em;\\">"'
        '     +"<div onclick=\\"_ttCloseConfirm()\\" style=\\"position:absolute;inset:0;background:rgba(15,23,42,.45);backdrop-filter:blur(3px);\\"></div>"'
        '     +"<div style=\\"position:relative;width:min(520px,92vw);max-height:86vh;background:#fff;border-radius:16px;box-shadow:0 30px 70px rgba(15,23,42,.25),0 10px 24px rgba(15,23,42,.08);border:1px solid rgba(226,232,240,.9);display:flex;flex-direction:column;overflow:hidden;\\">"'
        '       +"<div style=\\"padding:16px 20px 14px;display:flex;gap:10px;align-items:center;border-bottom:1px solid #F1F5F9;\\">"'
        '         +"<div style=\\"flex-shrink:0;width:32px;height:32px;border-radius:9px;background:"+accentBg+";display:flex;align-items:center;justify-content:center;\\">"+icon+"</div>"'
        '         +"<div style=\\"flex:1;min-width:0;\\"><div style=\\"font-size:.92rem;font-weight:700;color:#0F172A;line-height:1.25;\\">"+_ttEsc(opts.title)+"</div></div>"'
        '         +"<button onclick=\\"_ttCloseConfirm()\\" style=\\"width:30px;height:30px;border:none;background:transparent;color:#94A3B8;font-size:1.35rem;cursor:pointer;border-radius:6px;line-height:1;\\">&times;</button>"'
        '       +"</div>"'
        '       +"<div style=\\"padding:14px 20px;overflow-y:auto;flex:1;font-size:.84rem;color:#334155;line-height:1.6;\\">"+opts.bodyHtml+"</div>"'
        '       +"<div style=\\"padding:14px 20px;border-top:1px solid #F1F5F9;display:flex;justify-content:flex-end;gap:10px;\\">"'
        '         +"<button onclick=\\"_ttCloseConfirm()\\" style=\\"padding:9px 22px;border-radius:10px;border:1px solid #E2E8F0;background:#fff;color:#64748B;font-size:.84rem;font-weight:600;cursor:pointer;\\">취소</button>"'
        '         +"<button id=\\"tt-confirm-ok\\" style=\\"padding:9px 22px;border-radius:10px;border:none;background:"+accent+";color:#fff;font-size:.84rem;font-weight:600;cursor:pointer;letter-spacing:.01em;box-shadow:inset 0 1px 0 rgba(255,255,255,.25),0 1px 2px rgba(15,23,42,.06);\\">"+_ttEsc(opts.confirmText||"확인")+"</button>"'
        '       +"</div>"'
        '     +"</div>"'
        '   +"</div>";'
        '  var wrap=document.createElement("div");wrap.innerHTML=html;'
        '  while(wrap.firstChild)document.body.appendChild(wrap.firstChild);'
        '  document.getElementById("tt-confirm-ok").onclick=function(){'
        '    _ttCloseConfirm();'
        '    if(typeof opts.onConfirm==="function") opts.onConfirm();'
        '  };'
        '}'
        'function _ttStartPoll(){if(_ttPoll)clearInterval(_ttPoll);_ttPoll=setInterval(_ttCheck,2000);}'
        'function _ttCheck(){'
        'fetch("' + _UTILS_BASE + '/api/temp-table-drop-status")'
        '.then(function(r){return r.json();})'
        '.then(function(s){'
        'var btn=document.getElementById("tt-drop-all");'
        'var st=document.getElementById("tt-drop-status");'
        'if(s.running){'
        'st.textContent=(s.current||"")+" ("+(s.done||0)+"/"+(s.total||0)+")";'
        '}else if(s.elapsed!==null){'
        'clearInterval(_ttPoll);_ttPoll=null;'
        'var okN=s.succeeded||0,ngN=s.failed||0,errs=s.errors||[];'
        'if(s.error){'
        'btn.textContent="Error";btn.classList.remove("btn-freeze-running");btn.disabled=false;'
        'st.textContent=s.error;'
        '_ttShowModal({kind:"error",title:"Temp Table \uc0ad\uc81c \uc624\ub958",'
        'ok:0,ng:0,elapsed:s.elapsed,errors:[{table:"(worker)",error:s.error}],reload:false});'
        '}else if(ngN>0){'
        'btn.textContent="Partial / Failed";btn.classList.remove("btn-freeze-running");btn.disabled=false;'
        'st.textContent="Succeeded: "+okN+" / Failed: "+ngN+" ("+s.elapsed+"s)";'
        '_ttShowModal({kind:(okN>0?"warn":"error"),title:"Temp Table \uc0ad\uc81c \uacb0\uacfc",'
        'ok:okN,ng:ngN,elapsed:s.elapsed,errors:errs,reload:(okN>0)});'
        '}else{'
        'btn.innerHTML="\\u2713 Done";btn.classList.remove("btn-freeze-running");'
        'btn.classList.add("btn-freeze-done");'
        'st.textContent="Dropped "+okN+" tables ("+s.elapsed+"s)";'
        '_ttShowModal({kind:"ok",title:"Temp Table \uc0ad\uc81c \uc644\ub8cc",'
        'ok:okN,ng:0,elapsed:s.elapsed,errors:[],reload:true});'
        '}'
        '}'
        '});'
        '}'

        'function _ttEsc(s){return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}'
        'function _ttCloseModal(reload){var o=document.getElementById("tt-modal");if(o)o.remove();if(reload)location.reload();}'
        'function _ttShowModal(opt){'
        '  var ok=opt.ok||0,ng=opt.ng||0,errs=opt.errors||[],kind=opt.kind||"ok";'
        '  var accent=(kind==="ok")?"#10B981":((kind==="warn")?"#F59E0B":"#EF4444");'
        '  var accentBg=(kind==="ok")?"rgba(16,185,129,.1)":((kind==="warn")?"rgba(245,158,11,.12)":"rgba(239,68,68,.1)");'
        '  var icon=(kind==="ok")'
        '    ?"<svg width=\\"22\\" height=\\"22\\" viewBox=\\"0 0 24 24\\" fill=\\"none\\" stroke=\\"#10B981\\" stroke-width=\\"2.2\\" stroke-linecap=\\"round\\" stroke-linejoin=\\"round\\"><circle cx=\\"12\\" cy=\\"12\\" r=\\"10\\"/><path d=\\"M9 12l2 2 4-4\\"/></svg>"'
        '    :((kind==="warn")'
        '      ?"<svg width=\\"22\\" height=\\"22\\" viewBox=\\"0 0 24 24\\" fill=\\"none\\" stroke=\\"#F59E0B\\" stroke-width=\\"2.2\\" stroke-linecap=\\"round\\" stroke-linejoin=\\"round\\"><path d=\\"M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z\\"/><line x1=\\"12\\" y1=\\"9\\" x2=\\"12\\" y2=\\"13\\"/><line x1=\\"12\\" y1=\\"17\\" x2=\\"12.01\\" y2=\\"17\\"/></svg>"'
        '      :"<svg width=\\"22\\" height=\\"22\\" viewBox=\\"0 0 24 24\\" fill=\\"none\\" stroke=\\"#EF4444\\" stroke-width=\\"2.2\\" stroke-linecap=\\"round\\" stroke-linejoin=\\"round\\"><circle cx=\\"12\\" cy=\\"12\\" r=\\"10\\"/><line x1=\\"15\\" y1=\\"9\\" x2=\\"9\\" y2=\\"15\\"/><line x1=\\"9\\" y1=\\"9\\" x2=\\"15\\" y2=\\"15\\"/></svg>");'
        '  var rows=errs.map(function(e){'
        '    return "<div style=\\"padding:12px 14px;border-top:1px solid #F1F5F9;\\">"'
        '         + "<div style=\\"font-family:\'JetBrains Mono\',\'Consolas\',monospace;font-size:.8rem;font-weight:600;color:#0F172A;margin-bottom:4px;\\">"+_ttEsc(e.table)+"</div>"'
        '         + "<div style=\\"font-size:.76rem;color:#DC2626;line-height:1.5;white-space:pre-wrap;word-break:break-word;\\">"+_ttEsc(e.error)+"</div>"'
        '         + "</div>";'
        '  }).join("");'
        '  var failBlock=errs.length'
        '    ?"<div style=\\"margin-top:14px;border:1px solid #FEE2E2;border-radius:10px;background:#fff;\\">"'
        '     +"<div style=\\"padding:10px 14px;background:#FEF2F2;color:#991B1B;font-size:.72rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;border-radius:10px 10px 0 0;\\">\\uc2e4\\ud328 \\uc0c1\\uc138 ("+errs.length+")</div>"'
        '     +"<div style=\\"max-height:260px;overflow-y:auto;\\">"+rows+"</div></div>"'
        '    :"";'
        '  var html=""'
        '   +"<link href=\\"https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap\\" rel=\\"stylesheet\\">"'
        '   +"<div id=\\"tt-modal\\" style=\\"position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;font-family:\'Noto Sans KR\',\'Segoe UI\',system-ui,sans-serif;letter-spacing:-.01em;\\">"'
        '     +"<div onclick=\\"_ttCloseModal("+(opt.reload?"true":"false")+")\\" style=\\"position:absolute;inset:0;background:rgba(15,23,42,.45);backdrop-filter:blur(3px);\\"></div>"'
        '     +"<div style=\\"position:relative;width:min(520px,92vw);max-height:86vh;background:#fff;border-radius:16px;box-shadow:0 30px 70px rgba(15,23,42,.25),0 10px 24px rgba(15,23,42,.08);border:1px solid rgba(226,232,240,.9);display:flex;flex-direction:column;overflow:hidden;\\">"'
        '       +"<div style=\\"padding:16px 20px 14px;display:flex;gap:10px;align-items:center;border-bottom:1px solid #F1F5F9;\\">"'
        '         +"<div style=\\"flex-shrink:0;width:32px;height:32px;border-radius:9px;background:"+accentBg+";display:flex;align-items:center;justify-content:center;\\">"+icon+"</div>"'
        '         +"<div style=\\"flex:1;min-width:0;\\">"'
        '           +"<div style=\\"font-size:.92rem;font-weight:700;color:#0F172A;line-height:1.25;\\">"+_ttEsc(opt.title)+"</div>"'
        '           +"<div style=\\"font-size:.72rem;color:#64748B;margin-top:2px;\\">\\uacbd\\uacfc "+(opt.elapsed||0)+"s</div>"'
        '         +"</div>"'
        '         +"<button onclick=\\"_ttCloseModal("+(opt.reload?"true":"false")+")\\" style=\\"width:30px;height:30px;border:none;background:transparent;color:#94A3B8;font-size:1.35rem;cursor:pointer;border-radius:6px;line-height:1;\\" onmouseover=\\"this.style.background=\'#E2E8F0\';this.style.color=\'#475569\'\\" onmouseout=\\"this.style.background=\'transparent\';this.style.color=\'#94A3B8\'\\">&times;</button>"'
        '       +"</div>"'
        '       +"<div style=\\"padding:14px 20px;overflow-y:auto;flex:1;\\">"'
        '         +"<div style=\\"display:flex;flex-direction:column;gap:6px;font-size:.84rem;\\">"'
        '           +"<div style=\\"display:flex;align-items:baseline;gap:10px;\\">"'
        '             +"<span style=\\"min-width:88px;font-size:.72rem;font-weight:700;color:#059669;letter-spacing:.08em;text-transform:uppercase;\\">Succeeded</span>"'
        '             +"<span style=\\"color:#64748B;\\">:</span>"'
        '             +"<span style=\\"font-weight:600;color:#0F172A;\\">"+ok+"\\uac74</span>"'
        '           +"</div>"'
        '           +"<div style=\\"display:flex;align-items:baseline;gap:10px;\\">"'
        '             +"<span style=\\"min-width:88px;font-size:.72rem;font-weight:700;color:"+(ng>0?"#B91C1C":"#94A3B8")+";letter-spacing:.08em;text-transform:uppercase;\\">Failed</span>"'
        '             +"<span style=\\"color:#64748B;\\">:</span>"'
        '             +"<span style=\\"font-weight:600;color:"+(ng>0?"#7F1D1D":"#475569")+";\\">"+ng+"\\uac74</span>"'
        '           +"</div>"'
        '         +"</div>"'
        '         +failBlock'
        '       +"</div>"'
        '       +"<div style=\\"padding:14px 20px;border-top:1px solid #F1F5F9;display:flex;justify-content:flex-end;gap:10px;\\">"'
        '         +"<button onclick=\\"_ttCloseModal("+(opt.reload?"true":"false")+")\\" style=\\"padding:9px 22px;border-radius:10px;border:none;background:"+accent+";color:#fff;font-size:.84rem;font-weight:600;cursor:pointer;letter-spacing:.01em;box-shadow:inset 0 1px 0 rgba(255,255,255,.25),0 1px 2px rgba(15,23,42,.06);transition:filter .15s,transform .12s;\\" onmouseover=\\"this.style.filter=\'brightness(1.08)\'\\" onmouseout=\\"this.style.filter=\'\'\\">\\ud655\\uc778</button>"'
        '       +"</div>"'
        '     +"</div>"'
        '   +"</div>";'
        '  var wrap=document.createElement("div");wrap.innerHTML=html;'
        '  while(wrap.firstChild)document.body.appendChild(wrap.firstChild);'
        '}'
        '</script>'
    )

    body = ''.join([
        _page_title_html(title, *_HELP.get('disk_temp_table', (title, ''))),
        '<div class="insp-card">',
        '<div class="insp-card-hdr" style="justify-content:space-between;">',
        '<div class="insp-card-title">Temp Tables</div>',
        drop_btn,
        '</div>',
        '<div class="insp-card-body">', table_html, '</div>',
        '</div>',
        drop_js,
        _ts(),
        _sql_embed(sql),
    ])
    return _page('disk_temp_table', title, body)


def get_disk_top_segment_data():
    from sql_library import _SQL_TOP_SEGMENT
    svc_cfg = load_service_config()
    db_user = svc_cfg.get("repository", {}).get("user", "")
    if db_user:
        query = _SQL_TOP_SEGMENT % db_user.upper()
    else:
        return _warn_box("Please set DB User in Configuration.")


# ── VACUUM FREEZE background state ──
_vf_state = {"running": False, "started": None, "finished": None, "elapsed": None, "error": None}
_vf_lock = threading.Lock()

def _vf_worker():
    import time
    start = time.time()
    try:
        out, err = run_db_query("VACUUM FREEZE;")
        elapsed = round(time.time() - start, 1)
        with _vf_lock:
            _vf_state["running"] = False
            _vf_state["finished"] = _time.strftime("%Y-%m-%d %H:%M:%S")
            _vf_state["elapsed"] = elapsed
            _vf_state["error"] = err
    except Exception as e:
        with _vf_lock:
            _vf_state["running"] = False
            _vf_state["finished"] = _time.strftime("%Y-%m-%d %H:%M:%S")
            _vf_state["elapsed"] = round(time.time() - start, 1)
            _vf_state["error"] = str(e)

def api_vacuum_freeze():
    with _vf_lock:
        if _vf_state["running"]:
            return json.dumps({"ok": False, "error": "Already running since " + (_vf_state["started"] or "")})
        _vf_state["running"] = True
        _vf_state["started"] = _time.strftime("%Y-%m-%d %H:%M:%S")
        _vf_state["finished"] = None
        _vf_state["elapsed"] = None
        _vf_state["error"] = None
    t = threading.Thread(target=_vf_worker, daemon=True)
    t.start()
    return json.dumps({"ok": True, "message": "VACUUM FREEZE started"})

def api_vacuum_freeze_status():
    with _vf_lock:
        return json.dumps({
            "running": _vf_state["running"],
            "started": _vf_state["started"],
            "finished": _vf_state["finished"],
            "elapsed": _vf_state["elapsed"],
            "error": _vf_state["error"],
        })


def api_age_card():
    sql_age = _get_sql("age")
    if not sql_age:
        return json.dumps({"html": _warn_box("Age SQL을 사용할 수 없습니다.")})
    out_age, err_age = run_db_query(sql_age)
    if err_age:
        return json.dumps({"html": _warn_box(err_age)})
    headers, rows = _parse_db_table(out_age or "")
    return json.dumps({"html": _render_db_table_html(headers, rows)})


# ── VACUUM TABLE (per-table) background state ──
_vt_state = {"running": False, "started": None, "finished": None,
             "elapsed": None, "error": None, "current": None, "done": 0, "total": 0}
_vt_lock = threading.Lock()

def _vt_worker(tables):
    import time
    start = time.time()
    done = 0
    try:
        for schema, table in tables:
            with _vt_lock:
                _vt_state["current"] = schema + "." + table
                _vt_state["done"] = done
            fq = schema + "." + table
            out, err = run_db_query("VACUUM " + fq + ";")
            done += 1
        elapsed = round(time.time() - start, 1)
        with _vt_lock:
            _vt_state["running"] = False
            _vt_state["finished"] = _time.strftime("%Y-%m-%d %H:%M:%S")
            _vt_state["elapsed"] = elapsed
            _vt_state["done"] = done
            _vt_state["current"] = None
            _vt_state["error"] = None
    except Exception as e:
        with _vt_lock:
            _vt_state["running"] = False
            _vt_state["finished"] = _time.strftime("%Y-%m-%d %H:%M:%S")
            _vt_state["elapsed"] = round(time.time() - start, 1)
            _vt_state["done"] = done
            _vt_state["current"] = None
            _vt_state["error"] = str(e)

def api_vacuum_table():
    with _vt_lock:
        if _vt_state["running"]:
            return json.dumps({"ok": False, "error": "Already running since " + (_vt_state["started"] or "")})
    # Get the list of tables from vacuum SQL
    sql_vac = _get_sql("vacuum")
    if not sql_vac:
        return json.dumps({"ok": False, "error": "Vacuum SQL을 사용할 수 없습니다."})
    out, err = run_db_query(sql_vac)
    if err:
        return json.dumps({"ok": False, "error": err[:120]})
    headers, rows = _parse_db_table(out or "")
    if not rows:
        return json.dumps({"ok": False, "error": "No tables to vacuum"})
    # Extract schema.table pairs from query result
    h_upper = [h.upper() for h in headers]
    idx_schema = next((i for i, h in enumerate(h_upper) if 'SCHEMA' in h), -1)
    idx_table  = next((i for i, h in enumerate(h_upper) if 'TABLE' in h and 'SCHEMA' not in h), -1)
    if idx_schema < 0 or idx_table < 0:
        return json.dumps({"ok": False, "error": "Cannot parse schema/table from result"})
    tables = []
    for row in rows:
        schema = row[idx_schema].strip() if idx_schema < len(row) else ''
        table  = row[idx_table].strip()  if idx_table  < len(row) else ''
        if schema and table:
            tables.append((schema, table))
    if not tables:
        return json.dumps({"ok": False, "error": "No valid tables found"})
    with _vt_lock:
        _vt_state["running"] = True
        _vt_state["started"] = _time.strftime("%Y-%m-%d %H:%M:%S")
        _vt_state["finished"] = None
        _vt_state["elapsed"] = None
        _vt_state["error"] = None
        _vt_state["current"] = None
        _vt_state["done"] = 0
        _vt_state["total"] = len(tables)
    t = threading.Thread(target=_vt_worker, args=(tables,), daemon=True)
    t.start()
    return json.dumps({"ok": True, "message": "VACUUM TABLE started", "total": len(tables)})

def api_vacuum_table_status():
    with _vt_lock:
        return json.dumps({
            "running": _vt_state["running"],
            "started": _vt_state["started"],
            "finished": _vt_state["finished"],
            "elapsed": _vt_state["elapsed"],
            "error": _vt_state["error"],
            "current": _vt_state["current"],
            "done": _vt_state["done"],
            "total": _vt_state["total"],
        })


# ── TEMP TABLE bulk drop state ──
_tt_state = {"running": False, "started": None, "finished": None,
             "elapsed": None, "error": None, "current": None,
             "done": 0, "total": 0,
             "succeeded": 0, "failed": 0, "errors": []}
_tt_lock = threading.Lock()

def _tt_worker(tables):
    import time as _tm
    start = _tm.time()
    succeeded = 0
    failed = 0
    try:
        from db_utils import run_db_exec
        from service_config import load_service_config as _lsc
        _pg = "postgres" in _lsc().get("repository", {}).get("db_type", "").lower()
        for fq in tables:
            with _tt_lock:
                _tt_state["current"] = fq
                _tt_state["done"] = succeeded + failed
            if _pg:
                err = run_db_exec("DROP TABLE IF EXISTS " + fq)
            else:
                err = run_db_exec("DROP TABLE " + fq + " PURGE")
            if err:
                failed += 1
                with _tt_lock:
                    _tt_state["errors"].append({"table": fq, "error": str(err)[:300]})
            else:
                succeeded += 1
        with _tt_lock:
            _tt_state["running"] = False
            _tt_state["finished"] = _time.strftime("%Y-%m-%d %H:%M:%S")
            _tt_state["elapsed"] = round(_tm.time() - start, 1)
            _tt_state["succeeded"] = succeeded
            _tt_state["failed"] = failed
            _tt_state["done"] = succeeded + failed
            _tt_state["current"] = None
            _tt_state["error"] = None
    except Exception as e:
        with _tt_lock:
            _tt_state["running"] = False
            _tt_state["elapsed"] = round(_tm.time() - start, 1)
            _tt_state["succeeded"] = succeeded
            _tt_state["failed"] = failed
            _tt_state["done"] = succeeded + failed
            _tt_state["error"] = str(e)

def api_temp_table_drop_all():
    with _tt_lock:
        if _tt_state["running"]:
            return json.dumps({"ok": False, "error": "Already running"})
    sql = _get_sql("temp_table")
    if not sql:
        return json.dumps({"ok": False, "error": "SQL을 사용할 수 없습니다."})
    out, err = run_db_query(sql)
    if err:
        return json.dumps({"ok": False, "error": err[:120]})
    headers, rows = _parse_db_table(out or "")
    if not rows:
        return json.dumps({"ok": False, "error": "No tables to drop"})
    h_upper = [h.upper() for h in headers]
    idx_schema = next((i for i, h in enumerate(h_upper) if 'SCHEMA' in h), 0)
    idx_table  = next((i for i, h in enumerate(h_upper) if 'TABLE' in h and 'SCHEMA' not in h), 1)
    import re as _re
    tables = []
    for row in rows:
        schema = row[idx_schema].strip() if idx_schema < len(row) else ''
        table  = row[idx_table].strip()  if idx_table  < len(row) else ''
        if schema and table and table.lower().startswith('tt'):
            if not _re.search(r'[^a-zA-Z0-9_]', schema) and not _re.search(r'[^a-zA-Z0-9_]', table):
                tables.append(schema + '.' + table)
    if not tables:
        return json.dumps({"ok": False, "error": "No valid tt% tables"})
    with _tt_lock:
        _tt_state["running"] = True
        _tt_state["started"] = _time.strftime("%Y-%m-%d %H:%M:%S")
        _tt_state["finished"] = None
        _tt_state["elapsed"] = None
        _tt_state["error"] = None
        _tt_state["current"] = None
        _tt_state["done"] = 0
        _tt_state["total"] = len(tables)
        _tt_state["succeeded"] = 0
        _tt_state["failed"] = 0
        _tt_state["errors"] = []
    t = threading.Thread(target=_tt_worker, args=(tables,), daemon=True)
    t.start()
    return json.dumps({"ok": True, "total": len(tables)})

def api_temp_table_drop_status():
    with _tt_lock:
        return json.dumps({
            "running":   _tt_state["running"],
            "started":   _tt_state["started"],
            "elapsed":   _tt_state["elapsed"],
            "error":     _tt_state["error"],
            "current":   _tt_state["current"],
            "done":      _tt_state["done"],
            "total":     _tt_state["total"],
            "succeeded": _tt_state.get("succeeded", 0),
            "failed":    _tt_state.get("failed", 0),
            "errors":    _tt_state.get("errors", []),
        })
