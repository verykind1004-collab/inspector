# -*- coding: utf-8 -*-
import json
import re

from db_utils import _db_cfg, run_db_query, _parse_db_table, _sql_embed
from sql_library import _get_sql
from html_helpers import (
    _warn_box, _info_box, _page, _HELP_JS, _page_title_html, _HELP, _ts,
    _render_db_table_html, _inst_filter_block,
    _UTILS_BASE,
)


def api_alert_times(inst, alarm):
    """Return per-day occurrence counts for an (instance, alarm) pair over
    the last 30 days. Shape: {ok, days:[{day:'YYYY-MM-DD', count:N}, ...]}"""
    if not inst or not alarm:
        return json.dumps({"ok": False, "error": "Missing parameters"})
    if re.search(r"['\";\\]", inst) or re.search(r"['\";\\]", alarm):
        return json.dumps({"ok": False, "error": "Invalid characters"})
    pg      = "postgresql" in _db_cfg().get("db_type", "").lower()
    inst_e  = inst.replace("'", "''")
    alarm_e = alarm.replace("'", "''")
    if pg:
        schema = re.sub(r'[^a-z0-9_]', '', inst.lower())
        if not schema:
            return json.dumps({"ok": False, "error": "Invalid instance name"})
        sql = (
            "SELECT to_char(date_trunc('day', b.time), 'YYYY-MM-DD') AS \"DAY\",\n"
            "       COUNT(*) AS \"CNT\"\n"
            "FROM %s.ora_alarm_history b\n"
            "JOIN apm_db_info a ON a.db_id = b.db_id\n"
            "WHERE a.instance_name = '%s'\n"
            "  AND b.name = '%s'\n"
            "  AND b.time >= date_trunc('day', NOW() - INTERVAL '1 month')\n"
            "GROUP BY date_trunc('day', b.time)\n"
            "ORDER BY 1 DESC"
        ) % (schema, inst_e, alarm_e)
    else:
        sql = (
            "SELECT TO_CHAR(TRUNC(h.time), 'YYYY-MM-DD') AS \"DAY\",\n"
            "       COUNT(*) AS \"CNT\"\n"
            "FROM apm_db_info a\n"
            "JOIN ora_alarm_history h ON h.db_id = a.db_id\n"
            "WHERE h.time > SYSDATE - 30\n"
            "  AND a.instance_name = '%s'\n"
            "  AND h.name = '%s'\n"
            "GROUP BY TRUNC(h.time)\n"
            "ORDER BY 1 DESC"
        ) % (inst_e, alarm_e)
    out, err = run_db_query(sql)
    if err:
        return json.dumps({"ok": False, "error": err[:120]})
    headers, rows = _parse_db_table(out or "")
    days = []
    for row in rows:
        if not row:
            continue
        day = (row[0] or "").strip()
        cnt = (row[1] or "").strip() if len(row) > 1 else ""
        if day:
            try:
                cnt_val = int(cnt)
            except Exception:
                cnt_val = 0
            days.append({"day": day, "count": cnt_val})
    total = sum(d["count"] for d in days)
    return json.dumps({"ok": True, "days": days, "total": total})


def page_alert():
    sql   = _get_sql("alert")
    title = 'Alert Check'
    sub   = 'Alert history for last 30 days (Down / Disconnect events)'
    if not sql:
        body = ''.join([
            _page_title_html(title, *_HELP.get('alert', (title, ''))),
            _warn_box("현재 DB 타입에서는 지원하지 않는 쿼리입니다."),
        ])
        return _page('alert', title, body)
    out, err = run_db_query(sql)

    tooltip_html = (
        '<div id="alert-tt" data-ov-track style="display:none;position:fixed;z-index:9999;'
        'background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;'
        'padding:12px 16px;box-shadow:0 8px 32px rgba(0,0,0,.35);max-width:480px;'
        'min-width:200px;pointer-events:auto;">'
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;gap:8px;">'
        '<div id="alert-tt-header" style="font-size:.78rem;font-weight:700;'
        'color:#6366F1;line-height:1.4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"></div>'
        '<button id="alert-tt-close" onclick="_aclose()"'
        ' style="display:none;margin-left:8px;width:22px;height:22px;border-radius:50%;'
        'border:1px solid var(--bd);color:var(--c-muted);background:transparent;'
        'font-size:.85rem;cursor:pointer;line-height:1;transition:all .15s;flex-shrink:0;"'
        ' onmouseover="this.style.background=\'var(--bg-main)\';this.style.color=\'var(--c-main)\';this.style.borderColor=\'var(--c-main)\'"'
        ' onmouseout="this.style.background=\'transparent\';this.style.color=\'var(--c-muted)\';this.style.borderColor=\'var(--bd)\'">&times;</button>'
        '</div>'
        '<div id="alert-tt-body" style="max-height:260px;overflow-y:auto;font-size:.8rem;'
        'line-height:1.75;color:var(--c-text);font-variant-numeric:tabular-nums;"></div>'
        '</div>'
    )

    js = (
        '<script>'
        'var _aht=null;var _apinned=false;'
        'function _apos(el,tt){var r=el.getBoundingClientRect();var x=r.left+r.width/2-tt.offsetWidth/2;var y=r.bottom+6;if(x<8)x=8;if(x+tt.offsetWidth>window.innerWidth-8)x=window.innerWidth-tt.offsetWidth-8;if(y+tt.offsetHeight>window.innerHeight-8)y=r.top-tt.offsetHeight-6;tt.style.left=x+"px";tt.style.top=y+"px";}'
        'function _ahide(){if(_apinned)return;_aht=setTimeout(function(){document.getElementById("alert-tt").style.display="none";},150);}'
        'function _aclose(){_apinned=false;clearTimeout(_aht);document.getElementById("alert-tt").style.display="none";}'
        'function _ashow(trigEl,inst,alarm){'
        'clearTimeout(_aht);'
        'var tt=document.getElementById("alert-tt");'
        'var xb=document.getElementById("alert-tt-close");if(xb&&!_apinned)xb.style.display="none";'
        'var hdr=document.getElementById("alert-tt-header");'
        'hdr.innerHTML="<span>"+inst+"</span>"'
        '+" <span style=\\"color:#94a3b8;font-weight:400;margin:0 4px;\\">&mdash;</span> "'
        '+"<span style=\\"color:#ef4444;\\">"+alarm+"</span>";'
        'document.getElementById("alert-tt-body").innerHTML='
        '"<span style=\'color:var(--c-muted)\'>Loading...</span>";'
        '_apos(trigEl,tt);'
        'tt.style.display="block";'
        'fetch("' + _UTILS_BASE + '/api/alert-times?inst="+encodeURIComponent(inst)+"&alarm="+encodeURIComponent(alarm))'
        '.then(function(r){return r.json();})'
        '.then(function(d){'
        'var b=document.getElementById("alert-tt-body");'
        'if(d.ok&&d.days&&d.days.length){'
        'var max=0;d.days.forEach(function(x){if(x.count>max)max=x.count;});'
        'var rows=d.days.map(function(x){'
        'var pct=max>0?Math.round(x.count*100/max):0;'
        'return "<div style=\\"display:flex;align-items:center;gap:10px;padding:3px 0;\\">"'
        '+"<span style=\\"flex-shrink:0;min-width:92px;color:var(--c-muted);font-variant-numeric:tabular-nums;\\">"+x.day+"</span>"'
        '+"<span style=\\"flex:1;height:6px;background:rgba(99,102,241,.08);border-radius:3px;overflow:hidden;min-width:40px;\\">"'
        '+"<span style=\\"display:block;width:"+pct+"%;height:100%;background:linear-gradient(90deg,#6366F1,#8B5CF6);border-radius:3px;\\"></span></span>"'
        '+"<span style=\\"flex-shrink:0;min-width:42px;text-align:right;font-weight:600;color:var(--c-text);font-variant-numeric:tabular-nums;\\">"+x.count+"\\uac74</span>"'
        '+"</div>";'
        '}).join("");'
        'b.innerHTML=rows;'
        '}else if(d.error){'
        'b.innerHTML="<span style=\'color:#f87171\'>"+d.error+"</span>";'
        '}else{b.innerHTML="<span style=\'color:var(--c-muted)\'>조회된 기록이 없습니다.</span>";}'
        '}).catch(function(){'
        'document.getElementById("alert-tt-body").innerHTML='
        '"<span style=\'color:#f87171\'>Request failed.</span>";});}'
        'document.addEventListener("DOMContentLoaded",function(){'
        'var tbl=document.querySelector(".svc-table");'
        'if(!tbl)return;'
        'var ths=tbl.querySelectorAll("thead th");'
        'var instIdx=-1,alarmIdx=-1;'
        'ths.forEach(function(th,i){'
        'var t=th.textContent.trim().toUpperCase();'
        'if(t.indexOf("INSTANCE")!==-1)instIdx=i;'
        'if(t.indexOf("ALARM")!==-1&&t.indexOf("NAME")!==-1)alarmIdx=i;});'
        'if(instIdx<0||alarmIdx<0)return;'
        'tbl.querySelectorAll("tbody tr").forEach(function(tr){'
        'var cells=tr.querySelectorAll("td");'
        'if(!cells[instIdx]||!cells[alarmIdx])return;'
        'var inst=cells[instIdx].textContent.trim();'
        'var alarm=cells[alarmIdx].textContent.trim();'
        'if(!alarm)return;'
        'var cell=cells[alarmIdx];'
        'cell.style.cursor="pointer";'
        'cell.style.textDecoration="underline dotted";'
        'cell.style.textDecorationColor="var(--c-accent)";'
        'cell.addEventListener("mouseenter",function(e){if(!_apinned)_ashow(cell,inst,alarm);});'
        'cell.addEventListener("mouseleave",function(){_ahide();});'
        'cell.addEventListener("click",function(e){e.stopPropagation();'
        '_ashow(cell,inst,alarm);_apinned=true;'
        'document.getElementById("alert-tt-close").style.display="inline-block";});'
        '});'
        'var tt=document.getElementById("alert-tt");'
        'if(tt){tt.addEventListener("mouseenter",function(){clearTimeout(_aht);});'
        'tt.addEventListener("mouseleave",function(){_ahide();});}'
        'document.addEventListener("click",function(e){'
        'var tt=document.getElementById("alert-tt");'
        'if(_apinned&&tt&&window._ovOutside&&window._ovOutside(tt,e))_aclose();});'
        '});'
        '</script>'
    )

    if err:
        card_html = ('<div class="insp-card"><div class="insp-card-body" style="padding:14px 16px;">'
                     + _warn_box(err) + '</div></div>')
        fscript = ''
    else:
        headers, rows = _parse_db_table(out or '')
        if not rows:
            card_html = ('<div class="insp-card"><div class="insp-card-body" style="padding:14px 16px;">'
                         + _info_box("발생한 알람 이력이 없습니다.") + '</div></div>')
            fscript = ''
        else:
            tbl_html = _render_db_table_html(headers, rows)
            tbl_html = tbl_html.replace('<table class="svc-table">', '<table class="svc-table" id="inst-tbl">', 1)
            fui, fscript = _inst_filter_block('inst-tbl')
            fui = fui.replace('margin-bottom:14px;', '')
            card_html = ('<div class="insp-card">'
                         '<div class="insp-card-hdr">' + fui + '</div>'
                         '<div class="insp-card-body">' + tbl_html + '</div>'
                         '</div>')

    body = ''.join([
        _page_title_html(title, *_HELP.get('alert', (title, ''))),
        card_html,
        tooltip_html,
        js,
        _ts(),
        _sql_embed(sql),
        fscript,
    ])
    return _page('alert', title, body)
