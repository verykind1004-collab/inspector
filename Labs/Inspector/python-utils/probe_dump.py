import sys
sys.path.insert(0, '.')
from db_utils import run_db_query

def q(label, sql):
    print("==", label, "==")
    o, e = run_db_query(sql)
    print(e or o or "(empty)")
    print()

q("apm_db_info", "SELECT db_id, instance_name, host_ip, port FROM apm_db_info ORDER BY db_id")
q("ora_service_name", "SELECT service_id, name FROM ora_service_name ORDER BY service_id")
q("ora_service_info", "SELECT db_id, service_id FROM ora_service_info ORDER BY db_id")
q("apm_db_seq", "SELECT last_value FROM apm_db_seq")
q("ora_service_name_seq", "SELECT last_value FROM ora_service_name_seq")
q("schema check", "SELECT schemaname, tablename FROM pg_tables WHERE tablename='apm_db_info'")
