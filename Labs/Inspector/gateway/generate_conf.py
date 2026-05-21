#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# gateway/generate_conf.py
# Reads config.yaml and renders nginx.conf from nginx.conf.template.

import os
import sys

_GATEWAY_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR    = os.path.dirname(_GATEWAY_DIR)
_UTILS_DIR   = os.path.join(_ROOT_DIR, "python-utils")
sys.path.insert(0, _UTILS_DIR)

import config_loader

NGINX_CONF    = os.path.join(_GATEWAY_DIR, "nginx.conf")
TEMPLATE_PATH = os.path.join(_GATEWAY_DIR, "nginx.conf.template")


def main():
    cfg = config_loader.load()

    ssl_enabled = config_loader.get_ssl_enabled(cfg)
    ssl_port    = str(config_loader.get_ssl_port(cfg))
    ssl_cert    = config_loader.get_ssl_cert(cfg)
    ssl_key     = config_loader.get_ssl_key(cfg)
    base_path   = config_loader.get_base_path(cfg)
    check_path  = config_loader.get_check_path(cfg)

    # Build SSL server block if enabled
    ssl_block = ""
    if ssl_enabled and ssl_cert and ssl_key:
        # Resolve cert/key paths relative to gateway dir
        if not os.path.isabs(ssl_cert):
            ssl_cert = os.path.join(_GATEWAY_DIR, ssl_cert)
        if not os.path.isabs(ssl_key):
            ssl_key = os.path.join(_GATEWAY_DIR, ssl_key)
        ssl_block = """
    server {{
        listen {ssl_port} ssl;
        server_name _;

        ssl_certificate     {ssl_cert};
        ssl_certificate_key {ssl_key};
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;
        ssl_session_cache   shared:SSL:10m;
        ssl_session_timeout 10m;

        proxy_redirect ~^http://[^/]+/(.*) /$1;

        # /labs/* (BASE_PATH 없이) 는 차단. {base_path}/labs/* 만 허용.
        location = /labs           {{ return 404; }}
        location = /labs/          {{ return 404; }}
        location = /labs/maxspace {{ return 404; }}
        location /labs/maxspace/ {{ return 404; }}

        # Labs 내부 인증 게이트 (auth_request 전용)
        location = /labs/_auth {{
            internal;
            proxy_pass http://python_utils_backend/labs/api/check-auth;
            proxy_pass_request_body off;
            proxy_set_header Content-Length "";
            proxy_set_header Host            $host;
            proxy_set_header Cookie          $http_cookie;
            proxy_connect_timeout 3s;
            proxy_read_timeout    5s;
        }}

        location @labs_login_redirect_ssl {{
            return 302 {base_path}/labs/;
        }}

        # {base_path}/labs/* alias — MAXGAUGE 네임스페이스 하위에서도 동일 접속.
        # (SSL 블록은 기존에도 /labs/tablespace/api 프록시 없음 → 동일하게 정적 + 인증만 미러)
        location = {base_path}/labs  {{ return 301 {base_path}/labs/; }}
        location {base_path}/labs/ {{
            alias {labs_dir}/;
            index maxgauge-labs.html;
        }}
        location = {base_path}/labs/maxspace  {{ return 301 {base_path}/labs/maxspace/; }}
        location {base_path}/labs/maxspace/ {{
            alias {labs_dir}/MaxSpace/;
            index tablespace_dashboard.html;
        }}
        location = {base_path}/labs/_auth {{
            internal;
            proxy_pass http://python_utils_backend/labs/api/check-auth;
            proxy_pass_request_body off;
            proxy_set_header Content-Length "";
            proxy_set_header Host            $host;
            proxy_set_header Cookie          $http_cookie;
            proxy_connect_timeout 3s;
            proxy_read_timeout    5s;
        }}

        location {base_path}{check_path}/ {{
            proxy_pass       http://python_utils_backend/;
            proxy_set_header Host            $host;
            proxy_set_header X-Real-IP       $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_connect_timeout 10s;
            proxy_read_timeout    60s;
        }}

        location = {base_path}{check_path} {{
            return 301 {base_path}{check_path}/;
        }}

        location = /api/v1/login {{
            access_log {gw_dir}/log/access/login_audit.log login;
            proxy_pass       http://platformjs_backend;
            proxy_set_header Host            $host;
            proxy_set_header X-Real-IP       $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_connect_timeout 10s;
            proxy_read_timeout    300s;
        }}

        location /api/ {{
            proxy_pass       http://platformjs_backend;
            proxy_set_header Host            $host;
            proxy_set_header X-Real-IP       $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_connect_timeout 10s;
            proxy_read_timeout    300s;
        }}

        location {base_path}/ {{
            proxy_pass       http://platformjs_backend;
            proxy_set_header Host            $host;
            proxy_set_header X-Real-IP       $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade    $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_connect_timeout 10s;
            proxy_read_timeout    300s;
        }}

        location / {{
            set $redir "";
            if ($request_uri = "/") {{ set $redir "root"; }}
            if ($http_upgrade ~* "websocket") {{ set $redir ""; }}
            if ($redir = "root") {{ return 302 {base_path}/; }}

            proxy_pass       http://platformjs_backend;
            proxy_set_header Host            $host;
            proxy_set_header X-Real-IP       $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade    $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_connect_timeout 10s;
            proxy_read_timeout    300s;
        }}

        location = /ping {{
            access_log off;
            return 200 "pong\n";
            add_header Content-Type text/plain;
        }}
    }}
""".format(
            ssl_port=ssl_port, ssl_cert=ssl_cert, ssl_key=ssl_key,
            base_path=base_path, check_path=check_path, gw_dir=_GATEWAY_DIR,
            labs_dir=config_loader.get_labs_dir(cfg),
        )

    subs = {
        "{{GATEWAY_DIR}}":       _GATEWAY_DIR,
        "{{GATEWAY_PORT}}":      str(config_loader.get_gateway_port(cfg)),
        "{{PLATFORMJS_PORT}}":   str(config_loader.get_platformjs_port(cfg)),
        "{{PYTHON_UTILS_PORT}}": str(config_loader.get_utils_port(cfg)),
        "{{BASE_PATH}}":         base_path,
        "{{CHECK_PATH}}":        check_path,
        "{{SSL_SERVER_BLOCK}}":  ssl_block,
        "{{TABLESPACE_PORT}}":   str(config_loader.get_tablespace_port(cfg)),
        "{{LABS_DIR}}":          config_loader.get_labs_dir(cfg),
    }

    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        conf = f.read()

    for k, v in subs.items():
        conf = conf.replace(k, v)

    with open(NGINX_CONF, "w", encoding="utf-8") as f:
        f.write(conf)

    print("[gateway] nginx.conf generated: {}".format(NGINX_CONF))
    print("          Gateway     : :{}".format(subs["{{GATEWAY_PORT}}"]))
    if ssl_enabled and ssl_cert and ssl_key:
        print("          Gateway SSL : :{} (cert={})".format(ssl_port, ssl_cert))
    print("          PlatformJS  : :{}".format(subs["{{PLATFORMJS_PORT}}"]))
    print("          Python-utils: :{}  -> {}{}".format(
        subs["{{PYTHON_UTILS_PORT}}"],
        subs["{{BASE_PATH}}"],
        subs["{{CHECK_PATH}}"]
    ))


if __name__ == "__main__":
    main()
