# -*- coding: utf-8 -*-
"""Control Process – Start / Stop / Restart MaxGauge components + Observer (mxg_obsd)."""
import json
import os
import subprocess
import time

from service_config import load_service_config
from system_utils import (
    _get_pid_by_port, _proc_uptime_html, _xml_val, _dg_info, _repodb_info,
    _platformjs_pid_by_port, _port_is_listening,
)


# ── Shell helper ─────────────────────────────────────────────────────────────────

def _run_shell(cmd, cwd=None, env=None, timeout=30):
    """Run a shell command and return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.Popen(
            cmd, shell=True, cwd=cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        out, err = proc.communicate(timeout=timeout)
        return proc.returncode, out.decode('utf-8', errors='replace'), err.decode('utf-8', errors='replace')
    except subprocess.TimeoutExpired:
        proc.kill()
        return -1, '', 'Command timed out'
    except Exception as e:
        return -1, '', str(e)


def _run_bg(cmd, cwd=None, env=None):
    """Fire-and-forget: launch a background command without waiting."""
    try:
        subprocess.Popen(
            cmd, shell=True, cwd=cwd, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


# ── .mxgrc parser ────────────────────────────────────────────────────────────────

def _parse_mxgrc(home):
    """Parse .mxgrc file. Returns dict with DG_NAME, DG_XMS, DG_XMX, MXG_HOME, OS_TYPE, JAVA_HOME."""
    result = {}
    mxgrc = os.path.join(home, '.mxgrc')
    if not os.path.exists(mxgrc):
        return result
    try:
        with open(mxgrc, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line and not line.startswith('export') \
                        and not line.startswith('alias') and not line.startswith('PATH'):
                    key, _, val = line.partition('=')
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key in ('DG_NAME', 'DG_XMS', 'DG_XMX', 'MXG_HOME', 'OS_TYPE', 'JAVA_HOME'):
                        result[key] = val
    except Exception:
        pass
    return result


def _build_env(mxgrc):
    """Build environment dict from .mxgrc values."""
    env = os.environ.copy()
    for k in ('DG_NAME', 'DG_XMS', 'DG_XMX', 'MXG_HOME', 'OS_TYPE'):
        if k in mxgrc:
            env[k] = mxgrc[k]
    java_home = mxgrc.get('JAVA_HOME', '')
    if java_home:
        env['JAVA_HOME'] = java_home
        env['PATH'] = os.path.join(java_home, 'bin') + ':' + env.get('PATH', '')
    if mxgrc.get('MXG_HOME'):
        env['PATH'] = os.path.join(mxgrc['MXG_HOME'], 'bin') + ':' + env.get('PATH', '')
    return env


# ── Observer (mxg_obsd) helpers ──────────────────────────────────────────────────

def _get_dg_obsd_pid(dg_name):
    """Find observer PID for a DGServer by DG_NAME keyword."""
    if not dg_name:
        return None
    rc, out, _ = _run_shell(
        "ps -ef | grep mxg_obsd | grep -w '%s' | grep -v grep | awk '{print $2}'" % dg_name
    )
    pid = out.strip().split('\n')[0].strip() if out.strip() else ''
    return pid if pid and pid.isdigit() else None


def _get_pjs_obsd_pid(service_port):
    """Find observer PID for PlatformJS by DPJS{port} keyword."""
    if not service_port:
        return None
    rc, out, _ = _run_shell(
        "ps -ef | grep mxg_obsd | grep 'DPJS%s' | grep common.console.conf | grep -v grep | awk '{print $2}'"
        % service_port
    )
    pid = out.strip().split('\n')[0].strip() if out.strip() else ''
    return pid if pid and pid.isdigit() else None


def _stop_obsd(pid):
    """Kill an observer process. Returns (ok, message)."""
    if not pid:
        return True, 'Observer not running.'
    _run_shell('kill %s' % pid)
    time.sleep(1)
    # Verify killed
    rc, out, _ = _run_shell("ps -p %s -o pid= 2>/dev/null" % pid)
    if out.strip():
        _run_shell('kill -9 %s' % pid)
        time.sleep(0.5)
    return True, 'Observer stopped. (PID: %s)' % pid


def _start_dg_obsd(home, mxgrc):
    """Start DGServer observer. Returns (ok, message)."""
    dg_name = mxgrc.get('DG_NAME', '')
    os_type = mxgrc.get('OS_TYPE', 'linux64')
    if not dg_name:
        return False, 'DG_NAME not set in .mxgrc'

    # Check if already running
    existing = _get_dg_obsd_pid(dg_name)
    if existing:
        return False, 'Observer already running. (PID: %s)' % existing

    obsd_bin = os.path.join(home, 'bin', 'mxg_obsd', os_type, 'mxg_obsd')
    conf_file = os.path.join(home, 'conf', 'DG', 'common_linux.conf')
    if not os.path.exists(obsd_bin):
        return False, 'mxg_obsd binary not found: %s' % obsd_bin
    if not os.path.exists(conf_file):
        return False, 'Observer config not found: %s' % conf_file

    env = _build_env(mxgrc)
    bin_dir = os.path.join(home, 'bin')
    cmd = '%s -c %s -f %s -OTHERD -i 10 -D' % (obsd_bin, dg_name, conf_file)
    rc, out, err = _run_shell(cmd, cwd=bin_dir, env=env)
    time.sleep(1)

    pid = _get_dg_obsd_pid(dg_name)
    if pid:
        return True, 'Observer started. (PID: %s)' % pid
    return False, 'Observer start failed. %s' % (err.strip() or out.strip())


def _start_pjs_obsd(pjs_home, service_port):
    """Start PlatformJS observer. Returns (ok, message)."""
    if not service_port:
        return False, 'Service port unknown.'

    existing = _get_pjs_obsd_pid(service_port)
    if existing:
        return False, 'Observer already running. (PID: %s)' % existing

    obsd_bin = os.path.join(pjs_home, 'mxg_obsd', 'linux64', 'mxg_obsd')
    conf_file = os.path.join(pjs_home, 'config', 'common.console.conf')
    if not os.path.exists(obsd_bin):
        return False, 'mxg_obsd binary not found: %s' % obsd_bin
    if not os.path.exists(conf_file):
        return False, 'Observer config not found: %s' % conf_file

    # Load .mxgrc for JAVA_HOME
    mxgrc = _parse_mxgrc(pjs_home)
    env = _build_env(mxgrc)
    env['MXG_HOME'] = pjs_home

    cmd = '%s --DPJS%s -f %s -OTHERD -i 30 -D' % (obsd_bin, service_port, conf_file)
    rc, out, err = _run_shell(cmd, cwd=pjs_home, env=env)
    time.sleep(1)

    pid = _get_pjs_obsd_pid(service_port)
    if pid:
        return True, 'Observer started. (PID: %s)' % pid
    return False, 'Observer start failed. %s' % (err.strip() or out.strip())


# ── DGServer Start / Stop ────────────────────────────────────────────────────────

def _start_dgserver(home):
    """Start DGServer + Observer."""
    mxgrc = _parse_mxgrc(home)
    dg_name = mxgrc.get('DG_NAME', '')
    dg_xms = mxgrc.get('DG_XMS', '1024')
    dg_xmx = mxgrc.get('DG_XMX', '1024')
    if not dg_name:
        return False, '.mxgrc에 DG_NAME이 설정되지 않았습니다.'

    info = _dg_info(home)
    if info.get('status') == 'running':
        return False, '%s is already running. (PID: %s)' % (dg_name, info.get('pid', '-'))

    bin_dir = os.path.join(home, 'bin')
    if not os.path.exists(os.path.join(bin_dir, 'DGServer.jar')):
        return False, 'DGServer.jar not found in %s' % bin_dir

    env = _build_env(mxgrc)
    cmd = 'nohup java -Xms%sm -Xmx%sm -%s -jar DGServer.jar 1>/dev/null 2>&1 &' % (
        dg_xms, dg_xmx, dg_name)
    _run_bg(cmd, cwd=bin_dir, env=env)

    # Check process via ps (like dgsctl status) — no need to wait for port binding
    pid = None
    for _ in range(5):
        time.sleep(1)
        rc2, out2, _ = _run_shell(
            "ps -ef | grep -w '%s' | grep DGServer.jar | grep -v grep | awk '{print $2}'" % dg_name)
        pid = out2.strip().split('\n')[0].strip() if out2.strip() else ''
        if pid and pid.isdigit():
            break
        pid = None

    if not pid:
        return False, '%s start failed. Check logs.' % dg_name

    msgs = ['%s started. (PID: %s)' % (dg_name, pid)]

    # Start observer
    obsd_ok, obsd_msg = _start_dg_obsd(home, mxgrc)
    msgs.append('Observer: %s' % obsd_msg)

    return True, ' / '.join(msgs)


def _stop_dgserver(home):
    """Stop Observer first, then DGServer."""
    mxgrc = _parse_mxgrc(home)
    dg_name = mxgrc.get('DG_NAME', '')
    label = dg_name or 'DGServer'

    # 1) Stop observer first (prevents auto-restart)
    obsd_pid = _get_dg_obsd_pid(dg_name)
    obsd_msgs = []
    if obsd_pid:
        _, obsd_msg = _stop_obsd(obsd_pid)
        obsd_msgs.append('Observer: %s' % obsd_msg)
    else:
        obsd_msgs.append('Observer: not running')

    # 2) Stop DGServer process
    info = _dg_info(home)
    pid = info.get('pid', '-')
    if pid == '-' or info.get('status') != 'running':
        return True, '%s is not running. / %s' % (label, ' / '.join(obsd_msgs))

    _run_shell('kill %s' % pid)
    time.sleep(5)

    # Force kill if still alive
    info2 = _dg_info(home)
    if info2.get('status') == 'running':
        _run_shell('kill -9 %s' % pid)
        time.sleep(5)

    msgs = ['%s stopped. (PID: %s)' % (label, pid)]
    msgs.extend(obsd_msgs)
    return True, ' / '.join(msgs)


# ── PlatformJS Start / Stop ──────────────────────────────────────────────────────

def _get_pjs_port():
    import config_loader
    cfg = config_loader.load()
    return config_loader.get_platformjs_port(cfg)


def _start_platformjs(pjs_home):
    """Start PlatformJS + Observer."""
    pjs_port = _get_pjs_port()
    pid = _get_pid_by_port(pjs_port) or _platformjs_pid_by_port(pjs_port)
    if pid:
        return False, 'PlatformJS is already running. (PID: %s)' % pid

    start_sh = os.path.join(pjs_home, 'platformjs.start.sh')
    if not os.path.exists(start_sh):
        return False, 'platformjs.start.sh not found in %s' % pjs_home

    mxgrc = _parse_mxgrc(pjs_home)
    env = _build_env(mxgrc)

    cmd = 'bash platformjs.start.sh -r'
    _run_bg(cmd, cwd=pjs_home, env=env)

    # Check process via ps (like pjsctl status) — no need to wait for port binding
    pid = None
    for _ in range(5):
        time.sleep(1)
        rc2, out2, _ = _run_shell(
            "ps -ef | grep 'DPJS%s' | grep -v grep | grep -v mxg_obsd | awk '{print $2}'" % pjs_port)
        pid = out2.strip().split('\n')[0].strip() if out2.strip() else ''
        if pid and pid.isdigit():
            break
        pid = None

    if not pid:
        return False, 'PlatformJS start failed. Check logs.'

    msgs = ['PlatformJS started. (PID: %s, Port: %s)' % (pid, pjs_port)]

    # Start observer
    obsd_ok, obsd_msg = _start_pjs_obsd(pjs_home, pjs_port)
    msgs.append('Observer: %s' % obsd_msg)

    return True, ' / '.join(msgs)


def _stop_platformjs(pjs_home):
    """Stop Observer first, then PlatformJS."""
    pjs_port = _get_pjs_port()

    # 1) Stop observer first
    obsd_pid = _get_pjs_obsd_pid(pjs_port)
    obsd_msgs = []
    if obsd_pid:
        _, obsd_msg = _stop_obsd(obsd_pid)
        obsd_msgs.append('Observer: %s' % obsd_msg)
    else:
        obsd_msgs.append('Observer: not running')

    # 2) Stop PlatformJS
    pid = _get_pid_by_port(pjs_port) or _platformjs_pid_by_port(pjs_port)
    if not pid:
        return True, 'PlatformJS is not running. / %s' % ' / '.join(obsd_msgs)

    # Graceful shutdown via Jetty stop
    stop_sh = os.path.join(pjs_home, 'platformjs.stop.sh')
    if os.path.exists(stop_sh):
        mxgrc = _parse_mxgrc(pjs_home)
        env = _build_env(mxgrc)
        cmd = 'cd "%s" && bash platformjs.stop.sh' % pjs_home
        _run_shell(cmd, cwd=pjs_home, env=env, timeout=15)
    else:
        _run_shell('kill %s' % pid)

    time.sleep(5)

    # Force kill if still alive
    pid2 = _get_pid_by_port(pjs_port) or _platformjs_pid_by_port(pjs_port)
    if pid2:
        _run_shell('kill -9 %s' % pid2)
        time.sleep(5)

    msgs = ['PlatformJS stopped. (PID: %s)' % pid]
    msgs.extend(obsd_msgs)
    return True, ' / '.join(msgs)


# ── PostgreSQL Start / Stop ──────────────────────────────────────────────────────

def _start_postgresql():
    """Start PostgreSQL using Database/start.sh."""
    svc = load_service_config()
    pg_home = svc.get('repository', {}).get('pg_home', '')
    if not pg_home:
        return False, 'pg_home이 설정되지 않았습니다. Configuration에서 설정해주세요.'
    start_sh = os.path.join(pg_home, 'start.sh')
    if not os.path.exists(start_sh):
        return False, 'start.sh not found in %s' % pg_home

    rdb = _repodb_info()
    if rdb.get('status') == 'running':
        return False, 'PostgreSQL is already running.'

    cmd = 'cd "%s" && bash start.sh' % pg_home
    rc, out, err = _run_shell(cmd, cwd=pg_home, timeout=15)

    # Poll until DB accepts connections (max 20s, check every 2s)
    for _ in range(10):
        time.sleep(2)
        rdb = _repodb_info()
        if rdb.get('status') == 'running':
            return True, 'PostgreSQL started.'

    return False, 'Start command executed. %s %s' % (out.strip(), err.strip())


def _stop_postgresql():
    """Stop PostgreSQL using Database/stop.sh."""
    svc = load_service_config()
    pg_home = svc.get('repository', {}).get('pg_home', '')
    if not pg_home:
        return False, 'pg_home이 설정되지 않았습니다.'
    stop_sh = os.path.join(pg_home, 'stop.sh')
    if not os.path.exists(stop_sh):
        return False, 'stop.sh not found in %s' % pg_home

    rdb = _repodb_info()
    if rdb.get('status') != 'running':
        return False, 'PostgreSQL is not running.'

    cmd = 'cd "%s" && bash stop.sh' % pg_home
    _run_shell(cmd, cwd=pg_home, timeout=15)
    time.sleep(5)
    rdb = _repodb_info()
    if rdb.get('status') == 'running':
        return False, 'Stop command executed but still running.'
    return True, 'PostgreSQL stopped.'


# ── API ──────────────────────────────────────────────────────────────────────────

def api_control_status():
    """Return current status of all controllable components (+ observer) as JSON."""
    import config_loader
    svc = load_service_config()
    svcs = svc.get('services', {})
    repo = svc.get('repository', {})
    _c = config_loader.load()
    pjs_port = config_loader.get_platformjs_port(_c)
    db_type = repo.get('db_type', 'Oracle').lower()

    components = []

    # DGServer_M
    dgm_home = svcs.get('dgserver_m', '')
    if dgm_home:
        info = _dg_info(dgm_home)
        mxgrc = _parse_mxgrc(dgm_home)
        dg_name = mxgrc.get('DG_NAME', '')
        obsd_pid = _get_dg_obsd_pid(dg_name)
        components.append({
            'id': 'dgserver_m',
            'name': 'DGServer_M',
            'status': info.get('status', 'stopped') if info.get('exists') else 'unconfigured',
            'port': info.get('port', '-'),
            'pid': info.get('pid', '-'),
            'uptime': _proc_uptime_html(info.get('pid', '-')),
            'dg_name': dg_name or '-',
            'heap': '%s/%s MB' % (mxgrc.get('DG_XMS', '-'), mxgrc.get('DG_XMX', '-')),
            'obsd_pid': obsd_pid or '-',
            'obsd_status': 'running' if obsd_pid else 'stopped',
        })

    # DGServer_S1, S2, ...
    for i, dgs_home in enumerate(svcs.get('dgserver_s', [])):
        if not dgs_home:
            continue
        info = _dg_info(dgs_home)
        mxgrc = _parse_mxgrc(dgs_home)
        dg_name = mxgrc.get('DG_NAME', '')
        obsd_pid = _get_dg_obsd_pid(dg_name)
        components.append({
            'id': 'dgserver_s_%d' % (i + 1),
            'name': 'DGServer_S%d' % (i + 1),
            'status': info.get('status', 'stopped') if info.get('exists') else 'unconfigured',
            'port': info.get('port', '-'),
            'pid': info.get('pid', '-'),
            'uptime': _proc_uptime_html(info.get('pid', '-')),
            'dg_name': dg_name or '-',
            'heap': '%s/%s MB' % (mxgrc.get('DG_XMS', '-'), mxgrc.get('DG_XMX', '-')),
            'obsd_pid': obsd_pid or '-',
            'obsd_status': 'running' if obsd_pid else 'stopped',
        })

    # PlatformJS
    pjs_pid = _get_pid_by_port(pjs_port) or _platformjs_pid_by_port(pjs_port)
    pjs_status = 'running' if pjs_pid else ('running' if _port_is_listening(pjs_port) else 'stopped')
    pjs_obsd_pid = _get_pjs_obsd_pid(pjs_port)
    pjs_home = svcs.get('platformjs', '')
    components.append({
        'id': 'platformjs',
        'name': 'PlatformJS',
        'status': pjs_status,
        'port': str(pjs_port),
        'pid': pjs_pid or '-',
        'uptime': _proc_uptime_html(pjs_pid),
        'dg_name': '',
        'heap': '',
        'obsd_pid': pjs_obsd_pid or '-',
        'obsd_status': 'running' if pjs_obsd_pid else 'stopped',
    })

    # PostgreSQL (only if db_type is PostgreSQL)
    if 'postgres' in db_type:
        rdb = _repodb_info()
        components.append({
            'id': 'postgresql',
            'name': 'PostgreSQL',
            'status': rdb.get('status', 'stopped'),
            'port': rdb.get('port', '-'),
            'pid': '-',
            'uptime': '-',
            'dg_name': '',
            'heap': '',
            'obsd_pid': '-',
            'obsd_status': '-',
        })

    return json.dumps({'ok': True, 'components': components})


def api_control_action(raw_body):
    """Execute a control action (start/stop/restart) on a component."""
    try:
        data = json.loads(raw_body)
        comp_id = (data.get('id') or '').strip()
        action = (data.get('action') or '').strip()
    except Exception:
        return json.dumps({'ok': False, 'message': 'Invalid request'})

    if action not in ('start', 'stop', 'restart'):
        return json.dumps({'ok': False, 'message': 'Invalid action: %s' % action})
    if not comp_id:
        return json.dumps({'ok': False, 'message': 'No component specified'})

    svc = load_service_config()
    svcs = svc.get('services', {})
    repo = svc.get('repository', {})

    ok, msg = False, 'Unknown component'

    if comp_id == 'dgserver_m':
        home = svcs.get('dgserver_m', '')
        if not home:
            return json.dumps({'ok': False, 'message': 'DGServer_M 경로가 설정되지 않았습니다.'})
        if action == 'start':
            ok, msg = _start_dgserver(home)
        elif action == 'stop':
            ok, msg = _stop_dgserver(home)
        elif action == 'restart':
            _stop_dgserver(home)
            time.sleep(5)
            ok, msg = _start_dgserver(home)

    elif comp_id.startswith('dgserver_s_'):
        idx = int(comp_id.split('_')[-1]) - 1
        dgs_list = svcs.get('dgserver_s', [])
        if idx < 0 or idx >= len(dgs_list) or not dgs_list[idx]:
            return json.dumps({'ok': False, 'message': 'DGServer_S%d 경로가 설정되지 않았습니다.' % (idx + 1)})
        home = dgs_list[idx]
        if action == 'start':
            ok, msg = _start_dgserver(home)
        elif action == 'stop':
            ok, msg = _stop_dgserver(home)
        elif action == 'restart':
            _stop_dgserver(home)
            time.sleep(5)
            ok, msg = _start_dgserver(home)

    elif comp_id == 'platformjs':
        pjs_home = svcs.get('platformjs', '')
        if not pjs_home:
            return json.dumps({'ok': False, 'message': 'PlatformJS 경로가 설정되지 않았습니다.'})
        if action == 'start':
            ok, msg = _start_platformjs(pjs_home)
        elif action == 'stop':
            ok, msg = _stop_platformjs(pjs_home)
        elif action == 'restart':
            _stop_platformjs(pjs_home)
            time.sleep(5)
            ok, msg = _start_platformjs(pjs_home)

    elif comp_id == 'postgresql':
        if 'oracle' in repo.get('db_type', '').lower():
            return json.dumps({'ok': False, 'message': 'Oracle DB는 원격 제어를 지원하지 않습니다.'})
        if action == 'start':
            ok, msg = _start_postgresql()
        elif action == 'stop':
            ok, msg = _stop_postgresql()
        elif action == 'restart':
            _stop_postgresql()
            time.sleep(5)
            ok, msg = _start_postgresql()

    return json.dumps({'ok': ok, 'message': msg})
