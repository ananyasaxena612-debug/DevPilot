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
          analysis: "Something went wrong.",
          next_step: data.error,
          plan: [],
        });
      }
    } catch (error) {
      setResult({
        analysis: "Unable to connect to DevPilot backend.",
        next_step:
          "Make sure the Flask backend is running on port 5000.",
        plan: [],
      });
    }

    setLoading(false);
  };

  return (
    <div className="app">

      {/* Navbar */}
      <header className="navbar">

        <div className="logo">
          ⚡ DevPilot
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
              📄
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
              : "🔍 Analyze Log"}

          </button>

        </section>


        {/* Result Section */}
        {result && (

          <section className="result-card">

            <h2>
              AI Troubleshooting Analysis
            </h2>


            {/* Analysis */}
            <h3>
              Analysis
            </h3>

            <p>
              {result.analysis}
            </p>


            {/* Next Step */}
            <h3>
              Next Step
            </h3>

            <p>
              {result.next_step}
            </p>


            {/* Troubleshooting Plan */}
            <h3>
              Troubleshooting Plan
            </h3>

            <ul>

              {result.plan?.map(
                (step, index) => (
                  <li key={index}>
                    {step}
                  </li>
                )
              )}

            </ul>


            {/* Log Statistics */}
            {(result.total_lines !== undefined) && (

              <>

                <h3>
                  Log Statistics
                </h3>

                <p>
                  Total Lines: {result.total_lines}
                  <br />

                  Errors: {result.error_count}
                  <br />

                  Warnings: {result.warning_count}
                </p>

              </>

            )}

          </section>

        )}

      </main>

    </div>
  );
}

export default App;