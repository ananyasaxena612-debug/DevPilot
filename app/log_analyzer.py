def analyze_log(log_content):
    errors = []
    warnings = []

    lines = log_content.splitlines()

    for line in lines:
        if "ERROR" in line:
            errors.append(line)

        if "WARNING" in line:
            warnings.append(line)

    return errors, warnings
