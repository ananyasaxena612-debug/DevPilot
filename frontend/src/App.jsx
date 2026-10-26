import { useEffect, useState } from "react";
import "./App.css";

function App() {
  const [problem, setProblem] = useState("");
  const [logFile, setLogFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [aiOnline, setAiOnline] = useState(false);

  // Check backend / AI status
  useEffect(() => {
    fetch("http://127.0.0.1:5000/status")
      .then((response) => response.json())
      .then((data) => {
        setAiOnline(data.ai === "online");
      })
      .catch(() => {
        setAiOnline(false);
      });
  }, []);

  // Handle log file selection
  const handleFileChange = (event) => {
    const file = event.target.files[0];

    if (file) {
      setLogFile(file);
    }
  };

  // Send problem + log to backend
  const handleAnalyze = async () => {
    if (!problem && !logFile) {
      alert("Please describe the problem or upload a log file.");
      return;
    }

    setLoading(true);
    setResult(null);

    const formData = new FormData();

    formData.append("problem", problem);

    if (logFile) {
      formData.append("log", logFile);
    }

    try {
      const response = await fetch(
        "http://127.0.0.1:5000/analyze",
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json();

      if (data.success) {
        setResult(data);
      } else {
        setResult({
          problem_type: "Other",
          severity: "Unknown",
          analysis: "Something went wrong.",
          likely_causes: [],
          recommended_fixes: [],
          next_step: data.error || "Unable to analyze the log.",
          plan: [],
          total_lines: 0,
          error_count: 0,
          warning_count: 0,
        });
      }
    } catch (error) {
      setResult({
        problem_type: "Other",
        severity: "Unknown",
        analysis: "Unable to connect to DevPilot backend.",
        likely_causes: [],
        recommended_fixes: [],
        next_step:
          "Make sure the Flask backend is running on port 5000.",
        plan: [],
        total_lines: 0,
        error_count: 0,
        warning_count: 0,
      });
    }

    setLoading(false);
  };

  return (
    <div className="app">

      {/* Navbar */}
      <header className="navbar">

        <div className="logo">
          DevPilot
        </div>

        <div className="status">

          <span
            className={`status-dot ${
              aiOnline ? "online" : "offline"
            }`}
          ></span>

          {aiOnline ? "AI Online" : "AI Offline"}

        </div>

      </header>


      {/* Main Content */}
      <main className="container">

        {/* Hero Section */}
        <section className="hero">

          <p className="tag">
            DEVOPS TROUBLESHOOTING ASSISTANT
          </p>

          <h1>
            Find the problem.
            <br />
            <span>Fix it faster.</span>
          </h1>

          <p className="description">
            Upload your application log and let DevPilot
            analyze errors, identify possible causes,
            and generate a troubleshooting plan.
          </p>

        </section>


        {/* Input Card */}
        <section className="input-card">

          <label>
            Describe your problem
          </label>

          <textarea
            value={problem}
            onChange={(e) =>
              setProblem(e.target.value)
            }
            placeholder="Example: The application is unable to connect to the database..."
          />


          <label>
            Upload log file
          </label>


          {/* File Upload */}
          <div className="upload-box">

            <div className="upload-icon">
              File
            </div>

            <h3>
              {logFile
                ? logFile.name
                : "Upload your log file"}
            </h3>

            <p>
              {logFile
                ? "Log file selected successfully"
                : "Upload your .log or .txt file here"}
            </p>


            <label className="browse-btn">

              Browse files

              <input
                type="file"
                accept=".log,.txt"
                onChange={handleFileChange}
                hidden
              />

            </label>

          </div>


          {/* Analyze Button */}
          <button
            className="analyze-btn"
            onClick={handleAnalyze}
            disabled={loading}
          >

            {loading
              ? "Analyzing..."
              : "Analyze Log"}

          </button>

        </section>


        {/* Result Section */}
        {result && (

          <section className="result-card">

            <h2>
              AI Troubleshooting Analysis
            </h2>


            {/* Problem Type + Severity */}
            <div className="result-summary">

              <div className="summary-box">

                <span>
                  Problem Type
                </span>

                <strong>
                  {result.problem_type || "Other"}
                </strong>

              </div>


              <div className="summary-box">

                <span>
                  Severity
                </span>

                <strong
                  className={`severity ${
                    String(result.severity || "")
                      .toLowerCase()
                  }`}
                >
                  {result.severity || "Unknown"}
                </strong>

              </div>

            </div>


            {/* Main Problem */}
            <div className="result-section">

              <h3>
                Main Problem
              </h3>

              <p>
                {result.analysis ||
                  "No problem description available."}
              </p>

            </div>


            {/* Likely Causes */}
            <div className="result-section">

              <h3>
                Likely Causes
              </h3>

              {result.likely_causes?.length > 0 ? (

                <ul>

                  {result.likely_causes.map(
                    (cause, index) => (
                      <li key={index}>
                        {cause}
                      </li>
                    )
                  )}

                </ul>

              ) : (

                <p>
                  No specific cause identified.
                </p>

              )}

            </div>


            {/* Recommended Fixes */}
            <div className="result-section">

              <h3>
                Recommended Fixes
              </h3>

              {result.recommended_fixes?.length > 0 ? (

                <ol>

                  {result.recommended_fixes.map(
                    (fix, index) => (
                      <li key={index}>
                        {fix}
                      </li>
                    )
                  )}

                </ol>

              ) : (

                <p>
                  No specific fix was provided.
                </p>

              )}

            </div>


            {/* Next Step */}
            <div className="result-section">

              <h3>
                Next Step
              </h3>

              <p>
                {result.next_step ||
                  "No next step available."}
              </p>

            </div>


            {/* Troubleshooting Plan */}
            <div className="result-section">

              <h3>
                Troubleshooting Plan
              </h3>

              {result.plan?.length > 0 ? (

                <ol>

                  {result.plan.map(
                    (step, index) => (
                      <li key={index}>
                        {step}
                      </li>
                    )
                  )}

                </ol>

              ) : (

                <p>
                  No troubleshooting plan available.
                </p>

              )}

            </div>


            {/* Log Statistics */}
            <div className="result-section">

              <h3>
                Log Statistics
              </h3>

              <div className="statistics">

                <div className="stat-box">

                  <strong>
                    {result.total_lines ?? 0}
                  </strong>

                  <span>
                    Total Lines
                  </span>

                </div>


                <div className="stat-box">

                  <strong>
                    {result.error_count ?? 0}
                  </strong>

                  <span>
                    Errors
                  </span>

                </div>


                <div className="stat-box">

                  <strong>
                    {result.warning_count ?? 0}
                  </strong>

                  <span>
                    Warnings
                  </span>

                </div>

              </div>

            </div>

          </section>

        )}

      </main>

    </div>
  );
}

export default App;
