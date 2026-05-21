import sys
sys.path.insert(0, '.')
from db_utils import run_db_query

def q(label, sql):
    print("==", label, "==")
    o, e = run_db_query(sql)
    print(e or o or "(empty)")
    print()

# PlatformJS reads config.json for DB connection - check what DB it connects to
q("PlatformJS config.json databases",
  "SELECT 1")  # placeholder

# Check if PlatformJS uses the same DB or a different one
import json, os
pjs_cfg = "/home/inspector/PG/2604/PlatformJS/config/config.json"
if os.path.exists(pjs_cfg):
    with open(pjs_cfg) as f:
        cfg = json.load(f)
    dbs = cfg.get("databases", [])
    for db in dbs:
        print("PJS DB:", db.get("database_name"), db.get("database_type"),
              db.get("database_server"), db.get("database_port"), db.get("database_database"))
else:
    print("PJS config not found")

print()

# Inspector connects via service_config.json
from service_config import load_service_config
svc = load_service_config().get("repository", {})
print("Inspector DB:", svc.get("db_type"), svc.get("ip"), svc.get("port"), svc.get("sid"), "user:", svc.get("user"))

print()

# Check if they point to the same database
q("apm_db_info via Inspector connection",
  "SELECT db_id, instance_name FROM apm_db_info ORDER BY db_id")

# Check what PlatformJS SQL does - it typically reads from a specific query
q("MFOPA_DataModule_SelectServer equivalent",
  "SELECT a.db_id, a.instance_name, b.name as service_name "
  "FROM apm_db_info a "
  "LEFT JOIN ora_service_info si ON si.db_id = a.db_id "
  "LEFT JOIN ora_service_name b ON si.service_id = b.service_id "
  "ORDER BY a.db_id")

# Check ora_lc_config (PlatformJS needs this)
q("ora_lc_config",
  "SELECT db_id, download_parameter FROM ora_lc_config ORDER BY db_id")
