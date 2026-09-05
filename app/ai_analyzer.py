import requests


def analyze_with_ai(log_content):

    prompt = f"""
You are a DevOps troubleshooting assistant.

Analyze the following log and provide:
1. Main problem
2. Likely cause
3. Recommended solution

Log:
{log_content}
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False
        }
    )

    result = response.json()

    return result["response"]
