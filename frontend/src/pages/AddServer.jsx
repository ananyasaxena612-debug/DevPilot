import { useState, useEffect, useRef } from "react";
import { useNavigate, Link } from "react-router-dom";
import { createServer, getServerById } from "../services/api";
import {
  Server,
  Terminal,
  Copy,
  Check,
  ArrowLeft,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Shield,
  Cpu,
} from "lucide-react";

export default function AddServer() {
  const navigate = useNavigate();

  // Form states
  const [name, setName] = useState("");
  const [hostname, setHostname] = useState("");
  const [ipAddress, setIpAddress] = useState("");
  const [osInfo, setOsInfo] = useState("Ubuntu Linux");

  // Flow states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [createdData, setCreatedData] = useState(null); // { server, enrollment_token, install_command }
  const [copied, setCopied] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState("waiting"); // 'waiting' | 'connected'
  const pollTimerRef = useRef(null);

  // Poll server status after creation to detect when agent comes online
  useEffect(() => {
    if (!createdData?.server?.id || connectionStatus === "connected") return;

    const serverId = createdData.server.id;
    pollTimerRef.current = setInterval(async () => {
      try {
        const res = await getServerById(serverId);
        if (res?.server?.status === "online") {
          setConnectionStatus("connected");
          clearInterval(pollTimerRef.current);
        }
      } catch (err) {
        console.debug("Status polling ping:", err);
      }
    }, 3000);

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [createdData, connectionStatus]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!name.trim()) {
      setError("Please provide a name for this server");
      return;
    }

    try {
      setLoading(true);
      const res = await createServer({
        name: name.trim(),
        hostname: hostname.trim(),
        ip_address: ipAddress.trim(),
        os_info: osInfo,
      });
      setCreatedData(res);
      setConnectionStatus("waiting");
    } catch (err) {
      setError(err.message || "Failed to create server");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // ignore
    }
  };

  return (
    <div className="devpilot-page add-server-page">
      <div className="devpilot-page-header">
        <div>
          <Link to="/servers" className="btn-link" style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem", color: "var(--text-secondary)" }}>
            <ArrowLeft size={16} /> Back to Monitored Servers
          </Link>
          <h1 className="devpilot-title">
            <Server className="title-icon" /> Connect a Linux Server
          </h1>
          <p className="devpilot-subtitle">
            Register your Linux server and generate a secure, lightweight monitoring agent installation script
          </p>
        </div>
      </div>

      {error && (
        <div className="devpilot-banner devpilot-banner-error" style={{ marginBottom: "1.5rem" }}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      {!createdData ? (
        <div className="add-server-grid">
          {/* Form Card */}
          <div className="card form-card">
            <h2 className="card-title">Server Details</h2>
            <p className="card-subtitle">
              Provide identifying information for your host. SSH passwords or keys are never needed.
            </p>

            <form onSubmit={handleSubmit} className="add-server-form" style={{ marginTop: "1.5rem" }}>
              <div className="form-group">
                <label htmlFor="server-name">
                  Server Friendly Name <span className="required">*</span>
                </label>
                <input
                  id="server-name"
                  type="text"
                  placeholder="e.g. Production API Gateway or DB-Master"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
                <span className="field-hint">A human-readable label to identify this server in DevPilot</span>
              </div>

              <div className="form-row" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div className="form-group">
                  <label htmlFor="server-hostname">Hostname / FQDN (Optional)</label>
                  <input
                    id="server-hostname"
                    type="text"
                    placeholder="e.g. api-01.company.internal"
                    value={hostname}
                    onChange={(e) => setHostname(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="server-ip">IP Address (Optional)</label>
                  <input
                    id="server-ip"
                    type="text"
                    placeholder="e.g. 198.51.100.42"
                    value={ipAddress}
                    onChange={(e) => setIpAddress(e.target.value)}
                  />
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="server-os">Operating System</label>
                <select
                  id="server-os"
                  value={osInfo}
                  onChange={(e) => setOsInfo(e.target.value)}
                >
                  <option value="Ubuntu Linux">Ubuntu Linux</option>
                  <option value="Debian Linux">Debian Linux</option>
                  <option value="RHEL / CentOS / Rocky">RHEL / CentOS / Rocky</option>
                  <option value="Amazon Linux">Amazon Linux</option>
                  <option value="Arch Linux">Arch Linux</option>
                  <option value="Other Linux Distribution">Other Linux Distribution</option>
                </select>
              </div>

              <div className="form-actions" style={{ marginTop: "2rem" }}>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={loading}
                  style={{ width: "100%", justifyContent: "center" }}
                >
                  {loading ? (
                    <>
                      <RefreshCw className="spin" size={16} /> Generating Enrollment Credentials...
                    </>
                  ) : (
                    <>
                      <Terminal size={16} /> Generate Connection Token &amp; Command
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>

          {/* Security & Architecture Card */}
          <div className="card info-card">
            <h2 className="card-title">Zero-Credentials Security</h2>
            <div className="security-points" style={{ marginTop: "1rem" }}>
              <div className="security-point">
                <Shield className="point-icon" size={22} />
                <div>
                  <h4>No SSH Access Needed</h4>
                  <p>DevPilot never requests, accepts, or stores your SSH root passwords or private keys.</p>
                </div>
              </div>

              <div className="security-point">
                <Terminal className="point-icon" size={22} />
                <div>
                  <h4>Single-Use Short-Lived Token</h4>
                  <p>The enrollment token expires in 30 minutes and burns immediately upon first successful handshake.</p>
                </div>
              </div>

              <div className="security-point">
                <Cpu className="point-icon" size={22} />
                <div>
                  <h4>Ultra-Lightweight Standalone Agent</h4>
                  <p>Runs smoothly using Python standard library with minimal memory footprint (&lt;25MB) and zero external C-dependencies.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Step 2: Copy Command & Live Status */
        <div className="install-instruction-section">
          {connectionStatus === "connected" ? (
            <div className="devpilot-banner devpilot-banner-success" style={{ marginBottom: "2rem", padding: "1.5rem" }}>
              <CheckCircle size={32} style={{ color: "var(--status-online)" }} />
              <div>
                <h3 style={{ margin: "0 0 0.25rem 0", fontSize: "1.25rem" }}>Agent Connected Successfully!</h3>
                <p style={{ margin: 0, opacity: 0.9 }}>
                  <strong>{createdData.server.name}</strong> is now online and actively streaming system metrics and Docker telemetry to DevPilot.
                </p>
              </div>
              <div style={{ marginLeft: "auto", display: "flex", gap: "0.75rem" }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => navigate(`/monitoring?server_id=${createdData.server.id}`)}
                >
                  View Live Metrics &rarr;
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => navigate("/servers")}
                >
                  Server Fleet
                </button>
              </div>
            </div>
          ) : (
            <div className="devpilot-banner devpilot-banner-info" style={{ marginBottom: "2rem" }}>
              <RefreshCw className="spin" size={24} />
              <div>
                <h4 style={{ margin: "0 0 0.25rem 0" }}>Awaiting Agent Connection</h4>
                <p style={{ margin: 0 }}>
                  Execute the command below on <strong>{createdData.server.name}</strong>. This page will update automatically once telemetry is detected.
                </p>
              </div>
            </div>
          )}

          <div className="card command-display-card">
            <div className="command-header">
              <div>
                <h3 style={{ margin: 0, fontSize: "1.1rem" }}>Linux Terminal Command</h3>
                <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                  Run via SSH or host terminal as root or with sudo
                </span>
              </div>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => handleCopy(createdData.install_command)}
              >
                {copied ? <Check size={14} /> : <Copy size={14} />}
                <span>{copied ? "Copied to Clipboard!" : "Copy Command"}</span>
              </button>
            </div>

            <pre className="code-terminal" style={{ margin: "1rem 0" }}>
              {createdData.install_command}
            </pre>

            <div className="install-details-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginTop: "1.5rem" }}>
              <div className="detail-box">
                <span className="detail-label">Server ID</span>
                <span className="detail-value">{createdData.server.id}</span>
              </div>
              <div className="detail-box">
                <span className="detail-label">Enrollment Token (Expires in 30 min)</span>
                <span className="detail-value" style={{ fontFamily: "monospace" }}>
                  {createdData.enrollment_token}
                </span>
              </div>
            </div>
          </div>

          <div className="card manual-steps-card" style={{ marginTop: "1.5rem" }}>
            <h3 className="card-title">Alternative: Manual Setup</h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "1rem" }}>
              If you prefer not to pipe curl into bash:
            </p>
            <ol style={{ paddingLeft: "1.5rem", lineHeight: "1.7", fontSize: "0.9rem" }}>
              <li>
                Download the agent script:
                <br />
                <code>curl -sSL {createdData.install_command.split(" ")[2]} -o /opt/devpilot_agent.py</code>
              </li>
              <li>
                Run one-time enrollment:
                <br />
                <code>python3 /opt/devpilot_agent.py --enroll --endpoint {createdData.install_command.split("--endpoint ")[1].split(" ")[0]} --token {createdData.enrollment_token}</code>
              </li>
              <li>
                Run continuously in daemon mode:
                <br />
                <code>python3 /opt/devpilot_agent.py --daemon</code>
              </li>
            </ol>

            <div style={{ marginTop: "2rem", display: "flex", gap: "1rem" }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => navigate("/servers")}
              >
                Return to Servers List
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
