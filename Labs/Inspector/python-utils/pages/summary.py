# -*- coding: utf-8 -*-
import json
from datetime import datetime, timedelta
from db_utils import run_db_query, _parse_db_table, _sql_embed
from sql_library import _get_sql
from html_helpers import (
    _badge, _warn_box, _page_title_html, _page, _HELP, _HELP_JS, _ts,
    _UTILS_BASE,
)


def _build_summary_table(headers, rows):
    idx = {}
    for i, h in enumerate(headers):
        hu = h.upper()
        if 'INSTANCE' in hu:
            idx['inst'] = i
        elif 'SUMMARY' in hu and 'TYPE' in hu:
            idx['stype'] = i
        elif 'LAST' in hu or 'LAST_SUMMARY' in hu:
            idx['last'] = i
        elif hu == 'STATUS':
            idx['status'] = i
        elif 'DELAY' in hu:
            idx['delay'] = i

    delay_idx = idx.get('delay', -1)
    visible_cols = [i for i in range(len(headers)) if i != delay_idx]

    th_cells = ''.join(
        '<th class="sortable" onclick="tbSort(this)">%s<span class="sort-ic"></span></th>'
        % headers[i].replace('_', ' ').upper()
        for i in visible_cols
    )

    tr_rows = ''
    for row in rows:
        status_val = row[idx['status']].strip() if 'status' in idx and idx['status'] < len(row) else ''
        delay_val  = row[delay_idx].strip() if delay_idx >= 0 and delay_idx < len(row) else ''
        inst_val   = row[idx['inst']].strip() if 'inst' in idx and idx['inst'] < len(row) else ''
        stype_val  = row[idx['stype']].strip() if 'stype' in idx and idx['stype'] < len(row) else ''
        last_val   = row[idx['last']].strip() if 'last' in idx and idx['last'] < len(row) else ''

        cells_html = []
        for i in visible_cols:
            val = row[i].strip() if i < len(row) else ''

            if i == idx.get('status'):
                uv = status_val.upper()
                if uv == 'OK':
                    cells_html.append('<td>%s</td>' % _badge('ok', val))
                elif uv in ('CHECK', 'ERROR', 'WAITING'):
                    color   = '#f0a644' if uv == 'WAITING' else '#f06a6a'
                    bg      = 'rgba(240,166,68,.12)' if uv == 'WAITING' else 'rgba(240,106,106,.12)'
                    border  = 'rgba(240,166,68,.3)'  if uv == 'WAITING' else 'rgba(240,106,106,.3)'
                    cls     = 'badge-warn' if uv == 'WAITING' else 'badge-crit'
                    # delay 텍스트 색상도 STATUS 와 동일 톤 (WAITING=주황, CHECK/ERROR=빨강).
                    delay_span = (' <span style="color:%s;font-size:.8rem;font-weight:bold;margin-left:4px;">%s</span>' % (color, delay_val)) if delay_val else ''
                    badge_only = (
                        '<span class="badge %s"'
                        ' style="background:%s;color:%s;border:1px solid %s;'
                        'padding:2px 10px;border-radius:9999px;font-size:0.75rem;font-weight:600;'
                        'display:inline-block;line-height:1.2;text-align:center;min-width:32px;"'
                        '>%s</span>%s'
                    ) % (cls, bg, color, border, uv, delay_span)
                    cells_html.append(
                        '<td class="sum-hint" style="cursor:pointer;"'
                        ' data-inst="%s" data-stype="%s" data-last="%s" data-delay="%s" data-status="%s">%s</td>'
                        % (inst_val, stype_val, last_val, delay_val, uv, badge_only))
                else:
                    cells_html.append('<td>%s</td>' % val)
            else:
                cells_html.append('<td>%s</td>' % val)

        tr_rows += '<tr data-inst="%s" data-stype="%s" data-status="%s">%s</tr>' % (
            inst_val.lower(), stype_val, status_val, ''.join(cells_html))

    col_widths = {0: '8%', 1: '22%', 2: '25%', 3: '25%', 4: '20%'}
    col_style = ''.join(
        '<col style="width:%s;">' % col_widths.get(ci, 'auto')
        for ci in range(len(visible_cols))
    )
    return (
        '<div class="tbl-wrap">'
        '<table class="svc-table" id="sum-tbl" style="table-layout:fixed;">'
        '<colgroup>%s</colgroup>'
        '<thead><tr>%s</tr></thead>'
        '<tbody>%s</tbody>'
        '</table>'
        '</div>'
    ) % (col_style, th_cells, tr_rows)


def _summary_filter_page(active, title, sub, sql_key, mode):
    sql = _get_sql(sql_key)
    if not sql:
        body = ''.join([
            _page_title_html(title, *_HELP.get(sql_key, (title, ''))),
            _warn_box("현재 DB 타입에서는 지원하지 않는 쿼리입니다."),
        ])
        return _page(active, title, body)

    out, err = run_db_query(sql)
    if err:
        body = ''.join([
            _page_title_html(title, *_HELP.get(sql_key, (title, ''))),
            _warn_box(err),
            _ts(),
        ])
        return _page(active, title, body)

    headers, rows = _parse_db_table(out or "")
    table_html = _build_summary_table(headers, rows)

    tooltip_html = (
        '<div id="sum-tt" data-ov-track style="display:none;position:fixed;z-index:9999;'
        'background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;'
        'padding:12px 16px;box-shadow:0 8px 32px rgba(0,0,0,.35);max-width:360px;'
        'min-width:220px;pointer-events:auto;">'
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
        '<div id="sum-tt-title" style="font-size:.78rem;font-weight:700;'
        'color:#6366F1;letter-spacing:.02em;white-space:nowrap;"></div>'
        '<div style="display:flex;gap:6px;align-items:center;margin-left:10px;flex-shrink:0;">'
        '<button id="sum-tt-close" onclick="_sclose()"'
        ' style="display:none;width:22px;height:22px;border-radius:50%;'
        'border:1px solid var(--bd);color:var(--c-muted);background:transparent;'
        'font-size:.85rem;cursor:pointer;line-height:1;transition:all .15s;flex-shrink:0;"'
        ' onmouseover="this.style.background=\'var(--bg-main)\';this.style.color=\'var(--c-main)\';this.style.borderColor=\'var(--c-main)\'"'
        ' onmouseout="this.style.background=\'transparent\';this.style.color=\'var(--c-muted)\';this.style.borderColor=\'var(--bd)\'">'
        '&times;</button>'
        '</div>'
        '</div>'
        '<div id="sum-tt-body" style="font-size:.82rem;color:var(--c-muted);line-height:1.7;"></div>'
        '</div>'
    )

    css = (
        '<style>'
        '.inst-chip{padding:6px 14px;font-size:.8rem;color:var(--c-muted);cursor:pointer;'
        'transition:background .1s;white-space:nowrap;}'
        '.inst-chip:hover{background:var(--bg-main);color:var(--c-main);}'
        '.inst-chip b{color:var(--c-accent);font-style:normal;font-weight:700;}'
        '.stype-btn{padding:4px 13px;border-radius:999px;border:1px solid var(--bd);'
        'background:#ffffff;color:var(--c-muted);font-size:.75rem;font-weight:600;'
        'cursor:pointer;transition:all .15s;white-space:nowrap;'
        'font-family:Inter,Pretendard,sans-serif;}'
        '.stype-btn:hover{border-color:var(--c-accent);color:var(--c-accent);}'
        '.stype-btn.active{background:var(--c-accent);border-color:var(--c-accent);color:#fff;}'
        '.sum-hint{cursor:pointer;}'
        '</style>'
    )

    # JS — _spinned 체크를 mouseenter 핸들러에서 수행, _sshow 자체는 항상 실행
    js = (
        '<script>'
        'var _SUM_MODE="' + mode + '";'
        'var _sCur={inst:"",stype:"",last:"",delay:"",status:""};'
        'var _sht=null;var _spinned=false;'

        'function _spos(el,tt){'
        'var r=el.getBoundingClientRect();'
        'var x=r.left+r.width/2-tt.offsetWidth/2;'
        'var y=r.bottom+6;'
        'if(x<8)x=8;'
        'if(x+tt.offsetWidth>window.innerWidth-8)x=window.innerWidth-tt.offsetWidth-8;'
        'if(y+tt.offsetHeight>window.innerHeight-8)y=r.top-tt.offsetHeight-6;'
        'tt.style.left=x+"px";tt.style.top=y+"px";}'

        'function _shide(){if(_spinned)return;_sht=setTimeout(function(){document.getElementById("sum-tt").style.display="none";},150);}'
        'function _sclose(){_spinned=false;clearTimeout(_sht);document.getElementById("sum-tt").style.display="none";}'

        'function _sshow(el){'
        'clearTimeout(_sht);'
        '_sCur={inst:el.dataset.inst,stype:el.dataset.stype,last:el.dataset.last,delay:el.dataset.delay,status:el.dataset.status||""};'
        'var tt=document.getElementById("sum-tt");'
        'var xb=document.getElementById("sum-tt-close");'
        'if(xb&&!_spinned)xb.style.display="none";'
        'document.getElementById("sum-tt-title").textContent=_sCur.inst+" \u2014 "+_sCur.stype;'
        'var body="";'
        'if(_sCur.last)body+=\'<div><span style="color:var(--c-dim)">Last Summary : </span>\'+_sCur.last+\'</div>\';'
        'else body+=\'<div style="color:#f06a6a">No summary record found</div>\';'
        'var _dcol=(_sCur.status==="WAITING")?"#f0a644":"#f06a6a";'
        'if(_sCur.delay)body+=\'<div><span style="color:var(--c-dim)">Delay &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;: </span><span style="color:\'+_dcol+\';font-weight:600;">\'+_sCur.delay+\'</span></div>\';'
        'document.getElementById("sum-tt-body").innerHTML=body;'
        'tt.style.display="block";_spos(el,tt);}'

        '(function(){'
        'var tbl=document.getElementById("sum-tbl");'
        'if(!tbl)return;'
        'var rows=Array.prototype.slice.call(tbl.querySelectorAll("tbody tr"));'
        'var instances=[];var stypes=[];var iSet={};var sSet={};'
        'rows.forEach(function(tr){'
        'var inst=tr.dataset.inst||"";'
        'var stype=tr.dataset.stype||"";'
        'if(inst&&!iSet[inst]){iSet[inst]=1;instances.push(inst);}'
        'if(stype&&!sSet[stype]){sSet[stype]=1;stypes.push(stype);}'
        '});'
        'stypes.sort();'
        'var activeStype="ALL";'
        'var stypeWrap=document.getElementById("stype-btns");'
        'var allBtn=document.createElement("button");'
        'allBtn.className="stype-btn active";allBtn.textContent="ALL";allBtn.dataset.stype="ALL";'
        'allBtn.onclick=function(){setStype("ALL");};'
        'stypeWrap.appendChild(allBtn);'
        'stypes.forEach(function(st){'
        'var b=document.createElement("button");b.className="stype-btn";'
        'b.textContent=st;b.dataset.stype=st;'
        'b.onclick=function(){setStype(st);};'
        'stypeWrap.appendChild(b);'
        '});'
        'function setStype(st){'
        'activeStype=st;'
        'stypeWrap.querySelectorAll(".stype-btn").forEach(function(b){'
        'b.classList.toggle("active",b.dataset.stype===st);});'
        'applyFilter();}'
        'function applyFilter(){'
        'var q=document.getElementById("inst-srch").value.trim().toLowerCase();'
        'var vis=0;'
        'rows.forEach(function(tr){'
        'var im=!q||(tr.dataset.inst||"").indexOf(q)!==-1;'
        'var sm=activeStype==="ALL"||(tr.dataset.stype||"")===activeStype;'
        'var show=im&&sm;tr.style.display=show?"":"none";if(show)vis++;'
        '});'
        'document.getElementById("sum-no-res").style.display=vis?"none":"";'
        'tbl.style.display=vis?"":"none";'
        'updateSugg(q);}'
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
        'd.onclick=function(){'
        'document.getElementById("inst-srch").value=name;'
        'sg.style.display="none";applyFilter();};'
        'sg.appendChild(d);});'
        'sg.style.display="";}'
        'window.sumFilter=applyFilter;'
        'document.addEventListener("click",function(e){'
        'var sg=document.getElementById("inst-sugg");'
        'if(sg&&!sg.contains(e.target)&&e.target.id!=="inst-srch")sg.style.display="none";'
        '});'

        'var tt=document.getElementById("sum-tt");'
        'if(tt){'
        'tt.addEventListener("mouseenter",function(){clearTimeout(_sht);});'
        'tt.addEventListener("mouseleave",_shide);}'
        'document.querySelectorAll(".sum-hint").forEach(function(el){'
        'el.addEventListener("mouseenter",function(){if(!_spinned)_sshow(el);});'
        'el.addEventListener("mouseleave",_shide);'
        'el.addEventListener("click",function(e){'
        'e.stopPropagation();_sshow(el);_spinned=true;'
        'document.getElementById("sum-tt-close").style.display="inline-block";'
        '});'
        '});'
        'document.addEventListener("click",function(e){'
        'var tt=document.getElementById("sum-tt");'
        'if(_spinned&&tt&&window._ovOutside&&window._ovOutside(tt,e))_sclose();'
        '});'
        '})();'
        'function _instXToggle(){'
        'var x=document.getElementById("inst-x");if(!x)return;'
        'x.style.display=document.getElementById("inst-srch").value?"":"none";'
        '}'
        '</script>'
    )

    # ── Summary Check 새 디자인 (참고: maxgauge-1hour-check.html) ─────────────
    # filter-bar(검색+필터) + 데이터 테이블을 한 개의 사각 카드 안에 묶고,
    # 테이블 본문 글씨 색을 선명하게(#1A1D2E) 적용. 헤더 색은 예전 그대로
    # (#ECF0F7 / #5F6B80). 사이드바/topbar/그룹핑 버튼 보라색 active는 유지.
    card_css = (
        '<style>'
        '.sum-card{background:#ffffff;border:1px solid #E4E6ED;border-radius:0;'
        'box-shadow:0 1px 3px rgba(0,0,0,.06);overflow:hidden;'
        'display:flex;flex-direction:column;animation:sumFadeUp .35s ease both;}'
        '@keyframes sumFadeUp{from{opacity:0;transform:translateY(10px)}'
        'to{opacity:1;transform:translateY(0)}}'
        '.sum-card .sum-filter{display:flex;align-items:center;gap:10px;'
        'flex-wrap:wrap;padding:14px 18px;border-bottom:1px solid #E4E6ED;'
        'background:#ffffff;margin:0;}'
        '.sum-card .sum-tbl-wrap{flex:1;overflow:auto;background:#ffffff;}'
        '.sum-card .tbl-wrap{border:none!important;border-radius:0!important;'
        'box-shadow:none!important;background:#ffffff!important;overflow:visible!important;}'
        '.sum-card #sum-tbl{width:100%;border-collapse:collapse;font-size:13px;}'
        '.sum-card #sum-tbl thead th{padding:10px 16px;background:#ECF0F7;'
        'border-bottom:1px solid #D8DEE8;font-size:.72rem;font-weight:700;'
        'letter-spacing:.04em;text-transform:uppercase;color:#5F6B80;'
        'text-align:center;}'
        '.sum-card #sum-tbl tbody td{padding:13px 16px;'
        'border-bottom:1px solid #F0F1F5;text-align:center;color:#1A1D2E;}'
        '.sum-card #sum-tbl tbody tr:hover td{background:#F0F6FF;}'
        '.sum-card #sum-tbl tbody tr:last-child td{border-bottom:none;}'
        '</style>'
    )
    filter_ui_card = (
        '<div class="sum-filter">'
        '<div style="position:relative;">'
        '<input id="inst-srch" type="text" placeholder="Search instance name..."'
        ' autocomplete="off" oninput="sumFilter();_instXToggle();"'
        ' style="background:#fafafa;border:1px solid #E4E6ED;color:#1A1D2E;'
        'border-radius:8px;padding:6px 28px 6px 12px;font-size:12.5px;width:200px;'
        'outline:none;transition:border-color .15s,box-shadow .15s;'
        'font-family:Inter,Pretendard,sans-serif;"'
        ' onfocus="this.style.borderColor=\'#2563EB\';this.style.boxShadow=\'0 0 0 3px rgba(37,99,235,.08)\';this.style.background=\'#fff\'"'
        ' onblur="this.style.borderColor=\'#E4E6ED\';this.style.boxShadow=\'none\';this.style.background=\'#fafafa\'">'
        '<span id="inst-x" onclick="document.getElementById(\'inst-srch\').value=\'\';sumFilter();_instXToggle();"'
        ' style="display:none;position:absolute;right:8px;top:50%;transform:translateY(-50%);'
        'cursor:pointer;color:#94A3B8;font-size:.85rem;line-height:1;padding:2px;"'
        ' onmouseover="this.style.color=\'#334155\'"'
        ' onmouseout="this.style.color=\'#94A3B8\'"'
        '>&#x2715;</span>'
        '<div id="inst-sugg"'
        ' style="display:none;position:absolute;top:calc(100%% + 4px);left:0;'
        'background:#ffffff;border:1px solid #E4E6ED;border-radius:8px;'
        'min-width:220px;max-height:200px;overflow-y:auto;z-index:200;'
        'box-shadow:0 6px 24px rgba(0,0,0,.12);padding:4px 0;"></div>'
        '</div>'
        '<div id="stype-btns" style="display:flex;gap:6px;flex-wrap:wrap;'
        'align-items:center;"></div>'
        '</div>'
        '<div id="sum-no-res" style="display:none;color:var(--c-muted);'
        'font-size:.85rem;padding:14px 0;text-align:center;">'
        '일치하는 결과가 없습니다.</div>'
    )
    body = ''.join([
        '<style>.main{max-height:100vh!important;overflow:hidden!important;}'
        '.content-wrap{padding:24px 28px 48px!important;}</style>',
        _page_title_html(title, *_HELP.get(sql_key, (title, ''))),
        css,
        card_css,
        '<div class="sum-card" style="max-height:calc(100vh - 130px);">',
        filter_ui_card,
        '<div class="sum-tbl-wrap">',
        table_html,
        '</div>',
        '</div>',
        tooltip_html,
        js,
        _ts(),
        _sql_embed(sql),
    ])
    return _page(active, title, body)


def page_summary_10min():
    return _summary_filter_page('summary_10min', '10Min Summary Check',
                                'Checks last 10-minute summary collection status',
                                'summary_10min', '10min')


def page_summary_1hour():
    return _summary_filter_page('summary_1hour', '1Hour Summary Check',
                                'Checks last hourly (Daily) summary collection status',
                                'summary_1hour', '1hour')
