
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
        get_timeline_events,
        get_system_metrics_history,
        insert_timeline_event,
    )
    from backend.collector import collector
    from backend.investigator import investigate_incident as _investigate_incident
except ImportError:
    from database import (
        init_db,
        get_incidents,
        get_incident_by_id,
        resolve_incident,
        get_timeline_events,
        get_system_metrics_history,
        insert_timeline_event,
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
        cpu_usage = psutil.cpu_percent(interval=0.5)

        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return jsonify({
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
# INCIDENT TIME MACHINE API ROUTES
# --------------------------------------------------

@app.route("/api/incidents", methods=["GET"])
def list_incidents():
    try:
        status_filter = request.args.get("status")
        limit = int(request.args.get("limit", 50))
        incidents = get_incidents(status=status_filter, limit=limit)
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
        if inc:
            s = inc.get("start_epoch") or 0.0
            e = inc.get("end_epoch") or (s + 600.0)
            start_epoch = s - 300.0
            end_epoch = e + 300.0
        events = get_timeline_events(
            incident_id=incident_id,
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
        if inc:
            s = inc.get("start_epoch") or datetime.now(timezone.utc).timestamp()
            e = inc.get("end_epoch") or s
            start_epoch = s - (window_minutes * 60.0)
            end_epoch = e + (window_minutes * 60.0)
        metrics = get_system_metrics_history(
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
        start_epoch = request.args.get("start_epoch", type=float)
        end_epoch = request.args.get("end_epoch", type=float)
        event_type = request.args.get("event_type")
        severity = request.args.get("severity")
        events = get_timeline_events(
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
