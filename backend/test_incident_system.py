import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import backend.server as s
import backend.database as db
import backend.collector as col
import backend.investigator as inv

client = s.app.test_client()

print("=== 1. TEST DATABASE PERSISTENCE ===")
db.insert_system_metric({
    "cpu_usage": 45.2,
    "memory_usage": 68.4,
    "disk_usage": 52.1,
    "cpu_cores": 4
})
metrics = db.get_system_metrics_history(limit=5)
assert len(metrics) > 0, "Metrics history must not be empty"
print("Metrics persistence: PASSED (count =", len(metrics), ")")

print("=== 2. TEST SCENARIO: CPU SURGE ===")
res = client.post("/api/incidents/simulate", json={"scenario": "cpu_surge"})
assert res.status_code == 201, f"Expected 201, got {res.status_code}"
cpu_inc_id = res.get_json()["incident_id"]
inc = db.get_incident_by_id(cpu_inc_id)
assert inc is not None, "CPU surge incident must be found"
assert "CPU" in inc["title"] or "cpu" in inc["problem_type"].lower(), "Title or problem_type must reflect CPU"
print(f"CPU surge simulation: PASSED (id={cpu_inc_id}, title={inc['title']})")

print("=== 3. TEST SCENARIO: DATABASE OUTAGE ===")
res = client.post("/api/incidents/simulate", json={"scenario": "database_outage"})
assert res.status_code == 201
db_inc_id = res.get_json()["incident_id"]
res_tl = client.get(f"/api/incidents/{db_inc_id}/timeline")
assert res_tl.status_code == 200
events = res_tl.get_json()["events"]
assert len(events) > 0, "Timeline must have events"
res_inv = client.post(f"/api/incidents/{db_inc_id}/investigate")
assert res_inv.status_code == 200
inv_res = res_inv.get_json()["investigation"]
assert "incident_summary" in inv_res, "Investigation must contain summary"
assert len(inv_res["observed_facts"]) > 0, "Must have observed facts"
assert len(inv_res["recommended_troubleshooting_steps"]) > 0, "Must have troubleshooting steps"
print(f"Database outage & AI investigation: PASSED (events={len(events)}, status={inv_res.get('ai_engine_status')})")

print("=== 4. TEST SCENARIO: CONTAINER CRASH ===")
res = client.post("/api/incidents/simulate", json={"scenario": "container_crash"})
assert res.status_code == 201
cnt_inc_id = res.get_json()["incident_id"]
inc_cnt = db.get_incident_by_id(cnt_inc_id)
assert "Container" in inc_cnt["title"] or "container" in inc_cnt["problem_type"].lower()
print(f"Container crash simulation: PASSED (id={cnt_inc_id}, title={inc_cnt['title']})")

print("=== 5. TEST INCIDENT RESOLUTION ===")
res_res = client.post(f"/api/incidents/{cpu_inc_id}/resolve", json={"notes": "Operator scaled worker pool."})
assert res_res.status_code == 200
resolved_inc = db.get_incident_by_id(cpu_inc_id)
assert resolved_inc["status"] == "resolved", f"Status must be resolved, got {resolved_inc['status']}"
assert resolved_inc["end_epoch"] is not None, "End epoch must be recorded"
print("Incident resolution: PASSED")

print("=== 6. TEST METRICS TIMELINE WINDOW ===")
res_m = client.get(f"/api/incidents/{db_inc_id}/metrics?window=15")
assert res_m.status_code == 200
m_list = res_m.get_json()["metrics"]
assert len(m_list) > 0, "Incident window must contain metric samples"
print(f"Incident metrics window: PASSED (samples={len(m_list)})")

print("=== 7. TEST GLOBAL METRICS & TIMELINE APIS ===")
res_hist = client.get("/api/metrics/history?range=1h")
assert res_hist.status_code == 200
res_glob_tl = client.get("/api/timeline?limit=10")
assert res_glob_tl.status_code == 200
res_stats = client.get("/api/collector/stats")
assert res_stats.status_code == 200
print("Global telemetry endpoints: PASSED")

print("=== 8. TEST PRESERVATION OF EXISTING APIS ===")
res_sys = client.get("/monitor/system")
assert res_sys.status_code == 200
sys_data = res_sys.get_json()
assert "cpu" in sys_data and "memory" in sys_data and "disk" in sys_data
res_status = client.get("/status")
assert res_status.status_code == 200
res_home = client.get("/")
assert res_home.status_code == 200
print("Existing DevPilot monitoring and status endpoints: PASSED")

print("=== ALL VERIFICATION TESTS PASSED SUCCESSFULLY ===")
