import { useState, useEffect, useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Clock,
  Activity,
  RefreshCw,
  AlertTriangle,
  PlayCircle,
  CheckCircle2,
  Bot,
  Zap,
  Filter,
  Target,
  Server
} from "lucide-react";
import ServerSelector from "../components/ServerSelector";
import {
  getIncidents,
  getIncidentById,
  getIncidentTimeline,
  getIncidentMetrics,
  investigateIncident,
  resolveIncident,
  simulateIncident
} from "../services/api";

function formatEpoch(val) {
  if (!val) return "—";
  try {
    if (typeof val === "number" || (!isNaN(Number(val)) && !isNaN(parseFloat(val)))) {
      return new Date(Number(val) * 1000).toLocaleString();
    }
    const d = new Date(val);
    return isNaN(d.getTime()) ? String(val) : d.toLocaleString();
  } catch {
    return String(val);
  }
}

function formatShortEpoch(val) {
  if (!val) return "—";
  try {
    if (typeof val === "number" || (!isNaN(Number(val)) && !isNaN(parseFloat(val)))) {
      return new Date(Number(val) * 1000).toLocaleTimeString();
    }
    const d = new Date(val);
    return isNaN(d.getTime()) ? String(val) : d.toLocaleTimeString();
  } catch {
    return String(val);
  }
}

function severityClass(sev) {
  const s = (sev || "").toUpperCase();
  if (s === "CRITICAL" || s === "ERROR") return "sev-critical";
  if (s === "HIGH") return "sev-high";
  if (s === "MEDIUM" || s === "WARNING") return "sev-medium";
  if (s === "LOW" || s === "INFO") return "sev-low";
  return "sev-unknown";
}

function safeArray(arr) {
  if (Array.isArray(arr)) return arr;
  if (typeof arr === "string" && arr.trim()) return [arr.trim()];
  return [];
}

function MetricsChart({ metrics }) {
  const validMetrics = useMemo(() => {
    return (metrics || []).filter(
      (m) => m && typeof m.timestamp_epoch === "number" && !isNaN(m.timestamp_epoch)
    );
  }, [metrics]);

  if (!validMetrics || validMetrics.length === 0) {
    return (
      <div className="empty-state-card">
        <div className="empty-icon-wrap">
          <Activity size={32} />
        </div>
        <h4>No Metric Data Available</h4>
        <p>
          No CPU, RAM, or disk samples were recorded for this incident window.
        </p>
      </div>
    );
  }

  const width = 760;
  const height = 240;
  const pad = 44;
  const epochs = validMetrics.map((m) => m.timestamp_epoch);
  const minE = Math.min(...epochs);
  const maxE = Math.max(...epochs);
  const range = maxE > minE ? maxE - minE : 60;

  const toX = (e) => {
    if (maxE === minE) return width / 2;
    return pad + ((e - minE) / range) * (width - pad * 2);
  };

  const toY = (v) => {
    const clamped = Math.max(0, Math.min(100, Number(v) || 0));
    return height - pad - (clamped / 100) * (height - pad * 2);
  };

  const cpuPts = validMetrics.map((m) => `${toX(m.timestamp_epoch)},${toY(m.cpu_usage)}`).join(" ");
  const ramPts = validMetrics.map((m) => `${toX(m.timestamp_epoch)},${toY(m.memory_usage)}`).join(" ");
  const diskPts = validMetrics.map((m) => `${toX(m.timestamp_epoch)},${toY(m.disk_usage)}`).join(" ");

  const yTicks = [0, 25, 50, 75, 100];

  return (
    <div className="incident-chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} className="incident-chart" role="img" aria-label="Historical metrics chart">
        {yTicks.map((t) => (
          <g key={t}>
            <line
              x1={pad}
              y1={toY(t)}
              x2={width - pad}
              y2={toY(t)}
              className="chart-grid-line"
            />
            <text x={pad - 8} y={toY(t) + 4} className="chart-axis-label" textAnchor="end">
              {t}%
            </text>
          </g>
        ))}

        <polyline points={cpuPts} className="chart-line chart-line-cpu" fill="none" />
        <polyline points={ramPts} className="chart-line chart-line-ram" fill="none" />
        <polyline points={diskPts} className="chart-line chart-line-disk" fill="none" />

        {validMetrics.map((m, i) => (
          <circle
            key={`cpu-${i}`}
            cx={toX(m.timestamp_epoch)}
            cy={toY(m.cpu_usage)}
            r={2.5}
            className="chart-dot chart-dot-cpu"
          />
        ))}

        <text x={pad} y={height - 10} className="chart-axis-label" textAnchor="start">
          {formatShortEpoch(minE)}
        </text>
        <text x={width / 2} y={height - 10} className="chart-axis-label" textAnchor="middle">
          {formatShortEpoch((minE + maxE) / 2)}
        </text>
        <text x={width - pad} y={height - 10} className="chart-axis-label" textAnchor="end">
          {formatShortEpoch(maxE)}
        </text>
      </svg>

      <div className="chart-legend">
        <span className="legend-item">
          <span className="legend-swatch legend-cpu" /> CPU
        </span>
        <span className="legend-item">
          <span className="legend-swatch legend-ram" /> RAM
        </span>
        <span className="legend-item">
          <span className="legend-swatch legend-disk" /> Disk
        </span>
      </div>
    </div>
  );
}

export default function IncidentTimeMachine() {
  const [searchParams, setSearchParams] = useSearchParams();
  const serverIdParam = searchParams.get("server_id");
  const [selectedServerId, setSelectedServerId] = useState(serverIdParam || "all");

  const [incidents, setIncidents] = useState([]);
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedId, setSelectedId] = useState(null);
  const [incident, setIncident] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [metrics, setMetrics] = useState([]);
  const [metricWindow, setMetricWindow] = useState(15);
  const [investigation, setInvestigation] = useState(null);

  const [loadingIncidents, setLoadingIncidents] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [investigating, setInvestigating] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [simulating, setSimulating] = useState(false);

  const [error, setError] = useState("");
  const [timelineFilters, setTimelineFilters] = useState({ event_type: "", severity: "" });

  // Sync state if url search params change
  useEffect(() => {
    if (serverIdParam && serverIdParam !== selectedServerId) {
      setSelectedServerId(serverIdParam);
    }
  }, [serverIdParam]);

  // Load incidents list
  const refreshIncidents = useCallback(async (filterValue = statusFilter, srvId = selectedServerId) => {
    setLoadingIncidents(true);
    setError("");
    try {
      const targetServer = srvId === "all" ? null : srvId;
      const data = await getIncidents(
        filterValue === "all" ? null : filterValue,
        100,
        targetServer
      );
      const list = data.incidents || [];
      setIncidents(list);
      setSelectedId((curr) => {
        if (!curr && list.length > 0) return list[0].id;
        if (curr && !list.some((item) => item.id === curr)) {
          return list.length > 0 ? list[0].id : null;
        }
        return curr;
      });
    } catch (err) {
      setError(err.message || "Failed to load incidents.");
    } finally {
      setLoadingIncidents(false);
    }
  }, [statusFilter, selectedServerId]);

  // Initial and on-filter-change incident loading
  useEffect(() => {
    let ignore = false;

    const runFetch = async () => {
      try {
        const targetServer = selectedServerId === "all" ? null : selectedServerId;
        const data = await getIncidents(
          statusFilter === "all" ? null : statusFilter,
          100,
          targetServer
        );
        if (!ignore) {
          const list = data.incidents || [];
          setIncidents(list);
          setSelectedId((curr) => {
            if (!curr && list.length > 0) return list[0].id;
            if (curr && !list.some((item) => item.id === curr)) {
              return list.length > 0 ? list[0].id : null;
            }
            return curr;
          });
          setError("");
          setLoadingIncidents(false);
        }
      } catch (err) {
        if (!ignore) {
          setError(err.message || "Failed to load incidents.");
          setLoadingIncidents(false);
        }
      }
    };

    runFetch();
    return () => {
      ignore = true;
    };
  }, [statusFilter]);

  // Load selected incident details, timeline & metrics
  useEffect(() => {
    let ignore = false;

    const runFetchDetail = async () => {
      if (!selectedId) {
        if (!ignore) {
          setIncident(null);
          setTimeline([]);
          setMetrics([]);
          setInvestigation(null);
        }
        return;
      }
      setLoadingDetail(true);
      try {
        const detailRes = await getIncidentById(selectedId);
        const inc = detailRes.incident || null;
        if (!ignore) {
          setIncident(inc);
          let inv = inc && inc.ai_investigation ? inc.ai_investigation : null;
          if (typeof inv === "string") {
            try {
              inv = JSON.parse(inv);
            } catch {
              // keep as is
            }
          }
          setInvestigation(inv);
        }

        const timelineRes = await getIncidentTimeline(selectedId, {
          event_type: timelineFilters.event_type || undefined,
          severity: timelineFilters.severity || undefined,
          limit: 300
        });
        if (!ignore) {
          setTimeline(timelineRes.events || []);
        }

        const metricsRes = await getIncidentMetrics(selectedId, 1000, metricWindow);
        if (!ignore) {
          setMetrics(metricsRes.metrics || []);
          setError("");
          setLoadingDetail(false);
        }
      } catch (err) {
        if (!ignore) {
          setError(err.message || "Failed to load incident details.");
          setLoadingDetail(false);
        }
      }
    };

    runFetchDetail();
    return () => {
      ignore = true;
    };
  }, [selectedId, metricWindow, timelineFilters]);

  const handleInvestigate = async () => {
    if (!selectedId) return;
    setInvestigating(true);
    setError("");
    try {
      const res = await investigateIncident(selectedId);
      let inv = res.investigation || null;
      if (typeof inv === "string") {
        try {
          inv = JSON.parse(inv);
        } catch {
          // ignore
        }
      }
      setInvestigation(inv);
      const detailRes = await getIncidentById(selectedId);
      setIncident(detailRes.incident || incident);
    } catch (err) {
      setError(err.message || "AI investigation failed.");
    } finally {
      setInvestigating(false);
    }
  };

  const handleResolve = async () => {
    if (!selectedId) return;
    setResolving(true);
    setError("");
    try {
      const res = await resolveIncident(selectedId, "Marked resolved by operator.");
      setIncident(res.incident || incident);
      await refreshIncidents(statusFilter);
    } catch (err) {
      setError(err.message || "Failed to resolve incident.");
    } finally {
      setResolving(false);
    }
  };

  const handleSimulate = async (scenario) => {
    setSimulating(true);
    setError("");
    try {
      const res = await simulateIncident(scenario);
      await refreshIncidents(statusFilter);
      if (res.incident_id) {
        setSelectedId(res.incident_id);
      }
    } catch (err) {
      setError(err.message || "Simulation failed.");
    } finally {
      setSimulating(false);
    }
  };

  const sortedTimeline = useMemo(() => {
    return [...timeline].sort((a, b) => (a.timestamp_epoch || 0) - (b.timestamp_epoch || 0));
  }, [timeline]);

  const metricStats = useMemo(() => {
    const cpu = metrics.map((m) => m.cpu_usage).filter((v) => Number.isFinite(v));
    const ram = metrics.map((m) => m.memory_usage).filter((v) => Number.isFinite(v));
    const disk = metrics.map((m) => m.disk_usage).filter((v) => Number.isFinite(v));
    const avg = (arr) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null);
    return {
      samples: metrics.length,
      peakCpu: cpu.length ? Math.max(...cpu) : null,
      avgCpu: cpu.length ? avg(cpu) : null,
      peakRam: ram.length ? Math.max(...ram) : null,
      avgRam: ram.length ? avg(ram) : null,
      peakDisk: disk.length ? Math.max(...disk) : null
    };
  }, [metrics]);

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="header-left">
          <div className="header-tag">
            <Clock size={14} />
            <span>INCIDENT TIME MACHINE</span>
          </div>
          <h1 className="page-title">Incident Time Machine</h1>
          <p className="page-description">
            Reconstruct incidents chronologically using collected logs, metrics, Docker events, and AI investigation.
          </p>
        </div>

        <div className="header-actions">
          {/* Server Selector Filter */}
          <ServerSelector
            allowAll={true}
            selectedServerId={selectedServerId}
            onSelectServer={(newId) => {
              setSelectedServerId(newId);
              setSearchParams(newId === "all" ? {} : { server_id: newId });
              refreshIncidents(statusFilter, newId);
            }}
          />

          <div className="control-pill">
            <Filter size={14} />
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                refreshIncidents(e.target.value, selectedServerId);
              }}
              className="incident-select"
            >
              <option value="all">All Statuses</option>
              <option value="active">Active</option>
              <option value="resolved">Resolved</option>
            </select>
          </div>

          <button
            className="btn btn-secondary btn-sm"
            onClick={() => refreshIncidents(statusFilter, selectedServerId)}
            disabled={loadingIncidents}
          >
            <RefreshCw size={14} className={loadingIncidents ? "spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="result-section-card" style={{ borderColor: "var(--status-red)" }}>
          <div className="result-card-heading">
            <AlertTriangle size={18} className="heading-icon" style={{ color: "var(--status-red)" }} />
            <h3>Error</h3>
          </div>
          <p style={{ color: "var(--text-secondary)" }}>{error}</p>
        </div>
      )}

      <div className="incident-layout">
        <aside className="incident-list-card">
          <div className="result-card-heading">
            <Target size={18} className="heading-icon" />
            <h3>Incident History</h3>
          </div>

          {loadingIncidents ? (
            <div className="loading-state-card">
              <RefreshCw size={24} className="spin" />
              <p>Loading incidents…</p>
            </div>
          ) : incidents.length === 0 ? (
            <div className="empty-state-card">
              <div className="empty-icon-wrap">
                <Clock size={32} />
              </div>
              <h4>No Incidents Recorded</h4>
              <p>
                The collector is running. Incidents appear when thresholds are exceeded or can be generated for testing.
              </p>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center" }}>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleSimulate("database_outage")}
                  disabled={simulating}
                >
                  <PlayCircle size={14} /> Simulate DB Outage
                </button>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleSimulate("cpu_surge")}
                  disabled={simulating}
                >
                  <PlayCircle size={14} /> Simulate CPU Surge
                </button>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleSimulate("container_crash")}
                  disabled={simulating}
                >
                  <PlayCircle size={14} /> Simulate Container Crash
                </button>
              </div>
            </div>
          ) : (
            <div className="incident-list">
              {incidents.map((inc) => (
                <button
                  key={inc.id}
                  className={`incident-list-item ${selectedId === inc.id ? "active" : ""}`}
                  onClick={() => setSelectedId(inc.id)}
                >
                  <div className="incident-list-head">
                    <span className={`severity-badge ${severityClass(inc.severity)}`}>{inc.severity}</span>
                    <span className="incident-status-pill">{inc.status}</span>
                  </div>
                  <div className="incident-list-title">{inc.title}</div>
                  <div className="incident-list-meta">
                    <span>{inc.id}</span>
                    {inc.server_id && <span className="tag" style={{ fontSize: "0.7rem", padding: "1px 6px" }}>{inc.server_id}</span>}
                    <span>{formatEpoch(inc.start_epoch)}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </aside>

        <section className="incident-detail">
          {!selectedId ? (
            <div className="empty-state-card">
              <div className="empty-icon-wrap">
                <Target size={32} />
              </div>
              <h4>Select an Incident</h4>
              <p>Choose an incident from the history list to inspect its timeline and metrics.</p>
            </div>
          ) : loadingDetail ? (
            <div className="loading-state-card">
              <RefreshCw size={28} className="spin" />
              <p>Loading incident details…</p>
            </div>
          ) : !incident ? (
            <div className="empty-state-card">
              <h4>Incident Not Found</h4>
              <p>The selected incident could not be loaded.</p>
            </div>
          ) : (
            <>
              <div className="result-section-card">
                <div className="result-card-heading">
                  <Zap size={18} className="heading-icon" />
                  <h3>{incident.title}</h3>
                </div>
                <div className="incident-meta-grid">
                  <div className="incident-meta-item">
                    <span className="meta-label">Incident ID</span>
                    <span className="meta-value">{incident.id}</span>
                  </div>
                  <div className="incident-meta-item">
                    <span className="meta-label">Server</span>
                    <span className="meta-value" style={{ fontWeight: 600 }}>{incident.server_id || "SRV-LOCAL-001"}</span>
                  </div>
                  <div className="incident-meta-item">
                    <span className="meta-label">Status</span>
                    <span className={`severity-badge ${incident.status === "resolved" ? "sev-low" : "sev-high"}`}>
                      {incident.status}
                    </span>
                  </div>
                  <div className="incident-meta-item">
                    <span className="meta-label">Severity</span>
                    <span className={`severity-badge ${severityClass(incident.severity)}`}>{incident.severity}</span>
                  </div>
                  <div className="incident-meta-item">
                    <span className="meta-label">Problem Type</span>
                    <span className="meta-value">{incident.problem_type || "—"}</span>
                  </div>
                  <div className="incident-meta-item">
                    <span className="meta-label">Start Time</span>
                    <span className="meta-value">{formatEpoch(incident.start_epoch)}</span>
                  </div>
                  <div className="incident-meta-item">
                    <span className="meta-label">End / Resolved Time</span>
                    <span className="meta-value">{incident.end_epoch ? formatEpoch(incident.end_epoch) : "Still active"}</span>
                  </div>
                </div>

                {incident.description && (
                  <p className="incident-description">{incident.description}</p>
                )}

                <div className="incident-actions">
                  {incident.status !== "resolved" && (
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={handleResolve}
                      disabled={resolving}
                    >
                      <CheckCircle2 size={14} /> {resolving ? "Resolving…" : "Mark Resolved"}
                    </button>
                  )}
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={handleInvestigate}
                    disabled={investigating}
                  >
                    <Bot size={14} /> {investigating ? "Investigating…" : "Run AI Investigation"}
                  </button>
                </div>
              </div>

              <div className="result-section-card">
                <div className="result-card-heading">
                  <Clock size={18} className="heading-icon" />
                  <h3>Chronological Timeline</h3>
                </div>

                <div className="timeline-filters">
                  <select
                    value={timelineFilters.event_type}
                    onChange={(e) =>
                      setTimelineFilters((f) => ({ ...f, event_type: e.target.value }))
                    }
                    className="incident-select"
                  >
                    <option value="">All Event Types</option>
                    <option value="log">Log</option>
                    <option value="docker">Docker</option>
                    <option value="system_alert">System Alert</option>
                    <option value="incident">Incident</option>
                  </select>
                  <select
                    value={timelineFilters.severity}
                    onChange={(e) =>
                      setTimelineFilters((f) => ({ ...f, severity: e.target.value }))
                    }
                    className="incident-select"
                  >
                    <option value="">All Severities</option>
                    <option value="INFO">INFO</option>
                    <option value="WARNING">WARNING</option>
                    <option value="ERROR">ERROR</option>
                    <option value="CRITICAL">CRITICAL</option>
                  </select>
                </div>

                {sortedTimeline.length === 0 ? (
                  <div className="empty-state-card">
                    <h4>No Timeline Events</h4>
                    <p>No events were recorded for this incident window.</p>
                  </div>
                ) : (
                  <div className="incident-timeline">
                    {sortedTimeline.map((ev, idx) => (
                      <div key={ev.id || idx} className="incident-timeline-item">
                        <div className="timeline-marker-col">
                          <span className={`timeline-dot ${severityClass(ev.severity)}`} />
                          {idx < sortedTimeline.length - 1 && <span className="timeline-line" />}
                        </div>
                        <div className="timeline-event-card">
                          <div className="timeline-event-head">
                            <span className={`severity-badge ${severityClass(ev.severity)}`}>{ev.severity}</span>
                            <span className="event-type-badge">{ev.event_type}</span>
                            <span className="event-source">{ev.source}</span>
                            <span className="event-time">{formatEpoch(ev.timestamp_epoch)}</span>
                          </div>
                          <p className="event-message">{ev.message}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="result-section-card">
                <div className="result-card-heading">
                  <Activity size={18} className="heading-icon" />
                  <h3>Historical Metrics</h3>
                </div>

                <div className="timeline-filters">
                  <span className="meta-label">Time Range</span>
                  <select
                    value={metricWindow}
                    onChange={(e) => setMetricWindow(Number(e.target.value))}
                    className="incident-select"
                  >
                    <option value={5}>±5 minutes</option>
                    <option value={15}>±15 minutes</option>
                    <option value={30}>±30 minutes</option>
                    <option value={60}>±1 hour</option>
                  </select>
                </div>

                <div className="metric-stats-row">
                  <div className="metric-stat">
                    <span className="meta-label">Samples</span>
                    <span className="meta-value">{metricStats.samples}</span>
                  </div>
                  <div className="metric-stat">
                    <span className="meta-label">Peak CPU</span>
                    <span className="meta-value">{metricStats.peakCpu != null ? `${metricStats.peakCpu.toFixed(1)}%` : "—"}</span>
                  </div>
                  <div className="metric-stat">
                    <span className="meta-label">Avg CPU</span>
                    <span className="meta-value">{metricStats.avgCpu != null ? `${metricStats.avgCpu.toFixed(1)}%` : "—"}</span>
                  </div>
                  <div className="metric-stat">
                    <span className="meta-label">Peak RAM</span>
                    <span className="meta-value">{metricStats.peakRam != null ? `${metricStats.peakRam.toFixed(1)}%` : "—"}</span>
                  </div>
                  <div className="metric-stat">
                    <span className="meta-label">Avg RAM</span>
                    <span className="meta-value">{metricStats.avgRam != null ? `${metricStats.avgRam.toFixed(1)}%` : "—"}</span>
                  </div>
                  <div className="metric-stat">
                    <span className="meta-label">Peak Disk</span>
                    <span className="meta-value">{metricStats.peakDisk != null ? `${metricStats.peakDisk.toFixed(1)}%` : "—"}</span>
                  </div>
                </div>

                <MetricsChart metrics={metrics} />

                {metrics.length === 0 && (
                  <p className="missing-data-note">
                    No metric samples were recorded for this incident window. Data may not have been collected yet.
                  </p>
                )}
              </div>

              <div className="result-section-card">
                <div className="result-card-heading">
                  <Bot size={18} className="heading-icon" />
                  <h3>AI Incident Investigation</h3>
                </div>

                {!investigation ? (
                  <div className="empty-state-card">
                    <div className="empty-icon-wrap">
                      <Bot size={32} />
                    </div>
                    <h4>No Investigation Yet</h4>
                    <p>Run an AI investigation to get a summary, possible root causes, and troubleshooting steps based on collected data.</p>
                  </div>
                ) : (
                  <div className="investigation-content">
                    <div className="diagnosis-box">
                      {investigation.incident_summary || "No summary available."}
                    </div>

                    <div className="investigation-grid">
                      <div className="investigation-block">
                        <h4>Observed Facts</h4>
                        <ul className="styled-ordered-list">
                          {safeArray(investigation.observed_facts).map((f, i) => (
                            <li key={i} className="list-item-card">
                              <span className="step-counter">{i + 1}</span>
                              <p>{f}</p>
                            </li>
                          ))}
                          {safeArray(investigation.observed_facts).length === 0 && (
                            <li className="list-item-card"><p>No observed facts recorded.</p></li>
                          )}
                        </ul>
                      </div>

                      <div className="investigation-block">
                        <h4>Possible Root Causes</h4>
                        <ul className="styled-ordered-list">
                          {safeArray(investigation.possible_root_causes).map((c, i) => (
                            <li key={i} className="list-item-card">
                              <span className="step-counter">{i + 1}</span>
                              <p>{c}</p>
                            </li>
                          ))}
                          {safeArray(investigation.possible_root_causes).length === 0 && (
                            <li className="list-item-card"><p>Insufficient evidence to determine root cause.</p></li>
                          )}
                        </ul>
                      </div>
                    </div>

                    <div className="investigation-block">
                      <h4>Relevant Metric Anomalies</h4>
                      <ul className="styled-ordered-list">
                        {safeArray(investigation.relevant_metric_anomalies).map((a, i) => (
                          <li key={i} className="list-item-card">
                            <span className="step-counter green-counter">{i + 1}</span>
                            <p>{a}</p>
                          </li>
                        ))}
                        {safeArray(investigation.relevant_metric_anomalies).length === 0 && (
                          <li className="list-item-card"><p>No metric anomalies recorded.</p></li>
                        )}
                      </ul>
                    </div>

                    <div className="investigation-block">
                      <h4>Supporting Evidence</h4>
                      <ul className="styled-ordered-list">
                        {safeArray(investigation.supporting_evidence).map((e, i) => (
                          <li key={i} className="list-item-card">
                            <span className="step-counter">{i + 1}</span>
                            <p>{e}</p>
                          </li>
                        ))}
                        {safeArray(investigation.supporting_evidence).length === 0 && (
                          <li className="list-item-card"><p>No supporting evidence recorded.</p></li>
                        )}
                      </ul>
                    </div>

                    <div className="investigation-block">
                      <h4>Recommended Troubleshooting Steps</h4>
                      <ul className="styled-ordered-list">
                        {safeArray(investigation.recommended_troubleshooting_steps).map((s, i) => (
                          <li key={i} className="list-item-card">
                            <span className="step-counter">{i + 1}</span>
                            <p>{s}</p>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="investigation-block">
                      <h4>Preventive Suggestions</h4>
                      <ul className="styled-ordered-list">
                        {safeArray(investigation.preventive_suggestions).map((p, i) => (
                          <li key={i} className="list-item-card">
                            <span className="step-counter green-counter">{i + 1}</span>
                            <p>{p}</p>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="investigation-footer">
                      <span className="meta-label">AI Engine Status:</span>
                      <span className="meta-value">{investigation.ai_engine_status || "unknown"}</span>
                      <span className="meta-label">Confidence:</span>
                      <span className="meta-value">{investigation.confidence_level || "—"}</span>
                      <span className="meta-label">Investigated At:</span>
                      <span className="meta-value">
                        {formatEpoch(investigation.investigated_at)}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
