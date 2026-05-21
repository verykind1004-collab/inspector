# -*- coding: utf-8 -*-
import json

from db_utils import _parse_db_table, _sql_embed

# UTILS_BASE and PLATFORMJS_PORT injected at startup
_UTILS_BASE      = ""
_PLATFORMJS_PORT = 18081

def set_globals(utils_base, platformjs_port):
    global _UTILS_BASE, _PLATFORMJS_PORT
    _UTILS_BASE      = utils_base
    _PLATFORMJS_PORT = platformjs_port


# ── Page title localization (Korean) ──────────────────────────────────────────
# 페이지 상단 탭 제목만 한글화. 사이드바 메뉴 라벨은 영문 그대로 유지.
_KR_TITLE = {
    # Overview
    'Overview':                          '오버뷰',
    'Services':                          '서비스',
    # Instance / License
    'Instance List':                     '인스턴스 목록',
    'License Check':                     '라이선스 확인',
    # Partition
    'Partition Create Check':            '파티션 생성 확인',
    'Partition Drop Check':              '파티션 삭제 확인',
    'Partition Time Check':              '파티션 시간 확인',
    # Summary
    '10Min Summary Check':               '10분 Summary 확인',
    '1Hour Summary Check':               '1시간 Summary 확인',
    '10Min Summary History':             '10분 Summary 이력',
    '1Hour Summary History':             '1시간 Summary 이력',
    # Process
    'Gather Log':                        'Gather 로그',
    'Parameter':                         '파라미터',
    # Disk
    'Capacity Check':                    '용량 확인',
    'Vacuum/Age Check':                  'Vacuum/Age 확인',
    'Auto-Vacuum Check (tables pending manual vacuum)':
                                         'Auto-Vacuum 확인 (수동 Vacuum 대기 테이블)',
    'Age Check':                         'Age 확인',
    'Top Segment':                       '상위 Segment',
    'Temp Table':                        '임시 테이블',
    # Others
    'Session Check':                     '세션 확인',
    'Query Check':                       '쿼리 확인',
    'Alert Check':                       '알람 확인',
    'Alarm Send History':                '알람 발송 이력',
    # Tools / etc
    'Configuration':                     '환경 설정',
    # History
    'CPU Usage History':                 'CPU 사용량 이력',
    'Memory Usage History':              '메모리 사용량 이력',
    'Disk Usage History':                '디스크 사용량 이력',
    'Tablespace Usage History':          'Tablespace 사용량 이력',
    'Disk / TBS History':                '디스크 / TBS 이력',
    'Service Status History':            '서비스 상태 이력',
    'Qcnt Trend':                        'Qcnt 추이',
    'Heap Trend':                        'Heap 추이',
    'History Configuration':             'History 환경 설정',
}

def _kr_title(t):
    if not t:
        return t
    return _KR_TITLE.get(t, t)


# ── badge / bar / icon helpers ──────────────────────────────────────────────────

def _badge(status, text=None):
    _styles = {
        "ok":           ("#dcfce7", "#15803d", "#bbf7d0", "badge-ok"),
        "running":      ("#dcfce7", "#15803d", "#bbf7d0", "badge-ok"),
        "warning":      ("#fef3c7", "#92400e", "#fde68a", "badge-warn"),
        "waiting":      ("#fef3c7", "#92400e", "#fde68a", "badge-warn"),
        "critical":     ("#fee2e2", "#dc2626", "#fecaca", "badge-crit"),
        "stopped":      ("#fee2e2", "#dc2626", "#fecaca", "badge-crit"),
        "unconfigured": ("#f1f5f9", "#64748b", "#e2e8f0", "badge-muted"),
        "off":           ("#f1f5f9", "#94a3b8", "#e2e8f0", "badge-muted"),
    }
    bg, color, border, cls = _styles.get(status.lower(), ("#fee2e2", "#dc2626", "#fecaca", "badge-crit"))
    t = text or status.upper()
    style = (
        "background:%s;color:%s;border:1px solid %s;"
        "padding:2px 10px;border-radius:9999px;"
        "font-size:0.75rem;font-weight:600;"
        "display:inline-block;line-height:1.2;"
        "text-align:center;min-width:32px;"
    ) % (bg, color, border)
    return '<span class="badge %s" style="%s">%s</span>' % (cls, style, t)


def _svc_icon(status):
    s = status.lower()
    if s in ("running", "ok"):
        return '<span style="color:#22c55e; font-size:1.1rem; font-weight:bold;">&#10003;</span>'
    elif s == "unconfigured":
        return '<span style="color:#64748b; font-size:1.1rem;">&#8212;</span>'
    return '<span style="color:#ef4444; font-size:1.1rem; font-weight:bold;">&#10007;</span>'



def _bar_dyn(pct, status):
    """Like _bar() but adds data-bar-pct for client-side threshold updates."""
    colors = {"ok": "#22c55e", "warning": "#eab308", "critical": "#ef4444"}
    c = colors.get(status.lower(), "#ef4444")
    return (
        '<div style="margin-top:15px; width:100%%;">'
        '  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">'
        '    <span style="color:#94a3b8; font-size:0.75rem;">Usage</span>'
        '    <span style="color:#94a3b8; font-size:0.85rem;">%s%%</span>'
        '  </div>'
        '  <div class="bar-wrap" style="width:100%%; height:6px; border-radius:3px; overflow:hidden; margin:0; flex:none;">'
        '    <div data-bar-pct="%s" style="width:%s%%; background:%s; height:100%%; border-radius:3px;"></div>'
        '  </div>'
        '</div>'
    ) % (pct, pct, pct, c)


def _warn_box(msg):
    return '<div class="alert-box alert-warn">%s</div>' % msg


def _info_box(msg):
    style = ("padding:12px 16px; border-radius:8px; margin:10px 0; "
             "background:#3b82f615; border:1px solid #3b82f630; color:#3b82f6; font-size:0.9rem;")
    return '<div style="%s">%s</div>' % (style, msg)


def _ts():
    # Generated 타임스탬프 표시 제거 (모든 페이지 우하단). 호출처는 그대로 두고
    # 이 함수만 빈 문자열 반환.
    return ''


# ── table renderers ──────────────────────────────────────────────────────────────

def _render_db_table_html(headers, rows):
    if not headers and not rows:
        return '<p style="color:#94a3b8; font-size:0.85rem; padding:8px 0">조회 결과가 없습니다.</p>'

    idx_delay      = -1
    status_indices = []

    for i, h in enumerate(headers):
        h_up = h.upper()
        if 'STATUS' in h_up:
            status_indices.append(i)
        if h_up == 'DELAY_INFO':
            idx_delay = i

    def _cell(v, i, row):
        uv = str(v).upper().strip()
        is_status_col  = i in status_indices
        status_keywords = ('OK', 'CHECK', 'ERROR', 'INVALID', 'FAIL', 'FAILED', 'DOWN',
                           'WARNING', 'WARN', 'VALID', 'WAITING', 'RUNNING', 'STOPPED', 'OFF')
        is_status_value = uv in status_keywords

        if is_status_col or is_status_value:
            delay = ""
            if headers[i].upper() == 'STATUS' and idx_delay != -1 and idx_delay < len(row):
                delay = row[idx_delay] if row[idx_delay] else ""
            badge_html = ""
            if uv in ('OK', 'RUNNING'):
                badge_html = _badge("ok", v)
            elif uv in ('CHECK', 'ERROR', 'INVALID', 'FAIL', 'FAILED', 'DOWN', 'CRITICAL', 'STOPPED'):
                badge_html = _badge("critical", v)
            elif uv in ('WARNING', 'WARN', 'VALID'):
                badge_html = _badge("warning", v)
            elif uv == 'WAITING':
                badge_html = _badge("waiting", v)
            elif uv == 'OFF':
                badge_html = _badge("off", v)
            else:
                return '<td>%s</td>' % v
            if delay:
                return '<td>%s <span style="color:#94a3b8; font-size:0.8rem; margin-left:5px; font-weight:bold;">%s</span></td>' % (badge_html, delay)
            return '<td>%s</td>' % badge_html
        return '<td>%s</td>' % v

    visible_headers = [h for h in headers if h.upper() != 'DELAY_INFO']
    th_cells = ''.join('<th class="sortable" onclick="tbSort(this)">%s<span class="sort-ic"></span></th>' % h.replace('_', ' ').upper() for h in visible_headers)

    tr_rows = ''
    for row in rows:
        row_list  = list(row)
        while len(row_list) < len(headers):
            row_list.append('')
        cells_html = []
        for i, val in enumerate(row_list):
            if i < len(headers) and headers[i].upper() != 'DELAY_INFO':
                cells_html.append(_cell(val, i, row_list))
        tr_rows += '<tr>' + ''.join(cells_html) + '</tr>'

    return (
        '<div class="tbl-wrap">'
        '<table class="svc-table">'
        '<thead><tr>%s</tr></thead>'
        '<tbody>%s</tbody>'
        '</table>'
        '</div>'
    ) % (th_cells, tr_rows)


def _query_card(title, out, err):
    title_html = '<div class="card-title">' + title + '</div>' if title else ''
    if err:
        return '<div class="card">' + title_html + _warn_box(err) + '</div>'
    headers, rows = _parse_db_table(out or "")
    content = _render_db_table_html(headers, rows)
    return '<div class="card">' + title_html + content + '</div>'


# ── CSS ───────────────────────────────────────────────────────────────────────────

_CSS = (
    # ── CSS variables (light mode) ──────────────────────────────────────────
    ":root{--bg-main:#F9FAFB;--bg-card:#ffffff;--bg-input:#ffffff;"
    "--bg-log:#F3F4F6;--bd:#E5E7EB;--bd-card:transparent;--c-main:#0F172A;--c-muted:#64748B;"
    "--c-dim:#94A3B8;--c-accent:#6366F1;--tab-act-bg:#ffffff;--tab-idle-bg:#F1F5F9;--val-bg:#EEF2FF;"
    "--ok-bg:#F0FDF4;--ok-bd:rgba(22,163,74,.2);--ok-c:#15803D;"
    "--err-bg:#FEF2F2;--err-bd:rgba(220,38,38,.2);--err-c:#DC2626;"
    "--err-log-bg:#FEF2F2;--err-log-bd:rgba(220,38,38,.15);--err-log-c:#DC2626}"
    # ── Base reset ───────────────────────────────────────────────────────────
    "*{box-sizing:border-box;margin:0;padding:0}"
    "html,body{height:100%;font-family:'Pretendard','Inter','Segoe UI',-apple-system,BlinkMacSystemFont,sans-serif;background:#F9FAFB;color:#0F172A;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;letter-spacing:-0.01em}"
    "button,input,select,textarea{font-family:inherit;letter-spacing:inherit}"
    "a{color:inherit;text-decoration:none}"
    # ── Layout ───────────────────────────────────────────────────────────────
    ".layout{display:flex;min-height:100vh}"
    ".sidebar{width:220px;background:#1E293B;border-right:none;"
    "box-shadow:2px 0 16px rgba(15,23,42,.15);"
    "display:flex;flex-direction:column;position:fixed;top:0;left:0;height:100vh;overflow-y:auto;z-index:300}"
    ".main{margin-left:220px;flex:1;padding:0;min-height:100vh}"
    ".content-wrap{padding:32px 36px 48px;}"
    # ── Sidebar brand ────────────────────────────────────────────────────────
    ".sb-brand{padding:20px 16px 18px;font-size:.95rem;font-weight:800;color:#F1F5F9;"
    "border-bottom:1px solid rgba(255,255,255,.08);letter-spacing:.02em;"
    "display:flex;align-items:center;gap:10px;}"
    ".sb-brand-icon{width:28px;height:28px;border-radius:8px;"
    "background:linear-gradient(135deg,#6366F1,#8B5CF6);display:flex;"
    "align-items:center;justify-content:center;flex-shrink:0;"
    "box-shadow:0 3px 10px rgba(99,102,241,.4);}"
    ".sb-brand-text{display:flex;flex-direction:column;line-height:1.1;}"
    ".sb-brand-text span:first-child{font-size:.92rem;font-weight:800;"
    "background:linear-gradient(135deg,#C7D2FE,#E0E7FF);-webkit-background-clip:text;"
    "-webkit-text-fill-color:transparent;background-clip:text;}"
    ".sb-brand-text span:last-child{font-size:.6rem;font-weight:600;color:#818CF8;"
    "letter-spacing:.12em;text-transform:uppercase;margin-top:2px;}"
    # ── Nav labels & items ───────────────────────────────────────────────────
    ".nav-lbl{padding:14px 16px 5px;font-size:.63rem;font-weight:800;"
    "text-transform:uppercase;letter-spacing:.14em;color:#94A3B8;transition:all .18s;}"
    ".nav-lbl.nav-open{color:#C7D2FE;background:rgba(99,102,241,.1);"
    "margin:2px 8px;padding:10px 14px 6px;border-radius:8px 8px 0 0;}"
    ".nav-item{display:block;padding:9px 14px;margin:2px 8px;border-radius:10px;"
    "font-size:.84rem;color:#CBD5E1;transition:all .18s;background:transparent;}"
    ".nav-item:hover{background:rgba(255,255,255,.08);color:#F8FAFC}"
    ".nav-item.active{"
    "background:linear-gradient(135deg,#6366F1,#8B5CF6);"
    "color:#fff;font-weight:700;letter-spacing:.01em;"
    "box-shadow:0 4px 15px rgba(99,102,241,.4),0 0 0 1px rgba(139,92,246,.3);"
    "text-shadow:0 1px 2px rgba(0,0,0,.15);}"
    ".nav-sub{display:block;padding:7px 14px 7px 28px;margin:1px 8px;border-radius:8px;"
    "font-size:.8rem;color:#94A3B8;transition:all .18s;background:transparent;}"
    ".nav-sub:hover{background:rgba(255,255,255,.08);color:#E2E8F0}"
    ".nav-sub.active{"
    "background:linear-gradient(135deg,rgba(99,102,241,.85),rgba(139,92,246,.7));"
    "color:#fff;font-weight:600;"
    "box-shadow:0 3px 10px rgba(99,102,241,.3);}"
    ".nav-divider{border:none;border-top:1px solid rgba(255,255,255,.07);margin:5px 0}"
    ".nav-bottom{margin-top:auto;border-top:1px solid rgba(255,255,255,.07);padding:4px 0 8px}"
    # ── Cards ────────────────────────────────────────────────────────────────
    # [DESIGN-A] border-radius:14px → 0, border #E2E8F0 → #CBD5E1
    # (Inspector Overview 의 .insp-card 톤과 통일). 롤백 시 14px / #E2E8F0 복원.
    ".card{background:#ffffff;border:1px solid #CBD5E1;border-radius:0;"
    "padding:28px 26px;margin-bottom:20px;"
    "box-shadow:0 1px 3px rgba(15,23,42,.04),0 4px 16px rgba(15,23,42,.03)}"
    # Metric strip: 3px 두께로 위쪽 외곽선만 색 덮어씀 (없으면 기본 1px #E2E8F0 유지)
    ".card.metric-neutral,.card.metric-ok,.card.metric-warning,.card.metric-critical{border-top-width:3px}"
    # Status color strip on top of metric cards (Overview)
    ".card.metric-neutral{border-top-color:#cbd5e1}"
    ".card.metric-ok{border-top-color:#22c55e}"
    ".card.metric-warning{border-top-color:#f59e0b}"
    ".card.metric-critical{border-top-color:#ef4444}"
    ".card-title{font-size:.74rem;font-weight:700;text-transform:uppercase;"
    "letter-spacing:.08em;color:#6366F1;margin-bottom:18px;padding-bottom:10px;"
    "border-bottom:1px solid #F1F5F9;font-family:'Inter','Pretendard',sans-serif}"
    # ── Inner tbl-wrap inside card: subtle, no double-box ────────────────
    # [DESIGN-A] border-radius:10px → 0 (외곽 .card 와 톤 일치). 롤백 시 10px.
    ".card .tbl-wrap{border:1px solid #CBD5E1;border-radius:0;box-shadow:none;"
    "background:#F8FAFC;overflow:hidden}"
    # ── Grid & layout helpers ────────────────────────────────────────────────
    ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px;margin-bottom:20px}"
    ".row{display:flex;justify-content:space-between;align-items:center;margin-bottom:11px;font-size:.88rem}"
    ".lbl{color:#64748B}.val{font-weight:700;color:#0F172A}"
    ".badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.75rem;font-weight:600}"
    ".bar-wrap{background:#E2E8F0;border-radius:999px;height:5px;flex:1;margin:0 10px;overflow:hidden}"
    ".bar{height:100%;border-radius:999px}"
    ".info-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}"
    ".il .ilbl{font-size:.72rem;color:#94A3B8;margin-bottom:2px}"
    ".il .ival{font-size:.88rem;font-weight:600;color:#0F172A}"
    # ── Typography ───────────────────────────────────────────────────────────
    ".page-title{font-size:1.5rem;font-weight:800;color:#0F172A;margin-bottom:4px}"
    ".page-sub{font-size:.8rem;color:#64748B;margin-bottom:24px;margin-top:4px}"
    ".page-hdr{display:none;}"
    # ── Help button & tooltip ────────────────────────────────────────────────
    ".help-btn{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;"
    "border-radius:50%;border:1.5px solid #9CA3AF;background:transparent;color:#9CA3AF;"
    "cursor:pointer;flex-shrink:0;transition:border-color .15s,color .15s;user-select:none;padding:0;"
    "font-size:10px;font-weight:700;font-style:normal;font-family:Inter,Pretendard,sans-serif;line-height:1;}"
    ".help-btn:hover{border-color:#6366F1;color:#6366F1;}"
    ".help-tip{display:none;position:fixed;z-index:9999;max-width:800px;background:#ffffff;"
    "border:1px solid #e5e7eb;border-radius:12px;box-shadow:0 12px 32px rgba(0,0,0,.18);"
    "padding:16px 20px;pointer-events:none;}"
    ".help-tip-title{font-size:.72rem;font-weight:700;text-transform:uppercase;"
    "letter-spacing:.08em;color:#6366F1;margin-bottom:10px;}"
    ".help-tip-body{font-size:.82rem;color:#374151;line-height:1.7;}"
    ".help-tip-body li{margin-bottom:4px;margin-left:14px;list-style:disc;}"
    ".help-tip-body b{color:#1f2937;font-weight:800;font-size:.83rem;}"
    # ── Table wrapper & table ────────────────────────────────────────────────
    ".tbl-wrap{overflow-x:auto;border-radius:10px;border:1px solid #E5E7EB;overflow:hidden}"
    ".svc-table{width:100%;border-collapse:collapse;font-size:.83rem;min-width:500px;}"
    ".svc-table thead{position:sticky;top:0;z-index:2;}"
    ".svc-table th{text-align:center;padding:16px 18px;font-size:.72rem;font-weight:700;"
    "text-transform:uppercase;letter-spacing:.04em;white-space:nowrap;"
    "background:#ECF0F7;color:#5F6B80;"
    "border-bottom:1px solid #D8DEE8;border-right:1px solid #DFE4ED;}"
    ".svc-table th:last-child{border-right:none;}"
    ".svc-table td{padding:16px 18px;color:#4B5563;vertical-align:middle;text-align:center;"
    "border-bottom:1px solid #E5E7EB;border-right:1px solid #EBEDF1;}"
    ".svc-table td:last-child{border-right:none;}"
    ".svc-table td strong{color:#2D3748;font-weight:700;}"
    ".svc-table tbody tr:nth-child(odd){background:#ffffff}"
    ".svc-table tbody tr:nth-child(even){background:#F9FAFB}"
    ".svc-table tbody tr{transition:background .15s}"
    ".svc-table tbody tr:hover td{background:#E8EDFA!important;color:#0F172A;}"
    ".svc-table tr:last-child td{border-bottom:none;}"
    # ── Query output ─────────────────────────────────────────────────────────
    ".query-out{background:#F8FAFC;border:none;border-radius:8px;padding:16px;"
    "font-family:'Consolas','Monaco',monospace;font-size:.8rem;white-space:pre;overflow-x:auto;"
    "color:#334155;line-height:1.6}"
    # ── Status text colors ───────────────────────────────────────────────────
    ".clr-ok{color:#15803D;font-weight:600}.clr-chk{color:#DC2626;font-weight:600}"
    ".clr-wait{color:#B45309;font-weight:600}"
    ".log-err{color:#DC2626;font-weight:500}.log-warn{color:#B45309;font-weight:500}"
    # ── Alert boxes ──────────────────────────────────────────────────────────
    ".alert-box{padding:12px 16px;border-radius:8px;margin-bottom:12px;font-size:.88rem}"
    ".alert-warn{background:#FEF9EE;border:1px solid rgba(217,119,6,.12);color:#92400E}"
    ".alert-info{background:#F0F2FF;border:1px solid rgba(99,102,241,.12);color:#4338CA}"
    # ── Misc ─────────────────────────────────────────────────────────────────
    ".ts{font-size:.75rem;color:#64748b;margin-top:12px}"
    ".banner{background:#F0FDF4;color:#15803D;padding:10px 16px;border-radius:8px;"
    "margin-bottom:16px;font-size:.88rem;border:1px solid rgba(22,163,74,.15)}"
    # ── Form fields ──────────────────────────────────────────────────────────
    ".field-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}"
    ".field{display:flex;flex-direction:column;gap:5px}"
    ".field label{font-size:.82rem;color:#475569;font-weight:600}"
    ".inp{background:#ffffff;border:1px solid #B0BAC9;border-radius:8px;padding:8px 12px;"
    "color:#0F172A;font-size:.88rem;width:100%}"
    ".inp:focus{outline:none;border-color:#6366F1;background:#fff;box-shadow:0 0 0 2px rgba(99,102,241,.08)}"
    "select.inp{cursor:pointer}"
    ".path-field{display:flex;flex-direction:column;gap:5px;margin-bottom:10px}"
    ".path-field label{font-size:.82rem;color:#475569;font-weight:600}"
    ".dgs-row{display:flex;gap:8px;margin-bottom:8px;align-items:center}"
    ".dgs-row .inp{flex:1}"
    # ── Buttons ──────────────────────────────────────────────────────────────
    ".btn-icon{background:#F1F5F9;border:none;color:#64748B;border-radius:7px;"
    "width:32px;height:32px;cursor:pointer;font-size:1rem;flex-shrink:0;transition:all .15s}"
    ".btn-icon:hover{background:#E2E8F0;color:#0F172A}"
    ".btn-add{background:#EEF2FF;border:1px solid #6366F1;color:#4F46E5;border-radius:8px;"
    "padding:6px 14px;font-size:.82rem;font-weight:600;cursor:pointer;margin-top:4px;transition:all .15s}"
    ".btn-add:hover{background:#E0E7FF}"
    ".btn-save{background:#6366F1;border:none;color:#fff;border-radius:10px;"
    "padding:10px 32px;font-size:.92rem;font-weight:600;cursor:pointer;margin-top:8px;"
    "box-shadow:0 4px 14px rgba(99,102,241,.35);transition:all .15s}"
    ".btn-save:hover{background:#4F46E5;box-shadow:0 6px 18px rgba(99,102,241,.42)}"
    ".ts{color:#94A3B8}"
    # ── Scrollbar ────────────────────────────────────────────────────────────
    "::-webkit-scrollbar{width:5px;height:5px}"
    "::-webkit-scrollbar-track{background:transparent}"
    "::-webkit-scrollbar-thumb{background:#CBD5E1;border-radius:999px}"
    "::-webkit-scrollbar-thumb:hover{background:#6366F1}"
    "*{scrollbar-width:thin;scrollbar-color:#CBD5E1 transparent}"
    "@keyframes spin{to{transform:rotate(360deg)}}"
    "@keyframes _fadeUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}"
    ".page-hdr{animation:_fadeUp .25s cubic-bezier(.22,.68,0,1.2) both}"
    ".card{animation:_fadeUp .3s cubic-bezier(.22,.68,0,1.2) both}"
    ".tbl-wrap{animation:_fadeUp .3s cubic-bezier(.22,.68,0,1.2) .05s both}"
    # ── Freeze button ────────────────────────────────────────────────────────
    ".btn-freeze{float:right;margin-left:12px;padding:4px 14px;border-radius:20px;"
    "background:transparent;border:1px solid rgba(99,102,241,.5);color:#6366F1;font-size:.78rem;"
    "font-weight:600;cursor:pointer;letter-spacing:.03em;transition:all .2s;"
    "font-family:'Inter','Pretendard',-apple-system,sans-serif;}"
    ".btn-freeze:hover{background:#6366F1;color:#fff;border-color:#6366F1}"
    ".btn-freeze-running{background:#6366F1!important;color:#fff!important;"
    "pointer-events:none;opacity:.8}"
    ".btn-freeze-done{border-color:#22c55e!important;color:#22c55e!important;"
    "background:transparent!important;pointer-events:none}"
    ".btn-freeze-err{border-color:#ef4444!important;color:#ef4444!important;"
    "background:transparent!important}"
    # ── Misc interactive ─────────────────────────────────────────────────────
    ".ov-cfg-btn{background:none;border:none;cursor:pointer;color:#64748b;line-height:1;"
    "padding:3px 4px;border-radius:4px;transition:color .2s;display:inline-flex;align-items:center;}"
    ".ov-cfg-btn:hover{color:#6366F1;}"
    ".svc-refresh-btn{background:none;border:none;cursor:pointer;color:var(--c-dim);"
    "font-size:1.1rem;padding:2px 6px;border-radius:4px;line-height:1;transition:color .2s}"
    ".svc-refresh-btn:hover{color:var(--c-accent)}"
    ".svc-table th.sortable{cursor:pointer;user-select:none;white-space:nowrap}"
    ".svc-table th.sortable:hover{color:var(--c-accent)}"
    ".sort-ic{font-size:.7em;margin-left:3px;opacity:.45}"
    ".svc-refresh-btn.spinning{animation:spin .6s linear infinite;pointer-events:none}"
    # ── Badge overrides ─────────────────────────────────────────────────────
    ".badge-ok{"
    "background:#dcfce7!important;color:#15803d!important;"
    "border-color:#bbf7d0!important;font-weight:600!important}"
    ".badge-warn{"
    "background:#fef3c7!important;color:#92400e!important;"
    "border-color:#fde68a!important;font-weight:600!important}"
    ".badge-crit{"
    "background:#fee2e2!important;color:#dc2626!important;"
    "border-color:#fecaca!important;font-weight:600!important}"
    ".badge-muted{"
    "background:#f1f5f9!important;color:#64748b!important;"
    "border-color:#e2e8f0!important}"
    # ── insp-card: 공통 사각 카드 (참고: maxgauge-1hour-check.html) ──────────
    # filter-bar(검색/필터) + 데이터 테이블을 한 카드로 묶을 때 사용.
    # 헤더 색은 기존 .svc-table 톤(#ECF0F7 / #5F6B80) 유지, 본문 글씨는 #1A1D2E.
    # overflow:visible — 카드 헤더 안에 떠 있는 드롭다운(검색 sugg, DGS PORT 메뉴 등)이
    # 카드 본문 높이가 짧을 때 잘리지 않도록. border-radius:0이라 모서리 자를 필요 없음.
    ".insp-card{background:#ffffff;border:1px solid #CBD5E1;border-radius:0;"
    "box-shadow:0 1px 3px rgba(15,23,42,.06),0 0 0 1px rgba(15,23,42,.02);"
    "overflow:visible;display:flex;flex-direction:column;"
    "animation:_inspFadeUp .35s ease both;margin-bottom:16px;}"
    "@keyframes _inspFadeUp{from{opacity:0;transform:translateY(10px)}"
    "to{opacity:1;transform:translateY(0)}}"
    ".insp-card .insp-card-hdr{padding:14px 18px;border-bottom:1px solid #E4E6ED;"
    "background:#ffffff;display:flex;align-items:center;gap:10px;flex-wrap:wrap;}"
    ".insp-card .insp-card-title{font-size:.78rem;font-weight:700;color:#5F6B80;"
    "letter-spacing:.06em;text-transform:uppercase;"
    "font-family:Inter,Pretendard,sans-serif;}"
    ".insp-card .insp-card-body{background:#ffffff;}"
    ".insp-card .tbl-wrap{border:none!important;border-radius:0!important;"
    "box-shadow:none!important;background:#ffffff!important;overflow:visible!important;}"
    ".insp-card .svc-table{font-size:13px;}"
    ".insp-card .svc-table thead th{padding:10px 16px;background:#ECF0F7;"
    "border-bottom:1px solid #D8DEE8;font-size:.72rem;font-weight:700;"
    "letter-spacing:.04em;text-transform:uppercase;color:#5F6B80;text-align:center;"
    "border-right:none;}"
    ".insp-card .svc-table tbody td{padding:13px 16px;"
    "border-bottom:1px solid #F0F1F5;text-align:center;color:#1A1D2E;"
    "border-right:none;}"
    ".insp-card .svc-table tbody tr:nth-child(odd),"
    ".insp-card .svc-table tbody tr:nth-child(even){background:transparent;}"
    ".insp-card .svc-table tbody tr:hover td{background:#F0F6FF!important;}"
    ".insp-card .svc-table tbody tr:last-child td{border-bottom:none;}"
    # Overview metric 카드 status: 헤더 좌측 컬러 dot. 색은 부모 .metric-X에서 결정
    ".insp-card .status-dot{display:inline-block;width:8px;height:8px;border-radius:50%;"
    "margin-right:10px;flex-shrink:0;vertical-align:middle;background:#cbd5e1;"
    "transition:background .2s,box-shadow .2s;}"
    ".insp-card.metric-neutral .status-dot{background:#cbd5e1;}"
    ".insp-card.metric-ok .status-dot{background:#22c55e;"
    "box-shadow:0 0 0 3px rgba(34,197,94,.15);}"
    ".insp-card.metric-warning .status-dot{background:#f59e0b;"
    "box-shadow:0 0 0 3px rgba(245,158,11,.18);}"
    ".insp-card.metric-critical .status-dot{background:#ef4444;"
    "box-shadow:0 0 0 3px rgba(239,68,68,.18);}"
    # .grid 안에서는 카드 자체 margin 제거 (grid gap만 사용)
    ".grid > .insp-card{margin-bottom:0;}"
)


# ── help tooltip JS ───────────────────────────────────────────────────────────────

_HELP_JS = (
    '<div id="help-tip" class="help-tip" data-ov-track>'
    '<button id="help-tip-x" '
    'style="display:none;position:absolute;top:8px;right:10px;background:none;border:none;'
    'cursor:pointer;color:#6272a4;font-size:1.1rem;line-height:1;padding:2px 6px;'
    'border-radius:4px;transition:color .15s;">'
    '&#x2715;</button>'
    '<div class="help-tip-title" id="help-tip-title"></div>'
    '<div class="help-tip-body" id="help-tip-body"></div>'
    '</div>'
    '<script>document.addEventListener("DOMContentLoaded",function(){'
    'var tip=document.getElementById("help-tip");'
    'var tipX=document.getElementById("help-tip-x");'
    'window._htPinned=false;'
    'function pos(e){'
    '  if(window._htPinned)return;'
    '  var x=e.clientX+14,y=e.clientY+14;'
    '  if(x+tip.offsetWidth>window.innerWidth-8)x=e.clientX-tip.offsetWidth-14;'
    '  if(y+tip.offsetHeight>window.innerHeight-8)y=e.clientY-tip.offsetHeight-14;'
    '  tip.style.left=x+"px";tip.style.top=y+"px";}'
    'function showTip(btn){'
    '  document.getElementById("help-tip-title").textContent=btn.dataset.title||"Help";'
    '  document.getElementById("help-tip-body").innerHTML=btn.dataset.body||"";'
    '  tip.style.display="block";}'
    'tipX.addEventListener("click",function(e){'
    '  e.stopPropagation();'
    '  window._htPinned=false;'
    '  tip.style.display="none";'
    '  tip.style.pointerEvents="none";'
    '  tipX.style.display="none";});'
    'tipX.addEventListener("mouseenter",function(){tipX.style.color="#c8cfe8";});'
    'tipX.addEventListener("mouseleave",function(){tipX.style.color="#6272a4";});'
    'document.querySelectorAll(".help-btn").forEach(function(btn){'
    '  btn.addEventListener("mouseenter",function(e){'
    '    if(window._htPinned)return;showTip(btn);pos(e);});'
    '  btn.addEventListener("mousemove",function(e){if(!window._htPinned)pos(e);});'
    '  btn.addEventListener("mouseleave",function(){if(!window._htPinned)tip.style.display="none";});'
    '  btn.addEventListener("click",function(e){'
    '    e.stopPropagation();'
    '    window._htPinned=!window._htPinned;'
    '    if(window._htPinned){showTip(btn);pos(e);'
    '      tip.style.pointerEvents="auto";tipX.style.display="block";}'
    '    else{tip.style.display="none";tip.style.pointerEvents="none";tipX.style.display="none";}});'
    '});'
    'document.addEventListener("click",function(e){'
    '  if(window._htPinned&&window._ovOutside&&window._ovOutside(tip,e)){'
    '    window._htPinned=false;'
    '    tip.style.display="none";'
    '    tip.style.pointerEvents="none";'
    '    tipX.style.display="none";}});'
    '});</script>'
)


# ── help icon / title ─────────────────────────────────────────────────────────────

def _help_icon(title, body_html, gray=False):
    import html as _html
    t   = _html.escape(title, quote=True)
    b   = body_html.replace('"', '&quot;').replace("'", '&#39;')
    return '<span class="help-btn" data-title="{0}" data-body="{1}">i</span>'.format(t, b)


def _page_title_html(title, help_title='', help_body='', sub=''):
    disp_title = _kr_title(title)
    icon      = (' ' + _help_icon(help_title or disp_title, help_body)) if help_body else ''
    title_row = '<div class="page-hdr"><span class="page-title">{0}</span>{1}</div>'.format(disp_title, icon)
    return title_row


# ── HELP tooltip content dict ─────────────────────────────────────────────────────

_HELP = {
    'summary_10min': ('10분 Summary 확인', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">각 인스턴스별로 10분 단위 Summary 수집이 정상적으로 이루어지고 있는지 점검합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">APM_DB_INFO에 등록된 전체 인스턴스를 기준으로, ORA_LAST_SUMMARY 테이블에서 SUMMARY_TYPE이 %10Min인 가장 최근 수집 시각을 조회합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">STATUS 기준</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">OK : 가장 최근 수집 시각이 현재 기준 직전 10분 구간과 정확히 일치<br>WAITING : 오늘 수집은 이루어졌으나 현재 시각보다 1구간 이상 뒤쳐진 상태<br>CHECK : 수집 기록이 없거나 오늘 이전 날짜에 머물러 있어 확인이 필요한 상태</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">DELAY_INFO</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">WAITING/CHECK 상태일 때 기준 시각 대비 지연 시간을 표시합니다.<br>예: +0h 20m (20분 지연), +2d (2일 경과)</div></div></div>'),
    'summary_1hour': ('1시간 Summary 확인', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">각 인스턴스별로 1시간 단위 Summary 수집이 정상적으로 이루어지고 있는지 점검합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">APM_DB_INFO에 등록된 전체 인스턴스를 기준으로, ORA_LAST_SUMMARY 테이블에서 SUMMARY_TYPE이 %Daily인 가장 최근 수집 시각을 조회합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">STATUS 기준</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">OK : 가장 최근 수집 시각이 현재 기준 직전 정시(1시간 전)와 정확히 일치<br>WAITING : 오늘 수집은 이루어졌으나 현재 시각보다 1시간 이상 뒤쳐진 상태<br>CHECK : 수집 기록이 없거나 오늘 이전 날짜에 머물러 있어 확인이 필요한 상태</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">DELAY_INFO</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">WAITING/CHECK 상태일 때 기준 시각 대비 지연 시간을 표시합니다.<br>예: +2h (2시간 지연), +1d (전일 이후 미수집)</div></div></div>'),
    'partition_create': ('파티션 생성 확인', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">각 인스턴스별로 금일 기준 3일치의 파티션이 정상 생성되어 있는지 확인합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">APM_DB_INFO에 등록된 전체 인스턴스를 기준으로, 대상 일자의 파티션명이 DBA_TAB_PARTITIONS 및 PG_TABLES에 존재하는지 확인합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">STATUS 기준</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">일자별 파티션 개수가 서로 동일하면 OK,<br>일자 간 개수가 다르거나 일부가 누락되면 CHECK로 표시합니다.</div></div></div>'),
    'partition_drop': ('파티션 삭제 확인', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">각 인스턴스별로 보관 기간이 지났거나 Instance List에서 삭제하였지만 남아있는 파티션 테이블이 있는지 점검합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">{PYYYYMMDDXXX} 패턴이 적용되어 있는 테이블들을 조회하여 파티션은 있는데 APM_DB_INFO와 매칭되지 않거나, 보관 주기 지난 리스트를 확인합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">STATUS 기준</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">삭제 대상 파티션이 없으면 OK,<br>1건 이상 존재하면 CHECK로 표시합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">추가 기능</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">CHECK 상태인 인스턴스의 OLD PARTITION CNT에 마우스를 올리면 삭제 대상 테이블 목록을 확인할 수 있습니다.<br>필요 시 해당 화면에서 파티션 DROP을 수동으로 수행할 수 있습니다.</div></div></div>'),
    'partition_time': ('파티션 시간 확인', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">DGServer_M 로그를 기준으로 파티션 생성 및 삭제 작업의 시작/종료 시각과 소요 시간을 확인합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">DGServer_M 로그에서 파티션 CREATE, DROP 관련 메시지를 추출하여 스키마별로 START/FINISH를 한 행으로 표시합니다.<br>Oracle 환경의 경우 COMPRESS 작업 이력도 함께 조회합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">STATUS 기준</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">OK : START와 FINISH가 모두 존재하는 경우<br>CHECK : START 또는 FINISH 중 하나라도 없거나, APM_DB_INFO에 있는 인스턴스의 작업 이력이 없는 경우</div></div></div>'),
    'overview': ('오버뷰', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">MaxGauge 서버의 주요 시스템 리소스와 구성 서비스 상태를 실시간으로 모니터링합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">SYSTEM</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">호스트명, OS 종류/버전, 마지막 재시작 이후 경과 시간(업타임), 물리 CPU 코어 수를 표시합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">CPU</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">/proc/stat를 0.3초 간격으로 2회 읽어 CPU 사용률을 계산합니다.<br>User(사용자 영역), System(커널 영역), I/O Wait(디스크 I/O 대기) 항목으로 구분하여 표시합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">MEMORY</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">/proc/meminfo 기준으로 실제 사용 메모리를 계산합니다.<br>계산식은 Used = MemTotal - MemFree - Buffers - Cached이며, free -h와 동일한 기준입니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">DISK</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">Oracle 환경에서는 Repository DB를 기준으로 테이블스페이스별 사용률을 조회합니다.<br>PostgreSQL 환경에서는 pg_data_dir 경로(미설정 시 /)의 파일시스템 사용률을 os.statvfs()로 조회합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">SERVICES</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">Configuration에 등록되어 있는 수집 Process에 대해 PID를 기준으로 기동 상태를 확인합니다.<br>필요 시 새로고침 버튼으로 즉시 재조회할 수 있습니다.</div></div></div>'),
    'license': ('인스턴스 목록', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">Repository DB의 APM_DB_INFO 테이블에 등록된 전체 모니터링 대상 인스턴스 목록을 조회합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">APM_DB_INFO 테이블의 전체 행을 DB_ID 순으로 조회하여, 각 인스턴스의 기본 정보를 표시합니다.<br>DGS_PORT 컨럼은 각 Slave의 Summary 수행 로그를 통해 연결되어 있는 Slave Port를 표시합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">필터 기능</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">상단 검색창에서 인스턴스 이름으로 필터링할 수 있으며, DGS PORT 버튼을 클릭하면 수집 포트별로 그룹화하여 조회할 수 있습니다.</div></div></div>'),
    'session': ('세션 확인', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">각 인스턴스별로 가장 최근의 세션 수집 시각을 조회하여 수집 상태를 점검합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">APM_DB_INFO에 등록된 전체 인스턴스를 기준으로, 세션 데이터의 가장 최근 수집 시각을 표시합니다.<br>수집이 오래 멈춰 있으면 RTS 혹은 Slave Gather의 상태를 확인해야 합니다.</div></div></div>'),
    'query': ('쿼리 확인', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">각 인스턴스별 Query Base 수집 지표들의 수집 현황을 표시합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">Plan : 어제차 ORA_SQL_PLAN 파티션 테이블에 수집된 데이터가 한 건이라도 있으면 OK<br>Bind : 어제차 ORA_BIND_VALUE 파티션 테이블에 수집된 데이터가 한 건이라도 있으면 OK<br>Tablespace : 어제차 ORA_TABLESPACE_INFO 파티션 테이블에 수집된 데이터가 한 건이라도 있으면 OK<br>Parameter : 어제차 ORA_DB_PARAMETER 파티션 테이블에 수집된 데이터가 한 건이라도 있으면 OK</div></div></div>'),
    'alarm_history': ('알람 발송 이력', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">선택한 날짜에 임계치를 초과해 발송 대상이 된 알람(SMS_FLAG=1)을 인스턴스별로 조회하고, 각 알람에 대해 SMS / API / Mail 채널이 실제로 정상 발송됐는지 각 로그를 파싱해 확인합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">APM_DB_INFO 와 ORA_ALARM_HISTORY 를 JOIN 하여 선택한 날짜의 00:00 ~ 익일 00:00 사이에 SMS_FLAG = 1 로 기록된 알람을 시각 내림차순으로 최대 500건 조회합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">STATUS 기준</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">SUCCESS : 해당 발송 건의 처리 스레드에서 Finish 가 찍혔고 그 사이 ERROR 가 없음. 또는 일시적 실패 후 재시도 성공.<br>FAILED : [ERROR] 레벨, 또는 Failed / Exception 키워드, ORA-xxxxx, java Exception, Listener refused, 연결이 거부됨 등이 감지된 경우.<br>SKIPPED : 해당 로그 파일 자체가 없거나, 그 발송 건에 매칭되는 항목이 없는 경우.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">추가 기능</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">상단의 날짜 선택기 또는 좌/우 화살표 버튼으로 일자를 이동하면 자동 재조회됩니다.</div></div></div>'),
    'alert': ('알람 확인', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">최근 30일 간 발생한 주요 알람 이력을 조회합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">ORA_ALARM_HISTORY 테이블에서 최근 30일 간의 알람을 인스턴스별로 집계하여 표시합니다.<br>DB Down : 모니터링 대상 DB가 중지된 경우 발생<br>Listener Stop : 모니터링 대상 DB의 Listener가 중지된 경우 발생<br>RTS Daemon Disconnect : RTS와 Slave Gather의 연결이 끊겼을 경우 발생 (게더의 과도한 재기동 / License 비정상 인식 의심)<br>RTS Server Down : RTS가 중지된 경우 발생 (옵저버에 의한 과도한 재기동 혹은 모니터링 대상 DB의 패치 의심)</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">추가 기능</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">알람 이름 클릭 시 해당 알람의 상세 발생 시각 목록을 툴팁으로 확인할 수 있습니다.</div></div></div>'),
    'license_check': ('라이선스 확인', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">각 인스턴스별 라이선스의 상태를 표시합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">License Info</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">현재 등록되어 있는 라이선스의 정보를 표시합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">Instance License Status</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">각 인스턴스의 라이선스 상태 정보를 표시합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">Recent License Events</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">금일치 DGServer_M 로그에서 라이선스 관련 이벤트를 표시합니다.</div></div></div>'),
    'capacity': ('용량 확인', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">Repository DB의 각 스키마별 Disk 사용률을 조회합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">PG_CLASS, PG_NAMESPACE 테이블을 통해 스키마별 디스크 사용률을 확인합니다.<br>디스크 사용률이 높은 스키마 순서대로 정렬하여 표시합니다.</div></div></div>'),
    'vacuum': ('Vacuum/Age 확인', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">PostgreSQL의 Vacuum 실행 이력과 Transaction ID Age를 조회하여 Wraparound 위험을 점검합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">Vacuum Log</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">DGServer_M 로그에서 POSTGRESQL VACUUM 작업 이력(시작/종료/소요시간)을 추출하여 표시합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">Auto-Vacuum Check</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">autovacuum이 작동해야 하는데 안 되고 있는 테이블을 표시합니다. VACUUM TABLE 버튼 클릭 시 대상 테이블에 대하여 Vacuum을 수행합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">Age Check</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">Repository DB의 현재 Age 정보를 표시합니다. VACUUM FREEZE 버튼을 클릭하면 백그라운드로 VACUUM FREEZE를 수행합니다.</div></div></div>'),
    'history': ('Inspector History', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">써머리 수집 상태를 시간대별 띠 그래프로 시각화하여 표시합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">summary_history 테이블(PG)에 저장된 10분/1시간 써머리 수집 이력을 인스턴스별로 시간대 띠로 표시합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">추가 기능</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">날짜 · 시간대 · 인스턴스 필터 조작이 가능하며, 마우스 오버 시 정확한 시각과 상태를 확인할 수 있습니다.<br>세로 십자선이 모든 인스턴스에 걸쳐 표시됩니다.</div></div></div>'),
    'services': ('서비스', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">MaxGauge 구성 요소(DGServer, PlatformJS, Repository DB)의 실행 상태를 표시합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">service_config.json에 등록된 각 서비스의 PID, 포트, 버전, 업타임을 확인합니다.<br>새로고침 버튼으로 즉시 재조회할 수 있습니다.</div></div></div>'),
    'gather_log': ('Gather 로그', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">DGServer 의 로그를 탭 단위로 조회합니다. Overview 탭은 ERROR / WARN 요약, 개별 DGServer 탭은 일자별 로그 검색과 실시간 추적이 가능합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">Overview 탭은 각 DGServer_M / DGServer_Sn 의 최신 활성 로그(DGM_&lt;port&gt;.log / DGS_&lt;port&gt;.log) 에서 ERROR / WARN 패턴을 추출해 서버별 카드에 최근 500건을 표시합니다. 일자별 .log.zip 은 요약되지 않습니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">탭 구성</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">OBSD : OBSD(Observer) 로그 조회.<br>DGServer_M / DGServer_Sn : 해당 서버의 일자별 .log 및.zip 파일을 직접 열어, 키워드 검색과 시간 범위 필터링 가능.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">추가 기능</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">Follow 버튼으로 tail -f 와 동일한 실시간 로그 업데이트를 확인할 수 있습니다.</div></div></div>'),
    'process_param': ('파라미터', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">DGServer의 설정 파라미터(DGServer.xml)를 조회합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">DGServer_M/Sn의 DGServer.xml 파일의 파라미터 값을 표시합니다.<br>Search 탭 : 모든 DGServer의 파라미터 값을 검색 할 수 있습니다.<br>ENABLE : 현재 활성화 되어있는 파라미터, &lt;tag&gt;value&lt;/tag&gt; 형태<br>DISABLE : 현재 비활성화 되어있는 파라미터, &lt;!-- --&gt; 주석으로 감싸져 있는 형태</div></div></div>'),
    'disk_capacity': ('용량 확인', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">Repository DB의 각 스키마별 Disk 사용률을 조회합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">PG_CLASS, PG_NAMESPACE 테이블을 통해 스키마별 디스크 사용률을 확인합니다.<br>디스크 사용률이 높은 스키마 순서대로 정렬하여 표시합니다.</div></div></div>'),
    'disk_top_segment': ('상위 Segment', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">Repository DB에서 용량이 큰 상위 30개의 세그먼트 목록을 조회합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">테이블/인덱스 등 세그먼트를 TOTAL SIZE 크기 순으로 정렬하여 표시합니다.</div></div></div>'),
    'disk_temp_table': ('임시 테이블', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">pg_tables 및 user_tables 목록에서 tt% 테이블 목록을 표시합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">추가 기능</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">Drop Temp Table 버튼 클릭 시 표시된 Temp Table 들을 삭제합니다.</div></div></div>'),
    'history_os_cpu': ('CPU 사용량 이력', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">OS CPU 사용률을 1분 간격으로 수집한 히스토리 차트를 표시합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">INSP_OS_HISTORY 테이블에 1분 간격으로 수집된 CPU 사용률(User/System/IO Wait)을 시계열 차트로 표시합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조작 방법</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">상단 날짜 선택 및 AM/PM/Today 필터로 조회 범위를 조절할 수 있습니다.<br>차트 영역을 드래그하여 특정 시간대를 확대할 수 있으며, 더블클릭으로 전체 보기로 돌아올 수 있습니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">프로세스 목록 (차트 클릭 시)</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">차트의 한 시점을 단순 <b>클릭</b>하면 하단 패널에 그 분의 <b>Top 20 프로세스</b>가 표시됩니다.<table style=\"width:100%;border-collapse:collapse;margin-top:8px;font-size:.74rem;\"><thead><tr style=\"border-bottom:1px solid #e5e7eb;background:#f9fafb;\"><th style=\"text-align:left;padding:4px 8px;font-weight:600;color:#374151;width:64px;\">컬럼</th><th style=\"text-align:left;padding:4px 8px;font-weight:600;color:#374151;\">의미</th></tr></thead><tbody><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">PID</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">Process ID — OS가 부여하는 고유 번호</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">USER</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">프로세스를 실행한 OS 계정 (긴 이름은 + 로 잘림)</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">CPU%</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">프로세스 시작 후 누적 CPU 사용률. 100% = 코어 1개 풀. 멀티스레드면 100% 초과 가능 (시점 즉시값 아닌 평균)</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">MEM%</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">시스템 전체 RAM 대비 RSS 비율</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">RSS</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">Resident Set Size — 실제로 RAM에 올라간 메모리 (가장 현실적인 메모리 지표)</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">VSZ</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">Virtual Size — 요청한 가상 메모리 전체 (RSS + swap + mmap + 미할당). 보통 RSS 보다 훨씬 큼</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">THR</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">Threads — 프로세스 안의 스레드 개수 (Java 같은 멀티스레드 앱이 큰 값)</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">ETIME</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">Elapsed Time — 프로세스가 떠 있는 시간. dd-hh:mm:ss 형식 (예: 2-01:44:19 = 2일 1시간 44분)</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">COMM</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">Command — 실행 파일 이름만 (앞 64자)</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">ARGS</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">실행 시 넘긴 명령어 인자 전체 (256자 cap). 어떤 옵션으로 떴는지 확인 — 행 hover 시 전체 표시</td></tr></tbody></table></div></div></div>'),
    'history_os_memory': ('메모리 사용량 이력', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">OS 메모리 사용률을 1분 간격으로 수집한 히스토리 차트를 표시합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">INSP_OS_HISTORY 테이블에 1분 간격으로 수집된 메모리 사용률(Used/Free/Total)을 시계열 차트로 표시합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조작 방법</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">상단 날짜 선택 및 AM/PM/Today 필터로 조회 범위를 조절할 수 있습니다.<br>차트 영역을 드래그하여 특정 시간대를 확대할 수 있으며, 더블클릭으로 전체 보기로 돌아올 수 있습니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">프로세스 목록 (차트 클릭 시)</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">차트의 한 시점을 단순 <b>클릭</b>하면 하단 패널에 그 분의 <b>Top 20 프로세스</b>가 표시됩니다.<table style=\"width:100%;border-collapse:collapse;margin-top:8px;font-size:.74rem;\"><thead><tr style=\"border-bottom:1px solid #e5e7eb;background:#f9fafb;\"><th style=\"text-align:left;padding:4px 8px;font-weight:600;color:#374151;width:64px;\">컬럼</th><th style=\"text-align:left;padding:4px 8px;font-weight:600;color:#374151;\">의미</th></tr></thead><tbody><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">PID</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">Process ID — OS가 부여하는 고유 번호</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">USER</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">프로세스를 실행한 OS 계정 (긴 이름은 + 로 잘림)</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">CPU%</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">프로세스 시작 후 누적 CPU 사용률. 100% = 코어 1개 풀. 멀티스레드면 100% 초과 가능 (시점 즉시값 아닌 평균)</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">MEM%</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">시스템 전체 RAM 대비 RSS 비율</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">RSS</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">Resident Set Size — 실제로 RAM에 올라간 메모리 (가장 현실적인 메모리 지표)</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">VSZ</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">Virtual Size — 요청한 가상 메모리 전체 (RSS + swap + mmap + 미할당). 보통 RSS 보다 훨씬 큼</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">THR</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">Threads — 프로세스 안의 스레드 개수 (Java 같은 멀티스레드 앱이 큰 값)</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">ETIME</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">Elapsed Time — 프로세스가 떠 있는 시간. dd-hh:mm:ss 형식 (예: 2-01:44:19 = 2일 1시간 44분)</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">COMM</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">Command — 실행 파일 이름만 (앞 64자)</td></tr><tr><td style=\"padding:4px 8px;color:#374151;font-weight:600;border-bottom:1px solid #f3f4f6;\">ARGS</td><td style=\"padding:4px 8px;color:#6b7280;border-bottom:1px solid #f3f4f6;\">실행 시 넘긴 명령어 인자 전체 (256자 cap). 어떤 옵션으로 떴는지 확인 — 행 hover 시 전체 표시</td></tr></tbody></table></div></div></div>'),
    'history_disk_tbs': ('디스크 / TBS 이력', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">테이블스페이스 또는 디스크 사용률의 일별 추이를 조회합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">INSP_TBS_HISTORY 테이블에 매일 23:50에 수집된 테이블스페이스/디스크 사용률을 날짜 범위별로 조회합니다.</div></div></div>'),
    'history_process_status': ('서비스 상태 이력', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">MaxGauge 구성 서비스의 실행 상태 이력을 조회합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">INSP_SERVICE_HISTORY 테이블에 매시 수집된 DGServer, PlatformJS, Repository DB의 RUNNING/STOPPED 상태 이력을 타임라인으로 표시합니다.</div></div></div>'),
    'history_process_qcnt': ('Qcnt 추이', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">DGServer의 커넥션 수 및 큐 카운트 추이를 표시합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">INSP_QCNT_HISTORY 테이블에 1분 간격으로 수집된 DGServer 로그의 conn_info(active/total/max/qcnt)를 서비스별 차트로 표시합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조작 방법</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">상단 날짜 선택 및 AM/PM/Today 필터로 조회 범위를 조절할 수 있습니다.<br>차트 영역을 드래그하여 특정 시간대를 확대할 수 있으며, 더블클릭으로 전체 보기로 돌아올 수 있습니다.</div></div></div>'),
    'history_process_heap': ('Heap 추이', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">DGServer JVM Heap 메모리 사용률 추이를 표시합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">INSP_HEAP_HISTORY 테이블에 1분 간격으로 수집된 DGServer 로그의 DG MANAGER Heap 정보(Used/Alloc/Max MB)를 서비스별 차트로 표시합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조작 방법</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">상단 날짜 선택 및 AM/PM/Today 필터로 조회 범위를 조절할 수 있습니다.<br>차트 영역을 드래그하여 특정 시간대를 확대할 수 있으며, 더블클릭으로 전체 보기로 돌아올 수 있습니다.</div></div></div>'),
    'config_dump': ('Config Dump', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">MaxGauge 설정 테이블의 데이터를 JSON 형식으로 내보냅니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">인스턴스 관리, 계정 관리, 알림 설정, 수집 설정 등 카테고리별 설정 테이블을 선택하여 내보낼 수 있습니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">추가 기능</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">서버 마이그레이션(AS-IS \u2192 TO-BE) 시 설정 이관용으로 활용할 수 있습니다.</div></div></div>'),
    'script_manager': ('Script Manager', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">Repository DB에 직접 SQL을 실행할 수 있는 쿼리 실행기입니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">service_config.json에 설정된 Repository DB에 접속하여 SQL을 실행합니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">추가 기능</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">Ctrl+Enter로 빠르게 실행할 수 있으며, 결과는 테이블 형식으로 표시됩니다.</div></div></div>'),
    'history_summary_10min': ('10분 Summary 이력', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">INSP_SUMMARY_HISTORY 테이블에 저장된 10분 써머리 수집 이력을 인스턴스별 시간대 띠 그래프로 표시합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">스케줄러가 10분 간격으로 수집하여 INSP_SUMMARY_HISTORY에 저장한 10Min 타입의 써머리 상태(OK/WAITING/CHECK)를 조회합니다.<br>날짜 · 시간대 · 인스턴스 필터 조작이 가능하며, 마우스 오버 시 정확한 시각과 상태를 확인할 수 있습니다.</div></div></div>'),
    'history_summary_1hour': ('1시간 Summary 이력', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">INSP_SUMMARY_HISTORY 테이블에 저장된 1시간(Daily) 써머리 수집 이력을 인스턴스별 시간대 띠 그래프로 표시합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">조회 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">스케줄러가 1시간 간격으로 수집하여 INSP_SUMMARY_HISTORY에 저장한 Daily 타입의 써머리 상태(OK/WAITING/CHECK)를 조회합니다.<br>날짜 · 시간대 · 인스턴스 필터 조작이 가능하며, 마우스 오버 시 정확한 시각과 상태를 확인할 수 있습니다.</div></div></div>'),
    'decrypt': ('Encrypt / Decrypt', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">DGServer.jar의 encrypt/decrypt 기능을 사용하여 문자열을 암호화/복호화합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">동작 방식</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">텍스트 입력 후 Encrypt 버튼은 <code>DGServer_M/bin/DGServer.jar encrypt</code>, Decrypt 버튼은 <code>DGServer.jar decrypt</code> 명령을 실행합니다.<br>DGServer.xml 등에서 사용되는 패스워드를 생성하거나 확인할 때 사용합니다.</div></div></div>'),
    'control_process': ('Control Process', '<p style="margin:0 0 12px;padding-bottom:10px;border-bottom:1px solid #f3f4f6;color:#374151;font-size:.84rem;line-height:1.5;">MaxGauge 구성 프로세스(DGServer, PlatformJS, PostgreSQL)를 원격으로 시작/중지/재시작합니다.</p><div style="display:flex;flex-direction:column;gap:12px;"><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">제어 대상</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">DGServer_M, DGServer_S1~Sn, PlatformJS, PostgreSQL<br>Oracle DB는 원격 제어를 지원하지 않습니다.</div></div><div style="display:flex;flex-direction:column;gap:3px;"><div style="font-weight:600;color:#374151;font-size:.78rem;">동작 방식</div><div style="font-size:.77rem;color:#6b7280;line-height:1.6;">각 프로세스 HOME 경로의 .mxgrc 환경설정을 읽어 Start/Stop/Restart를 수행합니다.<br>DGServer: java -Xms/Xmx -DG_NAME -jar DGServer.jar<br>PlatformJS: platformjs.start.sh / platformjs.stop.sh<br>PostgreSQL: Database/start.sh / Database/stop.sh</div></div></div>'),
}




# ── instance filter block ─────────────────────────────────────────────────────────

def _inst_filter_block(tbl_id):
    """Returns (ui_html, script_html) for instance name search filter."""
    ui = (
        '<div style="margin-bottom:14px;">'
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
        '<div id="inst-sugg"'
        ' style="display:none;position:absolute;top:calc(100%% + 4px);left:0;'
        'background:var(--bg-card);border:1px solid var(--bd);border-radius:8px;'
        'min-width:240px;max-height:200px;overflow-y:auto;z-index:200;'
        'box-shadow:0 6px 24px rgba(0,0,0,.4);padding:4px 0;"></div>'
        '</div>'
        '</div>'
        '<div id="inst-no-res" style="display:none;color:var(--c-muted);font-size:.85rem;'
        'padding:14px 0;text-align:center;">일치하는 결과가 없습니다.</div>'
    )
    script = (
        '<script>'
        'function _instXToggle(){'
        'var x=document.getElementById("inst-x");if(!x)return;'
        'x.style.display=document.getElementById("inst-srch").value?"":"none";'
        '}'
        '</script>'
        '<style>'
        '.inst-chip{padding:6px 14px;font-size:.8rem;color:var(--c-muted);cursor:pointer;'
        'transition:background .1s;white-space:nowrap;}'
        '.inst-chip:hover{background:var(--bg-main);color:var(--c-main);}'
        '.inst-chip b{color:var(--c-accent);font-style:normal;font-weight:700;}'
        '</style>'
        '<script>'
        '(function(){'
        'var tbl=document.getElementById("' + tbl_id + '");'
        'if(!tbl)return;'
        'var ths=tbl.querySelectorAll("thead th");'
        'var instIdx=-1;'
        'ths.forEach(function(th,i){'
        'if(th.textContent.trim().toUpperCase().indexOf("INSTANCE")!==-1)instIdx=i;'
        '});'
        'if(instIdx<0)return;'
        'var rows=Array.prototype.slice.call(tbl.querySelectorAll("tbody tr"));'
        'var instances=[];var iSet={};'
        'rows.forEach(function(tr){'
        'var cells=tr.querySelectorAll("td");'
        'if(cells[instIdx]){'
        'var v=cells[instIdx].textContent.trim();'
        'tr.dataset.inst=v.toLowerCase();'
        'if(v&&!iSet[v]){iSet[v]=1;instances.push(v);}}'
        '});'
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
        'window.instFilter=function(){'
        'var q=document.getElementById("inst-srch").value.trim().toLowerCase();'
        'var vis=0;'
        'var curRows=Array.prototype.slice.call(tbl.querySelectorAll("tbody tr"));'
        'curRows.forEach(function(tr){'
        'if(!tr.dataset.inst){'
        'var cells=tr.querySelectorAll("td");'
        'if(cells[instIdx])tr.dataset.inst=cells[instIdx].textContent.trim().toLowerCase();'
        '}'
        'var show=!q||(tr.dataset.inst||"").indexOf(q)!==-1;'
        'tr.style.display=show?"":"none";if(show)vis++;'
        '});'
        'document.getElementById("inst-no-res").style.display=vis?"none":"";'
        'tbl.style.display=vis?"":"none";'
        'updateSugg(q);};'
        'document.addEventListener("click",function(e){'
        'var sg=document.getElementById("inst-sugg");'
        'if(sg&&!sg.contains(e.target)&&e.target.id!=="inst-srch")sg.style.display="none";'
        '});'
        '})();'
        '</script>'
    )
    return ui, script


# ── sidebar ───────────────────────────────────────────────────────────────────────

def _sidebar(active):
    b       = _UTILS_BASE
    from service_config import load_service_config
    cfg     = load_service_config()
    db_type = cfg.get("repository", {}).get("db_type", "Oracle").lower()
    is_pg   = "postgres" in db_type
    is_ora  = "oracle" in db_type

    def item(path, label, key):
        cls = 'nav-item active' if active == key else 'nav-item'
        return '<a href="%s%s" class="%s">%s</a>' % (b, path, cls, label)

    def sub(path, label, key):
        cls = 'nav-sub active' if active == key else 'nav-sub'
        return '<a href="%s%s" class="%s">%s</a>' % (b, path, cls, label)

    disk_subs = []
    if is_pg or is_ora:
        if is_pg:
            disk_subs.append(sub('/disk/capacity',   'Capacity Check',   'disk_capacity'))
            disk_subs.append(sub('/disk/vacuum-age', 'Vacuum/Age Check', 'disk_vacuum_age'))
        disk_subs.append(sub('/disk/top-segment', 'Top Segment', 'disk_top_segment'))
        disk_subs.append(sub('/disk/temp-table',  'Temp Table',  'disk_temp_table'))

    def grp(gid, label, children_html):
        arrow = ('<span class="nav-arrow" id="arrow-' + gid + '"'
                 ' style="font-size:.55rem;transition:transform .2s;display:inline-block;">&#9660;</span>')
        return ''.join([
            '<hr class="nav-divider">',
            '<div class="nav-lbl nav-toggle" onclick="toggleNav(\'' + gid + '\')" '
            'style="cursor:pointer;display:flex;justify-content:space-between;align-items:center;'
            'user-select:none;">',
            '<span>' + label + '</span>' + arrow,
            '</div>',
            '<div class="nav-grp" id="grp-' + gid + '">',
            children_html,
            '</div>',
        ])

    partition_children = ''.join([
        sub('/partition/create', 'Create Check', 'partition_create'),
        sub('/partition/drop',   'Drop Check',   'partition_drop'),
        sub('/partition/time',   'Time Check',   'partition_time'),
    ])
    summary_children = ''.join([
        sub('/summary/10min', '10Min Check', 'summary_10min'),
        sub('/summary/1hour', '1Hour Check', 'summary_1hour'),
    ])
    process_children = ''.join([
        sub('/process/gather', 'Gather Log', 'process_gather'),
        sub('/process/param',  'Parameter',  'process_param'),
    ])
    others_children = ''.join([
        sub('/session', 'Session Check',  'session'),
        sub('/query',   'Query Check',    'query'),
        sub('/alert',   'Alert Check',    'alert'),
        sub('/license-check', 'License Check', 'license_check'),
        sub('/history/alarm', 'Alarm Send History', 'alarm_history'),
    ])

    parts = [
        '<aside class="sidebar">',
        '<a href="' + b + '/" class="sb-brand" style="text-decoration:none;">'
        '<div class="sb-brand-icon" style="cursor:pointer;">'
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" '
        'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>'
        '</div>'
        '<div class="sb-brand-text"><span>MaxGauge</span><span>Inspector</span></div>'
        '</a>',
        item('/', '<span style="font-weight:700;">OverView</span>', 'overview').replace('class="nav-item', 'style="margin-top:6px;" class="nav-item'),
        item('/license', '<span style="font-weight:700;">Instance List</span>', 'license'),
        grp('partition', 'Partition', partition_children),
        grp('summary',   'Summary',  summary_children),
        grp('process',   'Process',  process_children),
    ]
    if disk_subs:
        parts.append(grp('disk', 'Disk', ''.join(disk_subs)))
    parts += [
        grp('others', 'Others', others_children),
        '</aside>',
        '<script>',
        'function _navHL(gid,open){'
        'var lbl=document.getElementById("arrow-"+gid);'
        'if(lbl)lbl=lbl.closest(".nav-lbl");'
        'if(lbl){if(open)lbl.classList.add("nav-open");else lbl.classList.remove("nav-open");}'
        '}'
        'function toggleNav(gid){'
        'var g=document.getElementById("grp-"+gid);'
        'var a=document.getElementById("arrow-"+gid);'
        'if(g.style.display==="none"){'
        'g.style.display="";a.style.transform="rotate(0deg)";'
        'localStorage.setItem("nav_"+gid,"1");_navHL(gid,true);'
        '}else{'
        'g.style.display="none";a.style.transform="rotate(-90deg)";'
        'localStorage.setItem("nav_"+gid,"0");_navHL(gid,false);'
        '}}',
        '(function(){'
        '["partition","summary","process","disk","others"].forEach(function(gid){'
        'var g=document.getElementById("grp-"+gid);if(!g)return;'
        'var a=document.getElementById("arrow-"+gid);'
        'var v=localStorage.getItem("nav_"+gid);'
        'if(v==="0"){g.style.display="none";if(a)a.style.transform="rotate(-90deg)";_navHL(gid,false);}'
        'else{_navHL(gid,true);}'
        '});'
        # sidebar scroll position restore
        'var _sb=document.querySelector(".sidebar");'
        'if(_sb){'
        '  var _sv=sessionStorage.getItem("sb_scroll");'
        '  if(_sv)_sb.scrollTop=parseInt(_sv,10);'
        '  _sb.addEventListener("scroll",function(){sessionStorage.setItem("sb_scroll",_sb.scrollTop);});'
        '}'
        '})();',
        '</script>',
    ]
    return ''.join(parts)


# ── full page wrapper ─────────────────────────────────────────────────────────────

def _tools_fab_block():
    """우하단 Tools FAB + 4개 도구 popup (Decrypt/Script/Control/Alert Service) +
    핸들러 JS 일괄 반환. Inspector 본체와 Inspector History 페이지 양쪽에서 사용."""
    return ''.join([
        # ── Tools FAB (우하단) + 위로 펼쳐지는 메뉴 ──
        '<div id="tools-fab-wrap" style="position:fixed;bottom:28px;right:28px;z-index:200;'
        'font-family:Inter,Pretendard,sans-serif;">',
        '<div id="tools-menu" style="display:none;position:absolute;bottom:calc(100% + 12px);right:0;'
        'min-width:200px;background:#ffffff;border:1px solid #E2E8F0;border-radius:12px;'
        'box-shadow:0 12px 40px rgba(15,23,42,.18);padding:6px 0;'
        'transform-origin:bottom right;opacity:0;transform:scale(.92) translateY(8px);">'
        '<a href="#" onclick="event.preventDefault();_openCtlProc();" style="display:flex;align-items:center;gap:8px;'
        'padding:9px 16px;font-size:.8rem;font-weight:500;color:#334155;text-decoration:none;transition:background .15s;"'
        ' onmouseover="this.style.background=\'#F1F5F9\'" onmouseout="this.style.background=\'transparent\'">'
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#8B5CF6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>'
        '</svg>Control Process</a>'
        '<a href="' + _UTILS_BASE + '/report" target="_blank" style="display:flex;align-items:center;gap:8px;'
        'padding:9px 16px;font-size:.8rem;font-weight:500;color:#334155;text-decoration:none;transition:background .15s;"'
        ' onmouseover="this.style.background=\'#F1F5F9\'" onmouseout="this.style.background=\'transparent\'">'
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#8B5CF6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>'
        '<line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>Daily Report</a>'
        '<a href="#" onclick="event.preventDefault();_openScript();" style="display:flex;align-items:center;gap:8px;'
        'padding:9px 16px;font-size:.8rem;font-weight:500;color:#334155;text-decoration:none;transition:background .15s;"'
        ' onmouseover="this.style.background=\'#F1F5F9\'" onmouseout="this.style.background=\'transparent\'">'
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#8B5CF6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>Script Manager</a>'
        '<a href="#" onclick="event.preventDefault();_openDecrypt();" style="display:flex;align-items:center;gap:8px;'
        'padding:9px 16px;font-size:.8rem;font-weight:500;color:#334155;text-decoration:none;transition:background .15s;"'
        ' onmouseover="this.style.background=\'#F1F5F9\'" onmouseout="this.style.background=\'transparent\'">'
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#8B5CF6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>Encrypt / Decrypt</a>'
        '<div style="position:relative;" onmouseenter="document.getElementById(\'as-sub\').style.display=\'block\'" onmouseleave="document.getElementById(\'as-sub\').style.display=\'none\'">'
        '<a href="#" onclick="event.preventDefault();" style="display:flex;align-items:center;gap:8px;'
        'padding:9px 16px;font-size:.8rem;font-weight:500;color:#334155;text-decoration:none;transition:background .15s;"'
        ' onmouseover="this.style.background=\'#F1F5F9\'" onmouseout="this.style.background=\'transparent\'">'
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#8B5CF6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M22 17H2a3 3 0 0 0 3-3V9a7 7 0 0 1 14 0v5a3 3 0 0 0 3 3zm-8.27 4a2 2 0 0 1-3.46 0"/></svg>'
        'Alert Service &#9666;</a>'
        '<div id="as-sub" style="display:none;position:absolute;right:100%;top:0;background:#fff;border:1px solid #E2E8F0;border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.12);min-width:120px;z-index:10001;overflow:hidden;margin-right:4px;">'
        '<a href="#" onclick="event.preventDefault();_svcOpen(\'sms\');" style="display:block;padding:9px 16px;font-size:.8rem;color:#334155;text-decoration:none;transition:background .15s;" onmouseover="this.style.background=\'#F1F5F9\'" onmouseout="this.style.background=\'transparent\'">SMS</a>'
        '<a href="#" onclick="event.preventDefault();_svcOpen(\'api\');" style="display:block;padding:9px 16px;font-size:.8rem;color:#334155;text-decoration:none;border-top:1px solid #F1F5F9;transition:background .15s;" onmouseover="this.style.background=\'#F1F5F9\'" onmouseout="this.style.background=\'transparent\'">API</a>'
        '<a href="#" onclick="event.preventDefault();_svcOpen(\'mail\');" style="display:block;padding:9px 16px;font-size:.8rem;color:#334155;text-decoration:none;border-top:1px solid #F1F5F9;transition:background .15s;" onmouseover="this.style.background=\'#F1F5F9\'" onmouseout="this.style.background=\'transparent\'">MAIL</a>'
        '</div></div>'
        '<a href="' + _UTILS_BASE + '/config-dump" style="display:flex;align-items:center;gap:8px;'
        'padding:9px 16px;font-size:.8rem;font-weight:500;color:#334155;text-decoration:none;transition:background .15s;"'
        ' onmouseover="this.style.background=\'#F1F5F9\'" onmouseout="this.style.background=\'transparent\'">'
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#8B5CF6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>'
        '</svg>Config Dump</a>'
        '</div>',
        '<button id="tools-fab-btn" onclick="_toolsToggle()" '
        'title="Tools" '
        'style="width:48px;height:48px;border-radius:50%;background:#ffffff;'
        'border:1.5px solid #E2E8F0;color:#6366F1;cursor:pointer;'
        'box-shadow:0 4px 12px rgba(15,23,42,.1);display:flex;align-items:center;justify-content:center;'
        'transition:all .15s;font-family:inherit;padding:0;" '
        'onmouseover="this.style.borderColor=\'#6366F1\';this.style.boxShadow=\'0 6px 18px rgba(99,102,241,.25)\';" '
        'onmouseout="this.style.borderColor=\'#E2E8F0\';this.style.boxShadow=\'0 4px 12px rgba(15,23,42,.1)\';">'
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>'
        '</svg>'
        '</button>'
        '</div>',
        '<script>'
        'window._toolsAnimating=false;'
        'function _toolsToggle(){'
        '  var d=document.getElementById("tools-menu");'
        '  if(window._toolsAnimating)return;'
        '  if(d.dataset.open==="1"){_toolsClose();}else{_toolsOpen();}'
        '}'
        'function _toolsOpen(){'
        '  var d=document.getElementById("tools-menu");'
        '  d.dataset.open="1";'
        '  d.style.display="block";'
        '  d.style.transition="none";'
        '  d.style.opacity="0";'
        '  d.style.transform="scale(.92) translateY(8px)";'
        '  requestAnimationFrame(function(){'
        '    d.style.transition="opacity .18s ease-out,transform .22s cubic-bezier(.16,1,.3,1)";'
        '    d.style.opacity="1";'
        '    d.style.transform="scale(1) translateY(0)";'
        '  });'
        '}'
        'function _toolsClose(){'
        '  var d=document.getElementById("tools-menu");'
        '  if(d.dataset.open!=="1")return;'
        '  window._toolsAnimating=true;'
        '  d.style.transition="opacity .14s ease-in,transform .16s ease-in";'
        '  d.style.opacity="0";'
        '  d.style.transform="scale(.94) translateY(6px)";'
        '  setTimeout(function(){'
        '    d.style.display="none";d.dataset.open="0";'
        '    window._toolsAnimating=false;'
        '  },160);'
        '}'
        'document.addEventListener("click",function(e){'
        '  var w=document.getElementById("tools-fab-wrap");'
        '  if(w&&!w.contains(e.target)){_toolsClose();}'
        '});'
        '</script>',
        '<div id="sql-popup-ov" style="display:none;position:fixed;inset:0;z-index:99999;'
        'background:rgba(0,0,0,.45);align-items:center;justify-content:center;" '
        'onmousedown="_ovMd(event)" onclick="_ovClick(event,_sqlClose)">'
        '<div style="background:#ffffff;border:1px solid #E2E8F0;border-radius:14px;'
        'padding:0;max-width:900px;width:92%;max-height:80vh;display:flex;'
        'flex-direction:column;box-shadow:0 24px 80px rgba(15,23,42,.2);">'
        '<div style="display:flex;justify-content:space-between;align-items:center;'
        'padding:14px 20px;border-bottom:1px solid #E2E8F0;flex-shrink:0;">'
        '<span style="font-size:.7rem;font-weight:700;text-transform:uppercase;'
        'letter-spacing:.12em;color:#6366F1;">SQL Query</span>'
        '<div style="display:flex;gap:8px;">'
        '<button onclick="_sqlClose()" style="background:#F1F5F9;border:1px solid '
        '#E2E8F0;color:#64748B;border-radius:6px;padding:4px 10px;'
        'font-size:.85rem;cursor:pointer;">&#x2715;</button>'
        '</div></div>'
        '<div id="sql-popup-body" style="margin:0;padding:20px;overflow:auto;'
        "font-family:'Geist Mono','Consolas',monospace;font-size:.8rem;line-height:1.75;"
        'color:#334155;word-break:break-word;flex:1;min-height:0;"></div>'
        '</div></div>'
        '<script>'
        # ── 공용 헬퍼: 팝업 바깥 클릭으로 닫을 때 "안에서 드래그→밖에서 mouseup"
        # 케이스에 닫히지 않도록 mousedown 시작 위치 기준으로 판단.
        # Pattern A (오버레이 onclick): onmousedown="_ovMd(event)" onclick="_ovClick(event,fn)"
        # Pattern B (document level !el.contains): _ovOutside(el, e) 호출로 판정.
        'window._ovMd=function(e){e.currentTarget._md=(e.target===e.currentTarget);};'
        'window._ovClick=function(e,fn){if(e.currentTarget._md&&e.target===e.currentTarget)fn();};'
        'window._ovOutside=function(el,e){return !el.contains(e.target)&&!el._mdInside;};'
        'document.addEventListener("mousedown",function(e){'
        '  document.querySelectorAll("[data-ov-track]").forEach(function(el){'
        '    el._mdInside=el.contains(e.target);'
        '  });'
        '},true);'
        'window.__PAGE_SQL__=window.__PAGE_SQL__||"";'
        'window.__PAGE_SQL_SECTIONS__=window.__PAGE_SQL_SECTIONS__||[];'
        'window.__PAGE_SQL_FNS__=window.__PAGE_SQL_FNS__||[];'
        'document.addEventListener("keydown",function(e){'
        'if(e.ctrlKey&&e.shiftKey&&(e.key==="S"||e.key==="s")){e.preventDefault();_sqlOpen();}'
        'if(e.key==="Escape")_sqlClose();'
        '});'
        # 칩 헤더 + body 블록 (function 정의와 SQL section 양쪽에서 동일하게 사용).
        'function _sqlBlock(label,title,bodyText,first){'
        '  var sec=document.createElement("div");'
        '  sec.style.cssText=first?"":("margin-top:22px;padding-top:18px;border-top:1px solid #E2E8F0;");'
        '  var hdr=document.createElement("div");'
        '  hdr.style.cssText="display:flex;align-items:center;gap:10px;margin-bottom:12px;";'
        '  var chip=document.createElement("span");'
        '  chip.textContent=label;'
        '  chip.style.cssText="display:inline-block;padding:3px 10px;background:#EEF2FF;color:#4F46E5;border-radius:6px;font-size:.62rem;font-weight:700;letter-spacing:.12em;font-family:Inter,Pretendard,sans-serif;";'
        '  var nm=document.createElement("span");'
        '  nm.textContent=title||"";'
        '  nm.style.cssText="font-weight:600;color:#0F172A;font-size:.86rem;font-family:\'Geist Mono\',\'Consolas\',monospace;";'
        '  hdr.appendChild(chip);hdr.appendChild(nm);sec.appendChild(hdr);'
        '  var pre=document.createElement("div");'
        '  pre.style.whiteSpace="pre-wrap";'
        '  pre.textContent=bodyText||"";'
        '  sec.appendChild(pre);'
        '  return sec;'
        '}'
        'function _sqlOpen(){'
        '  var body=document.getElementById("sql-popup-body");'
        '  body.innerHTML="";'
        '  var s=window.__PAGE_SQL__||"";'
        '  var sections=window.__PAGE_SQL_SECTIONS__||[];'
        '  var fns=window.__PAGE_SQL_FNS__||[];'
        '  if(!s&&!sections.length&&!fns.length){'
        '    body.textContent="(No SQL available for this page.)";'
        '  }else{'
        '    var rendered=0;'
        '    if(s){'
        '      var main=document.createElement("div");'
        '      main.style.whiteSpace="pre-wrap";'
        '      main.textContent=s;'
        '      body.appendChild(main);'
        '      rendered++;'
        '    }'
        '    sections.forEach(function(sec){'
        '      body.appendChild(_sqlBlock("QUERY",sec.title,sec.body,rendered===0));'
        '      rendered++;'
        '    });'
        '    fns.forEach(function(fn){'
        '      body.appendChild(_sqlBlock("FUNCTION",fn.schema+"."+fn.name,fn["def"],rendered===0));'
        '      rendered++;'
        '    });'
        '  }'
        '  document.getElementById("sql-popup-ov").style.display="flex";'
        '}'
        'function _sqlClose(){document.getElementById("sql-popup-ov").style.display="none";}'
                '</script>',
        # ── Tool popups (Decryption + Script Manager) ──
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">'
        '<style>'
        '#dec-win,#dec-win *{font-family:"Noto Sans KR","Segoe UI",system-ui,-apple-system,sans-serif;letter-spacing:-.01em;}'
        '#dec-win input[type=text]{transition:border-color .15s,box-shadow .15s,background .15s;}'
        '#dec-win input[type=text]:focus{border-color:#6366F1;box-shadow:0 0 0 3px rgba(99,102,241,.15);background:#fff;}'
        '.dec-btn{position:relative;display:inline-flex;align-items:center;justify-content:center;gap:5px;'
        'border:1px solid transparent;cursor:pointer;padding:0 11px;height:34px;border-radius:8px;font-weight:600;font-size:.76rem;'
        'letter-spacing:.01em;box-shadow:inset 0 1px 0 rgba(255,255,255,.35),0 1px 2px rgba(15,23,42,.06);'
        'transition:transform .12s cubic-bezier(.2,.8,.2,1),box-shadow .2s,filter .15s,background .2s,color .2s,border-color .2s;}'
        '.dec-btn:hover{transform:translateY(-1px);box-shadow:inset 0 1px 0 rgba(255,255,255,.45),0 3px 8px rgba(15,23,42,.1);}'
        '.dec-btn:active{transform:translateY(0);filter:brightness(.97);}'
        '.dec-btn:disabled{opacity:.5;cursor:not-allowed;transform:none;filter:grayscale(.2);}'
        '.dec-btn svg{width:13px;height:13px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;}'
        '.dec-btn-enc{background:rgba(99,102,241,.1);color:#4F46E5;border-color:rgba(99,102,241,.28);}'
        '.dec-btn-enc:hover{background:rgba(99,102,241,.18);border-color:rgba(99,102,241,.45);color:#4338CA;}'
        '.dec-btn-dec{background:rgba(245,158,11,.1);color:#B45309;border-color:rgba(245,158,11,.32);}'
        '.dec-btn-dec:hover{background:rgba(245,158,11,.18);border-color:rgba(245,158,11,.5);color:#92400E;}'
        '#dec-out{font-family:"JetBrains Mono","Consolas",monospace;}'
        '#dec-inp{font-family:"JetBrains Mono","Consolas",monospace;}'
        '</style>'
        '<div id="dec-win" style="display:none;position:fixed;z-index:9999;'
        'top:20%;left:50%;transform:translateX(-50%);width:560px;max-width:92vw;'
        'background:#fff;border-radius:16px;box-shadow:0 30px 70px rgba(15,23,42,.22),0 10px 24px rgba(15,23,42,.08);overflow:hidden;'
        'border:1px solid rgba(226,232,240,.9);">'
        '<div id="dec-hdr" style="display:flex;align-items:center;justify-content:space-between;'
        'padding:14px 20px;background:linear-gradient(180deg,#FAFBFF 0%,#F1F5F9 100%);'
        'border-bottom:1px solid #E2E8F0;cursor:move;user-select:none;">'
        '<span style="display:inline-flex;align-items:center;gap:8px;font-size:.88rem;font-weight:700;color:#4F46E5;letter-spacing:-.01em;">'
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6366F1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>'
        'Encrypt / Decrypt</span>'
        '<button onclick="document.getElementById(\'dec-win\').style.display=\'none\';" '
        'style="width:30px;height:30px;border:none;background:transparent;color:#94a3b8;'
        'font-size:1.4rem;cursor:pointer;border-radius:6px;line-height:1;transition:background .15s,color .15s;" '
        'onmouseover="this.style.background=\'#E2E8F0\';this.style.color=\'#475569\';" '
        'onmouseout="this.style.background=\'transparent\';this.style.color=\'#94a3b8\';">&times;</button></div>'
        '<div style="padding:20px;">'
        '<div style="font-size:.72rem;font-weight:600;color:#64748B;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;">Input</div>'
        '<div style="display:flex;gap:10px;align-items:stretch;">'
        '<input id="dec-inp" type="text" spellcheck="false" placeholder="Text to encrypt or decrypt..." '
        'style="flex:1;min-width:0;height:34px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;'
        'font-size:.8rem;padding:0 12px;outline:none;box-sizing:border-box;color:#0F172A;line-height:32px;">'
        '<button class="dec-btn dec-btn-enc" onclick="_doDec(\'encrypt\')" title="Encrypt (lock)">'
        '<svg viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>'
        'Encrypt</button>'
        '<button class="dec-btn dec-btn-dec" onclick="_doDec(\'decrypt\')" title="Decrypt (unlock)">'
        '<svg viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>'
        'Decrypt</button>'
        '</div>'
        '<div style="margin-top:8px;min-height:18px;"><span id="dec-st" style="font-size:.76rem;color:#94a3b8;"></span></div>'
        '<div style="font-size:.72rem;font-weight:600;color:#64748B;text-transform:uppercase;letter-spacing:.08em;margin:8px 0 6px;">Result</div>'
        '<input id="dec-out" type="text" readonly placeholder="Result will appear here..." '
        'style="width:100%;background:#F0FDF4;'
        'border:1px solid rgba(22,163,74,.25);border-radius:10px;color:#15803D;'
        'font-size:.86rem;padding:11px 13px;box-sizing:border-box;outline:none;">'
        '</div></div>'

        # ── Control Process popup ──
        '<div id="cp-win" style="display:none;position:fixed;z-index:9997;'
        'top:10%;left:50%;transform:translateX(-50%);width:860px;max-width:94vw;'
        'background:#fff;border-radius:14px;box-shadow:0 25px 60px rgba(0,0,0,.25);'
        'overflow:hidden;max-height:85vh;flex-direction:column;">'
        '<div id="cp-hdr" style="display:flex;align-items:center;justify-content:space-between;'
        'padding:12px 18px;background:#F8FAFC;border-bottom:1px solid #e5e7eb;cursor:move;user-select:none;">'
        '<div style="display:flex;align-items:center;gap:8px;">'
        '<span style="font-size:.85rem;font-weight:700;color:#6366F1;">Control Process</span>'
        '<button onclick="_cpRefresh()" id="cp-ref-btn" '
        'style="background:none;border:none;cursor:pointer;color:#94a3b8;font-size:1rem;'
        'padding:2px 6px;border-radius:4px;line-height:1;transition:color .2s;" '
        'title="Refresh">&#8635;</button>'
        '</div>'
        '<button onclick="_closeCtlProc();" '
        'style="width:30px;height:30px;border:none;background:transparent;color:#94a3b8;'
        'font-size:1.4rem;cursor:pointer;border-radius:4px;line-height:1;">&times;</button></div>'
        '<div style="padding:16px;overflow:auto;flex:1;min-height:0;">'
        '<div id="cp-tbl" style="margin-bottom:12px;">'
        '<div style="color:#94a3b8;font-size:.85rem;padding:20px;text-align:center;">Loading...</div></div>'
        '<div id="cp-log-wrap" style="display:none;border-top:1px solid #E2E8F0;padding-top:12px;margin-top:8px;">'
        '<div style="font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;'
        'color:#94a3b8;margin-bottom:8px;">Action Log</div>'
        '<div id="cp-log" style="max-height:140px;overflow-y:auto;font-family:monospace;'
        'font-size:.78rem;line-height:1.8;color:#475569;"></div>'
        '</div>'
        '</div></div>'

        '<div id="scr-win" style="display:none;position:fixed;z-index:9998;'
        'top:15%;left:50%;transform:translateX(-50%);width:740px;max-width:92vw;'
        'background:#fff;border-radius:14px;box-shadow:0 25px 60px rgba(0,0,0,.25);'
        'overflow:hidden;max-height:85vh;display:none;flex-direction:column;resize:both;min-width:400px;min-height:300px;">'
        '<div id="scr-hdr" style="display:flex;align-items:center;justify-content:space-between;'
        'padding:12px 18px;background:#F8FAFC;border-bottom:1px solid #e5e7eb;cursor:move;user-select:none;">'
        '<span style="font-size:.85rem;font-weight:700;color:#6366F1;">Script Manager</span>'
        '<div style="display:flex;gap:8px;align-items:center;">'

        '<button onclick="document.getElementById(\'scr-win\').style.display=\'none\';" '
        'style="width:30px;height:30px;border:none;background:transparent;color:#94a3b8;'
        'font-size:1.4rem;cursor:pointer;border-radius:4px;line-height:1;">&times;</button></div></div>'
        '<div style="padding:16px;display:flex;flex-direction:column;gap:8px;flex:1;min-height:0;">'
        '<div id="scr-schema-row" style="display:none;margin-bottom:2px;">'
        '<select id="scr-schema" style="padding:5px 10px;border-radius:6px;border:1px solid #CBD5E1;'
        'font-size:.8rem;color:#334155;background:#F8FAFC;outline:none;min-width:160px;">'
        '<option value="">-- schema --</option></select>'
        '<span style="font-size:.68rem;color:#94a3b8;margin-left:8px;">SET search_path</span>'
        '</div>'
        '<textarea id="scr-ed" spellcheck="false" rows="4" '
        'style="width:100%;background:#F8FAFC;border:1px solid #CBD5E1;border-radius:6px;'
        'font-family:monospace;font-size:.84rem;padding:9px;box-sizing:border-box;'
        'resize:vertical;outline:none;line-height:1.5;" placeholder="SELECT * FROM ..."></textarea>'
        '<div style="display:flex;gap:8px;align-items:center;">'
        '<button id="scr-run" onclick="_doScr()" style="background:#2845c8;color:#fff;border:none;'
        'border-radius:6px;padding:6px 18px;font-size:.84rem;cursor:pointer;">&#9654; Run</button>'
        '<button onclick="document.getElementById(\'scr-ed\').value=\'\';'
        'document.getElementById(\'scr-res\').innerHTML=\'\';'
        'document.getElementById(\'scr-st\').textContent=\'\';" '
        'style="background:transparent;color:#64748B;border:1px solid #CBD5E1;border-radius:6px;'
        'padding:6px 12px;font-size:.84rem;cursor:pointer;">Clear</button>'
        '<span id="scr-st" style="font-size:.75rem;color:#94a3b8;margin-left:4px;"></span></div>'
        '<div style="font-size:.68rem;color:#94a3b8;margin-top:2px;">Ctrl + Enter to run</div>'
        '<div id="scr-res" style="overflow:auto;max-height:40vh;border-radius:10px;"></div>'
        '</div></div>'

        '<script>'
        'var _TB="' + _UTILS_BASE + '";'
        'function _openDecrypt(){var w=document.getElementById("dec-win");document.getElementById("dec-inp").value="";document.getElementById("dec-out").value="";document.getElementById("dec-st").textContent="";w.style.top="20%";w.style.left="50%";w.style.transform="translateX(-50%)";w.style.display="block";_bringFront(w);}'
        'function _openScript(){'
        'var w=document.getElementById("scr-win");document.getElementById("scr-ed").value="";'
        'document.getElementById("scr-res").innerHTML="";document.getElementById("scr-st").textContent="";'
        'w.style.top="15%";w.style.left="50%";w.style.transform="translateX(-50%)";w.style.display="flex";_bringFront(w);'
        'fetch(_TB+"/api/script-schemas").then(function(r){return r.json();}).then(function(d){'
        'var row=document.getElementById("scr-schema-row");var sel=document.getElementById("scr-schema");'
        'if(d.ok&&d.schemas&&d.schemas.length){'
        'sel.innerHTML="<option value=\\"\\">public</option>"+d.schemas.map(function(s){'
        'return "<option value=\\""+s+"\\">"+s+"</option>";}).join("");'
        'row.style.display="flex";row.style.alignItems="center";row.style.gap="8px";'
        '}else{row.style.display="none";}'
        '}).catch(function(){document.getElementById("scr-schema-row").style.display="none";});'
        '}'
        'function _openCtlProc(){var w=document.getElementById("cp-win");w.style.top="10%";w.style.left="50%";w.style.transform="translateX(-50%)";w.style.display="flex";_bringFront(w);_cpRefresh();}'
        'function _closeCtlProc(){document.getElementById("cp-win").style.display="none";document.getElementById("cp-log").innerHTML="";document.getElementById("cp-log-wrap").style.display="none";}'

        'function _cpRefresh(){'
        'var btn=document.getElementById("cp-ref-btn");'
        'if(btn){btn.style.animation="spin .6s linear infinite";setTimeout(function(){btn.style.animation="";},600);}'
        'fetch(_TB+"/api/control-status").then(function(r){return r.json();}).then(function(d){'
        'if(!d.ok)return;_cpRender(d.components);'
        '}).catch(function(){});}'

        'function _cpRender(comps){'
        'var w=document.getElementById("cp-tbl");'
        'if(!comps||!comps.length){w.innerHTML="<div style=\\"color:#94a3b8;font-size:.85rem;padding:20px;text-align:center;\\">No components configured.</div>";return;}'
        'var th="padding:10px 14px;font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;background:#ECF0F7;color:#5F6B80;border-bottom:1px solid #D8DEE8;border-right:1px solid #DFE4ED;";'
        'var thL="padding:10px 14px;font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;background:#ECF0F7;color:#5F6B80;border-bottom:1px solid #D8DEE8;";'
        'var h="<table style=\\"width:100%;border-collapse:collapse;font-size:.82rem;\\">'
        '<thead><tr>"'
        '+"<th style=\\""+th+"\\">Component</th>"'
        '+"<th style=\\""+th+"\\">Status</th>"'
        '+"<th style=\\""+th+"\\">Port</th>"'
        '+"<th style=\\""+th+"\\">PID</th>"'
        '+"<th style=\\""+th+"\\">Uptime</th>"'
        '+"<th style=\\""+thL+"\\">Control</th>"'
        '+"</tr></thead><tbody>";'
        'comps.forEach(function(c){'
        'var st=c.status.toLowerCase();'
        'var badge="";'
        'if(st==="running")badge="<span style=\\"background:#dcfce7;color:#15803d;border:1px solid #bbf7d0;padding:2px 10px;border-radius:9999px;font-size:.72rem;font-weight:600;\\">RUNNING</span>";'
        'else if(st==="stopped")badge="<span style=\\"background:#fee2e2;color:#dc2626;border:1px solid #fecaca;padding:2px 10px;border-radius:9999px;font-size:.72rem;font-weight:600;\\">STOPPED</span>";'
        'else badge="<span style=\\"background:#F1F5F9;color:#64748B;border:1px solid rgba(100,116,139,.15);padding:2px 10px;border-radius:9999px;font-size:.72rem;font-weight:600;\\">"+c.status.toUpperCase()+"</span>";'
        'var extra="";'
        'if(c.dg_name)extra="<div style=\\"font-size:.68rem;color:#94a3b8;margin-top:1px;\\">"+c.dg_name+(c.heap?" &middot; Heap: "+c.heap:"")+"</div>";'
        'var ctrl="<div style=\\"display:flex;gap:5px;justify-content:center;\\">";'
        'var bs="padding:3px 12px;border-radius:5px;font-size:.72rem;font-weight:600;cursor:pointer;border:1px solid transparent;transition:all .15s;";'
        'if(st==="running"){'
        'ctrl+="<button style=\\""+bs+"background:#FEF2F2;color:#DC2626;border-color:rgba(220,38,38,.2);\\" onclick=\\"_cpAction(\'"+c.id+"\',\'stop\',\'"+c.name+"\')\\" onmouseover=\\"this.style.background=\'#FEE2E2\'\\" onmouseout=\\"this.style.background=\'#FEF2F2\'\\">Stop</button>";'
        'ctrl+="<button style=\\""+bs+"background:#EEF2FF;color:#6366F1;border-color:rgba(99,102,241,.25);\\" onclick=\\"_cpAction(\'"+c.id+"\',\'restart\',\'"+c.name+"\')\\" onmouseover=\\"this.style.background=\'#E0E7FF\'\\" onmouseout=\\"this.style.background=\'#EEF2FF\'\\">Restart</button>";'
        '}else if(st==="stopped"){'
        'ctrl+="<button style=\\""+bs+"background:#F0FDF4;color:#15803D;border-color:rgba(22,163,74,.25);\\" onclick=\\"_cpAction(\'"+c.id+"\',\'start\',\'"+c.name+"\')\\" onmouseover=\\"this.style.background=\'#DCFCE7\'\\" onmouseout=\\"this.style.background=\'#F0FDF4\'\\">Start</button>";'
        '}else{ctrl+="<span style=\\"color:#94a3b8;font-size:.75rem;\\">-</span>";}'
        'ctrl+="</div>";'
        'var td="padding:10px 14px;text-align:center;border-bottom:1px solid #E5E7EB;border-right:1px solid #EBEDF1;";'
        'var tdL="padding:10px 14px;text-align:center;border-bottom:1px solid #E5E7EB;";'
        'h+="<tr id=\\"cp-r-"+c.id+"\\">"'
        '+"<td style=\\""+td+"font-weight:600;\\">"+c.name+extra+"</td>"'
        '+"<td style=\\""+td+"\\">"+badge+"</td>"'
        '+"<td style=\\""+td+"\\">"+c.port+"</td>"'
        '+"<td style=\\""+td+"\\">"+c.pid+"</td>"'
        '+"<td style=\\""+td+"\\">"+c.uptime+"</td>"'
        '+"<td style=\\""+tdL+"\\">"+ctrl+"</td></tr>";'
        '});'
        'h+="</tbody></table>";w.innerHTML=h;}'

        'function _cpLog(msg,ok){'
        'var lw=document.getElementById("cp-log-wrap");lw.style.display="";'
        'var lg=document.getElementById("cp-log");'
        'var ts=new Date().toLocaleTimeString();'
        'var c=ok?"#15803D":"#DC2626";'
        'lg.innerHTML="<div style=\\"color:"+c+";\\">["+ts+"] "+msg+"</div>"+lg.innerHTML;}'

        'function _cpAction(id,action,name){'
        'var label=action.charAt(0).toUpperCase()+action.slice(1);'
        'if(action==="stop"||action==="restart"){if(!confirm(name+" "+label+" 하시겠습니까?"))return;}'
        'var row=document.getElementById("cp-r-"+id);'
        'if(row){var cell=row.cells[5];cell.innerHTML='
        '"<div style=\\"display:flex;align-items:center;justify-content:center;gap:5px;\\">"'
        '+"<span style=\\"display:inline-block;width:12px;height:12px;border:2px solid #6366F1;border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite;\\"></span>"'
        '+"<span style=\\"font-size:.72rem;color:#6366F1;font-weight:600;\\">"+label+"...</span></div>";}'
        'fetch(_TB+"/api/control-action",{method:"POST",headers:{"Content-Type":"application/json"},'
        'body:JSON.stringify({id:id,action:action})})'
        '.then(function(r){return r.json();})'
        '.then(function(d){_cpLog(name+" "+label+": "+d.message,d.ok);_cpRefresh();})'
        '.catch(function(e){_cpLog(name+" "+label+" failed: "+e,false);_cpRefresh();});}'
        'function _bringFront(el){el.style.zIndex=++_toolZ;}'
        'var _toolZ=9998;'
        'function _doDec(action){'
        'action=action||"decrypt";'
        'var inp=document.getElementById("dec-inp").value.trim();'
        'var st=document.getElementById("dec-st");var out=document.getElementById("dec-out");'
        'if(!inp){st.textContent="Enter text.";st.style.color="#f59e0b";return;}'
        'var label=action.charAt(0).toUpperCase()+action.slice(1)+"ing...";'
        'st.textContent=label;st.style.color="#6b7280";'
        'fetch(_TB+"/api/decrypt",{method:"POST",headers:{"Content-Type":"application/json"},'
        'body:JSON.stringify({text:inp,action:action})})'
        '.then(function(r){return r.json();})'
        '.then(function(d){if(d.ok){out.value=d.result;'
        'st.textContent=(action==="encrypt"?"Encrypted":"Decrypted");st.style.color="#22c55e";}'
        'else{out.value="";st.textContent=d.error||"Error";st.style.color="#ef4444";}'
        '}).catch(function(){st.textContent="Failed";st.style.color="#ef4444";});}'
        'function _doScr(){'
        'var ed=document.getElementById("scr-ed"),st=document.getElementById("scr-st"),'
        'rw=document.getElementById("scr-res"),sql=ed?ed.value.trim():"";'
        'if(!sql){st.textContent="SQL required";st.style.color="#f59e0b";return;}'
        'var btn=document.getElementById("scr-run");'
        'if(btn){btn.disabled=true;btn.style.opacity=".5";}'
        'st.textContent="Running...";st.style.color="#6b7280";var t0=Date.now();'
        'var ssel=document.getElementById("scr-schema");'
        'var schema=(ssel&&ssel.value)?ssel.value:"";'
        'fetch(_TB+"/api/script-run",{method:"POST",headers:{"Content-Type":"application/json"},'
        'body:JSON.stringify({sql:sql,schema:schema})})'
        '.then(function(r){return r.json();})'
        '.then(function(d){if(btn){btn.disabled=false;btn.style.opacity="1";}'
        'var el=(Date.now()-t0)+"ms";'
        'st.textContent=(d.ok?d.rows+" row(s)":"Error")+" \xb7 "+el;'
        'st.style.color=d.ok?"#22c55e":"#ef4444";if(rw)rw.innerHTML=d.html||"";'
        '}).catch(function(){if(btn){btn.disabled=false;btn.style.opacity="1";}'
        'st.textContent="Failed";st.style.color="#ef4444";});}'
        'document.addEventListener("keydown",function(e){'
        'if(document.getElementById("scr-win").style.display!=="none"'
        '&&(e.ctrlKey||e.metaKey)&&e.key==="Enter"){e.preventDefault();_doScr();}});'
        '(function(){function makeDrag(hdr,win){'
        'var ox=0,oy=0,mx=0,my=0;'
        'hdr.onmousedown=function(e){e.preventDefault();if(win.style.transform&&win.style.transform!=="none"){var r=win.getBoundingClientRect();win.style.left=r.left+"px";win.style.top=r.top+"px";win.style.transform="none";}mx=e.clientX;my=e.clientY;'
        '_bringFront(win);'
        'document.onmousemove=function(ev){ox=mx-ev.clientX;oy=my-ev.clientY;mx=ev.clientX;my=ev.clientY;'
        'win.style.top=(win.offsetTop-oy)+"px";win.style.left=(win.offsetLeft-ox)+"px";};'
        'document.onmouseup=function(){document.onmousemove=null;document.onmouseup=null;};};}'
        'makeDrag(document.getElementById("dec-hdr"),document.getElementById("dec-win"));'
        'makeDrag(document.getElementById("scr-hdr"),document.getElementById("scr-win"));'
        'makeDrag(document.getElementById("cp-hdr"),document.getElementById("cp-win"));'
        '})();'
        '</script>',
    _get_svc_modal_html(),
    ])


def _page(active, title, body, refresh=None, topbar=True, topbar_title=None, topbar_help_key=None):
    meta = ('<meta http-equiv="refresh" content="%d">' % refresh) if refresh else ''
    # topbar 모드일 때 본문 안의 기존 _page_title_html(.page-hdr) 자동 숨김
    if topbar:
        if topbar_title is None:
            topbar_title = title
        if topbar_help_key is None:
            topbar_help_key = active
    # 페이지 상단(탭) 제목 한글화 — 사이드바 라벨은 변경 없음
    title        = _kr_title(title)
    topbar_title = _kr_title(topbar_title)
    theme_js = (
        '<script>'
        'function tbSort(th){var tbl=th.closest("table");var tb=tbl.querySelector("tbody");'
        'var idx=Array.from(th.parentNode.children).indexOf(th);'
        'var asc=th.dataset.sort!=="asc";'
        'th.closest("thead").querySelectorAll("th").forEach(function(t){t.dataset.sort="";var ic=t.querySelector(".sort-ic");if(ic)ic.textContent="";});'
        'th.dataset.sort=asc?"asc":"desc";'
        'var ic=th.querySelector(".sort-ic");if(ic)ic.textContent=asc?" \u25b2":" \u25bc";'
        'var allRows=Array.from(tb.querySelectorAll("tr"));'
        'var visible=allRows.filter(function(r){return r.style.display!=="none";});'
        'var hidden=allRows.filter(function(r){return r.style.display==="none";});'
        'visible.sort(function(a,b){var av=a.cells[idx]?a.cells[idx].textContent.trim():"";var bv=b.cells[idx]?b.cells[idx].textContent.trim():"";var an=/^-?[\\d,]+\\.?\\d*$/.test(av)?parseFloat(av.replace(/,/g,"")):NaN;var bn=/^-?[\\d,]+\\.?\\d*$/.test(bv)?parseFloat(bv.replace(/,/g,"")):NaN;if(!isNaN(an)&&!isNaN(bn))return asc?an-bn:bn-an;return asc?av.localeCompare(bv):bv.localeCompare(av);});'
        'while(tb.firstChild)tb.removeChild(tb.firstChild);'
        'visible.forEach(function(r){tb.appendChild(r);});'
        'hidden.forEach(function(r){tb.appendChild(r);});}'
        '</script>'
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
        meta,
        '<title>', title, ' - MaxGauge Inspector</title>',
        '<link rel="preconnect" href="https://fonts.googleapis.com">',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        '<link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css" rel="stylesheet">',
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">',
        '<style>', _CSS, '</style>',
        theme_js,
        '<script>'
        '(function(){'
        'var _f=window.fetch;'
        'window.fetch=function(){'
        'return _f.apply(this,arguments).then(function(r){'
        'if(r.status===401){window.location.replace("/MAXGAUGE/labs/");return new Promise(function(){});}'
        'return r;'
        '});'
        '};'
        '})();'
        '</script>',
        '</head><body>',
        '<div class="layout">',
        _sidebar(active),
        '<main class="main">',
        # ── topbar (옵션: 본문 위 헤더 띠) ──
        ('<div class="topbar" style="display:flex;align-items:center;justify-content:space-between;'
         'height:52px;padding:0 36px;background:#ffffff;border-bottom:1px solid #E2E8F0;'
         'position:sticky;top:0;z-index:50;">'
         '<div style="display:flex;align-items:center;gap:10px;">'
         '<span style="font-size:1.05rem;font-weight:700;color:#0F172A;letter-spacing:-.01em;'
         "font-family:Inter,Pretendard,sans-serif;\">" + (topbar_title or title) + '</span>'
         + (_help_icon(*_HELP[topbar_help_key], gray=True) if topbar_help_key and topbar_help_key in _HELP else '')
         + '</div>'
        ) if topbar else '',
        # ── Tools dropdown + Inspector History (topbar 모드면 inline, 아니면 우상단 fixed) ──
        ('<div style="display:flex;gap:8px;align-items:center;">'
         if topbar else
         '<div style="position:fixed;top:14px;right:20px;z-index:100;display:flex;gap:8px;align-items:center;">'
        ),
        # Inspector History button
        # 토픽바(흰 배경) 에서 식별성 좋도록 인디고 chip 스타일.
        # 기본: indigo-50 bg / indigo-200 border / indigo-600 text.
        # 호버: solid indigo-500 + white text.
        '<a href="' + _UTILS_BASE + '/history/os/cpu" '
        'style="display:inline-block;padding:6px 16px;'
        'background:#EEF2FF;border:1px solid #C7D2FE;'
        'color:#4F46E5;border-radius:8px;font-size:.78rem;font-weight:600;'
        'text-decoration:none;letter-spacing:.02em;transition:all .15s;'
        'font-family:Inter,Pretendard,sans-serif;" '
        'onmouseover="this.style.background=\'#6366F1\';this.style.borderColor=\'#6366F1\';this.style.color=\'#ffffff\';" '
        'onmouseout="this.style.background=\'#EEF2FF\';this.style.borderColor=\'#C7D2FE\';this.style.color=\'#4F46E5\';">'
        'Inspector History</a>',
        # Back to Labs button (target=_top breaks out of iframe)
        '<a href="/MAXGAUGE/labs/" target="_top" '
        'style="display:inline-block;padding:6px 16px;'
        'background:#EEF2FF;border:1px solid #C7D2FE;'
        'color:#4F46E5;border-radius:8px;font-size:.78rem;font-weight:600;'
        'text-decoration:none;letter-spacing:.02em;transition:all .15s;'
        'font-family:Inter,Pretendard,sans-serif;" '
        'onmouseover="this.style.background=\'#6366F1\';this.style.borderColor=\'#6366F1\';this.style.color=\'#ffffff\';" '
        'onmouseout="this.style.background=\'#EEF2FF\';this.style.borderColor=\'#C7D2FE\';this.style.color=\'#4F46E5\';">'
        '&#8592; Labs</a>',
        '</div>',
        # topbar 모드면 topbar wrapper close
        ('</div>' if topbar else ''),
        # (Tools dropdown moved to bottom-right FAB; outside-click handler is added later)
        '',
        _HELP_JS,
        '<div class="content-wrap">', body, '</div>',
        _tools_fab_block(),
        '</main>',
        '</div></body></html>',
    ])


def _get_svc_modal_html():
    try:
        from pages.alert_svc_config import alert_svc_modal_html
        return alert_svc_modal_html()
    except Exception:
        return ''
