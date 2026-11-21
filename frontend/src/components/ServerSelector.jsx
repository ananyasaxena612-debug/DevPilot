import { useState, useEffect } from "react";
import { getServers } from "../services/api";
import { Server, ChevronDown } from "lucide-react";

export default function ServerSelector({ selectedServerId, onSelectServer, allowAll = false }) {
  const [servers, setServers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    async function load() {
      try {
        const res = await getServers();
        if (isMounted && res?.servers) {
          setServers(res.servers);
        }
      } catch (err) {
        console.error("Failed to load servers for selector:", err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    load();
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="server-selector-container">
      <div className="server-selector-label">
        <Server className="server-icon" size={15} />
        <span>Target Server:</span>
      </div>
      <div className="server-select-wrapper">
        <select
          value={selectedServerId || (allowAll ? "all" : (servers[0]?.id || "SRV-LOCAL-001"))}
          onChange={(e) => onSelectServer(e.target.value)}
          className="server-select-dropdown"
          disabled={loading}
          aria-label="Select Monitored Server"
        >
          {allowAll && <option value="all">All Connected Servers</option>}
          {servers.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} ({s.status === "online" ? "● Online" : "○ " + s.status}) - {s.hostname || s.ip_address || s.id}
            </option>
          ))}
          {servers.length === 0 && !loading && (
            <option value="SRV-LOCAL-001">Primary DevPilot Server (Local)</option>
          )}
        </select>
        <ChevronDown className="select-chevron" size={14} />
      </div>
    </div>
  );
}
