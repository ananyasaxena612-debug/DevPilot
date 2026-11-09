import { Link } from "react-router-dom";
import {
  Activity,
  Box,
  FileSearch,
  ArrowRight,
  Cpu,
  Zap,
  CheckCircle2,
  Terminal,
  FileDown,
  Sparkles
} from "lucide-react";

export default function Home() {
  return (
    <div className="home-page">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-badge">
          <Sparkles size={14} className="hero-badge-icon" />
          <span>DEVOPS OBSERVABILITY & AI TROUBLESHOOTING</span>
        </div>

        <h1 className="hero-title">
          Monitor Smarter.
          <br />
          <span className="hero-gradient-text">Troubleshoot Faster.</span>
        </h1>

        <p className="hero-description">
          A unified, high-performance platform for real-time infrastructure metrics,
          Docker container observability, and intelligent AI root-cause log diagnostics.
          Identify bottlenecks, track health, and resolve outages with confidence.
        </p>

        <div className="hero-cta-group">
          <Link to="/monitoring" className="btn btn-primary btn-lg">
            <span>Get Started</span>
            <ArrowRight size={18} />
          </Link>

          <Link to="/analyze" className="btn btn-secondary btn-lg">
            <FileSearch size={18} />
            <span>Analyze Logs</span>
          </Link>
        </div>

        {/* Hero Features Metric Ribbon */}
        <div className="hero-highlights-strip">
          <div className="highlight-pill">
            <span className="highlight-dot green" />
            <span className="highlight-title">System Telemetry:</span>
            <span className="highlight-val">CPU, RAM & Disk</span>
          </div>
          <div className="highlight-pill">
            <span className="highlight-dot blue" />
            <span className="highlight-title">Docker Orchestration:</span>
            <span className="highlight-val">Real-time Containers</span>
          </div>
          <div className="highlight-pill">
            <span className="highlight-dot purple" />
            <span className="highlight-title">AI Diagnostics:</span>
            <span className="highlight-val">Instant Root Cause</span>
          </div>
        </div>
      </section>

      {/* Feature Cards Section */}
      <section className="features-section">
        <div className="section-header-centered">
          <span className="section-eyebrow">CORE MODULES</span>
          <h2 className="section-heading-lg">Engineered for Rapid DevOps Operations</h2>
          <p className="section-subtext">
            Three dedicated modules built to give engineering teams full visibility and
            actionable remediation plans for their infrastructure.
          </p>
        </div>

        <div className="feature-cards-grid">
          {/* Card 1: System Monitoring */}
          <div className="feature-card">
            <div className="feature-card-header">
              <div className="feature-icon-box blue-accent">
                <Activity size={26} />
              </div>
              <span className="feature-tag">REAL-TIME</span>
            </div>

            <h3 className="feature-title">System Monitoring</h3>
            <p className="feature-description">
              Live hardware telemetry and resource allocation tracking. Monitor CPU load
              across logical cores, virtual memory consumption, and disk capacity with
              automated 5-second polling.
            </p>

            <ul className="feature-checklist">
              <li>
                <CheckCircle2 size={16} className="check-icon" />
                <span>Live CPU utilization & core counts</span>
              </li>
              <li>
                <CheckCircle2 size={16} className="check-icon" />
                <span>Dynamic memory usage (Used / Free / Total)</span>
              </li>
              <li>
                <CheckCircle2 size={16} className="check-icon" />
                <span>Persistent disk storage metrics & alerts</span>
              </li>
              <li>
                <CheckCircle2 size={16} className="check-icon" />
                <span>Visual progress bars with threshold warnings</span>
              </li>
            </ul>

            <div className="feature-card-footer">
              <Link to="/monitoring" className="feature-btn">
                <span>Open System Monitor</span>
                <ArrowRight size={16} />
              </Link>
            </div>
          </div>

          {/* Card 2: Docker Monitoring */}
          <div className="feature-card">
            <div className="feature-card-header">
              <div className="feature-icon-box green-accent">
                <Box size={26} />
              </div>
              <span className="feature-tag">CONTAINERS</span>
            </div>

            <h3 className="feature-title">Docker Monitoring</h3>
            <p className="feature-description">
              Comprehensive container visibility directly integrated with the Docker engine.
              Inspect running versus stopped services, image versions, CPU allocation,
              memory thresholds, and container health.
            </p>

            <ul className="feature-checklist">
              <li>
                <CheckCircle2 size={16} className="check-icon" />
                <span>Aggregate summary (Total, Running, Stopped)</span>
              </li>
              <li>
                <CheckCircle2 size={16} className="check-icon" />
                <span>Detailed container fleet inventory table</span>
              </li>
              <li>
                <CheckCircle2 size={16} className="check-icon" />
                <span>Container ID, image tag, and runtime health</span>
              </li>
              <li>
                <CheckCircle2 size={16} className="check-icon" />
                <span>Real-time container status color-coding</span>
              </li>
            </ul>

            <div className="feature-card-footer">
              <Link to="/docker" className="feature-btn">
                <span>View Docker Fleet</span>
                <ArrowRight size={16} />
              </Link>
            </div>
          </div>

          {/* Card 3: AI Log Analysis */}
          <div className="feature-card highlighted-feature">
            <div className="feature-card-header">
              <div className="feature-icon-box purple-accent">
                <Sparkles size={26} />
              </div>
              <span className="feature-tag highlight">AI POWERED</span>
            </div>

            <h3 className="feature-title">AI Log Analysis</h3>
            <p className="feature-description">
              Upload application logs or describe complex incidents to get immediate
              root-cause classification, severity ranking, step-by-step remediation plans,
              and downloadable PDF troubleshooting reports.
            </p>

            <ul className="feature-checklist">
              <li>
                <CheckCircle2 size={16} className="check-icon" />
                <span>Supports <code>.log</code> and <code>.txt</code> file uploads</span>
              </li>
              <li>
                <CheckCircle2 size={16} className="check-icon" />
                <span>Severity classification (Critical, High, Medium, Low)</span>
              </li>
              <li>
                <CheckCircle2 size={16} className="check-icon" />
                <span>Actionable troubleshooting roadmap & next steps</span>
              </li>
              <li>
                <CheckCircle2 size={16} className="check-icon" />
                <span>One-click PDF incident report generation</span>
              </li>
            </ul>

            <div className="feature-card-footer">
              <Link to="/analyze" className="feature-btn highlight-btn">
                <span>Launch Log Analyzer</span>
                <ArrowRight size={16} />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Workflow Section: How DevPilot Works */}
      <section className="workflow-section">
        <div className="section-header-centered">
          <span className="section-eyebrow">WORKFLOW</span>
          <h2 className="section-heading-lg">From Incident to Resolution in Seconds</h2>
          <p className="section-subtext">
            DevPilot replaces tedious manual log grepping and resource checking with a streamlined, automated workflow.
          </p>
        </div>

        <div className="workflow-grid">
          <div className="workflow-step">
            <div className="step-number">01</div>
            <div className="step-content">
              <div className="step-icon">
                <Cpu size={22} />
              </div>
              <h4>Capture Telemetry</h4>
              <p>
                Host and container metrics stream in real-time. Detect CPU bottlenecks,
                memory leaks, or failing containers before outages impact users.
              </p>
            </div>
          </div>

          <div className="workflow-step">
            <div className="step-number">02</div>
            <div className="step-content">
              <div className="step-icon">
                <Terminal size={22} />
              </div>
              <h4>Upload & Describe</h4>
              <p>
                Drop your server log file or paste an error message. DevPilot scans error patterns,
                extracts log lines, and prepares incident context.
              </p>
            </div>
          </div>

          <div className="workflow-step">
            <div className="step-number">03</div>
            <div className="step-content">
              <div className="step-icon">
                <FileDown size={22} />
              </div>
              <h4>Diagnose & Remediate</h4>
              <p>
                Receive an instant AI diagnosis with verified fixes, prioritized next steps,
                and a production-ready PDF report for team post-mortems.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Call to Action Banner */}
      <section className="cta-banner">
        <div className="cta-content">
          <div className="cta-badge">
            <Zap size={14} />
            <span>OPTIMIZE YOUR INFRASTRUCTURE</span>
          </div>
          <h2>Ready to Supercharge Your DevOps Workflow?</h2>
          <p>
            Start monitoring system telemetry, managing container health, and analyzing
            incidents with DevPilot now.
          </p>
          <div className="cta-actions">
            <Link to="/monitoring" className="btn btn-primary btn-lg">
              <span>Go to System Monitor</span>
              <ArrowRight size={18} />
            </Link>
            <Link to="/analyze" className="btn btn-secondary btn-lg">
              <span>Start AI Log Analysis</span>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
