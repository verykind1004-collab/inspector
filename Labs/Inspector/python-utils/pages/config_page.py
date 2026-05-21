# -*- coding: utf-8 -*-
import json
from service_config import load_service_config, save_service_config
from html_helpers import _page, _UTILS_BASE


def api_connection_test():
    import socket
    import os
    from system_utils import _dg_info, _get_pid_by_port, _platformjs_pid_by_port, _port_is_listening

    cfg  = load_service_config()
    repo = cfg.get("repository", {})
    svcs = cfg.get("services", {})
    results = []

    # Repository DB
    host = repo.get("ip", "")
    port = repo.get("port", "")
    if host and port:
        try:
            s = socket.socket()
            s.settimeout(3)
            s.connect((host, int(port)))
            s.close()
            results.append({"component": "Repository DB (%s)" % repo.get("db_type", ""), "status": "OK",
                            "detail": "%s:%s" % (host, port)})
        except Exception as e:
            results.append({"component": "Repository DB (%s)" % repo.get("db_type", ""), "status": "FAIL",
                            "detail": str(e)})
    else:
        results.append({"component": "Repository DB", "status": "SKIP", "detail": "IP/Port가 설정되지 않았습니다."})

    # DGServer_M
    dgm_home = svcs.get("dgserver_m", "")
    if dgm_home:
        info = _dg_info(dgm_home)
        st = info.get("status", "stopped") if info.get("exists") else "stopped"
        port_str = info.get("port", "-") if info.get("exists") else "-"
        results.append({"component": "DGServer_M", "status": "OK" if st == "running" else "FAIL",
                        "detail": "Port %s / PID %s" % (port_str, info.get("pid", "-")) if info.get("exists") else "Path not found"})
    else:
        results.append({"component": "DGServer_M", "status": "SKIP", "detail": "Not configured"})

    # DGServer_S
    for i, dgs_home in enumerate(svcs.get("dgserver_s", [])):
        name = "DGServer_S%d" % (i + 1)
        if not dgs_home:
            continue
        info = _dg_info(dgs_home)
        st = info.get("status", "stopped") if info.get("exists") else "stopped"
        port_str = info.get("port", "-") if info.get("exists") else "-"
        results.append({"component": name, "status": "OK" if st == "running" else "FAIL",
                        "detail": "Port %s / PID %s" % (port_str, info.get("pid", "-")) if info.get("exists") else "Path not found"})

    # PlatformJS
    pjs_home = svcs.get("platformjs", "")
    if pjs_home:
        import config_loader
        _c = config_loader.load()
        pjs_port = config_loader.get_platformjs_port(_c)
        pid = _get_pid_by_port(pjs_port) or _platformjs_pid_by_port(pjs_port)
        running = bool(pid) or _port_is_listening(pjs_port)
        results.append({"component": "PlatformJS", "status": "OK" if running else "FAIL",
                        "detail": "Port %s / PID %s" % (pjs_port, pid or "-")})
    else:
        results.append({"component": "PlatformJS", "status": "SKIP", "detail": "Not configured"})

    return json.dumps({"results": results})


def _build_config_body(saved=False):
    cfg      = load_service_config()
    repo     = cfg.get("repository", {})
    svcs     = cfg.get("services", {})
    logs     = cfg.get("log_paths", {})
    db_type  = repo.get("db_type", "Oracle")

    # Inspector History config
    from history import _load_insp_config as _lic
    _icfg    = _lic() or {}
    _ih_enabled  = _icfg.get("enabled", False)
    _ih_ret_days = _icfg.get("retention_days", 30)
    _ih_log_ret  = _icfg.get("log_retention_days", 10)
    _is_pg       = db_type == "PostgreSQL"

    dgs_svc  = svcs.get("dgserver_s", [""])
    if not dgs_svc:
        dgs_svc = [""]
    dgs_log  = logs.get("dgserver_s", [])
    while len(dgs_log) < len(dgs_svc):
        dgs_log.append("")

    dgs_svc_rows = ""
    for i, val in enumerate(dgs_svc):
        dgs_svc_rows += (
            '<div class="dgs-row" id="dgs-svc-row-' + str(i) + '">'
            '<input type="text" name="dgserver_s" id="svc_dgs_' + str(i) + '" value="' + val + '" '
            'placeholder="/path/to/DGServer_S' + str(i+1) + '" class="inp" '
            'oninput="syncLog(\'dgs\',' + str(i) + ',this.value)"/>'
            '<button type="button" class="btn-icon" onclick="removeDgs(' + str(i) + ')">-</button>'
            '</div>'
        )

    dgs_log_rows = ""
    for i, lval in enumerate(dgs_log[:len(dgs_svc)]):
        default_log = (dgs_svc[i] + "/log") if dgs_svc[i] else ""
        display_val = lval if lval else default_log
        dgs_log_rows += (
            '<div class="dgs-row" id="dgs-log-row-' + str(i) + '">'
            '<input type="text" name="log_dgserver_s" id="log_dgs_' + str(i) + '" value="' + display_val + '" '
            'placeholder="/path/to/DGServer_S' + str(i+1) + '/log" class="inp"/>'
            '</div>'
        )

    pjs_log_val = logs.get("platformjs", "") or (svcs.get("platformjs", "") + "/log" if svcs.get("platformjs", "") else "")
    dgm_log_val = logs.get("dgserver_m", "") or (svcs.get("dgserver_m", "") + "/log" if svcs.get("dgserver_m", "") else "")

    pg_hide = '' if db_type == 'PostgreSQL' else 'display:none'
    banner  = ''
    pass  # saved flag no longer used

    db_opts = ""
    for dt in ["Oracle", "PostgreSQL"]:
        sel = ' selected' if db_type == dt else ""
        db_opts += '<option value="%s"%s>%s</option>' % (dt, sel, dt)

    body = ''.join([
        '<p class="page-title" style="margin-bottom:24px;">Configuration</p>',
        banner,

        '<style>'
        '.req-field.inp-err{border-color:#EF4444!important;box-shadow:0 0 0 2px rgba(239,68,68,.15)!important;}'
        '.field-err-msg{color:#EF4444;font-size:.72rem;font-weight:600;margin-top:3px;display:none;}'
        '.btn-drop{padding:7px 18px;border-radius:8px;border:1px solid rgba(239,68,68,.3);background:rgba(239,68,68,.06);'
        'color:#B91C1C;font-size:.78rem;font-weight:600;cursor:pointer;transition:all .15s;display:inline-flex;align-items:center;gap:6px;}'
        '.btn-drop:hover{background:rgba(239,68,68,.12);border-color:rgba(239,68,68,.5);}'
        'details summary::-webkit-details-marker{display:none;}'
        '</style>',
        '<form id="config-form" onsubmit="return saveAndTest(event)">',

        '<div class="card">',
        '<div class="card-title" style="background:#ECF0F7;margin:-24px -24px 20px;padding:14px 24px;border-radius:14px 14px 0 0;border-bottom:1px solid #D8DEE8;">Repository Database</div>',
        '<div class="field-grid">',
        '<div class="field"><label>DB Type</label>',
        '<select name="db_type" id="db_type_sel" class="inp" onchange="onDbTypeChange(this.value)">',
        db_opts,
        '</select></div>',
        '<div class="field"><label>SID / Database</label>',
        '<input type="text" name="sid" value="' + repo.get("sid", "") + '" class="inp req-field" placeholder="SID or DB Name"/></div>',
        '<div class="field"><label>Port</label>',
        '<input type="text" name="port" value="' + repo.get("port", "") + '" class="inp req-field" placeholder="1521"/></div>',
        '</div>',
        '<div class="field-grid" style="margin-top:12px">',
        '<div class="field" style="grid-column:1/-1"><label>IP</label>',
        '<input type="text" name="ip" value="' + repo.get("ip", "") + '" class="inp req-field" placeholder="192.168.0.1"/></div>',
        '</div>',
        '<div id="pg_data_row" style="margin-top:12px;' + pg_hide + '">',
        '<div class="field-grid">',
        '<div class="field" style="grid-column:1/-1"><label>PostgreSQL Home Path</label>',
        '<input type="text" name="pg_home" id="pg_home_inp" value="' + repo.get("pg_home", "") + '" class="inp" placeholder="/path/to/postgresql" oninput="syncPgData(this.value)"/></div>',
        '</div>',
        '<div class="field-grid" style="margin-top:8px">',
        '<div class="field" style="grid-column:1/-1"><label>Data Directory</label>',
        '<input type="text" name="pg_data_dir" id="pg_data_inp" value="' + repo.get("pg_data_dir", "") + '" class="inp" placeholder="/path/to/postgresql/data"/></div>',
        '</div>',
        '</div>',
        '<div class="field-grid" style="margin-top:12px">',
        '<div class="field"><label>DB User</label>',
        '<input type="text" name="user" value="' + repo.get("user", "") + '" class="inp req-field" placeholder="username"/></div>',
        '<div class="field"><label>DB Password</label>',
        '<input type="password" name="password" value="' + repo.get("password", "") + '" class="inp req-field" placeholder="password"/></div>',
        '</div>',
        '<div style="display:flex;justify-content:flex-end;gap:10px;margin-top:16px;">',
        '<button type="button" onclick="runConnTest()" style="padding:8px 20px;border-radius:10px;'
        'border:1px solid #6366F1;background:transparent;color:#6366F1;font-size:.84rem;'
        'font-weight:600;cursor:pointer;transition:all .15s;"'
        ' onmouseover="this.style.background=\'#EEF2FF\'"'
        ' onmouseout="this.style.background=\'transparent\'"'
        '>Connection Test</button>',
        '<button type="button" onclick="_saveRepo()" class="btn-save" style="margin:0;padding:8px 28px;">SAVE</button>',
        '</div>',
        '<span id="repo-save-status" style="font-size:.78rem;display:block;margin-top:8px;text-align:right;"></span>',

        # ── 구분선 + 토글 영역 ──
        '<div style="margin-top:16px;border-top:1px solid #E2E8F0;padding-top:4px;">',

        # 토글 1: Collection Settings
        '<details style="margin:0;">'
        '<summary style="font-size:.78rem;font-weight:700;color:#64748B;cursor:pointer;user-select:none;'
        'letter-spacing:.06em;text-transform:uppercase;padding:10px 0;display:flex;align-items:center;gap:6px;list-style:none;">'
        '<span class="sect-arrow" style="font-size:.65rem;transition:transform .2s;">&#9654;</span> Collection Settings</summary>'
        '<div style="padding:0 0 10px;">'
        '<div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:16px 18px;">'
        '<div style="display:flex;align-items:center;gap:14px;margin-bottom:14px;">'
        '<span style="font-size:.85rem;font-weight:600;color:#475569;min-width:140px;">Data Collection</span>'
        '<label style="position:relative;display:inline-block;width:44px;height:24px;cursor:pointer;">'
        '<input type="checkbox" id="ih-chk-enabled"' + (' checked' if _ih_enabled else '') +
        ' onchange="_ihUpdToggle()" style="opacity:0;width:0;height:0;">'
        '<span id="ih-toggle-track" style="position:absolute;inset:0;border-radius:12px;transition:all .2s;'
        + ('background:#6366F1;"' if _ih_enabled else 'background:#CBD5E1;"') +
        '></span>'
        '<span id="ih-toggle-knob" style="position:absolute;top:2px;width:20px;height:20px;border-radius:50%;'
        'background:#fff;transition:all .2s;box-shadow:0 1px 3px rgba(0,0,0,.2);'
        + ('left:22px;"' if _ih_enabled else 'left:2px;"') +
        '></span></label>'
        '<span id="ih-toggle-label" style="font-size:.82rem;font-weight:600;'
        + ('color:#6366F1;"' if _ih_enabled else 'color:#94A3B8;"') +
        '>' + ('ON' if _ih_enabled else 'OFF') + '</span>'
        '</div>'
        '<div style="display:flex;align-items:center;gap:14px;margin-bottom:14px;">'
        '<span style="font-size:.85rem;font-weight:600;color:#475569;min-width:140px;">Retention Period</span>'
        '<input type="number" id="ih-inp-retention" value="' + str(_ih_ret_days) + '" min="1" max="365" '
        'style="width:80px;padding:8px 12px;border-radius:8px;border:1px solid #B0BAC9;background:#fff;'
        'color:#0F172A;font-size:.88rem;text-align:center;">'
        '<span style="font-size:.82rem;color:#64748B;">days</span>'
        '</div>'
        '<div style="display:flex;align-items:center;gap:14px;">'
        '<span style="font-size:.85rem;font-weight:600;color:#475569;min-width:140px;">Log Retention</span>'
        '<input type="number" id="ih-inp-log-ret" value="' + str(_ih_log_ret) + '" min="1" max="365" '
        'style="width:80px;padding:8px 12px;border-radius:8px;border:1px solid #B0BAC9;background:#fff;'
        'color:#0F172A;font-size:.88rem;text-align:center;">'
        '<span style="font-size:.82rem;color:#64748B;">days (IH log files)</span>'
        '</div>'
        '<div style="display:flex;justify-content:flex-end;margin-top:14px;">'
        '<button type="button" onclick="_ihSaveSettings()" class="btn-save" style="margin:0;padding:6px 20px;font-size:.82rem;">Save Settings</button>'
        '</div>'
        '<span id="ih-save-status" style="font-size:.78rem;display:block;margin-top:6px;text-align:right;"></span>'
        '</div></div></details>',

        # 토글 2: Collection Schedule
        '<details style="margin:0;">'
        '<summary style="font-size:.78rem;font-weight:700;color:#64748B;cursor:pointer;user-select:none;'
        'letter-spacing:.06em;text-transform:uppercase;padding:10px 0;display:flex;align-items:center;gap:6px;list-style:none;">'
        '<span class="sect-arrow" style="font-size:.65rem;transition:transform .2s;">&#9654;</span> Collection Schedule</summary>'
        '<div style="padding:0 0 10px;">'
        '<div style="border:1px solid #E5E7EB;border-radius:10px;overflow:hidden;">'
        '<table style="width:100%;border-collapse:collapse;font-size:.84rem;">'
        '<thead><tr style="background:#ECF0F7;">'
        '<th style="text-align:center;padding:10px 14px;color:#5F6B80;font-size:.72rem;font-weight:700;text-transform:uppercase;border-bottom:1px solid #D8DEE8;">수집 지표</th>'
        '<th style="text-align:center;padding:10px 14px;color:#5F6B80;font-size:.72rem;font-weight:700;text-transform:uppercase;border-bottom:1px solid #D8DEE8;">수집 주기</th>'
        '<th style="text-align:center;padding:10px 14px;color:#5F6B80;font-size:.72rem;font-weight:700;text-transform:uppercase;border-bottom:1px solid #D8DEE8;">수집 테이블</th>'
        '<th style="text-align:center;padding:10px 14px;color:#5F6B80;font-size:.72rem;font-weight:700;text-transform:uppercase;border-bottom:1px solid #D8DEE8;">상태</th>'
        '</tr></thead><tbody id="cfg-sched-body"></tbody>'
        '</table></div></div></details>',

        # 토글 3: Drop
        '<details style="margin:0;">'
        '<summary style="font-size:.78rem;font-weight:700;color:#64748B;cursor:pointer;user-select:none;'
        'letter-spacing:.06em;text-transform:uppercase;padding:10px 0;display:flex;align-items:center;gap:6px;list-style:none;">'
        '<span class="sect-arrow" style="font-size:.65rem;transition:transform .2s;">&#9654;</span> Drop</summary>'
        '<div style="padding:0 0 10px;">'
        '<div style="display:flex;gap:10px;flex-wrap:wrap;">'
        '<button type="button" class="btn-drop" onclick="_cfgDrop(\'proc\')">'
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>'
        '<span id="cfg-drop-proc-label">' + ('Drop Procedures' if not _is_pg else 'Drop Functions') + '</span></button>'
        '<button type="button" class="btn-drop" onclick="_cfgDrop(\'table\')">'
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>'
        'Drop Inspector History Tables</button>'
        '</div>'
        '<div style="font-size:.72rem;color:#64748B;margin-top:8px;line-height:1.5;">'
        'Inspector가 생성한 프로시저/함수 및 테이블을 삭제합니다.<br>삭제 후 재사용하려면 다시 생성해야 합니다.</div>'
        '</div></details>',

        '</div>',  # sect-area
        '</div>',  # card

        '<div class="card">',
        '<div class="card-title" style="background:#ECF0F7;margin:-24px -24px 20px;padding:14px 24px;border-radius:14px 14px 0 0;border-bottom:1px solid #D8DEE8;">Service Paths</div>',
        '<div class="path-field"><label>PlatformJS Path</label>',
        '<input type="text" name="platformjs" id="svc_pjs" value="' + svcs.get("platformjs", "") + '" '
        'class="inp" placeholder="/path/to/PlatformJS" oninput="syncLog(\'pjs\',null,this.value)"/></div>',
        '<div class="path-field"><label>DGServer_M Path</label>',
        '<input type="text" name="dgserver_m" id="svc_dgm" value="' + svcs.get("dgserver_m", "") + '" '
        'class="inp" placeholder="/path/to/DGServer_M" oninput="syncLog(\'dgm\',null,this.value)"/></div>',
        '<div class="path-field"><label>DGServer_Sn Paths</label>',
        '<div id="dgs-svc-container">' + dgs_svc_rows + '</div>',
        '<button type="button" class="btn-add" onclick="addDgs()">+ Add DGServer_Sn</button>',
        '</div></div>',

        '<div class="card">',
        '<div class="card-title" style="background:#ECF0F7;margin:-24px -24px 20px;padding:14px 24px;border-radius:14px 14px 0 0;border-bottom:1px solid #D8DEE8;">Log Paths</div>',
        '<div class="path-field"><label>PlatformJS Log Path</label>',
        '<input type="text" name="log_platformjs" id="log_pjs" value="' + pjs_log_val + '" '
        'class="inp" placeholder="/path/to/PlatformJS/log"/></div>',
        '<div class="path-field"><label>DGServer_M Log Path</label>',
        '<input type="text" name="log_dgserver_m" id="log_dgm" value="' + dgm_log_val + '" '
        'class="inp" placeholder="/path/to/DGServer_M/log"/></div>',
        '<div class="path-field"><label>DGServer_Sn Log Paths</label>',
        '<div id="dgs-log-container">' + dgs_log_rows + '</div>',
        '</div>',
        '<div style="display:flex;justify-content:flex-end;margin-top:16px;">',
        '<button type="button" onclick="_savePaths()" class="btn-save" style="margin:0;padding:8px 28px;">SAVE</button>',
        '</div>',
        '<span id="paths-save-status" style="font-size:.78rem;display:block;margin-top:8px;text-align:right;"></span>',
        '</div>',
        '</form>',

        # Connection test popup
        '<div id="ct-overlay" style="display:none;position:fixed;inset:0;z-index:10000;'
        'background:rgba(0,0,0,.4);align-items:center;justify-content:center;"'
        ' onmousedown="_ovMd(event)" onclick="_ovClick(event,function(){document.getElementById(\'ct-overlay\').style.display=\'none\';})">',
        '<div style="background:#ffffff;border:1px solid #E2E8F0;border-radius:16px;'
        'padding:0;min-width:520px;max-width:640px;box-shadow:0 24px 80px rgba(0,0,0,.15);overflow:hidden;">',
        # Header
        '<div style="display:flex;justify-content:space-between;align-items:center;'
        'padding:18px 24px;border-bottom:1px solid #E2E8F0;">',
        '<div style="display:flex;align-items:center;gap:10px;">',
        '<div style="width:28px;height:28px;border-radius:8px;'
        'background:linear-gradient(135deg,#6366F1,#8B5CF6);display:flex;'
        'align-items:center;justify-content:center;box-shadow:0 3px 10px rgba(99,102,241,.4);">'
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" '
        'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg></div>',
        '<span style="font-size:.88rem;font-weight:700;color:#0F172A;letter-spacing:.02em;">Connection Test</span>',
        '</div>',
        '<button onclick="document.getElementById(\'ct-overlay\').style.display=\'none\'" '
        'style="background:none;border:none;font-size:1.1rem;color:#64748B;cursor:pointer;'
        'transition:color .15s;" onmouseover="this.style.color=\'#0F172A\'" '
        'onmouseout="this.style.color=\'#64748B\'">&#x2715;</button>',
        '</div>',
        # Body
        '<div id="ct-body" style="padding:20px 24px;max-height:60vh;overflow-y:auto;">'
        '<div style="color:#94A3B8;font-size:.85rem;text-align:center;padding:20px 0;">Ready</div>'
        '</div>',
        '</div></div>',

        '<script>',
        'function validateConfig(){'
        '  var ok=true;'
        '  document.querySelectorAll(".req-field").forEach(function(inp){'
        '    var msg=inp.parentElement.querySelector(".field-err-msg");'
        '    if(!msg){'
        '      msg=document.createElement("div");msg.className="field-err-msg";'
        '      inp.parentElement.appendChild(msg);'
        '    }'
        '    if(!inp.value.trim()){'
        '      inp.classList.add("inp-err");'
        '      msg.textContent="This field is required.";msg.style.display="block";'
        '      ok=false;'
        '    }else{'
        '      inp.classList.remove("inp-err");msg.style.display="none";'
        '    }'
        '  });'
        '  if(!ok){window.scrollTo({top:0,behavior:"smooth"});}'
        '  return ok;'
        '}'
        'document.addEventListener("input",function(e){'
        '  if(e.target.classList.contains("req-field")&&e.target.classList.contains("inp-err")){'
        '    if(e.target.value.trim()){'
        '      e.target.classList.remove("inp-err");'
        '      var m=e.target.parentElement.querySelector(".field-err-msg");'
        '      if(m)m.style.display="none";'
        '    }'
        '  }'
        '});',
        'function saveAndTest(e){e.preventDefault();return false;}',
        'var __base="' + _UTILS_BASE + '";',

        'function _saveRepo(){'
        '  if(!validateConfig())return;'
        '  var form=document.getElementById("config-form");'
        '  var fd=new URLSearchParams(new FormData(form));'
        '  fd.set("_section","repo");'
        '  var st=document.getElementById("repo-save-status");'
        '  st.style.color="#6b7280";st.textContent="Saving...";'
        '  fetch(__base+"/config",{method:"POST",body:fd})'
        '  .then(function(r){return r.json();})'
        '  .then(function(d){'
        '    if(d.ok){'
        '      st.style.color="#22c55e";st.textContent="Repository DB saved.";'
        '      _showProcModal(d.db_type||"Oracle");'
        '    }else{st.style.color="#ef4444";st.textContent="Save failed.";}'
        '  }).catch(function(e){st.style.color="#ef4444";st.textContent="Error: "+e;});'
        '}',

        'function _savePaths(){'
        '  var form=document.getElementById("config-form");'
        '  var fd=new URLSearchParams(new FormData(form));'
        '  fd.set("_section","paths");'
        '  var st=document.getElementById("paths-save-status");'
        '  st.style.color="#6b7280";st.textContent="Saving...";'
        '  fetch(__base+"/config",{method:"POST",body:fd})'
        '  .then(function(r){return r.json();})'
        '  .then(function(d){'
        '    if(d.ok){st.style.color="#22c55e";st.textContent="Service/Log Paths saved.";}'
        '    else{st.style.color="#ef4444";st.textContent="Save failed.";}'
        '  }).catch(function(e){st.style.color="#ef4444";st.textContent="Error: "+e;});'
        '}',

        'function _showProcModal(dbType){'
        '  var isOra=(dbType==="Oracle");'
        '  var title=isOra?"Procedure 생성":"Function 생성";'
        '  var objName=isOra?"프로시저":"함수";'
        '  var desc=isOra'
        '    ?"<b>INSP_PARTITION_CREATE_TARGET</b> — 파티션 수동 생성 (D-1~D+3)<br>"'
        '    +"<b>INSP_PARTITION_DROP_TARGET</b> — 만료 파티션 수동 삭제<br><br>"'
        '    +"위 프로시저들은 Partition Create/Drop Check 기능에 사용됩니다."'
        '    :"<b>insp_session_check</b> — Session Check 조회<br>"'
        '    +"<b>insp_alarm_history_check</b> — Alert Check 조회<br>"'
        '    +"<b>insp_query_check</b> — Query Check 조회<br><br>"'
        '    +"위 함수들은 각 Check 페이지 조회 기능에 사용됩니다.";'
        '  var html="<div id=\\"proc-modal\\" style=\\"position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;\\">"'
        '    +"<div onclick=\\"document.getElementById(\'proc-modal\').remove()\\" style=\\"position:absolute;inset:0;background:rgba(15,23,42,.45);backdrop-filter:blur(3px);\\"></div>"'
        '    +"<div style=\\"position:relative;width:min(520px,92vw);background:#fff;border-radius:16px;box-shadow:0 30px 70px rgba(15,23,42,.25);border:1px solid rgba(226,232,240,.9);overflow:hidden;\\">"'
        '      +"<div style=\\"padding:16px 20px;border-bottom:1px solid #E2E8F0;display:flex;align-items:center;gap:10px;\\">"'
        '        +"<div style=\\"width:32px;height:32px;border-radius:9px;background:rgba(99,102,241,.1);display:flex;align-items:center;justify-content:center;\\">"'
        '        +"<svg width=\\"18\\" height=\\"18\\" viewBox=\\"0 0 24 24\\" fill=\\"none\\" stroke=\\"#6366F1\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\" stroke-linejoin=\\"round\\"><path d=\\"M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z\\"/></svg></div>"'
        '        +"<span style=\\"font-size:.92rem;font-weight:700;color:#0F172A;\\">"+title+"</span>"'
        '      +"</div>"'
        '      +"<div style=\\"padding:18px 20px;\\">"'
        '        +"<p style=\\"font-size:.88rem;color:#334155;margin:0 0 14px;\\">Repository DB에 "+objName+"를 생성하시겠습니까?</p>"'
        '        +"<div style=\\"background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:14px 16px;font-size:.82rem;color:#475569;line-height:1.7;\\">"+desc+"</div>"'
        '        +"<div id=\\"proc-modal-result\\" style=\\"margin-top:12px;font-size:.82rem;\\"></div>"'
        '      +"</div>"'
        '      +"<div style=\\"padding:14px 20px;border-top:1px solid #E2E8F0;display:flex;justify-content:flex-end;gap:10px;\\">"'
        '        +"<button onclick=\\"document.getElementById(\'proc-modal\').remove();_showTableModal(\'"+dbType+"\')\\" style=\\"padding:8px 20px;border-radius:10px;border:1px solid #CBD5E1;color:#64748B;background:#fff;font-size:.84rem;cursor:pointer;\\">아니오</button>"'
        '        +"<button id=\\"proc-modal-yes\\" onclick=\\"_doProcCreate(\'"+dbType+"\')\\" style=\\"padding:8px 20px;border-radius:10px;border:none;background:#6366F1;color:#fff;font-size:.84rem;font-weight:600;cursor:pointer;\\">예, 생성</button>"'
        '      +"</div>"'
        '    +"</div>"'
        '  +"</div>";'
        '  var w=document.createElement("div");w.innerHTML=html;'
        '  while(w.firstChild)document.body.appendChild(w.firstChild);'
        '}',

        'var _procDbType="";'
        'function _doProcCreate(dbType){'
        '  _procDbType=dbType||_procDbType;'
        '  var btn=document.getElementById("proc-modal-yes");'
        '  var res=document.getElementById("proc-modal-result");'
        '  btn.disabled=true;btn.textContent="Creating...";btn.style.opacity=".5";'
        '  fetch(__base+"/api/create-procedure")'
        '  .then(function(r){return r.json();})'
        '  .then(function(d){'
        '    if(d.ok){'
        '      res.innerHTML="<span style=\\"color:#22c55e;font-weight:600;\\">\\u2713 "+d.message+"</span>";'
        '      btn.style.display="none";'
        '      var noBtn=btn.parentElement.querySelector("[onclick*=proc-modal]");'
        '      if(noBtn){noBtn.textContent="확인";noBtn.style.background="#6366F1";noBtn.style.color="#fff";noBtn.style.borderColor="#6366F1";noBtn.style.fontWeight="600";'
        '        noBtn.onclick=function(){document.getElementById("proc-modal").remove();_showTableModal(_procDbType);};}'
        '    }else{'
        '      btn.disabled=false;btn.textContent="예, 생성";btn.style.opacity="1";'
        '      res.innerHTML="<span style=\\"color:#ef4444;\\">\\u2715 "+d.error+"</span>";'
        '    }'
        '  }).catch(function(){'
        '    btn.disabled=false;btn.textContent="예, 생성";btn.style.opacity="1";'
        '    res.innerHTML="<span style=\\"color:#ef4444;\\">요청 실패</span>";'
        '  });'
        '}',

        'function _showTableModal(dbType){'
        '  var isOra=(dbType==="Oracle");'
        '  var desc=""'
        '    +"<b>"+(isOra?"INSP_OS_HISTORY":"insp_os_history")+"</b> — OS CPU / Memory 사용률 이력<br>"'
        '    +"<b>"+(isOra?"INSP_TBS_HISTORY":"insp_tbs_history")+"</b> — Tablespace 사용률 이력<br>"'
        '    +"<b>"+(isOra?"INSP_SERVICE_HISTORY":"insp_service_history")+"</b> — DGServer / PlatformJS 서비스 상태 이력<br>"'
        '    +"<b>"+(isOra?"INSP_HEAP_HISTORY":"insp_heap_history")+"</b> — JVM Heap 사용량 이력<br>"'
        '    +"<b>"+(isOra?"INSP_QCNT_HISTORY":"insp_qcnt_history")+"</b> — 쿼리 수집 건수 이력<br>"'
        '    +"<b>"+(isOra?"INSP_SUMMARY_HISTORY":"insp_summary_history")+"</b> — 10분 / 1시간 Summary 수집 이력<br><br>"'
        '    +"위 테이블들은 <b>Inspector History</b> 기능 (OS, Tablespace, Process 등 히스토리 차트)에 사용됩니다.";'
        '  var html="<div id=\\"tbl-modal\\" style=\\"position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;\\">"'
        '    +"<div onclick=\\"document.getElementById(\'tbl-modal\').remove()\\" style=\\"position:absolute;inset:0;background:rgba(15,23,42,.45);backdrop-filter:blur(3px);\\"></div>"'
        '    +"<div style=\\"position:relative;width:min(560px,92vw);background:#fff;border-radius:16px;box-shadow:0 30px 70px rgba(15,23,42,.25);border:1px solid rgba(226,232,240,.9);overflow:hidden;\\">"'
        '      +"<div style=\\"padding:16px 20px;border-bottom:1px solid #E2E8F0;display:flex;align-items:center;gap:10px;\\">"'
        '        +"<div style=\\"width:32px;height:32px;border-radius:9px;background:rgba(99,102,241,.1);display:flex;align-items:center;justify-content:center;\\">"'
        '        +"<svg width=\\"18\\" height=\\"18\\" viewBox=\\"0 0 24 24\\" fill=\\"none\\" stroke=\\"#6366F1\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\" stroke-linejoin=\\"round\\"><rect x=\\"3\\" y=\\"3\\" width=\\"7\\" height=\\"7\\"/><rect x=\\"14\\" y=\\"3\\" width=\\"7\\" height=\\"7\\"/><rect x=\\"14\\" y=\\"14\\" width=\\"7\\" height=\\"7\\"/><rect x=\\"3\\" y=\\"14\\" width=\\"7\\" height=\\"7\\"/></svg></div>"'
        '        +"<span style=\\"font-size:.92rem;font-weight:700;color:#0F172A;\\">Inspector History Table 생성</span>"'
        '      +"</div>"'
        '      +"<div style=\\"padding:18px 20px;\\">"'
        '        +"<p style=\\"font-size:.88rem;color:#334155;margin:0 0 14px;\\">Inspector History 테이블을 생성하시겠습니까?</p>"'
        '        +"<div style=\\"background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:14px 16px;font-size:.82rem;color:#475569;line-height:1.7;\\">"+desc+"</div>"'
        '        +"<div id=\\"tbl-modal-result\\" style=\\"margin-top:12px;font-size:.82rem;\\"></div>"'
        '      +"</div>"'
        '      +"<div style=\\"padding:14px 20px;border-top:1px solid #E2E8F0;display:flex;justify-content:flex-end;gap:10px;\\">"'
        '        +"<button onclick=\\"document.getElementById(\'tbl-modal\').remove();_showCollModal(\'"+dbType+"\')\\" style=\\"padding:8px 20px;border-radius:10px;border:1px solid #CBD5E1;color:#64748B;background:#fff;font-size:.84rem;cursor:pointer;\\">아니오</button>"'
        '        +"<button id=\\"tbl-modal-yes\\" onclick=\\"_doTableCreate(\'"+dbType+"\')\\" style=\\"padding:8px 20px;border-radius:10px;border:none;background:#6366F1;color:#fff;font-size:.84rem;font-weight:600;cursor:pointer;\\">예, 생성</button>"'
        '      +"</div>"'
        '    +"</div>"'
        '  +"</div>";'
        '  var w=document.createElement("div");w.innerHTML=html;'
        '  while(w.firstChild)document.body.appendChild(w.firstChild);'
        '}',

        'var _tblDbType="";'
        'function _doTableCreate(dbType){'
        '  _tblDbType=dbType||_tblDbType;'
        '  var btn=document.getElementById("tbl-modal-yes");'
        '  var res=document.getElementById("tbl-modal-result");'
        '  btn.disabled=true;btn.textContent="Creating...";btn.style.opacity=".5";'
        '  fetch(__base+"/api/insp-init-tables",{method:"POST"})'
        '  .then(function(r){return r.json();})'
        '  .then(function(d){'
        '    if(d.ok){'
        '      res.innerHTML="<span style=\\"color:#22c55e;font-weight:600;\\">\\u2713 "+(d.message||"테이블 생성 완료")+"</span>";'
        '      btn.style.display="none";'
        '      var noBtn=btn.parentElement.querySelector("[onclick*=tbl-modal]");'
        '      if(noBtn){noBtn.textContent="확인";noBtn.style.background="#6366F1";noBtn.style.color="#fff";noBtn.style.borderColor="#6366F1";noBtn.style.fontWeight="600";'
        '        noBtn.onclick=function(){document.getElementById("tbl-modal").remove();_showCollModal(_tblDbType);};}'
        '    }else{'
        '      btn.disabled=false;btn.textContent="예, 생성";btn.style.opacity="1";'
        '      res.innerHTML="<span style=\\"color:#ef4444;\\">\\u2715 "+(d.error||"생성 실패")+"</span>";'
        '    }'
        '  }).catch(function(){'
        '    btn.disabled=false;btn.textContent="예, 생성";btn.style.opacity="1";'
        '    res.innerHTML="<span style=\\"color:#ef4444;\\">요청 실패</span>";'
        '  });'
        '}',
        
        'function runConnTest(){'
        '  var ov=document.getElementById("ct-overlay");'
        '  var bd=document.getElementById("ct-body");'
        '  ov.style.display="flex";'
        '  bd.innerHTML=\'<div style="color:#94A3B8;font-size:.85rem;text-align:center;padding:20px 0;">Testing...</div>\';'
        '  fetch(__base+"/api/connection-test")'
        '  .then(function(r){return r.json();})'
        '  .then(function(d){'
        '    var h=\'<div style="border:1px solid #E2E8F0;border-radius:10px;overflow:hidden;">\';'
        '    h+=\'<table style="width:100%;border-collapse:collapse;font-size:.84rem;">\';'
        '    h+=\'<thead><tr style="background:#ECF0F7;">\';'
        '    h+=\'<th style="text-align:center;padding:10px 14px;color:#5F6B80;font-size:.72rem;font-weight:700;text-transform:uppercase;border-bottom:1px solid #D8DEE8;">Component</th>\';'
        '    h+=\'<th style="text-align:center;padding:10px 14px;color:#5F6B80;font-size:.72rem;font-weight:700;text-transform:uppercase;border-bottom:1px solid #D8DEE8;">Status</th>\';'
        '    h+=\'<th style="text-align:center;padding:10px 14px;color:#5F6B80;font-size:.72rem;font-weight:700;text-transform:uppercase;border-bottom:1px solid #D8DEE8;">Detail</th>\';'
        '    h+=\'</tr></thead><tbody>\';'
        '    d.results.forEach(function(r){'
        '      var sc=r.status==="OK"?"#15803D":r.status==="FAIL"?"#DC2626":"#64748b";'
        '      var bg=r.status==="OK"?"#F0FDF4":r.status==="FAIL"?"#FEF2F2":"rgba(100,116,139,.12)";'
        '      var bd2=r.status==="OK"?"rgba(22,163,74,.2)":r.status==="FAIL"?"rgba(220,38,38,.2)":"rgba(100,116,139,.2)";'
        '      h+=\'<tr style="border-bottom:1px solid #F1F5F9;">\';'
        '      h+=\'<td style="padding:11px 14px;font-weight:600;color:#0F172A;text-align:center;">\'+r.component+\'</td>\';'
        '      h+=\'<td style="padding:11px 14px;text-align:center;"><span style="background:\'+bg+\';color:\'+sc+\';border:1px solid \'+bd2+\';padding:3px 12px;border-radius:999px;font-size:.75rem;font-weight:700;">\'+r.status+\'</span></td>\';'
        '      h+=\'<td style="padding:11px 14px;color:#64748B;font-size:.8rem;text-align:center;">\'+r.detail+\'</td>\';'
        '      h+=\'</tr>\';'
        '    });'
        '    h+=\'</tbody></table></div>\';'
        '    bd.innerHTML=h;'
        '  })'
        '  .catch(function(e){'
        '    bd.innerHTML=\'<div style="color:#f06a6a;font-size:.85rem;text-align:center;padding:20px 0;">Error: \'+e.message+\'</div>\';'
        '  });'
        '}',
        
        'var dgsCount=' + str(len(dgs_svc)) + ';',

        # IH toggle/settings/schedule/drop JS
        'function _ihUpdToggle(){'
        '  var c=document.getElementById("ih-chk-enabled"),t=document.getElementById("ih-toggle-track"),'
        '      k=document.getElementById("ih-toggle-knob"),l=document.getElementById("ih-toggle-label");'
        '  if(c.checked){t.style.background="#6366F1";k.style.left="22px";l.textContent="ON";l.style.color="#6366F1";}'
        '  else{t.style.background="#CBD5E1";k.style.left="2px";l.textContent="OFF";l.style.color="#94A3B8";}'
        '}',

        'function _ihSaveSettings(){'
        '  var en=document.getElementById("ih-chk-enabled").checked;'
        '  var ret=parseInt(document.getElementById("ih-inp-retention").value)||30;'
        '  var logRet=parseInt(document.getElementById("ih-inp-log-ret").value)||10;'
        '  var st=document.getElementById("ih-save-status");'
        '  st.style.color="#6b7280";st.textContent="Saving...";'
        '  fetch(__base+"/api/insp-config-save",{method:"POST",headers:{"Content-Type":"application/json"},'
        '    body:JSON.stringify({enabled:en,retention_days:ret,log_retention_days:logRet})})'
        '  .then(function(r){return r.json();})'
        '  .then(function(d){if(d.ok){st.style.color="#22c55e";st.textContent="Settings saved.";}else{st.style.color="#ef4444";st.textContent=d.error||"Failed.";}})'
        '  .catch(function(){st.style.color="#ef4444";st.textContent="Error";});'
        '}',

        'var _cfgSchedRows=['
        '["CPU / Memory","1분마다","' + ('INSP_' if not _is_pg else 'insp_') + 'OS_HISTORY"],'
        '["Qcnt (Connection)","1분마다","' + ('INSP_' if not _is_pg else 'insp_') + 'QCNT_HISTORY"],'
        '["Heap (JVM)","1분마다","' + ('INSP_' if not _is_pg else 'insp_') + 'HEAP_HISTORY"],'
        '["Service Status","1시간마다 (:00)","' + ('INSP_' if not _is_pg else 'insp_') + 'SERVICE_HISTORY"],'
        '["' + ('Tablespace' if not _is_pg else 'Disk') + '","매일 23:50","' + ('INSP_' if not _is_pg else 'insp_') + 'TBS_HISTORY"],'
        '["Summary (10Min)","10분마다 (:05, :15, ...)","' + ('INSP_' if not _is_pg else 'insp_') + 'SUMMARY_HISTORY"],'
        '["Summary (1Hour)","1시간마다 (:30)","' + ('INSP_' if not _is_pg else 'insp_') + 'SUMMARY_HISTORY"]'
        '];',

        'function _cfgLoadSched(){'
        '  fetch(__base+"/api/insp-table-status").then(function(r){return r.json();}).then(function(d){'
        '    var tb=document.getElementById("cfg-sched-body");if(!tb)return;tb.innerHTML="";'
        '    _cfgSchedRows.forEach(function(row){'
        '      var exists=d.ok&&d.tables&&(d.tables[row[2]]||d.tables[row[2].toUpperCase()]||d.tables[row[2].toLowerCase()]);'
        '      var st=exists?"<span style=\\"padding:3px 12px;border-radius:6px;border:1px solid #10b981;background:rgba(16,185,129,.08);color:#10b981;font-size:.72rem;font-weight:600;\\">OK</span>"'
        '                   :"<span style=\\"padding:3px 12px;border-radius:6px;border:1px solid #CBD5E1;background:rgba(148,163,184,.08);color:#94A3B8;font-size:.72rem;font-weight:600;\\">N/A</span>";'
        '      tb.innerHTML+="<tr style=\\"border-bottom:1px solid #F1F5F9;\\"><td style=\\"text-align:center;padding:10px 14px;\\">"+row[0]+"</td>"'
        '        +"<td style=\\"text-align:center;padding:10px 14px;\\">"+row[1]+"</td>"'
        '        +"<td style=\\"text-align:center;padding:10px 14px;font-size:.78rem;\\">"+row[2]+"</td>"'
        '        +"<td style=\\"text-align:center;padding:10px 14px;\\">"+st+"</td></tr>";'
        '    });'
        '  }).catch(function(){});'
        '}'
        'document.addEventListener("DOMContentLoaded",function(){_cfgLoadSched();'
        '  document.querySelectorAll("details").forEach(function(d){'
        '    d.addEventListener("toggle",function(){'
        '      var a=d.querySelector(".sect-arrow");if(a)a.style.transform=d.open?"rotate(90deg)":"";'
        '    });'
        '  });'
        '});',

        'var _cfgDropType="";'
        'function _cfgDrop(type){'
        '  _cfgDropType=type;'
        '  var isOra=document.getElementById("db_type_sel").value!=="PostgreSQL";'
        '  var title,desc,question;'
        '  if(type==="proc"){'
        '    title=isOra?"Drop Procedures":"Drop Functions";'
        '    question=isOra?"다음 프로시저를 삭제하시겠습니까?":"다음 함수를 삭제하시겠습니까?";'
        '    desc=isOra?"<b>INSP_PARTITION_CREATE_TARGET</b> — 파티션 수동 생성<br><b>INSP_PARTITION_DROP_TARGET</b> — 만료 파티션 수동 삭제<br><br><span style=\\"color:#7F1D1D\\">삭제 후 Partition Create/Drop Check 기능을 사용할 수 없습니다.</span>"'
        '         :"<b>insp_session_check</b> — Session Check<br><b>insp_alarm_history_check</b> — Alert Check<br><b>insp_query_check</b> — Query Check<br><br><span style=\\"color:#7F1D1D\\">삭제 후 각 Check 페이지 조회 기능을 사용할 수 없습니다.</span>";'
        '  }else{'
        '    title="Drop Inspector History Tables";'
        '    question="다음 테이블을 삭제하시겠습니까?";'
        '    var p=isOra?"INSP_":"insp_";'
        '    desc="<b>"+p+"OS_HISTORY</b> — OS CPU/Memory<br><b>"+p+"TBS_HISTORY</b> — Tablespace<br><b>"+p+"SERVICE_HISTORY</b> — Service 상태<br><b>"+p+"HEAP_HISTORY</b> — JVM Heap<br><b>"+p+"QCNT_HISTORY</b> — 쿼리 수집 건수<br><b>"+p+"SUMMARY_HISTORY</b> — Summary<br><br><span style=\\"color:#7F1D1D\\">삭제 후 Inspector History 차트 데이터가 모두 손실됩니다.</span>";'
        '  }'
        '  var html="<div id=\\"drop-modal\\" style=\\"position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;\\">"'
        '    +"<div onclick=\\"document.getElementById(\'drop-modal\').remove()\\" style=\\"position:absolute;inset:0;background:rgba(15,23,42,.45);backdrop-filter:blur(3px);\\"></div>"'
        '    +"<div style=\\"position:relative;width:min(520px,92vw);background:#fff;border-radius:16px;box-shadow:0 30px 70px rgba(15,23,42,.25);border:1px solid rgba(226,232,240,.9);overflow:hidden;\\">"'
        '      +"<div style=\\"padding:16px 20px;border-bottom:1px solid #E2E8F0;display:flex;align-items:center;gap:10px;\\">"'
        '        +"<div style=\\"width:32px;height:32px;border-radius:9px;background:rgba(239,68,68,.1);display:flex;align-items:center;justify-content:center;\\">"'
        '        +"<svg width=\\"18\\" height=\\"18\\" viewBox=\\"0 0 24 24\\" fill=\\"none\\" stroke=\\"#EF4444\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\" stroke-linejoin=\\"round\\"><polyline points=\\"3 6 5 6 21 6\\"/><path d=\\"M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2\\"/></svg></div>"'
        '        +"<span style=\\"font-size:.92rem;font-weight:700;color:#0F172A;\\">"+title+"</span>"'
        '      +"</div>"'
        '      +"<div style=\\"padding:18px 20px;\\">"'
        '        +"<p style=\\"font-size:.88rem;color:#334155;margin:0 0 14px;\\">"+question+"</p>"'
        '        +"<div style=\\"background:#FEF2F2;border:1px solid #FECACA;border-radius:10px;padding:14px 16px;font-size:.82rem;color:#991B1B;line-height:1.7;\\">"+desc+"</div>"'
        '        +"<div id=\\"drop-modal-result\\" style=\\"margin-top:12px;font-size:.82rem;\\"></div>"'
        '      +"</div>"'
        '      +"<div style=\\"padding:14px 20px;border-top:1px solid #E2E8F0;display:flex;justify-content:flex-end;gap:10px;\\">"'
        '        +"<button onclick=\\"document.getElementById(\'drop-modal\').remove()\\" style=\\"padding:8px 20px;border-radius:10px;border:1px solid #CBD5E1;color:#64748B;background:#fff;font-size:.84rem;cursor:pointer;\\">취소</button>"'
        '        +"<button id=\\"drop-modal-yes\\" onclick=\\"_doDropExec()\\" style=\\"padding:8px 20px;border-radius:10px;border:none;background:#EF4444;color:#fff;font-size:.84rem;font-weight:600;cursor:pointer;\\">삭제</button>"'
        '      +"</div>"'
        '    +"</div>"'
        '  +"</div>";'
        '  var w=document.createElement("div");w.innerHTML=html;'
        '  while(w.firstChild)document.body.appendChild(w.firstChild);'
        '}',

        'function _doDropExec(){'
        '  var btn=document.getElementById("drop-modal-yes");'
        '  var res=document.getElementById("drop-modal-result");'
        '  btn.disabled=true;btn.textContent="Dropping...";btn.style.opacity=".5";'
        '  var endpoint=_cfgDropType==="proc"?"/api/create-procedure":"/api/insp-drop-tables";'
        '  if(_cfgDropType==="proc")endpoint="/api/drop-procedures";'
        '  fetch(__base+endpoint,{method:"POST"}).then(function(r){return r.json();}).then(function(d){'
        '    if(d.ok){'
        '      res.innerHTML="<span style=\\"color:#22c55e;font-weight:600;\\">\\u2713 "+(d.message||"삭제 완료")+"</span>";'
        '      btn.style.display="none";'
        '      var noBtn=btn.parentElement.querySelector("[onclick*=drop-modal]");'
        '      if(noBtn){noBtn.textContent="확인";noBtn.style.background="#6366F1";noBtn.style.color="#fff";noBtn.style.borderColor="#6366F1";noBtn.style.fontWeight="600";}'
        '      _cfgLoadSched();'
        '    }else{'
        '      btn.disabled=false;btn.textContent="삭제";btn.style.opacity="1";'
        '      res.innerHTML="<span style=\\"color:#ef4444;\\">\\u2715 "+(d.error||"실패")+"</span>";'
        '    }'
        '  }).catch(function(){btn.disabled=false;btn.textContent="삭제";btn.style.opacity="1";res.innerHTML="<span style=\\"color:#ef4444;\\">요청 실패</span>";});'
        '}',

        'function _showCollModal(dbType){'
        '  var isOra=(dbType==="Oracle");'
        '  var html="<div id=\\"coll-modal\\" style=\\"position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;\\">"'
        '    +"<div onclick=\\"document.getElementById(\'coll-modal\').remove()\\" style=\\"position:absolute;inset:0;background:rgba(15,23,42,.45);backdrop-filter:blur(3px);\\"></div>"'
        '    +"<div style=\\"position:relative;width:min(540px,92vw);background:#fff;border-radius:16px;box-shadow:0 30px 70px rgba(15,23,42,.25);border:1px solid rgba(226,232,240,.9);overflow:hidden;\\">"'
        '      +"<div style=\\"padding:16px 20px;border-bottom:1px solid #E2E8F0;display:flex;align-items:center;gap:10px;\\">"'
        '        +"<div style=\\"width:32px;height:32px;border-radius:9px;background:rgba(99,102,241,.1);display:flex;align-items:center;justify-content:center;\\">"'
        '        +"<svg width=\\"18\\" height=\\"18\\" viewBox=\\"0 0 24 24\\" fill=\\"none\\" stroke=\\"#6366F1\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\" stroke-linejoin=\\"round\\"><circle cx=\\"12\\" cy=\\"12\\" r=\\"10\\"/><polyline points=\\"12 6 12 12 16 14\\"/></svg></div>"'
        '        +"<span style=\\"font-size:.92rem;font-weight:700;color:#0F172A;\\">Inspector History 수집 설정</span>"'
        '      +"</div>"'
        '      +"<div style=\\"padding:18px 20px;\\">"'
        '        +"<p style=\\"font-size:.88rem;color:#334155;margin:0 0 14px;\\">Inspector History 데이터 수집을 시작하시겠습니까?</p>"'
        '        +"<div style=\\"background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:14px 16px;font-size:.82rem;color:#475569;line-height:1.7;\\">"'
        '        +"수집을 활성화하면 아래 주기로 데이터가 자동 수집됩니다.<br><br>"'
        '        +"<b>CPU / Memory</b> — 1분마다<br>"'
        '        +"<b>Qcnt (Connection)</b> — 1분마다<br>"'
        '        +"<b>Heap (JVM)</b> — 1분마다<br>"'
        '        +"<b>Service Status</b> — 1시간마다<br>"'
        '        +"<b>"+(isOra?"Tablespace":"Disk")+"</b> — 매일 23:50<br>"'
        '        +"<b>Summary (10Min / 1Hour)</b> — 10분 / 1시간마다</div>"'
        '        +"<div id=\\"coll-modal-result\\" style=\\"margin-top:12px;font-size:.82rem;\\"></div>"'
        '      +"</div>"'
        '      +"<div style=\\"padding:14px 20px;border-top:1px solid #E2E8F0;display:flex;justify-content:flex-end;gap:10px;\\">"'
        '        +"<button onclick=\\"document.getElementById(\'coll-modal\').remove()\\" style=\\"padding:8px 20px;border-radius:10px;border:1px solid #CBD5E1;color:#64748B;background:#fff;font-size:.84rem;cursor:pointer;\\">나중에</button>"'
        '        +"<button id=\\"coll-modal-yes\\" onclick=\\"_doCollStart()\\" style=\\"padding:8px 20px;border-radius:10px;border:none;background:#6366F1;color:#fff;font-size:.84rem;font-weight:600;cursor:pointer;\\">수집 시작</button>"'
        '      +"</div>"'
        '    +"</div>"'
        '  +"</div>";'
        '  var w=document.createElement("div");w.innerHTML=html;'
        '  while(w.firstChild)document.body.appendChild(w.firstChild);'
        '}',

        'function _doCollStart(){'
        '  var btn=document.getElementById("coll-modal-yes");'
        '  var res=document.getElementById("coll-modal-result");'
        '  btn.disabled=true;btn.textContent="Setting...";btn.style.opacity=".5";'
        '  fetch(__base+"/api/insp-config-save",{method:"POST",headers:{"Content-Type":"application/json"},'
        '    body:JSON.stringify({enabled:true})})'
        '  .then(function(r){return r.json();})'
        '  .then(function(d){'
        '    if(d.ok){'
        '      res.innerHTML="<span style=\\"color:#22c55e;font-weight:600;\\">\\u2713 수집이 시작되었습니다.</span>";'
        '      btn.style.display="none";'
        '      var noBtn=btn.parentElement.querySelector("[onclick*=coll-modal]");'
        '      if(noBtn){noBtn.textContent="확인";noBtn.style.background="#6366F1";noBtn.style.color="#fff";noBtn.style.borderColor="#6366F1";noBtn.style.fontWeight="600";}'
        '      var chk=document.getElementById("ih-chk-enabled");if(chk){chk.checked=true;_ihUpdToggle();}'
        '    }else{'
        '      btn.disabled=false;btn.textContent="수집 시작";btn.style.opacity="1";'
        '      res.innerHTML="<span style=\\"color:#ef4444;\\">\\u2715 "+(d.error||"실패")+"</span>";'
        '    }'
        '  }).catch(function(){btn.disabled=false;btn.textContent="수집 시작";btn.style.opacity="1";'
        '    res.innerHTML="<span style=\\"color:#ef4444;\\">요청 실패</span>";});'
        '}',

        """
function onDbTypeChange(v){
  document.getElementById('pg_data_row').style.display = (v==='PostgreSQL') ? '' : 'none';
}

function syncPgData(val){
  var dataInp = document.getElementById('pg_data_inp');
  if(dataInp) dataInp.value = val ? val + '/data' : '';
}

function syncLog(type, idx, val){
  var logVal = val ? val + '/log' : '';
  if(type === 'pjs'){
    document.getElementById('log_pjs').value = logVal;
  } else if(type === 'dgm'){
    document.getElementById('log_dgm').value = logVal;
  } else if(type === 'dgs'){
    var el = document.getElementById('log_dgs_' + idx);
    if(el) el.value = logVal;
  }
}

function addDgs(){
  var sc = document.getElementById('dgs-svc-container');
  var lc = document.getElementById('dgs-log-container');
  var i = dgsCount;

  var sd = document.createElement('div');
  sd.className = 'dgs-row';
  sd.id = 'dgs-svc-row-' + i;

  var sInp = document.createElement('input');
  sInp.type = 'text';
  sInp.name = 'dgserver_s';
  sInp.id = 'svc_dgs_' + i;
  sInp.placeholder = '/path/to/DGServer_S' + (i + 1);
  sInp.className = 'inp';
  (function(idx){ sInp.addEventListener('input', function(){ syncLog('dgs', idx, this.value); }); })(i);

  var sBtn = document.createElement('button');
  sBtn.type = 'button';
  sBtn.className = 'btn-icon';
  sBtn.textContent = '-';
  (function(idx){ sBtn.addEventListener('click', function(){ removeDgs(idx); }); })(i);

  sd.appendChild(sInp);
  sd.appendChild(sBtn);
  sc.appendChild(sd);

  var ld = document.createElement('div');
  ld.className = 'dgs-row';
  ld.id = 'dgs-log-row-' + i;

  var lInp = document.createElement('input');
  lInp.type = 'text';
  lInp.name = 'log_dgserver_s';
  lInp.id = 'log_dgs_' + i;
  lInp.placeholder = '/path/to/DGServer_S' + (i + 1) + '/log';
  lInp.className = 'inp';

  ld.appendChild(lInp);
  lc.appendChild(ld);

  dgsCount++;
}

function removeDgs(i){
  var sc = document.getElementById('dgs-svc-container');
  var sr = document.getElementById('dgs-svc-row-' + i);
  var lr = document.getElementById('dgs-log-row-' + i);
  if(sr && sc.children.length > 1){
    sr.parentNode.removeChild(sr);
    if(lr) lr.parentNode.removeChild(lr);
  }
}
""",
        '</script>',
    ])
    return body


def page_config(saved=False):
    body = _build_config_body(saved)
    return _page('config', 'Configuration', body)


def page_config_in_history(saved=False):
    from pages.history_page import _history_page
    # Reuse config body but wrap in history layout
    body = _build_config_body(saved)
    return _history_page(body, active="configuration")
