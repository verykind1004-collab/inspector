# -*- coding: utf-8 -*-
import sys
import json
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

import config_loader

_cfg            = config_loader.load()
UTILS_PORT      = config_loader.get_utils_port(_cfg)
UTILS_BASE      = config_loader.get_base_path(_cfg) + config_loader.get_check_path(_cfg)

# Inject UTILS_BASE into html_helpers before importing pages
import html_helpers as _html_helpers
_html_helpers.set_globals(UTILS_BASE, config_loader.get_platformjs_port(_cfg))

import auth as _auth_module
_auth_module.set_utils_base(UTILS_BASE)
_auth_module.set_cookie_name(UTILS_PORT)

# ── Auth ─────────────────────────────────────────────────────────────────────
from auth import (
    _is_authenticated, _get_session_token, _delete_session, _COOKIE_NAME,
    _create_session, _get_session_info, page_login, verify_credential,
    _AUTH_USER, _AUTH_HASH, _AUTH_SALT, _SESSION_TTL,
)

LABS_BASE = '/MAXGAUGE/labs'

# ── Service config ─────────────────────────────────────────────────────────
from service_config import load_service_config, save_service_config

# ── History / scheduler ────────────────────────────────────────────────────
from history import _ensure_partition, _scheduler_loop
import threading as _threading

# ── Pages ──────────────────────────────────────────────────────────────────
from pages.overview  import page_overview, page_services, _services_table_html, api_tablespace, api_vitals, api_svc_uptimes
from pages.partition import (
    page_partition_create, page_partition_drop, page_partition_time,
    api_drop_list, api_drop_partitions, api_drop_partitions_status,
    api_create_partition, api_create_procedure,
)
from pages.summary   import page_summary_10min, page_summary_1hour
from pages.process   import page_process_gather, page_process_param, api_log_tail
from pages.dgxml_modify import api_dgxml_param_search, api_dgxml_param_save
from pages.disk      import (
    page_disk_capacity, page_disk_vacuum_age,
    page_disk_top_segment, page_disk_temp_table,
    api_vacuum_freeze, api_vacuum_freeze_status, api_age_card,
    api_temp_table_drop_all, api_temp_table_drop_status,
    api_vacuum_table, api_vacuum_table_status,
)
from pages.session       import page_session
from pages.query         import page_query
from pages.license       import page_license
from pages.license_check import page_license_check
from pages.report import page_report
from pages.alert         import page_alert, api_alert_times
from pages.alarm_history import page_alarm_history
from pages.alert_svc_config import api_alert_svc_read, api_alert_svc_save, api_alert_svc_copy
from pages.config_page   import page_config, page_config_in_history
from pages.config_page   import api_connection_test
from pages.history_page  import (
    api_insp_create_schema,
    page_history, api_history_data,
    api_history_instances, api_history_range,
    api_insp_init_tables, api_insp_drop_tables,
    api_insp_config_save, api_insp_config_load,
    api_insp_table_status, api_insp_create_one_table,
)
from pages.script_manager import api_script_run, api_script_schemas
from pages.decrypt import api_decrypt
from pages.config_dump    import page_config_dump, api_config_dump, api_config_restore
from pages.control_process import api_control_status, api_control_action
from pages.tablespace import (
    api_tablespace_data, api_tablespace_trend, api_tablespace_refresh,
)
from pages.history_views import (
    page_history_os_cpu, page_history_os_memory,
    page_history_disk_tbs, page_history_process_status,
    page_history_process_qcnt, page_history_process_heap,
    api_history_os, api_history_tbs, api_history_service, api_history_heap,
    api_history_qcnt, api_history_proc,
)


def _trigger_maxspace_reset():
    """Labs Configuration > Repository SAVE 직후 MaxSpace 풀/캐시를 즉시 무효화.

    MaxSpace 는 service_config.json 의 repository 섹션을 기반으로 풀을 만들기 때문에
    Repository 가 변경되면 다음 build_data 호출 시 자동 invalidation 되긴 하지만,
    캐시(_cache, _trend_cache) 가 TTL 안에 있으면 옛 데이터가 그대로 반환됨.
    그래서 SAVE 후 즉시 reset endpoint 를 호출해 캐시·풀을 폐기시킨다.
    실패는 silently — MaxSpace 가 안 떠 있어도 SAVE 자체는 성공해야 함."""
    import os as _os
    import json as _json
    import urllib.request as _ur
    try:
        labs_dir = config_loader.get_labs_dir(_cfg)
        ts_port  = config_loader.get_tablespace_port(_cfg)
        ts_cfg_path = _os.path.join(labs_dir, 'MaxSpace', 'conf', 'tablespace_config.json')
        if not _os.path.isfile(ts_cfg_path):
            return
        with open(ts_cfg_path) as _f:
            _ts = _json.load(_f)
        token = _ts.get('refresh_token', '') or ''
        if not token:
            return
        url = 'http://127.0.0.1:%d/api/reset?token=%s' % (int(ts_port), token)
        req = _ur.Request(url, method='POST')
        _ur.urlopen(req, timeout=3).read()
        sys.stdout.write('[python-utils] MaxSpace reset triggered\n')
        sys.stdout.flush()
    except Exception as _e:
        sys.stdout.write('[python-utils] MaxSpace reset trigger failed: %s\n' % _e)
        sys.stdout.flush()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stdout.write("[python-utils] %s\n" % (fmt % args))
        sys.stdout.flush()

    def _send(self, code, ctype, body):
        if not isinstance(body, bytes):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, url):
        self.send_response(302)
        self.send_header("Location", url)
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        # Fresh-navigation guard (block, no redirect).
        # /MAXGAUGE/utils/* 는 Labs 포털의 iframe 안에서만 접근 허용. 주소창 직접
        # 입력 / 새 탭 / 북마크처럼 top-level navigation 으로 들어오면 화면 자체를
        # 보여주지 않고 404 만 반환. (LABS 로 redirect 안 함 — 사용자가 의도적으로
        # /utils URL 을 외부에 노출되지 않게 하려는 정책.)
        sfs = self.headers.get("Sec-Fetch-Site", "")
        sfm = self.headers.get("Sec-Fetch-Mode", "")
        sfd = self.headers.get("Sec-Fetch-Dest", "")
        ref = self.headers.get("Referer", "")
        if sfs:
            is_in_app_nav = (sfs == "same-origin")
        else:
            is_in_app_nav = bool(ref) and (
                "/MAXGAUGE/utils" in ref or "/labs" in ref
            )
        if sfm or sfd:
            is_doc_nav = (sfm == "navigate" and sfd == "document")
        else:
            is_doc_nav = not (path.startswith("/api/") or path.startswith("/labs/api/"))
        is_fresh_nav = is_doc_nav and not is_in_app_nav
        if is_fresh_nav \
                and not path.startswith("/api/") and not path.startswith("/labs/api/"):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path == "/login":
            self._redirect(LABS_BASE)
            return

        if path == "/logout":
            token = _get_session_token(self)
            if token:
                _delete_session(token)
            self.send_response(302)
            self.send_header("Set-Cookie", "%s=; Path=/; Max-Age=0; HttpOnly" % _COOKIE_NAME)
            self.send_header("Location", LABS_BASE)
            self.end_headers()
            return

        # Labs: whoami endpoint (public — returns 200 always so clients can tell
        # logged-in vs not without hitting auth redirects).
        if path == "/labs/api/whoami":
            info = _get_session_info(self)
            if info:
                self._send(200, "application/json", json.dumps({
                    "ok": True, "id": info.get("user_id", ""),
                    "role": info.get("role", ""),
                }))
            else:
                self._send(200, "application/json", json.dumps({"ok": False}))
            return

        # Labs: nginx auth_request gateway. 세션 유효 → 204, 무효 → 401.
        # Bodyless; 보호 대상 리소스(/labs/maxpaper/ 등) 프록시 앞단에서 호출됨.
        if path == "/labs/api/check-auth":
            if _get_session_info(self) is not None:
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                self.send_response(401)
                self.send_header("Content-Length", "0")
                self.end_headers()
            return

        if path != "/api/ping" and not _is_authenticated(self):
            if path.startswith("/api/") or path.startswith("/labs/api/"):
                self._send(401, "application/json",
                    json.dumps({"ok": False, "error": "not authenticated"}))
            else:
                self._redirect(UTILS_BASE + "/login")
            return

        # Gate: if repository DB is not configured, render a friendly
        # message pointing the operator to Labs → Configuration (FAB).
        # Allow the labs api and a small set of internal endpoints to pass.
        _config_allowed = ("/labs/api/config", "/api/config", "/api/connection-test",
                           "/api/ping", "/logout")
        _repo = load_service_config().get("repository", {})
        _unconfigured = not _repo.get("ip") or not _repo.get("sid")
        if _unconfigured and path not in _config_allowed:
            self._send(200, "text/html; charset=utf-8",
                '<!DOCTYPE html><html><head><meta charset="UTF-8">'
                '<title>Setup required</title></head>'
                '<body style="font-family:system-ui,sans-serif;padding:48px;text-align:center;color:#1a1d2e;">'
                '<h2 style="color:#6c54e8;margin-bottom:12px;">Configuration 필요</h2>'
                '<p>Repository DB 정보가 설정되지 않았습니다.</p>'
                '<p><a href="/labs" target="_top" '
                'style="color:#6c54e8;text-decoration:none;font-weight:600;">'
                '→ Labs로 이동하여 Configuration 완료</a></p>'
                '</body></html>')
            return

        qs = self.path
        def _qs(key):
            return parse_qs(qs.split("?", 1)[1] if "?" in qs else "").get(key, [""])[0]

        routes = {
            "/":                      lambda: page_overview(),
            "/services":              lambda: page_services(),
            "/partition/create":      lambda: page_partition_create(),
            "/partition/drop":        lambda: page_partition_drop(),
            "/partition/time":        lambda: page_partition_time(),
            "/summary/10min":         lambda: page_summary_10min(),
            "/summary/1hour":         lambda: page_summary_1hour(),
            "/process/gather":        lambda: page_process_gather(self.path),
            "/api/log-tail":           lambda: self._send(200,"application/json",api_log_tail(_qs("path"),_qs("offset"))),
            "/process/param":         lambda: page_process_param(self.path),
            "/disk/capacity":         lambda: page_disk_capacity(),
            "/disk/vacuum-age":       lambda: page_disk_vacuum_age(),
            "/disk/top-segment":      lambda: page_disk_top_segment(),
            "/disk/temp-table":       lambda: page_disk_temp_table(),
            "/session":               lambda: page_session(),
            "/query":                 lambda: page_query(),
            "/license":               lambda: page_license(),
            "/license-check":         lambda: page_license_check(),
            "/report":                lambda: self._send(200, "text/html; charset=utf-8", page_report()),
            "/alert":                 lambda: page_alert(),
            "/labs/api/config":       lambda: json.dumps(load_service_config()),
            "/labs/api/tablespace/data":    lambda: api_tablespace_data(),
            "/labs/api/tablespace/trend":   lambda: api_tablespace_trend(self.path),
            "/labs/api/tablespace/refresh": lambda: api_tablespace_refresh(),
            "/config-dump":            lambda: page_config_dump(),
            "/api/control-status":     lambda: api_control_status(),
            "/history/os/cpu":         lambda: page_history_os_cpu(),
            "/history/os/memory":      lambda: page_history_os_memory(),
            "/history/disk/tbs":       lambda: page_history_disk_tbs(self.path),
            "/history/process/status":  lambda: page_history_process_status(),
            "/history/process/qcnt":    lambda: page_history_process_qcnt(),
            "/history/process/heap":    lambda: page_history_process_heap(),
            "/api/history-os":          lambda: api_history_os(self.path),
            "/api/history-tbs":         lambda: api_history_tbs(self.path),
            "/api/history-service":     lambda: api_history_service(self.path),
            "/api/history-heap":       lambda: api_history_heap(self.path),
            "/api/history-qcnt":       lambda: api_history_qcnt(self.path),
            "/api/history-proc":       lambda: api_history_proc(self.path),
            "/history":               lambda: page_history(self.path) if "type=" in self.path else self._redirect(UTILS_BASE + "/history/os/cpu"),
            "/history/configuration":  lambda: page_config_in_history(saved="saved=1" in self.path),
            "/history/alarm":          lambda: page_alarm_history(self.path),
            "/api/metrics":           lambda: json.dumps({"status": "ok", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}),
            "/api/ping":              lambda: json.dumps({"status": "ok"}),
            "/api/history-data":      lambda: api_history_data(self.path),
            "/api/history-instances": lambda: api_history_instances(),
            "/api/history-range":     lambda: api_history_range(self.path),
            "/api/services":          lambda: json.dumps({"html": _services_table_html()}),
            "/api/svc-uptimes":       lambda: api_svc_uptimes(),
            "/api/tablespace":        lambda: api_tablespace(force=_qs("force")=="1"),
            "/api/vitals":            lambda: api_vitals(),
            "/api/drop-list":         lambda: api_drop_list(_qs("db_id")),
            "/api/config":            lambda: json.dumps(load_service_config()),
            "/api/vacuum-freeze":     lambda: api_vacuum_freeze(),
            "/api/vacuum-freeze-status": lambda: api_vacuum_freeze_status(),
            "/api/vacuum-table":          lambda: api_vacuum_table(),
            "/api/vacuum-table-status":   lambda: api_vacuum_table_status(),
            "/api/age-card":          lambda: api_age_card(),
            "/api/temp-table-drop-all":    lambda: api_temp_table_drop_all(),
            "/api/temp-table-drop-status": lambda: api_temp_table_drop_status(),
            "/api/drop-partitions":   lambda: api_drop_partitions(_qs("db_id")),
            "/api/drop-partitions-status": lambda: api_drop_partitions_status(),
            "/api/create-partition":  lambda: api_create_partition(_qs("instance_name"), _qs("date_from"), _qs("date_to")),
            "/api/create-procedure":  lambda: api_create_procedure(),
            "/api/alert-times":       lambda: api_alert_times(_qs("inst"), _qs("alarm")),
            "/api/connection-test":   lambda: api_connection_test(),
            "/api/dgxml-param-search": lambda: api_dgxml_param_search(_qs("param")),
            "/api/alert-svc-read":     lambda: api_alert_svc_read(_qs("kind")),
            "/api/insp-config":      lambda: api_insp_config_load(),
            "/api/insp-table-status": lambda: api_insp_table_status(),
            "/api/script-schemas":   lambda: api_script_schemas(),
        }
        handler = routes.get(path)
        if handler:
            ct = "application/json" if path.startswith("/api/") else "text/html; charset=utf-8"
            self._send(200, ct, handler())
        else:
            self._send(404, "text/plain", "Not Found")

    def do_POST(self):
        path = self.path.split("?")[0]

        if path == "/login":
            self._redirect(LABS_BASE)
            return

        # ── Labs API: login / logout (no auth required) ─────────────────────
        if path == "/labs/api/login":
            length = int(self.headers.get("Content-Length", 0))
            raw    = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8", errors="ignore")) if raw else {}
            except Exception:
                payload = {}
            uid = (payload.get("id") or payload.get("username") or "").strip()
            pw  = payload.get("password") or payload.get("pw") or ""
            ok, role, err = verify_credential(uid, pw)
            if ok:
                token = _create_session(user_id=uid, role=role)
                self.send_response(200)
                self.send_header("Set-Cookie",
                    "%s=%s; Path=/; HttpOnly; SameSite=Lax" % (_COOKIE_NAME, token))
                self.send_header("Content-Type", "application/json")
                body = json.dumps({"ok": True, "role": role, "id": uid}).encode("utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self._send(200, "application/json",
                    json.dumps({"ok": False, "error": err or "invalid credentials"}))
            return

        if path == "/labs/api/logout":
            token = _get_session_token(self)
            if token:
                _delete_session(token)
            self.send_response(200)
            self.send_header("Set-Cookie",
                "%s=; Path=/; Max-Age=0; HttpOnly" % _COOKIE_NAME)
            self.send_header("Content-Type", "application/json")
            body = b'{"ok":true}'
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if not _is_authenticated(self):
            if path.startswith("/api/") or path.startswith("/labs/api/"):
                self._send(401, "application/json",
                    json.dumps({"ok": False, "error": "not authenticated"}))
            else:
                self._redirect(LABS_BASE)
            return

        # Gate: unconfigured → only allow labs config POST (save initial settings)
        _repo_p = load_service_config().get("repository", {})
        if (not _repo_p.get("ip") or not _repo_p.get("sid")) and path != "/labs/api/config":
            self._send(403, "application/json",
                json.dumps({"ok": False, "error": "Repository not configured"}))
            return

        if path == "/api/decrypt":
            length = int(self.headers.get("Content-Length", 0))
            raw    = self.rfile.read(length)
            self._send(200, "application/json", api_decrypt(raw))
            return

        if path == "/api/alert-svc-save":
            length = int(self.headers.get("Content-Length", 0))
            raw    = self.rfile.read(length)
            self._send(200, "application/json", api_alert_svc_save(raw))
            return

        if path == "/api/alert-svc-copy":
            length = int(self.headers.get("Content-Length", 0))
            raw    = self.rfile.read(length)
            self._send(200, "application/json", api_alert_svc_copy(raw))
            return

        if path == "/api/dgxml-param-save":
            length = int(self.headers.get("Content-Length", 0))
            raw    = self.rfile.read(length)
            self._send(200, "application/json", api_dgxml_param_save(raw))
            return

        if path == "/api/script-run":
            length = int(self.headers.get("Content-Length", 0))
            raw    = self.rfile.read(length)
            self._send(200, "application/json", api_script_run(raw))
            return

        if path == "/api/control-action":
            length = int(self.headers.get("Content-Length", 0))
            raw    = self.rfile.read(length)
            self._send(200, "application/json", api_control_action(raw))
            return

        if path == "/api/insp-create-schema":
            self._send(200, "application/json", api_insp_create_schema())
            return

        if path == "/api/insp-init-tables":
            self._send(200, "application/json", api_insp_init_tables())
            return

        if path == "/api/insp-drop-tables":
            self._send(200, "application/json", api_insp_drop_tables())
            return

        if path == "/api/insp-config-save":
            length = int(self.headers.get("Content-Length", 0))
            raw    = self.rfile.read(length)
            self._send(200, "application/json", api_insp_config_save(raw))
            return

        if path == "/api/insp-create-one-table":
            length = int(self.headers.get("Content-Length", 0))
            raw    = self.rfile.read(length)
            self._send(200, "application/json", api_insp_create_one_table(raw))
            return

        if path == "/api/config-dump":
            length = int(self.headers.get("Content-Length", 0))
            raw    = self.rfile.read(length)
            self._send(200, "application/json", api_config_dump(raw))
            return

        if path == "/api/config-restore":
            length = int(self.headers.get("Content-Length", 0))
            raw    = self.rfile.read(length)
            self._send(200, "application/json", api_config_restore(raw))
            return

        if path in ("/config", "/labs/api/config"):
            length = int(self.headers.get("Content-Length", 0))
            raw    = self.rfile.read(length)
            ctype  = (self.headers.get("Content-Type") or "").lower()

            # Labs posts JSON; legacy /config posts form-urlencoded.
            if "application/json" in ctype:
                try:
                    j = json.loads(raw.decode("utf-8", errors="ignore")) if raw else {}
                except Exception:
                    j = {}
                # Normalize JSON → same shape parse_qs produces (values as lists)
                data = {k: (v if isinstance(v, list) else [v]) for k, v in j.items()}
            else:
                try:
                    data = parse_qs(raw.decode("utf-8", errors="ignore"), keep_blank_values=True)
                except Exception:
                    data = {}

            section = data.get("_section", ["all"])[0]
            config  = load_service_config()

            if section in ("repo", "all"):
                config["repository"] = {
                    "db_type":     data.get("db_type",     ["Oracle"])[0],
                    "sid":         data.get("sid",          [""])[0],
                    "ip":          data.get("ip",           [""])[0],
                    "port":        data.get("port",         [""])[0],
                    "user":        data.get("user",         [""])[0],
                    "password":    data.get("password",     [""])[0],
                    "pg_home":     data.get("pg_home",      [""])[0],
                    "pg_data_dir": data.get("pg_data_dir",  [""])[0],
                }
            if section in ("paths", "all"):
                dgs_svc = [v.strip() for v in data.get("dgserver_s", [""]) if v.strip()] or [""]
                dgs_log = data.get("log_dgserver_s", [""])
                while len(dgs_log) < len(dgs_svc):
                    dgs_log.append("")
                dgs_log = dgs_log[:len(dgs_svc)]
                config["services"] = {
                    "platformjs":  data.get("platformjs",  [""])[0],
                    "dgserver_m":  data.get("dgserver_m",  [""])[0],
                    "dgserver_s":  dgs_svc,
                }
                config["log_paths"] = {
                    "platformjs":  data.get("log_platformjs",  [""])[0],
                    "dgserver_m":  data.get("log_dgserver_m",  [""])[0],
                    "dgserver_s":  dgs_log,
                }

            save_service_config(config)

            # Repository 가 변경되면 MaxSpace 의 풀/캐시 즉시 무효화 (실패는 silent)
            if section in ("repo", "all"):
                _trigger_maxspace_reset()

            # All paths return JSON now; Labs drives the UI.
            if section == "repo":
                db_type = config["repository"].get("db_type", "Oracle")
                self._send(200, "application/json", json.dumps({"ok": True, "db_type": db_type}))
            else:
                self._send(200, "application/json", json.dumps({"ok": True}))
        else:
            self._send(405, "text/plain", "Method Not Allowed")


if __name__ == "__main__":
    from datetime import date as _date
    _ensure_partition(_date.today())
    _ensure_partition(_date.today() + timedelta(days=1))
    _t = _threading.Thread(target=_scheduler_loop, daemon=True)
    _t.start()
    sys.stdout.write('[python-utils] scheduler started\n')
    sys.stdout.flush()
    server = HTTPServer(("0.0.0.0", UTILS_PORT), Handler)
    sys.stdout.write("[python-utils] port %d\n" % UTILS_PORT)
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
