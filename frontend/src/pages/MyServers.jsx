import { useState, useEffect, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  getServers,
  deleteServer,
  revokeServerKey,
  generateServerToken,
} from "../services/api";
import {
  Server,
  Plus,
  Activity,
  Clock,
  Terminal,
  Trash2,
  Slash,
  RefreshCw,
  Copy,
  Check,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Layers,
} from "lucide-react";

export default function MyServers() {
  const navigate = useNavigate();
  const [servers, setServers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copiedToken, setCopiedToken] = useState(false);
  const [tokenModal, setTokenModal] = useState(null); // { server, command, token }
  const [actionLoading, setActionLoading] = useState(false);

  const fetchServers = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const res = await getServers();
      if (res?.servers) {
        setServers(res.servers);
      }
    } catch (err) {
      setError(err.message || "Failed to fetch monitored servers");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchServers();
    // Refresh servers list every 15 seconds to catch live status / heartbeat updates
    const interval = setInterval(fetchServers, 15000);
    return () => clearInterval(interval);
  }, [fetchServers]);

  const handleCopyCommand = async (cmd) => {
    try {
      await navigator.clipboard.writeText(cmd);
      setCopiedToken(true);
      setTimeout(() => setCopiedToken(false), 2500);
    } catch {
      // ignore
    }
  };

  const handleShowTokenModal = async (server) => {
    try {
      setActionLoading(true);
      const res = await generateServerToken(server.id);
      setTokenModal({
        server,
        command: res.install_command,
        token: res.enrollment_token,
      });
    } catch (err) {
      alert("Failed to generate token: " + err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRevoke = async (server) => {
    if (
      !window.confirm(
        `Are you sure you want to revoke agent credentials for '${server.name}'? The agent will be disconnected and marked offline.`
      )
    ) {
      return;
    }
    try {
      setActionLoading(true);
      await revokeServerKey(server.id);
      await fetchServers();
    } catch (err) {
      alert("Revocation failed: " + err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async (server) => {
    if (server.id === "SRV-LOCAL-001") {
      alert("The primary local server cannot be deleted.");
      return;
    }
    if (
      !window.confirm(
        `Permanently remove server '${server.name}' (${server.id}) and all its historical configuration?`
      )
    ) {
      return;
    }
    try {
      setActionLoading(true);
      await deleteServer(server.id);
      await fetchServers();
    } catch (err) {
      alert("Delete failed: " + err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // Stats calculation
  const totalServers = servers.length;
  const onlineServers = servers.filter((s) => s.status === "online").length;
  const offlineServers = servers.filter((s) => s.status === "offline").length;
  const pendingServers = servers.filter((s) => s.status === "pending").length;
  const activeIncidentsTotal = servers.reduce(
    (acc, s) => acc + (s.active_incidents || 0),
    0
  );

  return (
    <div className="devpilot-page my-servers-page">
      {/* Page Header */}
      <div className="devpilot-page-header">
        <div>
          <h1 className="devpilot-title">
            <Server className="title-icon" /> Monitored Servers
          </h1>
          <p className="devpilot-subtitle">
            Manage Linux servers, inspect remote telemetry, and register new monitoring agents
          </p>
        </div>
        <div className="header-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={fetchServers}
            disabled={loading}
            title="Refresh Server List"
          >
            <RefreshCw className={loading ? "spin" : ""} size={16} /> Refresh
          </button>
          <Link to="/servers/add" className="btn btn-primary">
            <Plus size={16} /> Add Linux Server
          </Link>
        </div>
      </div>

      {error && (
        <div className="devpilot-banner devpilot-banner-error">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* Summary KPI Cards */}
      <div className="metrics-grid server-kpi-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Total Servers</span>
            <Server className="metric-icon" style={{ color: "var(--accent-primary)" }} />
          </div>
          <div className="metric-value">{totalServers}</div>
          <div className="metric-subtext">Infrastructure fleet</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Online &amp; Healthy</span>
            <CheckCircle className="metric-icon" style={{ color: "var(--status-online)" }} />
          </div>
          <div className="metric-value" style={{ color: "var(--status-online)" }}>
            {onlineServers}
          </div>
          <div className="metric-subtext">Actively transmitting telemetry</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Offline / Pending</span>
            <XCircle className="metric-icon" style={{ color: "var(--status-critical)" }} />
          </div>
          <div className="metric-value">
            {offlineServers + pendingServers}
          </div>
          <div className="metric-subtext">
            {offlineServers} offline &bull; {pendingServers} awaiting agent
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Active Incidents</span>
            <Activity className="metric-icon" style={{ color: activeIncidentsTotal > 0 ? "var(--status-critical)" : "var(--status-online)" }} />
          </div>
          <div className="metric-value" style={{ color: activeIncidentsTotal > 0 ? "var(--status-critical)" : "inherit" }}>
            {activeIncidentsTotal}
          </div>
          <div className="metric-subtext">Requiring operator attention</div>
        </div>
      </div>

      {/* Servers List */}
      <div className="servers-list-section" style={{ marginTop: "2rem" }}>
        <h2 className="section-title">Connected Server Fleet</h2>

        {loading && servers.length === 0 ? (
          <div className="loading-state">
            <RefreshCw className="spin" size={32} />
            <p>Loading server telemetry...</p>
          </div>
        ) : servers.length === 0 ? (
          <div className="empty-state-card">
            <Server size={48} style={{ opacity: 0.4, marginBottom: "1rem" }} />
            <h3>No Linux servers registered yet</h3>
            <p>Connect your first Linux server to start collecting metrics and detecting incidents.</p>
            <Link to="/servers/add" className="btn btn-primary" style={{ marginTop: "1rem" }}>
              <Plus size={16} /> Connect First Server
            </Link>
          </div>
        ) : (
          <div className="server-cards-grid">
            {servers.map((server) => {
              const isOnline = server.status === "online";
              const isPending = server.status === "pending";

              return (
                <div key={server.id} className={`server-card status-${server.status}`}>
                  <div className="server-card-top">
                    <div className="server-info-primary">
                      <div className="server-title-row">
                        <span className={`status-indicator-dot status-dot-${server.status}`} />
                        <h3 className="server-name">{server.name}</h3>
                        <span className="server-badge-id">{server.id}</span>
                      </div>
                      <div className="server-meta-tags">
                        <span className="tag">{server.os_info || "Linux"}</span>
                        {server.hostname && <span className="tag">{server.hostname}</span>}
                        {server.ip_address && <span className="tag">{server.ip_address}</span>}
                        {server.agent_version && <span className="tag">Agent v{server.agent_version}</span>}
                      </div>
                    </div>

                    <div className="server-status-pill-wrapper">
                      <span className={`server-status-pill status-${server.status}`}>
                        {isOnline ? "Online" : isPending ? "Pending Agent" : "Offline"}
                      </span>
                    </div>
                  </div>

                  <div className="server-card-body">
                    <div className="server-metrics-summary">
                      <div className="summary-item">
                        <span className="summary-label">Heartbeat</span>
                        <span className="summary-value">
                          {server.last_heartbeat_at
                            ? new Date(server.last_heartbeat_at).toLocaleTimeString()
                            : "Never"}
                        </span>
                      </div>
                      <div className="summary-item">
                        <span className="summary-label">Docker Telemetry</span>
                        <span className="summary-value">
                          {server.docker_enabled ? "Enabled" : "Disabled"}
                        </span>
                      </div>
                      <div className="summary-item">
                        <span className="summary-label">Active Incidents</span>
                        <span
                          className={`summary-value ${
                            server.active_incidents > 0 ? "text-critical" : "text-success"
                          }`}
                        >
                          {server.active_incidents || 0} active
                        </span>
                      </div>
                    </div>

                    {server.active_incidents > 0 && (
                      <div className="server-incident-alert">
                        <AlertTriangle size={16} />
                        <span>
                          {server.active_incidents} active incident(s) detected on this server.
                        </span>
                        <Link
                          to={`/incidents?server_id=${server.id}`}
                          className="btn-link"
                          style={{ marginLeft: "auto", fontSize: "0.85rem", fontWeight: 600 }}
                        >
                          Replay in Time Machine &rarr;
                        </Link>
                      </div>
                    )}
                  </div>

                  <div className="server-card-actions">
                    <button
                      type="button"
                      className="btn btn-sm btn-outline"
                      onClick={() => navigate(`/monitoring?server_id=${server.id}`)}
                      title="View System CPU, Memory & Disk Telemetry"
                    >
                      <Activity size={14} /> Live Metrics
                    </button>

                    <button
                      type="button"
                      className="btn btn-sm btn-outline"
                      onClick={() => navigate(`/docker?server_id=${server.id}`)}
                      title="View Docker Containers"
                    >
                      <Layers size={14} /> Containers
                    </button>

                    <button
                      type="button"
                      className="btn btn-sm btn-outline"
                      onClick={() => navigate(`/incidents?server_id=${server.id}`)}
                      title="Investigate Incidents"
                    >
                      <Clock size={14} /> Incidents
                    </button>

                    <div className="server-card-action-menu" style={{ marginLeft: "auto", display: "flex", gap: "0.5rem" }}>
                      <button
                        type="button"
                        className="btn btn-sm btn-secondary"
                        onClick={() => handleShowTokenModal(server)}
                        title="View Installation Command / Token"
                        disabled={actionLoading}
                      >
                        <Terminal size={14} /> Install
                      </button>

                      {isOnline && (
                        <button
                          type="button"
                          className="btn btn-sm btn-warning"
                          onClick={() => handleRevoke(server)}
                          title="Revoke Agent Key"
                          disabled={actionLoading}
                        >
                          <Slash size={14} />
                        </button>
                      )}

                      {server.id !== "SRV-LOCAL-001" && (
                        <button
                          type="button"
                          className="btn btn-sm btn-danger"
                          onClick={() => handleDelete(server)}
                          title="Delete Server"
                          disabled={actionLoading}
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Token / Install Command Modal */}
      {tokenModal && (
        <div className="devpilot-modal-overlay" onClick={() => setTokenModal(null)}>
          <div
            className="devpilot-modal-card"
            style={{ maxWidth: "700px" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="devpilot-modal-header">
              <div>
                <h2 className="devpilot-modal-title">
                  Install Agent on {tokenModal.server.name}
                </h2>
                <p className="devpilot-modal-subtitle">
                  Run this command on your Linux terminal to register and start the DevPilot agent
                </p>
              </div>
              <button
                type="button"
                className="devpilot-modal-close"
                onClick={() => setTokenModal(null)}
              >
                &times;
              </button>
            </div>

            <div className="modal-body">
              <div className="command-block-container">
                <div className="command-header">
                  <span>One-Line Automated Linux Installer</span>
                  <button
                    type="button"
                    className="btn btn-sm btn-outline"
                    onClick={() => handleCopyCommand(tokenModal.command)}
                  >
                    {copiedToken ? <Check size={14} /> : <Copy size={14} />}
                    <span>{copiedToken ? "Copied!" : "Copy"}</span>
                  </button>
                </div>
                <pre className="code-terminal">{tokenModal.command}</pre>
              </div>

              <div className="install-notes" style={{ marginTop: "1rem", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                <p><strong>What this installer does:</strong></p>
                <ul style={{ paddingLeft: "1.25rem", marginTop: "0.5rem" }}>
                  <li>Verifies Python 3 presence and downloads the standalone monitoring agent</li>
                  <li>Exchanges this single-use enrollment token for a persistent agent API key</li>
                  <li>Configures <code>/etc/systemd/system/devpilot-agent.service</code> for continuous monitoring</li>
                  <li>Starts telemetry collection for CPU, RAM, disk, load average, and Docker containers</li>
                </ul>
              </div>

              <div className="modal-footer" style={{ marginTop: "1.5rem", display: "flex", justifyContent: "flex-end" }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => setTokenModal(null)}
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
