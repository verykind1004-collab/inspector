# -*- coding: utf-8 -*-
import socket
import platform
from datetime import datetime

from service_config import load_service_config
from db_utils import _db_cfg, _sql_embed
from sql_library import _SQL_ORACLE_TABLESPACE_OVERVIEW
from system_utils import (
    _get_pjs_port,
    _cpu_percent, _memory, _pct_status, _disk_for_overview,
    _tablespace_for_overview, _uptime, _cpu_cores,
    _dg_info, _get_dg_version, _get_pjs_version, _get_client_version,
    _get_pid_by_port, _proc_uptime, _proc_uptime_html, _repodb_info,
    _get_repodb_version, _get_repodb_uptime, _pjs_info,
    _platformjs_pid_by_port, _port_is_listening,
)
from html_helpers import (
    _badge, _svc_icon, _bar_dyn, _warn_box, _page_title_html,
    _page, _HELP, _HELP_JS, _ts, _UTILS_BASE, _PLATFORMJS_PORT,
)


def _services_table_html():
    svc  = load_service_config()
    svcs = svc.get("services", {})

    def row(comp, st, pid, port, ver, uptime=None, uptime_id=None):
        _ov = 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
        sid = uptime_id.replace("uptime-", "") if uptime_id else None
        uid  = (' id="%s"'       % uptime_id) if uptime_id else ''
        iid  = (' id="icon-%s"'  % sid)        if sid else ''
        bid  = (' id="badge-%s"' % sid)        if sid else ''
        return (
            '<tr>'
            '<td' + iid + ' style="' + _ov + '">' + _svc_icon(st) + '</td>'
            '<td style="' + _ov + '"><strong>' + comp + '</strong></td>'
            '<td' + bid + ' style="' + _ov + '">' + _badge(st) + '</td>'
            '<td style="' + _ov + 'font-variant-numeric:tabular-nums;">' + port + '</td>'
            '<td style="' + _ov + 'font-variant-numeric:tabular-nums;">' + ver + '</td>'
            '<td' + uid + ' style="' + _ov + 'font-variant-numeric:tabular-nums;">' + (uptime if uptime is not None else _proc_uptime_html(pid)) + '</td>'
            '</tr>'
        )

    rows = ""
    dgm_home = svcs.get("dgserver_m", "")
    dgm = _dg_info(dgm_home)
    rows += row("DGServer_M",
                dgm.get("status", "stopped") if dgm.get("exists") else "stopped",
                dgm.get("pid", "-") if dgm.get("exists") else "-",
                dgm.get("port", "-") if dgm.get("exists") else "-",
                _get_dg_version(dgm_home),
                uptime_id="uptime-dgm")

    for i, dgs_home in enumerate(svcs.get("dgserver_s", [])):
        if not dgs_home:
            continue
        info = _dg_info(dgs_home)
        rows += row("DGServer_S%d" % (i + 1),
                    info.get("status", "stopped"),
                    info.get("pid", "-"),
                    info.get("port", "-"),
                    _get_dg_version(dgs_home),
                    uptime_id="uptime-dgs%d" % (i + 1))

    pjs_home = svcs.get("platformjs", "")
    pjs_port = _get_pjs_port() or _PLATFORMJS_PORT
    pjs_pid  = _get_pid_by_port(pjs_port) or _platformjs_pid_by_port(pjs_port)
    pjs_status = "running" if pjs_pid else ("running" if _port_is_listening(pjs_port) else "stopped")
    rows += row("PlatformJS",
                pjs_status,
                pjs_pid or "-",
                str(pjs_port),
                _get_pjs_version(pjs_home),
                uptime_id="uptime-pjs")

    # Client (web frontend) - not a process, just version info
    client_ver = _get_client_version(pjs_home)
    # Client row: plain text, no badge/icon styling
    _ov = 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
    rows += (
        '<tr>'
        '<td style="' + _ov + '"></td>'
        '<td style="' + _ov + '"><strong>Client</strong></td>'
        '<td style="' + _ov + 'color:#94A3B8;text-align:center;">-</td>'
        '<td style="' + _ov + 'color:#94A3B8;font-variant-numeric:tabular-nums;">-</td>'
        '<td style="' + _ov + 'font-variant-numeric:tabular-nums;">' + client_ver + '</td>'
        '<td style="' + _ov + 'color:#94A3B8;font-variant-numeric:tabular-nums;">-</td>'
        '</tr>'
    )

    rdb     = _repodb_info()
    rdb_ver = _get_repodb_version() if rdb["status"] == "running" else "-"
    rdb_up  = _get_repodb_uptime()  if rdb["status"] == "running" else "-"
    rows += row("Repository DB (" + rdb["db_type"] + ")",
                rdb["status"], "-", rdb["port"], rdb_ver, rdb_up,
                uptime_id="uptime-repodb")

    return (
        '<div class="tbl-wrap">'
        '<table class="svc-table" style="table-layout:fixed;">'
        '<colgroup><col style="width:4%"><col style="width:30%"><col style="width:14%"><col style="width:10%"><col style="width:22%"><col style="width:20%"></colgroup><thead><tr><th></th><th>Component</th><th>Status</th><th>Port</th><th>Version</th><th>Uptime</th></tr></thead>'
        '<tbody>' + rows + '</tbody>'
        '</table>'
        '</div>'
    )


def _tablespace_card_html():
    try:
        data = _tablespace_for_overview()

        if isinstance(data, str):
            return ''.join([
                '<div id="ts-tt" style="display:none;"></div>',
                '<div class="insp-card metric-warning" id="card-disk">',
                '<div class="insp-card-hdr"><div class="insp-card-title"><span class="status-dot"></span>Tablespace ' + _badge("warning") + '</div></div>',
                '<div class="insp-card-body" style="padding:14px 16px;">',
                _warn_box(data),
                '</div></div>',
            ])

        if not data or not isinstance(data, list):
            return ''.join([
                '<div id="ts-tt" style="display:none;"></div>',
                '<div class="insp-card metric-warning" id="card-disk">',
                '<div class="insp-card-hdr"><div class="insp-card-title"><span class="status-dot"></span>Tablespace ' + _badge("warning") + '</div></div>',
                '<div class="insp-card-body" style="padding:14px 16px;">',
                _warn_box("No tablespace data available."),
                '</div></div>',
            ])

        order = {"critical": 2, "warning": 1, "ok": 0}
        overall = max(data, key=lambda d: order.get(d.get("status", "ok"), 0))["status"]

        # 본문에는 사용률이 가장 높은 tablespace 하나만 표시 (System/CPU/Memory 카드와
        # 동일한 본문 높이). 나머지는 hover 툴팁에서 사용률과 함께 노출.
        sorted_data = sorted(data, key=lambda d: d.get('percent', 0), reverse=True)
        primary     = sorted_data[0]
        max_pct     = primary.get('percent', 0)

        _CFG_SVG = (
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
            ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/>'
            '<line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/>'
            '<line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/>'
            '<line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/>'
            '<line x1="17" y1="16" x2="23" y2="16"/></svg>'
        )

        # 툴팁: 모든 tablespace 사용률 (사용률 내림차순). primary 는 굵게.
        def _tt_row(d, is_primary):
            nm  = str(d.get('name', 'UNKNOWN')).upper()
            pct = d.get('percent', 0)
            color = '#ef4444' if d.get('status') == 'critical' else ('#f59e0b' if d.get('status') == 'warning' else '#22c55e')
            return ('<div style="font-size:.82rem;padding:4px 0;color:var(--c-main);'
                    'display:flex;justify-content:space-between;gap:14px;'
                    + ('font-weight:700;' if is_primary else '')
                    + '">'
                    '<span>' + nm + '</span>'
                    '<span style="font-variant-numeric:tabular-nums;color:' + color + ';">'
                    + ('%.1f%%' % pct) + '</span>'
                    '</div>')
        ts_tt_rows = ''.join(_tt_row(d, d is primary) for d in sorted_data)

        # ts-tt(툴팁) 은 position:fixed 라 grid 슬롯을 차지하지 않음. insp-card 는
        # grid 의 직접 자식이 되어 align-items:stretch 가 정상 적용됨.
        parts = [
            '<div id="ts-tt" style="display:none;position:fixed;z-index:9999;'
            'background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;'
            'padding:12px 16px;box-shadow:0 8px 32px rgba(0,0,0,.35);'
            'max-width:340px;min-width:220px;pointer-events:none;">'
            '<div style="font-size:.7rem;font-weight:700;text-transform:uppercase;'
            'letter-spacing:.07em;color:var(--c-dim);margin-bottom:8px;">TABLESPACE</div>'
            '<div style="max-height:240px;overflow-y:auto;">' + ts_tt_rows + '</div>'
            '</div>',
            '<div class="insp-card ov-metric metric-' + overall + '" id="card-disk" data-pct="' + str(max_pct) + '">',
            '<div class="insp-card-hdr" style="justify-content:space-between;flex-wrap:nowrap;">'
            '<div class="insp-card-title" style="cursor:pointer;min-width:0;" onmouseenter="_tsTtShow(event)" onmouseleave="_tsTtHide()">'
            '<span class="status-dot"></span>Tablespace <span id="badge-disk">' + _badge(overall) + '</span></div>'
            '<div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">'
            '<button class="ov-cfg-btn" onclick="openThPanel(\'disk\')" title="Threshold">' + _CFG_SVG + '</button>'
            '<button class="svc-refresh-btn" id="ts-refresh-btn" onclick="refreshTablespace(true)" title="Refresh">&#8635;</button>'
            '</div></div>',
            '<div class="insp-card-body" style="padding:18px 22px;">',
            '<div class="row"><span class="lbl">Total</span>'
            '<span class="val">%.2f GB</span></div>' % primary.get("total_gb", 0),
            '<div class="row"><span class="lbl">Used</span>'
            '<span class="val">%.2f GB</span></div>' % primary.get("used_gb", 0),
            '<div class="row"><span class="lbl">Free</span>'
            '<span class="val">%.2f GB</span></div>' % primary.get("free_gb", 0),
            _bar_dyn(primary.get("percent", 0), primary.get("status", "ok")),
            '</div>',
            '</div>',
        ]
        return "".join(parts)

    except Exception as e:
        return ''.join([
            '<div id="ts-tt" style="display:none;"></div>',
            '<div class="insp-card metric-critical" id="card-disk">',
            '<div class="insp-card-hdr"><div class="insp-card-title"><span class="status-dot"></span>Tablespace ' + _badge("critical") + '</div></div>',
            '<div class="insp-card-body" style="padding:14px 16px;">',
            _warn_box("Render Error: " + str(e)),
            '</div></div>',
        ])


def page_overview():
    cpu     = _cpu_percent()
    mem     = _memory()
    cpu_st  = _pct_status(cpu["percent"], 60, 80)
    db_conf = load_service_config().get("repository", {})
    db_type = db_conf.get("db_type", "Oracle").lower()
    is_oracle = "oracle" in db_type

    _CFG_SVG = (
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
        ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/>'
        '<line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/>'
        '<line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/>'
        '<line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/>'
        '<line x1="17" y1="16" x2="23" y2="16"/></svg>'
    )

    if is_oracle:
        disk_card = _tablespace_card_html()
    else:
        disk = _disk_for_overview()
        disk_card = ''.join([
            '<div class="insp-card ov-metric metric-' + disk["status"] + '" id="card-disk" data-pct="' + str(disk["percent"]) + '">',
            '<div class="insp-card-hdr" style="justify-content:space-between;">',
            '<div class="insp-card-title"><span class="status-dot"></span>Disk <span id="badge-disk">' + _badge(disk["status"]) + '</span></div>',
            '<button class="ov-cfg-btn" onclick="openThPanel(\'disk\')" title="Threshold">' + _CFG_SVG + '</button>',
            '</div>',
            '<div class="insp-card-body" style="padding:18px 22px;">',
            '' if not disk.get("error") else _warn_box(disk["error"]),
            '<div class="row"><span class="lbl">Total</span><span class="val">' + str(disk["total_gb"]) + ' GB</span></div>',
            '<div class="row"><span class="lbl">Used</span><span class="val">' + str(disk["used_gb"]) + ' GB</span></div>',
            '<div class="row"><span class="lbl">Free</span><span class="val">' + str(disk["free_gb"]) + ' GB</span></div>',
            _bar_dyn(disk["percent"], disk["status"]),
            '</div></div>',
        ])

    body = ''.join([
        _page_title_html('Overview', *_HELP.get('overview', ('Overview', ''))),
        '<div class="grid">',

        # System card — Inspector 가 떠 있으면 hostname/OS/uptime/cores 는 항상 수집되므로 OK 로 표시
        '<div class="insp-card metric-ok">',
        '<div class="insp-card-hdr"><div class="insp-card-title"><span class="status-dot"></span>System</div></div>',
        '<div class="insp-card-body" style="padding:18px 22px;">',
        '<div class="row"><span class="lbl">Hostname</span><span class="val">' + socket.gethostname() + '</span></div>',
        '<div class="row"><span class="lbl">OS</span><span class="val">' + platform.system() + ' ' + platform.release() + '</span></div>',
        '<div class="row"><span class="lbl">Uptime</span><span class="val">' + _uptime() + '</span></div>',
        '<div class="row"><span class="lbl">Cores</span><span class="val">' + str(_cpu_cores()) + '</span></div>',
        '</div></div>',

        # CPU card
        '<div class="insp-card ov-metric metric-' + cpu_st + '" id="card-cpu" data-pct="' + str(cpu["percent"]) + '">',
        '<div class="insp-card-hdr" style="justify-content:space-between;">',
        '<div class="insp-card-title"><span class="status-dot"></span>CPU <span id="badge-cpu">' + _badge(cpu_st) + '</span></div>',
        '<button class="ov-cfg-btn" onclick="openThPanel(\'cpu\')" title="Threshold">' + _CFG_SVG + '</button>',
        '</div>',
        '<div class="insp-card-body" style="padding:18px 22px;">',
        '<div class="row"><span class="lbl">User</span><span class="val">' + str(cpu["user"]) + '%</span></div>',
        '<div class="row"><span class="lbl">System</span><span class="val">' + str(cpu["system"]) + '%</span></div>',
        '<div class="row"><span class="lbl">I/O Wait</span><span class="val">' + str(cpu["iowait"]) + '%</span></div>',
        _bar_dyn(cpu["percent"], cpu_st),
        '</div></div>',

        # Memory card
        '<div class="insp-card ov-metric metric-' + mem["status"] + '" id="card-mem" data-pct="' + str(mem["percent"]) + '">',
        '<div class="insp-card-hdr" style="justify-content:space-between;">',
        '<div class="insp-card-title"><span class="status-dot"></span>Memory <span id="badge-mem">' + _badge(mem["status"]) + '</span></div>',
        '<button class="ov-cfg-btn" onclick="openThPanel(\'mem\')" title="Threshold">' + _CFG_SVG + '</button>',
        '</div>',
        '<div class="insp-card-body" style="padding:18px 22px;">',
        '<div class="row"><span class="lbl">Total</span><span class="val">' + str(mem["total_gb"]) + ' GB</span></div>',
        '<div class="row"><span class="lbl">Used</span><span class="val">' + str(mem["used_gb"]) + ' GB</span></div>',
        '<div class="row"><span class="lbl">Free</span><span class="val">' + str(mem["free_gb"]) + ' GB</span></div>',
        _bar_dyn(mem["percent"], mem["status"]),
        '</div></div>',

        disk_card,
        '</div>',

        # Services card
        '<div class="insp-card">',
        '<div class="insp-card-hdr" style="justify-content:space-between;">',
        '<div class="insp-card-title">Services</div>',
        '<button id="svc-refresh-btn" class="svc-refresh-btn" onclick="refreshServices()" title="Refresh">&#8635;</button>',
        '</div>',
        '<div class="insp-card-body" id="svc-table-wrap">',
        _services_table_html(),
        '</div>',
        '</div>',

        # Threshold settings panel
        '<div id="ov-th-panel" style="display:none;position:fixed;inset:0;z-index:10000;'
        'align-items:center;justify-content:center;background:rgba(0,0,0,.35);">',
        '<div style="background:#ffffff;border:1px solid #E2E8F0;border-radius:14px;'
        'padding:24px 28px;min-width:290px;box-shadow:0 8px 32px rgba(15,23,42,.15);">',
        '<div id="ov-th-title" style="font-size:.9rem;font-weight:700;color:#0F172A;margin-bottom:18px;"></div>',
        '<div style="margin-bottom:14px;">',
        '<label style="font-size:.78rem;color:#64748B;display:block;margin-bottom:6px;">WARNING (%)</label>',
        '<input id="ov-th-warn" type="number" min="1" max="99" style="width:100%%;padding:8px 12px;'
        'border-radius:8px;border:1px solid #CBD5E1;background:#ffffff;color:#0F172A;font-size:.9rem;box-sizing:border-box;">',
        '</div>',
        '<div style="margin-bottom:20px;">',
        '<label style="font-size:.78rem;color:#64748B;display:block;margin-bottom:6px;">CRITICAL (%)</label>',
        '<input id="ov-th-crit" type="number" min="1" max="99" style="width:100%%;padding:8px 12px;'
        'border-radius:8px;border:1px solid #CBD5E1;background:#ffffff;color:#0F172A;font-size:.9rem;box-sizing:border-box;">',
        '</div>',
        '<div style="display:flex;gap:10px;">',
        '<button onclick="applyThPanel()" style="flex:1;padding:9px;border-radius:8px;border:none;'
        'background:#6366F1;color:#fff;font-weight:600;cursor:pointer;font-size:.85rem;">Apply</button>',
        '<button onclick="closeThPanel()" style="flex:1;padding:9px;border-radius:8px;'
        'border:1px solid #E2E8F0;background:transparent;color:#64748B;cursor:pointer;font-size:.85rem;">Cancel</button>',
        '</div>',
        '</div></div>',

        # Threshold JS
        '<script>',
        '(function(){',
        'var DEFS={cpu:[60,80],mem:[80,90],disk:[80,90]};',
        'var BC={"ok":"background:#dcfce7;color:#15803d;border:1px solid #bbf7d0;",',
        '"warning":"background:#fef3c7;color:#92400e;border:1px solid #fde68a;",',
        '"critical":"background:#fee2e2;color:#dc2626;border:1px solid #fecaca;"};',
        'var BCS="padding:2px 10px;border-radius:9999px;font-size:0.75rem;font-weight:600;display:inline-block;line-height:1.2;text-align:center;min-width:32px;";',
        'var BARC={ok:"#22c55e",warning:"#eab308",critical:"#ef4444"};',
        'var BCLS={ok:"badge-ok",warning:"badge-warn",critical:"badge-crit"};',
        'function getTh(k){try{var v=JSON.parse(localStorage.getItem("ov_th_"+k));if(v&&v.length===2)return v;}catch(e){}return DEFS[k];}',
        'function setTh(k,w,c){localStorage.setItem("ov_th_"+k,JSON.stringify([w,c]));}',
        'function st(p,w,c){return p>=c?"critical":p>=w?"warning":"ok";}',
        'function applyCard(key){',
        '  var th=getTh(key);var w=th[0],c=th[1];',
        '  var card=document.getElementById("card-"+key);if(!card)return;',
        '  var pct=parseFloat(card.getAttribute("data-pct")||0);',
        '  var s=st(pct,w,c);',
        '  card.classList.remove("metric-ok","metric-warning","metric-critical");',
        '  card.classList.add("metric-"+s);',
        '  var badge=document.getElementById("badge-"+key);',
        '  if(badge)badge.innerHTML=\'<span class="badge \'+BCLS[s]+\'" style="\'+BCS+BC[s]+\'">\'+s.toUpperCase()+\'</span>\';',
        '  card.querySelectorAll("[data-bar-pct]").forEach(function(el){',
        '    var bp=parseFloat(el.getAttribute("data-bar-pct"));',
        '    el.style.background=BARC[st(bp,w,c)];',
        '  });',
        '}',
        'var _k=null;',
        'window.openThPanel=function(k){',
        '  _k=k;var th=getTh(k);',
        '  document.getElementById("ov-th-warn").value=th[0];',
        '  document.getElementById("ov-th-crit").value=th[1];',
        '  var L={cpu:"CPU",mem:"Memory",disk:"Disk"};',
        '  document.getElementById("ov-th-title").textContent=(L[_k]||_k)+" Threshold";',
        '  document.getElementById("ov-th-panel").style.display="flex";',
        '};',
        'window.closeThPanel=function(){document.getElementById("ov-th-panel").style.display="none";};',
        'window.applyThPanel=function(){',
        '  var w=parseInt(document.getElementById("ov-th-warn").value);',
        '  var c=parseInt(document.getElementById("ov-th-crit").value);',
        '  if(isNaN(w)||isNaN(c)||w<1||c<1||w>=c){alert("WARNING must be less than CRITICAL (1-99)");return;}',
        '  setTh(_k,w,c);applyCard(_k);closeThPanel();',
        '};',
        'window.applyCard=applyCard;',
        'document.addEventListener("DOMContentLoaded",function(){["cpu","mem","disk"].forEach(applyCard);});',
        '})();',
        '</script>',

        # Services + Tablespace refresh JS
        '<script>',
        'function refreshServices(){',
        '  var btn=document.getElementById("svc-refresh-btn");',
        '  btn.classList.add("spinning");',
        '  fetch("' + _UTILS_BASE + '/api/services")',
        '    .then(function(r){return r.json();})',
        '    .then(function(d){',
        '      document.getElementById("svc-table-wrap").innerHTML=d.html;',
        '      btn.classList.remove("spinning");',
        '    })',
        '    .catch(function(){btn.classList.remove("spinning");});',
        '}',
        'var _tsBusy=false;',
        'function refreshTablespace(force){',
        '  if(_tsBusy)return;_tsBusy=true;',
        '  var btn=document.getElementById("ts-refresh-btn");',
        '  if(btn)btn.classList.add("spinning");',
        '  var url="' + _UTILS_BASE + '/api/tablespace"+(force?"?force=1":"");',
        '  fetch(url)',
        '    .then(function(r){return r.json();})',
        '    .then(function(d){',
        '      if(d.html){',
        # 응답 HTML 안에 #ts-tt 와 #card-disk 두 요소가 들어 있음. 각각 기존 노드를 교체.
        '        var tmp=document.createElement("div");tmp.innerHTML=d.html;',
        '        var newTt=tmp.querySelector("#ts-tt");',
        '        var newCard=tmp.querySelector("#card-disk");',
        '        var oldTt=document.getElementById("ts-tt");',
        '        var oldCard=document.getElementById("card-disk");',
        '        if(newTt&&oldTt){oldTt.parentNode.replaceChild(newTt,oldTt);}',
        '        if(newCard&&oldCard){oldCard.parentNode.replaceChild(newCard,oldCard);}',
        '        if(typeof applyCard==="function")applyCard("disk");',
        '      }',
        '      var b=document.getElementById("ts-refresh-btn");',
        '      if(b)b.classList.remove("spinning");',
        '      _tsBusy=false;',
        '    })',
        '    .catch(function(){',
        '      var b=document.getElementById("ts-refresh-btn");if(b)b.classList.remove("spinning");',
        '      _tsBusy=false;',
        '    });',
        '}',
        # Oracle 만 /api/tablespace 호출. PG 는 서버에서 _disk_for_overview() 로 이미
        # Disk 카드를 채워 보냈으므로 refreshTablespace 가 돌면 Oracle 전용 SQL 이 실패해
        # 화면이 깨짐. 따라서 PG 에서는 자동 새로고침 비활성화.
        'document.addEventListener("DOMContentLoaded",function(){if(window.__OV_IS_ORACLE__)refreshTablespace(false);});',
        'function _tsTtShow(e){',
        '  var tt=document.getElementById("ts-tt");',
        '  if(!tt)return;',
        '  tt.style.display="block";',
        '  var x=e.clientX+14,y=e.clientY+14;',
        '  if(x+220>window.innerWidth)x=e.clientX-240;',
        '  if(y+160>window.innerHeight)y=e.clientY-170;',
        '  tt.style.left=x+"px";tt.style.top=y+"px";',
        '}',
        'function _tsTtHide(){',
        '  var tt=document.getElementById("ts-tt");',
        '  if(tt)tt.style.display="none";',
        '}',
        '</script>',
        # Vitals auto-refresh JS
        '<script>',
        '(function(){',
        'function _updCard(id,pct,rows){',
        '  var c=document.getElementById(id);if(!c)return;',
        '  c.setAttribute("data-pct",pct);',
        '  var vs=c.querySelectorAll(".row .val");',
        '  rows.forEach(function(v,i){if(vs[i])vs[i].textContent=v;});',
        '  var bar=c.querySelector("[data-bar-pct]");',
        '  if(bar){',
        '    bar.style.width=pct+"%";bar.setAttribute("data-bar-pct",pct);',
        '    var bwp=bar.parentElement.parentElement;',
        '    var sp=bwp.querySelector("div:first-child span:last-child");',
        '    if(sp)sp.textContent=pct+"%";',
        '  }',
        '  if(typeof applyCard==="function")applyCard(id.replace("card-",""));',
        '}',
        'var _svcBusy=false;',
        'function _autoSvc(){',
        '  if(_svcBusy)return;',
        '  _svcBusy=true;',
        '  fetch("' + _UTILS_BASE + '/api/svc-uptimes")',
        '    .then(function(r){return r.json();})',
        '    .then(function(d){',
        '      Object.keys(d).forEach(function(id){',
        '        var el=document.getElementById(id);',
        '        if(el)el.innerHTML=d[id];',
        '      });',
        '      _svcBusy=false;',
        '    })',
        '    .catch(function(){_svcBusy=false;});',
        '}',
        'function _fmtNow(){',
        '  var n=new Date();',
        '  var p=function(v){return String(v).padStart(2,"0");};',
        '  return n.getFullYear()+"-"+p(n.getMonth()+1)+"-"+p(n.getDate())',
        '       +" "+p(n.getHours())+":"+p(n.getMinutes())+":"+p(n.getSeconds());',
        '}',
        'function _fetchVitals(){',
        '  fetch("' + _UTILS_BASE + '/api/vitals")',
        '    .then(function(r){return r.json();})',
        '    .then(function(d){',
        '      if(d.cpu)_updCard("card-cpu",d.cpu.percent,',
        '        [d.cpu.user+"%",d.cpu.system+"%",d.cpu.iowait+"%"]);',
        '      if(d.mem)_updCard("card-mem",d.mem.percent,',
        '        [d.mem.total_gb+" GB",d.mem.used_gb+" GB",d.mem.free_gb+" GB"]);',
        '    })',
        '    .catch(function(){});',
        '}',
        'document.addEventListener("DOMContentLoaded",function(){',
        '  setInterval(_fetchVitals,3000);',
        '  setInterval(_autoSvc,3000);',
        '});',
        '})();',
        # is_oracle 플래그 — Oracle 일 때만 Tablespace API 자동 호출.
        'window.__OV_IS_ORACLE__=' + ('true' if is_oracle else 'false') + ';',
        '</script>',
    ])
    body += _ts()
    # Oracle 환경에서만 Tablespace 사용량을 SQL 로 수집하므로 Ctrl+Shift+S 팝업에 노출.
    # PG 환경은 os.statvfs() 기반이라 표시할 SQL 없음.
    if is_oracle:
        body += _sql_embed(_SQL_ORACLE_TABLESPACE_OVERVIEW)
    return _page('overview', 'Overview', body)


def page_services():
    svc  = load_service_config()
    svcs = svc.get("services", {})

    def dg_row(comp, info):
        st  = info.get("status", "stopped") if info.get("exists") else "stopped"
        pid = info.get("pid", "-") if info.get("exists") else "-"
        _ov = 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
        return (
            '<tr>'
            '<td style="' + _ov + '">' + _svc_icon(st) + '</td>'
            '<td style="' + _ov + '"><strong>' + comp + '</strong></td>'
            '<td style="' + _ov + '">' + _badge(st) + '</td>'
            '<td style="' + _ov + 'font-variant-numeric:tabular-nums;">' + (info.get("port", "-") if info.get("exists") else "-") + '</td>'
            '<td style="' + _ov + 'font-variant-numeric:tabular-nums;font-family:monospace;color:#94a3b8;font-size:.82rem;">' + _proc_uptime_html(pid) + '</td>'
            '</tr>'
        )

    rows = ""
    dgm_home = svcs.get("dgserver_m", "")
    dgm = _dg_info(dgm_home)
    rows += dg_row("DGServer_M", dgm)

    for i, dgs_home in enumerate(svcs.get("dgserver_s", [])):
        if not dgs_home:
            continue
        rows += dg_row("DGServer_S%d" % (i + 1), _dg_info(dgs_home))

    pjs = _pjs_info(_PLATFORMJS_PORT)
    rows += (
        '<tr>'
        '<td style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + _svc_icon(pjs["status"]) + '</td>'
        '<td style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"><strong>PlatformJS</strong></td>'
        '<td style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + _badge(pjs["status"]) + '</td>'
        '<td style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-variant-numeric:tabular-nums;">' + pjs["port"] + '</td>'
        '<td style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-variant-numeric:tabular-nums;font-family:monospace;color:#94a3b8;font-size:.82rem;">' + _proc_uptime_html(pjs["pid"]) + '</td>'
        '</tr>'
    )

    rdb = _repodb_info()
    rows += (
        '<tr>'
        '<td style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + _svc_icon(rdb["status"]) + '</td>'
        '<td style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"><strong>Repository DB (' + rdb["db_type"] + ')</strong></td>'
        '<td style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + _badge(rdb["status"]) + '</td>'
        '<td style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-variant-numeric:tabular-nums;">' + rdb["port"] + '</td>'
        '<td style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-variant-numeric:tabular-nums;font-family:monospace;color:#94a3b8;font-size:.82rem;">-</td>'
        '</tr>'
    )

    body = ''.join([
        _page_title_html('Services', *_HELP.get('services', ('Services', ''))),
        '<div class="insp-card">',
        '<div class="insp-card-body">',
        '<table class="svc-table" style="table-layout:fixed;">',
        '<colgroup><col style="width:4%"><col style="width:36%"><col style="width:16%"><col style="width:12%"><col style="width:22%"></colgroup><thead><tr><th></th><th>Component</th><th>Status</th>'
        '<th>Port</th><th>Uptime</th></tr></thead>',
        '<tbody>', rows, '</tbody>',
        '</table></div></div>',
    ])
    return _page('services', 'Services', body)


def api_tablespace(force=False):
    import json
    from system_utils import _get_pjs_port,  _TS_CACHE
    if force:
        _TS_CACHE['ts'] = 0  # invalidate cache
    html = _tablespace_card_html()
    return json.dumps({'html': html})


def api_vitals():
    import json
    from system_utils import _get_pjs_port,  _cpu_percent, _memory, _pct_status
    cpu    = _cpu_percent()
    mem    = _memory()
    cpu_st = _pct_status(cpu['percent'], 60, 80)
    return json.dumps({
        'cpu': {
            'percent': cpu['percent'],
            'user':    cpu['user'],
            'system':  cpu['system'],
            'iowait':  cpu['iowait'],
            'status':  cpu_st,
        },
        'mem': {
            'percent':  mem['percent'],
            'total_gb': mem['total_gb'],
            'used_gb':  mem['used_gb'],
            'free_gb':  mem['free_gb'],
            'status':   mem['status'],
        },
    })


def api_svc_uptimes():
    import json
    svc  = load_service_config()
    svcs = svc.get("services", {})
    result = {}

    def _set_svc(sid, st, pid):
        result["uptime-" + sid] = _proc_uptime_html(pid)
        result["icon-"   + sid] = _svc_icon(st)
        result["badge-"  + sid] = _badge(st)

    dgm_home = svcs.get("dgserver_m", "")
    dgm = _dg_info(dgm_home)
    dgm_st  = dgm.get("status", "stopped") if dgm.get("exists") else "stopped"
    dgm_pid = dgm.get("pid", "-") if dgm.get("exists") else "-"
    _set_svc("dgm", dgm_st, dgm_pid)

    for i, dgs_home in enumerate(svcs.get("dgserver_s", [])):
        if not dgs_home:
            continue
        info = _dg_info(dgs_home)
        dgs_st  = info.get("status", "stopped") if info.get("exists") else "stopped"
        dgs_pid = info.get("pid", "-") if info.get("exists") else "-"
        _set_svc("dgs%d" % (i + 1), dgs_st, dgs_pid)

    pjs_port   = _get_pjs_port() or _PLATFORMJS_PORT
    pjs_pid    = _get_pid_by_port(pjs_port) or _platformjs_pid_by_port(pjs_port)
    pjs_status = "running" if pjs_pid else ("running" if _port_is_listening(pjs_port) else "stopped")
    _set_svc("pjs", pjs_status, pjs_pid or "-")

    rdb    = _repodb_info()
    rdb_up = _get_repodb_uptime() if rdb["status"] == "running" else "-"
    result["uptime-repodb"] = rdb_up
    result["icon-repodb"]   = _svc_icon(rdb["status"])
    result["badge-repodb"]  = _badge(rdb["status"])

    return json.dumps(result)
