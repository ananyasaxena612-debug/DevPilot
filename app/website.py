import streamlit as st

st.title("DevPilot")
st.write("AI-powered DevOps Troubleshooting Assistant")

problem = st.text_area("Describe your problem")

log_file = st.file_uploader("Upload your log file")

if st.button("Analyze"):
    st.write("Log received successfully!")
