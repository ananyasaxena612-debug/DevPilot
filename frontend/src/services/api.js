// DevPilot API Client
export const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_URL) ||
  "http://127.0.0.1:5000";

/**
 * Robust JSON fetcher with clear diagnostics for HTML error pages and network failures
 */
async function safeJsonFetch(url, options = {}) {
  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.headers || {}),
      },
    });
  } catch (err) {
    throw new Error(
      `Unable to connect to DevPilot backend at ${url}. Is the backend running on port 5000? (${err.message})`,
      { cause: err }
    );
  }

  const contentType = response.headers.get("content-type") || "";

  // If server returned HTML (e.g., 404 / 502 / Vite SPA fallback)
  if (!contentType.includes("application/json")) {
    const rawText = await response.text();
    if (rawText.includes("<!doctype") || rawText.includes("<html")) {
      if (response.status === 404) {
        throw new Error(
          `DevPilot API endpoint not found (HTTP 404) at ${url}. Ensure the backend is running the updated server.py.`
        );
      }
      throw new Error(
        `DevPilot backend returned an HTML document (HTTP ${response.status}) instead of JSON for ${url}.`
      );
    }
    if (!response.ok) {
      throw new Error(`Server returned error HTTP ${response.status}: ${rawText.slice(0, 150)}`);
    }
    throw new Error(`Expected JSON but received ${contentType || "plain text"} from ${url}`);
  }

  let data;
  try {
    data = await response.json();
  } catch (err) {
    throw new Error(
      `Malformed JSON response received from ${url} (HTTP ${response.status})`,
      { cause: err }
    );
  }

  if (!response.ok) {
    const errorMsg = data?.error || data?.message || `Request failed with HTTP ${response.status}`;
    throw new Error(errorMsg);
  }

  return data;
}

/**
 * Fetch health & status of backend and AI engine
 */
export async function getBackendStatus() {
  return safeJsonFetch(`${API_BASE_URL}/status`);
}

/**
 * Fetch real-time system monitoring telemetry
 */
export async function getSystemMetrics() {
  const data = await safeJsonFetch(`${API_BASE_URL}/monitor/system`);
  if (!data.cpu || !data.memory || !data.disk) {
    throw new Error("Invalid system metrics format returned from server.");
  }
  return data;
}

/**
 * Fetch Docker containers status and list
 */
export async function getDockerMetrics() {
  const data = await safeJsonFetch(`${API_BASE_URL}/monitor/docker`);
  if (!Array.isArray(data.containers)) {
    throw new Error("Invalid Docker metrics format returned from server.");
  }
  return data;
}

/**
 * Analyze problem description and/or uploaded log file
 * @param {Object} params
 * @param {string} params.problem
 * @param {File|null} params.logFile
 */
export async function analyzeLog({ problem = "", logFile = null }) {
  const formData = new FormData();
  if (problem) {
    formData.append("problem", problem);
  }
  if (logFile) {
    formData.append("log", logFile);
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/analyze`, {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
      body: formData,
    });
  } catch (err) {
    throw new Error(`Failed to contact analysis endpoint: ${err.message}`, { cause: err });
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    const text = await response.text();
    throw new Error(`Analysis server returned non-JSON HTTP ${response.status}: ${text.slice(0, 150)}`);
  }

  const data = await response.json();
  if (!response.ok || !data.success) {
    throw new Error(data.error || `Analysis failed with HTTP ${response.status}`);
  }
  return data;
}

/**
 * Request PDF report generation and trigger download
 * @param {Object} reportData
 */
export async function downloadPdfReport(reportData) {
  const response = await fetch(`${API_BASE_URL}/download-report`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(reportData),
  });

  if (!response.ok) {
    let message = "Unable to generate PDF report.";
    try {
      const err = await response.json();
      message = err.error || message;
    } catch {
      // keep fallback
    }
    throw new Error(message);
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "DevPilot_Troubleshooting_Report.pdf";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

// --------------------------------------------------
// INCIDENT TIME MACHINE API FUNCTIONS
// --------------------------------------------------

/**
 * List all incidents, optionally filtered by status
 * @param {string|null} status - "active" | "resolved" | null for all
 * @param {number} limit
 */
export async function getIncidents(status = null, limit = 50) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set("status", status);
  return safeJsonFetch(`${API_BASE_URL}/api/incidents?${params}`);
}

/**
 * Get a single incident by ID
 * @param {string} id
 */
export async function getIncidentById(id) {
  return safeJsonFetch(`${API_BASE_URL}/api/incidents/${id}`);
}

/**
 * Resolve an incident
 * @param {string} id
 * @param {string} notes
 */
export async function resolveIncident(id, notes = "Marked resolved by operator.") {
  return safeJsonFetch(`${API_BASE_URL}/api/incidents/${id}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes }),
  });
}

/**
 * Get timeline events for a specific incident
 * @param {string} id
 * @param {Object} filters - { event_type, severity, limit }
 */
export async function getIncidentTimeline(id, filters = {}) {
  const params = new URLSearchParams({ limit: String(filters.limit || 200) });
  if (filters.event_type) params.set("event_type", filters.event_type);
  if (filters.severity) params.set("severity", filters.severity);
  return safeJsonFetch(`${API_BASE_URL}/api/incidents/${id}/timeline?${params}`);
}

/**
 * Get historical metrics for a specific incident window
 * @param {string} id
 * @param {number} limit
 * @param {number} windowMinutes
 */
export async function getIncidentMetrics(id, limit = 500, windowMinutes = 5) {
  const params = new URLSearchParams({
    limit: String(limit),
    window: String(windowMinutes),
  });
  return safeJsonFetch(`${API_BASE_URL}/api/incidents/${id}/metrics?${params}`);
}

/**
 * Trigger AI investigation for an incident
 * @param {string} id
 */
export async function investigateIncident(id) {
  return safeJsonFetch(`${API_BASE_URL}/api/incidents/${id}/investigate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Simulate an incident for demo/testing purposes
 * @param {string} scenario - "database_outage" | "cpu_surge" | "container_crash"
 */
export async function simulateIncident(scenario = "database_outage") {
  return safeJsonFetch(`${API_BASE_URL}/api/incidents/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario }),
  });
}

/**
 * Fetch global historical metrics with optional time range
 * @param {string} range - "15m" | "1h" | "6h" | "24h"
 * @param {number} limit
 */
export async function getMetricsHistory(range = "1h", limit = 500) {
  const params = new URLSearchParams({ range, limit: String(limit) });
  return safeJsonFetch(`${API_BASE_URL}/api/metrics/history?${params}`);
}

/**
 * Fetch the global timeline events
 * @param {Object} filters - { event_type, severity, limit }
 */
export async function getGlobalTimeline(filters = {}) {
  const params = new URLSearchParams({ limit: String(filters.limit || 200) });
  if (filters.event_type) params.set("event_type", filters.event_type);
  if (filters.severity) params.set("severity", filters.severity);
  return safeJsonFetch(`${API_BASE_URL}/api/timeline?${params}`);
}

/**
 * Fetch collector stats (uptime, counts, last collection time)
 */
export async function getCollectorStats() {
  return safeJsonFetch(`${API_BASE_URL}/api/collector/stats`);
}
