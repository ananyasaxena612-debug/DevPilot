"""
DevPilot - Persistent Database Module (SQLite)
Stores historical system metrics, timeline events, and detected incidents.
"""

import os
import sqlite3
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Locate database in backend directory
DB_PATH = os.environ.get(
    "DEVPILOT_DB_PATH",
    str(Path(__file__).resolve().parent / "devpilot_history.db")
)


def get_db_connection():
    """Create a thread-safe connection to SQLite with WAL mode enabled."""
    conn = sqlite3.connect(DB_PATH, timeout=20.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """Initialize database tables and indexes if they do not exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. System Metrics Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                timestamp_epoch REAL NOT NULL,
                cpu_usage REAL NOT NULL,
                cpu_cores INTEGER,
                memory_usage REAL NOT NULL,
                memory_used_gb REAL,
                memory_total_gb REAL,
                memory_available_gb REAL,
                disk_usage REAL NOT NULL,
                disk_used_gb REAL,
                disk_total_gb REAL,
                disk_free_gb REAL
            );
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_epoch 
            ON system_metrics (timestamp_epoch);
        """)

        # 2. Timeline Events Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS timeline_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                timestamp_epoch REAL NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                source TEXT NOT NULL,
                message TEXT NOT NULL,
                metadata TEXT,
                incident_id TEXT,
                fingerprint TEXT UNIQUE
            );
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_epoch 
            ON timeline_events (timestamp_epoch);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_incident 
            ON timeline_events (incident_id);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_type 
            ON timeline_events (event_type);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_severity 
            ON timeline_events (severity);
        """)

        # 3. Incidents Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY,
                incident_number INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                problem_type TEXT,
                severity TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                start_time TEXT NOT NULL,
                start_epoch REAL NOT NULL,
                end_time TEXT,
                end_epoch REAL,
                resolved_at TEXT,
                resolution_notes TEXT,
                trigger_event_id INTEGER,
                ai_investigation TEXT,
                FOREIGN KEY (trigger_event_id) REFERENCES timeline_events (id)
            );
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_incidents_start 
            ON incidents (start_epoch);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_incidents_status 
            ON incidents (status);
        """)

        conn.commit()
    logger.info("Initialized DevPilot SQLite database at %s", DB_PATH)


def compute_event_fingerprint(timestamp, source, message, event_type=""):
    """Generate SHA256 hash to prevent duplicate event inserts."""
    raw = f"{timestamp}|{source}|{event_type}|{message.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------
# Metrics Operations
# ----------------------------------------------------------------------

def insert_system_metric(metric_data):
    """Insert a single system metric sample."""
    now = datetime.now(timezone.utc)
    ts_iso = metric_data.get("timestamp") or now.isoformat()
    ts_epoch = metric_data.get("timestamp_epoch") or now.timestamp()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO system_metrics (
                timestamp, timestamp_epoch,
                cpu_usage, cpu_cores,
                memory_usage, memory_used_gb, memory_total_gb, memory_available_gb,
                disk_usage, disk_used_gb, disk_total_gb, disk_free_gb
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ts_iso,
            ts_epoch,
            float(metric_data.get("cpu_usage", 0.0)),
            int(metric_data.get("cpu_cores", 1)),
            float(metric_data.get("memory_usage", 0.0)),
            float(metric_data.get("memory_used_gb", 0.0)),
            float(metric_data.get("memory_total_gb", 0.0)),
            float(metric_data.get("memory_available_gb", 0.0)),
            float(metric_data.get("disk_usage", 0.0)),
            float(metric_data.get("disk_used_gb", 0.0)),
            float(metric_data.get("disk_total_gb", 0.0)),
            float(metric_data.get("disk_free_gb", 0.0)),
        ))
        conn.commit()
        return cursor.lastrowid


def get_system_metrics_history(start_epoch=None, end_epoch=None, limit=600):
    """Retrieve historical metrics within epoch window, ordered chronologically."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM system_metrics"
        conditions = []
        params = []

        if start_epoch is not None:
            conditions.append("timestamp_epoch >= ?")
            params.append(start_epoch)
        if end_epoch is not None:
            conditions.append("timestamp_epoch <= ?")
            params.append(end_epoch)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        # If no start_epoch specified, fetch the most recent samples
        if start_epoch is None:
            query += " ORDER BY timestamp_epoch DESC"
        else:
            query += " ORDER BY timestamp_epoch ASC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        results = [dict(row) for row in rows]
        if start_epoch is None:
            results.reverse()
        return results


# ----------------------------------------------------------------------
# Timeline Events Operations
# ----------------------------------------------------------------------

def insert_timeline_event(event_data):
    """
    Insert a timeline event.
    Avoids duplicate entries using unique fingerprint.
    """
    now = datetime.now(timezone.utc)
    ts_iso = event_data.get("timestamp") or now.isoformat()
    ts_epoch = event_data.get("timestamp_epoch") or now.timestamp()
    source = event_data.get("source", "system")
    message = event_data.get("message", "")
    event_type = event_data.get("event_type", "log")
    severity = event_data.get("severity", "INFO").upper()

    metadata = event_data.get("metadata")
    if isinstance(metadata, (dict, list)):
        metadata_str = json.dumps(metadata)
    else:
        metadata_str = str(metadata) if metadata else None

    fingerprint = event_data.get("fingerprint") or compute_event_fingerprint(
        ts_iso, source, message, event_type
    )

    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO timeline_events (
                    timestamp, timestamp_epoch, event_type, severity,
                    source, message, metadata, incident_id, fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ts_iso,
                ts_epoch,
                event_type,
                severity,
                source,
                message,
                metadata_str,
                event_data.get("incident_id"),
                fingerprint
            ))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Duplicate fingerprint: return existing ID
            cursor.execute(
                "SELECT id FROM timeline_events WHERE fingerprint = ?",
                (fingerprint,)
            )
            row = cursor.fetchone()
            return row["id"] if row else None


def get_timeline_events(incident_id=None, start_epoch=None, end_epoch=None,
                        event_type=None, severity=None, limit=300, order=None):
    """Retrieve chronological events with optional filters."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM timeline_events"
        conditions = []
        params = []

        if incident_id is not None:
            conditions.append("incident_id = ?")
            params.append(incident_id)
        if start_epoch is not None:
            conditions.append("timestamp_epoch >= ?")
            params.append(start_epoch)
        if end_epoch is not None:
            conditions.append("timestamp_epoch <= ?")
            params.append(end_epoch)
        if event_type and event_type != "all":
            conditions.append("event_type = ?")
            params.append(event_type)
        if severity and severity != "all":
            conditions.append("severity = ?")
            params.append(severity.upper())

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        # If order not explicitly specified:
        # For general timeline without filters, fetch the latest events
        if order is None:
            sort_desc = (incident_id is None and start_epoch is None)
        else:
            sort_desc = (order.upper() == "DESC")

        if sort_desc:
            query += " ORDER BY timestamp_epoch DESC"
        else:
            query += " ORDER BY timestamp_epoch ASC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        events = []
        for r in rows:
            item = dict(r)
            if item.get("metadata"):
                try:
                    item["metadata"] = json.loads(item["metadata"])
                except Exception:
                    pass
            events.append(item)

        if sort_desc:
            events.reverse()

        return events


def link_events_to_incident(incident_id, start_epoch, end_epoch=None):
    """Associate all unlinked events in [start_epoch, end_epoch] with an incident."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if end_epoch is not None:
            cursor.execute("""
                UPDATE timeline_events
                SET incident_id = ?
                WHERE (incident_id IS NULL OR incident_id = '')
                  AND timestamp_epoch >= ?
                  AND timestamp_epoch <= ?
            """, (incident_id, start_epoch, end_epoch))
        else:
            cursor.execute("""
                UPDATE timeline_events
                SET incident_id = ?
                WHERE (incident_id IS NULL OR incident_id = '')
                  AND timestamp_epoch >= ?
            """, (incident_id, start_epoch))
        conn.commit()
        return cursor.rowcount


# ----------------------------------------------------------------------
# Incidents Operations
# ----------------------------------------------------------------------

def create_incident(incident_data):
    """Create a new detected incident."""
    now = datetime.now(timezone.utc)
    ts_iso = incident_data.get("start_time") or now.isoformat()
    ts_epoch = incident_data.get("start_epoch") or now.timestamp()
    inc_id = incident_data.get("id")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM incidents")
        count = cursor.fetchone()["cnt"] + 1

        if not inc_id:
            date_str = now.strftime("%Y%m%d")
            base_id = f"INC-{date_str}-{count:04d}"
            inc_id = base_id
            attempt = 1
            while True:
                cursor.execute("SELECT 1 FROM incidents WHERE id = ?", (inc_id,))
                if not cursor.fetchone():
                    break
                inc_id = f"{base_id}-{attempt}"
                attempt += 1

        cursor.execute("""
            INSERT INTO incidents (
                id, incident_number, title, description,
                problem_type, severity, status,
                start_time, start_epoch, end_time, end_epoch,
                trigger_event_id, ai_investigation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            inc_id,
            count,
            incident_data.get("title", "Infrastructure Anomaly"),
            incident_data.get("description", ""),
            incident_data.get("problem_type", "General DevOps Issue"),
            incident_data.get("severity", "High"),
            incident_data.get("status", "active"),
            ts_iso,
            ts_epoch,
            incident_data.get("end_time"),
            incident_data.get("end_epoch"),
            incident_data.get("trigger_event_id"),
            incident_data.get("ai_investigation")
        ))
        conn.commit()

    # Link events from a 3-minute window before incident up to now
    window_start = ts_epoch - 180.0
    link_events_to_incident(inc_id, window_start, ts_epoch + 60.0)

    logger.info("Created new incident: %s (%s)", inc_id, incident_data.get("title"))
    return inc_id


def get_incidents(status=None, limit=50):
    """List recorded incidents with optional status filter."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM incidents"
        params = []
        if status and status != "all":
            query += " WHERE status = ?"
            params.append(status)

        query += " ORDER BY start_epoch DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        incidents = []
        for r in rows:
            item = dict(r)
            if item.get("ai_investigation"):
                try:
                    item["ai_investigation"] = json.loads(item["ai_investigation"])
                except Exception:
                    pass
            incidents.append(item)
        return incidents


def get_incident_by_id(incident_id):
    """Retrieve full incident details by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        row = cursor.fetchone()
        if not row:
            return None
        item = dict(row)
        if item.get("ai_investigation"):
            try:
                item["ai_investigation"] = json.loads(item["ai_investigation"])
            except Exception:
                pass
        return item


def resolve_incident(incident_id, notes=None):
    """Mark an incident as resolved with timestamp and notes."""
    now = datetime.now(timezone.utc)
    ts_iso = now.isoformat()
    ts_epoch = now.timestamp()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE incidents
            SET status = 'resolved',
                end_time = ?,
                end_epoch = ?,
                resolved_at = ?,
                resolution_notes = ?
            WHERE id = ?
        """, (ts_iso, ts_epoch, ts_iso, notes or "Resolved by engineer.", incident_id))
        conn.commit()
        updated = cursor.rowcount > 0

    if updated:
        # Also create a timeline event documenting resolution
        insert_timeline_event({
            "timestamp": ts_iso,
            "timestamp_epoch": ts_epoch,
            "event_type": "incident",
            "severity": "INFO",
            "source": "devpilot:resolution",
            "message": f"Incident {incident_id} marked as RESOLVED. Notes: {notes or 'No notes provided.'}",
            "incident_id": incident_id
        })
    return updated


def update_incident_ai_investigation(incident_id, investigation_data):
    """Cache AI investigation results on the incident."""
    if isinstance(investigation_data, (dict, list)):
        investigation_str = json.dumps(investigation_data)
    else:
        investigation_str = str(investigation_data)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE incidents
            SET ai_investigation = ?
            WHERE id = ?
        """, (investigation_str, incident_id))
        conn.commit()
        return cursor.rowcount > 0

