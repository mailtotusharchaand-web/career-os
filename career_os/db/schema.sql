-- Career OS Operational SQLite Schema
-- Target: career_os.db

PRAGMA foreign_keys = ON;

-- 1. Discovery Runs (Every discovery cycle)
CREATE TABLE IF NOT EXISTS discovery_runs (
    id TEXT PRIMARY KEY,                       -- e.g., 'run_0001', 'run_0002'
    run_number INTEGER UNIQUE NOT NULL,       -- 1, 2, 3...
    started_at TEXT NOT NULL,                  -- ISO8601 UTC
    completed_at TEXT,                         -- ISO8601 UTC
    status TEXT NOT NULL,                      -- 'COMPLETED', 'FAILED', 'IN_PROGRESS'
    cv_path TEXT,
    max_budget INTEGER,
    total_raw_records INTEGER DEFAULT 0,
    total_unique_opportunities INTEGER DEFAULT 0,
    new_opportunities INTEGER DEFAULT 0,
    previously_seen_opportunities INTEGER DEFAULT 0,
    reappeared_opportunities INTEGER DEFAULT 0,
    expired_opportunities INTEGER DEFAULT 0,
    already_applied_opportunities INTEGER DEFAULT 0,
    already_reviewed_opportunities INTEGER DEFAULT 0,
    evaluations_required INTEGER DEFAULT 0,
    evaluations_reused INTEGER DEFAULT 0,
    llm_calls_avoided INTEGER DEFAULT 0,
    provider_metrics_json TEXT,                -- JSON: JobSpy / JobsPipe breakdown
    source_summary_json TEXT,                  -- JSON: Status breakdown by source
    health_records_json TEXT                   -- JSON: Observable source health records
);

-- 2. Canonical Opportunities (Single source of truth for discovered jobs)
CREATE TABLE IF NOT EXISTS opportunities (
    id TEXT PRIMARY KEY,                       -- e.g., 'disc_0001' (preserves historical IDs)
    canonical_key TEXT UNIQUE NOT NULL,        -- SHA256(normalized_title || normalized_company || normalized_location)
    title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    company TEXT NOT NULL,
    normalized_company TEXT NOT NULL,
    location TEXT NOT NULL,
    normalized_location_json TEXT,             -- JSON: City, state, country, is_india
    description TEXT NOT NULL,
    description_hash TEXT NOT NULL,            -- SHA256 of cleaned description text
    job_url TEXT,
    job_type TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    salary_interval TEXT,
    currency TEXT,
    salary_raw TEXT,
    is_remote INTEGER DEFAULT 0,
    first_seen_run_id TEXT NOT NULL REFERENCES discovery_runs(id),
    first_seen_at TEXT NOT NULL,
    last_seen_run_id TEXT NOT NULL REFERENCES discovery_runs(id),
    last_seen_at TEXT NOT NULL,
    appearance_count INTEGER DEFAULT 1,
    presence_status TEXT NOT NULL DEFAULT 'AVAILABLE', -- 'AVAILABLE', 'DISAPPEARED', 'EXPIRED'
    current_opportunity_status TEXT NOT NULL DEFAULT 'UNKNOWN', -- 'UNKNOWN', 'AVAILABLE', 'EXPIRED'
    current_application_status TEXT NOT NULL DEFAULT 'NOT_APPLIED', -- 'NOT_APPLIED' ... 'OFFER'
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 3. Opportunity Source & Provider Provenance (Multi-source, multi-provider tracking)
CREATE TABLE IF NOT EXISTS opportunity_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,                    -- 'jobspy', 'jobspipe'
    source TEXT NOT NULL,                      -- 'indeed', 'linkedin', 'jobspipe', etc.
    external_job_id TEXT,
    job_url TEXT,
    search_query TEXT,
    hypothesis_id TEXT,
    opportunity_type TEXT,
    hypothesis_concept TEXT,
    discovered_at TEXT NOT NULL,
    discovery_run_id TEXT NOT NULL REFERENCES discovery_runs(id),
    UNIQUE(opportunity_id, provider, source, external_job_id)
);

-- 4. Discovery Run to Opportunity Manifest (Cross-run presence/absence tracking)
CREATE TABLE IF NOT EXISTS discovery_run_opportunities (
    discovery_run_id TEXT NOT NULL REFERENCES discovery_runs(id) ON DELETE CASCADE,
    opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    discovery_classification TEXT NOT NULL,    -- 'NEW', 'SEEN', 'REAPPEARED', 'ALREADY_APPLIED'
    rank_in_run INTEGER,
    created_at TEXT NOT NULL,
    PRIMARY KEY(discovery_run_id, opportunity_id)
);

-- 5. LLM Candidate Evaluations
CREATE TABLE IF NOT EXISTS evaluations (
    id TEXT PRIMARY KEY,                       -- e.g., 'eval_disc_0001'
    opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    recommendation TEXT,                       -- 'YES', 'NO', 'STRONG_YES', etc.
    score REAL,
    fit_dimensions_json TEXT,                  -- JSON: role_fit, domain_fit, technical_depth, etc.
    strengths_json TEXT,                       -- JSON: list of strings
    gaps_json TEXT,                            -- JSON: list of strings
    reasoning TEXT,
    gate_failed INTEGER DEFAULT 0,
    gate_failure_reasons_json TEXT,            -- JSON: list of strings
    gate_passed_checks_json TEXT,              -- JSON: list of strings
    evaluated_at TEXT NOT NULL,
    evaluator_model TEXT,                      -- e.g., 'gemini-1.5-flash', 'heuristic_v2'
    content_hash TEXT NOT NULL,                -- Hash of evaluated payload
    is_reused INTEGER DEFAULT 0,               -- 1 if reused, 0 if fresh LLM call
    reuse_type TEXT,                           -- 'REUSED_EXACT', 'REUSED_SAME_POSTING', 'REUSED_EQUIVALENT_ROLE', NULL
    source_evaluation_id TEXT REFERENCES evaluations(id),
    reuse_reason TEXT,
    evaluation_status TEXT DEFAULT 'EVALUATED' -- 'EVALUATED', 'REUSED', 'PENDING', 'FAILED'
);

-- 6. Human Review Decisions
CREATE TABLE IF NOT EXISTS human_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id TEXT UNIQUE NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    verdict TEXT NOT NULL,                     -- 'RELEVANT', 'ADJACENT', 'WEAK', 'IRRELEVANT'
    counterfactual TEXT NOT NULL,              -- 'YES', 'PROBABLY', 'NO', 'UNSURE'
    priority TEXT NOT NULL,                    -- 'HIGH', 'MEDIUM', 'LOW'
    opportunity_status TEXT NOT NULL DEFAULT 'AVAILABLE',
    application_status TEXT NOT NULL DEFAULT 'NOT_APPLIED',
    notes TEXT,
    opportunity_type TEXT,
    search_query TEXT,
    source TEXT,
    reviewed_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 7. Application Lifecycle History (Immutable audit trail)
CREATE TABLE IF NOT EXISTS application_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    previous_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    notes TEXT
);

-- 8. Evaluation Profiles (Schema-ready placeholder; explicitly UNUSED in this milestone)
CREATE TABLE IF NOT EXISTS evaluation_profiles (
    id TEXT PRIMARY KEY,
    role_archetype TEXT NOT NULL,
    canonical_fingerprint TEXT UNIQUE NOT NULL,
    exemplar_evaluation_id TEXT REFERENCES evaluations(id),
    created_at TEXT NOT NULL
);

-- 9. Email Sync Checkpoints (Durable synchronization tracking)
CREATE TABLE IF NOT EXISTS email_sync_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,                    -- 'gmail', 'mock', 'outlook'
    account_id TEXT NOT NULL,                  -- user account email
    last_synced_at TEXT NOT NULL,              -- ISO8601 UTC
    last_history_id TEXT,                      -- Gmail API historyId
    last_message_timestamp TEXT,               -- ISO8601 UTC of newest message processed
    sync_status TEXT NOT NULL DEFAULT 'HEALTHY',-- 'HEALTHY', 'ERROR', 'IN_PROGRESS'
    messages_processed INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(provider, account_id)
);

-- 10. Email Raw Messages Ingestion Index (Deduplication & Data Minimization)
CREATE TABLE IF NOT EXISTS email_raw_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    account_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    thread_id TEXT,
    sender TEXT,
    sender_domain TEXT,
    recipients_json TEXT,
    subject TEXT,
    snippet TEXT,
    body_hash TEXT NOT NULL,
    received_at TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    labels_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(provider, account_id, message_id)
);

-- 11. Career Events (Provider-Independent Evidence & Timeline Records)
CREATE TABLE IF NOT EXISTS career_events (
    id TEXT PRIMARY KEY,                       -- e.g., 'evt_...'
    event_type TEXT NOT NULL,                  -- 'APPLICATION_CONFIRMATION', 'INTERVIEW_INVITATION', 'OFFER', etc.
    opportunity_id TEXT REFERENCES opportunities(id) ON DELETE SET NULL,
    occurred_at TEXT NOT NULL,                 -- ISO8601 UTC
    source_provider TEXT NOT NULL,             -- 'gmail', 'mock'
    source_account_id TEXT NOT NULL,
    source_message_id TEXT NOT NULL,
    source_thread_id TEXT,
    confidence_score REAL NOT NULL,
    confidence_level TEXT NOT NULL,            -- 'HIGH', 'MEDIUM', 'LOW', 'AMBIGUOUS'
    status TEXT NOT NULL DEFAULT 'PENDING_CONFIRMATION', -- 'AUTOMATIC_APPLIED', 'PENDING_CONFIRMATION', 'CONFIRMED', 'REJECTED', 'IGNORED'
    evidence_json TEXT NOT NULL,               -- JSON: subject, sender, snippet, extracted_metadata
    candidate_matches_json TEXT,               -- JSON: list of potential matching opportunities
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source_provider, source_account_id, source_message_id)
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_opportunities_canonical_key ON opportunities(canonical_key);
CREATE INDEX IF NOT EXISTS idx_opportunities_app_status ON opportunities(current_application_status);
CREATE INDEX IF NOT EXISTS idx_opportunities_opp_status ON opportunities(current_opportunity_status);
CREATE INDEX IF NOT EXISTS idx_opp_sources_opp_id ON opportunity_sources(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_run_opps_run_id ON discovery_run_opportunities(discovery_run_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_opp_id ON evaluations(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_content_hash ON evaluations(content_hash);
CREATE INDEX IF NOT EXISTS idx_human_reviews_opp_id ON human_reviews(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_career_events_opp_id ON career_events(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_career_events_status ON career_events(status);
CREATE INDEX IF NOT EXISTS idx_career_events_source_msg ON career_events(source_provider, source_account_id, source_message_id);
CREATE INDEX IF NOT EXISTS idx_raw_emails_msg ON email_raw_messages(provider, account_id, message_id);
CREATE INDEX IF NOT EXISTS idx_sync_checkpoints_acc ON email_sync_checkpoints(provider, account_id);

