# DevPilot – DevOps Monitoring & Incident Investigation Platform

DevPilot is an AI-assisted DevOps platform designed for monitoring Linux server fleets, detecting performance anomalies in real time, and investigating operational incidents chronologically using local AI (Ollama Llama 3.2).

![DevPilot Platform](https://img.shields.io/badge/DevPilot-v2.0.0-blue?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.11+-yellow?style=flat-square)
![React](https://img.shields.io/badge/React-19.2+-61dafb?style=flat-square)

---

## Key Features

- **Multi-Server Monitoring Fleet**: Connect and monitor multiple remote Linux servers from a unified, responsive dashboard.
- **Zero-Credentials Remote Agent**: Install the ultra-lightweight agent (`agent/devpilot_agent.py`) via a copy-paste one-line bash installer with short-lived enrollment tokens (`dpt_...`). No SSH passwords or keys needed.
- **Incident Time Machine**: Reconstruct incidents step-by-step with chronological event replay across application logs, metrics, and Docker lifecycle transitions.
- **AI-Assisted Investigation**: Synthesize incident telemetry using Ollama (Llama 3.2) or deterministic rule-based analysis to determine root cause, impact, and actionable remediation steps.
- **Live System & Docker Monitoring**: Real-time CPU, RAM, Disk, and Container health telemetry with instant server-selector dropdown.
- **Log Analysis & PDF Reports**: Upload raw system logs for automated anomaly extraction and export professional troubleshooting reports.
- **Multi-Tenant Authentication**: Cryptographic user registration and login with salt-hashed passwords and HMAC-SHA256 session tokens.

---

## Platform Components

| Component | Technology | Description |
|---|---|---|
| **Frontend** | React 19 + Vite | High-contrast Dark/Light theme dashboard with live metrics charts, incident timeline replay, and server fleet management. |
| **Backend** | Python Flask + SQLite WAL | REST API engine, token verification, incident detection engine, and AI synthesis. |
| **Agent** | Python Standalone Script | Outbound telemetry scraper running as a systemd service with offline sample spooling and secret redaction. |
| **Database** | SQLite 3 (WAL Mode) | Persistent, lightweight, zero-configuration database with multi-server schemas and historical indexing. |
| **Local AI** | Ollama (Llama 3.2) | Local, private LLM reasoning with evidence-based root cause analysis. |

---

## Quick Start (Development)

### 1. Run the Backend
```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate # Linux/macOS

# Install dependencies
pip install -r backend/requirements.txt

# Start backend server
python backend/server.py
```
The backend starts on `http://127.0.0.1:5000`.

### 2. Run the Frontend
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## Production Deployment with Docker Compose

Deploy the entire stack in one command:

```bash
docker compose up -d --build
```

Access:
- Frontend: `http://localhost:80` (or `http://localhost:5173`)
- Backend API: `http://localhost:5000`
- Ollama AI: `http://localhost:11434`

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for full VPS and SSL setup instructions.

---

## Documentation

- [System Architecture & Security Design](docs/ARCHITECTURE.md)
- [Remote Linux Agent Setup Guide](docs/AGENT_SETUP.md)
- [Production Deployment Guide](docs/DEPLOYMENT.md)

---

## Verification & Tests

Run the backend test suites:
```bash
# Incident Time Machine regression test
python backend/test_incident_system.py

# Multi-server and agent end-to-end integration test
python backend/test_multiserver_agent.py

# Frontend production build check
npm run build --prefix frontend
```

