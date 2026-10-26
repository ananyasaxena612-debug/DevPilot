from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import os

# DevPilot ke app folder ka exact path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(BASE_DIR, "app")

sys.path.insert(0, APP_DIR)

from app.agent import run_agent


app = Flask(__name__)
CORS(app)


# -----------------------------------------
# Home
# -----------------------------------------

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "message": "DevPilot backend is running"
    })


# -----------------------------------------
# Backend + AI Status
# -----------------------------------------

@app.route("/status", methods=["GET"])
def status():

    return jsonify({
        "backend": "online",
        "ai": "online"
    })


# -----------------------------------------
# Analyze Log
# -----------------------------------------

@app.route("/analyze", methods=["POST"])
def analyze():

    try:

        # Problem description receive karna
        problem = request.form.get(
            "problem",
            ""
        )

        # Uploaded log file receive karna
        log_file = request.files.get(
            "log"
        )

        log = ""

        if log_file:

            log = log_file.read().decode(
                "utf-8",
                errors="ignore"
            )


        # -----------------------------------------
        # Basic Log Statistics
        # -----------------------------------------

        lines = log.splitlines()

        error_count = sum(
            1
            for line in lines
            if "ERROR" in line.upper()
        )

        warning_count = sum(
            1
            for line in lines
            if "WARNING" in line.upper()
        )


        # -----------------------------------------
        # Problem + Log
        # -----------------------------------------

        combined_log = f"""
Problem Description:
{problem}

Log:
{log}
"""


        # -----------------------------------------
        # Run DevPilot Agent
        # -----------------------------------------

        result = run_agent(
            combined_log
        )


        # -----------------------------------------
        # Extract AI Analysis
        # -----------------------------------------

        analysis = result.get(
            "analysis",
            "No analysis available."
        )

        problem_type = result.get(
            "problem_type",
            "Other"
        )

        severity = result.get(
            "severity",
            "Unknown"
        )

        likely_causes = result.get(
            "likely_causes",
            []
        )

        recommended_fixes = result.get(
            "recommended_fixes",
            []
        )

        next_step = result.get(
            "next_step",
            ""
        )

        plan = result.get(
            "plan",
            []
        )


        # -----------------------------------------
        # Send Complete Result to Frontend
        # -----------------------------------------

        return jsonify({

            "success": True,

            # AI result
            "analysis": analysis,

            "problem_type": problem_type,

            "severity": severity,

            "likely_causes": likely_causes,

            "recommended_fixes": recommended_fixes,

            # Agent result
            "next_step": next_step,

            "plan": plan,

            # Log statistics
            "total_lines": len(lines),

            "error_count": error_count,

            "warning_count": warning_count

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "error": str(e)

        }), 500


# -----------------------------------------
# Start Flask Server
# -----------------------------------------

app.run(
    host="0.0.0.0",
    port=5000,
    debug=True
)
