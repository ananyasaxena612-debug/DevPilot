import streamlit as st
from log_analyzer import analyze_log

st.title("DevPilot")
st.write("AI-powered DevOps Troubleshooting Assistant")

problem = st.text_area("Describe your problem")

log_file = st.file_uploader("Upload your log file", type=["log", "txt"])

if st.button("Analyze"):

    if log_file is not None:

        log_content = log_file.read().decode("utf-8")

        errors, warnings = analyze_log(log_content)

        st.subheader("Analysis Result")

        if errors:
            st.error("Errors Detected")

            for error in errors:
                st.write(error)
        else:
            st.success("No Errors Found")

        if warnings:
            st.warning("Warnings Detected")

            for warning in warnings:
                st.write(warning)
        else:
            st.info("No Warnings Found")

    else:
        st.warning("Please upload a log file.")
