import requests
import json


OLLAMA_URL = "http://host.docker.internal:11434/api/generate"


def analyze_with_ai(log_content):

    prompt = f"""
You are a professional DevOps troubleshooting assistant.

Analyze the application log carefully.

Your task is to identify:
1. The actual problem type
2. The severity based on the impact
3. The main technical problem
4. The most likely causes supported by the log
5. Practical recommended fixes

You MUST return ONLY valid JSON.

Do NOT use Markdown.
Do NOT use headings.
Do NOT use code fences.
Do NOT write anything outside the JSON.

Use EXACTLY this structure:

{{
    "problem_type": "Database",
    "severity": "Critical",
    "main_problem": "The application is unable to connect to the PostgreSQL database on port 5432.",
    "likely_causes": [
        "PostgreSQL service may not be running",
        "Database server may not be reachable on port 5432",
        "Database connection configuration may be incorrect"
    ],
    "recommended_fixes": [
        "Check whether the PostgreSQL service is running",
        "Verify that PostgreSQL is listening on port 5432",
        "Verify the database host and connection configuration"
    ]
}}

IMPORTANT RULES:

problem_type MUST be exactly one of:

Database
Network
Application
Permission
Docker
Configuration
Performance
Other

severity MUST be exactly one of:

Critical
High
Medium
Low

Severity rules:

Critical:
Use Critical when the problem prevents the application from functioning.

High:
Use High when the problem seriously affects an important application function.

Medium:
Use Medium when the problem affects functionality but the application can still operate.

Low:
Use Low only when the issue has minor impact and does not significantly affect functionality.

Do NOT automatically choose Low.

For a database connection failure that prevents the application from functioning,
use Critical or High depending on the evidence in the log.

main_problem must be short, specific and technical.

likely_causes MUST contain at least 2 practical causes
that are supported by the log.

recommended_fixes MUST contain at least 2 practical troubleshooting steps
that directly address the identified problem.

Do not return empty arrays when the log provides enough information
to identify reasonable causes or fixes.

Do not invent unrelated information.

IMPORTANT:

If the log contains an error such as:

"Connection refused on port 5432"

or indicates that the application cannot connect to PostgreSQL,
identify the problem as Database.

For this type of problem:

problem_type = "Database"

and if the database failure prevents the application from functioning:

severity = "Critical"

The causes and fixes should be specific to the database connection problem.

LOG:

{log_content}
"""

    try:

        # -----------------------------------------
        # Send request to Ollama
        # -----------------------------------------

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": "llama3.2",
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )

        response.raise_for_status()

        result = response.json()

        ai_response = result.get(
            "response",
            ""
        ).strip()


        # -----------------------------------------
        # Debug: Raw AI Response
        # -----------------------------------------

        print(
            "RAW AI RESPONSE:",
            ai_response,
            flush=True
        )


        # -----------------------------------------
        # Remove Markdown code fences if AI adds them
        # -----------------------------------------

        if ai_response.startswith("```"):

            ai_response = ai_response.replace(
                "```json",
                ""
            )

            ai_response = ai_response.replace(
                "```",
                ""
            )

            ai_response = ai_response.strip()


        # -----------------------------------------
        # Convert AI JSON to Python dictionary
        # -----------------------------------------

        try:

            structured_result = json.loads(
                ai_response
            )

        except json.JSONDecodeError:

            print(
                "AI returned invalid JSON:",
                ai_response,
                flush=True
            )

            return {
                "problem_type": "Other",
                "severity": "Unknown",
                "main_problem": ai_response,
                "likely_causes": [],
                "recommended_fixes": []
            }


        # -----------------------------------------
        # Allowed values
        # -----------------------------------------

        allowed_problem_types = {
            "database",
            "network",
            "application",
            "permission",
            "docker",
            "configuration",
            "performance",
            "other"
        }

        allowed_severities = {
            "critical",
            "high",
            "medium",
            "low"
        }


        # -----------------------------------------
        # Read AI fields
        # -----------------------------------------

        problem_type = str(
            structured_result.get(
                "problem_type",
                "Other"
            )
        ).strip()

        severity = str(
            structured_result.get(
                "severity",
                "Unknown"
            )
        ).strip()

        main_problem = str(
            structured_result.get(
                "main_problem",
                ""
            )
        ).strip()

        likely_causes = structured_result.get(
            "likely_causes",
            []
        )

        recommended_fixes = structured_result.get(
            "recommended_fixes",
            []
        )


        # -----------------------------------------
        # Normalize Problem Type
        # -----------------------------------------

        if problem_type.lower() in allowed_problem_types:

            problem_type_map = {
                "database": "Database",
                "network": "Network",
                "application": "Application",
                "permission": "Permission",
                "docker": "Docker",
                "configuration": "Configuration",
                "performance": "Performance",
                "other": "Other"
            }

            problem_type = problem_type_map[
                problem_type.lower()
            ]

        else:

            problem_type = "Other"


        # -----------------------------------------
        # Normalize Severity
        # -----------------------------------------

        if severity.lower() in allowed_severities:

            severity_map = {
                "critical": "Critical",
                "high": "High",
                "medium": "Medium",
                "low": "Low"
            }

            severity = severity_map[
                severity.lower()
            ]

        else:

            severity = "Unknown"


        # -----------------------------------------
        # Make sure causes are lists
        # -----------------------------------------

        if not isinstance(
            likely_causes,
            list
        ):

            likely_causes = [
                str(likely_causes)
            ]

        if not isinstance(
            recommended_fixes,
            list
        ):

            recommended_fixes = [
                str(recommended_fixes)
            ]


        # -----------------------------------------
        # Database fallback
        # -----------------------------------------

        log_lower = log_content.lower()


        database_error = (
            "5432" in log_lower
            or "postgresql" in log_lower
            or "postgres" in log_lower
            or "database connection" in log_lower
            or "connection refused" in log_lower
        )


        if database_error:

            problem_type = "Database"

            # If the log clearly shows connection failure,
            # the application is likely unable to use the database.

            if (
                "connection refused" in log_lower
                or "failed to connect" in log_lower
                or "database connection failed" in log_lower
                or "unable to connect" in log_lower
            ):

                severity = "Critical"


            # Fill missing AI causes
            if len(likely_causes) == 0:

                likely_causes = [

                    "PostgreSQL service may not be running.",

                    "PostgreSQL may not be reachable on port 5432.",

                    "Database host or connection configuration may be incorrect."

                ]


            # Fill missing AI fixes
            if len(recommended_fixes) == 0:

                recommended_fixes = [

                    "Check whether the PostgreSQL service is running.",

                    "Verify that PostgreSQL is listening on port 5432.",

                    "Verify the database host and connection configuration."

                ]


            # Fill missing main problem
            if not main_problem:

                main_problem = (
                    "The application is unable to connect "
                    "to the PostgreSQL database on port 5432."
                )


        # -----------------------------------------
        # Final safety fallback
        # -----------------------------------------

        if not main_problem:

            main_problem = (
                "The AI could not identify a specific problem."
            )


        # -----------------------------------------
        # Final structured response
        # -----------------------------------------

        final_result = {

            "problem_type": problem_type,

            "severity": severity,

            "main_problem": main_problem,

            "likely_causes": likely_causes,

            "recommended_fixes": recommended_fixes

        }


        print(
            "STRUCTURED AI RESULT:",
            json.dumps(
                final_result,
                indent=2
            ),
            flush=True
        )


        return final_result


    # -----------------------------------------
    # Ollama connection error
    # -----------------------------------------

    except requests.exceptions.RequestException as error:

        print(
            "Ollama connection error:",
            error,
            flush=True
        )

        return {

            "problem_type": "Other",

            "severity": "Unknown",

            "main_problem": (
                "Unable to connect to the AI service."
            ),

            "likely_causes": [

                "Ollama may not be running.",

                "The Ollama API may not be reachable."

            ],

            "recommended_fixes": [

                "Check whether Ollama is running.",

                "Verify the Ollama API address.",

                "Check Docker-to-host connectivity."

            ]

        }


    # -----------------------------------------
    # Unexpected error
    # -----------------------------------------

    except Exception as error:

        print(
            "AI analysis error:",
            error,
            flush=True
        )

        return {

            "problem_type": "Other",

            "severity": "Unknown",

            "main_problem": (
                "An unexpected error occurred "
                "during AI analysis."
            ),

            "likely_causes": [],

            "recommended_fixes": []

        }
