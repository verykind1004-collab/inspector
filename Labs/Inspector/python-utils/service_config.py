# -*- coding: utf-8 -*-
import os
import json

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'service_config.json')


def load_service_config():
    default = {
        "repository": {"db_type": "Oracle", "sid": "", "ip": "", "port": "",
                       "user": "", "password": "", "pg_home": "", "pg_data_dir": ""},
        "services":   {"platformjs": "", "dgserver_m": "", "dgserver_s": [""]},
        "log_paths":  {"platformjs": "", "dgserver_m": "", "dgserver_s": [""]}
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save_service_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)
