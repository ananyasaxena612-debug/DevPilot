import { useState, useEffect, useCallback } from "react";
import {
  Activity,
  Cpu,
  Layers,
  HardDrive,
  RefreshCw,
  AlertTriangle,
  Server,
  Clock,
  SlidersHorizontal
} from "lucide-react";
import MetricCard from "../components/MetricCard";
import { getSystemMetrics } from "../services/api";

export default function SystemMonitoring() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);

  const fetchMetrics = useCallback(async (isManual = false) => {
    if (isManual) setIsRefreshing(true);
    try {
      const data = await getSystemMetrics();
      setMetrics(data);
      setError("");
      setLastUpdated(new Date());
    } catch (err) {
      setError(err.message || "Failed to connect to the system monitoring endpoint.");
    } finally {
      setLoading(false);
      if (isManual) {
        setTimeout(() => setIsRefreshing(false), 400);
      }
    }
  }, []);

  useEffect(() => {
    let ignore = false;

    const runInitialFetch = async () => {
      try {
        const data = await getSystemMetrics();
        if (!ignore) {
          setMetrics(data);
          setError("");
          setLastUpdated(new Date());
          setLoading(false);
        }
      } catch (err) {
        if (!ignore) {
          setError(err.message || "Failed to connect to the system monitoring endpoint.");
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
      fetchMetrics();
    }, 5000);

    return () => {
      ignore = true;
      clearInterval(intervalId);
    };
  }, [fetchMetrics, autoRefreshEnabled]);

  const formatGb = (val) => {
    const num = Number(val);
    return Number.isFinite(num) ? num.toFixed(2) : "0.00";
  };

  return (
    <div className="page-container">
      {/* Page Header */}
      <div className="page-header">
        <div className="header-left">
          <div className="header-tag">
            <Activity size={14} />
            <span>LIVE TELEMETRY</span>
          </div>
          <h1 className="page-title">System Monitoring</h1>
          <p className="page-description">
            Real-time host & container resource utilization metrics polled every 5 seconds.
          </p>
        </div>

        <div className="header-actions">
          {/* Auto Refresh Switch */}
          <button
            className={`control-pill ${autoRefreshEnabled ? "active-pill" : ""}`}
            onClick={() => setAutoRefreshEnabled(!autoRefreshEnabled)}
            title="Toggle automatic 5-second polling"
          >
            <span className={`pulse-indicator ${autoRefreshEnabled ? "pulse-on" : "pulse-off"}`} />
            <span>Auto-refresh: 5s {autoRefreshEnabled ? "(Active)" : "(Paused)"}</span>
          </button>

          {/* Refresh Now Button */}
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => fetchMetrics(true)}
            disabled={isRefreshing}
          >
            <RefreshCw size={14} className={isRefreshing ? "spin-animation" : ""} />
            <span>Refresh Now</span>
          </button>
        </div>
      </div>

      {/* Error Alert if any */}
      {error && (
        <div className="alert-banner alert-warning">
          <div className="alert-content">
            <AlertTriangle size={18} className="alert-icon" />
            <div>
              <strong>Monitoring alert:</strong> {error}
              {metrics && (
                <span className="alert-subtext"> Showing last recorded metrics snapshot.</span>
              )}
            </div>
          </div>
          <button className="btn btn-sm btn-outline-warning" onClick={() => fetchMetrics(true)}>
            Retry Connection
          </button>
        </div>
      )}

      {/* Main Content */}
      {loading && !metrics ? (
        <div className="loading-state-card">
          <div className="spinner-large" />
          <h3>Connecting to System Telemetry...</h3>
          <p>Fetching CPU, memory, and disk utilization from backend.</p>
        </div>
      ) : metrics ? (
        <>
          {/* Top 3 Metric Cards */}
          <div className="metric-cards-grid">
            {/* CPU */}
            <MetricCard
              title="CPU Utilization"
              value={metrics?.cpu?.usage}
              unit="%"
              icon={<Cpu size={26} />}
              badgeText={`${metrics?.cpu?.cores ?? 0} Cores`}
              description={`${metrics?.cpu?.cores ?? 0} logical cores active • Current interval usage`}
            />

            {/* Memory */}
            <MetricCard
              title="Virtual Memory"
              value={metrics?.memory?.usage}
              unit="%"
              icon={<Layers size={26} />}
              badgeText={`${formatGb(metrics?.memory?.used)} GB Used`}
              description={`${formatGb(metrics?.memory?.used)} GB used of ${formatGb(metrics?.memory?.total)} GB total (${formatGb(metrics?.memory?.available)} GB free)`}
            />

            {/* Disk */}
            <MetricCard
              title="Disk Storage"
              value={metrics?.disk?.usage}
              unit="%"
              icon={<HardDrive size={26} />}
              badgeText={`${formatGb(metrics?.disk?.used)} GB Used`}
              description={`${formatGb(metrics?.disk?.used)} GB used of ${formatGb(metrics?.disk?.total)} GB root partition (${formatGb(metrics?.disk?.free)} GB available)`}
            />
          </div>

          {/* Detailed Resource Breakdown Section */}
          <div className="details-section">
            <div className="details-section-header">
              <div className="details-title-row">
                <SlidersHorizontal size={18} className="text-accent" />
                <h3>Detailed Hardware Breakdown</h3>
              </div>
              <span className="scope-tag">
                Scope: <code>{metrics?.scope || "backend_container"}</code>
              </span>
            </div>

            <div className="details-cards-grid">
              {/* CPU Breakdown Card */}
              <div className="detail-breakdown-card">
                <div className="detail-card-head">
                  <div className="detail-card-icon blue">
                    <Cpu size={18} />
                  </div>
                  <div>
                    <h4>CPU Processor</h4>
                    <span>Processing Capacity</span>
                  </div>
                </div>

                <div className="detail-card-stats">
                  <div className="detail-stat-row">
                    <span className="stat-label">Total Logical Cores</span>
                    <span className="stat-value">{metrics?.cpu?.cores ?? "N/A"}</span>
                  </div>
                  <div className="detail-stat-row">
                    <span className="stat-label">Current Load</span>
                    <span className="stat-value">{(metrics?.cpu?.usage ?? 0).toFixed(1)}%</span>
                  </div>
                  <div className="detail-stat-row">
                    <span className="stat-label">Health Status</span>
                    <span className={`status-text ${(metrics?.cpu?.usage ?? 0) >= 85 ? "danger" : (metrics?.cpu?.usage ?? 0) >= 65 ? "warning" : "good"}`}>
                      {(metrics?.cpu?.usage ?? 0) >= 85 ? "High Load" : (metrics?.cpu?.usage ?? 0) >= 65 ? "Moderate Load" : "Healthy"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Memory Breakdown Card */}
              <div className="detail-breakdown-card">
                <div className="detail-card-head">
                  <div className="detail-card-icon green">
                    <Layers size={18} />
                  </div>
                  <div>
                    <h4>RAM Memory</h4>
                    <span>Virtual Memory Allocation</span>
                  </div>
                </div>

                <div className="detail-card-stats">
                  <div className="detail-stat-row">
                    <span className="stat-label">Allocated / Used</span>
                    <span className="stat-value">{formatGb(metrics?.memory?.used)} GB</span>
                  </div>
                  <div className="detail-stat-row">
                    <span className="stat-label">Available / Free</span>
                    <span className="stat-value">{formatGb(metrics?.memory?.available)} GB</span>
                  </div>
                  <div className="detail-stat-row">
                    <span className="stat-label">Total Installed</span>
                    <span className="stat-value">{formatGb(metrics?.memory?.total)} GB</span>
                  </div>
                </div>
              </div>

              {/* Disk Breakdown Card */}
              <div className="detail-breakdown-card">
                <div className="detail-card-head">
                  <div className="detail-card-icon purple">
                    <HardDrive size={18} />
                  </div>
                  <div>
                    <h4>Disk Volume</h4>
                    <span>Root Filesystem Storage</span>
                  </div>
                </div>

                <div className="detail-card-stats">
                  <div className="detail-stat-row">
                    <span className="stat-label">Used Space</span>
                    <span className="stat-value">{formatGb(metrics?.disk?.used)} GB</span>
                  </div>
                  <div className="detail-stat-row">
                    <span className="stat-label">Free Space</span>
                    <span className="stat-value">{formatGb(metrics?.disk?.free)} GB</span>
                  </div>
                  <div className="detail-stat-row">
                    <span className="stat-label">Total Capacity</span>
                    <span className="stat-value">{formatGb(metrics?.disk?.total)} GB</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Footer Metadata */}
          <div className="telemetry-timestamp-bar">
            <div className="timestamp-info">
              <Clock size={14} />
              <span>
                Last updated:{" "}
                <strong>
                  {lastUpdated ? lastUpdated.toLocaleTimeString() : "Waiting for telemetry..."}
                </strong>
              </span>
            </div>
            <div className="source-info">
              <Server size={14} />
              <span>Endpoint: <code>http://127.0.0.1:5000/monitor/system</code></span>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
