# -*- coding: utf-8 -*-
import os
import sys

_SCRIPT_DIR      = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR        = os.path.dirname(_SCRIPT_DIR)           # Inspector/
_LABS_DIR        = os.path.dirname(_ROOT_DIR)             # Labs/
# Look for config.yaml: 1) Labs/ (grandparent), 2) Inspector/ (parent), 3) python-utils/
_LABS_CFG        = os.path.join(_LABS_DIR,   "config.yaml")
_PARENT_CFG      = os.path.join(_ROOT_DIR,   "config.yaml")
_LOCAL_CFG       = os.path.join(_SCRIPT_DIR, "config.yaml")
if os.path.exists(_LABS_CFG):
    CONFIG_PATH = _LABS_CFG
elif os.path.exists(_PARENT_CFG):
    CONFIG_PATH = _PARENT_CFG
else:
    CONFIG_PATH = _LOCAL_CFG

def _parse(path):
    result, section = {}, None
    with open(path) as f:
        for raw in f:
            line = raw.rstrip()
            if not line or line.lstrip().startswith("#"):
                continue
            if not raw.startswith(" ") and line.endswith(":"):
                section = line[:-1].strip()
                result[section] = {}
            elif section and ":" in line:
                k, _, v = line.partition(":")
                v = v.split("#")[0].strip().strip('"').strip("'")
                try:
                    v = int(v)
                except ValueError:
                    pass
                result[section][k.strip()] = v
    return result

def load():
    if not os.path.exists(CONFIG_PATH):
        print("[ERROR] config.yaml 없음: " + CONFIG_PATH)
        sys.exit(1)
    try:
        import yaml
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f)
    except ImportError:
        return _parse(CONFIG_PATH)

def _as_int(v, default):
    """YAML 에서 빈 값(`key:`)이 None 으로 파싱되거나 문자열이 들어와도
    default 로 떨어지도록 안전하게 변환."""
    if v is None or v == "":
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default

def _as_str(v, default=""):
    if v is None:
        return default
    return str(v)

def get_gateway_port(cfg):    return _as_int((cfg.get("gateway")      or {}).get("port"),       8080)
def get_platformjs_port(cfg): return _as_int((cfg.get("platformjs")   or {}).get("port"),       3000)
def get_base_path(cfg):       return _as_str((cfg.get("platformjs")   or {}).get("base_path"), "/MAXGAUGE").rstrip("/")
def get_utils_port(cfg):      return _as_int((cfg.get("python_utils") or {}).get("port"),       8083)
def get_check_path(cfg):      return _as_str((cfg.get("python_utils") or {}).get("check_path"), "/check").rstrip("/")

def get_java_path(cfg):
    v = (cfg or {}).get("java", {})
    if not isinstance(v, dict):
        return ""
    p = v.get("path", "")
    return str(p).strip() if p else ""

def get_ssl_enabled(cfg):     return bool((cfg.get("gateway") or {}).get("ssl_enabled", False))
def get_ssl_port(cfg):        return _as_int((cfg.get("gateway") or {}).get("ssl_port"), 8443)
def get_ssl_cert(cfg):        return _as_str((cfg.get("gateway") or {}).get("ssl_cert"), "")
def get_ssl_key(cfg):         return _as_str((cfg.get("gateway") or {}).get("ssl_key"),  "")

def get_tablespace_port(cfg): return _as_int((cfg.get("tablespace") or {}).get("port"), 8084)
def get_labs_dir(cfg):
    """labs.dir 우선. 비어 있으면 config.yaml 이 있는 디렉토리를 곧 Labs 로 간주.
    배포 환경마다 labs.dir 수동 설정 안 해도 되도록 자동 추론."""
    d = str((cfg.get("labs") or {}).get("dir", "")).strip()
    if d:
        return d
    return os.path.dirname(CONFIG_PATH)
