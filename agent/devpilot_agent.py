#!/usr/bin/env python3
"""
DevPilot Standalone Monitoring Agent
Lightweight, resilient telemetry agent for remote Linux servers.
Collects system metrics, load averages, top processes, docker containers, and permitted logs.
Includes offline sample buffering and automated secret redaction.
"""

import os
import sys
import time
import json
import re
import socket
import platform
import logging
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib import request as url_request, error as url_error

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [DevPilot-Agent] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("devpilot_agent")

DEFAULT_CONFIG_PATHS = [
    "/etc/devpilot/agent.conf",
    os.path.expanduser("~/.devpilot/agent.conf"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.conf")
]

AGENT_VERSION = "2.0.0"

# Sensitive patterns to redact from logs
SECRET_PATTERNS = [
    (re.compile(r'(?i)(password|passwd|pwd)[\s:=]+([^\s,;]+)'), r'\1=***REDACTED***'),
    (re.compile(r'(?i)(api[_-]?key|apikey)[\s:=]+([^\s,;]+)'), r'\1=***REDACTED***'),
    (re.compile(r'(?i)(secret|token|bearer|auth|authorization)[\s:=]+([^\s,;]+)'), r'\1=***REDACTED***'),
    (re.compile(r'(?i)bearer\s+[a-zA-Z0-9_\-\.]{15,}'), r'Bearer ***REDACTED***'),
    (re.compile(r'(?i)(private[_-]?key)[\s:=]+([^\s,;]+)'), r'\1=***REDACTED***'),
]


def redact_secrets(text: str) -> str:
    """Mask credentials and secrets from log lines prior to transmission."""
    if not text:
        return ""
    sanitized = str(text)
    for pattern, repl in SECRET_PATTERNS:
        sanitized = pattern.sub(repl, sanitized)
    return sanitized


class DevPilotAgent:
    """Standalone collector and transmitter for DevPilot platform."""

    def __init__(self, config_file=None):
        self.config_path = self._resolve_config_path(config_file)
        self.config = self._load_config()
        self.spool_file = self.config.get("spool_file", "/tmp/devpilot_spool.json")
        self.endpoint = self.config.get("endpoint", "http://localhost:5000").rstrip("/")
        self.api_key = self.config.get("api_key", "")
        self.server_id = self.config.get("server_id", "")
        self.interval = int(self.config.get("collection_interval", 10))
        self.docker_enabled = bool(self.config.get("docker_enabled", True))
        self.log_paths = self.config.get("log_paths", ["/var/log/syslog", "/var/log/messages"])
        self.spool_buffer = []
        self.max_spool_size = int(self.config.get("max_spool_size", 120))
        self._log_offsets = {}
        self._prev_cpu_times = None

    def _resolve_config_path(self, user_path):
        if user_path and os.path.exists(user_path):
            return user_path
        for p in DEFAULT_CONFIG_PATHS:
            if os.path.exists(p):
                return p
        return user_path or DEFAULT_CONFIG_PATHS[0]

    def _load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Could not read config at %s: %s", self.config_path, e)
        return {}

    def save_config(self, updates: dict):
        """Persist configuration updates to disk."""
        self.config.update(updates)
        os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            os.chmod(self.config_path, 0o600)  # Restrict permissions
            logger.info("Saved configuration to %s", self.config_path)
            # Re-read cached values
            self.endpoint = self.config.get("endpoint", self.endpoint).rstrip("/")
            self.api_key = self.config.get("api_key", self.api_key)
            self.server_id = self.config.get("server_id", self.server_id)
        except Exception as e:
            logger.error("Failed writing config to %s: %s", self.config_path, e)

    # ------------------------------------------------------------------
    # Network Transmission with Offline Spooling
    # ------------------------------------------------------------------

    def _send_payload(self, path: str, payload: dict, timeout=8):
        """Send JSON payload via HTTP POST with agent auth headers."""
        url = f"{self.endpoint}{path}"
        data_bytes = json.dumps(payload).encode("utf-8")
        req = url_request.Request(
            url,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"DevPilotAgent/{AGENT_VERSION}",
                "X-Agent-Key": self.api_key
            },
            method="POST"
        )
        try:
            with url_request.urlopen(req, timeout=timeout) as resp:
                if resp.status in (200, 201, 204):
                    body = resp.read().decode("utf-8")
                    return json.loads(body) if body else {"success": True}
        except url_error.HTTPError as he:
            logger.error("HTTP error %s communicating with %s: %s", he.code, url, he.reason)
            return None
        except Exception as e:
            logger.warning("Connection failure to %s: %s", url, e)
            return None

    def _spool_metric(self, sample):
        """Append sample to offline spool buffer."""
        self.spool_buffer.append(sample)
        if len(self.spool_buffer) > self.max_spool_size:
            self.spool_buffer.pop(0)  # Evict oldest sample

    def _flush_spool_buffer(self):
        """Attempt to transmit queued historical samples after reconnection."""
        if not self.spool_buffer:
            return
        logger.info("Reconnected to DevPilot. Flushing %d buffered samples...", len(self.spool_buffer))
        while self.spool_buffer:
            sample = self.spool_buffer[0]
            resp = self._send_payload("/api/agent/metrics", sample)
            if resp:
                self.spool_buffer.pop(0)
            else:
                break

    # ------------------------------------------------------------------
    # Telemetry Collectors
    # ------------------------------------------------------------------

    def collect_host_info(self):
        """Gather static and runtime host metadata."""
        try:
            hostname = socket.gethostname()
        except Exception:
            hostname = "unknown"

        ip_addr = "127.0.0.1"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_addr = s.getsockname()[0]
            s.close()
        except Exception:
            pass

        os_info = f"{platform.system()} {platform.release()}"
        if os.path.exists("/etc/os-release"):
            try:
                with open("/etc/os-release", "r") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            os_info = line.split("=", 1)[1].strip().strip('"')
                            break
            except Exception:
                pass

        return {
            "hostname": hostname,
            "ip_address": ip_addr,
            "os_info": os_info,
            "agent_version": AGENT_VERSION,
            "python_version": platform.python_version()
        }

    def collect_system_metrics(self):
        """Collect host CPU, RAM, Disk, Load averages, and Top processes."""
        now = datetime.now(timezone.utc)
        ts_iso = now.isoformat()
        ts_epoch = now.timestamp()

        # Try psutil first if present
        try:
            import psutil
            cpu_pct = float(psutil.cpu_percent(interval=None))
            cpu_cores = int(psutil.cpu_count(logical=True) or 1)
            vm = psutil.virtual_memory()
            mem_pct = float(vm.percent)
            mem_used_gb = round(vm.used / (1024 ** 3), 2)
            mem_total_gb = round(vm.total / (1024 ** 3), 2)
            mem_avail_gb = round(vm.available / (1024 ** 3), 2)

            # Disk usage for root filesystem
            du = psutil.disk_usage('/')
            disk_pct = float(du.percent)
            disk_used_gb = round(du.used / (1024 ** 3), 2)
            disk_total_gb = round(du.total / (1024 ** 3), 2)
            disk_free_gb = round(du.free / (1024 ** 3), 2)

            # Load average
            try:
                load_avg = list(psutil.getloadavg())
            except Exception:
                load_avg = [0.0, 0.0, 0.0]

            # Top 5 processes by CPU / Memory
            top_procs = []
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                    try:
                        pinfo = proc.info
                        top_procs.append({
                            "pid": pinfo.get("pid"),
                            "name": pinfo.get("name") or "unknown",
                            "cpu_percent": float(pinfo.get("cpu_percent") or 0.0),
                            "memory_percent": round(float(pinfo.get("memory_percent") or 0.0), 2)
                        })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                top_procs = sorted(top_procs, key=lambda x: x.get("cpu_percent", 0.0), reverse=True)[:5]
            except Exception:
                top_procs = []

            return {
                "server_id": self.server_id,
                "timestamp": ts_iso,
                "timestamp_epoch": ts_epoch,
                "cpu_usage": cpu_pct,
                "cpu_cores": cpu_cores,
                "memory_usage": mem_pct,
                "memory_used_gb": mem_used_gb,
                "memory_total_gb": mem_total_gb,
                "memory_available_gb": mem_avail_gb,
                "disk_usage": disk_pct,
                "disk_used_gb": disk_used_gb,
                "disk_total_gb": disk_total_gb,
                "disk_free_gb": disk_free_gb,
                "load_avg": load_avg,
                "top_processes": top_procs
            }

        except ImportError:
            # Fallback to standard /proc inspection on Linux
            return self._collect_linux_proc_metrics(ts_iso, ts_epoch)

    def _collect_linux_proc_metrics(self, ts_iso, ts_epoch):
        """Native Linux /proc metric scraper without psutil dependency."""
        cpu_cores = os.cpu_count() or 1
        cpu_pct = 0.0

        # CPU from /proc/stat
        if os.path.exists("/proc/stat"):
            try:
                with open("/proc/stat", "r") as f:
                    cpu_line = f.readline().split()[1:]
                    cpu_nums = [float(x) for x in cpu_line]
                    idle = cpu_nums[3] + cpu_nums[4]
                    total = sum(cpu_nums)
                    if self._prev_cpu_times:
                        prev_idle, prev_total = self._prev_cpu_times
                        d_idle = idle - prev_idle
                        d_total = total - prev_total
                        if d_total > 0:
                            cpu_pct = round(100.0 * (1.0 - (d_idle / d_total)), 1)
                    self._prev_cpu_times = (idle, total)
            except Exception:
                pass

        # Memory from /proc/meminfo
        mem_total_kb = 1
        mem_avail_kb = 1
        if os.path.exists("/proc/meminfo"):
            try:
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            mem_total_kb = int(line.split()[1])
                        elif line.startswith("MemAvailable:"):
                            mem_avail_kb = int(line.split()[1])
            except Exception:
                pass

        mem_used_kb = max(0, mem_total_kb - mem_avail_kb)
        mem_pct = round((mem_used_kb / mem_total_kb) * 100.0, 1)
        mem_used_gb = round(mem_used_kb / (1024 * 1024), 2)
        mem_total_gb = round(mem_total_kb / (1024 * 1024), 2)
        mem_avail_gb = round(mem_avail_kb / (1024 * 1024), 2)

        # Disk via statvfs
        try:
            st = os.statvfs('/')
            total_b = st.f_blocks * st.f_frsize
            free_b = st.f_bavail * st.f_frsize
            used_b = total_b - free_b
            disk_pct = round((used_b / total_b) * 100.0, 1) if total_b > 0 else 0.0
            disk_used_gb = round(used_b / (1024 ** 3), 2)
            disk_total_gb = round(total_b / (1024 ** 3), 2)
            disk_free_gb = round(free_b / (1024 ** 3), 2)
        except Exception:
            disk_pct, disk_used_gb, disk_total_gb, disk_free_gb = 0.0, 0.0, 0.0, 0.0

        # Load average
        try:
            load_avg = list(os.getloadavg())
        except (AttributeError, OSError):
            load_avg = [0.0, 0.0, 0.0]

        return {
            "server_id": self.server_id,
            "timestamp": ts_iso,
            "timestamp_epoch": ts_epoch,
            "cpu_usage": cpu_pct,
            "cpu_cores": cpu_cores,
            "memory_usage": mem_pct,
            "memory_used_gb": mem_used_gb,
            "memory_total_gb": mem_total_gb,
            "memory_available_gb": mem_avail_gb,
            "disk_usage": disk_pct,
            "disk_used_gb": disk_used_gb,
            "disk_total_gb": disk_total_gb,
            "disk_free_gb": disk_free_gb,
            "load_avg": load_avg,
            "top_processes": []
        }

    def collect_docker_containers(self):
        """Inspect running and stopped containers via Docker CLI or socket."""
        if not self.docker_enabled:
            return []

        containers = []
        try:
            # Query docker CLI formatted output
            res = subprocess.run(
                ["docker", "ps", "-a", "--format", "{{json .}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0 and res.stdout:
                for line in res.stdout.strip().splitlines():
                    if not line.strip():
                        continue
                    try:
                        c = json.loads(line)
                        status_str = c.get("Status", "").lower()
                        containers.append({
                            "container_id": c.get("ID", ""),
                            "name": c.get("Names", "unknown"),
                            "image": c.get("Image", "unknown"),
                            "status": "running" if "up" in status_str else ("exited" if "exited" in status_str else "other"),
                            "status_raw": c.get("Status", ""),
                            "ports": c.get("Ports", ""),
                            "created_at": c.get("CreatedAt", "")
                        })
                    except Exception:
                        pass
        except Exception as e:
            logger.debug("Docker CLI unavailable on host: %s", e)

        return containers

    def collect_logs(self):
        """Read and sanitize new error/warning lines from permitted log files."""
        events = []
        for path in self.log_paths:
            if not os.path.exists(path) or not os.path.isfile(path):
                continue

            try:
                curr_size = os.path.getsize(path)
                prev_offset = self._log_offsets.get(path, None)

                # Initialize offset on first encounter to avoid dumping gigabytes of history
                if prev_offset is None:
                    self._log_offsets[path] = max(0, curr_size - 10000)
                    prev_offset = self._log_offsets[path]

                if curr_size < prev_offset:
                    # File was rotated/truncated
                    prev_offset = 0

                if curr_size > prev_offset:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(prev_offset)
                        new_content = f.read(50000)  # Read up to 50KB at once
                        self._log_offsets[path] = f.tell()

                        for line in new_content.splitlines():
                            line_clean = line.strip()
                            if not line_clean:
                                continue
                            lower = line_clean.lower()
                            if any(k in lower for k in ("error", "fatal", "critical", "warn", "exception", "failed")):
                                sev = "CRITICAL" if any(k in lower for k in ("fatal", "critical")) else ("ERROR" if "error" in lower or "exception" in lower else "WARNING")
                                redacted = redact_secrets(line_clean)
                                events.append({
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "severity": sev,
                                    "source": os.path.basename(path),
                                    "message": redacted[:500]
                                })
            except Exception as e:
                logger.debug("Error tailing log %s: %s", path, e)

        return events

    # ------------------------------------------------------------------
    # Lifecycle & Enrollment
    # ------------------------------------------------------------------

    def enroll(self, enrollment_token: str, endpoint: str = None):
        """Perform one-time enrollment using token to obtain persistent agent key."""
        if endpoint:
            self.endpoint = endpoint.rstrip("/")
        host_meta = self.collect_host_info()
        payload = {
            "enrollment_token": enrollment_token,
            "hostname": host_meta["hostname"],
            "ip_address": host_meta["ip_address"],
            "os_info": host_meta["os_info"],
            "agent_version": AGENT_VERSION,
            "docker_enabled": 1 if self.docker_enabled else 0
        }
        logger.info("Enrolling host %s with DevPilot at %s...", host_meta["hostname"], self.endpoint)
        resp = self._send_payload("/api/agent/enroll", payload)
        if resp and resp.get("success"):
            self.api_key = resp["api_key"]
            self.server_id = resp["server_id"]
            self.save_config({
                "endpoint": self.endpoint,
                "api_key": self.api_key,
                "server_id": self.server_id,
                "collection_interval": self.interval,
                "docker_enabled": self.docker_enabled,
                "log_paths": self.log_paths
            })
            logger.info("Enrollment SUCCESSFUL! Server ID: %s (%s)", self.server_id, resp.get("server_name"))
            return True
        else:
            err = resp.get("error") if resp else "Failed to contact DevPilot backend"
            logger.error("Enrollment FAILED: %s", err)
            return False

    def send_heartbeat(self):
        """Send lightweight periodic keepalive ping."""
        host_meta = self.collect_host_info()
        payload = {
            "agent_version": AGENT_VERSION,
            "os_info": host_meta["os_info"],
            "ip_address": host_meta["ip_address"],
            "docker_enabled": 1 if self.docker_enabled else 0
        }
        return self._send_payload("/api/agent/heartbeat", payload)

    def run_cycle(self):
        """Execute one complete sampling and transmission round."""
        # 1. System Metrics
        metrics = self.collect_system_metrics()
        resp = self._send_payload("/api/agent/metrics", metrics)
        if resp:
            # Successfully delivered, flush any backlog
            self._flush_spool_buffer()
        else:
            # Buffer sample for later delivery
            self._spool_metric(metrics)

        # 2. Docker Containers
        if self.docker_enabled:
            containers = self.collect_docker_containers()
            if containers:
                self._send_payload("/api/agent/docker", {"containers": containers})

        # 3. Permitted Log Events
        log_events = self.collect_logs()
        if log_events:
            self._send_payload("/api/agent/logs", {"logs": log_events})

    def run(self):
        """Main continuous daemon execution loop."""
        if not self.api_key or not self.server_id:
            logger.error("Agent is not enrolled! Please run with --enroll --token <TOKEN> first.")
            sys.exit(1)

        logger.info("Starting DevPilot Agent daemon (server_id=%s, interval=%ds)", self.server_id, self.interval)

        heartbeat_counter = 0
        while True:
            try:
                cycle_start = time.time()
                self.run_cycle()

                # Send heartbeat every 30 seconds
                heartbeat_counter += self.interval
                if heartbeat_counter >= 30:
                    self.send_heartbeat()
                    heartbeat_counter = 0

                elapsed = time.time() - cycle_start
                sleep_sec = max(1.0, self.interval - elapsed)
                time.sleep(sleep_sec)
            except KeyboardInterrupt:
                logger.info("Agent received interrupt signal. Exiting cleanly.")
                break
            except Exception as e:
                logger.exception("Unexpected error in agent loop: %s", e)
                time.sleep(5.0)


def main():
    parser = argparse.ArgumentParser(description="DevPilot Standalone Linux Monitoring Agent")
    parser.add_argument("--config", "-c", help="Path to agent configuration file")
    parser.add_argument("--enroll", action="store_true", help="Enroll with DevPilot backend")
    parser.add_argument("--endpoint", help="DevPilot backend URL (e.g., http://devpilot.local:5000)")
    parser.add_argument("--token", help="Single-use enrollment token from DevPilot UI")
    parser.add_argument("--run-once", action="store_true", help="Collect and output single sample to stdout")
    parser.add_argument("--daemon", action="store_true", help="Run continuously as daemon")
    args = parser.parse_args()

    agent = DevPilotAgent(config_file=args.config)

    if args.enroll:
        if not args.token:
            logger.error("--token is required for enrollment")
            sys.exit(1)
        endpoint = args.endpoint or agent.endpoint
        success = agent.enroll(args.token, endpoint=endpoint)
        if not success:
            sys.exit(1)
        if not args.daemon and not args.run_once:
            print("Enrollment complete. You can now start the agent daemon.")
            return

    if args.run_once:
        sample = {
            "host": agent.collect_host_info(),
            "metrics": agent.collect_system_metrics(),
            "docker": agent.collect_docker_containers() if agent.docker_enabled else [],
            "logs": agent.collect_logs()
        }
        print(json.dumps(sample, indent=2))
        return

    # Default: Run agent daemon
    agent.run()


if __name__ == "__main__":
    main()
