# -*- coding: utf-8 -*-
import os
import re
import subprocess

from service_config import load_service_config
from system_utils import _xml_val, _read_lines
from html_helpers import (
    _warn_box, _info_box, _page_title_html, _page,
    _HELP, _HELP_JS, _ts, _UTILS_BASE,
)

try:
    from urllib.parse import unquote, unquote_plus
except ImportError:
    from urllib import unquote


def _pick_latest_log(home, is_master):
    prefix  = "DGM_" if is_master else "DGS_"
    log_dir = os.path.join(home, "log")
    if not os.path.isdir(log_dir):
        return ""
    candidates = [f for f in os.listdir(log_dir)
                  if f.startswith(prefix) and f.endswith(".log")]
    if not candidates:
        return ""
    candidates.sort(key=lambda f: os.path.getmtime(os.path.join(log_dir, f)), reverse=True)
    return os.path.join(log_dir, candidates[0])


def _gather_log_html():
    svc      = load_service_config()
    services = svc.get("services", {})
    homes    = []

    dgm = services.get("dgserver_m", "")
    if dgm:
        homes.append(("DGServer_M", dgm, True))

    for i, dgs in enumerate(services.get("dgserver_s", [])):
        if dgs:
            homes.append(("DGServer_S{0}".format(i + 1), dgs, False))

    if not homes:
        return _warn_box("No DGServer paths configured. Go to Configuration.")

    parts = []
    for idx, (name, home, is_master) in enumerate(homes):
        xmlfile = os.path.join(home, "conf", "DGServer.xml")
        port    = _xml_val(xmlfile, "gather_port")

        if port:
            logfile = os.path.join(home, "log", ("DGM_" if is_master else "DGS_") + port + ".log")
            if not os.path.exists(logfile):
                logfile = _pick_latest_log(home, is_master)
        else:
            logfile = _pick_latest_log(home, is_master)

        parts.append('<div class="insp-card">')
        parts.append('<div class="insp-card-hdr">')
        parts.append('<div class="insp-card-title">{0}</div>'.format(name))
        parts.append('</div>')
        parts.append('<div class="insp-card-body" style="padding:15px;">')

        if not logfile or not os.path.exists(logfile):
            parts.append(_warn_box("로그 파일을 찾을 수 없습니다: " + home))
        else:
            try:
                OVERVIEW_LIMIT = 500
                grep_pat = r'\[ERROR|\[WARN'
                # 총 건수
                cp = subprocess.Popen(['grep', '-cE', grep_pat, logfile],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                cout, _ = cp.communicate()
                try:
                    total_err = int(cout.strip())
                except Exception:
                    total_err = 0
                # 마지막 500건
                gp = subprocess.Popen(['grep', '-E', grep_pat, logfile],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                tp = subprocess.Popen(['tail', '-n', str(OVERVIEW_LIMIT)],
                         stdin=gp.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                gp.stdout.close()
                tout, _ = tp.communicate()
                err_lines = tout.splitlines() if tout else []

                if not err_lines:
                    parts.append(
                        '<div style="background:var(--ok-bg); border:1px solid var(--ok-bd); color:var(--ok-c); padding:12px; border-radius:8px; font-size:0.85rem;">'
                        '오류가 발견되지 않았습니다.'
                        '</div>'
                    )
                else:
                    shown = len(err_lines)
                    if total_err > shown:
                        cnt_text = 'Found {0:,} / {1:,} entries (showing last {2:,})'.format(shown, total_err, shown)
                        warn_tag = '<span style="color:#f59e0b;font-weight:600;"> &#9888; Too many results. Use search to filter.</span>'
                    else:
                        cnt_text = 'Found {0:,} error/warning entries'.format(shown)
                        warn_tag = ''
                    log_content = '\n'.join(err_lines)
                    esc      = log_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

                    parts.append('<div style="background:var(--err-bg); border:1px solid var(--err-bd); border-radius:8px; padding:12px;">')
                    parts.append('<div style="font-size:0.75rem; font-weight:600; color:var(--err-c); margin-bottom:8px; display:flex; justify-content:space-between;">')
                    parts.append('<span>{0}{1}</span>'.format(cnt_text, warn_tag))
                    parts.append('</div>')
                    parts.append(
                        '<div style="max-height:300px; overflow-y:auto; background:var(--err-log-bg); border-radius:4px; padding:10px; border:1px solid var(--err-log-bd);">'
                        '<pre style="margin:0; font-family:\'JetBrains Mono\', \'Fira Code\', monospace; font-size:12px; color:var(--err-log-c); white-space:pre-wrap; line-height:1.5;">{0}</pre>'
                        '</div>'.format(esc)
                    )
                    parts.append('</div>')
            except Exception as e:
                parts.append(_warn_box("로그 읽기 오류: " + str(e)))

        parts.append('</div>')
        parts.append('</div>')

    return ''.join(parts)


def _gather_log_server_html(log_dir, safe_id, selected_file, search_term="", time_from="", time_to=""):
    b     = _UTILS_BASE + "/process/gather"
    parts = []

    log_files = []

    def _scan_log_dir(dirpath, prefix):
        if not dirpath or not os.path.isdir(dirpath):
            return
        try:
            for f in os.listdir(dirpath):
                if f.endswith(".log") or f.endswith(".log.zip"):
                    rel = (prefix + "/" + f) if prefix else f
                    log_files.append((rel, os.path.getmtime(os.path.join(dirpath, f))))
        except Exception:
            pass

    _scan_log_dir(log_dir, "")
    _scan_log_dir(os.path.join(log_dir, "maxgauge") if log_dir else "", "maxgauge")
    log_files.sort(key=lambda x: x[1], reverse=True)
    log_names = [x[0] for x in log_files]

    # ── 카드 시작: 헤더(파일 select) + 본문(검색/로그) ──
    parts.append('<div class="insp-card">')
    parts.append('<div class="insp-card-hdr" style="display:block;">')
    if not log_names:
        parts.append(_warn_box("로그 파일이 없습니다."))
    else:
        sel_js = "location.href='%s?tab=%s&file='+encodeURIComponent(this.value)" % (b, safe_id)
        parts.append('<select onchange="%s" style="width:100%%;padding:8px 12px;border-radius:8px;border:1px solid var(--bd);background:var(--bg-input);color:var(--c-main);font-size:.84rem;">' % sel_js)
        parts.append('<option value="">-- Select log file --</option>')

        # 그룹 분류
        grp_dgx      = []  # DGM_ / DGS_ 로 시작
        grp_maxgauge = []  # maxgauge/ 하위
        grp_other    = []  # 나머지

        for f in log_names:
            base = f.split('/')[-1].lower()
            if f.startswith('maxgauge/'):
                grp_maxgauge.append(f)
            elif base.startswith('dgm_') or base.startswith('dgs_'):
                grp_dgx.append(f)
            else:
                grp_other.append(f)

        def _opts(files):
            return ''.join(
                '<option value="%s"%s>%s</option>' % (f, ' selected' if f == selected_file else '', f)
                for f in files
            )

        for label, grp in [
            ('DG',    grp_dgx),
            ('OBSD',  grp_maxgauge),
            ('Other', sorted(grp_other, reverse=True)),
        ]:
            if grp:
                parts.append('<optgroup label="%s">' % label)
                parts.append(_opts(grp))
                parts.append('</optgroup>')

        parts.append('</select>')
    parts.append('</div>')  # close insp-card-hdr

    if not selected_file:
        parts.append('</div>')  # close insp-card (헤더만 있고 끝)
        return ''.join(parts)

    log_path = os.path.join(log_dir, selected_file)
    if not os.path.exists(log_path):
        parts.append('<div class="insp-card-body" style="padding:14px 16px;">')
        parts.append(_warn_box("File not found"))
        parts.append('</div></div>')
        return ''.join(parts)

    parts.append('<div class="insp-card-body" style="padding:14px 16px;">')

    is_zip = selected_file.endswith(".log.zip")

    try:
        import zipfile as _zf, re as _re
        SEARCH_LIMIT = 500

        time_re  = _re.compile(r'^\[(\d{2}:\d{2}:\d{2}(?:\.\d+)?)')
        has_time = bool(time_from or time_to)
        tf = (time_from or "00:00:00.000").ljust(12, '0')
        tt = (time_to   or "23:59:59.999").ljust(12, '9')

        _last_ts_in_range = [False]

        def _time_match(line):
            if not has_time:
                return True
            m = time_re.match(line)
            if m:
                ts = m.group(1).ljust(12, '0')
                _last_ts_in_range[0] = (tf <= ts <= tt)
                return _last_ts_in_range[0]
            # Continuation line (stack trace, Caused by, etc.)
            # — include if the preceding timestamped line was in range.
            return _last_ts_in_range[0]

        has_any_filter = bool(search_term) or has_time

        if is_zip:
            with _zf.ZipFile(log_path, 'r') as zf:
                inner = zf.namelist()
                if not inner:
                    parts.append(_warn_box("Empty zip file"))
                    return ''.join(parts)
                all_lines = zf.read(inner[0]).decode('utf-8', errors='replace').splitlines()

            if has_any_filter:
                pat = _re.compile(_re.escape(search_term), _re.IGNORECASE) if search_term else None
                matched = [l for l in all_lines
                           if (not pat or pat.search(l)) and _time_match(l)]
                total_match = len(matched)
                shown_lines = matched[:SEARCH_LIMIT]
                filter_label = "Search Results"
            else:
                total_match = None
                shown_lines = all_lines[-1000:]
                filter_label = "Latest 1,000 lines"
        else:
            if has_any_filter:
                if search_term and not has_time:
                    cnt_proc  = subprocess.Popen(['grep', '-ic', search_term, log_path],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                    cnt_out, _ = cnt_proc.communicate()
                    try:
                        total_match = int(cnt_out.strip())
                    except Exception:
                        total_match = 0
                    cmd          = ['grep', '-i', '-m', str(SEARCH_LIMIT), search_term, log_path]
                    filter_label = "Search Results"
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                    stdout, _ = proc.communicate()
                    shown_lines = stdout.splitlines() if stdout else []
                else:
                    with open(log_path, 'r', encoding='utf-8', errors='replace') as _lf:
                        all_lines = _lf.readlines()
                    pat = _re.compile(_re.escape(search_term), _re.IGNORECASE) if search_term else None
                    matched = [l.rstrip('\n') for l in all_lines
                               if (not pat or pat.search(l)) and _time_match(l)]
                    total_match = len(matched)
                    shown_lines = matched[:SEARCH_LIMIT]
                    filter_label = "Search Results"
            else:
                total_match  = None
                cmd          = ['tail', '-n', '1000', log_path]
                filter_label = "Latest 1,000 lines"
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                stdout, _ = proc.communicate()
                shown_lines = stdout.splitlines() if stdout else []

        total_count = len(shown_lines)
    except Exception as e:
        parts.append(_warn_box("Error: " + str(e)))
        return ''.join(parts)

    f_attr     = selected_file.replace('"', '&quot;')
    s_attr     = (search_term or "").replace('"', '&quot;').replace('&', '&amp;')
    tf_attr    = (time_from or "").replace('"', '&quot;')
    tt_attr    = (time_to   or "").replace('"', '&quot;')
    has_filter = bool(search_term or time_from or time_to)
    clear_link = '<a href="{0}?tab={1}&file={2}" style="padding:8px 14px;border-radius:8px;border:1px solid var(--bd);color:var(--c-muted);font-size:.84rem;text-decoration:none;">Clear</a>'.format(b, safe_id, f_attr) if has_filter else ""

    if is_zip:
        follow_btn = ''
    else:
        follow_btn = (
            '<button type="button" id="follow-btn-{0}" onclick="_followToggle(\'{0}\',\'{1}\')"'
            ' style="padding:8px 16px;border-radius:8px;border:1px solid #10b981;color:#10b981;'
            'background:transparent;font-size:.84rem;cursor:pointer;white-space:nowrap;transition:all .15s;">Follow</button>'
        ).format(safe_id, log_path.replace("'", "\\'"))
    _form = (
        '<form method="GET" action="{0}" style="margin-bottom:10px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;">'
        '<input type="hidden" name="tab" value="{1}"><input type="hidden" name="file" value="{2}">'
        '<input type="text" name="search" value="{3}" placeholder="Keyword search..." '
        'style="flex:1;min-width:140px;padding:8px 12px;border-radius:8px;border:1px solid var(--bd);background:var(--bg-input);color:var(--c-main);font-size:.84rem;outline:none;">'
        '<span style="color:var(--c-muted);font-size:.78rem;white-space:nowrap;">Time</span>'
        '<input type="text" name="time_from" value="{tf}" placeholder="HH:MM:SS.mmm" '
        'style="padding:6px 8px;border-radius:8px;border:1px solid var(--bd);background:var(--bg-input);color:var(--c-main);font-family:JetBrains Mono,Consolas,monospace;font-size:.82rem;outline:none;width:130px;">'
        '<span style="color:var(--c-muted);font-size:.78rem;">~</span>'
        '<input type="text" name="time_to" value="{tt}" placeholder="HH:MM:SS.mmm" '
        'style="padding:6px 8px;border-radius:8px;border:1px solid var(--bd);background:var(--bg-input);color:var(--c-main);font-family:JetBrains Mono,Consolas,monospace;font-size:.82rem;outline:none;width:130px;">'
        '<button type="submit" style="padding:8px 16px;border-radius:8px;border:none;background:#3b82f6;color:#fff;font-size:.84rem;cursor:pointer;">Search</button>'
        '{4}</form>'
    ).format(b, safe_id, f_attr, s_attr, clear_link, tf=tf_attr, tt=tt_attr)
    parts.append(_form.replace('</form>', follow_btn + '</form>', 1))

    if search_term and total_match is not None and total_match > total_count:
        filter_info = (
            '{0}: {1:,} / {2:,} lines (showing first {3:,}) &mdash; {4}'
            '<span style="color:#f59e0b;font-weight:600;margin-left:6px;">'
            '&#9888; Too many results. Refine your search.</span>'
        ).format(filter_label, total_count, total_match, total_count, log_path)
    else:
        filter_info = '{0}: {1:,} lines &mdash; {2}'.format(filter_label, total_count, log_path)
    parts.append('<div style="font-size:.73rem;color:var(--c-muted);margin-bottom:6px;">{0}</div>'.format(filter_info))

    parts.append('<div id="log-wrap-{sid}" style="max-height:620px;overflow-y:auto;background:var(--bg-log);border:1px solid var(--bd-card);border-radius:8px;padding:10px;">'.format(sid=safe_id))
    parts.append('<pre id="log-pre-{sid}" style="margin:0;font-family:\'JetBrains Mono\',monospace;font-size:11px;line-height:1.6;white-space:pre-wrap;color:var(--c-muted);">'.format(sid=safe_id))

    formatted_output = []
    for line in shown_lines:
        esc = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        up  = line.upper()
        if '[ERROR' in up:
            formatted_output.append('<span class="log-err">{0}</span>'.format(esc))
        elif '[WARN' in up:
            formatted_output.append('<span class="log-warn">{0}</span>'.format(esc))
        else:
            formatted_output.append(esc)

    parts.append('\n'.join(formatted_output))
    parts.append('</pre></div>')

    parts.append(
        '<script>'
        'var _fTimers={},_fOffsets={},_fOn={};'
        'function _fEscape(s){return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}'
        'function _fColorLine(s){var u=s.toUpperCase();'
        '  if(u.indexOf("[ERROR")>=0)return "<span class=\\"log-err\\">"+_fEscape(s)+"</span>";'
        '  if(u.indexOf("[WARN")>=0)return "<span class=\\"log-warn\\">"+_fEscape(s)+"</span>";'
        '  return _fEscape(s);}'
        'function _followToggle(sid,fpath){'
        '  var btn=document.getElementById("follow-btn-"+sid);'
        '  if(_fOn[sid]){clearInterval(_fTimers[sid]);_fOn[sid]=false;'
        '    btn.style.background="transparent";btn.style.color="#10b981";btn.textContent="Follow";'
        '  }else{_fOn[sid]=true;'
        '    btn.style.background="#10b981";btn.style.color="#fff";btn.textContent="Following...";'
        '    _fOffsets[sid]=0;'
        '    var pre=document.getElementById("log-pre-"+sid);'
        '    var wrap=document.getElementById("log-wrap-"+sid);'
        '    pre.innerHTML="";'
        '    _fFetch(sid,fpath,wrap,pre);'
        '    _fTimers[sid]=setInterval(function(){_fFetch(sid,fpath,wrap,pre);},2000);'
        '  }'
        '}'
        'function _fFetch(sid,fpath,wrap,pre){'
        '  var atBottom=wrap.scrollHeight-wrap.scrollTop-wrap.clientHeight<60;'
        '  fetch("' + _UTILS_BASE + '/api/log-tail?path="+encodeURIComponent(fpath)+"&offset="+(_fOffsets[sid]||0))'
        '  .then(function(r){return r.json();})'
        '  .then(function(d){'
        '    if(d.error){clearInterval(_fTimers[sid]);_fOn[sid]=false;'
        '      var b=document.getElementById("follow-btn-"+sid);'
        '      if(b){b.style.background="transparent";b.style.color="#ef4444";b.textContent="Error";}'
        '      return;}'
        '    if(d.lines&&d.lines.length){'
        '      var html=d.lines.map(_fColorLine).join("\\n");'
        '      if(pre.innerHTML)pre.innerHTML+="\\n"+html;else pre.innerHTML=html;}'
        '    _fOffsets[sid]=d.offset;'
        '    if(atBottom)wrap.scrollTop=wrap.scrollHeight;'
        '  }).catch(function(){});'
        '}'
        '</script>'
    )
    parts.append('</div></div>')  # close insp-card-body, insp-card
    return ''.join(parts)


# ── OBSD Tab ──────────────────────────────────────────────────────────────────

def _gather_obsd_html(selected_proc="", selected_file="", search_term="", time_from="", time_to=""):
    import datetime as _dt
    svc      = load_service_config()
    services = svc.get("services", {})

    procs = []
    dgm = services.get("dgserver_m", "")
    if dgm:
        procs.append(("dgm", "DGServer_M", os.path.join(dgm, "log", "maxgauge")))
    for i, dgs in enumerate(services.get("dgserver_s", [])):
        if dgs:
            procs.append(("dgs{0}".format(i + 1), "DGServer_S{0}".format(i + 1),
                          os.path.join(dgs, "log", "maxgauge")))

    if not procs:
        return _warn_box("No DGServer paths configured. Go to Configuration.")

    parts = []

    for proc_id, proc_name, log_dir in procs:
        obsd_files = []
        if os.path.isdir(log_dir):
            try:
                for f in os.listdir(log_dir):
                    if re.match(r'^obsd\d+\.log(\.zip)?$', f):
                        fp = os.path.join(log_dir, f)
                        obsd_files.append((f, os.path.getsize(fp), os.path.getmtime(fp)))
            except Exception:
                pass
        obsd_files.sort(key=lambda x: x[2], reverse=True)

        cnt      = len(obsd_files)
        badge_bg = "#6366F1" if cnt else "#94A3B8"

        parts.append('<div class="insp-card">')
        # 카드 헤더 (서버명 + 파일 개수 뱃지)
        parts.append(
            '<div class="insp-card-hdr" style="justify-content:space-between;">'
            '<div class="insp-card-title">{name}</div>'
            '<span style="background:{bg};color:#fff;font-size:.7rem;font-weight:700;'
            'padding:2px 10px;border-radius:999px;">{cnt} files</span>'
            '</div>'.format(name=proc_name, bg=badge_bg, cnt=cnt)
        )

        if not obsd_files:
            parts.append(
                '<div class="insp-card-body" style="padding:18px;color:var(--c-muted);font-size:.84rem;">'
                'OBSD 로그 파일이 없습니다.</div>'
            )
        else:
            parts.append(
                '<table style="width:100%;border-collapse:collapse;">'
                '<thead><tr style="background:#F1F5F9;">'
                '<th style="padding:8px 16px;font-size:.72rem;font-weight:700;color:#64748B;'
                'text-align:left;letter-spacing:.04em;text-transform:uppercase;">파일명</th>'
                '<th style="padding:8px 16px;font-size:.72rem;font-weight:700;color:#64748B;'
                'text-align:left;letter-spacing:.04em;text-transform:uppercase;">날짜</th>'
                '<th style="padding:8px 16px;font-size:.72rem;font-weight:700;color:#64748B;'
                'text-align:left;letter-spacing:.04em;text-transform:uppercase;">크기</th>'
                '</tr></thead><tbody>'
            )
            for i, (fname, fsize, fmtime) in enumerate(obsd_files):
                dt       = _dt.datetime.fromtimestamp(fmtime)
                date_str = dt.strftime("%Y-%m-%d %H:%M")
                if fsize < 1024:
                    size_str = "{0} B".format(fsize)
                elif fsize < 1024 * 1024:
                    size_str = "{0:.1f} KB".format(fsize / 1024)
                else:
                    size_str = "{0:.1f} MB".format(fsize / (1024 * 1024))

                row_bg   = "#ffffff" if i % 2 == 0 else "#F8FAFC"
                log_path = os.path.join(log_dir, fname).replace("'", "\\'")
                vid      = "obsdv-{pid}-{idx}".format(pid=proc_id, idx=i)

                parts.append(
                    '<tr id="obsd-row-{vid}" style="background:{bg};border-top:1px solid #F1F5F9;'
                    'cursor:pointer;transition:background .12s;" '
                    'onclick="_obsdToggle(\'{vid}\',\'{lp}\')" '
                    'onmouseover="if(!document.getElementById(\'{vid}\'))this.style.background=\'#F0F4FF\';" '
                    'onmouseout="this.style.background=\'{bg}\';">'.format(
                        vid=vid, bg=row_bg, lp=log_path)
                )
                parts.append(
                    '<td style="padding:9px 16px;">'
                    '<span style="display:inline-block;width:14px;color:#94A3B8;font-size:.7rem;'
                    'transition:transform .15s;" id="obsd-arrow-{vid}">&#9658;</span>'
                    '&nbsp;<span style="color:#6366F1;font-size:.82rem;font-weight:400;'
                    'font-family:\'JetBrains Mono\',Consolas,monospace;">{f}</span>'
                    '</td>'.format(vid=vid, f=fname)
                )
                parts.append(
                    '<td style="padding:9px 16px;font-size:.8rem;color:var(--c-muted);">'
                    '{0}</td>'.format(date_str)
                )
                parts.append(
                    '<td style="padding:9px 16px;font-size:.8rem;color:var(--c-muted);">'
                    '{0}</td>'.format(size_str)
                )
                parts.append('</tr>')
                # 뷰어 placeholder row (처음엔 숨김)
                parts.append(
                    '<tr id="{vid}" style="display:none;">'
                    '<td colspan="3" style="padding:0;border-top:none;">'
                    '<div id="{vid}-inner" style="border-top:2px solid #C7D2FE;'
                    'background:#FAFBFF;padding:14px 18px;">'
                    '<div style="color:var(--c-muted);font-size:.84rem;">Loading...</div>'
                    '</div></td></tr>'.format(vid=vid)
                )

            parts.append('</tbody></table>')

        parts.append('</div>')  # end card

    # ── JS: 토글 + 로그 fetch + 클라이언트 필터 ──
    parts.append('''<script>
var _obsdData={};
var _obsdLoaded={};
function _obsdColorLine(l){
  var e=l.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  var u=l.toUpperCase();
  if(u.indexOf("[ERROR")>=0)return"<span class=\\"log-err\\">"+e+"</span>";
  if(u.indexOf("[WARN")>=0)return"<span class=\\"log-warn\\">"+e+"</span>";
  return e;
}
function _obsdRender(vid,lines){
  var pre=document.getElementById(vid+"-pre");
  if(!pre)return;
  pre.innerHTML=lines.map(_obsdColorLine).join("\\n");
}
function _obsdFilter(vid,q){
  var lines=_obsdData[vid]||[];
  var filtered=q?lines.filter(function(l){return l.toLowerCase().indexOf(q.toLowerCase())>=0;}):lines;
  _obsdRender(vid,filtered);
  var cnt=document.getElementById(vid+"-cnt");
  if(cnt)cnt.textContent=filtered.length+" lines"+(q?" (filtered)":"");
}
function _obsdToggle(vid,logPath){
  var vrow=document.getElementById(vid);
  var arrow=document.getElementById("obsd-arrow-"+vid);
  var frow=document.getElementById("obsd-row-"+vid);
  if(!vrow)return;
  var open=vrow.style.display==="none"||vrow.style.display==="";
  // 이미 다른 row 와 달리 현재 state 로 toggle
  if(vrow.style.display!=="none"){
    vrow.style.display="none";
    if(arrow){arrow.style.transform="rotate(0deg)";arrow.style.color="#94A3B8";}
    if(frow)frow.style.background=frow.dataset.bg||"";
    return;
  }
  // 열기
  vrow.style.display="";
  if(arrow){arrow.style.transform="rotate(90deg)";arrow.style.color="#6366F1";}
  if(frow){frow.dataset.bg=frow.style.background;frow.style.background="#EEF2FF";}
  vrow.scrollIntoView({behavior:"smooth",block:"nearest"});
  if(_obsdLoaded[vid])return;
  _obsdLoaded[vid]=true;
  var inner=document.getElementById(vid+"-inner");
  if(!inner)return;
  // fetch last 1000 lines via log-tail
  fetch("''' + _UTILS_BASE + '''/api/log-tail?path="+encodeURIComponent(logPath)+"&offset=0")
    .then(function(r){return r.json();})
    .then(function(d){
      if(d.error){inner.innerHTML="<div style=\\"color:#ef4444;font-size:.83rem;\\">"+d.error+"</div>";return;}
      var lines=d.lines||[];
      _obsdData[vid]=lines;
      inner.innerHTML=[
        "<div style=\\"display:flex;align-items:center;gap:8px;margin-bottom:10px;\\">",
        "<input type=\\"text\\" placeholder=\\"Filter keywords...\\"",
        " oninput=\\"_obsdFilter('"+vid+"',this.value)\\"",
        " style=\\"flex:1;padding:6px 10px;border-radius:7px;border:1px solid var(--bd);",
        "background:var(--bg-input);color:var(--c-main);font-size:.8rem;outline:none;\\" >",
        "<span id=\\""+vid+"-cnt\\" style=\\"font-size:.72rem;color:var(--c-muted);white-space:nowrap;\\">",
        lines.length+" lines</span>",
        "</div>",
        "<div style=\\"max-height:520px;overflow-y:auto;background:var(--bg-log);",
        "border-radius:8px;padding:10px;\\">",
        "<pre id=\\""+vid+"-pre\\" style=\\"margin:0;font-family:'JetBrains Mono',monospace;",
        "font-size:11px;line-height:1.6;white-space:pre-wrap;color:var(--c-muted);\\"></pre>",
        "</div>"
      ].join("");
      _obsdRender(vid,lines);
    })
    .catch(function(){
      inner.innerHTML="<div style=\\"color:#ef4444;font-size:.83rem;\\">Network error</div>";
    });
}
</script>'''
    )

    return ''.join(parts)


def _build_param_table(parsed):
    rows = []
    for is_disabled, key, val in parsed:
        if is_disabled:
            status_label = '<span style="color:var(--c-muted);border:1px solid var(--c-dim);padding:3px 8px;border-radius:6px;font-size:0.7rem;font-weight:600;text-transform:uppercase;">Disable</span>'
            val_style    = 'color:var(--c-dim);font-family:"JetBrains Mono","Fira Code",monospace;opacity:0.7;'
            key_style    = 'color:var(--c-dim);font-weight:400;'
        else:
            status_label = '<span style="color:#10b981;border:1px solid #10b981;padding:3px 8px;border-radius:6px;font-size:0.7rem;font-weight:700;text-transform:uppercase;background:rgba(16,185,129,0.1);">Enable</span>'
            val_style    = 'color:var(--c-accent);font-family:"JetBrains Mono","Fira Code",monospace;font-weight:600;background:var(--val-bg);padding:2px 6px;border-radius:4px;'
            key_style    = 'color:var(--c-main);font-weight:500;'
        row  = '<tr class="param-row" style="border-bottom:1px solid #E5E7EB;">'
        row += '<td style="width:42%;padding:12px 8px;text-align:center;{0}font-family:\'Inter\',sans-serif;">{1}</td>'.format(key_style, key)
        row += '<td style="width:42%;padding:12px 8px;text-align:center;{0}">{1}</td>'.format(val_style, val)
        row += '<td style="width:16%;padding:12px 8px;text-align:center;">{0}</td>'.format(status_label)
        row += '</tr>'
        rows.append(row)
    if not rows:
        return _info_box("No parameters detected.")
    _hsty = 'text-align:center;padding:10px 8px;font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.03em;color:#5F6B80;cursor:pointer;user-select:none;border-bottom:1px solid #D8DEE8;'
    t  = '<table class="svc-table" style="table-layout:fixed;width:100%;border-collapse:collapse;border:none;">'
    t += '<thead style="position:sticky;top:0;z-index:3;"><tr style="background:transparent;">'
    t += '<th class="sortable" onclick="tbSort(this)" style="width:42%;' + _hsty + '">Parameter<span class="sort-ic"></span></th>'
    t += '<th class="sortable" onclick="tbSort(this)" style="width:42%;' + _hsty + '">Value<span class="sort-ic"></span></th>'
    t += '<th class="sortable" onclick="tbSort(this)" style="width:16%;' + _hsty + '">Status<span class="sort-ic"></span></th>'
    t += '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>'
    return t


def _parse_param_data():
    svc      = load_service_config()
    services = svc.get("services", {})
    homes    = []

    dgm = services.get("dgserver_m", "")
    if dgm:
        homes.append(("DGServer_M", dgm))

    for i, dgs in enumerate(services.get("dgserver_s", [])):
        if dgs:
            homes.append(("DGServer_S" + str(i + 1), dgs))

    if not homes:
        return _warn_box("No DGServer paths configured. Go to Configuration.")

    # Allow optional attributes in opening tag, e.g. <database_sid service="false">PGN</database_sid>
    RE_PARAM = re.compile(r"<(\w+)(?:\s[^>]*)?>([^<]+)</\1>")
    all_data = []
    for name, home in homes:
        xmlfile = os.path.join(home, "conf", "DGServer.xml")
        safe_id = re.sub(r'[^a-z0-9]', '', name.lower())
        if not os.path.exists(xmlfile):
            all_data.append((name, xmlfile, safe_id, [], "설정 파일을 찾을 수 없습니다: " + xmlfile))
        else:
            try:
                lines  = _read_lines(xmlfile)
                parsed = []
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    m = RE_PARAM.search(line)
                    if m:
                        comment_pos = line.find("<!--")
                        is_disabled = (comment_pos >= 0 and comment_pos < m.start())
                        parsed.append((is_disabled, m.group(1), m.group(2)))
                parsed.sort(key=lambda r: 1 if r[0] else 0)
                all_data.append((name, xmlfile, safe_id, parsed, None))
            except Exception as e:
                all_data.append((name, xmlfile, safe_id, [], "파일 읽기 오류: " + str(e)))

    return all_data


def _gather_param_html(active_tab="search"):
    all_data = _parse_param_data()
    if isinstance(all_data, str):
        return all_data

    b       = _UTILS_BASE + "/process/param"
    all_ids = ["search"] + [d[2] for d in all_data]
    if active_tab not in all_ids:
        active_tab = "search"

    TAB_BASE   = ('padding:4px 11px;border-radius:14px;font-size:0.76rem;font-weight:600;'
                  'margin:0;text-decoration:none;white-space:nowrap;text-align:center;'
                  'box-sizing:border-box;display:inline-block;line-height:1.6;')
    TAB_IDLE   = TAB_BASE + 'background:#F1F5F9;color:#64748B;border:1px solid #E2E8F0;cursor:pointer;'
    TAB_ACTIVE = TAB_BASE + 'background:#EEF2FF;color:#4338CA;border:1.5px solid #6366F1;cursor:default;'

    parts = []

    parts.append(
        '<script>'
        'function filterParamSearch(){'
        'var v=document.getElementById("paramSearchInput").value.toUpperCase().trim();'
        'document.querySelectorAll(".psearch-group").forEach(function(g){'
        'if(!v){g.style.display="none";return;}'
        'var cnt=0;'
        'g.querySelectorAll(".param-row").forEach(function(r){'
        'if(r.textContent.toUpperCase().indexOf(v)>-1){r.style.display="";cnt++;}else{r.style.display="none";}'
        '});'
        'g.style.display=cnt>0?"block":"none";'
        '});}'
        '</script>'
    )

    parts.append('<div style="display:flex;flex-wrap:wrap;gap:5px;padding-bottom:10px;'
                 'margin-bottom:16px;border-bottom:1px solid var(--bd);">')
    s = TAB_ACTIVE if active_tab == "search" else TAB_IDLE
    parts.append('<a href="%s?tab=search" style="%s">Search</a>' % (b, s))
    for name, xmlfile, safe_id, parsed, error in all_data:
        s = TAB_ACTIVE if active_tab == safe_id else TAB_IDLE
        parts.append('<a href="%s?tab=%s" style="%s">%s</a>' % (b, safe_id, s, name))
    parts.append('</div>')

    if active_tab == "search":
        # 검색 영역(검색 input + Modify 버튼)은 카드 밖 상단에
        parts.append(
            '<div style="display:flex;gap:8px;margin-bottom:16px;">'
            '<div style="position:relative;flex:1;">'
            '<input type="text" id="paramSearchInput" oninput="filterParamSearch();_paramXToggle();" '
            'placeholder="Search parameters across all gathers..." '
            'style="width:100%;padding:8px 28px 8px 12px;border-radius:8px;border:1px solid var(--bd);'
            'background:var(--bg-input);color:var(--c-main);font-size:.84rem;outline:none;box-sizing:border-box;">'
            '<span id="param-x" onclick="document.getElementById(\'paramSearchInput\').value=\'\';filterParamSearch();_paramXToggle();"'
            ' style="display:none;position:absolute;right:10px;top:50%;transform:translateY(-50%);'
            'cursor:pointer;color:#94A3B8;font-size:.85rem;line-height:1;padding:2px;"'
            ' onmouseover="this.style.color=\'#334155\'" onmouseout="this.style.color=\'#94A3B8\'"'
            '>&#x2715;</span>'
            '</div>'
            '<button onclick="_openModifyPanel()" style="padding:8px 18px;border-radius:8px;border:1px solid #6366F1;color:#6366F1;background:transparent;font-size:.84rem;font-weight:600;cursor:pointer;white-space:nowrap;transition:all .15s;font-family:Inter,Pretendard,sans-serif;" onmouseover="this.style.background=\'#6366F1\';this.style.color=\'#fff\'" onmouseout="this.style.background=\'transparent\';this.style.color=\'#6366F1\'">Modify</button>'
            '</div>'
            '<script>'
            'function _paramXToggle(){'
            'var x=document.getElementById("param-x");if(!x)return;'
            'x.style.display=document.getElementById("paramSearchInput").value?"":"none";'
            '}'
            '</script>'
        )
        # 검색 결과 그룹은 각각 사각 .insp-card 다중 (검색 시에만 표시)
        for name, xmlfile, safe_id, parsed, error in all_data:
            parts.append('<div class="psearch-group insp-card" style="display:none;">')
            parts.append('<div class="insp-card-hdr">')
            parts.append('<div class="insp-card-title">' + name + '</div>')
            parts.append('</div>')
            parts.append('<div class="insp-card-body">')
            if error:
                parts.append('<div style="padding:14px 16px;">' + _warn_box(error) + '</div>')
            else:
                parts.append(_build_param_table(parsed))
            parts.append('</div></div>')
        from pages.dgxml_modify import modify_panel_html as _mphtml
        parts.append(_mphtml())
    else:
        for name, xmlfile, safe_id, parsed, error in all_data:
            if safe_id != active_tab:
                continue
            parts.append('<div class="insp-card">')
            parts.append('<div class="insp-card-body">')
            if error:
                parts.append('<div style="padding:14px 16px;">' + _warn_box(error) + '</div>')
            else:
                parts.append('<div style="max-height:calc(100vh - 260px);overflow-y:auto;overflow-x:hidden;">')
                parts.append(_build_param_table(parsed))
                parts.append('</div>')
            parts.append('</div></div>')
            parts.append('<div style="position:fixed;bottom:30px;right:24px;z-index:50;'
                         'font-size:.68rem;color:#94A3B8;letter-spacing:.02em;">'
                         'Source: ' + xmlfile + '</div>')
            break

    return "".join(parts)



def api_log_tail(log_path_str, offset_str):
    import json
    try:
        offset = int(offset_str or '0')
        if not log_path_str or not os.path.exists(log_path_str):
            return json.dumps({"error": "file not found"})
        fsize = os.path.getsize(log_path_str)
        if offset == 0:
            proc = subprocess.Popen(
                ['tail', '-n', '300', log_path_str],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
            )
            stdout, _ = proc.communicate()
            raw_lines = stdout.splitlines() if stdout else []
            return json.dumps({"lines": raw_lines, "offset": fsize})
        else:
            if offset > fsize:
                offset = 0
            with open(log_path_str, 'r', errors='replace') as f:
                f.seek(offset)
                chunk = f.read()
                new_offset = f.tell()
            raw_lines = chunk.splitlines() if chunk.strip() else []
            return json.dumps({"lines": raw_lines, "offset": new_offset})
    except Exception as e:
        import json as _j
        return _j.dumps({"error": str(e)})


def page_process_gather(path=""):
    active_tab    = "overview"
    selected_file = ""
    search_term   = ""
    time_from     = ""
    time_to       = ""
    selected_proc = ""
    if "?" in path:
        for part in path.split("?", 1)[1].split("&"):
            if part.startswith("tab="):
                active_tab = unquote(part[4:])
            elif part.startswith("file="):
                selected_file = unquote(part[5:])
            elif part.startswith("search="):
                search_term = unquote_plus(part[7:])
            elif part.startswith("time_from="):
                time_from = unquote(part[10:]).strip()
            elif part.startswith("time_to="):
                time_to = unquote(part[8:]).strip()
            elif part.startswith("proc="):
                selected_proc = unquote(part[5:])

    svc       = load_service_config()
    log_paths = svc.get("log_paths", {})

    tabs = [("overview", "Overview", None), ("obsd", "OBSD", None)]
    dgm_log = log_paths.get("dgserver_m", "")
    if dgm_log:
        tabs.append(("dgm", "DGServer_M", dgm_log))
    for i, dgs_log in enumerate(log_paths.get("dgserver_s", [])):
        if dgs_log:
            tabs.append(("dgs{0}".format(i + 1), "DGServer_S{0}".format(i + 1), dgs_log))

    all_ids = [t[0] for t in tabs]
    if active_tab not in all_ids:
        active_tab = "overview"

    TAB_BASE   = ('padding:4px 11px;border-radius:14px;font-size:0.76rem;font-weight:600;'
                  'margin:0;text-decoration:none;white-space:nowrap;text-align:center;'
                  'box-sizing:border-box;display:inline-block;line-height:1.6;')
    TAB_IDLE   = TAB_BASE + 'background:#F1F5F9;color:#64748B;border:1px solid #E2E8F0;cursor:pointer;'
    TAB_ACTIVE = TAB_BASE + 'background:#EEF2FF;color:#4338CA;border:1.5px solid #6366F1;cursor:default;'

    b     = _UTILS_BASE + "/process/gather"
    parts = []

    parts.append('<div style="display:flex;flex-wrap:wrap;gap:5px;padding-bottom:10px;'
                 'margin-bottom:16px;border-bottom:1px solid var(--bd);">')
    for tab_id, label, _ in tabs:
        s = TAB_ACTIVE if active_tab == tab_id else TAB_IDLE
        parts.append('<a href="%s?tab=%s" style="%s">%s</a>' % (b, tab_id, s, label))
    parts.append('</div>')

    if active_tab == "overview":
        parts.append(_gather_log_html())
    elif active_tab == "obsd":
        parts.append(_gather_obsd_html(selected_proc, selected_file, search_term, time_from, time_to))
    else:
        for tab_id, label, log_dir in tabs:
            if tab_id != active_tab:
                continue
            parts.append(_gather_log_server_html(log_dir, tab_id, selected_file, search_term, time_from, time_to))
            break

    body = ''.join([
        _page_title_html('Gather Log', *_HELP.get('gather_log', ('Gather Log', ''))),
        ''.join(parts),
        _ts(),
    ])
    return _page('process_gather', 'Gather Log', body, topbar_help_key='gather_log')


def page_process_param(path=""):
    active_tab = "search"
    if "?" in path:
        for part in path.split("?", 1)[1].split("&"):
            if part.startswith("tab="):
                active_tab = part[4:]
                break
    body = ''.join([
        _gather_param_html(active_tab),
        _ts(),
    ])
    return _page('process_param', 'Parameter', body,
                 topbar=True, topbar_title='Parameter', topbar_help_key='process_param')
