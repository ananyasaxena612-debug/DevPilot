import streamlit as st

from log_analyzer import analyze_log
from agent import run_agent


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="DevPilot",
    page_icon="⚡",
    layout="wide"
)


# --------------------------------------------------
# CUSTOM CSS
# --------------------------------------------------

st.markdown("""
<style>

    .main-title {
        font-size: 42px;
        font-weight: 700;
        margin-bottom: 5px;
    }

    .subtitle {
        font-size: 18px;
        color: #888888;
        margin-bottom: 30px;
    }

    .section-title {
        font-size: 24px;
        font-weight: 600;
        margin-top: 25px;
        margin-bottom: 15px;
    }

    .info-card {
        padding: 20px;
        border-radius: 12px;
        border: 1px solid rgba(128,128,128,0.25);
        margin-bottom: 15px;
    }

    .step-card {
        padding: 14px 18px;
        border-radius: 10px;
        border: 1px solid rgba(128,128,128,0.20);
        margin-bottom: 8px;
    }

    .status-card {
        padding: 18px;
        border-radius: 12px;
        border: 1px solid rgba(128,128,128,0.25);
        margin: 15px 0;
    }

</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# HEADER
# --------------------------------------------------

st.markdown(
    '<div class="main-title">⚡ DevPilot</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'AI-Powered DevOps Troubleshooting Assistant'
    '</div>',
    unsafe_allow_html=True
)


# --------------------------------------------------
# INPUT SECTION
# --------------------------------------------------

st.markdown(
    '<div class="section-title">📝 Describe the Problem</div>',
    unsafe_allow_html=True
)

problem = st.text_area(
    "Problem Description",
    placeholder="Example: The application is unable to connect to the database.",
    label_visibility="collapsed"
)


st.markdown(
    '<div class="section-title">📄 Upload Log File</div>',
    unsafe_allow_html=True
)

log_file = st.file_uploader(
    "Upload your application or server log",
    type=["log", "txt"]
)


# --------------------------------------------------
# ANALYZE BUTTON
# --------------------------------------------------

if st.button("🔍 Analyze Log", use_container_width=True):

    if log_file is None:

        st.warning("Please upload a log file before starting the analysis.")

    else:

        # ------------------------------------------
        # READ LOG FILE
        # ------------------------------------------

        log_content = log_file.read().decode("utf-8")


        # ------------------------------------------
        # LOG ANALYSIS
        # ------------------------------------------

        errors, warnings = analyze_log(log_content)


        # ------------------------------------------
        # BASIC LOG RESULTS
        # ------------------------------------------

        st.markdown(
            '<div class="section-title">📊 Log Analysis</div>',
            unsafe_allow_html=True
        )

        col1, col2 = st.columns(2)

        with col1:

            st.metric(
                "🔴 Errors Detected",
                len(errors)
            )

        with col2:

            st.metric(
                "🟡 Warnings Detected",
                len(warnings)
            )


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


        # ------------------------------------------
        # AI + AGENT ANALYSIS
        # ------------------------------------------

        st.markdown(
            '<div class="section-title">'
            '🤖 AI Troubleshooting Analysis'
            '</div>',
            unsafe_allow_html=True
        )


        # ------------------------------------------
        # CUSTOM ANALYSIS STATUS
        # ------------------------------------------

        with st.status(
            "⚡ DevPilot is analyzing your log...",
            expanded=True
        ) as status:

            st.write("✓ Log file received")

            st.write("✓ Detecting errors and warnings")

            st.write("⟳ AI analysis in progress")

            agent_result = run_agent(log_content)

            st.write("✓ Generating troubleshooting plan")

            status.update(
                label="✅ Analysis completed",
                state="complete",
                expanded=False
            )


        # ------------------------------------------
        # AI ANALYSIS RESULT
        # ------------------------------------------

        st.markdown(
            '<div class="info-card">',
            unsafe_allow_html=True
        )

        st.write(agent_result["analysis"])

        st.markdown(
            '</div>',
            unsafe_allow_html=True
        )


        # ------------------------------------------
        # RECOMMENDED NEXT STEP
        # ------------------------------------------

        st.markdown(
            '<div class="section-title">'
            '🧭 Recommended Next Step'
            '</div>',
            unsafe_allow_html=True
        )

        st.info(agent_result["next_step"])


        # ------------------------------------------
        # TROUBLESHOOTING PLAN
        # ------------------------------------------

        st.markdown(
            '<div class="section-title">'
            '🛠️ Troubleshooting Plan'
            '</div>',
            unsafe_allow_html=True
        )


        for number, step in enumerate(
            agent_result["plan"],
            start=1
        ):

            st.markdown(
                f"""
                <div class="step-card">
                    <strong>Step {number}</strong><br>
                    ➜ {step}
                </div>
                """,
                unsafe_allow_html=True
            )


        # ------------------------------------------
        # FOOTER MESSAGE
        # ------------------------------------------

        st.success(
            "Analysis complete. Review the recommended "
            "troubleshooting steps before taking action."
        )
