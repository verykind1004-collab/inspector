# -*- coding: utf-8 -*-
import os
import sys
import json
import threading
from datetime import datetime, timedelta

# ── bundled drivers (Labs/drivers, Labs 공용) ─────────────────────────────────
import glob as _glob
_LABS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_py3_sites = _glob.glob(
    os.path.join(_LABS_DIR, 'drivers', 'python3', 'lib', 'python3.*', 'site-packages'))
if _py3_sites and _py3_sites[0] not in sys.path:
    sys.path.insert(0, _py3_sites[0])
del _glob, _py3_sites, _LABS_DIR

from db_utils import run_db_query, _parse_db_table
from sql_library import _get_sql
from service_config import load_service_config

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── IH (Inspector History) Logger ──────────────────────────────────────────────

import zipfile as _ih_zf

_IH_LOG_DIR = os.path.join(_SCRIPT_DIR, 'log', 'IH')

def _ih_log(msg):
    """Write a timestamped log line to IH/IH_YYYYMMDD.log"""
    try:
        os.makedirs(_IH_LOG_DIR, exist_ok=True)
        fname = 'IH_' + datetime.now().strftime('%Y%m%d') + '.log'
        fpath = os.path.join(_IH_LOG_DIR, fname)
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:23]
        with open(fpath, 'a', encoding='utf-8') as f:
            f.write('[%s] %s\n' % (ts, msg))
    except Exception:
        pass


def _ih_log_collect(name, success=True, detail=''):
    """Log a collection event."""
    status = 'OK' if success else 'FAIL'
    msg = '[COLLECT] %s %s' % (name, status)
    if detail:
        msg += ' | ' + detail
    _ih_log(msg)


def _ih_rotate_logs():
    """Compress yesterday's IH log to zip, delete logs older than log_retention_days."""
    try:
        os.makedirs(_IH_LOG_DIR, exist_ok=True)
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        yesterday_log = os.path.join(_IH_LOG_DIR, 'IH_' + yesterday + '.log')
        yesterday_zip = os.path.join(_IH_LOG_DIR, 'IH_' + yesterday + '.log.zip')

        # Compress yesterday's log
        if os.path.exists(yesterday_log) and not os.path.exists(yesterday_zip):
            with _ih_zf.ZipFile(yesterday_zip, 'w', _ih_zf.ZIP_DEFLATED) as zf:
                zf.write(yesterday_log, os.path.basename(yesterday_log))
            os.remove(yesterday_log)
            _ih_log('[ROTATE] Compressed IH_%s.log' % yesterday)

        # Delete old logs/zips beyond retention
        cfg = _load_insp_config()
        ret_days = cfg.get('log_retention_days', 10)
        cutoff = (datetime.now() - timedelta(days=ret_days)).strftime('%Y%m%d')
        for fname in os.listdir(_IH_LOG_DIR):
            if not fname.startswith('IH_'):
                continue
            dm = re.search(r'IH_(\d{8})', fname)
            if dm and dm.group(1) < cutoff:
                os.remove(os.path.join(_IH_LOG_DIR, fname))
                _ih_log('[ROTATE] Deleted old log: %s' % fname)
    except Exception as e:
        _ih_log('[ROTATE] Error: %s' % str(e))


# ── PG History (existing) ────────────────────────────────────────────────────────

_HIST_PG_HOST = '127.0.0.1'
_HIST_PG_PORT = 5432
_HIST_PG_DB   = 'MI'
_HIST_PG_USER = 'postgres'
_HIST_PG_PASS = 'postgres'


def _hist_connect():
    import psycopg2
    return psycopg2.connect(
        host=_HIST_PG_HOST, port=_HIST_PG_PORT, dbname=_HIST_PG_DB,
        user=_HIST_PG_USER, password=_HIST_PG_PASS
    )


def _ensure_partition(target_date=None):
    from datetime import date as _date
    if target_date is None:
        target_date = _date.today() + timedelta(days=1)
    d0  = target_date.strftime('%Y-%m-%d')
    d1  = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')
    tbl = 'summary_history_' + target_date.strftime('%Y%m%d')
    try:
        conn = _hist_connect()
        cur  = conn.cursor()
        cur.execute("SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE c.relname=%s AND n.nspname='public'", (tbl,))
        if not cur.fetchone():
            cur.execute(
                "CREATE TABLE %s PARTITION OF summary_history "
                "FOR VALUES FROM ('%s') TO ('%s')" % (tbl, d0, d1)
            )
            cur.execute("CREATE INDEX idx_%s_type_at ON %s(check_type, checked_at)" % (tbl, tbl))
            cur.execute("CREATE INDEX idx_%s_inst ON %s(instance, summary_type)" % (tbl, tbl))
        conn.commit()
        cur.close(); conn.close()
    except Exception:
        pass


def _insert_history(rows_data):
    try:
        conn = _hist_connect()
        cur  = conn.cursor()
        cur.executemany(
            'INSERT INTO summary_history '
            '(checked_at,check_type,instance,summary_type,status,last_summary,delay_info) '
            'VALUES (%s,%s,%s,%s,%s,%s,%s)',
            [(r[0], r[1], r[2], r[3] or None, r[4], r[5] or None, r[6] or None)
             for r in rows_data]
        )
        conn.commit()
        cur.close(); conn.close()
    except Exception:
        pass


def _collect_summary_history(check_type):
    try:
        sql_key = 'summary_10min' if check_type == '10min' else 'summary_1hour'
        sql = _get_sql(sql_key)
        if not sql:
            return
        out, err = run_db_query(sql)
        if err or not out:
            return
        headers, rows = _parse_db_table(out)
        if not rows:
            return
        h = [x.upper() for x in headers]
        idx_dbid  = next((i for i, x in enumerate(h) if x == 'DB ID'), -1)
        idx_inst  = next((i for i, x in enumerate(h) if 'INSTANCE' in x), -1)
        idx_stype = next((i for i, x in enumerate(h) if 'SUMMARY' in x and 'TYPE' in x), -1)
        idx_st    = next((i for i, x in enumerate(h) if x == 'STATUS'), -1)
        idx_last  = next((i for i, x in enumerate(h) if 'LAST' in x and 'SUMMARY' in x), -1)
        idx_delay = next((i for i, x in enumerate(h) if 'DELAY' in x), -1)
        now  = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        pg_data = []
        ora_data = []
        for row in rows:
            dbid  = row[idx_dbid].strip()  if 0 <= idx_dbid  < len(row) else ''
            inst  = row[idx_inst].strip()  if 0 <= idx_inst  < len(row) else ''
            stype = row[idx_stype].strip() if 0 <= idx_stype < len(row) else ''
            st    = row[idx_st].strip()    if 0 <= idx_st    < len(row) else ''
            last  = row[idx_last].strip()  if 0 <= idx_last  < len(row) else ''
            delay = row[idx_delay].strip() if 0 <= idx_delay < len(row) else ''
            # summary_type 이 비어있는 row 는 ora_last_summary 에 매칭 레코드가 없는
            # (한 번도 수집 안 된) 인스턴스라 의미 없는 NULL row 가 누적되므로 skip.
            if inst and st and stype:
                pg_data.append((now, check_type, inst, stype, st, last, delay))
                ora_data.append((dbid, inst, stype, st, last, delay))

        # PG: existing behavior
        if pg_data:
            _insert_history(pg_data)

        # Oracle INSP_: if enabled
        if ora_data and _is_oracle_insp_enabled():
            from insp_oracle import insp_insert_summary
            insp_insert_summary(check_type, ora_data)

        # PG INSP_: if enabled
        if ora_data and _is_pg_insp_enabled():
            from insp_pg import insp_pg_insert_summary
            insp_pg_insert_summary(check_type, ora_data)
    except Exception:
        pass


# ── INSP Config helpers ──────────────────────────────────────────────────────────

_INSP_CFG_PATH = os.path.join(_SCRIPT_DIR, 'insp_config.json')
_insp_cfg_cache = {'data': None, 'ts': 0}


def _load_insp_config():
    import time
    now = time.time()
    if _insp_cfg_cache['data'] and (now - _insp_cfg_cache['ts']) < 10:
        return _insp_cfg_cache['data']
    default = {"enabled": False, "tables_initialized": False, "retention_days": 31, "log_retention_days": 10}
    try:
        with open(_INSP_CFG_PATH, 'r') as f:
            cfg = json.load(f)
        _insp_cfg_cache['data'] = cfg
        _insp_cfg_cache['ts'] = now
        return cfg
    except Exception:
        return default


def _is_oracle_insp_enabled():
    cfg = _load_insp_config()
    if not cfg.get("enabled") or not cfg.get("tables_initialized"):
        return False
    svc = load_service_config()
    db_type = svc.get("repository", {}).get("db_type", "").lower()
    return "oracle" in db_type


def _is_pg_insp_enabled():
    cfg = _load_insp_config()
    if not cfg.get("enabled") or not cfg.get("tables_initialized"):
        return False
    svc = load_service_config()
    db_type = svc.get("repository", {}).get("db_type", "").lower()
    return "postgres" in db_type


# ── Oracle INSP collectors ───────────────────────────────────────────────────────

def _collect_os():
    """Collect CPU + Memory and insert to INSP_OS_HISTORY."""
    try:
        from system_utils import _cpu_percent, _memory
        cpu = _cpu_percent()
        mem = _memory()
        if _is_oracle_insp_enabled():
            from insp_oracle import insp_insert_os
            insp_insert_os(cpu, mem)
        if _is_pg_insp_enabled():
            from insp_pg import insp_pg_insert_os
            insp_pg_insert_os(cpu, mem)
    except Exception:
        pass


def _collect_proc():
    """Collect top-20 processes (by max cpu/mem) and insert to INSP_PROC_HISTORY.
    추후 'Inspector History > CPU/Memory 화면 시점 클릭 시 하단 프로세스 목록' 표출 용도.
    실패는 silent — 기존 _collect_os 등과 같은 정책."""
    try:
        from system_utils import _proc_snapshot_top
        rows = _proc_snapshot_top(20)
        if not rows:
            return
        if _is_oracle_insp_enabled():
            from insp_oracle import insp_insert_proc
            insp_insert_proc(rows)
        if _is_pg_insp_enabled():
            from insp_pg import insp_pg_insert_proc
            insp_pg_insert_proc(rows)
    except Exception:
        pass


def _collect_services():
    """Collect service statuses and insert to INSP_SERVICE_HISTORY."""
    try:
        from system_utils import _dg_info, _pjs_info, _repodb_info, _proc_uptime, _get_pid_by_port, _platformjs_pid_by_port
        from insp_oracle import insp_insert_services
        import config_loader

        svc = load_service_config()
        svcs = svc.get("services", {})
        _c = config_loader.load()
        pjs_port = config_loader.get_platformjs_port(_c)

        rows = []

        # DGServer_M
        dgm_home = svcs.get("dgserver_m", "")
        if dgm_home:
            info = _dg_info(dgm_home)
            st = info.get("status", "stopped") if info.get("exists") else "stopped"
            rows.append(("DGServer_M", st.upper(),
                         info.get("pid", "-"), info.get("port", "-"),
                         _proc_uptime(info.get("pid", "-"))))

        # DGServer_S
        for i, dgs_home in enumerate(svcs.get("dgserver_s", [])):
            if not dgs_home:
                continue
            info = _dg_info(dgs_home)
            st = info.get("status", "stopped") if info.get("exists") else "stopped"
            rows.append(("DGServer_S%d" % (i + 1), st.upper(),
                         info.get("pid", "-"), info.get("port", "-"),
                         _proc_uptime(info.get("pid", "-"))))

        # PlatformJS
        pjs_pid = _get_pid_by_port(pjs_port) or _platformjs_pid_by_port(pjs_port)
        rows.append(("PlatformJS", "RUNNING" if pjs_pid else "STOPPED",
                     pjs_pid or "-", str(pjs_port), _proc_uptime(pjs_pid)))

        # Repository DB
        rdb = _repodb_info()
        rows.append(("Repository DB", rdb["status"].upper(),
                     "-", rdb["port"], "-"))

        if _is_oracle_insp_enabled():
            insp_insert_services(rows)
        if _is_pg_insp_enabled():
            from insp_pg import insp_pg_insert_services
            insp_pg_insert_services(rows)
    except Exception:
        pass


_last_heap_ts = {}  # {svc_name: 'YYYY-MM-DD HH:MM'} — track last collected minute per service


def _collect_heap():
    """Parse DGS logs for DG MANAGER Heap info with per-minute timestamps.
    - Parses [HH:MM:SS.mmm] from each log line
    - Groups by minute, keeps last value per minute
    - Only inserts minutes newer than previously collected
    """
    import re
    import subprocess
    global _last_heap_ts
    try:
        svc = load_service_config()
        svcs = svc.get("services", {})
        log_paths = svc.get("log_paths", {})
        today = datetime.now().strftime('%Y-%m-%d')
        all_rows = []  # list of (svc_name, 'YYYY-MM-DD HH:MM:SS', used, alloc, max_mb)

        time_pat = re.compile(r'^\[(\d{2}:\d{2}):\d{2}\.\d{3}\]')
        heap_pat = re.compile(r'Heap\s+(\d+)/(\d+)\((\d+)MB\)')

        for i, dgs_home in enumerate(svcs.get("dgserver_s", [])):
            if not dgs_home:
                continue
            svc_name = "DGServer_S%d" % (i + 1)
            dgs_log_dir = ""
            dgs_logs = log_paths.get("dgserver_s", [])
            if i < len(dgs_logs) and dgs_logs[i]:
                dgs_log_dir = dgs_logs[i]
            else:
                dgs_log_dir = os.path.join(dgs_home, "log")
            if not os.path.isdir(dgs_log_dir):
                continue
            from system_utils import _xml_val
            xmlfile = os.path.join(dgs_home, "conf", "DGServer.xml")
            port = _xml_val(xmlfile, "gather_port")
            if port:
                logfile = os.path.join(dgs_log_dir, "DGS_%s.log" % port)
            else:
                candidates = [f for f in os.listdir(dgs_log_dir)
                              if f.startswith("DGS_") and f.endswith(".log")]
                if not candidates:
                    continue
                candidates.sort(key=lambda f: os.path.getmtime(os.path.join(dgs_log_dir, f)), reverse=True)
                logfile = os.path.join(dgs_log_dir, candidates[0])
            if not os.path.exists(logfile):
                continue
            try:
                proc = subprocess.Popen(['grep', 'Heap', logfile],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, _ = proc.communicate(timeout=10)
                lines = out.decode('utf-8', errors='replace').splitlines()
                # Keep only last 1440 lines (max 1 day of 1-min data)
                if len(lines) > 1440:
                    lines = lines[-1440:]
            except Exception:
                continue

            # Parse all Heap lines with timestamps, group by minute (last value wins)
            minute_map = {}  # {'HH:MM': (used, alloc, max_mb)}
            for line in lines:
                hm = heap_pat.search(line)
                if not hm:
                    continue
                tm = time_pat.search(line)
                if not tm:
                    continue
                hhmm = tm.group(1)  # 'HH:MM'
                minute_map[hhmm] = (int(hm.group(1)), int(hm.group(2)), int(hm.group(3)))

            if not minute_map:
                continue

            # Filter: only minutes newer than last collected
            last_ts = _last_heap_ts.get(svc_name, '')  # 'YYYY-MM-DD HH:MM' or ''
            new_last = last_ts
            for hhmm in sorted(minute_map.keys()):
                full_ts = today + ' ' + hhmm  # 'YYYY-MM-DD HH:MM'
                if full_ts <= last_ts:
                    continue
                used, alloc, max_mb = minute_map[hhmm]
                collected_at = full_ts + ':00'  # 'YYYY-MM-DD HH:MM:00'
                all_rows.append((svc_name, collected_at, used, alloc, max_mb))
                if full_ts > new_last:
                    new_last = full_ts
            if new_last > last_ts:
                _last_heap_ts[svc_name] = new_last

        if all_rows and _is_pg_insp_enabled():
            from insp_pg import insp_pg_insert_heap
            insp_pg_insert_heap(all_rows)
        if all_rows and _is_oracle_insp_enabled():
            from insp_oracle import insp_insert_heap
            insp_insert_heap(all_rows)
        return bool(all_rows)
    except Exception:
        return False


_last_qcnt_ts = {}  # {svc_name: 'YYYY-MM-DD HH:MM'} — track last collected minute per service


def _collect_qcnt():
    """Parse DGS logs for conn_info with per-minute timestamps.
    - Parses [HH:MM:SS.mmm] from each log line
    - Groups by minute, keeps last value per minute
    - Only inserts minutes newer than previously collected
    """
    import re
    import subprocess
    global _last_qcnt_ts
    try:
        svc = load_service_config()
        svcs = svc.get("services", {})
        log_paths = svc.get("log_paths", {})
        today = datetime.now().strftime('%Y-%m-%d')
        all_rows = []  # list of (svc_name, 'YYYY-MM-DD HH:MM:SS', act, total, max_conn, qcnt)

        time_pat = re.compile(r'^\[(\d{2}:\d{2}):\d{2}\.\d{3}\]')
        qcnt_pat = re.compile(r'conn_info.*total\s*\(\s*(\d+)/(\d+)/(\d+)\[(\d+)\]\s*\)')

        for i, dgs_home in enumerate(svcs.get("dgserver_s", [])):
            if not dgs_home:
                continue
            svc_name = "DGServer_S%d" % (i + 1)
            dgs_log_dir = ""
            dgs_logs = log_paths.get("dgserver_s", [])
            if i < len(dgs_logs) and dgs_logs[i]:
                dgs_log_dir = dgs_logs[i]
            else:
                dgs_log_dir = os.path.join(dgs_home, "log")
            if not os.path.isdir(dgs_log_dir):
                continue
            from system_utils import _xml_val
            xmlfile = os.path.join(dgs_home, "conf", "DGServer.xml")
            port = _xml_val(xmlfile, "gather_port")
            if port:
                logfile = os.path.join(dgs_log_dir, "DGS_%s.log" % port)
            else:
                candidates = [f for f in os.listdir(dgs_log_dir)
                              if f.startswith("DGS_") and f.endswith(".log")]
                if not candidates:
                    continue
                candidates.sort(key=lambda f: os.path.getmtime(os.path.join(dgs_log_dir, f)), reverse=True)
                logfile = os.path.join(dgs_log_dir, candidates[0])
            if not os.path.exists(logfile):
                continue
            try:
                proc = subprocess.Popen(['grep', 'conn_info', logfile],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, _ = proc.communicate(timeout=10)
                lines = out.decode('utf-8', errors='replace').splitlines()
                if len(lines) > 1440:
                    lines = lines[-1440:]
            except Exception:
                continue

            # Parse all conn_info lines with timestamps, group by minute (last value wins)
            minute_map = {}  # {'HH:MM': (act, total, max_conn, qcnt)}
            for line in lines:
                qm = qcnt_pat.search(line)
                if not qm:
                    continue
                tm = time_pat.search(line)
                if not tm:
                    continue
                hhmm = tm.group(1)
                minute_map[hhmm] = (int(qm.group(1)), int(qm.group(2)),
                                    int(qm.group(3)), int(qm.group(4)))

            if not minute_map:
                continue

            # Filter: only minutes newer than last collected
            last_ts = _last_qcnt_ts.get(svc_name, '')
            new_last = last_ts
            for hhmm in sorted(minute_map.keys()):
                full_ts = today + ' ' + hhmm
                if full_ts <= last_ts:
                    continue
                act, total, max_conn, qcnt = minute_map[hhmm]
                collected_at = full_ts + ':00'
                all_rows.append((svc_name, collected_at, act, total, max_conn, qcnt))
                if full_ts > new_last:
                    new_last = full_ts
            if new_last > last_ts:
                _last_qcnt_ts[svc_name] = new_last

        if all_rows and _is_pg_insp_enabled():
            from insp_pg import insp_pg_insert_qcnt
            insp_pg_insert_qcnt(all_rows)
        if all_rows and _is_oracle_insp_enabled():
            from insp_oracle import insp_insert_qcnt
            insp_insert_qcnt(all_rows)
        return bool(all_rows)
    except Exception:
        return False


def _collect_tablespace():
    """Collect tablespace/disk usage and insert to INSP_TBS_HISTORY."""
    try:
        if _is_oracle_insp_enabled():
            from system_utils import _tablespace_for_overview
            from insp_oracle import insp_insert_tbs
            data = _tablespace_for_overview(force=True)
            if isinstance(data, list):
                insp_insert_tbs(data)
        if _is_pg_insp_enabled():
            from system_utils import _disk_for_overview
            from insp_pg import insp_pg_insert_tbs
            disk = _disk_for_overview()
            if isinstance(disk, dict) and not disk.get("error"):
                insp_pg_insert_tbs([{
                    "name": disk.get("path", "/"),
                    "used_gb": disk["used_gb"],
                    "total_gb": disk["total_gb"],
                    "free_gb": disk["free_gb"],
                    "percent": disk["percent"],
                    "status": disk["status"],
                }])
    except Exception:
        pass



def _collect_monthly_summary():
    """Aggregate last month's CPU/Memory/Disk into insp_monthly_summary.
    Runs on the 1st of each month at 00:10.
    """
    from datetime import date
    try:
        today = date.today()
        if today.month == 1:
            year_month = '%d-12' % (today.year - 1)
            start = '%d-12-01' % (today.year - 1)
        else:
            year_month = '%d-%02d' % (today.year, today.month - 1)
            start = '%d-%02d-01' % (today.year, today.month - 1)
        end = today.strftime('%Y-%m-01')

        if _is_pg_insp_enabled():
            from insp_pg import _insp_pg_connect, insp_pg_upsert_monthly_summary
            conn = _insp_pg_connect()
            if not conn:
                return
            cur = conn.cursor()
            cur.execute(
                "SELECT ROUND(AVG(cpu_percent)::numeric,1), "
                "       ROUND(AVG(mem_percent)::numeric,1), "
                "       ROUND(AVG(mem_used_gb)::numeric,1), "
                "       ROUND(AVG(mem_total_gb)::numeric,1), "
                "       COUNT(*) "
                "FROM insp.insp_os_history "
                "WHERE collected_at >= %s AND collected_at < %s",
                (start, end)
            )
            os_row = cur.fetchone()
            cur.execute(
                "SELECT ROUND(AVG(used_percent)::numeric,1), "
                "       ROUND(AVG(used_gb)::numeric,1), "
                "       ROUND(AVG(total_gb)::numeric,1) "
                "FROM insp.insp_tbs_history "
                "WHERE collected_at >= %s AND collected_at < %s",
                (start, end)
            )
            tbs_row = cur.fetchone()
            cur.close(); conn.close()
            if os_row and os_row[4] and int(os_row[4]) > 0:
                insp_pg_upsert_monthly_summary(
                    year_month=year_month,
                    cpu_avg=float(os_row[0] or 0),
                    mem_avg=float(os_row[1] or 0),
                    mem_used_gb=float(os_row[2] or 0),
                    mem_total_gb=float(os_row[3] or 0),
                    disk_avg=float(tbs_row[0] or 0) if tbs_row and tbs_row[0] else 0,
                    disk_used_gb=float(tbs_row[1] or 0) if tbs_row and tbs_row[1] else 0,
                    disk_total_gb=float(tbs_row[2] or 0) if tbs_row and tbs_row[2] else 0,
                    sample_count=int(os_row[4]),
                )
                _ih_log_collect('Monthly Summary (%s)' % year_month)

        if _is_oracle_insp_enabled():
            from insp_oracle import _insp_connect, insp_upsert_monthly_summary
            conn = _insp_connect()
            if not conn:
                return
            cur = conn.cursor()
            cur.execute(
                "SELECT ROUND(AVG(CPU_PERCENT),1), ROUND(AVG(MEM_PERCENT),1), "
                "       ROUND(AVG(MEM_USED_GB),1), ROUND(AVG(MEM_TOTAL_GB),1), COUNT(*) "
                "FROM INSP_OS_HISTORY "
                "WHERE COLLECTED_AT >= TO_TIMESTAMP(:1,'YYYY-MM-DD') "
                "  AND COLLECTED_AT <  TO_TIMESTAMP(:2,'YYYY-MM-DD')",
                (start, end)
            )
            os_row = cur.fetchone()
            cur.execute(
                "SELECT ROUND(AVG(USED_PERCENT),1), ROUND(AVG(USED_GB),1), ROUND(AVG(TOTAL_GB),1) "
                "FROM INSP_TBS_HISTORY "
                "WHERE COLLECTED_AT >= TO_TIMESTAMP(:1,'YYYY-MM-DD') "
                "  AND COLLECTED_AT <  TO_TIMESTAMP(:2,'YYYY-MM-DD')",
                (start, end)
            )
            tbs_row = cur.fetchone()
            conn.commit(); cur.close(); conn.close()
            if os_row and os_row[4] and int(os_row[4]) > 0:
                insp_upsert_monthly_summary(
                    year_month=year_month,
                    cpu_avg=float(os_row[0] or 0),
                    mem_avg=float(os_row[1] or 0),
                    mem_used_gb=float(os_row[2] or 0),
                    mem_total_gb=float(os_row[3] or 0),
                    disk_avg=float(tbs_row[0] or 0) if tbs_row and tbs_row[0] else 0,
                    disk_used_gb=float(tbs_row[1] or 0) if tbs_row and tbs_row[1] else 0,
                    disk_total_gb=float(tbs_row[2] or 0) if tbs_row and tbs_row[2] else 0,
                    sample_count=int(os_row[4]),
                )
                _ih_log_collect('Monthly Summary Oracle (%s)' % year_month)
    except Exception as e:
        _ih_log('[MONTHLY] Error: %s' % str(e))


def _do_retention_cleanup():
    """Drop old INSP_ partitions based on retention_days."""
    try:
        cfg = _load_insp_config()
        days = cfg.get("retention_days", 31)
        if _is_oracle_insp_enabled():
            from insp_oracle import insp_cleanup_old_partitions
            insp_cleanup_old_partitions(days)
        if _is_pg_insp_enabled():
            from insp_pg import insp_pg_cleanup_old_partitions
            insp_pg_cleanup_old_partitions(days)
    except Exception:
        pass


# ── Nginx log rotation ────────────────────────────────────────────────────────

def _rotate_nginx_logs():
    """Rotate nginx access/login logs daily: rename current to YYYY-MM-DD.log"""
    try:
        import config_loader
        cfg = config_loader.load()
        import config_loader
        _gw_cfg = config_loader.load()
        gateway_dir = _gw_cfg.get('gateway', {}).get('path', '') or os.path.join(os.path.dirname(_SCRIPT_DIR), 'gateway')
        log_dir = os.path.join(gateway_dir, 'log', 'access')
        pid_file = os.path.join(gateway_dir, 'log', 'nginx.pid')

        if not os.path.isdir(log_dir):
            return

        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        rotated = False
        for src_name, dst_prefix in [('access.log', yesterday + '_access.log'),
                                      ('login_audit.log', yesterday + '_login.log')]:
            src = os.path.join(log_dir, src_name)
            dst = os.path.join(log_dir, dst_prefix)
            if os.path.exists(src) and os.path.getsize(src) > 0 and not os.path.exists(dst):
                os.rename(src, dst)
                rotated = True

        # Send USR1 signal to nginx to reopen log files
        if rotated and os.path.exists(pid_file):
            import signal
            with open(pid_file) as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGUSR1)
    except Exception:
        pass


# ── Scheduler ────────────────────────────────────────────────────────────────────

def _scheduler_loop():
    import time as _t
    from datetime import date as _date

    _last_10min     = [None]
    _last_1hour     = [None]
    _last_partition  = [None]
    _last_os         = [None]
    _last_service    = [None]
    _last_daily      = [None]
    _last_cleanup    = [None]
    _last_qcnt       = [None]
    _last_heap       = [None]
    _last_monthly    = [None]
    _last_proc       = [None]

    _ih_log('[SCHEDULER] Inspector History scheduler started')
    while True:
        try:
            now = datetime.now()
            h   = now.hour
            m   = now.minute

            # ── Existing PG summary collection ───────────────────────────
            if m % 10 == 5:
                key_10 = now.strftime('%Y-%m-%d %H:') + str(m)
                if key_10 != _last_10min[0]:
                    _last_10min[0] = key_10
                    _collect_summary_history('10min')
                    _ih_log_collect('Summary 10min')
            if m == 30:
                key_1h = now.strftime('%Y-%m-%d %H')
                if key_1h != _last_1hour[0]:
                    _last_1hour[0] = key_1h
                    _collect_summary_history('1hour')
                    _ih_log_collect('Summary 1hour')

            # ── PG partition management ──────────────────────────────────
            if h == 23 and m == 50:
                key_p = now.strftime('%Y-%m-%d')
                if key_p != _last_partition[0]:
                    _last_partition[0] = key_p
                    _ensure_partition(_date.today() + timedelta(days=1))
                    _ensure_partition(_date.today() + timedelta(days=2))
                    # INSP_ PG partitions
                    if _is_pg_insp_enabled():
                        from insp_pg import insp_pg_ensure_partitions
                        insp_pg_ensure_partitions(_date.today() + timedelta(days=1))
                        insp_pg_ensure_partitions(_date.today() + timedelta(days=2))

            # ── INSP_ collection (Oracle or PG, if enabled) ─────────────
            if _is_oracle_insp_enabled() or _is_pg_insp_enabled():

                # OS: every 1 minute
                key_os = now.strftime('%Y-%m-%d %H:%M')
                if key_os != _last_os[0]:
                    _last_os[0] = key_os
                    _collect_os()
                    _ih_log_collect('OS (CPU/Memory)')
                # Process snapshot (top 20): 1분 1회, OS 와 같은 분 키 사용
                if key_os != _last_proc[0]:
                    _last_proc[0] = key_os
                    _collect_proc()
                    _ih_log_collect('Process snapshot (top 20)')
                # Qcnt: retry until success within the same minute
                if key_os != _last_qcnt[0]:
                    if _collect_qcnt():
                        _last_qcnt[0] = key_os
                        _ih_log_collect('Qcnt')
                # Heap: retry until success within the same minute
                if key_os != _last_heap[0]:
                    if _collect_heap():
                        _last_heap[0] = key_os
                        _ih_log_collect('Heap')

                # Service: every hour (at minute 0)
                if m == 0:
                    key_svc = now.strftime('%Y-%m-%d %H')
                    if key_svc != _last_service[0]:
                        _last_service[0] = key_svc
                        _collect_services()
                        _ih_log_collect('Service Status')

                # Daily 23:50: TBS + Partition
                if h == 23 and m == 50:
                    key_daily = now.strftime('%Y-%m-%d')
                    if key_daily != _last_daily[0]:
                        _last_daily[0] = key_daily
                        _collect_tablespace()
                        _ih_log_collect('Tablespace/Disk')

                # IH log rotation: daily at 00:02
                if h == 0 and m == 2:
                    _ih_rotate_logs()

                # Nginx log rotation: daily at 00:01
                if h == 0 and m == 1:
                    key_rotate = now.strftime('%Y-%m-%d')
                    if key_rotate != _last_cleanup[0]:  # reuse to avoid extra var
                        _rotate_nginx_logs()

                # Retention cleanup: daily at 00:05
                if h == 0 and m == 5:
                    key_cl = now.strftime('%Y-%m-%d')
                    if key_cl != _last_cleanup[0]:
                        _last_cleanup[0] = key_cl
                        _do_retention_cleanup()

                # Monthly summary: 1st of month at 00:10
                if now.day == 1 and h == 0 and m == 10:
                    key_mo = now.strftime('%Y-%m')
                    if key_mo != _last_monthly[0]:
                        _last_monthly[0] = key_mo
                        _collect_monthly_summary()

        except Exception:
            pass
        _t.sleep(30)
