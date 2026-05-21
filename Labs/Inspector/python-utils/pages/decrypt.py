# -*- coding: utf-8 -*-
import json
import os
import re
import shlex
import subprocess
import config_loader
from service_config import load_service_config
from html_helpers import _page, _page_title_html, _ts, _UTILS_BASE, _HELP


_ALLOWED_ACTIONS = ('encrypt', 'decrypt')


def _resolve_java_cmd(jar_path, action):
    """Build the argv that runs DGServer.jar.

    Priority:
      1) config.yaml `java.path` — explicit path wins.
      2) Login shell (`bash -lc`) — sources ~/.bash_profile so whatever
         JAVA_HOME / PATH the operator configured is used.
    Returns (argv, note) where note is a short description for errors.
    """
    try:
        cfg = config_loader.load()
    except Exception:
        cfg = {}
    java_path = config_loader.get_java_path(cfg) if hasattr(config_loader, 'get_java_path') else ''
    if java_path:
        if not os.path.isfile(java_path) or not os.access(java_path, os.X_OK):
            return None, 'config.yaml java.path is invalid or not executable: ' + java_path
        return [java_path, '-jar', jar_path, action], 'explicit'
    # Fall back to login shell so ~/.bash_profile JAVA_HOME/PATH applies.
    inner = 'exec java -jar %s %s' % (shlex.quote(jar_path), action)
    return ['bash', '-lc', inner], 'login-shell'


def api_decrypt(raw_body):
    """Run `java -jar DGServer.jar <action>` where action is encrypt or decrypt.
    Kept under the legacy name api_decrypt for route compatibility."""
    try:
        data   = json.loads(raw_body)
        text   = (data.get('text') or '').strip()
        action = (data.get('action') or 'decrypt').strip().lower()
    except Exception:
        return json.dumps({'ok': False, 'error': 'Invalid request'})
    if not text:
        return json.dumps({'ok': False, 'error': 'No text provided'})
    if action not in _ALLOWED_ACTIONS:
        return json.dumps({'ok': False, 'error': 'Invalid action: ' + action})

    svc = load_service_config()
    dgm_home = svc.get('services', {}).get('dgserver_m', '')
    if not dgm_home:
        return json.dumps({'ok': False, 'error': 'DGServer_M 경로가 설정되지 않았습니다.'})

    jar_path = os.path.join(dgm_home, 'bin', 'DGServer.jar')
    if not os.path.exists(jar_path):
        return json.dumps({'ok': False, 'error': 'DGServer.jar 파일을 찾을 수 없습니다.'})

    argv, note = _resolve_java_cmd(jar_path, action)
    if argv is None:
        return json.dumps({'ok': False, 'error': note})

    proc = None
    try:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.join(dgm_home, 'bin')
        )
        stdout, stderr = proc.communicate(input=(text + '\n').encode('utf-8'), timeout=10)
        output = stdout.decode('utf-8', errors='replace').strip()

        label = 'Encrypt' if action == 'encrypt' else 'Decrypt'
        m = re.search(label + r'\s*:\s*(.+)', output, re.IGNORECASE)
        result = m.group(1).strip() if m else ''

        if result:
            return json.dumps({'ok': True, 'result': result, 'action': action})
        err_text = stderr.decode('utf-8', errors='replace').strip()
        hint = ''
        if 'command not found' in err_text.lower() or 'java: not found' in err_text.lower():
            hint = ' (java 실행 불가 — config.yaml 의 java.path 설정 또는 ~/.bash_profile 의 JAVA_HOME/PATH 를 확인하세요.)'
        return json.dumps({
            'ok': False,
            'error': 'No ' + action + ' result.' + hint
                     + ' Output: ' + output[:200]
                     + ((' Stderr: ' + err_text[:200]) if err_text else '')
        })
    except subprocess.TimeoutExpired:
        if proc is not None:
            proc.kill()
        return json.dumps({'ok': False, 'error': 'Timeout (10s)'})
    except FileNotFoundError as e:
        return json.dumps({'ok': False, 'error': 'java 실행파일을 찾을 수 없습니다: ' + str(e)[:200]})
    except PermissionError as e:
        return json.dumps({'ok': False, 'error': 'java 실행 권한 없음: ' + str(e)[:200]})
    except Exception as e:
        return json.dumps({'ok': False, 'error': str(e)[:200]})
