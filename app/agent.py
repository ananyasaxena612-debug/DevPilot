from ai_analyzer import analyze_with_ai


def run_agent(log_content):

    # Step 1: Ask AI to analyze the log
    analysis = analyze_with_ai(log_content)

    # Step 2: Convert analysis to lowercase
    analysis_lower = analysis.lower()

    # Step 3: Agent decides the troubleshooting plan

    if "database" in analysis_lower:

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

    elif "connection" in analysis_lower:

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

    elif "permission" in analysis_lower:

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

    elif "timeout" in analysis_lower:

        next_step = (
            "Check network connectivity and investigate "
            "why the requested service is responding slowly."
        )

        plan = [
            "Check network connectivity.",
            "Verify that the target service is running.",
            "Check whether the service is responding slowly.",
            "Review service logs for timeout-related errors."
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

    # Step 4: Return complete agent result
    return {
        "analysis": analysis,
        "next_step": next_step,
        "plan": plan
    }