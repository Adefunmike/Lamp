"""
Lamp Backend API (PoC) — now with persistent storage
========================================================
Run:
    pip install fastapi uvicorn scikit-learn pydantic
    uvicorn main:app --reload

Storage: SQLite, via database.py — no separate database server needed.
Data is written to lamp.db (created automatically next to this file) and
survives restarts. The demo dataset is loaded into it once, the first time
you run the app.

Endpoints:
    POST /reports              submit a new citizen report
    GET  /reports               list reports (filter by state/category/status)
    GET  /reports/{id}          get one report with full AI reasoning
    GET  /dashboard/summary     KPIs for the admin dashboard
    GET  /dashboard/hotspots    emerging hotspots (grouped by LGA)
    POST /assistant/ask         AI civic-intelligence Q&A over the report data
                                 (answers ONLY from stored data - no hallucination)
"""

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid
import os
import hashlib
import secrets

from lamp_ai.classifier import classify_report, find_similar_reports, compute_risk_score
import database

app = FastAPI(title="Lamp API", version="0.2.0-poc")

# CORS: the citizen report form (report.html) and dashboard are opened as
# static files in the browser, so we allow cross-origin requests to the
# local API for this PoC. In production, restrict allow_origins to the
# real frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- database setup: create table, seed demo data once ----------
database.init_db()
DEMO_CSV = os.path.join(os.path.dirname(__file__), "data", "lamp_demo_reports.csv")
if not os.path.exists(DEMO_CSV):
    DEMO_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "lamp_demo_reports.csv")
loaded = database.seed_from_csv(DEMO_CSV)
if loaded:
    print(f"Seeded database with {loaded} demo reports.")
else:
    print("Database already has data — skipping seed.")

# ---------- auth (PoC-level: see database.py note on hashing/tokens) ----------
# In-memory session map (token -> user_id). Resets when the server restarts,
# which just means users log in again — fine for a local demo.
SESSIONS = {}


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


def current_user_id(x_auth_token: Optional[str] = Header(None)) -> Optional[str]:
    """Looks up the logged-in user from the X-Auth-Token header, if present.
    Returns None if no token / not logged in — endpoints that use this
    treat that as 'anonymous / guest', not an error."""
    return SESSIONS.get(x_auth_token)


class AuthIn(BaseModel):
    username: str
    password: str


@app.post("/auth/register")
def register(auth: AuthIn):
    if len(auth.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    user_id = f"USR-{uuid.uuid4().hex[:8].upper()}"
    salt = secrets.token_hex(8)
    password_hash = hash_password(auth.password, salt)
    ok = database.create_user(user_id, auth.username, password_hash, salt, datetime.utcnow().isoformat())
    if not ok:
        raise HTTPException(status_code=409, detail="That username is already taken.")
    token = secrets.token_hex(16)
    SESSIONS[token] = user_id
    return {"user_id": user_id, "username": auth.username, "token": token}


@app.post("/auth/login")
def login(auth: AuthIn):
    user = database.get_user_by_username(auth.username)
    if not user or hash_password(auth.password, user["salt"]) != user["password_hash"]:
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    token = secrets.token_hex(16)
    SESSIONS[token] = user["user_id"]
    return {"user_id": user["user_id"], "username": user["username"], "token": token}


@app.get("/reports/mine")
def my_reports(user_id: Optional[str] = None, x_auth_token: Optional[str] = Header(None)):
    """Returns the logged-in user's own submitted reports. Accepts the
    token either via header (preferred) or query param (for quick testing
    from the browser/docs UI)."""
    uid = SESSIONS.get(x_auth_token) or user_id
    if not uid:
        raise HTTPException(status_code=401, detail="Log in to see your submitted reports.")
    total, results = database.get_reports_by_user(uid)
    return {"count": total, "reports": results}


class ReportIn(BaseModel):
    description: str
    state: str
    lga: str
    community: Optional[str] = None
    anonymous: bool = True
    num_affected_est: Optional[int] = 50
    evidence_type: Optional[str] = "text_only"
    report_kind: Optional[str] = "complaint"  # "complaint" or "safety"


EVIDENCE_CONF = {"photo": 0.9, "video": 0.95, "voice_note": 0.7, "text_only": 0.5, "none": 0.3}


@app.post("/reports")
def submit_report(report: ReportIn, x_auth_token: Optional[str] = Header(None)):
    """Citizen submits a report. Pipeline:
    classify -> duplicate check -> risk score -> saved to the database,
    queued for human verification.

    Safety reports (report_kind='safety') are always stored as anonymous,
    regardless of the anonymous flag sent — protecting the reporter is not
    optional for that category."""
    classification = classify_report(report.description)

    _, existing = database.list_reports(state=report.state, limit=200)
    existing_texts = [r["description"] for r in existing]
    similar = find_similar_reports(report.description, existing_texts)

    severity = 3  # default mid severity pending human review; not asserted as fact
    evidence_conf = EVIDENCE_CONF.get(report.evidence_type, 0.5)
    risk = compute_risk_score(severity, classification.urgency_1to5, report.num_affected_est or 50, evidence_conf)

    is_safety = report.report_kind == "safety"
    user_id = SESSIONS.get(x_auth_token)  # None if not logged in — that's fine, guests can still report

    record = {
        "report_id": f"LMP-{uuid.uuid4().hex[:8].upper()}",
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "state": report.state,
        "lga": report.lga,
        "community": report.community or "Unspecified",
        "category": classification.category,
        "description": report.description,
        "severity_1to5": severity,
        "urgency_1to5": classification.urgency_1to5,
        "num_affected_est": report.num_affected_est,
        "evidence_type": report.evidence_type,
        "evidence_confidence": evidence_conf,
        "verification_status": "Unverified",
        "ai_confidence": classification.confidence,
        "risk_score": risk["risk_score"],
        "response_status": "No Action Yet",
        "resolution_date": "",
        "reporter_anonymous": True if is_safety else report.anonymous,
        "is_demo_data": False,
        "report_kind": report.report_kind,
        "user_id": user_id,
    }
    database.insert_report(record)

    return {
        "report": record,
        "ai_reasoning": {
            "classification_explanation": classification.explanation,
            "similar_reports_found": similar[:5],
            "risk_score_breakdown": risk,
        },
        "next_step": "Saved to the database, queued for human verification before appearing on the public dashboard.",
    }


@app.get("/reports")
def list_reports(state: Optional[str] = None, category: Optional[str] = None,
                  status: Optional[str] = None, report_kind: Optional[str] = None, limit: int = 50):
    total, results = database.list_reports(state=state, category=category, status=status,
                                             report_kind=report_kind, limit=limit)
    return {"count": total, "reports": results}


@app.get("/reports/{report_id}")
def get_report(report_id: str):
    record = database.get_report(report_id)
    if not record:
        raise HTTPException(status_code=404, detail="Report not found")
    return record


@app.get("/dashboard/summary")
def dashboard_summary():
    return database.summary()


@app.get("/dashboard/hotspots")
def dashboard_hotspots(top_n: int = 10):
    return database.hotspots(top_n=top_n)


class AssistantQuery(BaseModel):
    question: str


@app.post("/assistant/ask")
def ask_assistant(query: AssistantQuery):
    """Answers ONLY using the stored report data (retrieval, not generation
    from a general-purpose LLM's imagination) - always returns the evidence
    it used so the answer is auditable."""
    q = query.question.lower()
    rows = database.all_reports()

    if "water" in q:
        rows = [r for r in rows if r["category"] == "Water Infrastructure"]
    elif "unresolved" in q or "urgent" in q:
        rows = [r for r in rows if r["response_status"] != "Resolved" and float(r.get("risk_score", 0)) >= 50]
    elif "lagos" in q:
        rows = [r for r in rows if r["state"] == "Lagos"]

    by_lga: dict = {}
    for r in rows:
        by_lga[r["lga"]] = by_lga.get(r["lga"], 0) + 1
    top = sorted(by_lga.items(), key=lambda x: -x[1])[:3]

    return {
        "answer_summary": f"Found {len(rows)} matching reports. Top locations: {top}",
        "evidence_report_ids": [r["report_id"] for r in rows[:10]],
        "note": "Answer generated from stored report data only, evidence IDs shown above.",
    }