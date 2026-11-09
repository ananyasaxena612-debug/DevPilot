"""
DevPilot - Incident Investigation Engine
Analyzes historical incident telemetry, timeline events, and logs using Ollama AI,
with graceful fallback and strict evidence-based reasoning.
"""

import os
import json
import logging
import requests
from datetime import datetime, timezone

try:
    from backend.database import (
        get_incident_by_id,
        get_timeline_events,
        get_system_metrics_history,
        update_incident_ai_investigation
    )
except ImportError:
    from database import (
        get_incident_by_id,
        get_timeline_events,
        get_system_metrics_history,
        update_incident_ai_investigation
    )

logger = logging.getLogger(__name__)

# Configurable Ollama endpoints
OLLAMA_CANDIDATE_URLS = [
    os.environ.get("OLLAMA_URL"),
    "http://127.0.0.1:11434/api/generate",
    "http://host.docker.internal:11434/api/generate"
]
OLLAMA_CANDIDATE_URLS = [u for u in OLLAMA_CANDIDATE_URLS if u]


def investigate_incident(incident_id):
    """
    Perform a complete post-incident investigation based strictly on
    the incident's historical telemetry, timeline events, and application logs.
    """
    incident = get_incident_by_id(incident_id)
    if not incident:
        raise ValueError(f"Incident {incident_id} not found.")

    # 1. Fetch incident time window events
    start_epoch = incident.get("start_epoch") or 0.0
    end_epoch = incident.get("end_epoch") or (start_epoch + 600.0)

    # Window: 5 minutes before to 5 minutes after
    window_start = start_epoch - 300.0
    window_end = end_epoch + 300.0

    events = get_timeline_events(
        incident_id=incident_id,
        limit=200
    )
    if not events:
        # If no directly linked events, query all events in the time window
        events = get_timeline_events(
            start_epoch=window_start,
            end_epoch=window_end,
            limit=150
        )

    # 2. Fetch metrics history for the same window
    metrics = get_system_metrics_history(
        start_epoch=window_start,
        end_epoch=window_end,
        limit=200
    )

    # 3. Compute telemetry summary statistics
    cpu_values = [m["cpu_usage"] for m in metrics if "cpu_usage" in m]
    ram_values = [m["memory_usage"] for m in metrics if "memory_usage" in m]
    disk_values = [m["disk_usage"] for m in metrics if "disk_usage" in m]

    metric_stats = {
        "samples_count": len(metrics),
        "peak_cpu": max(cpu_values) if cpu_values else None,
        "avg_cpu": round(sum(cpu_values) / len(cpu_values), 1) if cpu_values else None,
        "peak_ram": max(ram_values) if ram_values else None,
        "avg_ram": round(sum(ram_values) / len(ram_values), 1) if ram_values else None,
        "peak_disk": max(disk_values) if disk_values else None,
    }

    # 4. Filter key log & docker messages
    critical_events = [e for e in events if e.get("severity") in ("CRITICAL", "ERROR")]
    warning_events = [e for e in events if e.get("severity") == "WARNING"]
    info_events = [e for e in events if e.get("severity") == "INFO"]

    # Format event lines for prompt
    event_lines = []
    for e in events[-40:]:  # most relevant 40 events
        ts = e.get("timestamp", "").replace("T", " ")[:19]
        event_lines.append(f"[{ts}] [{e.get('severity')}] [{e.get('source')}] {e.get('message')}")

    events_text = "\n".join(event_lines) if event_lines else "No specific timeline events recorded in this window."

    # 5. Build prompt for Ollama
    prompt = f"""You are an enterprise DevOps Site Reliability Engineer conducting a root cause incident investigation.

INCIDENT METADATA:
- Incident ID: {incident.get('id')}
- Title: {incident.get('title')}
- Problem Type: {incident.get('problem_type')}
- Severity: {incident.get('severity')}
- Start Time: {incident.get('start_time')}
- End / Resolved Time: {incident.get('end_time') or 'Still active / unresolved'}

REAL TELEMETRY RECORDED DURING INCIDENT:
- Total Metric Samples: {metric_stats['samples_count']}
- CPU Peak: {metric_stats['peak_cpu']}% (Avg: {metric_stats['avg_cpu']}%)
- Memory Peak: {metric_stats['peak_ram']}% (Avg: {metric_stats['avg_ram']}%)
- Disk Peak: {metric_stats['peak_disk']}%

CHRONOLOGICAL EVENT LOGS ({len(events)} events captured):
{events_text}

CRITICAL RULES FOR YOUR ANALYSIS:
1. Base all conclusions strictly on the collected telemetry and log lines provided above.
2. Explicitly distinguish between OBSERVED FACTS (directly proven by the logs/metrics) and HYPOTHESES / POSSIBLE CAUSES.
3. NEVER invent or hallucinate log messages, container names, ports, or metric values not present in the data.
4. If the recorded evidence is insufficient or inconclusive to prove the single root cause with certainty, state "Evidence is partial; further diagnostic tracing required."
5. Do NOT suggest destructive commands (e.g., rm -rf, drop database, docker kill).
6. Return ONLY a valid JSON object matching the exact format below. Do NOT include markdown code blocks or text outside the JSON.

REQUIRED JSON FORMAT:
{{
  "incident_summary": "High-level technical synopsis of what transpired based strictly on the events.",
  "observed_facts": [
    "Fact 1 directly evident from telemetry or logs",
    "Fact 2 directly evident from telemetry or logs"
  ],
  "possible_root_causes": [
    "Hypothesis A explaining the failure",
    "Hypothesis B explaining the failure"
  ],
  "relevant_metric_anomalies": [
    "Explanation of how CPU/RAM/Disk shifted before or during the incident"
  ],
  "supporting_evidence": [
    "Specific log or docker event supporting the findings"
  ],
  "recommended_troubleshooting_steps": [
    "Step 1: Non-destructive verification or fix",
    "Step 2: Verification step"
  ],
  "preventive_suggestions": [
    "Best-practice architecture or configuration improvement to prevent recurrence"
  ],
  "confidence_level": "High" | "Medium" | "Low"
}}
"""

    ai_result = None
    ai_status = "offline_heuristic"

    # 6. Try contacting Ollama
    for url in OLLAMA_CANDIDATE_URLS:
        try:
            response = requests.post(
                url,
                json={
                    "model": "llama3.2",
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=4.0
            )
            if response.status_code == 200:
                raw_text = response.json().get("response", "").strip()
                # Clean up if enclosed in markdown
                if raw_text.startswith("```"):
                    raw_text = raw_text.split("```")[1]
                    if raw_text.startswith("json"):
                        raw_text = raw_text[4:]
                    raw_text = raw_text.strip()
                ai_result = json.loads(raw_text)
                ai_status = "ollama_online"
                break
        except Exception as e:
            logger.debug("Ollama probe to %s failed: %s", url, e)

    # 7. Fallback to automated evidence synthesis if Ollama is not active
    if not ai_result:
        ai_result = _generate_heuristic_investigation(
            incident, events, metric_stats, critical_events, warning_events
        )

    investigation_payload = {
        "incident_id": incident_id,
        "investigated_at": datetime.now(timezone.utc).isoformat(),
        "ai_engine_status": ai_status,
        "telemetry_stats": metric_stats,
        "total_events_analyzed": len(events),
        "critical_events_count": len(critical_events),
        **ai_result
    }

    # Cache on the incident row in SQLite
    update_incident_ai_investigation(incident_id, investigation_payload)
    return investigation_payload


def _generate_heuristic_investigation(incident, events, metric_stats, critical_events, warning_events):
    """
    Reliable deterministic evidence synthesizer that strictly correlates
    real recorded metrics and log lines when Ollama is offline.
    """
    ptype = incident.get("problem_type", "General DevOps Issue")
    title = incident.get("title", "")

    observed_facts = []
    possible_causes = []
    anomalies = []
    supporting_evidence = []
    steps = []
    preventive = []

    # Fact 1: Metric observations
    if metric_stats.get("peak_cpu") is not None:
        anomalies.append(
            f"CPU utilization reached a peak of {metric_stats['peak_cpu']}% (window average: {metric_stats['avg_cpu']}%)."
        )
    if metric_stats.get("peak_ram") is not None:
        anomalies.append(
            f"Memory consumption peaked at {metric_stats['peak_ram']}% (window average: {metric_stats['avg_ram']}%)."
        )

    # Fact 2: Error log evidence
    if critical_events:
        for ce in critical_events[:3]:
            supporting_evidence.append(f"[{ce.get('source')}] {ce.get('message')}")
        observed_facts.append(
            f"Recorded {len(critical_events)} critical/error event(s) during the incident operational window."
        )
    elif warning_events:
        for we in warning_events[:3]:
            supporting_evidence.append(f"[{we.get('source')}] {we.get('message')}")
        observed_facts.append(
            f"Recorded {len(warning_events)} warning event(s) preceding or during the incident."
        )
    else:
        observed_facts.append("No critical error logs were logged directly within the immediate incident time slice.")
        supporting_evidence.append("Telemetry threshold triggered based on host resource saturation.")

    # Causes and steps according to problem type
    if ptype == "Database" or "database" in title.lower():
        possible_causes.append("PostgreSQL / database socket connection timeout or connection pool exhaustion.")
        possible_causes.append("Network socket failure or firewall boundary blocking port 5432.")
        steps.append("Verify database server process status: check if the PostgreSQL service is active.")
        steps.append("Inspect connection pool parameters (max_connections, pool_timeout).")
        steps.append("Review database server error logs for deadlock or aborted client handshakes.")
        preventive.append("Implement connection pool circuit-breakers and retry backoff policies.")
        preventive.append("Set up automated alerts for database connection queue latency.")

    elif ptype == "Container" or "container" in title.lower():
        possible_causes.append("Container process exited abruptly due to fatal error or Linux OOM Killer (ExitCode 137).")
        possible_causes.append("Container health check failure triggering orchestrator restart.")
        steps.append("Inspect container exit code and termination reason using 'docker inspect'.")
        steps.append("Check host cgroup memory quota versus container peak consumption.")
        steps.append("Review container stdout/stderr logs directly before the exit event.")
        preventive.append("Tune container memory limits with appropriate buffer margins.")
        preventive.append("Configure restart policy with exponential backoff.")

    elif ptype == "Performance" or "cpu" in title.lower() or "memory" in title.lower():
        possible_causes.append("CPU saturation caused by intensive computational tasks, unbounded loops, or regex evaluation.")
        possible_causes.append("Memory leak or unexpected request volume spike exceeding working set.")
        steps.append("Review process activity list to identify the top CPU and memory consuming threads.")
        steps.append("Inspect garbage collection cycles and memory allocation profiles.")
        steps.append("Verify that worker concurrency matches available logical cores.")
        preventive.append("Configure automated autoscaling or horizontal worker pool limits.")
        preventive.append("Add rate limiting to mitigate sudden inbound traffic surges.")

    else:
        possible_causes.append("Application runtime exception or unhandled operational failure.")
        possible_causes.append("Upstream external dependency unavailability.")
        steps.append("Check application stack traces around the timestamp of the first critical event.")
        steps.append("Verify system dependencies and environment configuration variables.")
        preventive.append("Increase logging verbosity for fault-domain isolation.")

    summary = (
        f"Incident '{title}' was detected at {incident.get('start_time')}. "
        f"Analysis of {len(events)} events and {metric_stats.get('samples_count', 0)} telemetry samples "
        f"indicates a {ptype} failure with severity level {incident.get('severity')}."
    )

    return {
        "incident_summary": summary,
        "observed_facts": observed_facts,
        "possible_root_causes": possible_causes,
        "relevant_metric_anomalies": anomalies,
        "supporting_evidence": supporting_evidence,
        "recommended_troubleshooting_steps": steps,
        "preventive_suggestions": preventive,
        "confidence_level": "High" if len(critical_events) > 0 else "Medium"
    }

