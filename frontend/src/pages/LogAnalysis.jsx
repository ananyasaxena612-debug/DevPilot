import { useState, useRef } from "react";
import {
  Upload,
  FileText,
  X,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  Download,
  Terminal,
  ShieldAlert,
  ArrowRight,
  ListOrdered,
  Sparkles,
  RotateCcw
} from "lucide-react";
import { analyzeLog, downloadPdfReport } from "../services/api";

const SAMPLE_SCENARIOS = [
  {
    label: "Database Connection Failure",
    problem: "The application backend failed to connect to PostgreSQL on port 5432 after cluster restart.",
    logContent: `2026-11-02 22:30:01 INFO Application boot sequence initiated
2026-11-02 22:30:03 INFO Loading config from environment
2026-11-02 22:30:05 WARNING Database connection is taking longer than expected (host: db.internal:5432)
2026-11-02 22:30:08 ERROR Database connection failed: connection refused to 10.0.0.12:5432
2026-11-02 22:30:08 ERROR psycopg2.OperationalError: could not connect to server: Connection refused
2026-11-02 22:30:09 CRITICAL Fatal exception encountered in worker thread; terminating server process
2026-11-02 22:30:10 INFO Application stopped with exit code 1`,
    filename: "database_error.log",
  },
  {
    label: "Disk Space Outage",
    problem: "File upload service crashed with disk write errors on root partition.",
    logContent: `2026-11-02 18:00:01 - INFO - Application worker started
2026-11-02 18:00:05 - INFO - Bulk batch upload request received (payload 1.4GB)
2026-11-02 18:00:10 - WARNING - Disk space is running critically low (<2% available on /var/log)
2026-11-02 18:00:12 - ERROR - OSError: [Errno 28] No space left on device: '/var/data/uploads/chunk_9.bin'
2026-11-02 18:00:15 - ERROR - Write transaction aborted for upload session #99142
2026-11-02 18:00:20 - INFO - Application stopped`,
    filename: "disk_exhaustion.log",
  },
];

export default function LogAnalysis() {
  const [problem, setProblem] = useState("");
  const [logFile, setLogFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [dragActive, setDragActive] = useState(false);

  const fileInputRef = useRef(null);
  const resultRef = useRef(null);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      validateAndSetFile(file);
    }
  };

  const validateAndSetFile = (file) => {
    const validExtensions = [".log", ".txt"];
    const ext = "." + file.name.split(".").pop().toLowerCase();
    if (!validExtensions.includes(ext) && file.type !== "text/plain") {
      setErrorMessage("Please upload a valid .log or .txt file.");
      return;
    }
    setLogFile(file);
    setErrorMessage("");
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const removeFile = (e) => {
    e.stopPropagation();
    setLogFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const loadSample = (scenario) => {
    setProblem(scenario.problem);
    const blob = new Blob([scenario.logContent], { type: "text/plain" });
    const file = new File([blob], scenario.filename, { type: "text/plain" });
    setLogFile(file);
    setErrorMessage("");
    setResult(null);
  };

  const handleReset = () => {
    setProblem("");
    setLogFile(null);
    setResult(null);
    setErrorMessage("");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleAnalyze = async () => {
    if (!problem.trim() && !logFile) {
      setErrorMessage("Please describe your problem or upload a log file.");
      return;
    }

    setLoading(true);
    setErrorMessage("");
    setResult(null);

    try {
      const data = await analyzeLog({ problem, logFile });
      setResult(data);
      setTimeout(() => {
        resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    } catch (err) {
      setErrorMessage(
        err.message || "Unable to complete AI analysis. Check that the backend is running."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadReport = async () => {
    if (!result) return;
    setDownloading(true);
    try {
      await downloadPdfReport({
        problem: problem || (logFile ? `Analysis for ${logFile.name}` : "DevOps incident report"),
        analysis: result.analysis,
        problem_type: result.problem_type,
        severity: result.severity,
        likely_causes: result.likely_causes,
        recommended_fixes: result.recommended_fixes,
        plan: result.plan,
        next_step: result.next_step,
      });
    } catch (err) {
      alert(err.message || "Failed to download PDF report.");
    } finally {
      setDownloading(false);
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  const getSeverityClass = (sev) => {
    const s = String(sev || "").toLowerCase();
    if (s.includes("crit")) return "sev-critical";
    if (s.includes("high")) return "sev-high";
    if (s.includes("med")) return "sev-medium";
    if (s.includes("low")) return "sev-low";
    return "sev-unknown";
  };

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div className="header-left">
          <div className="header-tag">
            <Sparkles size={14} />
            <span>AI DIAGNOSTICS</span>
          </div>
          <h1 className="page-title">AI Log Analysis</h1>
          <p className="page-description">
            Describe your infrastructure problem and upload server logs (.log, .txt) to receive instant root-cause analysis, severity classification, and remediation steps.
          </p>
        </div>
      </div>

      {/* Input Panel Card */}
      <div className="analysis-input-card">
        {/* Quick Sample Presets */}
        <div className="sample-presets-bar">
          <span className="presets-label">
            <Terminal size={14} />
            <span>Quick Test Scenarios:</span>
          </span>
          <div className="presets-buttons">
            {SAMPLE_SCENARIOS.map((scenario, idx) => (
              <button
                key={idx}
                type="button"
                className="btn-preset"
                onClick={() => loadSample(scenario)}
              >
                {scenario.label}
              </button>
            ))}
          </div>
        </div>

        {/* Problem Description */}
        <div className="form-group">
          <label htmlFor="problem-desc" className="form-label">
            <span>Describe the problem</span>
            <span className="form-label-hint">Optional if log file is provided</span>
          </label>
          <textarea
            id="problem-desc"
            rows={4}
            className="form-textarea"
            placeholder="Example: The web service fails with 502 Bad Gateway after deploying PostgreSQL database migrations..."
            value={problem}
            onChange={(e) => setProblem(e.target.value)}
          />
        </div>

        {/* File Upload Zone */}
        <div className="form-group">
          <label className="form-label">
            <span>Upload log file (.log, .txt)</span>
            <span className="form-label-hint">Max file size ~10MB</span>
          </label>

          <div
            className={`file-dropzone ${dragActive ? "dropzone-active" : ""} ${logFile ? "dropzone-has-file" : ""}`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".log,.txt,text/plain"
              onChange={handleFileChange}
              style={{ display: "none" }}
            />

            {logFile ? (
              <div className="selected-file-display">
                <div className="file-icon-wrap">
                  <FileText size={28} />
                </div>
                <div className="file-details">
                  <span className="file-name">{logFile.name}</span>
                  <span className="file-size">{formatFileSize(logFile.size)} • Ready for analysis</span>
                </div>
                <button
                  type="button"
                  className="btn-remove-file"
                  onClick={removeFile}
                  title="Remove file"
                  aria-label="Remove uploaded log file"
                >
                  <X size={16} />
                </button>
              </div>
            ) : (
              <div className="dropzone-idle">
                <div className="upload-circle-icon">
                  <Upload size={24} />
                </div>
                <h4>Drag and drop your log file here</h4>
                <p>or click to browse from your computer (.log or .txt files)</p>
                <span className="btn btn-secondary btn-sm dropzone-browse-btn">
                  Browse Files
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Error message if any */}
        {errorMessage && (
          <div className="form-error-banner">
            <AlertCircle size={16} />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Action Controls */}
        <div className="form-actions-row">
          <button
            type="button"
            className="btn btn-primary btn-lg action-analyze-btn"
            onClick={handleAnalyze}
            disabled={loading}
          >
            {loading ? (
              <>
                <div className="spinner-sm" />
                <span>Running AI Diagnosis...</span>
              </>
            ) : (
              <>
                <Sparkles size={18} />
                <span>Analyze Log with AI</span>
              </>
            )}
          </button>

          {(problem || logFile || result) && (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={handleReset}
              disabled={loading}
            >
              <RotateCcw size={16} />
              <span>Reset Form</span>
            </button>
          )}
        </div>
      </div>

      {/* Analysis Results Display */}
      {result && (
        <div className="analysis-result-container" ref={resultRef}>
          {/* Result Header & Status Banner */}
          <div className="result-header-card">
            <div className="result-badge-row">
              <span className="result-complete-pill">
                <CheckCircle2 size={14} />
                <span>AI ANALYSIS COMPLETE</span>
              </span>
              <span className="result-timestamp">{result.timestamp}</span>
            </div>

            <div className="result-classification-grid">
              {/* Problem Type Box */}
              <div className="classification-card">
                <span className="classification-label">PROBLEM TYPE</span>
                <div className="classification-value">
                  <Terminal size={18} className="text-accent" />
                  <strong>{result.problem_type || "General DevOps Issue"}</strong>
                </div>
              </div>

              {/* Severity Box */}
              <div className="classification-card">
                <span className="classification-label">SEVERITY LEVEL</span>
                <div className="classification-value">
                  <span className={`severity-tag ${getSeverityClass(result.severity)}`}>
                    <ShieldAlert size={16} />
                    <span>{result.severity || "Unknown"}</span>
                  </span>
                </div>
              </div>

              {/* Log Statistics Summary Box */}
              <div className="classification-card stats-card">
                <span className="classification-label">LOG TELEMETRY SUMMARY</span>
                <div className="log-stats-mini-row">
                  <div className="stat-unit">
                    <span className="stat-num">{result.log_stats?.total_lines ?? 0}</span>
                    <span className="stat-lbl">Lines</span>
                  </div>
                  <div className="stat-unit text-danger">
                    <span className="stat-num">{result.log_stats?.error_count ?? 0}</span>
                    <span className="stat-lbl">Errors</span>
                  </div>
                  <div className="stat-unit text-warning">
                    <span className="stat-num">{result.log_stats?.warning_count ?? 0}</span>
                    <span className="stat-lbl">Warnings</span>
                  </div>
                  <div className="stat-unit text-info">
                    <span className="stat-num">{result.log_stats?.info_count ?? 0}</span>
                    <span className="stat-lbl">Info</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Section: Main Technical Problem */}
          <div className="result-section-card">
            <div className="result-card-heading">
              <AlertCircle size={18} className="heading-icon text-accent" />
              <h3>Main Problem Diagnosis</h3>
            </div>
            <div className="diagnosis-box">
              <p>{result.analysis || "No specific problem description was provided."}</p>
            </div>
          </div>

          {/* Section: Likely Causes & Recommended Fixes */}
          <div className="results-two-col-grid">
            {/* Likely Causes */}
            <div className="result-section-card">
              <div className="result-card-heading">
                <AlertTriangle size={18} className="heading-icon text-warning" />
                <h3>Likely Causes</h3>
              </div>
              {result.likely_causes && result.likely_causes.length > 0 ? (
                <ol className="styled-ordered-list">
                  {result.likely_causes.map((cause, idx) => (
                    <li key={idx} className="list-item-card">
                      <span className="step-counter">{idx + 1}</span>
                      <p>{cause}</p>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="no-data-text">No specific root causes identified.</p>
              )}
            </div>

            {/* Recommended Fixes */}
            <div className="result-section-card">
              <div className="result-card-heading">
                <CheckCircle2 size={18} className="heading-icon text-green" />
                <h3>Recommended Fixes</h3>
              </div>
              {result.recommended_fixes && result.recommended_fixes.length > 0 ? (
                <ol className="styled-ordered-list">
                  {result.recommended_fixes.map((fix, idx) => (
                    <li key={idx} className="list-item-card fix-item">
                      <span className="step-counter green-counter">{idx + 1}</span>
                      <p>{fix}</p>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="no-data-text">No specific fix recommended.</p>
              )}
            </div>
          </div>

          {/* Section: Immediate Next Step */}
          <div className="result-section-card next-step-card">
            <div className="result-card-heading">
              <ArrowRight size={18} className="heading-icon text-accent" />
              <h3>Immediate Next Step</h3>
            </div>
            <div className="next-step-callout">
              <p>
                {result.next_step ||
                  "Review the recommended fixes above and verify application connectivity."}
              </p>
            </div>
          </div>

          {/* Section: Troubleshooting Action Plan */}
          <div className="result-section-card">
            <div className="result-card-heading">
              <ListOrdered size={18} className="heading-icon text-accent" />
              <h3>Troubleshooting Action Plan</h3>
            </div>
            {result.plan && result.plan.length > 0 ? (
              <div className="timeline-plan">
                {result.plan.map((step, idx) => (
                  <div key={idx} className="timeline-item">
                    <div className="timeline-marker">{idx + 1}</div>
                    <div className="timeline-content">
                      <span className="timeline-step-title">Phase {idx + 1}</span>
                      <p>{step}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="no-data-text">No sequential action plan was generated.</p>
            )}
          </div>

          {/* PDF Download and Actions Bar */}
          <div className="result-actions-card">
            <div className="actions-info">
              <h4>Export Incident Documentation</h4>
              <p>
                Download a formatted, professional PDF troubleshooting report containing all
                diagnostics, statistics, and remediation steps.
              </p>
            </div>
            <button
              type="button"
              className="btn btn-primary btn-lg download-report-btn"
              onClick={handleDownloadReport}
              disabled={downloading}
            >
              {downloading ? (
                <>
                  <div className="spinner-sm" />
                  <span>Generating PDF...</span>
                </>
              ) : (
                <>
                  <Download size={18} />
                  <span>Download PDF Report</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
