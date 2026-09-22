# Lamp 
*"See it. Report it. Fix it together."*

An AI-powered civic intelligence platform that turns scattered Nigerian citizen
reports on public-service failures, unfinished projects, and community safety
risks into verified, prioritized, evidence-backed intelligence that NGOs,
journalists, and local institutions can act on.

> **This is a proof of concept.** All data in `/data` and `/dashboard` is
> synthetic (`is_demo_data: true`). No real people, places-as-victims, or
> government allegations are represented.

---

## 1. Problem

Across Lagos, Kano, Enugu, Kaduna and everywhere in between, the same pattern
repeats: a borehole project is announced and never finished; a health centre
runs out of drugs; a road washes out every rainy season. Residents complain
on WhatsApp groups, at town-hall meetings, to local radio but those
complaints evaporate. No one aggregates them across a community, so:

- The same failure gets reported ten times with nobody connecting the dots.
- There's no record of whether it was ever fixed.
- Government dashboards report *official* project status, never the
  ground-truth gap citizens actually experience.
- Journalists and NGOs have no reliable, evidence-backed way to find out
  *where the problem is worst* without weeks of fieldwork.
- The people most affected — rural, low-income communities — have the least
  power to escalate, so their reports are the ones most likely to vanish.

Left alone, this erodes trust in both government and civic institutions, and
the resulting information vacuum gets filled by rumor. It matters
particularly in Nigeria because of scale (36 states, huge rural-urban and
connectivity divides) and because so much civic reporting infrastructure
(USSD, community radio, WhatsApp) already exists informally — it's just never
aggregated or made actionable.

## 2. Solution — user journey

```
Citizen notices problem
      │
      ▼
Report (text / voice / photo / location, anonymous by default)
      │
      ▼
AI classification (category, urgency, entities) ── explains its reasoning
      │
      ▼
Duplicate / similarity check against existing reports
      │
      ▼
Transparent risk score (documented formula, not a black box)
      │
      ▼
Human verification queue  ◄── nothing is published as "fact" before this
      │
      ▼
Dashboard: hotspots, trends, accountability tracker
      │
      ▼
NGO / journalist / LGA reviews → verifies → refers / acts
      │
      ▼
Status flows back to the community (Verified / Needs Verification /
Reported Problem / No Recent Info)
      │
      ▼
Impact measured (resolution rate, response time, recurrence)
```

## 3. AI components (all explainable, all human-supervised)

| Component | Input | Technique | Output | Why AI | Accuracy check | Human oversight |
|---|---|---|---|---|---|---|
| **Classification** | Free-text report | Keyword/rule-based for PoC (`backend/ai/classifier.py`); swap-in for a fine-tuned multilingual transformer in production | Category, urgency, confidence, explanation string | Reports arrive unstructured, in mixed English/Pidgin | Precision/recall against a labeled sample; confidence threshold routes low-confidence reports straight to human review | Every classification ships with its reasoning; low-confidence → "Needs Human Review" category |
| **Duplicate/similarity detection** | New report text + existing reports in same state | TF-IDF + cosine similarity (`find_similar_reports`) | Ranked candidate matches with similarity scores | Prevents duplicate effort, surfaces corroboration | Manual audit of a sample of flagged pairs | Verifier confirms "duplicate" / "corroborating" / "unrelated" — never auto-merged |
| **Risk/priority scoring** | Severity, urgency, people affected, evidence confidence | Documented formula: `severity × urgency × (1 + affected/1000) × evidence_confidence`, scaled 0–100 | Score + full breakdown of inputs | Consistent triage across thousands of reports | Spot-checked against verifier judgment; formula is versioned | Score is a *sorting aid*, never a sole basis for action |
| **Civic intelligence assistant** | Natural-language question from an authorized user | Retrieval over stored report data (RAG pattern) — answers ONLY from what's in the database | Summary answer + evidence report IDs | Lets NGOs/journalists query without SQL | Every answer must cite retrievable evidence IDs; answers with zero evidence are flagged, not invented | Assistant is retrieval-constrained, not free-generation, to prevent hallucination |
| *(Roadmap, not in this PoC)* Voice-to-text, multilingual NLP (Pidgin/Hausa/Yoruba/Igbo), image classification for infrastructure damage | — | Whisper-class ASR; multilingual transformer fine-tune; vision classifier | — | Extends reach to non-literate, non-English-first users | — | — |

**What AI is deliberately *not* allowed to do:** publish an unverified report
as fact, name/accuse an individual or organization of a crime, auto-close a
case, or generate an answer to the civic assistant without citing evidence
rows it actually retrieved.

## 4. Designed for the Nigerian context

- **Language:** English + Nigerian Pidgin keyword sets in the classifier
  (extendable to Hausa/Yoruba/Igbo with a multilingual model in production).
- **Connectivity:** report submission designed to degrade gracefully — text
  works over 2G; the roadmap includes a USSD/SMS front-end for the module
  that currently assumes a smartphone.
- **Digital literacy:** category selection uses plain-language prompts, not
  bureaucratic taxonomy; voice-note submission is a first-class evidence
  type, not an afterthought.
- **Trust & fear of retaliation:** anonymous submission is the *default*, not
  an option to find; location precision is stored at three levels
  (exact / community / LGA-only) so a report can be geographically useful
  without exposing an exact address.
- **Misinformation / false reports:** the platform never labels something
  "false" — it uses *Unverified → Needs Corroboration → Corroborated →
  Conflicting Reports → High-Confidence*, always distinguishing citizen
  report from established fact.
- **Community tension:** dispute-related categories route to a mediation/
  referral pathway rather than a public "blame" feed.

## 5. Safety & privacy

- Anonymous by default; no phone/email stored raw — only salted hashes if a
  citizen opts in to be contacted for follow-up.
- Location precision is fuzzed by default for sensitive categories (Safety,
  Abuse/Protection).
- Role-based access: citizens can submit and see public statuses only;
  verifiers/org admins see full detail; every access is written to
  `audit_logs`.
- Rate limiting and duplicate-detection double as basic abuse prevention.
- For anything resembling an active emergency, the product **routes to
  appropriate emergency/support services** rather than pretending to be one
  — Lamp is a reporting/aggregation layer, not a dispatcher.
- No report is ever displayed as an accusation against a named individual;
  organizational/project-level accountability items are shown as
  "citizen-reported" vs. "official" status side by side, never merged.

## 6. Data model

See [`database/schema.sql`](database/schema.sql) for the full DDL. Core
entities: `users`, `organizations`, `locations`, `report_categories`,
`reports`, `evidence`, `ai_analysis`, `risk_scores`, `verifications`,
`responses`, `public_projects`, `project_updates`, `audit_logs`.

```
users ──< reports >── locations
reports ──< evidence
reports ──< ai_analysis
reports ──< risk_scores
reports ──< verifications
reports ──< responses >── organizations
public_projects ──< project_updates
public_projects ──< reports (linked_project_id)
(all mutating actions) ──< audit_logs
```

## 7. Tech stack

- **Frontend (production):** React/Next.js — PoC ships a static dashboard instead (see §9)
- **Backend:** Python + FastAPI (`backend/main.py`)
- **Database:** PostgreSQL (`database/schema.sql`); PoC uses an in-memory store seeded from the CSV for zero-setup demoing
- **AI:** scikit-learn (TF-IDF/cosine similarity) + rule-based classifier now; PyTorch/transformer fine-tune + LLM-backed RAG assistant in production
- **Maps:** Mapbox/Leaflet (production) — PoC dashboard uses Chart.js only, to stay dependency-free and open instantly
- **Auth:** JWT/OAuth (production)
- **Deployment:** Docker (production)

## 8. System architecture

```
Citizen
  │
  ▼
Web/Mobile/USSD interface
  │
  ▼
API (FastAPI)
  │
  ▼
Report processing ──► AI/NLP pipeline (classify, dedupe, risk score)
  │
  ▼
Human verification queue
  │
  ▼
PostgreSQL
  │
  ├──► Community dashboard (public, verified-only view)
  └──► Authorized org dashboard + AI civic assistant
            │
            ▼
      Response / referral to appropriate authority or service
            │
            ▼
      Status update flows back to citizen/community
```

## 9. What's actually running in this PoC

```
lamp/
├── backend/
│   ├── main.py                # FastAPI app: submit/list reports, dashboard KPIs, AI assistant
│   └── ai/classifier.py       # classification, duplicate detection, risk scoring
├── database/
│   └── schema.sql             # full PostgreSQL schema
├── data/
│   ├── generate_synthetic_data.py
│   └── lamp_demo_reports.csv   # 500 synthetic reports (DEMO DATA)
├── dashboard/
│   ├── dashboard.html         # 4-page interactive dashboard (NGO/journalist/official view), opens standalone in any browser
│   └── report.html            # citizen-facing report submission form (text, voice recording, photo, location, anonymous toggle) — posts to the live API
└── README.md                  # this file
```

**Already tested working:** report submission → classification → duplicate
check → risk scoring → dashboard KPIs → hotspot ranking → evidence-cited AI
assistant Q&A (all verified via a live smoke test against the FastAPI app).

To run the backend:
```bash
cd backend
pip install fastapi uvicorn scikit-learn pydantic
uvicorn main:app --reload
# then POST to http://127.0.0.1:8000/reports, GET /dashboard/summary, etc.
```

To view the admin dashboard: just open `dashboard/dashboard.html` in a
browser — no server needed, data is embedded.

To submit a report as a citizen: start the backend (`uvicorn main:app
--reload`), then open `dashboard/report.html` in a browser. It's a real
working form — text description, in-browser voice recording (playback only
in this PoC; transcription is a roadmap item), photo attach (kept on-device
for the demo), state/LGA/community, estimated people affected, and an
anonymous toggle — and it posts live to `POST /reports`, showing back the
AI's category, confidence, reasoning, and any similar reports it found.

## 10. Impact KPIs

| KPI | How it's measured |
|---|---|
| Reports processed | Count in `reports` table |
| % auto-categorized with high confidence | `ai_analysis.confidence ≥ 0.7` / total |
| Duplicate-detection precision | Verifier agreement rate on flagged similar pairs |
| Verification rate | `verifications` rows / total reports |
| Avg. response time | `responses.responded_at − reports.submitted_at` |
| Resolution rate | `response_status = Resolved` / total |
| Communities reached | distinct `location_id` with ≥1 report |
| NGO time saved | self-reported before/after survey with pilot partners |

## 11. Business & sustainability model

- **Free** for citizens, always — reporting a safety or service concern is
  never paywalled.
- **Paid institutional dashboards** for NGOs, media houses, local government,
  research institutions (tiered by data volume/seats).
- **Analytics & API access** subscriptions for organizations that want to
  pull structured data into their own systems.
- **Research & grant partnerships** with development organizations
  (this is the typical path for civic-tech in Nigeria — e.g. donor-funded
  pilots before institutional adoption).

## 12. Scalability roadmap

| Phase | Scope |
|---|---|
| 1 — PoC (this repo) | Single-region synthetic demo, in-memory store |
| 2 — Pilot | 2–3 LGAs, real PostgreSQL, real verifier workflow, WhatsApp/USSD intake |
| 3 — Multi-state | Multilingual NLP, image classification for infra damage, org onboarding |
| 4 — Nationwide | Full 36-state coverage, mobile app, offline-first sync |
| 5 — Institutional integration | API partnerships with NGOs/CSOs/relevant public institutions, public accountability tracker at scale |

## 13. Responsible AI

| Risk | Safeguard |
|---|---|
| Bias in classification | Keyword sets reviewed for regional/language coverage; confidence threshold routes uncertain cases to humans |
| False accusation | Platform never names individuals as guilty; organizational accountability shown as citizen-reported vs. official, side by side |
| Hallucination (assistant) | Retrieval-constrained — every answer must cite real evidence IDs from the database |
| False reports | Verification pipeline (Unverified → Corroborated), never auto-published as fact |
| Privacy/surveillance | Anonymous by default, location fuzzing, salted contact hashes, role-based access, audit logs |
| Political misuse | No electoral-integrity claims in this PoC scope; accountability items are service-delivery focused, not partisan |
| Model errors | Every AI output ships with a human-readable explanation and a confidence score, not just a label |

## 14. Demo script (3–5 min)

1. A citizen in a Kano community submits an anonymous report: *"borehole
   project announced but not completed, no water for 3 weeks."*
2. AI classifies it (Water Infrastructure, urgency raised by "no water"),
   shows its reasoning.
3. System flags 2 similar existing reports from the same LGA — same issue,
   different reporters — corroboration, not duplication.
4. Transparent risk score computed live, with the formula shown.
5. Dashboard hotspot map updates: this LGA is now a top-3 hotspot for water
   complaints.
6. Switch to the NGO dashboard — verifier reviews the report, marks
   "Corroborated."
7. NGO admin asks the AI assistant: *"Which communities have the most
   unresolved water complaints?"* — gets an answer with cited evidence IDs.
8. NGO refers the issue to the relevant agency; status changes to
   "Referred."
9. Community view shows the project status flip from Reported Problem to
 Needs Verification, then eventually Verified once resolved.
10. Close on the accountability tracker showing official vs. citizen-reported
    status side by side — the core trust-building mechanic of the product.

## 15. Elevator pitches

Every day, Nigerians report broken infrastructure and service
failures on WhatsApp groups and at town halls — and those reports vanish.
Lamp aggregates them: AI classifies and de-duplicates reports, computes a
transparent risk score, and routes verified issues to NGOs, journalists, and
local officials through a civic intelligence dashboard. Citizens report for
free, always anonymously if they choose; institutions get analytics and an
AI assistant that answers questions from real report data — never invented.
It's designed for Nigeria's connectivity and language realities from day
one, and it's built so no AI output is ever treated as fact until a human
verifies it.

## 16. Limitations & future work
*Classification* is presently keyword-based; production deployment requires a fine-tuned multilingual model covering Pidgin, Hausa, Yoruba, and Igbo.
*Evaluation used synthetic data*; field deployment with a pilot community is needed to assess real-world classification accuracy and reporting uptake.
*USSD/SMS* intake for low-connectivity users is designed but not yet implemented.

---

*Built as a proof of concept. All figures, reports, and locations in the
demo dataset are synthetic and clearly labeled as such — nothing here
represents a real event, real government project, or real person.*
