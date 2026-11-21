# DevPilot Monitoring Agent Setup Guide

This guide describes how to connect and install the lightweight DevPilot Monitoring Agent on any remote Linux server.

---

## 1. Quick Start: One-Line Installer

1. Navigate to the DevPilot Dashboard $\to$ **Servers** $\to$ click **"+ Add Linux Server"**.
2. Enter your server's friendly name (e.g. `Production Web 01`) and click **"Generate Connection Token & Command"**.
3. Copy the generated one-line command and run it on your remote Linux server as root:

```bash
curl -sSL http://<YOUR_DEVPILOT_IP>:5000/install.sh | sudo bash -s -- --endpoint http://<YOUR_DEVPILOT_IP>:5000 --token dpt_<YOUR_TOKEN>
```

4. The installer script will automatically:
   - Check or install Python 3.
   - Download `/opt/devpilot/devpilot_agent.py`.
   - Perform token enrollment and save credentials to `/etc/devpilot/agent.conf` (`chmod 600`).
   - Create and enable the systemd unit `devpilot-agent.service`.
   - Start continuous telemetry streaming.
5. In your DevPilot dashboard, the status badge will automatically turn **Green (Online)**!

---

## 2. Managing the Agent Service

Verify agent status on the Linux host:

```bash
# Check service status
sudo systemctl status devpilot-agent

# View real-time logs
sudo journalctl -u devpilot-agent -f

# Restart agent
sudo systemctl restart devpilot-agent

# Stop agent
sudo systemctl stop devpilot-agent
```

---

## 3. Configuration File (`/etc/devpilot/agent.conf`)

The agent reads configuration from `/etc/devpilot/agent.conf`:

```json
{
  "endpoint": "http://192.168.1.100:5000",
  "server_id": "srv_7a8b9c0d1e2f",
  "api_key": "dpk_YOUR_PERSISTENT_KEY",
  "collection_interval": 10,
  "docker_enabled": true,
  "log_paths": [
    "/var/log/syslog",
    "/var/log/messages",
    "/var/log/nginx/error.log"
  ],
  "max_spool_size": 120
}
```

### Configuration Options
- `endpoint`: URL of the DevPilot backend.
- `server_id`: Unique server identifier assigned by DevPilot.
- `api_key`: Persistent agent authentication key.
- `collection_interval`: Polling frequency in seconds (default: 10s).
- `docker_enabled`: Inspects Docker container state via local socket or CLI (default: `true`).
- `log_paths`: List of files tailed for error and warning messages with automatic secret redaction.
- `max_spool_size`: Maximum historical samples spooled during offline disconnections.

---

## 4. Manual / Standalone Installation

If you prefer not to pipe curl into bash:

1. Download the agent script:
```bash
sudo mkdir -p /opt/devpilot /etc/devpilot
sudo curl -sSL http://<YOUR_DEVPILOT_IP>:5000/agent/devpilot_agent.py -o /opt/devpilot/devpilot_agent.py
sudo chmod +x /opt/devpilot/devpilot_agent.py
```

2. Perform enrollment:
```bash
sudo python3 /opt/devpilot/devpilot_agent.py \
  --enroll \
  --endpoint "http://<YOUR_DEVPILOT_IP>:5000" \
  --token "<ENROLLMENT_TOKEN>" \
  --config "/etc/devpilot/agent.conf"
```

3. Run in the background:
```bash
sudo nohup python3 /opt/devpilot/devpilot_agent.py --daemon --config /etc/devpilot/agent.conf > /var/log/devpilot-agent.log 2>&1 &
```

