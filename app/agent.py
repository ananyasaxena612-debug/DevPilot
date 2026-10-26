from app.ai_analyzer import analyze_with_ai


def run_agent(log_content):

    # Step 1: Get structured response from AI
    analysis = analyze_with_ai(log_content)

    # Step 2: Extract values directly from dictionary
    problem_type = analysis.get("problem_type", "Other")
    severity = analysis.get("severity", "Unknown")

    main_problem = analysis.get(
        "main_problem",
        "No problem description available."
    )

    likely_causes = analysis.get(
        "likely_causes",
        []
    )

    recommended_fixes = analysis.get(
        "recommended_fixes",
        []
    )

    # Step 3: Normalize Problem Type
    allowed_problem_types = {
        "database": "Database",
        "network": "Network",
        "application": "Application",
        "permission": "Permission",
        "docker": "Docker",
        "configuration": "Configuration",
        "performance": "Performance",
        "other": "Other"
    }

    problem_type = allowed_problem_types.get(
        str(problem_type).strip().lower(),
        "Other"
    )

    # Step 4: Normalize Severity
    allowed_severities = {
        "critical": "Critical",
        "high": "High",
        "medium": "Medium",
        "low": "Low"
    }

    severity = allowed_severities.get(
        str(severity).strip().lower(),
        "Unknown"
    )

    # Step 5: Generate troubleshooting plan
    if problem_type == "Database":

        next_step = (
            "Check the database service status, "
            "database host, port, username, and password configuration."
        )

        plan = [
            "Check whether the database service is running.",
            "Verify the database host and port.",
            "Verify the database username and password configuration.",
            "Check database server logs for related errors."
        ]

    elif problem_type == "Network":

        next_step = (
            "Check network connectivity and verify that "
            "the required service is running."
        )

        plan = [
            "Check whether the required service is running.",
            "Verify network connectivity.",
            "Check the service host and port.",
            "Review related application and service logs."
        ]

    elif problem_type == "Permission":

        next_step = (
            "Check file and directory permissions "
            "for the affected application or service."
        )

        plan = [
            "Identify the file or directory causing the issue.",
            "Check its current permissions.",
            "Verify that the application user has the required access.",
            "Review security settings if the problem continues."
        ]

    elif problem_type == "Docker":

        next_step = (
            "Check the Docker container status, "
            "container logs, image configuration, and ports."
        )

        plan = [
            "Check whether the Docker container is running.",
            "Review the container logs for errors.",
            "Verify the Docker image and configuration.",
            "Check the required port mapping."
        ]

    elif problem_type == "Configuration":

        next_step = (
            "Review the application configuration "
            "and verify that all required settings are correct."
        )

        plan = [
            "Check the application configuration files.",
            "Verify required environment variables.",
            "Check configuration values for errors.",
            "Restart the application after correcting the configuration."
        ]

    elif problem_type == "Performance":

        next_step = (
            "Investigate slow response times and "
            "check application and system resources."
        )

        plan = [
            "Check application response time.",
            "Check CPU and memory usage.",
            "Identify slow operations or requests.",
            "Review service logs for performance issues."
        ]

    elif problem_type == "Application":

        next_step = (
            "Review the application error and "
            "investigate the affected component."
        )

        plan = [
            "Identify the application component causing the error.",
            "Review the relevant configuration.",
            "Check application logs for related errors.",
            "Restart the affected service if appropriate."
        ]

    else:

        next_step = (
            "Review the AI analysis and investigate "
            "the service mentioned in the log."
        )

        plan = [
            "Review the identified problem.",
            "Check the affected service status.",
            "Review the relevant configuration.",
            "Check application and service logs."
        ]

    # Step 6: Return final structured result
    return {
        "analysis": main_problem,
        "problem_type": problem_type,
        "severity": severity,
        "likely_causes": likely_causes,
        "recommended_fixes": recommended_fixes,
        "next_step": next_step,
        "plan": plan
    }
