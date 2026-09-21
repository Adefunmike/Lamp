"""
Lamp Database Layer — SQLite (PoC)
=====================================
Uses Python's built-in sqlite3 module, so there's nothing extra to install.
The table mirrors the core `reports` entity from database/schema.sql,
flattened into one table for simplicity. When you're ready for production,
this is the piece you'd swap for the full PostgreSQL schema (schema.sql) —
the function signatures below (insert_report, list_reports, etc.) are the
seam to do that behind.

The database file (lamp.db) is created automatically, next to this file,
the first time the app runs. It persists between restarts.
"""

import sqlite3
import os
import csv

DB_PATH = os.path.join(os.path.dirname(__file__), "lamp.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    report_id           TEXT PRIMARY KEY,
    date                 TEXT,
    state                 TEXT,
    lga                    TEXT,
    community               TEXT,
    category                 TEXT,
    description                TEXT,
    severity_1to5                INTEGER,
    urgency_1to5                  INTEGER,
    num_affected_est                INTEGER,
    evidence_type                     TEXT,
    evidence_confidence                 REAL,
    verification_status                   TEXT,
    ai_confidence                           REAL,
    risk_score                                REAL,
    response_status                             TEXT,
    resolution_date                               TEXT,
    reporter_anonymous                              INTEGER,
    is_demo_data                                      INTEGER,
    report_kind                                         TEXT DEFAULT 'complaint',
    user_id                                               TEXT
);

CREATE TABLE IF NOT EXISTS users (
    user_id       TEXT PRIMARY KEY,
    username        TEXT UNIQUE NOT NULL,
    password_hash      TEXT NOT NULL,
    salt                  TEXT NOT NULL,
    created_at              TEXT
);
"""


def _migrate(conn):
    """Add columns to a reports table that was created before this version,
    without losing any existing data."""
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(reports)").fetchall()}
    if "report_kind" not in existing_cols:
        conn.execute("ALTER TABLE reports ADD COLUMN report_kind TEXT DEFAULT 'complaint'")
    if "user_id" not in existing_cols:
        conn.execute("ALTER TABLE reports ADD COLUMN user_id TEXT")
    conn.commit()


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate(conn)
    conn.close()


def is_empty():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    conn.close()
    return count == 0


def seed_from_csv(csv_path):
    """One-time load of the synthetic demo dataset into the database,
    only runs if the reports table is currently empty."""
    if not is_empty() or not os.path.exists(csv_path):
        return 0
    conn = get_connection()
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        conn.execute(
            """INSERT OR IGNORE INTO reports
               (report_id, date, state, lga, community, category, description,
                severity_1to5, urgency_1to5, num_affected_est, evidence_type,
                evidence_confidence, verification_status, ai_confidence,
                risk_score, response_status, resolution_date,
                reporter_anonymous, is_demo_data)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                r["report_id"], r["date"], r["state"], r["lga"], r["community"],
                r["category"], r["description"], r["severity_1to5"], r["urgency_1to5"],
                r["num_affected_est"], r["evidence_type"], r["evidence_confidence"],
                r["verification_status"], r["ai_confidence"], r["risk_score"],
                r["response_status"], r["resolution_date"],
                1 if r["reporter_anonymous"] in ("True", "1", True) else 0,
                1 if r["is_demo_data"] in ("True", "1", True) else 0,
            ),
        )
    conn.commit()
    conn.close()
    return len(rows)


def insert_report(record: dict):
    conn = get_connection()
    conn.execute(
        """INSERT INTO reports
           (report_id, date, state, lga, community, category, description,
            severity_1to5, urgency_1to5, num_affected_est, evidence_type,
            evidence_confidence, verification_status, ai_confidence,
            risk_score, response_status, resolution_date,
            reporter_anonymous, is_demo_data, report_kind, user_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            record["report_id"], record["date"], record["state"], record["lga"],
            record["community"], record["category"], record["description"],
            record["severity_1to5"], record["urgency_1to5"], record["num_affected_est"],
            record["evidence_type"], record["evidence_confidence"],
            record["verification_status"], record["ai_confidence"], record["risk_score"],
            record["response_status"], record["resolution_date"],
            1 if record["reporter_anonymous"] else 0,
            1 if record["is_demo_data"] else 0,
            record.get("report_kind", "complaint"),
            record.get("user_id"),
        ),
    )
    conn.commit()
    conn.close()


def _row_to_dict(row):
    d = dict(row)
    d["reporter_anonymous"] = bool(d["reporter_anonymous"])
    d["is_demo_data"] = bool(d["is_demo_data"])
    return d


def list_reports(state=None, category=None, status=None, report_kind=None, user_id=None, limit=50):
    conn = get_connection()
    query = "SELECT * FROM reports WHERE 1=1"
    params = []
    if state:
        query += " AND state = ?"; params.append(state)
    if category:
        query += " AND category = ?"; params.append(category)
    if status:
        query += " AND verification_status = ?"; params.append(status)
    if report_kind:
        query += " AND report_kind = ?"; params.append(report_kind)
    if user_id:
        query += " AND user_id = ?"; params.append(user_id)
    total = conn.execute(query.replace("SELECT *", "SELECT COUNT(*)"), params).fetchone()[0]
    query += " ORDER BY date DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return total, [_row_to_dict(r) for r in rows]


def get_report(report_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def all_reports():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM reports").fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def summary():
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    verified = conn.execute(
        "SELECT COUNT(*) FROM reports WHERE verification_status IN ('Corroborated','High-Confidence')"
    ).fetchone()[0]
    resolved = conn.execute("SELECT COUNT(*) FROM reports WHERE response_status = 'Resolved'").fetchone()[0]
    high_priority = conn.execute("SELECT COUNT(*) FROM reports WHERE risk_score >= 60").fetchone()[0]
    conn.close()
    return {
        "total_reports": total,
        "verified_reports": verified,
        "resolved_cases": resolved,
        "high_priority_open": high_priority,
        "resolution_rate_pct": round(100 * resolved / total, 1) if total else 0,
    }


def hotspots(top_n=10):
    conn = get_connection()
    rows = conn.execute(
        "SELECT state, lga, COUNT(*) as report_count FROM reports "
        "GROUP BY state, lga ORDER BY report_count DESC LIMIT ?", (top_n,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------
# Users / auth
#
# PoC-level auth: salted SHA-256 password hashing, and a simple opaque
# token (a random string stored alongside the account) rather than a real
# session/JWT system. This is fine for a hackathon demo on localhost, but
# is NOT production-grade auth — production should use a vetted library
# (e.g. passlib + JWT, or an auth provider) instead of hand-rolled hashing.
# ---------------------------------------------------------------------

def create_user(user_id, username, password_hash, salt, created_at):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (user_id, username, password_hash, salt, created_at) VALUES (?,?,?,?,?)",
            (user_id, username, password_hash, salt, created_at),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # username already taken
    finally:
        conn.close()


def get_user_by_username(username):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_reports_by_user(user_id, limit=50):
    return list_reports(user_id=user_id, limit=limit)
