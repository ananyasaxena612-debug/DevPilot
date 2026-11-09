"""
DevPilot - Continuous Background Telemetry Collector & Incident Detector
Monitors system resources, docker events, and application logs in real time,
recording historical data to SQLite and detecting operational incidents.
"""

import os
import re
import time
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

import psutil

try:
    import docker
except ImportError:
    docker = None

try:
    from backend.database import (
        insert_system_metric,
        insert_timeline_event,
        create_incident,
        get_incidents,
        link_events_to_incident
    )
except ImportError:
    from database import (
        insert_system_metric,
        insert_timeline_event,
        create_incident,
        get_incidents,
        link_events_to_incident
    )

logger = logging.getLogger(__name__)

# Configurable thresholds
CPU_ALERT_THRESHOLD = float(os.environ.get("DEVPILOT_CPU_THRESHOLD", "85.0"))
MEMORY_ALERT_THRESHOLD = float(os.environ.get("DEVPILOT_MEMORY_THRESHOLD", "85.0"))
DISK_ALERT_THRESHOLD = float(os.environ.get("DEVPILOT_DISK_THRESHOLD", "90.0"))
COLLECTION_INTERVAL = float(os.environ.get("DEVPILOT_COLLECT_INTERVAL", "5.0"))


class DataCollector:
    """Continuous background worker that ingests telemetry and detects incidents."""

    def __init__(self, interval=COLLECTION_INTERVAL):
        self.interval = interval
        self.running = False
        self.thread = None
        self._lock = threading.Lock()

        # Track state across cycles
        self._last_container_states = {}  # container_id -> status
        self._log_file_offsets = {}       # file_path -> byte_offset
        self._active_incident_cooldowns = {} # trigger_key -> last_incident_epoch
        self._consecutive_cpu_high = 0
        self._recent_error_timestamps = [] # timestamps of errors in window
        self._stats = {
            "metrics_collected": 0,
            "events_recorded": 0,
            "incidents_detected": 0,
            "start_time": None
        }

    def start(self):
        """Start collector thread if not already running."""
        with self._lock:
            if self.running:
                return
            self.running = True
            self._stats["start_time"] = datetime.now(timezone.utc).isoformat()
            self.thread = threading.Thread(
                target=self._run_loop,
                name="DevPilotTelemetryCollector",
                daemon=True
            )
            self.thread.start()
            logger.info("DevPilot Background Telemetry Collector started (interval=%.1fs)", self.interval)

    def stop(self):
        """Signal collector loop to stop."""
        with self._lock:
            self.running = False

    def get_stats(self):
        """Return diagnostic stats of the collector."""
        with self._lock:
            return {
                **self._stats,
                "is_active": self.running,
                "interval_seconds": self.interval,
                "tracked_log_files": len(self._log_file_offsets),
                "tracked_containers": len(self._last_container_states)
            }

    def _run_loop(self):
        """Main execution loop."""
        # Initial non-blocking cpu_percent setup
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

        while self.running:
            try:
                cycle_start = time.time()

                # 1. Collect System Metrics
                metric_entry = self._collect_system_metrics()

                # 2. Ingest Application Logs
                new_log_events = self._collect_application_logs()

                # 3. Ingest Docker State Changes
                docker_events = self._collect_docker_events()

                # 4. Evaluate Incident Detection Rules
                self._evaluate_incident_rules(metric_entry, new_log_events, docker_events)

                # Sleep remainder of interval
                elapsed = time.time() - cycle_start
                sleep_time = max(0.5, self.interval - elapsed)
                time.sleep(sleep_time)

            except Exception as e:
                logger.exception("Error in DevPilot collector loop: %s", e)
                time.sleep(self.interval)

    # ------------------------------------------------------------------
    # 1. System Metrics Collection
    # ------------------------------------------------------------------

    def _collect_system_metrics(self):
        """Query host resources and persist sample to SQLite."""
        now = datetime.now(timezone.utc)
        now_epoch = now.timestamp()
        now_iso = now.isoformat()

        cpu_usage = psutil.cpu_percent(interval=None)
        cpu_cores = psutil.cpu_count() or 1
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        record = {
            "timestamp": now_iso,
            "timestamp_epoch": now_epoch,
            "cpu_usage": round(cpu_usage, 2),
            "cpu_cores": cpu_cores,
            "memory_usage": round(memory.percent, 2),
            "memory_used_gb": round(memory.used / (1024 ** 3), 3),
            "memory_total_gb": round(memory.total / (1024 ** 3), 3),
            "memory_available_gb": round(memory.available / (1024 ** 3), 3),
            "disk_usage": round(disk.percent, 2),
            "disk_used_gb": round(disk.used / (1024 ** 3), 3),
            "disk_total_gb": round(disk.total / (1024 ** 3), 3),
            "disk_free_gb": round(disk.free / (1024 ** 3), 3),
        }

        insert_system_metric(record)
        with self._lock:
            self._stats["metrics_collected"] += 1
        return record

    # ------------------------------------------------------------------
    # 2. Application Logs Collection
    # ------------------------------------------------------------------

    def _collect_application_logs(self):
        """Tail log files in the project logs directory."""
        collected_events = []
        project_root = Path(__file__).resolve().parent.parent
        logs_dir = project_root / "logs"

        if not logs_dir.exists():
            return collected_events

        # Identify .log and .txt files
        log_files = list(logs_dir.glob("*.log")) + list(logs_dir.glob("*.txt"))

        for file_path in log_files:
            str_path = str(file_path)
            try:
                file_size = file_path.stat().st_size
                last_offset = self._log_file_offsets.get(str_path, 0)

                # If file rotated or truncated, reset offset
                if file_size < last_offset:
                    last_offset = 0

                if file_size == last_offset:
                    continue

                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(last_offset)
                    new_lines = f.readlines()
                    self._log_file_offsets[str_path] = f.tell()

                for line in new_lines:
                    line = line.strip()
                    if not line:
                        continue
                    event = self._parse_log_line(line, file_path.name)
                    if event:
                        event_id = insert_timeline_event(event)
                        if event_id:
                            event["id"] = event_id
                            collected_events.append(event)
                            with self._lock:
                                self._stats["events_recorded"] += 1

            except Exception as e:
                logger.debug("Failed reading log file %s: %s", file_path, e)

        return collected_events

    def _parse_log_line(self, line, file_name):
        """Parse log lines into structured timeline events."""
        now = datetime.now(timezone.utc)
        ts_iso = now.isoformat()
        ts_epoch = now.timestamp()
        severity = "INFO"
        message = line

        # Common format: 2026-09-01 20:44:22,214 - INFO - DevPilot application started
        match1 = re.match(
            r"^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[,\.]\d+)?)\s*(?:-\s*)?([A-Z]+)\s*(?:-\s*)?(.*)$",
            line
        )
        if match1:
            raw_ts, raw_level, raw_msg = match1.groups()
            severity = raw_level.upper()
            message = raw_msg.strip()
            try:
                clean_ts = raw_ts.replace(",", ".")
                dt = datetime.fromisoformat(clean_ts)
                ts_iso = dt.replace(tzinfo=timezone.utc).isoformat()
                ts_epoch = dt.timestamp()
            except Exception:
                pass
        else:
            # Fallback severity keyword detection
            lower = line.lower()
            if "critical" in lower or "fatal" in lower:
                severity = "CRITICAL"
            elif "error" in lower or "failed" in lower or "exception" in lower:
                severity = "ERROR"
            elif "warning" in lower or "warn" in lower:
                severity = "WARNING"

        return {
            "timestamp": ts_iso,
            "timestamp_epoch": ts_epoch,
            "event_type": "log",
            "severity": severity,
            "source": f"file:{file_name}",
            "message": message,
            "metadata": {"raw_line": line, "file": file_name}
        }

    # ------------------------------------------------------------------
    # 3. Docker State Tracking
    # ------------------------------------------------------------------

    def _collect_docker_events(self):
        """Check container statuses and emit lifecycle events on state transitions."""
        events = []
        if not docker:
            return events

        try:
            client = docker.from_env()
            containers = client.containers.list(all=True)
            current_states = {}

            for c in containers:
                c.reload()
                cid = c.short_id
                name = c.name
                status = c.status.lower()
                current_states[cid] = status

                # Check if this container transitioned state
                if cid in self._last_container_states:
                    prev_status = self._last_container_states[cid]
                    if prev_status != status:
                        now = datetime.now(timezone.utc)
                        now_epoch = now.timestamp()
                        now_iso = now.isoformat()

                        # Determine severity
                        if status in ("exited", "dead"):
                            exit_code = c.attrs.get("State", {}).get("ExitCode", 0)
                            sev = "CRITICAL" if exit_code != 0 else "WARNING"
                            msg = f"Container '{name}' stopped (state: {status}, exit code: {exit_code})"
                        elif status == "running":
                            sev = "INFO"
                            msg = f"Container '{name}' started / transitioned to running"
                        else:
                            sev = "WARNING"
                            msg = f"Container '{name}' status changed: {prev_status} -> {status}"

                        event_data = {
                            "timestamp": now_iso,
                            "timestamp_epoch": now_epoch,
                            "event_type": "docker",
                            "severity": sev,
                            "source": f"docker:{name}",
                            "message": msg,
                            "metadata": {
                                "container_id": cid,
                                "container_name": name,
                                "image": c.image.tags[0] if c.image.tags else "Unknown",
                                "previous_status": prev_status,
                                "current_status": status,
                                "exit_code": c.attrs.get("State", {}).get("ExitCode")
                            }
                        }
                        insert_timeline_event(event_data)
                        events.append(event_data)
                        with self._lock:
                            self._stats["events_recorded"] += 1

            self._last_container_states = current_states

        except Exception as e:
            # Docker might not be running; handle gracefully
            logger.debug("Docker monitoring probe in collector: %s", e)

        return events

    # ------------------------------------------------------------------
    # 4. Incident Detection Logic
    # ------------------------------------------------------------------

    def _evaluate_incident_rules(self, metric, log_events, docker_events):
        """Evaluate telemetry anomalies and trigger incident creation if warranted."""
        now_epoch = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()

        # Rule 1: Sustained High CPU Usage
        cpu = metric.get("cpu_usage", 0.0)
        if cpu >= CPU_ALERT_THRESHOLD:
            self._consecutive_cpu_high += 1
            if self._consecutive_cpu_high >= 2:
                self._trigger_incident(
                    trigger_key="high_cpu",
                    title=f"Sustained High CPU Load ({cpu:.1f}%)",
                    description=(
                        f"Host processor utilization reached {cpu:.1f}%, exceeding the "
                        f"configured operational threshold of {CPU_ALERT_THRESHOLD}%."
                    ),
                    problem_type="Performance",
                    severity="Critical" if cpu >= 92.0 else "High",
                    metric_snapshot=metric
                )
        else:
            self._consecutive_cpu_high = 0

        # Rule 2: Memory Exhaustion Warning
        ram = metric.get("memory_usage", 0.0)
        if ram >= MEMORY_ALERT_THRESHOLD:
            self._trigger_incident(
                trigger_key="high_memory",
                title=f"High Memory Consumption Alert ({ram:.1f}%)",
                description=(
                    f"Virtual memory utilization rose to {ram:.1f}% "
                    f"({metric.get('memory_used_gb', 0)} GB used of {metric.get('memory_total_gb', 0)} GB)."
                ),
                problem_type="Performance",
                severity="High",
                metric_snapshot=metric
            )

        # Rule 3: Disk Space Exhaustion
        disk = metric.get("disk_usage", 0.0)
        if disk >= DISK_ALERT_THRESHOLD:
            self._trigger_incident(
                trigger_key="high_disk",
                title=f"Critical Disk Volume Saturation ({disk:.1f}%)",
                description=(
                    f"Root storage volume capacity reached {disk:.1f}%. "
                    f"Only {metric.get('disk_free_gb', 0)} GB remains available."
                ),
                problem_type="Performance",
                severity="Critical",
                metric_snapshot=metric
            )

        # Rule 4: Docker Container Termination
        for de in docker_events:
            meta = de.get("metadata", {})
            if meta.get("current_status") in ("exited", "dead"):
                cname = meta.get("container_name", "container")
                exit_code = meta.get("exit_code", 0)
                self._trigger_incident(
                    trigger_key=f"container_stop_{cname}",
                    title=f"Container Outage: '{cname}' Stopped Unexpectedly",
                    description=f"Docker container '{cname}' halted execution with status '{meta.get('current_status')}' and exit code {exit_code}.",
                    problem_type="Container",
                    severity="Critical" if exit_code != 0 else "High",
                    metric_snapshot=metric
                )

        # Rule 5: Error Burst in Logs
        for le in log_events:
            if le.get("severity") in ("ERROR", "CRITICAL"):
                self._recent_error_timestamps.append(le.get("timestamp_epoch", now_epoch))

        # Filter errors to last 60 seconds
        cutoff = now_epoch - 60.0
        self._recent_error_timestamps = [t for t in self._recent_error_timestamps if t >= cutoff]
        if len(self._recent_error_timestamps) >= 3:
            self._trigger_incident(
                trigger_key="log_error_burst",
                title=f"Repeated Application Errors ({len(self._recent_error_timestamps)} in 60s)",
                description=(
                    f"A burst of {len(self._recent_error_timestamps)} application error log messages "
                    f"was detected within a 60-second operational window."
                ),
                problem_type="Application",
                severity="High",
                metric_snapshot=metric
            )

    def _trigger_incident(self, trigger_key, title, description,
                          problem_type, severity, metric_snapshot=None):
        """Creates an incident record if cooldown period has elapsed."""
        now_epoch = time.time()
        last_triggered = self._active_incident_cooldowns.get(trigger_key, 0.0)

        # Cooldown: 180 seconds between duplicate triggers of the same type
        if now_epoch - last_triggered < 180.0:
            return None

        # Check if an active incident with this exact title already exists
        active_incidents = get_incidents(status="active", limit=10)
        for ai in active_incidents:
            if ai.get("title") == title:
                return None

        self._active_incident_cooldowns[trigger_key] = now_epoch
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        # Insert incident trigger event into timeline
        trigger_event_id = insert_timeline_event({
            "timestamp": now_iso,
            "timestamp_epoch": now_epoch,
            "event_type": "incident",
            "severity": "CRITICAL" if severity == "Critical" else "WARNING",
            "source": "devpilot:detector",
            "message": f"[INCIDENT DETECTED] {title} - {description}",
            "metadata": metric_snapshot
        })

        inc_id = create_incident({
            "title": title,
            "description": description,
            "problem_type": problem_type,
            "severity": severity,
            "status": "active",
            "start_time": now_iso,
            "start_epoch": now_epoch,
            "trigger_event_id": trigger_event_id
        })

        with self._lock:
            self._stats["incidents_detected"] += 1

        logger.warning("ALERT: Detected and recorded incident %s: %s", inc_id, title)
        return inc_id

    # ------------------------------------------------------------------
    # 5. Incident Simulation (For testing & demos)
    # ------------------------------------------------------------------

    def simulate_incident(self, scenario_type="database_outage"):
        """
        Injects realistic historical telemetry and events to simulate an operational incident.
        Guarantees end-to-end testing of Time Machine even without an active production failure.
        """
        now = datetime.now(timezone.utc)
        base_epoch = now.timestamp() - 120.0  # Started 2 minutes ago

        scenarios = {
            "database_outage": {
                "title": "PostgreSQL Connection Timeout & Thread Pool Exhaustion",
                "problem_type": "Database",
                "severity": "Critical",
                "description": "Application database pool timed out attempting to establish socket connection to postgres.internal:5432.",
                "events": [
                    (-110, "log", "INFO", "app.py", "Health check OK; active connections: 14/20"),
                    (-80, "log", "WARNING", "app.py", "Database query latency exceeded SLA (2840ms on /api/orders)"),
                    (-65, "system_alert", "WARNING", "monitor:ram", "RAM utilization increased rapidly to 86.4% due to connection queueing"),
                    (-50, "log", "ERROR", "app.py", "psycopg2.OperationalError: could not connect to server: Connection timed out"),
                    (-45, "log", "ERROR", "app.py", "Database pool exhausted; rejecting inbound API request #8841"),
                    (-40, "log", "CRITICAL", "app.py", "Worker process terminated unexpectedly with unhandled DBException"),
                    (-20, "docker", "WARNING", "docker:postgres_db", "Container 'postgres_db' health check reported unhealthy"),
                    (-5, "log", "ERROR", "app.py", "Retry connection cycle 3/3 failed for host 10.0.0.12:5432")
                ],
                "metric_samples": [
                    (-120, 24.5, 45.2, 58.1),
                    (-90, 38.0, 52.8, 58.1),
                    (-60, 78.4, 86.4, 58.1),
                    (-30, 84.1, 88.2, 58.2),
                    (0, 42.0, 87.5, 58.2),
                ]
            },
            "cpu_surge": {
                "title": "CPU Overload Spike & Worker Deadlock",
                "problem_type": "Performance",
                "severity": "High",
                "description": "Host logical cores spiked to 96.2% utilization caused by unoptimized regex pattern matching in background worker.",
                "events": [
                    (-100, "log", "INFO", "worker.py", "Starting batch regex processing job #449"),
                    (-70, "system_alert", "WARNING", "monitor:cpu", "CPU load exceeded 80% threshold across 8 cores"),
                    (-50, "system_alert", "CRITICAL", "monitor:cpu", "CPU sustained at 96.2% utilization for >30 seconds"),
                    (-35, "log", "WARNING", "worker.py", "Heartbeat delayed by 18400ms"),
                    (-15, "log", "ERROR", "worker.py", "Task execution timeout: thread blocked in regex evaluation")
                ],
                "metric_samples": [
                    (-120, 15.0, 40.0, 50.0),
                    (-90, 45.0, 42.0, 50.0),
                    (-60, 88.0, 44.0, 50.0),
                    (-30, 96.2, 46.0, 50.0),
                    (0, 94.8, 46.5, 50.0),
                ]
            },
            "container_crash": {
                "title": "Backend Service Container Unexpected Exit (Code 137)",
                "problem_type": "Container",
                "severity": "Critical",
                "description": "Container 'devpilot_api' was killed by Linux kernel OOM Killer after exceeding memory cgroup quota.",
                "events": [
                    (-115, "log", "INFO", "app.py", "Inbound payload burst: 450 concurrent requests"),
                    (-85, "system_alert", "WARNING", "monitor:ram", "Container memory cgroup approaching limit (492MB / 512MB)"),
                    (-60, "docker", "CRITICAL", "docker:devpilot_api", "Container 'devpilot_api' state changed: running -> exited (ExitCode: 137 OOMKilled)"),
                    (-40, "log", "ERROR", "nginx", "502 Bad Gateway while connecting to upstream devpilot_api:5000"),
                    (-10, "docker", "INFO", "docker:devpilot_api", "Container restart attempt initiated by orchestrator")
                ],
                "metric_samples": [
                    (-120, 30.0, 55.0, 62.0),
                    (-90, 52.0, 82.0, 62.0),
                    (-60, 68.0, 91.5, 62.0),
                    (-30, 25.0, 50.0, 62.0),
                    (0, 22.0, 48.0, 62.0),
                ]
            }
        }

        scenario = scenarios.get(scenario_type, scenarios["database_outage"])

        # Insert historical metric samples
        for offset_sec, cpu, ram, disk in scenario["metric_samples"]:
            sample_epoch = base_epoch + offset_sec
            sample_iso = datetime.fromtimestamp(sample_epoch, timezone.utc).isoformat()
            insert_system_metric({
                "timestamp": sample_iso,
                "timestamp_epoch": sample_epoch,
                "cpu_usage": cpu,
                "cpu_cores": 8,
                "memory_usage": ram,
                "memory_used_gb": round((ram / 100.0) * 16.0, 2),
                "memory_total_gb": 16.0,
                "memory_available_gb": round(16.0 - (ram / 100.0) * 16.0, 2),
                "disk_usage": disk,
                "disk_used_gb": round((disk / 100.0) * 256.0, 2),
                "disk_total_gb": 256.0,
                "disk_free_gb": round(256.0 - (disk / 100.0) * 256.0, 2)
            })

        # Insert timeline events
        first_event_id = None
        for offset_sec, ev_type, sev, src, msg in scenario["events"]:
            ev_epoch = base_epoch + offset_sec
            ev_iso = datetime.fromtimestamp(ev_epoch, timezone.utc).isoformat()
            eid = insert_timeline_event({
                "timestamp": ev_iso,
                "timestamp_epoch": ev_epoch,
                "event_type": ev_type,
                "severity": sev,
                "source": src,
                "message": msg,
                "metadata": {"simulation": True, "scenario": scenario_type}
            })
            if first_event_id is None:
                first_event_id = eid

        # Create incident
        inc_start_iso = datetime.fromtimestamp(base_epoch, timezone.utc).isoformat()
        inc_id = create_incident({
            "title": scenario["title"],
            "description": scenario["description"],
            "problem_type": scenario["problem_type"],
            "severity": scenario["severity"],
            "status": "active",
            "start_time": inc_start_iso,
            "start_epoch": base_epoch,
            "trigger_event_id": first_event_id
        })

        # Associate the simulated events with the incident
        link_events_to_incident(inc_id, base_epoch - 180.0, time.time() + 60.0)
        return inc_id


# Global Singleton Collector
collector = DataCollector()

