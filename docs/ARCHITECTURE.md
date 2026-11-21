# DevPilot System Architecture & Security Design

DevPilot is an enterprise-grade, multi-tenant DevOps monitoring and AI-assisted incident investigation platform. It provides continuous host telemetry collection, automated incident detection, an interactive Incident Time Machine, and deterministic + LLM-powered root cause analysis.

---

## 1. High-Level Architecture

```
+--------------------------------------------------------------------------+
|                            USER BROWSER                                  |
|   React + Vite SPA Dashboard (Light / Dark Theme)                        |
|   - Multi-Server Fleet View (/servers)                                   |
|   - System Live Telemetry (/monitoring)                                  |
|   - Container Health (/docker)                                           |
|   - Incident Time Machine Replay & Investigation (/incidents)             |
+--------------------------------------------------------------------------+
                                    |
                         HTTPS / JSON REST API
                                    v
+--------------------------------------------------------------------------+
|                          DEVPILOT BACKEND                                |
|   Flask Application Engine (Port 5000)                                   |
|                                                                          |
|   [Auth & Token Engine]         [Telemetry Collector]                    |
|   - PBKDF2 Password Hashing     - 5s Background Thread                   |
|   - HMAC-SHA256 Bearer Tokens   - Native Docker API Probe                |
|   - Dynamic /install.sh         - Multi-Server Incident Rule Engine      |
|                                                                          |
|   [Agent Ingestion Engine]      [AI Incident Investigator]               |
|   - /api/agent/enroll           - Ollama (Llama 3.2)                     |
|   - /api/agent/heartbeat        - Evidence-Based Telemetry Synthesis     |
|   - /api/agent/metrics          - Deterministic Offline Fallback         |
|   - /api/agent/docker / logs                                             |
+--------------------------------------------------------------------------+
          |                                              |
          v                                              v
+-----------------------+                    +-----------------------+
|  SQLite WAL Database  |                    | Ollama Local AI Server|
|  - users              |                    | Model: llama3.2       |
|  - servers            |                    | Port: 11434           |
|  - enrollment_tokens  |                    +-----------------------+
|  - agent_credentials  |
|  - system_metrics     |
|  - timeline_events    |
|  - incidents          |
+-----------------------+
          ^
          | Secure HTTP Ingestion (X-Agent-Key: dpk_...)
          |
+--------------------------------------------------------------------------+
|                   REMOTE LINUX SERVERS (FLEET)                           |
|                                                                          |
|   [Host 1: Ubuntu 24.04]         [Host 2: Debian / RHEL]                 |
|   - devpilot-agent.service       - devpilot-agent.service                |
|   - /proc metric scraper         - /proc metric scraper                  |
|   - Docker socket inspector      - Docker socket inspector               |
|   - Offline spool buffer         - Offline spool buffer                  |
|   - Automated secret redaction   - Automated secret redaction            |
+--------------------------------------------------------------------------+
```

---

## 2. Zero-Credentials Security Model

DevPilot implements an agent-initiated outbound push architecture:
- **No Inbound SSH Required**: The DevPilot server never opens SSH connections or asks operators for passwords, `sudo` access, or private keys.
- **Short-Lived Enrollment Tokens (`dpt_...`)**: Single-use tokens expire in 30 minutes and are burned atomically immediately upon successful agent handshake.
- **Persistent Revocable API Keys (`dpk_...`)**: Stored as SHA-256 hashes in SQLite. Operators can revoke any agent key at any time from the DevPilot dashboard.
- **Automated Secret Redaction**: The agent sanitizes logs before transmission using regex pattern replacement for passwords, bearer tokens, API keys, and certificates.
- **Offline Spooling Buffer**: When host network drops, the agent buffers up to 120 samples in a local queue and flushes them sequentially upon reconnect.

---

## 3. Database Schema Overview

The database uses SQLite in WAL mode (`PRAGMA journal_mode = WAL`) with idempotent migrations:

1. **`users`**: Multi-tenant user accounts with salt-hashed passwords.
2. **`servers`**: Monitored host records, agent versions, and heartbeat timestamps.
3. **`enrollment_tokens`**: Short-lived single-use onboarding tokens.
4. **`agent_credentials`**: Active and revoked `dpk_...` API key hashes.
5. **`system_metrics`**: High-resolution host metrics (`cpu_usage`, `memory_usage`, `disk_usage`, `load_avg`, etc.) indexed by `server_id` and timestamp epoch.
6. **`timeline_events`**: Chronological event stream (`log`, `metric`, `docker`, `system`) indexed by `server_id` and epoch.
7. **`incidents`**: Detected anomalies (`active`, `resolved`), AI investigations, and trigger event associations.

---

## 4. Incident Detection Engine Rules

Telemetry anomalies trigger incidents based on strict operational thresholds:
1. **Sustained High CPU**: CPU utilization $\ge 85\%$ for two consecutive cycles (Severity: High or Critical if $\ge 92\%$).
2. **Memory Exhaustion Alert**: Virtual memory utilization $\ge 85\%$ (Severity: High).
3. **Storage Volume Saturation**: Root volume disk usage $\ge 90\%$ (Severity: Critical).
4. **Container Outages**: Any Docker container exiting unexpectedly with a non-zero exit code (e.g., Code 137 OOM-Kill).
5. **Application Error Bursts**: $\ge 3$ error/critical log lines reported within a 60-second operational window.
6. **Agent Heartbeat Missed**: Server silent for $>90$ seconds transitions to `offline` with an automatic connectivity incident.

