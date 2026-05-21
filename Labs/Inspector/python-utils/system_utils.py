# -*- coding: utf-8 -*-
import os
import re
import socket
import subprocess
import time

from service_config import load_service_config
from db_utils import run_db_query, _parse_db_table
from sql_library import _SQL_ORACLE_TABLESPACE_OVERVIEW


# ── file helpers ─────────────────────────────────────────────────────────────────

def _read_lines(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.readlines()
    except Exception:
        return []


# ── system metrics ───────────────────────────────────────────────────────────────

def _run(cmd):
    try:
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        return out.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def _proc_snapshot_top(n=20):
    """Top N processes by max(cpu%, mem%) — INSP_PROC_HISTORY 수집용.

    분당 1회 호출. `ps -eo ...` 한 번 + python 정렬 1회로 가벼움.
    반환: list of dict — keys: pid, user, cpu_pct, mem_pct, rss_kb, vsz_kb,
                                threads, etime, comm, args (args 256자 cap).
    추후 'Inspector History > CPU/Memory 화면에서 특정 시점 하단 프로세스 목록'
    표출 목적이며, 현재는 백엔드 수집만 진행. 실패는 silent.
    """
    out = _run("ps -eo pid,user,%cpu,%mem,rss,vsz,nlwp,etime,comm,args --no-headers")
    if not out:
        return []
    rows = []
    for line in out.splitlines():
        parts = line.split(None, 9)
        if len(parts) < 10:
            continue
        try:
            rows.append({
                "pid":     int(parts[0]),
                "user":    parts[1][:64],
                "cpu_pct": float(parts[2]),
                "mem_pct": float(parts[3]),
                "rss_kb":  int(parts[4]),
                "vsz_kb":  int(parts[5]),
                "threads": int(parts[6]),
                "etime":   parts[7][:32],
                "comm":    parts[8][:64],
                "args":    parts[9][:256],
            })
        except (ValueError, IndexError):
            continue
    # max(cpu, mem) 기준으로 top N 추출 — cpu 만 또는 mem 만 높아도 포함.
    rows.sort(key=lambda r: max(r["cpu_pct"], r["mem_pct"]), reverse=True)
    return rows[:n]


def _cpu_percent():
    try:
        def read_stat():
            with open("/proc/stat") as f:
                line = f.readline()
            return list(map(int, line.split()[1:]))
        v1 = read_stat()
        time.sleep(0.3)
        v2 = read_stat()
        dt = sum(v2) - sum(v1)
        if dt == 0:
            return {"percent": 0.0, "user": 0.0, "system": 0.0, "iowait": 0.0}
        def pct(idx):
            return round((v2[idx] - v1[idx]) / float(dt) * 100, 1)
        idle_diff = v2[3] - v1[3]
        total = round((1.0 - idle_diff / float(dt)) * 100, 1)
        return {"percent": total, "user": pct(0), "system": pct(2), "iowait": pct(4)}
    except Exception:
        return {"percent": 0.0, "user": 0.0, "system": 0.0, "iowait": 0.0}


def _pct_status(pct, warn, crit):
    if pct >= crit:  return "critical"
    if pct >= warn:  return "warning"
    return "ok"


def _memory():
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":")
                info[k.strip()] = int(v.strip().split()[0])
        total   = info.get("MemTotal", 0)
        free_kb = info.get("MemFree", 0)
        buffers = info.get("Buffers", 0)
        cached  = info.get("Cached", 0)
        used    = total - free_kb - buffers - cached
        free    = total - used
        def to_gb(kb): return round(kb / 1048576.0, 1)
        pct = round(used / float(total) * 100, 1) if total else 0
        return {"total_gb": to_gb(total), "used_gb": to_gb(used),
                "free_gb": to_gb(free), "percent": pct,
                "status": _pct_status(pct, 80, 90)}
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0, "status": "ok"}


def _disk_path(path):
    """Return disk usage for a given path."""
    try:
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize
        free  = st.f_bavail * st.f_frsize
        used  = total - free
        def to_gb(b): return round(b / 1073741824.0, 1)
        pct = round(used / float(total) * 100, 1) if total else 0
        return {"path": path, "total_gb": to_gb(total), "used_gb": to_gb(used),
                "free_gb": to_gb(free), "percent": pct,
                "status": _pct_status(pct, 80, 90), "error": None}
    except Exception as e:
        return {"path": path, "total_gb": 0, "used_gb": 0, "free_gb": 0,
                "percent": 0, "status": "ok", "error": str(e)}


def _disk():
    return _disk_path("/")


def _disk_for_overview():
    """Return OS disk info (used for PG overview)."""
    cfg     = load_service_config()
    repo    = cfg.get("repository", {})
    pg_data = repo.get("pg_data_dir", "").strip()
    if pg_data:
        return _disk_path(pg_data)
    return _disk_path("/")


_TS_CACHE   = {'data': None, 'ts': 0}
_TS_TTL     = 300  # 5 minutes
_TS_ERR_TTL = 30   # 30 seconds for errors

def _tablespace_for_overview(force=False):
    """Query Oracle tablespace usage. Returns list of dicts or error string."""
    import time as _time
    if (not force
            and _TS_CACHE['data'] is not None
            and (_time.time() - _TS_CACHE['ts']) < _TS_TTL):
        return _TS_CACHE['data']
    def _cache_err(msg):
        _TS_CACHE['data'] = msg
        _TS_CACHE['ts']   = _time.time() - _TS_TTL + _TS_ERR_TTL
        return msg
    out, err = run_db_query(_SQL_ORACLE_TABLESPACE_OVERVIEW)
    if err:
        return _cache_err(err)
    raw = (out or "").strip()
    if not raw:
        return _cache_err("No output from Oracle. Check DB connection in Configuration.")
    headers, rows = _parse_db_table(raw)
    if not rows:
        return _cache_err("Could not parse tablespace data. Output: " + raw[:300].replace("<", "&lt;"))
    result = []
    for row in rows:
        try:
            if len(row) < 5:
                continue
            name     = str(row[0]).strip()
            used_gb  = float(row[1])
            total_gb = float(row[2])
            free_gb  = float(row[3])
            pct      = float(row[4])
            if not name:
                continue
            status = _pct_status(pct, 80, 90)
            result.append({"name": name, "used_gb": used_gb, "total_gb": total_gb,
                           "free_gb": free_gb, "percent": pct, "status": status})
        except (ValueError, IndexError):
            continue
    if not result:
        return _cache_err("Could not parse tablespace data. Output: " + raw[:300].replace("<", "&lt;"))
    _TS_CACHE['data'] = result
    _TS_CACHE['ts']   = _time.time()
    return result


def _uptime():
    try:
        with open("/proc/uptime") as f:
            sec = int(float(f.read().split()[0]))
        d, r = divmod(sec, 86400)
        h, r = divmod(r, 3600)
        m, s = divmod(r, 60)
        parts = []
        if d: parts.append("%dd" % d)
        if h: parts.append("%dh" % h)
        if m: parts.append("%dm" % m)
        parts.append("%ds" % s)
        return " ".join(parts)
    except Exception:
        return "-"


def _cpu_cores():
    try:
        count = 0
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("processor"):
                    count += 1
        return count
    except Exception:
        return "-"


# ── process / service checkers ───────────────────────────────────────────────────

def _find_ss_bin():
    """ss often lives in /usr/sbin which is NOT on python-utils' PATH when
    started via nohup. Return an absolute path we can actually execute."""
    for p in ("/usr/sbin/ss", "/sbin/ss", "/usr/bin/ss"):
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    # fall through to $PATH lookup (unlikely to succeed if the above failed)
    out = _run("command -v ss 2>/dev/null").strip()
    return out or None


def _port_is_listening(port):
    """Return True if something is LISTENing on the port, even if we cannot
    see the owner PID (non-privileged /proc/net visibility)."""
    ss_bin = _find_ss_bin()
    if ss_bin:
        if _run("%s -tln 2>/dev/null | grep -E ':%s[[:space:]]'" % (ss_bin, port)):
            return True
    if _run("netstat -tln 2>/dev/null | grep -E ':%s[[:space:]]'" % port):
        return True
    return False


def _get_pid_by_port(port):
    """Resolve the PID listening on `port`. Works best when the caller owns
    the process; on systems where ss/netstat hide PIDs from non-root we may
    return None even though the port is bound — callers should combine this
    with a ps-based fallback (see _pid_by_cmdline_pattern)."""
    try:
        ss_bin = _find_ss_bin()
        out = ""
        if ss_bin:
            out = _run("%s -tlnp 2>/dev/null | grep -E ':%s[[:space:]]'" % (ss_bin, port))
        if not out:
            out = _run("netstat -tlnp 2>/dev/null | grep -E ':%s[[:space:]]'" % port)
        if not out:
            return None
        for part in out.split():
            if "pid=" in part:
                return part.split("pid=")[-1].split(",")[0]
            if "/" in part and part.split("/")[0].isdigit():
                return part.split("/")[0]
        return None
    except Exception:
        return None


def _pid_by_cmdline_pattern(grep_args):
    """Find a PID whose ps -ef line matches ALL given grep patterns.
    grep_args: list of literal strings to match (each via `grep`). Used as
    a fallback for status detection when port-based PID lookup fails."""
    try:
        pipeline = "ps -ef"
        for g in grep_args:
            safe = g.replace('"', '\\"')
            pipeline += ' | grep -- "%s"' % safe
        pipeline += " | grep -v grep | awk '{print $2}'"
        out = _run(pipeline).strip()
        if not out:
            return None
        pid = out.split('\n')[0].strip()
        return pid if pid.isdigit() else None
    except Exception:
        return None


def _dgserver_pid_by_name(dg_name):
    """PID of the running DGServer.jar for a given DG_NAME (e.g. DG_M_ORA2311)."""
    if not dg_name:
        return None
    return _pid_by_cmdline_pattern(["-" + dg_name + " ", "DGServer.jar"])


def _platformjs_pid_by_port(pjs_port):
    """PID of the PlatformJS jetty process identified by its -DPJS<port> flag."""
    if not pjs_port:
        return None
    pid = _pid_by_cmdline_pattern(["-DPJS" + str(pjs_port), "start.jar"])
    if pid:
        return pid
    # Some builds omit -DPJS; fall back to port + jetty marker.
    return _pid_by_cmdline_pattern(["jetty.port=" + str(pjs_port), "start.jar"])


def _proc_start_time(pid):
    """Return process start time as 'YYYY-MM-DD HH:MM:SS' or '-'."""
    if not pid or pid == "-":
        return "-"
    try:
        from datetime import datetime
        out = _run("ps -p %s -o lstart=" % pid).strip()
        if not out:
            return "-"
        dt = datetime.strptime(out.strip(), "%a %b %d %H:%M:%S %Y")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "-"


def _proc_uptime(pid):
    if not pid or pid == "-":
        return "-"
    try:
        out = _run("ps -p %s -o etime=" % pid).strip()
        if not out:
            return "-"
        out = out.strip()
        parts = out.replace('-', ':').split(':')
        parts = [int(x) for x in parts]
        if len(parts) == 2:
            total = parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            total = parts[0] * 3600 + parts[1] * 60 + parts[2]
        else:
            total = parts[0] * 86400 + parts[1] * 3600 + parts[2] * 60 + parts[3]
        d, r = divmod(total, 86400)
        h, r = divmod(r, 3600)
        m, s = divmod(r, 60)
        result = []
        if d: result.append("%dd" % d)
        if h: result.append("%dh" % h)
        if m: result.append("%dm" % m)
        result.append("%ds" % s)
        return " ".join(result)
    except Exception:
        return "-"


def _proc_uptime_html(pid):
    """Return uptime text with tooltip showing start time."""
    uptime = _proc_uptime(pid)
    if uptime == "-":
        return "-"
    start = _proc_start_time(pid)
    return '<span title="Started: %s" style="cursor:default;">%s</span>' % (start, uptime)


def _xml_val(xmlfile, tag):
    try:
        with open(xmlfile) as f:
            content = f.read()
        m = re.search(r'<' + tag + r'[^>]*>([^<]+)</' + tag + r'>', content)
        return m.group(1).strip() if m else ''
    except Exception:
        return ''



def _check_tcp(host, port):
    try:
        s = socket.socket()
        s.settimeout(3)
        s.connect((host, int(port)))
        s.close()
        return True
    except Exception:
        return False


def _dg_info(home):
    if not home or not os.path.isdir(home):
        return {"exists": False, "home": home or ""}
    xmlfile   = os.path.join(home, "conf", "DGServer.xml")
    port      = _xml_val(xmlfile, "gather_port")
    repo_type = _xml_val(xmlfile, "database_type")
    repo_ip   = _xml_val(xmlfile, "database_ip")
    repo_port = _xml_val(xmlfile, "database_port")
    repo_sid  = _xml_val(xmlfile, "database_sid") or _xml_val(xmlfile, "database_database")
    pid       = _get_pid_by_port(port) if port else None
    # Port-based PID lookup fails when ss/netstat cannot show the owner
    # (non-privileged /proc/net visibility). Fall back to ps by DG_NAME so the
    # UI reports RUNNING whenever the jar is actually up.
    dg_name = ""
    if not pid:
        mxgrc_path = os.path.join(home, ".mxgrc")
        if os.path.isfile(mxgrc_path):
            try:
                with open(mxgrc_path) as _f:
                    for _line in _f:
                        _line = _line.strip()
                        if _line.startswith("export "):
                            _line = _line[7:]
                        if "=" in _line and _line.split("=", 1)[0].strip() == "DG_NAME":
                            dg_name = _line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception:
                pass
        if dg_name:
            pid = _dgserver_pid_by_name(dg_name)
    status = "running" if pid else ("running" if (port and _port_is_listening(port)) else "stopped")
    return {
        "exists": True, "home": home,
        "port": port or "-", "pid": pid or "-",
        "status": status,
        "repo_type": repo_type or "-", "repo_ip": repo_ip or "-",
        "repo_port": repo_port or "-", "repo_sid": repo_sid or "-",
    }


def _repodb_info():
    repo  = load_service_config().get("repository", {})
    host  = repo.get("ip", "")
    port  = repo.get("port", "")
    if not host or not port:
        return {"status": "unconfigured", "host": "-", "port": "-",
                "db_type": repo.get("db_type", "-"), "sid": "-", "user": "-"}
    up = _check_tcp(host, port)
    return {"status": "running" if up else "stopped",
            "host": host, "port": port,
            "db_type": repo.get("db_type", "-"),
            "sid": repo.get("sid", ""), "user": repo.get("user", "")}


def _get_repodb_version():
    try:
        cfg     = _db_cfg_local()
        db_type = cfg.get("db_type", "Oracle").lower()
        if "oracle" in db_type:
            sql = (
                "SELECT CASE WHEN TO_NUMBER(SUBSTR(VERSION, 1, INSTR(VERSION, '.') - 1)) >= 18 "
                "THEN VERSION_FULL ELSE VERSION END AS DB_VERSION FROM V$INSTANCE;"
            )
        else:
            sql = "SELECT current_setting('server_version') AS db_version;"
        out, err = run_db_query(sql)
        if err or not out:
            return "-"
        try:
            headers, rows = _parse_db_table(out)
            if rows and rows[0]:
                return str(rows[0][0]).strip()
        except Exception:
            pass
        for line in reversed(out.strip().split('\n')):
            line = line.strip()
            if line and not line.startswith('-') and not line.startswith('('):
                return line
        return "-"
    except Exception:
        return "-"


def _get_repodb_uptime():
    from datetime import datetime
    try:
        cfg     = _db_cfg_local()
        db_type = cfg.get("db_type", "Oracle").lower()
        if "oracle" in db_type:
            sql = "SELECT TO_CHAR(STARTUP_TIME, 'YYYY-MM-DD HH24:MI:SS') AS start_time FROM V$INSTANCE"
        else:
            sql = "SELECT to_char(pg_postmaster_start_time(), 'YYYY-MM-DD HH24:MI:SS') AS start_time"
        out, err = run_db_query(sql)
        if err or not out:
            return "-"
        headers, rows = _parse_db_table(out)
        if not rows or not rows[0]:
            return "-"
        val = str(rows[0][0]).strip()
        if not val or val == "None":
            return "-"
        try:
            dt      = datetime.strptime(val[:19], "%Y-%m-%d %H:%M:%S")
            elapsed = int((datetime.now() - dt).total_seconds())
            if elapsed < 0:
                return "-"
            d = elapsed // 86400
            h = (elapsed % 86400) // 3600
            m = (elapsed % 3600) // 60
            if d > 0:
                upstr = "{0}d {1}h {2}m".format(d, h, m)
            elif h > 0:
                upstr = "{0}h {1}m".format(h, m)
            else:
                upstr = "{0}m".format(m)
            return '<span title="Started: {0}" style="cursor:default;">{1}</span>'.format(val[:19], upstr)
        except ValueError:
            return val
    except Exception:
        return "-"


def _db_cfg_local():
    return load_service_config().get("repository", {})


# ── version helpers ───────────────────────────────────────────────────────────────

def _find_java():
    """Resolve java binary path. 하드코딩된 시스템 경로 없이 다음 순서로 탐색:

      1) config.yaml 의 java.path  — 명시적 override (auth.py / decrypt.py 와 통일)
      2) $JAVA_HOME/bin/java
      3) bash login shell 의 PATH (~/.bash_profile 반영) — `bash -lc 'command -v java'`
         python-utils 는 nohup 으로 떠서 자체 PATH 가 비어있으므로 login shell 통해 우회.
      4) ~/jdk*/bin/java · ~/jdk*/jre/bin/java glob — 사용자 홈에 풀어둔 JDK 자동 발견
      5) 다 실패 → "java" 문자열 (실행시 실패하지만 graceful)
    """
    def _ok(p):
        return p and os.path.isfile(p) and os.access(p, os.X_OK)

    # 1) config.yaml java.path
    try:
        import config_loader
        cfg = config_loader.load()
        if hasattr(config_loader, 'get_java_path'):
            cfg_path = config_loader.get_java_path(cfg)
            if _ok(cfg_path):
                return cfg_path
    except Exception:
        pass

    # 2) JAVA_HOME
    java_home = os.environ.get("JAVA_HOME", "")
    if java_home:
        cand = os.path.join(java_home, "bin", "java")
        if _ok(cand):
            return cand

    # 3) bash login shell PATH 통해 찾기
    try:
        out = subprocess.check_output(
            ['bash', '-lc', 'command -v java'],
            stderr=subprocess.DEVNULL, timeout=5
        ).decode('utf-8', errors='ignore').strip()
        # symlink 일 수 있으니 realpath 로 풀어 실제 실행 파일 확인
        if out:
            real = os.path.realpath(out)
            if _ok(real):
                return real
            if _ok(out):
                return out
    except Exception:
        pass

    # 4) ~/jdk*/bin/java glob — jdk 이름 안의 첫 숫자(메이저 버전)가 큰 쪽 우선
    import glob as _glob, re as _re
    home = os.path.expanduser("~")
    cands = (_glob.glob(os.path.join(home, "jdk*", "bin", "java"))
             + _glob.glob(os.path.join(home, "jdk*", "jre", "bin", "java")))
    def _ver_key(p):
        m = _re.search(r'/jdk(\d+)', p)
        return int(m.group(1)) if m else 0
    for p in sorted(cands, key=_ver_key, reverse=True):
        if _ok(p):
            return p

    return "java"


def _run_jar(java, jar, args):
    """Run java -jar <jar> <args> and return stdout+stderr regardless of exit code."""
    try:
        proc = subprocess.Popen(
            [java, "-jar", jar] + args,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out, _ = proc.communicate()
        return out.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _get_dg_version(home):
    if not home or not os.path.isdir(home):
        return "-"
    jar = os.path.join(home, "bin", "DGServer.jar")
    if not os.path.isfile(jar):
        return "-"
    out = _run_jar(_find_java(), jar, ["-v"])
    m = re.search(r'MaxGauge\s*([0-9]+(?:\.[0-9]+){2,})', out)
    if m:
        return m.group(1)
    m = re.search(r'[0-9]+(?:\.[0-9]+){2,}', out)
    return m.group(0) if m else "-"


def _find_pjs_java(pjs_home):
    """Find java binary suitable for PlatformJS.
    1. Check running PlatformJS process's java via /proc/PID/exe
    2. Fall back to _find_java()
    """
    try:
        import config_loader
        cfg = config_loader.load()
        pjs_port = config_loader.get_platformjs_port(cfg)
        pid = _get_pid_by_port(pjs_port)
        if pid:
            exe = os.path.realpath("/proc/%s/exe" % pid)
            if os.path.isfile(exe):
                return exe
    except Exception:
        pass
    return _find_java()


def _get_pjs_version(pjs_home):
    if not pjs_home or not os.path.isdir(pjs_home):
        return "-"
    jar = os.path.join(pjs_home, "svc", "www", "WEB-INF", "lib", "exem_platformjs.jar")
    if not os.path.isfile(jar):
        return "-"
    out = _run_jar(_find_pjs_java(pjs_home), jar, ["-version"])
    m = re.search(r'[0-9]+(?:\.[0-9]+){5}', out)
    if not m:
        return "-"
    ver = m.group(0)
    ver = re.sub(r'\.0\.', '.', ver, count=1)
    return ver




def _get_client_version(pjs_home):
    """Get client BuildNumber from VersionControl.js."""
    if not pjs_home or not os.path.isdir(pjs_home):
        return "-"
    vc = os.path.join(pjs_home, "svc", "www", "MAXGAUGE", "common", "VersionControl.js")
    if not os.path.exists(vc):
        return "-"
    try:
        with open(vc, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(500)
        m = re.search(r'BuildNumber="([^"]+)"', content)
        return m.group(1) if m else "-"
    except Exception:
        return "-"


def _get_pjs_port():
    """Get PlatformJS port from service_config's platformjs path config/config.json."""
    try:
        import json as _j
        svc = load_service_config()
        pjs_home = svc.get("services", {}).get("platformjs", "")
        if not pjs_home:
            return None
        cfg_file = os.path.join(pjs_home, "config", "config.json")
        if not os.path.exists(cfg_file):
            return None
        with open(cfg_file) as _f:
            cfg = _j.load(_f)
        return int(cfg.get("service_port", 0)) or None
    except Exception:
        return None


def _pjs_info(platformjs_port=None):
    if not platformjs_port:
        platformjs_port = _get_pjs_port() or 0
    pid = _get_pid_by_port(platformjs_port) or _platformjs_pid_by_port(platformjs_port)
    svc = load_service_config()
    pjs_home = svc.get("services", {}).get("platformjs", "")
    cfg_file = os.path.join(pjs_home, "config", "config.json") if pjs_home else ""
    db = {}
    if cfg_file and os.path.exists(cfg_file):
        try:
            import json as _j
            with open(cfg_file) as _f:
                _cfg = _j.load(_f)
            dbs = _cfg.get("databases", [])
            if dbs:
                db = dbs[0]
        except Exception:
            pass
    status = "running" if pid else ("running" if (platformjs_port and _port_is_listening(platformjs_port)) else "stopped")
    return {
        "port": str(platformjs_port), "pid": pid or "-",
        "status": status,
        "repo_type": str(db.get("database_type", "-")),
        "repo_ip":   str(db.get("database_server", "-")),
        "repo_port": str(db.get("database_port", "-")),
        "repo_sid":  str(db.get("database_database", "-")),
    }
