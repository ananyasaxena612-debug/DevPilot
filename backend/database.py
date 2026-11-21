"""
DevPilot - Persistent Database Module (SQLite)
Stores historical system metrics, timeline events, detected incidents,
multi-tenant users, connected servers, and secure agent credentials.
"""

import os
import sqlite3
import hashlib
import hmac
import secrets
import json
import base64
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Locate database in backend directory
DB_PATH = os.environ.get(
    "DEVPILOT_DB_PATH",
    str(Path(__file__).resolve().parent / "devpilot_history.db")
)

SECRET_KEY = os.environ.get("DEVPILOT_SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError("DEVPILOT_SECRET_KEY environment variable is required")



def get_db_connection():
    """Create a thread-safe connection to SQLite with WAL mode enabled."""
    conn = sqlite3.connect(DB_PATH, timeout=20.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _get_table_columns(cursor, table_name):
    """Retrieve existing column names for an existing table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row["name"] for row in cursor.fetchall()]


def init_db():
    """
    Initialize database tables and indexes, running idempotent
    migrations to preserve existing historical data without data loss.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # ------------------------------------------------------------------
        # 1. Users Table
        # ------------------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'admin',
                created_at TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);")

        # ------------------------------------------------------------------
        # 2. Servers Table
        # ------------------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS servers (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                hostname TEXT,
                ip_address TEXT,
                os_info TEXT DEFAULT 'Linux',
                status TEXT NOT NULL DEFAULT 'pending',
                agent_version TEXT,
                docker_enabled INTEGER DEFAULT 0,
                last_heartbeat_at TEXT,
                last_heartbeat_epoch REAL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_servers_user ON servers (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_servers_status ON servers (status);")

        # ------------------------------------------------------------------
        # 3. Agent Enrollment Tokens Table (Short-lived, single-use)
        # ------------------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS enrollment_tokens (
                id TEXT PRIMARY KEY,
                server_id TEXT NOT NULL,
                token_hash TEXT UNIQUE NOT NULL,
                expires_at_epoch REAL NOT NULL,
                is_used INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (server_id) REFERENCES servers (id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tokens_hash ON enrollment_tokens (token_hash);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tokens_server ON enrollment_tokens (server_id);")

        # ------------------------------------------------------------------
        # 4. Agent Credentials Table (Persistent revocable API keys)
        # ------------------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_credentials (
                id TEXT PRIMARY KEY,
                server_id TEXT UNIQUE NOT NULL,
                api_key_hash TEXT UNIQUE NOT NULL,
                is_revoked INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                last_used_at TEXT,
                FOREIGN KEY (server_id) REFERENCES servers (id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_key_hash ON agent_credentials (api_key_hash);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_key_server ON agent_credentials (server_id);")

        # ------------------------------------------------------------------
        # 5. System Metrics Table
        # ------------------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT DEFAULT 'SRV-LOCAL-001',
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

        # Migration: Ensure server_id column exists in system_metrics
        metric_cols = _get_table_columns(cursor, "system_metrics")
        if "server_id" not in metric_cols:
            cursor.execute("ALTER TABLE system_metrics ADD COLUMN server_id TEXT DEFAULT 'SRV-LOCAL-001';")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_epoch ON system_metrics (timestamp_epoch);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_server ON system_metrics (server_id);")

        # ------------------------------------------------------------------
        # 6. Timeline Events Table
        # ------------------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS timeline_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT DEFAULT 'SRV-LOCAL-001',
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

        # Migration: Ensure server_id column exists in timeline_events
        event_cols = _get_table_columns(cursor, "timeline_events")
        if "server_id" not in event_cols:
            cursor.execute("ALTER TABLE timeline_events ADD COLUMN server_id TEXT DEFAULT 'SRV-LOCAL-001';")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_epoch ON timeline_events (timestamp_epoch);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_incident ON timeline_events (incident_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_server ON timeline_events (server_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON timeline_events (event_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_severity ON timeline_events (severity);")

        # ------------------------------------------------------------------
        # 7. Incidents Table
        # ------------------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY,
                incident_number INTEGER,
                server_id TEXT DEFAULT 'SRV-LOCAL-001',
                user_id TEXT DEFAULT 'USR-ADMIN-001',
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

        # Migration: Ensure server_id and user_id columns exist in incidents
        inc_cols = _get_table_columns(cursor, "incidents")
        if "server_id" not in inc_cols:
            cursor.execute("ALTER TABLE incidents ADD COLUMN server_id TEXT DEFAULT 'SRV-LOCAL-001';")
        if "user_id" not in inc_cols:
            cursor.execute("ALTER TABLE incidents ADD COLUMN user_id TEXT DEFAULT 'USR-ADMIN-001';")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_start ON incidents (start_epoch);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents (status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_server ON incidents (server_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_user ON incidents (user_id);")

        # ------------------------------------------------------------------
        # 8. Seed Default User and Local Server if none exist
        # ------------------------------------------------------------------
        cursor.execute("SELECT id FROM users WHERE id = 'USR-ADMIN-001' OR email = 'admin@devpilot.local'")
        admin_row = cursor.fetchone()
        if not admin_row:
            admin_pwd = os.environ.get("DEVPILOT_ADMIN_PASSWORD", "admin@devpilot123")
            admin_hash = hash_password(admin_pwd)
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
                INSERT INTO users (id, email, password_hash, name, role, created_at)
                VALUES ('USR-ADMIN-001', 'admin@devpilot.local', ?, 'DevPilot Administrator', 'admin', ?)
            """, (admin_hash, now_iso))
            logger.info("Seeded default administrator account (admin@devpilot.local)")

        cursor.execute("SELECT id FROM servers WHERE id = 'SRV-LOCAL-001'")
        local_srv = cursor.fetchone()
        if not local_srv:
            now = datetime.now(timezone.utc)
            cursor.execute("""
                INSERT INTO servers (
                    id, user_id, name, hostname, ip_address, os_info,
                    status, agent_version, docker_enabled, last_heartbeat_at,
                    last_heartbeat_epoch, created_at
                ) VALUES (
                    'SRV-LOCAL-001', 'USR-ADMIN-001', 'Primary DevPilot Server',
                    'localhost', '127.0.0.1', 'Linux / Local Host',
                    'online', '2.0.0', 1, ?, ?, ?
                )
            """, (now.isoformat(), now.timestamp(), now.isoformat()))
            logger.info("Seeded primary local server record (SRV-LOCAL-001)")

        # Link any legacy null server_id records to primary server
        cursor.execute("UPDATE system_metrics SET server_id = 'SRV-LOCAL-001' WHERE server_id IS NULL OR server_id = ''")
        cursor.execute("UPDATE timeline_events SET server_id = 'SRV-LOCAL-001' WHERE server_id IS NULL OR server_id = ''")
        cursor.execute("UPDATE incidents SET server_id = 'SRV-LOCAL-001' WHERE server_id IS NULL OR server_id = ''")
        cursor.execute("UPDATE incidents SET user_id = 'USR-ADMIN-001' WHERE user_id IS NULL OR user_id = ''")

        conn.commit()
    logger.info("DevPilot database initialized & validated at %s", DB_PATH)


# ----------------------------------------------------------------------
# Password & Authentication Helpers (Cryptographically Secure)
# ----------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with a unique random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        100_000
    )
    return f"{salt}${key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password in constant time to prevent timing attacks."""
    try:
        salt_hex, key_hex = stored_hash.split("$", 1)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            100_000
        )
        return hmac.compare_digest(key.hex(), key_hex)
    except Exception:
        return False


def create_user_session_token(user_id: str, email: str, ttl_days: int = 7) -> str:
    """Generate an HMAC-SHA256 signed bearer session token."""
    now = time.time()
    exp = int(now + (ttl_days * 86400))
    payload = f"{user_id}:{email}:{exp}"
    sig = hmac.new(
        SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    raw = f"{payload}:{sig}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")


def verify_user_session_token(token: str):
    """Verify bearer token signature and expiration; returns user dict or None."""
    if not token:
        return None
    try:
        raw = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        parts = raw.split(":", 3)
        if len(parts) != 4:
            return None
        user_id, email, exp_str, sig = parts
        exp = int(exp_str)
        if time.time() > exp:
            return None  # Expired

        expected_payload = f"{user_id}:{email}:{exp_str}"
        expected_sig = hmac.new(
            SECRET_KEY.encode("utf-8"),
            expected_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(sig, expected_sig):
            return None

        # Verify user still exists in database
        user = get_user_by_id(user_id)
        if user:
            user["user_id"] = user["id"]
        return user
    except Exception:
        return None


# ----------------------------------------------------------------------
# User Operations
# ----------------------------------------------------------------------

def create_user(email: str, password: str, name: str, role: str = "member"):
    """Create a new registered user."""
    email_clean = email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise ValueError("A valid email address is required.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")

    user_id = f"usr_{secrets.token_hex(6)}"
    pwd_hash = hash_password(password)
    now_iso = datetime.now(timezone.utc).isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email_clean,))
        if cursor.fetchone():
            raise ValueError(f"User with email '{email_clean}' already exists.")

        cursor.execute("""
            INSERT INTO users (id, email, password_hash, name, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, email_clean, pwd_hash, name.strip() or "Operator", role, now_iso))
        conn.commit()

    return get_user_by_id(user_id)


def get_user_by_email(email: str):
    """Fetch user by email address."""
    if not email:
        return None
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, password_hash, name, role, created_at FROM users WHERE email = ?", (email.strip().lower(),))
        row = cursor.fetchone()
        if not row:
            return None
        item = dict(row)
        item["user_id"] = item["id"]
        return item


def get_user_by_id(user_id: str):
    """Fetch user by user ID."""
    if not user_id:
        return None
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, name, role, created_at FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        item = dict(row)
        item["user_id"] = item["id"]
        return item


# ----------------------------------------------------------------------
# Server Management Operations
# ----------------------------------------------------------------------

def create_server(user_id: str, name: str, hostname: str = None, ip_address: str = None, os_info: str = None):
    """Register a new monitored server record for a user."""
    if not name or not name.strip():
        raise ValueError("Server name is required.")

    server_id = f"srv_{secrets.token_hex(6)}"
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    now_epoch = now.timestamp()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO servers (
                id, user_id, name, hostname, ip_address, os_info,
                status, agent_version, docker_enabled, last_heartbeat_at,
                last_heartbeat_epoch, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL, 0, ?, ?, ?)
        """, (
            server_id,
            user_id,
            name.strip(),
            hostname or "",
            ip_address or "",
            os_info or "Linux",
            now_iso,
            now_epoch,
            now_iso
        ))
        conn.commit()

    return get_server_by_id(server_id, user_id=user_id)


def get_servers(user_id: str = None):
    """List all servers with active incident tallies, optionally filtered by owner."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT s.*,
                (SELECT COUNT(*) FROM incidents i WHERE i.server_id = s.id AND i.status = 'active') as active_incidents,
                (SELECT COUNT(*) FROM incidents i WHERE i.server_id = s.id) as total_incidents,
                (SELECT COUNT(*) FROM agent_credentials ac WHERE ac.server_id = s.id AND ac.is_revoked = 0) as has_enrolled_agent
            FROM servers s
        """
        params = []
        if user_id:
            query += " WHERE s.user_id = ?"
            params.append(user_id)
        query += " ORDER BY s.created_at DESC"
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def get_server_by_id(server_id: str, user_id: str = None):
    """Get single server record by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT s.*,
                (SELECT COUNT(*) FROM incidents i WHERE i.server_id = s.id AND i.status = 'active') as active_incidents,
                (SELECT COUNT(*) FROM incidents i WHERE i.server_id = s.id) as total_incidents,
                (SELECT COUNT(*) FROM agent_credentials ac WHERE ac.server_id = s.id AND ac.is_revoked = 0) as has_enrolled_agent
            FROM servers s
            WHERE s.id = ?
        """
        params = [server_id]
        if user_id:
            query += " AND s.user_id = ?"
            params.append(user_id)
        cursor.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None


def update_server(server_id: str, updates: dict, user_id: str = None):
    """Update server fields."""
    allowed_fields = [
        "name", "hostname", "ip_address", "os_info",
        "status", "agent_version", "docker_enabled",
        "last_heartbeat_at", "last_heartbeat_epoch"
    ]
    set_clauses = []
    params = []
    for k, v in updates.items():
        if k in allowed_fields:
            set_clauses.append(f"{k} = ?")
            params.append(v)
    if not set_clauses:
        return False

    query = f"UPDATE servers SET {', '.join(set_clauses)} WHERE id = ?"
    params.append(server_id)
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount > 0


def delete_server(server_id: str, user_id: str = None):
    """Remove a server and its associated agent credentials/data."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = "DELETE FROM servers WHERE id = ?"
        params = [server_id]
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount > 0


def record_server_heartbeat(server_id: str, agent_version: str = None, os_info: str = None, ip_address: str = None, docker_enabled: int = None):
    """Record heartbeat communication and update live server status."""
    now = datetime.now(timezone.utc)
    updates = {
        "status": "online",
        "last_heartbeat_at": now.isoformat(),
        "last_heartbeat_epoch": now.timestamp()
    }
    if agent_version:
        updates["agent_version"] = agent_version
    if os_info:
        updates["os_info"] = os_info
    if ip_address:
        updates["ip_address"] = ip_address
    if docker_enabled is not None:
        updates["docker_enabled"] = int(docker_enabled)

    return update_server(server_id, updates)


# ----------------------------------------------------------------------
# Agent Enrollment & Revocation Operations
# ----------------------------------------------------------------------

def create_enrollment_token(server_id: str, ttl_minutes: int = 30) -> str:
    """Generate a secure, single-use, short-lived enrollment credential."""
    raw_token = f"dpt_{secrets.token_urlsafe(32)}"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    token_id = f"tok_{secrets.token_hex(8)}"
    expires_epoch = time.time() + (ttl_minutes * 60)
    created_at = datetime.now(timezone.utc).isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Invalidate any existing unused tokens for this server
        cursor.execute("UPDATE enrollment_tokens SET is_used = 1 WHERE server_id = ? AND is_used = 0", (server_id,))
        cursor.execute("""
            INSERT INTO enrollment_tokens (id, server_id, token_hash, expires_at_epoch, is_used, created_at)
            VALUES (?, ?, ?, ?, 0, ?)
        """, (token_id, server_id, token_hash, expires_epoch, created_at))
        conn.commit()

    return raw_token


def verify_and_consume_enrollment_token(raw_token: str):
    """Validate enrollment token and atomically mark it used. Returns server_id or None."""
    if not raw_token or not raw_token.strip():
        return None
    token_hash = hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()
    now_epoch = time.time()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, server_id, expires_at_epoch, is_used
            FROM enrollment_tokens
            WHERE token_hash = ?
        """, (token_hash,))
        row = cursor.fetchone()
        if not row:
            return None
        if row["is_used"] == 1:
            return None  # Token already consumed
        if now_epoch > row["expires_at_epoch"]:
            return None  # Token expired

        # Invalidate token immediately
        cursor.execute("UPDATE enrollment_tokens SET is_used = 1 WHERE id = ?", (row["id"],))
        conn.commit()
        return row["server_id"]


def generate_agent_api_key(server_id: str) -> str:
    """Issue a persistent, revocable Agent API Key for an enrolled server."""
    raw_key = f"dpk_{secrets.token_urlsafe(40)}"
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    key_id = f"cred_{secrets.token_hex(8)}"
    now_iso = datetime.now(timezone.utc).isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Revoke previous keys for this server
        cursor.execute("UPDATE agent_credentials SET is_revoked = 1 WHERE server_id = ?", (server_id,))
        cursor.execute("""
            INSERT INTO agent_credentials (id, server_id, api_key_hash, is_revoked, created_at, last_used_at)
            VALUES (?, ?, ?, 0, ?, ?)
        """, (key_id, server_id, key_hash, now_iso, now_iso))
        cursor.execute("UPDATE servers SET status = 'online' WHERE id = ?", (server_id,))
        conn.commit()

    return raw_key


def verify_agent_api_key(raw_key: str):
    """Validate an incoming Agent API Key. Returns server record if valid and active."""
    if not raw_key or not raw_key.strip():
        return None
    key_hash = hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()
    now_iso = datetime.now(timezone.utc).isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ac.id as cred_id, ac.server_id, ac.is_revoked, s.*
            FROM agent_credentials ac
            JOIN servers s ON s.id = ac.server_id
            WHERE ac.api_key_hash = ?
        """, (key_hash,))
        row = cursor.fetchone()
        if not row or row["is_revoked"] == 1:
            return None

        # Update last_used_at timestamp
        cursor.execute("UPDATE agent_credentials SET last_used_at = ? WHERE id = ?", (now_iso, row["cred_id"]))
        conn.commit()
        return dict(row)


def revoke_agent_credentials(server_id: str) -> bool:
    """Revoke agent credentials and mark server offline."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE agent_credentials SET is_revoked = 1 WHERE server_id = ?", (server_id,))
        cursor.execute("UPDATE servers SET status = 'offline' WHERE id = ?", (server_id,))
        conn.commit()
        return cursor.rowcount > 0


# ----------------------------------------------------------------------
# Metrics Operations (Server-Aware)
# ----------------------------------------------------------------------

def insert_system_metric(metric_data):
    """Insert a single system metric sample linked to a server."""
    now = datetime.now(timezone.utc)
    ts_iso = metric_data.get("timestamp") or now.isoformat()
    ts_epoch = metric_data.get("timestamp_epoch") or now.timestamp()
    server_id = metric_data.get("server_id") or "SRV-LOCAL-001"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO system_metrics (
                server_id, timestamp, timestamp_epoch,
                cpu_usage, cpu_cores,
                memory_usage, memory_used_gb, memory_total_gb, memory_available_gb,
                disk_usage, disk_used_gb, disk_total_gb, disk_free_gb
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            server_id,
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


def get_system_metrics_history(server_id=None, start_epoch=None, end_epoch=None, limit=600):
    """Retrieve historical metrics within epoch window, ordered chronologically."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM system_metrics"
        conditions = []
        params = []

        if server_id and server_id != "all":
            conditions.append("server_id = ?")
            params.append(server_id)
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
# Timeline Events Operations (Server-Aware & Fingerprinted)
# ----------------------------------------------------------------------

def compute_event_fingerprint(timestamp, source, message, event_type="", server_id="SRV-LOCAL-001"):
    """Generate SHA256 hash to prevent duplicate event inserts."""
    raw = f"{server_id}|{timestamp}|{source}|{event_type}|{message.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def insert_timeline_event(event_data):
    """
    Insert a timeline event linked to a server.
    Avoids duplicate entries using unique fingerprint.
    """
    now = datetime.now(timezone.utc)
    ts_iso = event_data.get("timestamp") or now.isoformat()
    ts_epoch = event_data.get("timestamp_epoch") or now.timestamp()
    server_id = event_data.get("server_id") or "SRV-LOCAL-001"
    event_type = event_data.get("event_type", "log")
    severity = (event_data.get("severity") or "INFO").upper()
    source = event_data.get("source", "system")
    message = event_data.get("message", "")

    metadata = event_data.get("metadata")
    if metadata and isinstance(metadata, (dict, list)):
        metadata_str = json.dumps(metadata)
    else:
        metadata_str = str(metadata) if metadata else None

    fingerprint = event_data.get("fingerprint") or compute_event_fingerprint(
        ts_iso, source, message, event_type, server_id
    )

    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO timeline_events (
                    server_id, timestamp, timestamp_epoch, event_type, severity,
                    source, message, metadata, incident_id, fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                server_id,
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


def get_timeline_events(server_id=None, incident_id=None, start_epoch=None, end_epoch=None,
                        event_type=None, severity=None, limit=300, order=None):
    """Retrieve chronological events with optional filters."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM timeline_events"
        conditions = []
        params = []

        if server_id and server_id != "all":
            conditions.append("server_id = ?")
            params.append(server_id)
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
        # For general timeline without filters, fetch latest events
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


def link_events_to_incident(incident_id, start_epoch, end_epoch=None, server_id=None):
    """Associate all unlinked events in [start_epoch, end_epoch] with an incident."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            UPDATE timeline_events
            SET incident_id = ?
            WHERE (incident_id IS NULL OR incident_id = '')
              AND timestamp_epoch >= ?
        """
        params = [incident_id, start_epoch]
        if end_epoch:
            query += " AND timestamp_epoch <= ?"
            params.append(end_epoch)
        if server_id:
            query += " AND server_id = ?"
            params.append(server_id)

        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount


# ----------------------------------------------------------------------
# Incidents Operations (Multi-Server & Multi-Tenant Aware)
# ----------------------------------------------------------------------

def create_incident(incident_data):
    """Create a new detected incident linked to a server and user."""
    now = datetime.now(timezone.utc)
    ts_iso = incident_data.get("start_time") or now.isoformat()
    ts_epoch = incident_data.get("start_epoch") or now.timestamp()
    server_id = incident_data.get("server_id") or "SRV-LOCAL-001"
    user_id = incident_data.get("user_id") or "USR-ADMIN-001"
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
                id, incident_number, server_id, user_id, title, description,
                problem_type, severity, status,
                start_time, start_epoch, end_time, end_epoch,
                trigger_event_id, ai_investigation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            inc_id,
            count,
            server_id,
            user_id,
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
    link_events_to_incident(inc_id, window_start, ts_epoch + 60.0, server_id=server_id)

    logger.info("Created new incident: %s (%s) for server %s", inc_id, incident_data.get("title"), server_id)
    return inc_id


def get_incidents(server_id=None, user_id=None, status=None, limit=50):
    """List recorded incidents with server, user, and status filters."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT i.*, s.name as server_name, s.ip_address as server_ip
            FROM incidents i
            LEFT JOIN servers s ON s.id = i.server_id
        """
        conditions = []
        params = []

        if server_id and server_id != "all":
            conditions.append("i.server_id = ?")
            params.append(server_id)
        if user_id:
            conditions.append("i.user_id = ?")
            params.append(user_id)
        if status and status != "all":
            conditions.append("i.status = ?")
            params.append(status)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY i.start_epoch DESC"
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


def get_incident_by_id(incident_id, user_id=None):
    """Retrieve full incident details by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT i.*, s.name as server_name, s.ip_address as server_ip, s.os_info as server_os
            FROM incidents i
            LEFT JOIN servers s ON s.id = i.server_id
            WHERE i.id = ?
        """
        params = [incident_id]
        if user_id:
            query += " AND i.user_id = ?"
            params.append(user_id)

        cursor.execute(query, params)
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


def resolve_incident(incident_id, notes=None, user_id=None):
    """Mark an incident as resolved with timestamp and notes."""
    now = datetime.now(timezone.utc)
    ts_iso = now.isoformat()
    ts_epoch = now.timestamp()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            UPDATE incidents
            SET status = 'resolved',
                end_time = ?,
                end_epoch = ?,
                resolved_at = ?,
                resolution_notes = ?
            WHERE id = ?
        """
        params = [ts_iso, ts_epoch, ts_iso, notes or "Resolved by engineer.", incident_id]
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        cursor.execute(query, params)
        conn.commit()
        updated = cursor.rowcount > 0

    if updated:
        inc = get_incident_by_id(incident_id)
        srv_id = inc.get("server_id") if inc else "SRV-LOCAL-001"
        insert_timeline_event({
            "server_id": srv_id,
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
