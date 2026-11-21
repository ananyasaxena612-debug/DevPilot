import { useState, useEffect, useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Box,
  Play,
  Square,
  RefreshCw,
  Search,
  AlertTriangle,
  Clock,
  Terminal,
  CheckCircle,
  HelpCircle
} from "lucide-react";
import ServerSelector from "../components/ServerSelector";
import { getDockerMetrics } from "../services/api";

export default function DockerMonitoring() {
  const [searchParams, setSearchParams] = useSearchParams();
  const serverId = searchParams.get("server_id") || "SRV-LOCAL-001";

  const [dockerData, setDockerData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all"); // 'all' | 'running' | 'stopped'
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);

  const fetchDocker = useCallback(async (isManual = false) => {
    if (isManual) setIsRefreshing(true);
    try {
      const data = await getDockerMetrics(serverId);
      setDockerData(data);
      setError("");
      setLastUpdated(new Date());
    } catch (err) {
      setError(
        err.message ||
          "Unable to connect to Docker engine. Ensure Docker Desktop / daemon is active."
      );
    } finally {
      setLoading(false);
      if (isManual) {
        setTimeout(() => setIsRefreshing(false), 400);
      }
    }
  }, [serverId]);

  useEffect(() => {
    let ignore = false;

    const runInitialFetch = async () => {
      try {
        setLoading(true);
        const data = await getDockerMetrics(serverId);
        if (!ignore) {
          setDockerData(data);
          setError("");
          setLastUpdated(new Date());
          setLoading(false);
        }
      } catch (err) {
        if (!ignore) {
          setError(
            err.message ||
              "Unable to connect to Docker engine. Ensure Docker Desktop / daemon is active."
          );
          setLoading(false);
        }
      }
    };

    runInitialFetch();

    if (!autoRefreshEnabled) {
      return () => {
        ignore = true;
      };
    }

    const intervalId = setInterval(() => {
      fetchDocker();
    }, 5000);

    return () => {
      ignore = true;
      clearInterval(intervalId);
    };
  }, [fetchDocker, autoRefreshEnabled, serverId]);

  const containers = useMemo(() => dockerData?.containers || [], [dockerData]);

  const summary = {
    total: dockerData?.total_containers ?? containers.length,
    running: dockerData?.running ?? containers.filter((c) => c.status === "running").length,
    stopped: dockerData?.stopped ?? containers.filter((c) => c.status !== "running").length,
  };

  const filteredContainers = useMemo(() => {
    return containers.filter((c) => {
      const name = (c.name || "").toLowerCase();
      const id = (c.id || "").toLowerCase();
      const image = (c.image || "").toLowerCase();
      const status = (c.status || "").toLowerCase();
      const search = searchTerm.toLowerCase();

      const matchesSearch =
        name.includes(search) || id.includes(search) || image.includes(search);

      if (!matchesSearch) return false;

      if (statusFilter === "running") {
        return status === "running";
      }
      if (statusFilter === "stopped") {
        return status !== "running";
      }
      return true;
    });
  }, [containers, searchTerm, statusFilter]);

  const formatOptionalMetric = (val) => {
    if (val === undefined || val === null) return "N/A";
    const num = Number(val);
    return Number.isFinite(num) ? num.toFixed(1) : "N/A";
  };

  return (
    <div className="page-container">
      {/* Page Header */}
      <div className="page-header">
        <div className="header-left">
          <div className="header-tag">
            <Box size={14} />
            <span>CONTAINER FLEET</span>
          </div>
          <h1 className="page-title">Docker Monitoring</h1>
          <p className="page-description">
            Track Docker containers, runtime states, resource allocations, and health statuses in real time.
          </p>
        </div>

        <div className="header-actions">
          {/* Target Server Dropdown */}
          <ServerSelector
            selectedServerId={serverId}
            onSelectServer={(newId) => setSearchParams({ server_id: newId })}
          />

          <button
            className={`control-pill ${autoRefreshEnabled ? "active-pill" : ""}`}
            onClick={() => setAutoRefreshEnabled(!autoRefreshEnabled)}
            title="Toggle automatic 5-second polling"
          >
            <span className={`pulse-indicator ${autoRefreshEnabled ? "pulse-on" : "pulse-off"}`} />
            <span>Auto-refresh: 5s {autoRefreshEnabled ? "(Active)" : "(Paused)"}</span>
          </button>

          <button
            className="btn btn-secondary btn-sm"
            onClick={() => fetchDocker(true)}
            disabled={isRefreshing}
          >
            <RefreshCw size={14} className={isRefreshing ? "spin-animation" : ""} />
            <span>Refresh Fleet</span>
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="alert-banner alert-warning">
          <div className="alert-content">
            <AlertTriangle size={18} className="alert-icon" />
            <div>
              <strong>Docker Connectivity Note:</strong> {error}
              <div className="alert-subtext">
                Ensure Docker daemon or Docker Desktop is running and reachable via the backend container.
              </div>
            </div>
          </div>
          <button className="btn btn-sm btn-outline-warning" onClick={() => fetchDocker(true)}>
            Retry Connection
          </button>
        </div>
      )}

      {/* Summary Stat Cards */}
      <div className="docker-summary-grid">
        <div
          className={`docker-stat-card ${statusFilter === "all" ? "stat-card-active" : ""}`}
          onClick={() => setStatusFilter("all")}
          role="button"
          tabIndex={0}
        >
          <div className="docker-stat-icon-wrap blue">
            <Box size={24} />
          </div>
          <div className="docker-stat-content">
            <span className="docker-stat-label">Total Containers</span>
            <div className="docker-stat-number">{summary.total}</div>
            <span className="docker-stat-sub">Tracked in local engine</span>
          </div>
        </div>

        <div
          className={`docker-stat-card ${statusFilter === "running" ? "stat-card-active" : ""}`}
          onClick={() => setStatusFilter("running")}
          role="button"
          tabIndex={0}
        >
          <div className="docker-stat-icon-wrap green">
            <Play size={24} className="fill-current" />
          </div>
          <div className="docker-stat-content">
            <span className="docker-stat-label">Running Containers</span>
            <div className="docker-stat-number text-green">{summary.running}</div>
            <span className="docker-stat-sub">Active & processing workloads</span>
          </div>
        </div>

        <div
          className={`docker-stat-card ${statusFilter === "stopped" ? "stat-card-active" : ""}`}
          onClick={() => setStatusFilter("stopped")}
          role="button"
          tabIndex={0}
        >
          <div className="docker-stat-icon-wrap red">
            <Square size={24} className="fill-current" />
          </div>
          <div className="docker-stat-content">
            <span className="docker-stat-label">Stopped Containers</span>
            <div className="docker-stat-number text-red">{summary.stopped}</div>
            <span className="docker-stat-sub">Exited or idle containers</span>
          </div>
        </div>
      </div>

      {/* Container Fleet Table Container */}
      <div className="table-card-container">
        {/* Table Toolbar */}
        <div className="table-toolbar">
          <div className="toolbar-left">
            <h3>Container Fleet Details</h3>
            <span className="count-badge">
              Showing {filteredContainers.length} of {containers.length}
            </span>
          </div>

          <div className="toolbar-right">
            {/* Filter buttons */}
            <div className="filter-buttons-group">
              <button
                className={`filter-btn ${statusFilter === "all" ? "active" : ""}`}
                onClick={() => setStatusFilter("all")}
              >
                All ({summary.total})
              </button>
              <button
                className={`filter-btn ${statusFilter === "running" ? "active" : ""}`}
                onClick={() => setStatusFilter("running")}
              >
                Running ({summary.running})
              </button>
              <button
                className={`filter-btn ${statusFilter === "stopped" ? "active" : ""}`}
                onClick={() => setStatusFilter("stopped")}
              >
                Stopped ({summary.stopped})
              </button>
            </div>

            {/* Search Input */}
            <div className="search-input-wrap">
              <Search size={15} className="search-icon" />
              <input
                type="text"
                placeholder="Search container, ID, or image..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="search-input"
              />
            </div>
          </div>
        </div>

        {/* Table Content */}
        {loading && !dockerData ? (
          <div className="loading-state-card">
            <div className="spinner-large" />
            <h3>Querying Docker Engine...</h3>
            <p>Fetching container list and statistics from the Docker daemon.</p>
          </div>
        ) : filteredContainers.length > 0 ? (
          <div className="table-wrapper">
            <table className="modern-table">
              <thead>
                <tr>
                  <th>Container</th>
                  <th>Image</th>
                  <th>Status</th>
                  <th>CPU Usage</th>
                  <th>Memory</th>
                  <th>Health</th>
                </tr>
              </thead>
              <tbody>
                {filteredContainers.map((container) => {
                  const isRunning = container.status === "running";
                  return (
                    <tr key={container.id || container.name}>
                      {/* Name & ID */}
                      <td>
                        <div className="container-name-cell">
                          <div className="name-with-indicator">
                            <span
                              className={`status-indicator-dot ${isRunning ? "dot-running" : "dot-stopped"}`}
                            />
                            <strong>{container.name}</strong>
                          </div>
                          <span className="container-id-badge">ID: {container.id}</span>
                        </div>
                      </td>

                      {/* Image */}
                      <td>
                        <div className="image-tag-cell" title={container.image}>
                          <code>{container.image}</code>
                        </div>
                      </td>

                      {/* Status */}
                      <td>
                        <span
                          className={`status-pill-badge ${isRunning ? "pill-running" : "pill-stopped"}`}
                        >
                          {isRunning ? (
                            <Play size={10} className="fill-current" />
                          ) : (
                            <Square size={10} className="fill-current" />
                          )}
                          <span>{container.status}</span>
                        </span>
                      </td>

                      {/* CPU Usage */}
                      <td>
                        <span className="metric-cell-val">
                          {formatOptionalMetric(container.cpu_percentage)}
                          {container.cpu_percentage != null ? "%" : ""}
                        </span>
                      </td>

                      {/* Memory */}
                      <td>
                        <span className="metric-cell-val">
                          {formatOptionalMetric(container.memory_usage_mb)}
                          {container.memory_usage_mb != null ? " MB" : ""}
                        </span>
                      </td>

                      {/* Health */}
                      <td>
                        <div className="health-cell">
                          {container.health ? (
                            container.health.toLowerCase().includes("healthy") ? (
                              <span className="health-badge healthy">
                                <CheckCircle size={13} />
                                <span>{container.health}</span>
                              </span>
                            ) : (
                              <span className="health-badge warning">
                                <AlertTriangle size={13} />
                                <span>{container.health}</span>
                              </span>
                            )
                          ) : (
                            <span className="health-badge neutral">
                              <HelpCircle size={13} />
                              <span>Not configured</span>
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state-card">
            <div className="empty-icon-wrap">
              <Box size={36} />
            </div>
            <h4>No Containers Found</h4>
            <p>
              {searchTerm || statusFilter !== "all"
                ? "No containers matched your current search and filter criteria."
                : "No containers were detected on this Docker host."}
            </p>
            {(searchTerm || statusFilter !== "all") && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setSearchTerm("");
                  setStatusFilter("all");
                }}
              >
                Reset Filters
              </button>
            )}
          </div>
        )}
      </div>

      {/* Telemetry Footer */}
      <div className="telemetry-timestamp-bar">
        <div className="timestamp-info">
          <Clock size={14} />
          <span>
            Last polled:{" "}
            <strong>
              {lastUpdated ? lastUpdated.toLocaleTimeString() : "Awaiting response"}
            </strong>
          </span>
        </div>
        <div className="source-info">
          <Terminal size={14} />
          <span>API Endpoint: <code>http://127.0.0.1:5000/monitor/docker</code></span>
        </div>
      </div>
    </div>
  );
}
