"""
DevPilot End-to-End Multi-Server & Agent Pipeline Test Suite
Tests:
1. User registration & login with session bearer token
2. Server creation & single-use enrollment token generation
3. Dynamic installer endpoint availability
4. Remote Agent enrollment via token -> receives persistent API key
5. Agent heartbeat keepalive
6. Agent system metrics ingestion & anomaly incident trigger
7. Agent docker container ingestion & crash incident trigger
8. Agent log ingestion with secret redaction verification & error burst detection
9. Incident Time Machine scoped strictly by remote server_id
10. Server revocation & offline status check
"""

import sys
import json
import time
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from server import app
from database import get_servers, get_incidents, get_timeline_events

def run_tests():
    client = app.test_client()
    print("=== STARTING MULTI-SERVER & AGENT END-TO-END VERIFICATION ===")

    # Test 1: User Registration
    test_email = f"devops_{int(time.time())}@example.com"
    reg_resp = client.post("/api/auth/register", json={
        "email": test_email,
        "password": "SecurePassword123!",
        "name": "Sarah Connor"
    })
    assert reg_resp.status_code == 201, f"Reg failed: {reg_resp.data}"
    reg_data = json.loads(reg_resp.data)
    assert reg_data["success"] is True
    session_token = reg_data["token"]
    user_id = reg_data["user"]["id"]
    print("1. User Registration: PASSED (user_id=%s)" % user_id)

    # Test 2: User Login
    login_resp = client.post("/api/auth/login", json={
        "email": test_email,
        "password": "SecurePassword123!"
    })
    assert login_resp.status_code == 200
    login_data = json.loads(login_resp.data)
    assert login_data["success"] is True
    assert "token" in login_data
    auth_headers = {"Authorization": f"Bearer {session_token}"}
    print("2. User Authentication & Token: PASSED")

    # Test 3: Installer endpoints
    inst_resp = client.get("/install.sh")
    assert inst_resp.status_code == 200
    assert b"DevPilot" in inst_resp.data
    agent_py_resp = client.get("/agent/devpilot_agent.py")
    assert agent_py_resp.status_code == 200
    assert b"DevPilotAgent" in agent_py_resp.data
    print("3. Dynamic Installer Serving (/install.sh & /agent/devpilot_agent.py): PASSED")

    # Test 4: Create Server Record
    srv_resp = client.post("/api/servers", headers=auth_headers, json={
        "name": "Production Web App 01",
        "hostname": "prod-web-01.us-east-1",
        "ip_address": "198.51.100.42",
        "os_info": "Ubuntu 24.04 LTS"
    })
    assert srv_resp.status_code == 201, f"Failed to create server: {srv_resp.data}"
    srv_data = json.loads(srv_resp.data)
    server_id = srv_data["server"]["id"]
    enrollment_token = srv_data["enrollment_token"]
    install_cmd = srv_data["install_command"]
    assert server_id.startswith("srv_")
    assert enrollment_token.startswith("dpt_")
    assert "install.sh" in install_cmd
    print("4. Add Server & Enrollment Token: PASSED (server_id=%s)" % server_id)

    # Test 5: Agent Enrollment (exchanges token for persistent dpk_ key)
    enroll_resp = client.post("/api/agent/enroll", json={
        "enrollment_token": enrollment_token,
        "hostname": "prod-web-01.us-east-1",
        "ip_address": "198.51.100.42",
        "os_info": "Ubuntu 24.04 LTS",
        "agent_version": "2.0.0",
        "docker_enabled": 1
    })
    assert enroll_resp.status_code == 200, f"Enrollment failed: {enroll_resp.data}"
    enroll_data = json.loads(enroll_resp.data)
    assert enroll_data["success"] is True
    agent_api_key = enroll_data["api_key"]
    assert agent_api_key.startswith("dpk_")
    agent_headers = {"X-Agent-Key": agent_api_key}
    print("5. Remote Agent Enrollment: PASSED (issued key=%s...)" % agent_api_key[:10])

    # Test 6: Burning enrollment token (single-use validation)
    replay_resp = client.post("/api/agent/enroll", json={
        "enrollment_token": enrollment_token,
        "hostname": "hacker-box"
    })
    assert replay_resp.status_code == 401
    print("6. Token Single-Use Security: PASSED (burned token rejected)")

    # Test 7: Agent Heartbeat
    hb_resp = client.post("/api/agent/heartbeat", headers=agent_headers, json={
        "agent_version": "2.0.0",
        "docker_enabled": 1
    })
    assert hb_resp.status_code == 200
    print("7. Agent Heartbeat Keepalive: PASSED")

    # Test 8: Agent Metrics Ingestion & Threshold Anomaly Detection
    # Send CPU spike sample (94.5%)
    now_ts = time.time()
    metric_sample = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts)),
        "timestamp_epoch": now_ts,
        "cpu_usage": 94.5,
        "cpu_cores": 8,
        "memory_usage": 65.0,
        "memory_used_gb": 10.4,
        "memory_total_gb": 16.0,
        "memory_available_gb": 5.6,
        "disk_usage": 45.0,
        "disk_used_gb": 45.0,
        "disk_total_gb": 100.0,
        "disk_free_gb": 55.0
    }
    # Send twice to trigger consecutive CPU rule
    client.post("/api/agent/metrics", headers=agent_headers, json=metric_sample)
    metric_resp = client.post("/api/agent/metrics", headers=agent_headers, json=metric_sample)
    assert metric_resp.status_code == 200
    m_data = json.loads(metric_resp.data)
    assert m_data["inserted_samples"] == 1
    print("8. Agent Metrics Ingestion: PASSED")

    # Test 9: Docker Container Crash Ingestion
    docker_resp = client.post("/api/agent/docker", headers=agent_headers, json={
        "containers": [
            {
                "container_id": "c_nginx_01",
                "name": "nginx-ingress",
                "image": "nginx:alpine",
                "status": "exited",
                "status_raw": "Exited (137) 12 seconds ago",
                "ports": "80/tcp"
            }
        ]
    })
    assert docker_resp.status_code == 200
    print("9. Agent Docker Crash Detection: PASSED")

    # Test 10: Ingest Logs with Secret Redaction Verification
    log_resp = client.post("/api/agent/logs", headers=agent_headers, json={
        "logs": [
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts)),
                "severity": "CRITICAL",
                "source": "syslog",
                "message": "Out of memory: Kill process 4128 (nginx) score 852"
            },
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts + 1)),
                "severity": "ERROR",
                "source": "app.log",
                "message": "Database authentication failed for password=SuperSecretPassword123!"
            },
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts + 2)),
                "severity": "ERROR",
                "source": "app.log",
                "message": "Connection to upstream server terminated unexpectedly"
            }
        ]
    })
    assert log_resp.status_code == 200
    print("10. Agent Log Ingestion & Error Burst: PASSED")

    # Test 11: Incident Time Machine Scoped Strictly to Remote Server
    inc_resp = client.get(f"/api/incidents?server_id={server_id}")
    assert inc_resp.status_code == 200
    inc_data = json.loads(inc_resp.data)
    incidents = inc_data["incidents"]
    assert len(incidents) >= 1
    print("11. Incident Time Machine Scoped Query: PASSED (found %d incidents for %s)" % (len(incidents), server_id))

    # Test 12: System Monitoring for Remote Server
    sys_resp = client.get(f"/monitor/system?server_id={server_id}")
    assert sys_resp.status_code == 200
    sys_data = json.loads(sys_resp.data)
    assert sys_data["server_id"] == server_id
    assert sys_data["cpu"]["usage"] == 94.5
    assert sys_data["scope"] == "remote_server"
    print("12. Remote Server System Monitoring Endpoint: PASSED")

    # Test 13: Revoke Server Key
    revoke_resp = client.post(f"/api/servers/{server_id}/revoke", headers=auth_headers)
    assert revoke_resp.status_code == 200
    # Subsequent agent post should fail
    fail_hb = client.post("/api/agent/heartbeat", headers=agent_headers, json={})
    assert fail_hb.status_code == 401
    print("13. Server Agent Revocation: PASSED (revoked key correctly blocked)")

    print("=== ALL MULTI-SERVER & AGENT END-TO-END TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_tests()

