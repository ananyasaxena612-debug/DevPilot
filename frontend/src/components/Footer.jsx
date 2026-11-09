import { Link } from "react-router-dom";
import { Zap, ShieldCheck } from "lucide-react";

export default function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="footer-wrapper">
      <div className="footer-content">
        <div className="footer-top">
          <div className="footer-brand-column">
            <Link to="/" className="footer-brand">
              <div className="logo-badge mini">
                <Zap size={16} />
              </div>
              <span className="brand-name">DevPilot</span>
            </Link>
            <p className="footer-mission">
              Modern DevOps telemetry and AI-driven troubleshooting platform.
              Monitor system health, container fleets, and resolve production errors in seconds.
            </p>
            <div className="footer-badge">
              <ShieldCheck size={14} />
              <span>Production Ready Observability</span>
            </div>
          </div>

          <div className="footer-links-group">
            <div className="footer-column">
              <h4>Navigation</h4>
              <ul>
                <li><Link to="/">Home Overview</Link></li>
                <li><Link to="/monitoring">System Telemetry</Link></li>
                <li><Link to="/docker">Docker Containers</Link></li>
                <li><Link to="/analyze">AI Log Diagnostics</Link></li>
              </ul>
            </div>

            <div className="footer-column">
              <h4>Telemetry APIs</h4>
              <ul>
                <li><code>GET /monitor/system</code></li>
                <li><code>GET /monitor/docker</code></li>
                <li><code>POST /analyze</code></li>
                <li><code>POST /download-report</code></li>
              </ul>
            </div>

            <div className="footer-column">
              <h4>Core Engine</h4>
              <ul>
                <li><span className="footer-item-label">Backend:</span> Flask (Python)</li>
                <li><span className="footer-item-label">AI:</span> Ollama Llama Model</li>
                <li><span className="footer-item-label">Containers:</span> Docker Engine API</li>
                <li><span className="footer-item-label">Reporting:</span> ReportLab PDF</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="footer-bottom">
          <div className="footer-legal">
            <span>© {currentYear} DevPilot Platform. All rights reserved.</span>
          </div>
          <div className="footer-stats-summary">
            <span className="dot online-pulse" />
            <span>DevPilot System Active</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
