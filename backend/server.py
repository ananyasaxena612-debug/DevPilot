
import os
import io
import re
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import psutil
import docker

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from xml.sax.saxutils import escape
import sys
from pathlib import Path

current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.agent import run_agent

try:
    from backend.database import (
        init_db,
        get_incidents,
        get_incident_by_id,
        resolve_incident,
        create_incident,
        get_timeline_events,
        get_system_metrics_history,
        insert_timeline_event,
        insert_system_metric,
        create_user,
        get_user_by_email,
        get_user_by_id,
        verify_password,
        create_user_session_token,
        verify_user_session_token,
        create_server,
        get_servers,
        get_server_by_id,
        update_server,
        delete_server,
        record_server_heartbeat,
        create_enrollment_token,
        verify_and_consume_enrollment_token,
        generate_agent_api_key,
        verify_agent_api_key,
        revoke_agent_credentials,
        get_db_connection,
    )
    from backend.collector import collector
    from backend.investigator import investigate_incident as _investigate_incident
except ImportError:
    from database import (
        init_db,
        get_incidents,
        get_incident_by_id,
        resolve_incident,
        create_incident,
        get_timeline_events,
        get_system_metrics_history,
        insert_timeline_event,
        insert_system_metric,
        create_user,
        get_user_by_email,
        get_user_by_id,
        verify_password,
        create_user_session_token,
        verify_user_session_token,
        create_server,
        get_servers,
        get_server_by_id,
        update_server,
        delete_server,
        record_server_heartbeat,
        create_enrollment_token,
        verify_and_consume_enrollment_token,
        generate_agent_api_key,
        verify_agent_api_key,
        revoke_agent_credentials,
        get_db_connection,
    )
    from collector import collector
    from investigator import investigate_incident as _investigate_incident


# --------------------------------------------------
# FLASK CONFIGURATION
# --------------------------------------------------

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

# Initialize database and start background telemetry collection
try:
    init_db()
    collector.start()
    logger.info("DevPilot background telemetry collector started.")
except Exception as _init_err:
    logger.error("Failed to start collector: %s", _init_err)


def get_timestamp():
    return datetime.now(IST).strftime("%d-%m-%Y %I:%M:%S %p IST")


# --------------------------------------------------
# ERROR HANDLERS (Always return JSON, never HTML)
# --------------------------------------------------

@app.errorhandler(404)
def not_found_handler(error):
    return jsonify({
        "success": False,
        "error": f"Endpoint not found: {request.path}",
        "status": 404,
        "timestamp": get_timestamp()
    }), 404


@app.errorhandler(400)
def bad_request_handler(error):
    return jsonify({
        "success": False,
        "error": str(error),
        "status": 400,
        "timestamp": get_timestamp()
    }), 400


@app.errorhandler(500)
def internal_error_handler(error):
    return jsonify({
        "success": False,
        "error": "Internal server error occurred.",
        "status": 500,
        "timestamp": get_timestamp()
    }), 500


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def get_log_statistics(log_text):
    lines = log_text.splitlines()

    error_count = sum(
        1 for line in lines if "error" in line.lower()
    )

    warning_count = sum(
        1 for line in lines if "warning" in line.lower()
    )

    info_count = sum(
        1 for line in lines if "info" in line.lower()
    )

    return {
        "total_lines": len(lines),
        "error_count": error_count,
        "warning_count": warning_count,
        "info_count": info_count
    }


def normalize_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        return [value]

    return [str(value)]


# --------------------------------------------------
# MULTI-SERVER & AGENT STATE CACHE & HELPERS
# --------------------------------------------------

_remote_server_containers = {}   # server_id -> list of container dicts
_agent_incident_cooldowns = {}   # trigger_key -> last_epoch
_agent_consecutive_high_cpu = {} # server_id -> count
_agent_recent_error_epochs = {}  # server_id -> list of float epochs


def get_authenticated_user(required=False):
    """
    Extract and verify Bearer session token from request.
    Returns user dict or None.
    """
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "token" in request.args:
        token = request.args.get("token")

    user = verify_user_session_token(token) if token else None
    return user


def get_authenticated_agent():
    """
    Validate incoming agent API Key from X-Agent-Key or Authorization header.
    Returns server record dict or None.
    """
    api_key = request.headers.get("X-Agent-Key")
    if not api_key:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            api_key = auth[7:].strip()
        elif auth.startswith("Agent "):
            api_key = auth[6:].strip()
        elif auth.startswith("dpk_"):
            api_key = auth.strip()

    if not api_key or not api_key.startswith("dpk_"):
        return None

    return verify_agent_api_key(api_key)


def check_and_update_server_offline_statuses():
    """
    Checks servers with status 'online'. If heartbeat missed > 90s, marks offline.
    """
    now_epoch = datetime.now(timezone.utc).timestamp()
    try:
        servers = get_servers()
        for s in servers:
            if s.get("id") == "SRV-LOCAL-001":
                continue
            if s.get("status") == "online":
                last_hb = s.get("last_heartbeat_epoch") or 0.0
                if (now_epoch - last_hb) > 90.0:
                    update_server(s["id"], {"status": "offline"})
                    insert_timeline_event({
                        "server_id": s["id"],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "timestamp_epoch": now_epoch,
                        "event_type": "system",
                        "severity": "CRITICAL",
                        "source": "server:monitor",
                        "message": f"Server '{s.get('name')}' went OFFLINE: Agent heartbeat missed (>90s)",
                        "metadata": {"server_id": s["id"], "last_heartbeat_epoch": last_hb}
                    })
    except Exception as e:
        logger.debug("Heartbeat sweep notice: %s", e)


def evaluate_agent_metric_anomalies(server, metric):
    """
    Evaluate system thresholds for remote agent metrics and trigger incidents.
    """
    now_epoch = datetime.now(timezone.utc).timestamp()
    server_id = server["id"]
    cpu = float(metric.get("cpu_usage", 0.0))
    ram = float(metric.get("memory_usage", 0.0))
    disk = float(metric.get("disk_usage", 0.0))

    # CPU Check (consecutive)
    consecutive = _agent_consecutive_high_cpu.get(server_id, 0)
    if cpu >= 85.0:
        consecutive += 1
        _agent_consecutive_high_cpu[server_id] = consecutive
        if consecutive >= 2:
            _trigger_agent_incident(
                server=server,
                trigger_key=f"{server_id}:high_cpu",
                title=f"Sustained High CPU Load ({cpu:.1f}%) on {server.get('name')}",
                description=f"Host processor utilization reached {cpu:.1f}%, exceeding the operational threshold of 85.0%.",
                problem_type="Performance",
                severity="Critical" if cpu >= 92.0 else "High",
                metric_snapshot=metric
            )
    else:
        _agent_consecutive_high_cpu[server_id] = 0

    # Memory Check
    if ram >= 85.0:
        _trigger_agent_incident(
            server=server,
            trigger_key=f"{server_id}:high_memory",
            title=f"High Memory Alert ({ram:.1f}%) on {server.get('name')}",
            description=f"Memory utilization rose to {ram:.1f}% ({metric.get('memory_used_gb', 0)} GB used of {metric.get('memory_total_gb', 0)} GB).",
            problem_type="Performance",
            severity="High",
            metric_snapshot=metric
        )

    # Disk Check
    if disk >= 90.0:
        _trigger_agent_incident(
            server=server,
            trigger_key=f"{server_id}:high_disk",
            title=f"Critical Disk Volume Saturation ({disk:.1f}%) on {server.get('name')}",
            description=f"Root storage capacity reached {disk:.1f}%. Free space: {metric.get('disk_free_gb', 0)} GB.",
            problem_type="Performance",
            severity="Critical",
            metric_snapshot=metric
        )


def _trigger_agent_incident(server, trigger_key, title, description, problem_type, severity, metric_snapshot=None):
    now_epoch = datetime.now(timezone.utc).timestamp()
    last_triggered = _agent_incident_cooldowns.get(trigger_key, 0.0)
    if now_epoch - last_triggered < 180.0:
        return None

    active = get_incidents(server_id=server["id"], status="active", limit=5)
    for a in active:
        if a.get("title") == title:
            return None

    _agent_incident_cooldowns[trigger_key] = now_epoch
    now_iso = datetime.now(timezone.utc).isoformat()

    event_id = insert_timeline_event({
        "server_id": server["id"],
        "timestamp": now_iso,
        "timestamp_epoch": now_epoch,
        "event_type": "metric" if problem_type == "Performance" else "system",
        "severity": "CRITICAL" if severity == "Critical" else "ERROR",
        "source": f"agent:{server['id']}",
        "message": title,
        "metadata": metric_snapshot or {}
    })

    incident_id = create_incident({
        "server_id": server["id"],
        "user_id": server.get("user_id", "USR-ADMIN-001"),
        "title": title,
        "description": description,
        "problem_type": problem_type,
        "severity": severity,
        "start_time": now_iso,
        "start_epoch": now_epoch,
        "trigger_event_id": event_id
    })
    logger.info("Agent incident created for server %s: %s (id: %s)", server["id"], title, incident_id)
    return incident_id


# --------------------------------------------------
# HEALTH CHECK ROUTE
# --------------------------------------------------

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "DevPilot Backend is running!",
        "status": "online",
        "timestamp": get_timestamp()
    }), 200


# --------------------------------------------------
# STATUS ROUTE
# --------------------------------------------------

@app.route("/status", methods=["GET"])
def status():

    return jsonify({
        "backend": "online",
        "ai": "online",
        "application": "DevPilot",
        "timestamp": get_timestamp()
    }), 200


# --------------------------------------------------
# SYSTEM MONITORING ROUTE
# --------------------------------------------------

@app.route("/monitor/system", methods=["GET"])
def monitor_system():

    try:
        server_id = request.args.get("server_id")
        if server_id and server_id != "SRV-LOCAL-001":
            # Retrieve latest recorded metric sample for this remote server
            history = get_system_metrics_history(server_id=server_id, limit=1)
            if history:
                m = history[-1]
                return jsonify({
                    "server_id": server_id,
                    "cpu": {
                        "usage": m.get("cpu_usage", 0.0),
                        "cores": m.get("cpu_cores", 1)
                    },
                    "memory": {
                        "usage": m.get("memory_usage", 0.0),
                        "total": m.get("memory_total_gb", 0.0),
                        "used": m.get("memory_used_gb", 0.0),
                        "available": m.get("memory_available_gb", 0.0)
                    },
                    "disk": {
                        "usage": m.get("disk_usage", 0.0),
                        "total": m.get("disk_total_gb", 0.0),
                        "used": m.get("disk_used_gb", 0.0),
                        "free": m.get("disk_free_gb", 0.0)
                    },
                    "scope": "remote_server",
                    "timestamp": m.get("timestamp") or get_timestamp()
                }), 200
            else:
                return jsonify({
                    "server_id": server_id,
                    "cpu": {"usage": 0.0, "cores": 1},
                    "memory": {"usage": 0.0, "total": 0.0, "used": 0.0, "available": 0.0},
                    "disk": {"usage": 0.0, "total": 0.0, "used": 0.0, "free": 0.0},
                    "scope": "remote_server_waiting",
                    "timestamp": get_timestamp(),
                    "message": "Waiting for remote agent telemetry"
                }), 200

        # Local host monitoring fallback
        cpu_usage = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return jsonify({
            "server_id": "SRV-LOCAL-001",
            "cpu": {
                "usage": cpu_usage,
                "cores": psutil.cpu_count()
            },
            "memory": {
                "usage": memory.percent,
                "total": round(memory.total / (1024 ** 3), 2),
                "used": round(memory.used / (1024 ** 3), 2),
                "available": round(memory.available / (1024 ** 3), 2)
            },
            "disk": {
                "usage": disk.percent,
                "total": round(disk.total / (1024 ** 3), 2),
                "used": round(disk.used / (1024 ** 3), 2),
                "free": round(disk.free / (1024 ** 3), 2)
            },
            "scope": "backend_container",
            "timestamp": get_timestamp()
        }), 200

    except Exception as e:
        logger.exception("System monitoring failed")

        return jsonify({
            "error": str(e)
        }), 500


# --------------------------------------------------
# DOCKER MONITORING ROUTE
# --------------------------------------------------

@app.route("/monitor/docker", methods=["GET"])
def monitor_docker():

    try:
        server_id = request.args.get("server_id")
        if server_id and server_id != "SRV-LOCAL-001":
            # Fetch remote containers from memory cache
            containers = _remote_server_containers.get(server_id, [])
            running_cnt = sum(1 for c in containers if c.get("status") == "running")
            stopped_cnt = len(containers) - running_cnt
            return jsonify({
                "server_id": server_id,
                "total_containers": len(containers),
                "running": running_cnt,
                "stopped": stopped_cnt,
                "containers": containers,
                "scope": "remote_server",
                "timestamp": get_timestamp()
            }), 200

        # Local host docker inspection
        if not docker:
            return jsonify({
                "server_id": "SRV-LOCAL-001",
                "total_containers": 0,
                "running": 0,
                "stopped": 0,
                "containers": [],
                "timestamp": get_timestamp()
            }), 200

        client = docker.from_env()

        containers = client.containers.list(all=True)

        container_data = []

        running_count = 0
        stopped_count = 0

        for container in containers:

            container.reload()

            state = container.status

            if state == "running":
                running_count += 1
            else:
                stopped_count += 1

            container_data.append({
                "id": container.short_id,
                "name": container.name,
                "image": (
                    container.image.tags[0]
                    if container.image.tags
                    else "Unknown"
                ),
                "status": state
            })

        return jsonify({
            "server_id": "SRV-LOCAL-001",
            "total_containers": len(container_data),
            "running": running_count,
            "stopped": stopped_count,
            "containers": container_data,
            "timestamp": get_timestamp()
        }), 200

    except Exception as e:
        logger.exception("Docker monitoring failed")

        return jsonify({
            "error": str(e),
            "containers": [],
            "total_containers": 0,
            "running": 0,
            "stopped": 0
        }), 500


# --------------------------------------------------
# AI LOG ANALYSIS ROUTE
# --------------------------------------------------

@app.route("/analyze", methods=["POST"])
def analyze():

    try:
        problem = request.form.get("problem", "").strip()

        uploaded_file = request.files.get("log")

        log_text = ""

        # Read uploaded log file
        if uploaded_file and uploaded_file.filename:

            log_text = uploaded_file.read().decode(
                "utf-8",
                errors="replace"
            )

        if not problem and not log_text:
            return jsonify({
                "error": "Please describe your problem or upload a log file."
            }), 400

        # Combine problem description and uploaded log
        combined_input = f"""
Problem Description:
{problem if problem else "Not provided"}

Uploaded Log Content:
{log_text if log_text else "No log file uploaded"}
"""

        logger.info("Starting DevPilot analysis")

        # IMPORTANT:
        # run_agent accepts only ONE argument.
        agent_result = run_agent(combined_input)

        # Ensure the result is a dictionary
        if not isinstance(agent_result, dict):
            agent_result = {
                "analysis": str(agent_result)
            }

        analysis = agent_result.get(
            "analysis",
            agent_result.get("result", "No analysis returned.")
        )

        problem_type = agent_result.get(
            "problem_type",
            "General DevOps Issue"
        )

        severity = agent_result.get(
            "severity",
            "Unknown"
        )

        likely_causes = normalize_list(
            agent_result.get("likely_causes", [])
        )

        recommended_fixes = normalize_list(
            agent_result.get("recommended_fixes", [])
        )

        next_step = agent_result.get(
            "next_step",
            "Review the analysis and verify the suggested fixes."
        )

        plan = normalize_list(
            agent_result.get("plan", [])
        )

        log_stats = get_log_statistics(log_text)

        response = {
            "success": True,
            "analysis": analysis,
            "problem_type": problem_type,
            "severity": severity,
            "likely_causes": likely_causes,
            "recommended_fixes": recommended_fixes,
            "next_step": next_step,
            "plan": plan,
            "log_stats": log_stats,
            "timestamp": get_timestamp()
        }

        logger.info("Analysis completed successfully")

        return jsonify(response), 200

    except Exception as e:

        logger.exception("Analysis failed")

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# --------------------------------------------------
# PDF REPORT HELPER
# --------------------------------------------------

def add_numbered_list(story, items, styles):

    if not items:
        story.append(
            Paragraph("No information available.", styles["Normal"])
        )
        return

    for index, item in enumerate(items, start=1):

        safe_item = escape(str(item))

        story.append(
            Paragraph(
                f"<b>{index}.</b> {safe_item}",
                styles["Normal"]
            )
        )

        story.append(Spacer(1, 6))


# --------------------------------------------------
# PDF REPORT ROUTE
# --------------------------------------------------

@app.route("/download-report", methods=["POST"])
def download_report():

    try:
        data = request.get_json(silent=True) or {}

        buffer = io.BytesIO()

        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=45,
            leftMargin=45,
            topMargin=45,
            bottomMargin=45
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Title"],
            fontSize=22,
            textColor=colors.HexColor("#2563EB"),
            spaceAfter=12
        )

        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=13,
            textColor=colors.HexColor("#1D4ED8"),
            spaceBefore=12,
            spaceAfter=7
        )

        story = []

        story.append(
            Paragraph("DevPilot - Troubleshooting Report", title_style)
        )

        story.append(
            Paragraph(
                f"Generated on: {escape(get_timestamp())}",
                styles["Normal"]
            )
        )

        story.append(Spacer(1, 15))
        story.append(HRFlowable(width="100%", color=colors.grey))
        story.append(Spacer(1, 12))

        # Problem description
        story.append(
            Paragraph("Problem Description", heading_style)
        )

        problem = escape(str(data.get("problem", "Not provided")))

        story.append(
            Paragraph(problem, styles["Normal"])
        )

        # Analysis
        story.append(
            Paragraph("AI Analysis", heading_style)
        )

        analysis = escape(
            str(data.get("analysis", "No analysis available."))
        )

        story.append(
            Paragraph(analysis, styles["Normal"])
        )

        # Problem type
        story.append(
            Paragraph("Problem Type", heading_style)
        )

        problem_type = escape(
            str(data.get("problem_type", "Unknown"))
        )

        story.append(
            Paragraph(problem_type, styles["Normal"])
        )

        # Severity
        story.append(
            Paragraph("Severity", heading_style)
        )

        severity = escape(
            str(data.get("severity", "Unknown"))
        )

        story.append(
            Paragraph(severity, styles["Normal"])
        )

        # Likely causes
        story.append(
            Paragraph("Likely Causes", heading_style)
        )

        add_numbered_list(
            story,
            normalize_list(data.get("likely_causes", [])),
            styles
        )

        # Recommended fixes
        story.append(
            Paragraph("Recommended Fixes", heading_style)
        )

        add_numbered_list(
            story,
            normalize_list(data.get("recommended_fixes", [])),
            styles
        )

        # Action plan
        story.append(
            Paragraph("Action Plan", heading_style)
        )

        add_numbered_list(
            story,
            normalize_list(data.get("plan", [])),
            styles
        )

        # Next step
        story.append(
            Paragraph("Next Step", heading_style)
        )

        next_step = escape(
            str(data.get("next_step", "Not provided"))
        )

        story.append(
            Paragraph(next_step, styles["Normal"])
        )

        document.build(story)

        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name="DevPilot_Report.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:

        logger.exception("PDF generation failed")

        return jsonify({
            "error": str(e)
        }), 500


# --------------------------------------------------
# DYNAMIC INSTALLER ROUTES
# --------------------------------------------------

@app.route("/install.sh", methods=["GET"])
def serve_install_script():
    """Serve dynamic bash installer script for remote Linux servers."""
    try:
        script_path = project_root / "agent" / "install.sh"
        if not script_path.exists():
            # Fallback path if running in different working directory
            script_path = Path(__file__).resolve().parent.parent / "agent" / "install.sh"
        return send_file(
            str(script_path),
            mimetype="text/plain",
            as_attachment=False
        )
    except Exception as e:
        logger.exception("Failed to serve install.sh")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/agent/devpilot_agent.py", methods=["GET"])
def serve_agent_script():
    """Serve the standalone Python agent script for download."""
    try:
        script_path = project_root / "agent" / "devpilot_agent.py"
        if not script_path.exists():
            script_path = Path(__file__).resolve().parent.parent / "agent" / "devpilot_agent.py"
        return send_file(
            str(script_path),
            mimetype="text/plain",
            as_attachment=False
        )
    except Exception as e:
        logger.exception("Failed to serve devpilot_agent.py")
        return jsonify({"success": False, "error": str(e)}), 500


# --------------------------------------------------
# AUTHENTICATION API ROUTES
# --------------------------------------------------

@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    try:
        data = request.get_json(silent=True) or {}
        email = data.get("email", "").strip()
        password = data.get("password", "")
        name = data.get("name", "").strip()

        if not email or "@" not in email:
            return jsonify({"success": False, "error": "A valid email address is required."}), 400
        if len(password) < 6:
            return jsonify({"success": False, "error": "Password must be at least 6 characters."}), 400

        user = create_user(email=email, password=password, name=name)
        token = create_user_session_token(user["id"], user["email"])
        return jsonify({
            "success": True,
            "message": "User registered successfully.",
            "token": token,
            "user": user,
            "timestamp": get_timestamp()
        }), 201
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.exception("Registration failed")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    try:
        data = request.get_json(silent=True) or {}
        email = data.get("email", "").strip()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"success": False, "error": "Email and password are required."}), 400

        user = get_user_by_email(email)
        if not user or not verify_password(password, user["password_hash"]):
            return jsonify({"success": False, "error": "Invalid email or password."}), 401

        # Strip password hash before returning user object
        user_safe = {
            "id": user["id"],
            "email": user["email"],
            "name": user.get("name", "Operator"),
            "role": user.get("role", "admin"),
            "created_at": user.get("created_at")
        }
        token = create_user_session_token(user["id"], user["email"])
        return jsonify({
            "success": True,
            "message": "Authentication successful.",
            "token": token,
            "user": user_safe,
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        logger.exception("Login failed")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    try:
        user = get_authenticated_user()
        if not user:
            # Fall back to default admin for single-user dev mode
            user = get_user_by_id("USR-ADMIN-001")
        if not user:
            return jsonify({"success": False, "error": "Unauthorized"}), 401

        return jsonify({
            "success": True,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user.get("name", "Operator"),
                "role": user.get("role", "admin"),
                "created_at": user.get("created_at")
            },
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --------------------------------------------------
# SERVER MANAGEMENT API ROUTES
# --------------------------------------------------

@app.route("/api/servers", methods=["GET"])
def list_servers():
    try:
        check_and_update_server_offline_statuses()
        user = get_authenticated_user()
        user_id = user["id"] if user and user.get("role") != "admin" else None
        servers = get_servers(user_id=user_id)
        return jsonify({
            "success": True,
            "count": len(servers),
            "servers": servers,
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        logger.exception("Failed to list servers")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/servers", methods=["POST"])
def add_server():
    try:
        user = get_authenticated_user()
        user_id = user["id"] if user else "USR-ADMIN-001"

        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()
        hostname = data.get("hostname", "").strip()
        ip_address = data.get("ip_address", "").strip()
        os_info = data.get("os_info", "Linux").strip()

        if not name:
            return jsonify({"success": False, "error": "Server name is required."}), 400

        server = create_server(
            user_id=user_id,
            name=name,
            hostname=hostname,
            ip_address=ip_address,
            os_info=os_info
        )
        token = create_enrollment_token(server["id"], ttl_minutes=30)

        # Build dynamic install command using requested host
        host_url = request.host_url.rstrip("/")
        install_command = f"curl -sSL {host_url}/install.sh | sudo bash -s -- --endpoint {host_url} --token {token}"

        insert_timeline_event({
            "server_id": server["id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "timestamp_epoch": datetime.now(timezone.utc).timestamp(),
            "event_type": "system",
            "severity": "INFO",
            "source": "server:management",
            "message": f"Server '{name}' added to DevPilot. Enrollment token issued.",
            "metadata": {"server_id": server["id"], "user_id": user_id}
        })

        return jsonify({
            "success": True,
            "message": f"Server '{name}' created. Run install command on your server to enroll.",
            "server": server,
            "enrollment_token": token,
            "install_command": install_command,
            "expires_in_minutes": 30,
            "timestamp": get_timestamp()
        }), 201
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.exception("Failed to add server")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/servers/<server_id>", methods=["GET"])
def get_server_detail(server_id):
    try:
        check_and_update_server_offline_statuses()
        server = get_server_by_id(server_id)
        if not server:
            return jsonify({"success": False, "error": f"Server '{server_id}' not found."}), 404

        # Include latest metrics sample
        latest_metrics = get_system_metrics_history(server_id=server_id, limit=1)
        latest_sample = latest_metrics[-1] if latest_metrics else None

        return jsonify({
            "success": True,
            "server": server,
            "latest_metrics": latest_sample,
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/servers/<server_id>", methods=["PUT"])
def update_server_endpoint(server_id):
    try:
        data = request.get_json(silent=True) or {}
        updated = update_server(server_id, data)
        if not updated:
            return jsonify({"success": False, "error": f"Server '{server_id}' not found or no changes made."}), 404
        server = get_server_by_id(server_id)
        return jsonify({
            "success": True,
            "message": "Server updated successfully.",
            "server": server,
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/servers/<server_id>", methods=["DELETE"])
def delete_server_endpoint(server_id):
    try:
        if server_id == "SRV-LOCAL-001":
            return jsonify({"success": False, "error": "Primary DevPilot Server cannot be deleted."}), 400
        deleted = delete_server(server_id)
        if not deleted:
            return jsonify({"success": False, "error": f"Server '{server_id}' not found."}), 404
        return jsonify({
            "success": True,
            "message": f"Server '{server_id}' deleted successfully.",
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/servers/<server_id>/token", methods=["POST"])
def generate_new_enrollment_token(server_id):
    try:
        server = get_server_by_id(server_id)
        if not server:
            return jsonify({"success": False, "error": f"Server '{server_id}' not found."}), 404

        token = create_enrollment_token(server_id, ttl_minutes=30)
        host_url = request.host_url.rstrip("/")
        install_command = f"curl -sSL {host_url}/install.sh | sudo bash -s -- --endpoint {host_url} --token {token}"

        return jsonify({
            "success": True,
            "server_id": server_id,
            "enrollment_token": token,
            "install_command": install_command,
            "expires_in_minutes": 30,
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/servers/<server_id>/revoke", methods=["POST"])
def revoke_server_key(server_id):
    try:
        revoked = revoke_agent_credentials(server_id)
        return jsonify({
            "success": True,
            "message": f"Agent credentials for server '{server_id}' have been revoked.",
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --------------------------------------------------
# AGENT ENROLLMENT & INGESTION API ROUTES
# --------------------------------------------------

@app.route("/api/agent/enroll", methods=["POST"])
def agent_enroll():
    """Initial one-time registration exchange converting token to persistent agent API key."""
    try:
        data = request.get_json(silent=True) or {}
        token = data.get("enrollment_token", "").strip()
        if not token:
            return jsonify({"success": False, "error": "Enrollment token is required."}), 400

        server_id = verify_and_consume_enrollment_token(token)
        if not server_id:
            return jsonify({
                "success": False,
                "error": "Invalid or expired enrollment token. Please generate a new token in DevPilot."
            }), 401

        server = get_server_by_id(server_id)
        if not server:
            return jsonify({"success": False, "error": "Associated server not found."}), 404

        # Generate persistent agent API key
        api_key = generate_agent_api_key(server_id)

        # Update host runtime properties
        hostname = data.get("hostname", server.get("hostname", ""))
        ip_addr = data.get("ip_address", server.get("ip_address", ""))
        os_info = data.get("os_info", server.get("os_info", ""))
        agent_version = data.get("agent_version", "2.0.0")
        docker_enabled = int(data.get("docker_enabled", 0))

        now = datetime.now(timezone.utc)
        update_server(server_id, {
            "hostname": hostname,
            "ip_address": ip_addr,
            "os_info": os_info,
            "agent_version": agent_version,
            "docker_enabled": docker_enabled,
            "status": "online",
            "last_heartbeat_at": now.isoformat(),
            "last_heartbeat_epoch": now.timestamp()
        })

        insert_timeline_event({
            "server_id": server_id,
            "timestamp": now.isoformat(),
            "timestamp_epoch": now.timestamp(),
            "event_type": "system",
            "severity": "INFO",
            "source": f"agent:{server_id}",
            "message": f"DevPilot Agent v{agent_version} enrolled successfully for server '{server['name']}' ({hostname})",
            "metadata": {"hostname": hostname, "ip_address": ip_addr, "os_info": os_info}
        })

        logger.info("Successfully enrolled remote agent for server %s (%s)", server_id, server["name"])
        return jsonify({
            "success": True,
            "message": "Enrollment successful.",
            "server_id": server_id,
            "server_name": server["name"],
            "api_key": api_key,
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        logger.exception("Agent enrollment error")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/agent/heartbeat", methods=["POST"])
def agent_heartbeat():
    try:
        server = get_authenticated_agent()
        if not server:
            return jsonify({"success": False, "error": "Unauthorized agent key"}), 401

        data = request.get_json(silent=True) or {}
        record_server_heartbeat(
            server_id=server["id"],
            agent_version=data.get("agent_version"),
            os_info=data.get("os_info"),
            ip_address=data.get("ip_address"),
            docker_enabled=data.get("docker_enabled")
        )
        return jsonify({"success": True, "status": "online", "timestamp": get_timestamp()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/agent/metrics", methods=["POST"])
def agent_ingest_metrics():
    try:
        server = get_authenticated_agent()
        if not server:
            return jsonify({"success": False, "error": "Unauthorized agent key"}), 401

        data = request.get_json(silent=True) or {}
        server_id = server["id"]

        # Support single sample or batch of buffered samples
        samples = data if isinstance(data, list) else [data]
        inserted = 0
        for sample in samples:
            sample["server_id"] = server_id
            insert_system_metric(sample)
            inserted += 1

        # Evaluate threshold rules on newest sample
        if samples:
            newest = samples[-1]
            evaluate_agent_metric_anomalies(server, newest)

        # Update server keepalive
        now = datetime.now(timezone.utc)
        update_server(server_id, {
            "status": "online",
            "last_heartbeat_at": now.isoformat(),
            "last_heartbeat_epoch": now.timestamp()
        })

        return jsonify({
            "success": True,
            "server_id": server_id,
            "inserted_samples": inserted,
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        logger.exception("Error ingesting agent metrics")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/agent/docker", methods=["POST"])
def agent_ingest_docker():
    try:
        server = get_authenticated_agent()
        if not server:
            return jsonify({"success": False, "error": "Unauthorized agent key"}), 401

        data = request.get_json(silent=True) or {}
        containers = data.get("containers", [])
        server_id = server["id"]
        _remote_server_containers[server_id] = containers

        # Check for container failure state
        for c in containers:
            status = c.get("status", "").lower()
            if status in ("exited", "dead"):
                cname = c.get("name", "unknown")
                trigger_key = f"{server_id}:docker_exit_{cname}"
                now_epoch = datetime.now(timezone.utc).timestamp()
                if now_epoch - _agent_incident_cooldowns.get(trigger_key, 0.0) > 180.0:
                    _agent_incident_cooldowns[trigger_key] = now_epoch
                    now_iso = datetime.now(timezone.utc).isoformat()
                    eid = insert_timeline_event({
                        "server_id": server_id,
                        "timestamp": now_iso,
                        "timestamp_epoch": now_epoch,
                        "event_type": "docker",
                        "severity": "CRITICAL",
                        "source": f"docker:{cname}",
                        "message": f"Container '{cname}' exited on server {server.get('name')}",
                        "metadata": c
                    })
                    create_incident({
                        "server_id": server_id,
                        "user_id": server.get("user_id", "USR-ADMIN-001"),
                        "title": f"Container Outage: '{cname}' Stopped on {server.get('name')}",
                        "description": f"Container '{cname}' exited with status: {c.get('status_raw', status)}",
                        "problem_type": "Container",
                        "severity": "High",
                        "start_time": now_iso,
                        "start_epoch": now_epoch,
                        "trigger_event_id": eid
                    })

        return jsonify({"success": True, "count": len(containers), "timestamp": get_timestamp()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/agent/logs", methods=["POST"])
def agent_ingest_logs():
    try:
        server = get_authenticated_agent()
        if not server:
            return jsonify({"success": False, "error": "Unauthorized agent key"}), 401

        data = request.get_json(silent=True) or {}
        logs = data.get("logs", [])
        server_id = server["id"]
        now_epoch = datetime.now(timezone.utc).timestamp()

        recorded = 0
        for entry in logs:
            insert_timeline_event({
                "server_id": server_id,
                "timestamp": entry.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                "timestamp_epoch": now_epoch,
                "event_type": "log",
                "severity": entry.get("severity", "WARNING"),
                "source": entry.get("source", "agent:log"),
                "message": entry.get("message", ""),
                "metadata": entry
            })
            recorded += 1

            # Log burst detection
            if entry.get("severity") in ("CRITICAL", "ERROR"):
                burst = _agent_recent_error_epochs.setdefault(server_id, [])
                burst.append(now_epoch)

        # Evaluate error burst (>3 in 60s)
        cutoff = now_epoch - 60.0
        active_burst = [t for t in _agent_recent_error_epochs.get(server_id, []) if t >= cutoff]
        _agent_recent_error_epochs[server_id] = active_burst
        if len(active_burst) >= 3:
            _trigger_agent_incident(
                server=server,
                trigger_key=f"{server_id}:log_burst",
                title=f"Application Error Burst ({len(active_burst)} in 60s) on {server.get('name')}",
                description=f"A burst of {len(active_burst)} application errors was reported by the monitoring agent within 60 seconds.",
                problem_type="Application",
                severity="High"
            )

        return jsonify({"success": True, "recorded": recorded, "timestamp": get_timestamp()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --------------------------------------------------
# INCIDENT TIME MACHINE API ROUTES
# --------------------------------------------------

@app.route("/api/incidents", methods=["GET"])
def list_incidents():
    try:
        status_filter = request.args.get("status")
        server_id = request.args.get("server_id")
        user_id = request.args.get("user_id")
        limit = int(request.args.get("limit", 50))
        incidents = get_incidents(server_id=server_id, user_id=user_id, status=status_filter, limit=limit)
        return jsonify({
            "success": True,
            "count": len(incidents),
            "incidents": incidents,
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        logger.exception("Failed to fetch incidents")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/incidents/simulate", methods=["POST"])
def simulate_incident_endpoint():
    try:
        data = request.get_json(silent=True) or {}
        scenario = data.get("scenario", "database_outage")
        inc_id = collector.simulate_incident(scenario)
        incident = get_incident_by_id(inc_id)
        return jsonify({
            "success": True,
            "incident_id": inc_id,
            "incident": incident,
            "message": f"Simulated incident '{scenario}' created successfully.",
            "timestamp": get_timestamp()
        }), 201
    except Exception as e:
        logger.exception("Simulation failed")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/incidents/<incident_id>", methods=["GET"])
def get_incident_detail(incident_id):
    try:
        incident = get_incident_by_id(incident_id)
        if not incident:
            return jsonify({
                "success": False,
                "error": f"Incident '{incident_id}' not found."
            }), 404
        return jsonify({
            "success": True,
            "incident": incident,
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/incidents/<incident_id>/resolve", methods=["POST"])
def resolve_incident_endpoint(incident_id):
    try:
        data = request.get_json(silent=True) or {}
        notes = data.get("notes", "Marked resolved by operator.")
        updated = resolve_incident(incident_id, notes=notes)
        if not updated:
            return jsonify({
                "success": False,
                "error": "Incident not found or could not update."
            }), 404
        incident = get_incident_by_id(incident_id)
        return jsonify({
            "success": True,
            "message": f"Incident {incident_id} resolved.",
            "incident": incident,
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/incidents/<incident_id>/timeline", methods=["GET"])
def get_incident_timeline(incident_id):
    try:
        limit = int(request.args.get("limit", 200))
        event_type = request.args.get("event_type")
        severity = request.args.get("severity")
        inc = get_incident_by_id(incident_id)
        start_epoch = None
        end_epoch = None
        server_id = None
        if inc:
            server_id = inc.get("server_id")
            s = inc.get("start_epoch") or 0.0
            e = inc.get("end_epoch") or (s + 600.0)
            start_epoch = s - 300.0
            end_epoch = e + 300.0
        events = get_timeline_events(
            incident_id=incident_id,
            server_id=server_id,
            start_epoch=start_epoch,
            end_epoch=end_epoch,
            event_type=event_type,
            severity=severity,
            limit=limit
        )
        return jsonify({
            "success": True,
            "count": len(events),
            "events": events,
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/incidents/<incident_id>/metrics", methods=["GET"])
def get_incident_metrics(incident_id):
    try:
        limit = int(request.args.get("limit", 500))
        window_minutes = int(request.args.get("window", 5))
        window_minutes = max(1, min(window_minutes, 120))
        inc = get_incident_by_id(incident_id)
        start_epoch = None
        end_epoch = None
        server_id = None
        if inc:
            server_id = inc.get("server_id")
            s = inc.get("start_epoch") or datetime.now(timezone.utc).timestamp()
            e = inc.get("end_epoch") or s
            start_epoch = s - (window_minutes * 60.0)
            end_epoch = e + (window_minutes * 60.0)
        metrics = get_system_metrics_history(
            server_id=server_id,
            start_epoch=start_epoch,
            end_epoch=end_epoch,
            limit=limit
        )
        return jsonify({
            "success": True,
            "count": len(metrics),
            "metrics": metrics,
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/incidents/<incident_id>/investigate", methods=["POST"])
def investigate_incident_endpoint(incident_id):
    try:
        result = _investigate_incident(incident_id)
        return jsonify({
            "success": True,
            "investigation": result,
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        logger.exception("Investigation failed for incident %s", incident_id)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/metrics/history", methods=["GET"])
def get_metrics_history():
    try:
        range_str = request.args.get("range")
        server_id = request.args.get("server_id")
        limit = int(request.args.get("limit", 500))
        start_epoch = request.args.get("start_epoch", type=float)
        end_epoch = request.args.get("end_epoch", type=float)
        now_epoch = datetime.now(timezone.utc).timestamp()
        if range_str == "15m":
            start_epoch = now_epoch - 900.0
        elif range_str == "1h":
            start_epoch = now_epoch - 3600.0
        elif range_str == "6h":
            start_epoch = now_epoch - 21600.0
        elif range_str == "24h":
            start_epoch = now_epoch - 86400.0
        metrics = get_system_metrics_history(
            server_id=server_id,
            start_epoch=start_epoch,
            end_epoch=end_epoch,
            limit=limit
        )
        return jsonify({
            "success": True,
            "count": len(metrics),
            "metrics": metrics,
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/timeline", methods=["GET"])
def get_global_timeline():
    try:
        limit = int(request.args.get("limit", 200))
        server_id = request.args.get("server_id")
        start_epoch = request.args.get("start_epoch", type=float)
        end_epoch = request.args.get("end_epoch", type=float)
        event_type = request.args.get("event_type")
        severity = request.args.get("severity")
        events = get_timeline_events(
            server_id=server_id,
            start_epoch=start_epoch,
            end_epoch=end_epoch,
            event_type=event_type,
            severity=severity,
            limit=limit
        )
        return jsonify({
            "success": True,
            "count": len(events),
            "events": events,
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/collector/stats", methods=["GET"])
def collector_stats():
    try:
        stats = collector.get_stats()
        return jsonify({
            "success": True,
            "stats": stats,
            "timestamp": get_timestamp()
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --------------------------------------------------
# RUN SERVER
# --------------------------------------------------

if __name__ == "__main__":

    logger.info("Starting DevPilot backend")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
