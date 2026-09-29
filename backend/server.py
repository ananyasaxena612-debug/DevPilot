from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import os

# DevPilot ke app folder ka exact path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(BASE_DIR, "app")

sys.path.insert(0, APP_DIR)

from agent import run_agent


app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "DevPilot backend is running"
    })


@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "backend": "online",
        "ai": "online"
    })


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        # Problem description receive karna
        problem = request.form.get("problem", "")

        # Uploaded log file receive karna
        log_file = request.files.get("log")

        log = ""

        if log_file:
            log = log_file.read().decode("utf-8", errors="ignore")

        # -----------------------------
        # Basic Log Statistics
        # -----------------------------

        lines = log.splitlines()

        error_count = sum(
            1 for line in lines
            if "ERROR" in line.upper()
        )

        warning_count = sum(
            1 for line in lines
            if "WARNING" in line.upper()
        )

        # Problem + Log ko AI Agent ko dena
        combined_log = f"""
Problem Description:
{problem}

Log:
{log}
"""

        # AI Agent run karna
        result = run_agent(combined_log)

        # Frontend ko complete response bhejna
        return jsonify({
            "success": True,

            "analysis": result.get(
                "analysis",
                ""
            ),

            "next_step": result.get(
                "next_step",
                ""
            ),

            "plan": result.get(
                "plan",
                []
            ),

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


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )