# -*- coding: utf-8 -*-
"""Alert Service (SMS/API/Mail) XML config read/write via web UI."""
import os
import re
import json
import shutil
import time

from service_config import load_service_config
from system_utils import _xml_val, _read_lines

try:
    from html_helpers import _UTILS_BASE
except Exception:
    _UTILS_BASE = ""


def _get_svc_dirs():
    """Return list of (name, svc_dir_path) for all DGServer_S instances."""
    svc = load_service_config()
    services = svc.get("services", {})
    result = []
    for i, dgs in enumerate(services.get("dgserver_s", [])):
        if dgs:
            svc_dir = os.path.join(dgs, "svc")
            if os.path.isdir(svc_dir):
                result.append(("DGServer_S%d" % (i + 1), svc_dir))
    return result


def _get_xml_path(svc_dir, kind):
    """Return (active_path, sample_path, is_active)."""
    active = os.path.join(svc_dir, kind + ".xml")
    sample = os.path.join(svc_dir, "sample_" + kind + ".xml")
    if os.path.exists(active):
        return active, sample, True
    return sample, sample, False


def _parse_xml_simple(path):
    """Parse XML file into dict of tag->value pairs (simple flat parsing)."""
    if not os.path.exists(path):
        return {}
    result = {}
    try:
        content = ''.join(_read_lines(path))
        # Extract tag-value pairs
        for m in re.finditer(r'<([a-zA-Z_]\w*)(?:\s+[^>]*)?>([^<]*)</\1>', content):
            tag, val = m.group(1), m.group(2).strip()
            result[tag] = val
        # Extract attributes
        for m in re.finditer(r'<(\w+)\s+((?:\w+="[^"]*"\s*)+)/?>', content):
            tag = m.group(1)
            attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(2)))
            if attrs:
                result[tag + '_attrs'] = attrs
        # Extract multi-line content blocks (QUERY, DATA, CONTENT, SUBJECT)
        for block_tag in ('SMS_INSERT_QUERY', 'DATA', 'CONTENT', 'SUBJECT'):
            m = re.search(r'<%s>(.*?)</%s>' % (block_tag, block_tag), content, re.DOTALL)
            if m:
                result[block_tag] = m.group(1).strip()
        # Extract bind values
        binds = {}
        for m in re.finditer(r'<(b\d+)>([^<]*)</\1>', content):
            binds[m.group(1)] = m.group(2).strip()
        if binds:
            result['_binds'] = binds
        # Extract headers
        headers = {}
        for m in re.finditer(r'<(h\d+)>([^<]*)</\1>', content):
            headers[m.group(1)] = m.group(2).strip()
        if headers:
            result['_headers'] = headers
        # Extract RAC node
        m = re.search(r'<Node>([^<]*)</Node>', content)
        if m:
            result['rac_node'] = m.group(1).strip()
        # Extract service attribute from sid tag
        m = re.search(r'<sms_database_sid\s+service="(\w+)">', content)
        if m:
            result['sms_database_sid_service'] = m.group(1)
        # Raw content for fallback
        result['_raw'] = content
    except Exception as e:
        result['_error'] = str(e)
    return result


# ── API: Read config ─────────────────────────────────────────────────────

def api_alert_svc_read(kind_str):
    """Read SMS/API/Mail XML config. Returns JSON."""
    kind = (kind_str or '').strip().lower()
    if kind not in ('sms', 'api', 'mail'):
        return json.dumps({"ok": False, "error": "Invalid kind: %s" % kind})

    svc_dirs = _get_svc_dirs()
    if not svc_dirs:
        return json.dumps({"ok": False, "error": "No DGServer_S configured"})

    results = []
    for name, svc_dir in svc_dirs:
        xml_path, sample_path, is_active = _get_xml_path(svc_dir, kind)
        parsed = _parse_xml_simple(xml_path)
        results.append({
            "dgserver": name,
            "svc_dir": svc_dir,
            "active": is_active,
            "xml_path": xml_path,
            "config": {k: v for k, v in parsed.items() if not k.startswith('_')},
            "binds": parsed.get('_binds', {}),
            "headers": parsed.get('_headers', {}),
            "raw": parsed.get('_raw', ''),
        })

    return json.dumps({"ok": True, "kind": kind, "results": results}, ensure_ascii=False)


# ── API: Save config ─────────────────────────────────────────────────────

def api_alert_svc_save(raw_body):
    """Save SMS/API/Mail XML config changes."""
    try:
        data = json.loads(raw_body.decode('utf-8', errors='ignore'))
    except Exception:
        return json.dumps({"ok": False, "error": "Invalid JSON"})

    kind = data.get("kind", "").lower()
    svc_dir = data.get("svc_dir", "")
    activate = data.get("activate")  # True/False/None
    raw_xml = data.get("raw_xml", "")

    if kind not in ('sms', 'api', 'mail'):
        return json.dumps({"ok": False, "error": "Invalid kind"})
    if not svc_dir or not os.path.isdir(svc_dir):
        return json.dumps({"ok": False, "error": "svc dir not found"})

    active_path = os.path.join(svc_dir, kind + ".xml")
    sample_path = os.path.join(svc_dir, "sample_" + kind + ".xml")
    is_active = os.path.exists(active_path)

    results = []

    try:
        # Save XML content
        if raw_xml:
            target = active_path if is_active else sample_path
            if os.path.exists(target):
                _today = time.strftime('%y%m%d')
                _seq = 0
                while os.path.exists(target + '.bak_' + _today + '_' + str(_seq)):
                    _seq += 1
                bak = target + '.bak_' + _today + '_' + str(_seq)
                shutil.copy2(target, bak)
                results.append("Backup: %s" % os.path.basename(bak))
            with open(target, 'w', encoding='utf-8') as f:
                f.write(raw_xml)
            results.append("XML saved: %s" % os.path.basename(target))

        # Activate/Deactivate
        if activate is True and not is_active:
            # Copy sample to active (not rename, keep sample as reference)
            src = sample_path if os.path.exists(sample_path) else None
            if raw_xml:
                # Already written to sample_path, now copy to active
                shutil.copy2(sample_path, active_path)
            elif src:
                shutil.copy2(src, active_path)
            # Also handle .jar and .unit
            for ext in ('.jar', '.unit'):
                s = os.path.join(svc_dir, "sample_" + kind + ext)
                a = os.path.join(svc_dir, kind + ext)
                if os.path.exists(s) and not os.path.exists(a):
                    shutil.copy2(s, a)
                    results.append("Activated: %s" % os.path.basename(a))
            results.append("Service activated. Restart DGServer_S to apply.")

        elif activate is False and is_active:
            # Deactivate: remove active files (keep sample)
            for ext in ('.xml', '.jar', '.unit'):
                a = os.path.join(svc_dir, kind + ext)
                if os.path.exists(a):
                    os.remove(a)
                    results.append("Removed: %s" % os.path.basename(a))
            results.append("Service deactivated. Restart DGServer_S to apply.")

    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)[:300]})

    return json.dumps({"ok": True, "results": results}, ensure_ascii=False)


# ── API: Copy config to other DGServers ──────────────────────────────────

def api_alert_svc_copy(raw_body):
    """Copy current XML content and active state to selected target DGServers (with backup)."""
    try:
        data = json.loads(raw_body.decode('utf-8', errors='ignore'))
    except Exception:
        return json.dumps({"ok": False, "error": "Invalid JSON"})

    kind        = data.get("kind", "").lower()
    raw_xml     = data.get("raw_xml", "")
    target_dirs = data.get("target_svc_dirs", [])
    activate    = data.get("activate")   # True / False from source active state

    if kind not in ('sms', 'api', 'mail'):
        return json.dumps({"ok": False, "error": "Invalid kind"})
    if not raw_xml:
        return json.dumps({"ok": False, "error": "No XML content"})
    if not target_dirs:
        return json.dumps({"ok": False, "error": "No targets selected"})

    def _backup(path):
        if not os.path.exists(path):
            return None
        _today = time.strftime('%y%m%d')
        _seq = 0
        while os.path.exists(path + '.bak_' + _today + '_' + str(_seq)):
            _seq += 1
        bak = path + '.bak_' + _today + '_' + str(_seq)
        shutil.copy2(path, bak)
        return bak

    results = []
    for svc_dir in target_dirs:
        if not os.path.isdir(svc_dir):
            results.append({"svc_dir": svc_dir, "status": "error", "message": "Directory not found"})
            continue
        try:
            active_path = os.path.join(svc_dir, kind + ".xml")
            sample_path = os.path.join(svc_dir, "sample_" + kind + ".xml")
            bak = None

            if activate is True:
                # Source is active → make target active too
                bak = _backup(active_path) or _backup(sample_path)
                with open(sample_path, 'w', encoding='utf-8') as f:
                    f.write(raw_xml)
                with open(active_path, 'w', encoding='utf-8') as f:
                    f.write(raw_xml)
                for ext in ('.jar', '.unit'):
                    s = os.path.join(svc_dir, "sample_" + kind + ext)
                    a = os.path.join(svc_dir, kind + ext)
                    if os.path.exists(s) and not os.path.exists(a):
                        shutil.copy2(s, a)
                written = active_path

            elif activate is False:
                # Source is inactive → make target inactive too
                bak = _backup(sample_path)
                with open(sample_path, 'w', encoding='utf-8') as f:
                    f.write(raw_xml)
                for ext in ('.xml', '.jar', '.unit'):
                    a = os.path.join(svc_dir, kind + ext)
                    if os.path.exists(a):
                        os.remove(a)
                written = sample_path

            else:
                # activate not specified → write to whichever file currently exists
                target = active_path if os.path.exists(active_path) else sample_path
                bak = _backup(target)
                with open(target, 'w', encoding='utf-8') as f:
                    f.write(raw_xml)
                written = target

            results.append({
                "svc_dir": svc_dir,
                "status": "ok",
                "file": os.path.basename(written),
                "backup": os.path.basename(bak) if bak else None,
            })
        except Exception as e:
            results.append({"svc_dir": svc_dir, "status": "error", "message": str(e)[:200]})

    all_ok = all(r["status"] == "ok" for r in results)
    return json.dumps({"ok": all_ok, "results": results}, ensure_ascii=False)


# ── Modal HTML/JS ────────────────────────────────────────────────────────

def alert_svc_modal_html():
    """Return the Alert Service Config modal HTML + JS."""
    ub = _UTILS_BASE

    # Load XML parameter reference HTML
    import os as _os
    _xpr_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '_xml_param_ref.html')
    _xml_param_ref = open(_xpr_path, encoding='utf-8').read() if _os.path.exists(_xpr_path) else ''

    return ''.join([

        '<div id="svc-cfg-modal" style="display:none;position:fixed;z-index:9996;'
        'top:5%;left:50%;transform:translateX(-50%);width:95%;max-width:1400px;'
        'background:#fff;border-radius:14px;box-shadow:0 25px 60px rgba(0,0,0,.25);'
        'max-height:90vh;display:none;flex-direction:column;resize:both;overflow:hidden;">',

        # Header (draggable)
        '<div id="svc-cfg-hdr" style="display:flex;align-items:center;justify-content:space-between;'
        'padding:14px 20px;background:#F8FAFC;border-bottom:1px solid #e5e7eb;cursor:move;user-select:none;">',
        '<span id="svc-cfg-title" style="font-size:.88rem;font-weight:700;color:#6366F1;">Service Config</span>',
        '<button onclick="_svcClose()" '
        'style="width:30px;height:30px;border:none;background:transparent;color:#94a3b8;'
        'font-size:1.4rem;cursor:pointer;border-radius:4px;line-height:1;">&times;</button>',
        '</div>',

        # Body
        '<div style="padding:20px 24px;flex:1;overflow-y:auto;">',

        # DGServer selector + status
        '<div style="display:flex;gap:12px;margin-bottom:16px;align-items:center;">',
        '<select id="svc-dgs-sel" onchange="_svcLoadDgs()" style="padding:8px 12px;border-radius:8px;border:1px solid #CBD5E1;font-size:.84rem;"></select>',
        '<label style="display:flex;align-items:center;gap:6px;font-size:.84rem;color:#334155;cursor:pointer;">',
        '<input type="checkbox" id="svc-active-cb" style="accent-color:#6366F1;width:16px;height:16px;"> Active</label>',
        '</div>',

        # Two-column layout: XML editor (left) + param references (right)
        '<div style="display:flex;gap:16px;align-items:stretch;">',

        # LEFT column — XML editor
        '<div style="flex:1 1 55%;min-width:0;display:flex;flex-direction:column;">',
        '<div style="font-size:.75rem;font-weight:700;color:#64748B;margin-bottom:6px;text-transform:uppercase;letter-spacing:.03em;">XML Configuration</div>',
        '<textarea id="svc-xml-editor" style="width:100%;flex:1;min-height:560px;font-family:JetBrains Mono,Consolas,monospace;font-size:.8rem;line-height:1.6;padding:14px;border:1px solid #E2E8F0;border-radius:10px;resize:vertical;color:#334155;background:#FAFAFA;box-sizing:border-box;outline:none;tab-size:4;" spellcheck="false"></textarea>',
        '</div>',

        # RIGHT column — reference panels
        '<div style="flex:1 1 45%;min-width:0;display:flex;flex-direction:column;gap:12px;max-height:calc(92vh - 240px);overflow-y:auto;">',

        _xml_param_ref,

        # Bind parameter reference
        '<details id="bind-param-ref" style="border:1px solid #E2E8F0;border-radius:10px;overflow:hidden;">',
        '<summary style="padding:10px 16px;font-size:.78rem;font-weight:600;color:#6366F1;cursor:pointer;background:#F8FAFC;user-select:none;">사용 가능한 Bind Parameter 목록</summary>',
        '<div style="padding:12px 16px;background:#fff;">',
        '<table style="width:100%;font-size:.75rem;border-collapse:collapse;">',
        '<thead><tr style="border-bottom:2px solid #E2E8F0;">',
        '<th style="text-align:center;padding:6px 8px;color:#64748B;font-weight:700;width:35%;border-right:1px solid #E2E8F0;">Parameter</th>',
        '<th style="text-align:left;padding:6px 8px;color:#64748B;font-weight:700;">Description</th>',
        '</tr></thead><tbody>',
        '<tr style="border-bottom:1px solid #F1F5F9;"><td style="padding:5px 8px;color:#334155;font-size:.74rem;text-align:center;border-right:1px solid #F1F5F9;">p$sms_user_name$</td><td style="padding:5px 8px;color:#334155;">SMS 수신자명</td></tr>',
        '<tr style="border-bottom:1px solid #F1F5F9;"><td style="padding:5px 8px;color:#334155;font-size:.74rem;text-align:center;border-right:1px solid #F1F5F9;">p$phone_number$</td><td style="padding:5px 8px;color:#334155;">사용자 정보에 등록된 전화번호</td></tr>',
        '<tr style="border-bottom:1px solid #F1F5F9;"><td style="padding:5px 8px;color:#334155;font-size:.74rem;text-align:center;border-right:1px solid #F1F5F9;">p$tnsname$</td><td style="padding:5px 8px;color:#334155;">Instance 명</td></tr>',
        '<tr style="border-bottom:1px solid #F1F5F9;"><td style="padding:5px 8px;color:#334155;font-size:.74rem;text-align:center;border-right:1px solid #F1F5F9;">p$business_name$</td><td style="padding:5px 8px;color:#334155;">Configuration에서 설정한 비즈니스명</td></tr>',
        '<tr style="border-bottom:1px solid #F1F5F9;"><td style="padding:5px 8px;color:#334155;font-size:.74rem;text-align:center;border-right:1px solid #F1F5F9;">p$alert_type$</td><td style="padding:5px 8px;color:#334155;">Alert 유형 (DB Stat, DB Wait, Server Alert 등)</td></tr>',
        '<tr style="border-bottom:1px solid #F1F5F9;"><td style="padding:5px 8px;color:#334155;font-size:.74rem;text-align:center;border-right:1px solid #F1F5F9;">p$resource_name$</td><td style="padding:5px 8px;color:#334155;">Alert 지표명</td></tr>',
        '<tr style="border-bottom:1px solid #F1F5F9;"><td style="padding:5px 8px;color:#334155;font-size:.74rem;text-align:center;border-right:1px solid #F1F5F9;">p$value$</td><td style="padding:5px 8px;color:#334155;">Alert 값</td></tr>',
        '<tr style="border-bottom:1px solid #F1F5F9;"><td style="padding:5px 8px;color:#334155;font-size:.74rem;text-align:center;border-right:1px solid #F1F5F9;">p$level$</td><td style="padding:5px 8px;color:#334155;">Alert 레벨 (0=Normal, 1=Warning, 2=Critical)</td></tr>',
        '<tr style="border-bottom:1px solid #F1F5F9;"><td style="padding:5px 8px;color:#334155;font-size:.74rem;text-align:center;border-right:1px solid #F1F5F9;">p$string_level$</td><td style="padding:5px 8px;color:#334155;">Alert 레벨 문자열 (N/W/C)</td></tr>',
        '<tr style="border-bottom:1px solid #F1F5F9;"><td style="padding:5px 8px;color:#334155;font-size:.74rem;text-align:center;border-right:1px solid #F1F5F9;">p$description$</td><td style="padding:5px 8px;color:#334155;">Alert 설명 (TBS: Name/Usage%/Free, Disk: FS/Mount/Usage%/Size)</td></tr>',
        '<tr style="border-bottom:1px solid #F1F5F9;"><td style="padding:5px 8px;color:#334155;font-size:.74rem;text-align:center;border-right:1px solid #F1F5F9;">p$server_time$</td><td style="padding:5px 8px;color:#334155;">Alert 발생 시간 (epoch)</td></tr>',
        '<tr style="border-bottom:1px solid #F1F5F9;"><td style="padding:5px 8px;color:#334155;font-size:.74rem;text-align:center;border-right:1px solid #F1F5F9;">p$string_server_time$</td><td style="padding:5px 8px;color:#334155;">Alert 발생 시간 (출력 형식 변경 가능)</td></tr>',
        '<tr style="border-bottom:1px solid #F1F5F9;"><td style="padding:5px 8px;color:#334155;font-size:.74rem;text-align:center;border-right:1px solid #F1F5F9;">p$current_time$</td><td style="padding:5px 8px;color:#334155;">DG가 Alert 정보를 수신한 시간 (epoch)</td></tr>',
        '<tr style="border-bottom:1px solid #F1F5F9;"><td style="padding:5px 8px;color:#334155;font-size:.74rem;text-align:center;border-right:1px solid #F1F5F9;">p$string_current_time$</td><td style="padding:5px 8px;color:#334155;">DG가 Alert 정보를 수신한 시간 (출력 형식 변경 가능)</td></tr>',
        '<tr style="border-bottom:1px solid #F1F5F9;"><td style="padding:5px 8px;color:#334155;font-size:.74rem;text-align:center;border-right:1px solid #F1F5F9;">p$sid$</td><td style="padding:5px 8px;color:#334155;">해당 Instance의 SID</td></tr>',
        '<tr style="border-bottom:1px solid #F1F5F9;"><td style="padding:5px 8px;color:#334155;font-size:.74rem;text-align:center;border-right:1px solid #F1F5F9;">p$server_id$</td><td style="padding:5px 8px;color:#334155;">해당 Instance의 Server ID (=db_id)</td></tr>',
        '<tr><td style="padding:5px 8px;color:#334155;font-size:.74rem;text-align:center;border-right:1px solid #F1F5F9;">p$host_name$</td><td style="padding:5px 8px;color:#334155;">해당 Instance의 Host Name</td></tr>',
        '</tbody></table>',
        '</div></details>',

        '</div>',  # right column
        '</div>',  # two-column wrap

        '</div>',  # body

        # Footer
        '<div style="padding:14px 24px;border-top:1px solid #E2E8F0;display:flex;justify-content:flex-end;gap:10px;">',
        '<button id="svc-copyto-btn" onclick="_svcCopyToOpen()" style="padding:9px 20px;border-radius:8px;border:1px solid #6366F1;color:#6366F1;background:#fff;font-size:.84rem;font-weight:600;cursor:pointer;">Copy To</button>',
        '<button id="svc-save-btn" onclick="_svcSave()" style="padding:9px 20px;border-radius:8px;border:none;background:#6366F1;color:#fff;font-size:.84rem;font-weight:600;cursor:pointer;">Save</button>',
        '</div>',

        '</div>',  # panel

        # Copy To popup — CSS + HTML matching reference design
        '<style>'
        '.svc-ct-ov{position:fixed;inset:0;z-index:10001;display:none;align-items:center;justify-content:center;background:rgba(15,15,30,.45);backdrop-filter:blur(6px);padding:24px;}'
        '@keyframes svcCtIn{from{opacity:0;transform:scale(.94) translateY(8px)}to{opacity:1;transform:scale(1) translateY(0)}}'
        '.svc-ct-modal{background:#fff;border-radius:16px;width:100%;max-width:420px;box-shadow:0 0 0 1px rgba(108,84,232,.12),0 24px 60px rgba(0,0,0,.18);overflow:hidden;animation:svcCtIn .25s cubic-bezier(.34,1.56,.64,1) both;}'
        '.svc-ct-hdr{padding:22px 24px 18px;display:flex;align-items:flex-start;justify-content:space-between;border-bottom:1px solid #f0eeff;}'
        '.svc-ct-icon{width:42px;height:42px;background:#ede9fd;border-radius:12px;display:grid;place-items:center;flex-shrink:0;}'
        '.svc-ct-icon svg{width:20px;height:20px;stroke:#6c54e8;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;}'
        '.svc-ct-ttl{font-size:16px;font-weight:700;color:#1a1d2e;letter-spacing:-.01em;}'
        '.svc-ct-sub{font-size:12px;color:#9ca3af;margin-top:2px;}'
        '.svc-ct-x{width:28px;height:28px;border:1px solid #e4e6ed;border-radius:7px;background:#fff;display:grid;place-items:center;cursor:pointer;color:#9ca3af;font-size:13px;transition:border-color .15s,color .15s;flex-shrink:0;}'
        '.svc-ct-x:hover{border-color:#ef4444;color:#ef4444;}'
        '.svc-ct-body{padding:16px 24px;}'
        '.svc-ct-desc{font-size:13px;color:#6b7280;line-height:1.6;margin-bottom:14px;}'
        '.svc-ct-sw{position:relative;margin-bottom:10px;}'
        '.svc-ct-si{position:absolute;left:10px;top:50%;transform:translateY(-50%);width:14px;height:14px;stroke:#9ca3af;fill:none;stroke-width:2;stroke-linecap:round;pointer-events:none;}'
        '.svc-ct-sinp{width:100%;padding:8px 12px 8px 34px;border:1px solid #e4e6ed;border-radius:8px;font-size:12.5px;color:#1a1d2e;background:#fafafa;outline:none;transition:border-color .15s,box-shadow .15s;box-sizing:border-box;}'
        '.svc-ct-sinp:focus{border-color:#6c54e8;box-shadow:0 0 0 3px rgba(108,84,232,.08);background:#fff;}'
        '.svc-ct-sinp::placeholder{color:#9ca3af;}'
        '.svc-ct-selall{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:#faf9ff;border:1px solid #e8e2ff;border-radius:8px 8px 0 0;border-bottom:none;cursor:pointer;user-select:none;}'
        '.svc-ct-selall:hover{background:#f3f0ff;}'
        '.svc-ct-selall-lbl{display:flex;align-items:center;gap:8px;font-size:12px;font-weight:600;color:#6c54e8;}'
        '.svc-ct-cnt{font-size:11px;color:#a993f5;font-weight:500;}'
        '.svc-ct-list{border:1px solid #e8e2ff;border-radius:0 0 8px 8px;overflow-y:auto;max-height:240px;}'
        '.svc-ct-list::-webkit-scrollbar{width:4px;}'
        '.svc-ct-list::-webkit-scrollbar-track{background:#faf9ff;}'
        '.svc-ct-list::-webkit-scrollbar-thumb{background:#c4b5fd;border-radius:99px;}'
        '.svc-ct-item{display:flex;align-items:center;justify-content:space-between;padding:11px 14px;cursor:pointer;transition:background .12s;border-bottom:1px solid #f0eeff;user-select:none;}'
        '.svc-ct-item:last-child{border-bottom:none;}'
        '.svc-ct-item:hover{background:#faf9ff;}'
        '.svc-ct-item.on{background:#f5f3ff;}'
        '.svc-ct-il{display:flex;align-items:center;gap:10px;}'
        '.svc-ct-cb{width:17px;height:17px;border:1.5px solid #d1d5db;border-radius:5px;background:#fff;display:grid;place-items:center;flex-shrink:0;transition:border-color .15s,background .15s;}'
        '.svc-ct-item.on .svc-ct-cb{background:#6c54e8;border-color:#6c54e8;}'
        '.svc-ct-cb svg{width:10px;height:10px;stroke:#fff;fill:none;stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round;opacity:0;transition:opacity .15s;}'
        '.svc-ct-item.on .svc-ct-cb svg{opacity:1;}'
        '.svc-ct-nm{font-size:13px;font-weight:500;color:#1a1d2e;}'
        '.svc-ct-badge{font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:20px;}'
        '.svc-ct-badge.act{background:#dcfce7;color:#15803d;border:1px solid #bbf7d0;}'
        '.svc-ct-badge.inact{background:#f3f4f6;color:#9ca3af;border:1px solid #e5e7eb;}'
        '.svc-ct-ftr{padding:14px 24px 20px;display:flex;align-items:center;justify-content:space-between;border-top:1px solid #f0eeff;}'
        '.svc-ct-fi{font-size:11.5px;color:#a993f5;font-weight:500;}'
        '.svc-ct-fbtns{display:flex;gap:8px;}'
        '.svc-ct-btn{padding:9px 22px;border-radius:9px;font-size:13.5px;font-weight:600;cursor:pointer;transition:all .15s;border:none;font-family:inherit;}'
        '.svc-ct-btn.cancel{background:#f4f5f8;color:#6b7280;border:1px solid #e4e6ed;}'
        '.svc-ct-btn.cancel:hover{background:#e9eaee;color:#1a1d2e;}'
        '.svc-ct-btn.copy{background:#6c54e8;color:#fff;box-shadow:0 2px 8px rgba(108,84,232,.35);padding:9px 28px;}'
        '.svc-ct-btn.copy:hover{background:#5a43d0;box-shadow:0 4px 16px rgba(108,84,232,.45);transform:translateY(-1px);}'
        '.svc-ct-btn.copy:disabled{background:#c4b5fd;box-shadow:none;cursor:not-allowed;transform:none;}'
        '.svc-ct-res{padding:0 24px 16px;font-size:.8rem;min-height:0;}'
        '</style>',

        '<div id="svc-copyto-popup" class="svc-ct-ov">',
        '<div class="svc-ct-modal">',

        # header
        '<div class="svc-ct-hdr">',
        '<div style="display:flex;align-items:center;gap:12px;">',
        '<div class="svc-ct-icon">',
        '<svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2"/>'
        '<path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>',
        '</div>',
        '<div><div class="svc-ct-ttl">Copy To</div>'
        '<div class="svc-ct-sub">적용할 DGServer를 선택하세요</div></div>',
        '</div>',
        '<button class="svc-ct-x" onclick="_svcCopyToClose()">✕</button>',
        '</div>',

        # body
        '<div class="svc-ct-body">',
        '<div class="svc-ct-desc">현재 편집 중인 XML을 적용할 DGServer를 선택하세요.</div>',
        '<div class="svc-ct-sw">',
        '<svg class="svc-ct-si" viewBox="0 0 24 24">'
        '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
        '<input class="svc-ct-sinp" type="text" id="svc-ct-search" '
        'placeholder="프로세스 검색..." oninput="_svcCtFilter()">',
        '</div>',
        '<div class="svc-ct-selall" onclick="_svcCtToggleAll()">',
        '<div class="svc-ct-selall-lbl">',
        '<div class="svc-ct-cb" id="svc-ct-cb-all">'
        '<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></div>',
        '전체 선택',
        '</div>',
        '<span class="svc-ct-cnt" id="svc-ct-cnt">0 / 0 선택</span>',
        '</div>',
        '<div class="svc-ct-list" id="svc-ct-list"></div>',
        '</div>',  # body

        # footer
        '<div class="svc-ct-ftr">',
        '<span class="svc-ct-fi" id="svc-ct-fi">선택된 프로세스 없음</span>',
        '<div class="svc-ct-fbtns">',
        '<button class="svc-ct-btn cancel" onclick="_svcCopyToClose()">닫기</button>',
        '<button class="svc-ct-btn copy" id="svc-ct-copy-btn" disabled onclick="_svcDoCopy()">Copy</button>',
        '</div>',
        '</div>',

        # result area (below footer, inside modal)
        '<div id="svc-copyto-result" class="svc-ct-res"></div>',

        '</div></div>',  # modal, popup

        # Copy 확인 모달
        '<div id="svc-ct-confirm" style="display:none;position:fixed;inset:0;z-index:10002;'
        'align-items:center;justify-content:center;background:rgba(15,15,30,.55);backdrop-filter:blur(6px);padding:24px;">',
        '<div style="background:#fff;border-radius:16px;width:100%;max-width:400px;'
        'box-shadow:0 0 0 1px rgba(108,84,232,.12),0 24px 60px rgba(0,0,0,.22);overflow:hidden;'
        'animation:svcCtIn .2s cubic-bezier(.34,1.56,.64,1) both;">',

        # confirm header
        '<div style="padding:20px 24px 16px;display:flex;align-items:center;gap:12px;border-bottom:1px solid #f0eeff;">',
        '<div style="width:40px;height:40px;background:#fff7ed;border-radius:12px;display:grid;place-items:center;flex-shrink:0;">',
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f97316" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>'
        '<line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
        '</div>',
        '<div>',
        '<div style="font-size:15px;font-weight:700;color:#1a1d2e;letter-spacing:-.01em;">복사 확인</div>',
        '<div style="font-size:12px;color:#9ca3af;margin-top:2px;" id="svc-ct-confirm-sub"></div>',
        '</div>',
        '</div>',

        # confirm body
        '<div style="padding:16px 24px;">',
        '<p style="font-size:13px;color:#374151;margin:0 0 12px;line-height:1.6;">'
        '아래 DGServer의 <strong id="svc-ct-confirm-kind" style="color:#6c54e8;"></strong> XML을 현재 편집 내용으로 덮어씁니다.</p>',
        '<div id="svc-ct-confirm-list" style="display:flex;flex-direction:column;gap:6px;max-height:180px;overflow-y:auto;"></div>',
        '<p style="font-size:11.5px;color:#9ca3af;margin:12px 0 0;line-height:1.5;">'
        '&#9432; 덮어쓰기 전 기존 파일은 자동으로 백업됩니다.</p>',
        '</div>',

        # confirm footer
        '<div style="padding:14px 24px 20px;display:flex;justify-content:flex-end;gap:8px;border-top:1px solid #f0eeff;">',
        '<button class="svc-ct-btn cancel" onclick="_svcCtConfirmClose()">취소</button>',
        '<button class="svc-ct-btn copy" id="svc-ct-confirm-ok" onclick="_svcDoActualCopy()">Copy</button>',
        '</div>',

        '</div></div>',  # confirm modal

        # JavaScript
        '<script>',
        'var _svcKind="",_svcData=null;',
        'function _svcOpen(kind){',
        '  _svcKind=kind;',
        '  var w=document.getElementById("svc-cfg-modal");',
        '  document.getElementById("svc-cfg-title").textContent=kind.toUpperCase()+" Service Configuration";',
        '  w.style.top="5%";w.style.left="50%";w.style.transform="translateX(-50%)";w.style.display="flex";',
        '  if(typeof _bringFront==="function")_bringFront(w);',
        '  _svcShowXmlParams(kind);',
        '  _svcBindRefMutex();',
        '  _svcInitDrag();',
        '  var sel=document.getElementById("svc-dgs-sel");',
        '  sel.innerHTML="<option>Loading...</option>";',
        '  document.getElementById("svc-xml-editor").value="Loading...";',
        '  fetch("', ub, '/api/alert-svc-read?kind="+kind)',
        '  .then(function(r){return r.json();})',
        '  .then(function(d){',
        '    if(!d.ok){_svcDialog({kind:"error",title:"불러오기 실패",body:d.error||"알 수 없는 오류"});return;}',
        '    _svcData=d.results;',
        '    sel.innerHTML=d.results.map(function(r,i){',
        '      return "<option value=\\""+i+"\\">"+r.dgserver+(r.active?" (Active)":" (Inactive)")+"</option>";',
        '    }).join("");',
        '    _svcLoadDgs();',
        '  }).catch(function(){_svcDialog({kind:"error",title:"요청 실패",body:"네트워크 오류로 데이터를 불러오지 못했습니다."});});',
        '}',
        'function _svcLoadDgs(){',
        '  var idx=document.getElementById("svc-dgs-sel").value;',
        '  if(!_svcData||!_svcData[idx])return;',
        '  var r=_svcData[idx];',
        '  document.getElementById("svc-active-cb").checked=r.active;',
        '  document.getElementById("svc-xml-editor").value=r.raw||"(no XML found)";',
        '}',
        'function _svcClose(){document.getElementById("svc-cfg-modal").style.display="none";}',
        'var _svcDragBound=false;'
        'function _svcInitDrag(){'
        '  if(_svcDragBound)return;'
        '  var hdr=document.getElementById("svc-cfg-hdr"),win=document.getElementById("svc-cfg-modal");'
        '  if(!hdr||!win)return;'
        '  var ox=0,oy=0,mx=0,my=0;'
        '  hdr.onmousedown=function(e){e.preventDefault();'
        '    if(win.style.transform&&win.style.transform!=="none"){var r=win.getBoundingClientRect();win.style.left=r.left+"px";win.style.top=r.top+"px";win.style.transform="none";}'
        '    mx=e.clientX;my=e.clientY;'
        '    if(typeof _bringFront==="function")_bringFront(win);'
        '    document.onmousemove=function(ev){ox=mx-ev.clientX;oy=my-ev.clientY;mx=ev.clientX;my=ev.clientY;'
        '      win.style.top=(win.offsetTop-oy)+"px";win.style.left=(win.offsetLeft-ox)+"px";};'
        '    document.onmouseup=function(){document.onmousemove=null;document.onmouseup=null;};'
        '  };'
        '  _svcDragBound=true;'
        '}',
        'var _svcRefBound=false;'
        'function _svcBindRefMutex(){'
        '  if(_svcRefBound)return;'
        '  var ids=["xml-param-ref","bind-param-ref"];'
        '  ids.forEach(function(id){'
        '    var el=document.getElementById(id);'
        '    if(!el)return;'
        '    el.addEventListener("toggle",function(){'
        '      if(!el.open)return;'
        '      ids.forEach(function(other){'
        '        if(other===id)return;'
        '        var o=document.getElementById(other);'
        '        if(o&&o.open)o.open=false;'
        '      });'
        '    });'
        '  });'
        '  _svcRefBound=true;'
        '}',
        # ── 통합 Dialog (Service Configuration 전용. native alert/confirm 대체) ──
        'function _svcDlgEsc(s){',
        '  return String(s==null?"":s).replace(/[&<>\\"\\\']/g,function(c){',
        '    return ({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","\\\'":"&#39;"})[c];',
        '  });',
        '}',
        'function _svcDialog(opts){',
        '  var k=opts.kind||"info";',
        '  var iconBgs={success:"#dcfce7",error:"#fee2e2",confirm:"#ede9fd",info:"#e0f2fe"};',
        '  var iconColors={success:"#15803d",error:"#dc2626",confirm:"#6c54e8",info:"#0284c7"};',
        '  var iconPaths={',
        '    success:"<polyline points=\\"20 6 9 17 4 12\\"/>",',
        '    error:"<line x1=\\"18\\" y1=\\"6\\" x2=\\"6\\" y2=\\"18\\"/><line x1=\\"6\\" y1=\\"6\\" x2=\\"18\\" y2=\\"18\\"/>",',
        '    confirm:"<circle cx=\\"12\\" cy=\\"12\\" r=\\"10\\"/><path d=\\"M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3\\"/><line x1=\\"12\\" y1=\\"17\\" x2=\\"12.01\\" y2=\\"17\\"/>",',
        '    info:"<circle cx=\\"12\\" cy=\\"12\\" r=\\"10\\"/><line x1=\\"12\\" y1=\\"16\\" x2=\\"12\\" y2=\\"12\\"/><line x1=\\"12\\" y1=\\"8\\" x2=\\"12.01\\" y2=\\"8\\"/>"',
        '  };',
        '  var ov=document.getElementById("svc-dlg-ov");',
        '  if(!ov){ov=document.createElement("div");ov.id="svc-dlg-ov";ov.className="svc-ct-ov";ov.style.zIndex="10100";document.body.appendChild(ov);}',
        '  var showCancel=(k==="confirm");',
        '  var confirmText=opts.confirmText||"확인";',
        '  var cancelText=opts.cancelText||"취소";',
        '  var bodyHtml=opts.html_body||_svcDlgEsc(opts.body||"").replace(/\\n/g,"<br>");',
        '  ov.innerHTML=""+',
        '    "<div class=\\"svc-ct-modal\\" style=\\"max-width:440px;\\">"+',
        '      "<div style=\\"padding:22px 24px 16px;display:flex;align-items:center;gap:12px;border-bottom:1px solid #f0eeff;\\">"+',
        '        "<div style=\\"width:42px;height:42px;background:"+iconBgs[k]+";border-radius:12px;display:grid;place-items:center;flex-shrink:0;\\">"+',
        '          "<svg width=\\"20\\" height=\\"20\\" viewBox=\\"0 0 24 24\\" fill=\\"none\\" stroke=\\""+iconColors[k]+"\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\" stroke-linejoin=\\"round\\">"+iconPaths[k]+"</svg>"+',
        '        "</div>"+',
        '        "<div style=\\"flex:1;min-width:0;\\"><div style=\\"font-size:15px;font-weight:700;color:#1a1d2e;letter-spacing:-.01em;\\">"+_svcDlgEsc(opts.title||"")+"</div></div>"+',
        '      "</div>"+',
        '      "<div style=\\"padding:18px 24px;font-size:13px;color:#374151;line-height:1.6;max-height:320px;overflow-y:auto;\\">"+bodyHtml+"</div>"+',
        '      "<div style=\\"padding:14px 24px 20px;display:flex;justify-content:flex-end;gap:8px;border-top:1px solid #f0eeff;\\">"+',
        '        (showCancel?"<button class=\\"svc-ct-btn cancel\\" id=\\"svc-dlg-cancel\\">"+_svcDlgEsc(cancelText)+"</button>":"")+',
        '        "<button class=\\"svc-ct-btn copy\\" id=\\"svc-dlg-ok\\">"+_svcDlgEsc(confirmText)+"</button>"+',
        '      "</div>"+',
        '    "</div>";',
        '  ov.style.display="flex";',
        '  function _close(){ov.style.display="none";ov.innerHTML="";}',
        '  document.getElementById("svc-dlg-ok").onclick=function(){_close();if(typeof opts.onConfirm==="function")opts.onConfirm();};',
        '  if(showCancel){document.getElementById("svc-dlg-cancel").onclick=function(){_close();if(typeof opts.onCancel==="function")opts.onCancel();};}',
        '}',
        # ── _svcSave: native alert/confirm → _svcDialog 로 통합 ──
        'function _svcSave(){',
        '  var idx=document.getElementById("svc-dgs-sel").value;',
        '  if(!_svcData||!_svcData[idx]){_svcDialog({kind:"error",title:"오류",body:"DGServer 데이터가 없습니다."});return;}',
        '  var r=_svcData[idx];',
        '  var activate=document.getElementById("svc-active-cb").checked;',
        '  var raw=document.getElementById("svc-xml-editor").value;',
        '  _svcDialog({',
        '    kind:"confirm",',
        '    title:"설정 저장",',
        '    html_body:"<p style=\\"margin:0;\\">"+_svcKind.toUpperCase()+" Service 설정을 <strong style=\\"color:#6c54e8;\\">"+_svcDlgEsc(r.dgserver)+"</strong> 에 저장하시겠습니까?</p>"+',
        '              "<p style=\\"font-size:11.5px;color:#9ca3af;margin:12px 0 0;line-height:1.5;\\">&#9432; 저장 전 기존 XML 파일은 자동 백업됩니다.</p>",',
        '    confirmText:"Save",',
        '    cancelText:"취소",',
        '    onConfirm:function(){',
        '      var btn=document.getElementById("svc-save-btn");btn.disabled=true;btn.textContent="Saving...";',
        '      fetch("', ub, '/api/alert-svc-save",{method:"POST",',
        '        headers:{"Content-Type":"application/json"},',
        '        body:JSON.stringify({kind:_svcKind,svc_dir:r.svc_dir,activate:activate,raw_xml:raw})})',
        '      .then(function(r){return r.json();})',
        '      .then(function(d){',
        '        btn.disabled=false;btn.textContent="Save";',
        '        if(d.ok){',
        '          var listHtml=(d.results||[]).map(function(s){return "<li style=\\"margin:3px 0;color:#475569;\\">"+_svcDlgEsc(s)+"</li>";}).join("");',
        '          _svcDialog({',
        '            kind:"success",',
        '            title:"저장 완료",',
        '            html_body:"<p style=\\"margin:0 0 8px;color:#1a1d2e;\\">다음 파일이 갱신되었습니다.</p>"+',
        '                      "<ul style=\\"margin:0;padding-left:18px;font-size:12.5px;\\">"+listHtml+"</ul>",',
        '            confirmText:"확인",',
        '            onConfirm:function(){_svcClose();location.reload();}',
        '          });',
        '        }else{',
        '          _svcDialog({kind:"error",title:"저장 실패",body:d.error||"알 수 없는 오류"});',
        '        }',
        '      }).catch(function(){',
        '        btn.disabled=false;btn.textContent="Save";',
        '        _svcDialog({kind:"error",title:"요청 실패",body:"네트워크 오류로 저장하지 못했습니다."});',
        '      });',
        '    }',
        '  });',
        '}',

        # Copy To JS
        'var _svcCtItems=[],_svcCtChecked=new Set(),_svcCtQuery="";',

        'function _svcCopyToOpen(){',
        '  if(!_svcData||_svcData.length<2){_svcDialog({kind:"info",title:"복사 대상 없음",body:"복사 대상 DGServer 가 없습니다."});return;}',
        '  var curIdx=parseInt(document.getElementById("svc-dgs-sel").value);',
        '  _svcCtItems=_svcData.map(function(r,i){return Object.assign({},r,{_idx:i});}).filter(function(r){return r._idx!==curIdx;});',
        '  _svcCtChecked=new Set();',
        '  _svcCtQuery="";',
        '  var si=document.getElementById("svc-ct-search");if(si)si.value="";',
        '  document.getElementById("svc-copyto-result").innerHTML="";',
        '  _svcCtRender();',
        '  var popup=document.getElementById("svc-copyto-popup");',
        '  popup.style.display="flex";',
        '}',

        'function _svcCtFilter(){',
        '  _svcCtQuery=document.getElementById("svc-ct-search").value;',
        '  _svcCtRender();',
        '}',

        'function _svcCtVisible(){',
        '  var q=_svcCtQuery.toLowerCase();',
        '  return q?_svcCtItems.filter(function(r){return r.dgserver.toLowerCase().indexOf(q)>-1;}):_svcCtItems.slice();',
        '}',

        'function _svcCtRender(){',
        '  var list=document.getElementById("svc-ct-list");',
        '  var visible=_svcCtVisible();',
        '  list.innerHTML=visible.map(function(r){',
        '    var on=_svcCtChecked.has(r.svc_dir)?"on":"";',
        '    var badge=r.active'
        '      ?"<span class=\\"svc-ct-badge act\\">Active</span>"'
        '      :"<span class=\\"svc-ct-badge inact\\">Inactive</span>";',
        '    return "<div class=\\"svc-ct-item "+on+"\\" onclick=\\"_svcCtToggle(\'"+r.svc_dir+"\')\\">"',
        '      +"<div class=\\"svc-ct-il\\">"',
        '      +"<div class=\\"svc-ct-cb\\"><svg viewBox=\\"0 0 24 24\\"><polyline points=\\"20 6 9 17 4 12\\"/></svg></div>"',
        '      +"<span class=\\"svc-ct-nm\\">"+r.dgserver+"</span>"',
        '      +"</div>"+badge+"</div>";',
        '  }).join("");',
        '  _svcCtUpdateState(visible);',
        '}',

        'function _svcCtToggle(svcDir){',
        '  if(_svcCtChecked.has(svcDir))_svcCtChecked.delete(svcDir);',
        '  else _svcCtChecked.add(svcDir);',
        '  _svcCtRender();',
        '}',

        'function _svcCtToggleAll(){',
        '  var visible=_svcCtVisible();',
        '  var allOn=visible.length>0&&visible.every(function(r){return _svcCtChecked.has(r.svc_dir);});',
        '  if(allOn){visible.forEach(function(r){_svcCtChecked.delete(r.svc_dir);});}',
        '  else{visible.forEach(function(r){_svcCtChecked.add(r.svc_dir);});}',
        '  _svcCtRender();',
        '}',

        'function _svcCtUpdateState(visible){',
        '  var n=_svcCtChecked.size,total=_svcCtItems.length;',
        '  var vis=visible||_svcCtVisible();',
        '  var allOn=vis.length>0&&vis.every(function(r){return _svcCtChecked.has(r.svc_dir);});',
        '  document.getElementById("svc-ct-cnt").textContent=n+" / "+total+" 선택";',
        '  document.getElementById("svc-ct-fi").textContent=n===0?"선택된 프로세스 없음":n+"개 프로세스에 적용";',
        '  var copyBtn=document.getElementById("svc-ct-copy-btn");',
        '  if(copyBtn)copyBtn.disabled=(n===0);',
        '  var cbAll=document.getElementById("svc-ct-cb-all");',
        '  if(cbAll){cbAll.style.background=allOn?"#6c54e8":"";cbAll.style.borderColor=allOn?"#6c54e8":"";',
        '    cbAll.querySelector("svg").style.opacity=allOn?"1":"0";}',
        '}',

        'function _svcCopyToClose(){',
        '  document.getElementById("svc-copyto-popup").style.display="none";',
        '}',

        # _svcDoCopy: 확인 모달 표시
        'var _svcCtPendingTargets=[],_svcCtPendingRaw="",_svcCtPendingActivate=false;',
        'function _svcDoCopy(){',
        '  if(_svcCtChecked.size===0){return;}',
        '  _svcCtPendingTargets=Array.from(_svcCtChecked);',
        '  _svcCtPendingRaw=document.getElementById("svc-xml-editor").value;',
        '  _svcCtPendingActivate=document.getElementById("svc-active-cb").checked;',
        '  var names=_svcCtItems.filter(function(r){return _svcCtChecked.has(r.svc_dir);}).map(function(r){return r.dgserver;});',
        '  var kindLabel=_svcKind.toUpperCase();',
        '  document.getElementById("svc-ct-confirm-kind").textContent=kindLabel;',
        '  document.getElementById("svc-ct-confirm-sub").textContent=names.length+"개 DGServer에 적용";',
        '  var listEl=document.getElementById("svc-ct-confirm-list");',
        '  listEl.innerHTML=names.map(function(n){',
        '    return "<div style=\\"display:flex;align-items:center;gap:8px;padding:8px 12px;'
        'background:#faf9ff;border:1px solid #e8e2ff;border-radius:8px;font-size:13px;font-weight:500;color:#1a1d2e;\\">"',
        '      +"<svg width=\\"14\\" height=\\"14\\" viewBox=\\"0 0 24 24\\" fill=\\"none\\" stroke=\\"#6c54e8\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\" stroke-linejoin=\\"round\\">'
        '<rect x=\\"9\\" y=\\"9\\" width=\\"13\\" height=\\"13\\" rx=\\"2\\"/>'
        '<path d=\\"M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1\\"/></svg>"',
        '      +n+"</div>";',
        '  }).join("");',
        '  document.getElementById("svc-ct-confirm").style.display="flex";',
        '}',

        'function _svcCtConfirmClose(){',
        '  document.getElementById("svc-ct-confirm").style.display="none";',
        '}',

        # 실제 복사 실행
        'function _svcDoActualCopy(){',
        '  var btn=document.getElementById("svc-ct-confirm-ok");',
        '  var res=document.getElementById("svc-copyto-result");',
        '  btn.disabled=true;btn.textContent="Copying...";',
        '  fetch("', ub, '/api/alert-svc-copy",{method:"POST",',
        '    headers:{"Content-Type":"application/json"},',
        '    body:JSON.stringify({kind:_svcKind,raw_xml:_svcCtPendingRaw,target_svc_dirs:_svcCtPendingTargets,activate:_svcCtPendingActivate})})',
        '  .then(function(r){return r.json();})',
        '  .then(function(d){',
        '    btn.disabled=false;btn.textContent="Copy";',
        '    _svcCtConfirmClose();',
        '    if(d.ok){',
        '      var lines=d.results.map(function(r){',
        '        return (r.status==="ok"?"✓ ":"✕ ")+(r.file||r.svc_dir)+(r.backup?" (backup: "+r.backup+")":"");',
        '      });',
        '      res.innerHTML="<div style=\\"color:#15803d;font-weight:600;margin-bottom:4px;\\">완료</div>"',
        '        +"<div style=\\"font-size:.78rem;color:#475569;white-space:pre-line;\\">"+lines.join("\\n")+"</div>";',
        '    }else{',
        '      var errs=(d.results||[]).map(function(r){return r.status==="error"?"✕ "+(r.svc_dir||"")+" — "+(r.message||""):"";}).filter(Boolean);',
        '      res.innerHTML="<div style=\\"color:#EF4444;font-weight:600;margin-bottom:4px;\\">"+(d.error||"일부 실패")+"</div>"',
        '        +(errs.length?"<div style=\\"font-size:.78rem;color:#EF4444;white-space:pre-line;\\">"+errs.join("\\n")+"</div>":"");',
        '    }',
        '  }).catch(function(){',
        '    btn.disabled=false;btn.textContent="Copy";',
        '    _svcCtConfirmClose();',
        '    res.innerHTML="<span style=\\"color:#EF4444;\\">요청 실패</span>";',
        '  });',
        '}',
        '</script>',
    ])
