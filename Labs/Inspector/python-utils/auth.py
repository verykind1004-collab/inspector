# -*- coding: utf-8 -*-
import time
import threading
import hashlib
import os
import shlex
import subprocess
import secrets as _secrets

# UTILS_BASE and COOKIE_NAME are injected at startup
_UTILS_BASE = ""
_COOKIE_NAME = "mxg_sid"

def set_utils_base(base):
    global _UTILS_BASE
    _UTILS_BASE = base

def set_cookie_name(port):
    global _COOKIE_NAME
    _COOKIE_NAME = "mxg_sid_%s" % port


_AUTH_ENABLED  = True
_AUTH_USER     = 'maxgauge'
_AUTH_SALT     = 'mxg_inspector_salt_v1'
_AUTH_HASH     = 'ffb3ac5ee5445547dc04b542cf7d329efeb0178de4148c2ec8a9a877fb3ed316'
_SESSION_TTL   = 1 * 3600
_SESSIONS      = {}
_SESSION_LOCK  = threading.Lock()


def _create_session(user_id='', role=''):
    token = _secrets.token_hex(32)
    with _SESSION_LOCK:
        _SESSIONS[token] = {
            'expiry': time.time() + _SESSION_TTL,
            'user_id': user_id,
            'role': role,
        }
    return token


def _delete_session(token):
    with _SESSION_LOCK:
        _SESSIONS.pop(token, None)


def _get_session_info(handler):
    """Return session dict {user_id, role, expiry} or None."""
    token = _get_session_token(handler)
    if not token:
        return None
    with _SESSION_LOCK:
        info = _SESSIONS.get(token)
    if not info:
        return None
    if time.time() > info.get('expiry', 0):
        _delete_session(token)
        return None
    return info


def _get_session_token(handler):
    cookie = handler.headers.get('Cookie', '')
    prefix = _COOKIE_NAME + '='
    for part in cookie.split(';'):
        part = part.strip()
        if part.startswith(prefix):
            return part[len(prefix):]
    return None


def _is_authenticated(handler):
    if not _AUTH_ENABLED:
        return True
    return _get_session_info(handler) is not None


def _verify_maxgauge(password):
    return hashlib.sha256((_AUTH_SALT + password).encode('utf-8')).hexdigest() == _AUTH_HASH


def _dgs_decrypt(encrypted_text):
    """Invoke DGServer.jar decrypt. Returns (plaintext, error)."""
    try:
        import config_loader
        from service_config import load_service_config
    except Exception as e:
        return None, 'import failed: ' + str(e)

    svc = load_service_config()
    dgm_home = svc.get('services', {}).get('dgserver_m', '')
    if not dgm_home:
        return None, 'DGServer_M not configured'
    jar_path = os.path.join(dgm_home, 'bin', 'DGServer.jar')
    if not os.path.exists(jar_path):
        return None, 'DGServer.jar not found: ' + jar_path

    try:
        cfg = config_loader.load()
    except Exception:
        cfg = {}
    java_path = ''
    if hasattr(config_loader, 'get_java_path'):
        java_path = config_loader.get_java_path(cfg) or ''
    if java_path and os.path.isfile(java_path) and os.access(java_path, os.X_OK):
        argv = [java_path, '-jar', jar_path, 'decrypt']
    else:
        argv = ['bash', '-lc', 'exec java -jar %s decrypt' % shlex.quote(jar_path)]

    try:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                cwd=os.path.join(dgm_home, 'bin'))
        stdout, _ = proc.communicate(input=(encrypted_text + '\n').encode('utf-8'),
                                     timeout=10)
        output = stdout.decode('utf-8', errors='replace').strip()
        import re
        m = re.search(r'Decrypt\s*:\s*(.*)', output, re.IGNORECASE)
        if m:
            return m.group(1).strip(), None
        return None, 'unexpected output: ' + output[:200]
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
        return None, 'decrypt timeout'
    except Exception as e:
        return None, str(e)[:200]


def _fetch_user_row(user_id):
    """Query apm_user_list from repository DB. Returns (row_dict, error).
    row_dict keys: password, is_locked. None if not found."""
    try:
        from service_config import load_service_config
    except Exception as e:
        return None, 'import failed: ' + str(e)

    repo = load_service_config().get('repository', {}) or {}
    if not repo.get('ip') or not repo.get('sid'):
        return None, 'repository not configured'

    db_type = (repo.get('db_type') or '').lower()
    try:
        if 'postgres' in db_type:
            import psycopg2
            conn = psycopg2.connect(host=repo['ip'], port=int(repo.get('port') or 5432),
                                    user=repo.get('user', ''), password=repo.get('password', ''),
                                    dbname=repo['sid'], connect_timeout=5)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("SELECT password, COALESCE(is_locked,0) FROM apm_user_list WHERE user_id=%s",
                        (user_id,))
            row = cur.fetchone()
            cur.close(); conn.close()
            if not row:
                return None, None
            return {'password': row[0], 'is_locked': int(row[1] or 0)}, None
        elif 'oracle' in db_type:
            import oracledb
            dsn = '%s:%s/%s' % (repo['ip'], int(repo.get('port') or 1521), repo['sid'])
            conn = oracledb.connect(user=repo.get('user', ''),
                                    password=repo.get('password', ''), dsn=dsn,
                                    tcp_connect_timeout=30)
            conn.call_timeout = 30000
            cur = conn.cursor()
            cur.execute("SELECT password, NVL(is_locked,0) FROM apm_user_list WHERE user_id=:1",
                        [user_id])
            row = cur.fetchone()
            cur.close(); conn.close()
            if not row:
                return None, None
            return {'password': row[0], 'is_locked': int(row[1] or 0)}, None
        else:
            return None, 'unsupported db_type: ' + db_type
    except Exception as e:
        return None, 'db error: ' + str(e)[:200]


def verify_credential(user_id, password):
    """Labs login verification. Returns (ok:bool, role:str, error:str|None).

    role is 'engineer' only for the hardcoded maxgauge account; 'user' otherwise.
    """
    uid = (user_id or '').strip()
    pw  = password or ''

    if uid == _AUTH_USER and _verify_maxgauge(pw):
        return True, 'engineer', None

    row, err = _fetch_user_row(uid)
    if err:
        return False, '', err
    if row is None:
        return False, '', 'invalid credentials'
    if row.get('is_locked'):
        return False, '', 'account is locked'

    plain, derr = _dgs_decrypt(row['password'])
    if derr:
        return False, '', 'decrypt failed: ' + derr
    if plain != pw:
        return False, '', 'invalid credentials'

    return True, 'user', None


def page_login(error=False):
    err_html = (
        '<div style="background:rgba(240,106,106,.12);border:1px solid rgba(240,106,106,.35);'
        'color:#f06a6a;padding:10px 14px;border-radius:8px;font-size:.85rem;margin-bottom:16px;">'
        'Invalid username or password.</div>'
    ) if error else ''
    return ''.join([
        '<!DOCTYPE html><html lang="en"><head>',
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>Login - MaxGauge Inspector</title>',
        '<link rel="preconnect" href="https://fonts.googleapis.com">',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">',
        '<style>',
        '*{box-sizing:border-box;margin:0;padding:0}',
        'body{background:#F9FAFB;color:#0F172A;font-family:"Noto Sans KR","Segoe UI",system-ui,sans-serif;',
        'min-height:100vh;display:flex;align-items:center;justify-content:center;}',
        '.login-wrap{width:100%;max-width:400px;padding:0 16px;}',
        '.login-brand{text-align:center;font-family:"Inter","Noto Sans KR",sans-serif;font-size:1.85rem;font-weight:800;color:#1E293B;',
        'letter-spacing:-.02em;margin-bottom:36px;}',
        '.login-brand span{background:linear-gradient(135deg,#6366F1,#8B5CF6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}',
        '.login-card{background:#ffffff;border:1px solid #E2E8F0;border-radius:12px;padding:32px;'
        'box-shadow:0 4px 24px rgba(15,23,42,.08);}',
        'label{display:block;font-size:.78rem;color:#64748B;margin-bottom:6px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;}',
        'input[type=text],input[type=password]{',
        'width:100%;padding:10px 12px;background:#ffffff;border:1px solid #CBD5E1;',
        'border-radius:8px;color:#0F172A;font-size:.9rem;outline:none;margin-bottom:18px;}',
        'input[type=text]:focus,input[type=password]:focus{border-color:#6366F1;}',
        'button{width:100%;padding:11px;background:#6366F1;border:none;border-radius:8px;',
        'color:#ffffff;font-size:.9rem;font-weight:700;cursor:pointer;letter-spacing:.03em;}',
        'button:hover{background:#4F46E5;}',
        '</style></head><body>',
        '<div class="login-wrap">',
        '<div class="login-brand">MaxGauge <span>Inspector</span></div>',
        '<div class="login-card">',
        err_html,
        '<form method="POST" action="', _UTILS_BASE, '/login" autocomplete="off" '
        'data-lpignore="true" data-form-type="other">',
        '<label>Username</label>',
        '<input type="text" name="username" autofocus autocomplete="off" '
        'autocorrect="off" autocapitalize="off" spellcheck="false" '
        'data-lpignore="true" data-form-type="other">',
        '<label>Password</label>',
        '<input type="password" name="password" autocomplete="new-password" '
        'autocorrect="off" autocapitalize="off" spellcheck="false" '
        'data-lpignore="true" data-form-type="other">',
        '<button type="submit">Sign In</button>',
        '</form>',
        '</div></div></body></html>',
    ])
