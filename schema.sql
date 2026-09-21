-- =========================================================
-- Lamp Database Schema (PostgreSQL)
-- =========================================================
-- Conceptual ERD:
-- users --< reports >-- locations
-- reports --< evidence
-- reports --< ai_analysis
-- reports --< risk_scores
-- reports --< verifications
-- reports --< responses
-- organizations --< responses
-- public_projects --< project_updates
-- public_projects --< reports (linked_project_id, nullable)
-- all mutating actions --< audit_logs
-- =========================================================

CREATE TABLE users (
    user_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name        VARCHAR(100),              -- NULL if anonymous
    is_anonymous         BOOLEAN NOT NULL DEFAULT TRUE,
    contact_hash         VARCHAR(128),               -- salted hash, never raw phone/email
    role                 VARCHAR(20) NOT NULL DEFAULT 'citizen', -- citizen, verifier, org_admin, journalist
    created_at           TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE organizations (
    org_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                 VARCHAR(150) NOT NULL,
    org_type             VARCHAR(50),               -- NGO, CSO, media, local_government, research
    verified_partner     BOOLEAN DEFAULT FALSE,
    created_at           TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE locations (
    location_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state                VARCHAR(50) NOT NULL,
    lga                  VARCHAR(80) NOT NULL,
    community             VARCHAR(120),
    latitude              NUMERIC(9,6),               -- generalized/fuzzed for vulnerable reports
    longitude             NUMERIC(9,6),
    precision_level        VARCHAR(20) DEFAULT 'lga'    -- exact, community, lga_only (privacy control)
);

CREATE TABLE report_categories (
    category_id           SERIAL PRIMARY KEY,
    name                  VARCHAR(80) NOT NULL UNIQUE,
    track                 VARCHAR(50)                -- stability, transparency, safety
);

CREATE TABLE reports (
    report_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                UUID REFERENCES users(user_id),
    location_id             UUID REFERENCES locations(location_id),
    category_id             INT REFERENCES report_categories(category_id),
    linked_project_id        UUID REFERENCES public_projects(project_id),
    description             TEXT NOT NULL,
    severity_1to5            SMALLINT,
    urgency_1to5             SMALLINT,
    num_affected_est          INT,
    is_anonymous             BOOLEAN DEFAULT TRUE,
    submitted_at              TIMESTAMP NOT NULL DEFAULT now(),
    verification_status        VARCHAR(30) DEFAULT 'Unverified',
    response_status            VARCHAR(30) DEFAULT 'No Action Yet',
    resolved_at                TIMESTAMP
);

CREATE TABLE evidence (
    evidence_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id               UUID REFERENCES reports(report_id) ON DELETE CASCADE,
    evidence_type            VARCHAR(20),              -- photo, voice_note, video, text_only
    storage_ref               TEXT,                     -- encrypted object storage pointer
    uploaded_at               TIMESTAMP DEFAULT now()
);

CREATE TABLE ai_analysis (
    analysis_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id                UUID REFERENCES reports(report_id) ON DELETE CASCADE,
    predicted_category         VARCHAR(80),
    confidence                 NUMERIC(4,3),
    matched_keywords            TEXT[],
    similar_report_ids          UUID[],
    explanation                 TEXT,                   -- human-readable reasoning, always stored
    model_version                VARCHAR(30),
    created_at                   TIMESTAMP DEFAULT now()
);

CREATE TABLE risk_scores (
    risk_score_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id                 UUID REFERENCES reports(report_id) ON DELETE CASCADE,
    severity_1to5              SMALLINT,
    urgency_1to5                SMALLINT,
    num_affected_est             INT,
    evidence_confidence           NUMERIC(4,3),
    score_0to100                  NUMERIC(5,1),
    formula_version                VARCHAR(20),
    computed_at                     TIMESTAMP DEFAULT now()
);

CREATE TABLE verifications (
    verification_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id                  UUID REFERENCES reports(report_id) ON DELETE CASCADE,
    verified_by_user_id          UUID REFERENCES users(user_id),
    status                       VARCHAR(30),           -- Unverified, Needs Corroboration, Corroborated, Conflicting, High-Confidence
    notes                        TEXT,
    verified_at                  TIMESTAMP DEFAULT now()
);

CREATE TABLE responses (
    response_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id                  UUID REFERENCES reports(report_id) ON DELETE CASCADE,
    org_id                      UUID REFERENCES organizations(org_id),
    action_taken                 TEXT,
    status                       VARCHAR(30),           -- referred, in_progress, resolved
    responded_at                 TIMESTAMP DEFAULT now()
);

CREATE TABLE public_projects (
    project_id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                        VARCHAR(200),
    responsible_institution        VARCHAR(150),
    location_id                   UUID REFERENCES locations(location_id),
    official_status                VARCHAR(30),          -- from public records
    community_status                VARCHAR(30),          -- derived from citizen reports (never overwrites official_status)
    status_flag                    VARCHAR(20),           -- verified / needs_verification / reported_problem / no_recent_info
    created_at                      TIMESTAMP DEFAULT now()
);

CREATE TABLE project_updates (
    update_id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id                    UUID REFERENCES public_projects(project_id) ON DELETE CASCADE,
    update_text                    TEXT,
    source                          VARCHAR(20),          -- official, citizen_report
    posted_at                       TIMESTAMP DEFAULT now()
);

CREATE TABLE audit_logs (
    log_id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id                  UUID REFERENCES users(user_id),
    action                          VARCHAR(100),
    target_table                    VARCHAR(50),
    target_id                        UUID,
    metadata                         JSONB,
    created_at                        TIMESTAMP DEFAULT now()
);

-- Indexes for dashboard performance
CREATE INDEX idx_reports_location ON reports(location_id);
CREATE INDEX idx_reports_category ON reports(category_id);
CREATE INDEX idx_reports_status ON reports(verification_status, response_status);
CREATE INDEX idx_risk_scores_report ON risk_scores(report_id);
