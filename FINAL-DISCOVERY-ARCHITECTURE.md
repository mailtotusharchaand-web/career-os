# FINAL-DISCOVERY-ARCHITECTURE.md

**Date:** 2026-08-17  
**Status:** Architecture Freeze (Post-Correction Gate)  
**Audience:** Implementation agent — this document is the sole architectural authority

---

## 1. Architecture Overview

### 1.1 Foundational Principle

Career OS is an **open-world opportunity discovery system**. It discovers opportunities from the candidate's actual capabilities and stated objective — not from developer-maintained lists of domains, industries, companies, titles, role families, career paths, markets, or countries.

**The candidate may discover they are competitive for an opportunity they did not previously know existed.**

### 1.2 Separation of Concerns: Discovery vs. Eligibility vs. Application Readiness

To avoid both provincial blindness and international queue-flooding, the system strictly separates three distinct concepts:

```
[A. DISCOVERY]              [B. ELIGIBILITY / VISA]         [C. APPLICATION READINESS]
What exists that matches    Can the candidate legally      Is this actionable in the
candidate capabilities?     work in this market?           primary review queue right now?
       │                              │                                  │
Open-world search (Home,       Contextual JD analysis         Classified into:
Explicit Requested Geo,        (not_required, available,      • PRIMARY
Unscoped Global)               unknown, unavailable)          • INTERNATIONAL_VERIFY
                                                              • NOT_ACTIONABLE
                                                              • AUDIT_ONLY
```

1. **Discovery is Open-World:** Discovers opportunities without geographic or domain prejudice. International opportunities can be discovered via candidate-requested geography or global unscoped queries.
2. **Eligibility is Evidence-Driven:** Analyzes whether the candidate has right-to-work in the job location or if explicit sponsorship/relocation support is provided in the job description.
3. **Application Readiness is Queue-Gated:** International opportunities with unconfirmed sponsorship are NEVER silently discarded, but are placed in a secondary `INTERNATIONAL_VERIFY` queue to prevent flooding the default `PRIMARY` queue.

### 1.3 Core Architectural Constraints

- **C1 — No hardcoded career taxonomy.** Terms like "Product Management", "Fintech", "Trading Technology" may appear as LLM-generated hypotheses but MUST NOT become permanent code, config, or prompt constraints.
- **C2 — No taxonomy relocation.** Replacing hardcoded Python lists with equivalent hardcoded lists inside prompts or config files violates C1 equally.
- **C3 — UNKNOWN is a valid system state.** When the system lacks evidence to decide, `UNKNOWN` is preferred over guessing, hardcoded exceptions, silent rejection, or silent acceptance.
- **C4 — Infrastructure data ≠ career preferences.** Static infrastructure data (ISO-3166 country codes, 50 US state abbreviations, source capabilities, parser rules) is permitted. Career preferences (target domains, target countries, target companies) are NOT permitted as permanent system data.
- **C5 — Anti-patch principle.** When an unseen edge case appears, UNKNOWN/AMBIGUOUS is preferred over adding a manually curated exception.
- **C6 — Candidate-owned configuration.** Values like `home_country` and `requested_geographies` belong to the candidate in `config/candidate.json` and are NEVER automatically changed by the system.

---

## 2. Pipeline / Data Flow

```
CV file (DOCX/PDF)
  │
  ▼
[Stage 1]  CV Parsing ─────────────────────────── deterministic (markitdown)
  │  output: raw CV text
  ▼
[Stage 2]  Candidate Capability Model ─────────── LLM (reasoning on capabilities)
  │  output: candidate_model.json
  ▼
[Stage 3]  Opportunity Hypotheses ──────────────── LLM (open-world potential)
  │  output: opportunity_hypotheses.json
  ▼
[Stage 4]  Search Intents ─────────────────────── LLM (diverse search terms)
  │  output: search_intents.json
  ▼
[Stage 5]  Source Capability Router ────────────── deterministic (capability matching)
  │  output: search_plan.json
  ▼
[Stage 6]  Source Adapters (JobSpy/API) ────────── deterministic network execution
  │  output: raw_jobs.json (append-only)
  ▼
[Stage 7]  Normalize + Deduplicate ─────────────── deterministic canonical identity
  │  output: normalized_jobs.json
  ▼
[Stage 8]  User Constraint Gates ───────────────── deterministic hard gates
  │  output: constraint evaluation
  ▼
[Stage 9]  Geography & Visa Annotation ─────────── deterministic contextual parsing
  │  output: location & visa_status annotation
  ▼
[Stage 10] Queue Classification ────────────────── deterministic queue routing
  │  output: PRIMARY | INTERNATIONAL_VERIFY | NOT_ACTIONABLE | AUDIT_ONLY
  ▼
[Stage 11] LLM Opportunity Evaluation ─────────── LLM (evaluate.py on eligible queues)
  │  output: llm_evaluations.json
  ▼
[Stage 12] Ranking & Presentation ──────────────── deterministic diversification
  │  output: ranked results per queue
  ▼
[Stage 13] Human Review UI ────────────────────── human sovereign review
  │  output: human_review.json
```

---

## 3. Stage Contracts

### Stage 1: CV Parsing
- **Input:** CV file path (DOCX or PDF).
- **Output:** Raw CV text (string, ≤6000 chars).
- **Owner:** Existing `parse_cv()` in `evaluate.py`.
- **Type:** Deterministic text extraction via MarkItDown.
- **Persistence:** In-memory; recorded in `candidate_model.json`.
- **Failure:** Fatal.

### Stage 2: Candidate Capability Model
- **Input:** Raw CV text + LLM.
- **Output:** `candidate_model.json` (§4).
- **Owner:** Candidate model generator.
- **Type:** LLM capability reasoning.
- **Persistence:** Immutable `runs/<run-id>/candidate_model.json`.
- **Failure:** Fatal. Retry 4× with exponential backoff.

### Stage 3: Opportunity Hypotheses
- **Input:** Candidate model + `config/objective.json`.
- **Output:** `opportunity_hypotheses.json` (§5).
- **Owner:** Hypothesis generator.
- **Type:** LLM open-world reasoning.
- **Persistence:** Immutable `runs/<run-id>/opportunity_hypotheses.json`.
- **Failure:** Fatal. Retry 4×.

### Stage 4: Search Intents
- **Input:** Opportunity hypotheses + `config/candidate.json` (`home_country`, `requested_geographies`).
- **Output:** `search_intents.json` (§6).
- **Owner:** Search intent planner.
- **Type:** LLM intent & terminology generation.
- **Persistence:** Immutable per wave: `runs/<run-id>/search_intents.json`.
- **Failure:** Fatal. Retry 4×.

### Stage 5: Source Capability Router
- **Input:** Search intents + `config/sources.json`.
- **Output:** `search_plan.json` (§10).
- **Owner:** Source router.
- **Type:** Deterministic capability matching.
- **Persistence:** `runs/<run-id>/search_plan.json`.
- **Failure:** Non-fatal per intent. Unrouteable intents logged and skipped.

### Stage 6: Source Adapters (Execution)
- **Input:** `search_plan.json`.
- **Output:** Raw job dictionaries.
- **Owner:** Source adapter modules wrapping JobSpy / external APIs.
- **Type:** Deterministic network execution.
- **Persistence:** Append-only `runs/<run-id>/raw_jobs.json`.
- **Failure:** **Non-fatal per source.** Isolated try/except per source adapter call. Failure in LinkedIn must not halt Indeed or Naukri.

### Stage 7: Normalize + Deduplicate
- **Input:** `raw_jobs.json`.
- **Output:** `normalized_jobs.json` (§12).
- **Owner:** Normalizer / deduplicator.
- **Type:** Deterministic schema mapping + canonical exact deduplication.
- **Persistence:** `runs/<run-id>/normalized_jobs.json`.
- **Failure:** Non-fatal per record. Malformed records logged and skipped.

### Stage 8: User Constraint Gates
- **Input:** `normalized_jobs.json` + `config/constraints.json`.
- **Output:** Gated records with explicit pass/fail reasons (§13).
- **Owner:** Deterministic gate engine.
- **Type:** Deterministic verification of candidate-declared hard constraints.
- **Persistence:** Inline gate metadata.
- **Failure:** Non-fatal. Missing constraints default to open-world pass.

### Stage 9: Geography & Visa Annotation
- **Input:** Gated jobs + `config/candidate.json`.
- **Output:** Enriched records with `normalized_location` (§8) and `visa_status` / `visa_notes` (§9).
- **Owner:** Geography and contextual visa analyzer.
- **Type:** Deterministic token-aware geography matching + contextual sentence polarity analysis.
- **Persistence:** Inline enrichment.
- **Failure:** Non-fatal. Fallback: `country_code: "UNKNOWN"`, `visa_status: "unknown"`.

### Stage 10: Application Queue Classification
- **Input:** Annotated jobs.
- **Output:** `queue_state`: `PRIMARY | INTERNATIONAL_VERIFY | NOT_ACTIONABLE | AUDIT_ONLY` (§7).
- **Owner:** Queue classification engine.
- **Type:** Deterministic queue routing rules.
- **Persistence:** Inline field `queue_state`.
- **Failure:** Non-fatal.

### Stage 11: LLM Opportunity Evaluation
- **Input:** Jobs in `PRIMARY` and `INTERNATIONAL_VERIFY` queues + candidate CV text.
- **Output:** Structured evaluations (16-field schema in `evaluate.py`).
- **Owner:** Existing `evaluate.py` evaluation engine.
- **Type:** LLM semantic evaluation.
- **Persistence:** Incremental `llm_evaluations.json`.
- **Failure:** Non-fatal per job. Error logged; retried on subsequent run.

### Stage 12: Ranking & Diversification
- **Input:** Evaluated jobs per queue.
- **Output:** Diversified, ranked presentation order.
- **Owner:** Presentation ranker.
- **Type:** Deterministic multi-factor sort + company interleaving.
- **Persistence:** Preserved in final evaluated artifact.
- **Failure:** Non-fatal.

### Stage 13: Human Review UI
- **Input:** Evaluated and classified jobs.
- **Output:** `human_review.json`.
- **Owner:** Existing `review_server.py` and `review_ui/`.
- **Type:** Human sovereign decision.
- **Persistence:** `human_review.json`.

---

## 4. Candidate Capability Model Schema

```json
{
  "version": "1.0",
  "generated_at": "<ISO-8601>",
  "cv_hash": "<sha256 of CV text>",
  "facts": {
    "current_role": "<string>",
    "current_company": "<string>",
    "location": "<string>",
    "total_experience_years": "<number>",
    "experience": [
      {
        "role": "<string>",
        "company": "<string>",
        "duration": "<string>",
        "highlights": ["<string>"]
      }
    ],
    "education": ["<string>"],
    "certifications": ["<string>"]
  },
  "capabilities": [
    {
      "capability": "<string — what the candidate can do>",
      "evidence": ["<string — specific CV fact>"],
      "proficiency": "practiced | demonstrated | led",
      "transferable": true
    }
  ],
  "seniority_signals": {
    "years_experience": "<number>",
    "leadership_scope": "<string or null>",
    "scale_evidence": "<string or null>",
    "estimated_level": "<string>"
  },
  "candidate_summary": "<2-3 sentence factual capability summary>"
}
```

### Schema Invariants
- `capabilities` is a flat list. It MUST NOT be categorized into domain buckets ("fintech", "product", "analytics").
- Default is `transferable: true`. Marked `false` only for hyper-specific proprietary platform tooling with zero transferability.
- No career goals, target domains, or prescriptive role paths are stored in this model.

---

## 5. Opportunity Hypothesis Schema

```json
{
  "hypothesis_id": "<string — e.g. hyp_001>",
  "type": "direct | adjacent | transferable | unexpected | stretch",
  "capability_basis": ["<capability strings from candidate model>"],
  "opportunity_concept": "<string>",
  "transferable_reasoning": "<string>",
  "search_terminology": ["<string — job board queries>"],
  "geographic_hypothesis": "<string or null — advisory only>",
  "confidence": "high | medium | low",
  "evidence": "<string — specific CV facts>"
}
```

### Invariants
- **Advisory Geographic Hypotheses:** `geographic_hypothesis` is informational metadata. It MUST NOT become a hard search filter.
- **Evidence-Driven Novelty:** All hypotheses must be grounded in CV evidence. No artificial novelty quotas.
- **Hypothesis Budget:** Controlled by `max_hypotheses` (default: 15).

---

## 6. Search Intent Schema

```json
{
  "intent_id": "<string — e.g. int_001>",
  "hypothesis_id": "<string>",
  "search_query": "<string — query string for source>",
  "terminology_variants": ["<string>"],
  "seniority_signal": "<string or null>",
  "location_intent": "<string or null — 'India', 'Remote', or null for unscoped>",
  "remote_intent": "<boolean>",
  "source_preference": "<string or null>"
}
```

### Dynamic Budget Control (No Fixed Ratios)
- Governed by execution budgets: `max_search_intents` (default: 25), `max_source_requests` (default: 50), `max_results` (default: 500).
- Home-country coverage is guaranteed (at least one intent targets configured home country).
- Unscoped/global discovery is guaranteed (at least one intent has `location_intent: null`).
- Allocation between home country and unscoped discovery is dynamic based on candidate objective and budget. NO fixed percentage split.

---

## 7. Application Queue & Eligibility Architecture

### 7.1 The Four Sovereign Queues

Every discovered opportunity is assigned an explicit `queue_state`:

| Queue State | Meaning | Eligibility Criteria | UI Presentation |
|-------------|---------|----------------------|-----------------|
| `PRIMARY` | Realistically actionable immediately | (1) Home country job, OR<br>(2) Explicitly requested geography, OR<br>(3) International + explicit sponsorship / relocation | Default primary review queue |
| `INTERNATIONAL_VERIFY` | High potential, but sponsorship/relocation unconfirmed | International job + sponsorship `unknown` / `conditional` / `ambiguous` | Secondary review bucket with warning: *"International — sponsorship not confirmed. Verify eligibility before applying."* |
| `NOT_ACTIONABLE` | Incompatible with candidate constraints | (1) International + sponsorship `unavailable` (when candidate requires sponsorship), OR<br>(2) Excluded employment type, OR<br>(3) Expired recency | Excluded from review queues; retained in run artifacts |
| `AUDIT_ONLY` | System/debug provenance | Raw duplicates, malformed records, synthetic test jobs | Available for pipeline auditing |

### 7.2 Non-Deletion Invariant
All normalized jobs are retained in `normalized_jobs.json`. Gating and filtering occur via `queue_state` classification, NEVER by destructive deletion.

---

## 8. Geography Model & Normalization

### 8.1 Configuration Contract (`config/candidate.json`)

```json
{
  "home_country": "IN",
  "home_country_confirmed": false,
  "requested_geographies": [],
  "configured_at": null
}
```

- `home_country` defaults to `"IN"` for this instance.
- Candidate confirms or updates during setup.
- The system NEVER automatically changes `home_country` or `requested_geographies` from CV text, IP, or job locations.
- Referenced everywhere as `configured_home_country`.

### 8.2 Token-Aware Geography Normalization Rules

Applied in strict priority order without large third-party databases:

1. **Rule 1: Explicit Country Suffix.** Match ISO-3166 country name or alpha-2 code following comma/dash (e.g. `"Bengaluru, India"` → `country_code: "IN"`).
2. **Rule 2: US State Disambiguation.** If a 2-letter token after a comma matches one of the 50 US State abbreviations, it resolves to `US`. This guarantees `"Indianapolis, IN"` → `country_code: "US"` (Indiana, NOT India).
3. **Rule 3: Remote Prefix Handling.**
   - `"Remote - India"` → `country_code: "IN"`, `is_remote: true`
   - `"Remote - United States"` → `country_code: "US"`, `is_remote: true`
   - `"Remote - Global"` → `country_code: "GLOBAL"`, `is_remote: true`
   - `"Remote"` → `country_code: "UNKNOWN"`, `is_remote: true`
4. **Rule 4: Standard ISO-3166 Country Name Match.** Full country name in string (e.g. `"Singapore"`, `"United Kingdom"`) resolves to corresponding ISO code.
5. **Rule 5: Fallback to UNKNOWN.** If unresolvable, set `country_code: "UNKNOWN"`. Do NOT add one-off city exceptions.

### 8.3 Normalized Location Schema

```json
{
  "raw": "<original string>",
  "city": "<string or null>",
  "state": "<string or null>",
  "country_code": "<ISO-3166 alpha-2 | 'GLOBAL' | 'UNKNOWN'>",
  "is_remote": "<boolean>",
  "is_home_country": "<boolean>"
}
```

---

## 9. Visa & Relocation Contextual Model

### 9.1 Visa Status Classification

| Status Value | Meaning |
|--------------|---------|
| `not_required` | Job is in candidate's configured `home_country` |
| `available` | Contextual analysis confirms explicit sponsorship or relocation assistance |
| `unknown` | No mention in JD, OR conditional language, OR ambiguous/conflicting signals |
| `unavailable` | Contextual analysis confirms explicit refusal of sponsorship / strict citizen-only requirement |

### 9.2 Contextual Polarity Analysis

Visa status is determined by sentence-level contextual polarity analysis, NOT isolated keyword presence:

- **Explicit Positive (`available`):**
  - "We sponsor work visas", "Visa sponsorship provided", "Relocation assistance package included"
- **Explicit Negative (`unavailable`):**
  - "We do not sponsor visas", "Must be authorized to work in the US without sponsorship", "US Citizens or Permanent Residents only"
- **Conditional / Ambiguous (`unknown`):**
  - "Relocation assistance may be available in exceptional cases", "Sponsorship considered on a case-by-case basis"
- **Conflicting Signals (`unknown`):**
  - Contains both positive and negative phrases in different sections of JD.
- **No Evidence (`unknown`):**
  - No visa/relocation terms mentioned.

### 9.3 Negative Inference Prohibition
Sponsorship MUST NEVER be inferred from:
- Multinational status or employer size
- Presence of Indian office/entity
- Remote work status
- Candidate qualifications
- Historical sponsorship databases or Easy Apply status

---

## 10. Source Adapter Architecture

### 10.1 Layered Source Contract

```
[SearchIntent] ──► [Source Router] ──► [Source Adapter] ──► [JobSpy / API] ──► [Raw Jobs]
```

- **Source Router:** Matches `SearchIntent.location_intent` against `SourceCapabilities.geographic_coverage`. Contains ZERO career or domain logic.
- **Source Adapter:** Translates generic `SearchIntent` into source-specific JobSpy / REST parameters. Handles source-specific retries and rate limits.
- **Source Isolation:** Every adapter call is isolated with independent try/except and health metrics. A failure in LinkedIn or Indeed NEVER halts Naukri or the pipeline.

### 10.2 Source Capability Registry (`config/sources.json`)

```json
{
  "sources": {
    "indeed": {
      "adapter": "jobspy",
      "geographic_coverage": ["global"],
      "supports_location_param": true,
      "supports_country_param": true,
      "supports_remote_filter": false,
      "description_available": true,
      "salary_available": "sometimes",
      "date_posted_available": true,
      "enabled": true
    },
    "naukri": {
      "adapter": "jobspy",
      "geographic_coverage": ["IN"],
      "supports_location_param": true,
      "supports_country_param": false,
      "supports_remote_filter": false,
      "description_available": true,
      "salary_available": "sometimes",
      "date_posted_available": true,
      "enabled": true
    },
    "linkedin": {
      "adapter": "jobspy",
      "geographic_coverage": ["global"],
      "supports_location_param": true,
      "supports_country_param": false,
      "supports_remote_filter": true,
      "description_available": true,
      "salary_available": "rarely",
      "date_posted_available": true,
      "enabled": true
    },
    "google": {
      "adapter": "jobspy",
      "geographic_coverage": ["global"],
      "enabled": false
    },
    "glassdoor": {
      "adapter": "jobspy",
      "geographic_coverage": ["global"],
      "enabled": false
    },
    "zip_recruiter": {
      "adapter": "jobspy",
      "geographic_coverage": ["US", "CA"],
      "enabled": false
    }
  }
}
```

### 10.3 Source Health & Backoff
- 3 consecutive failures disable a source for `backoff_minutes` (default: 60).
- Health stats recorded in `discovery_metrics.json`.

---

## 11. Source Expansion Strategy

- **Phase 1 Active Sources:** Indeed, Naukri, LinkedIn.
- **Phase 2 Config-Enabled Sources:** Google Jobs, Glassdoor, ZipRecruiter, Bayt (enable via `config/sources.json` with zero code changes).
- **Prohibited Scrapers:** No fragile custom scrapers for Workday, Instahyre, or Wellfound.
- **Expansion Metrics:** Source expansion is justified only by measured incremental unique yield, reliability, and description quality.

---

## 12. Normalization & Deduplication

### 12.1 Canonical Job Schema

```json
{
  "job_id": "<sha256 hash of normalized identity key>",
  "title": "<string>",
  "company": "<string>",
  "location": "<original string>",
  "normalized_location": { "...§8.3..." },
  "description": "<string>",
  "job_url": "<string>",
  "salary_min": "<number or null>",
  "salary_max": "<number or null>",
  "salary_interval": "<string or null>",
  "is_remote": "<boolean>",
  "job_type": "<string>",
  "date_posted": "<ISO date or empty>",
  "visa_status": "<§9.1>",
  "visa_notes": "<string or null>",
  "queue_state": "PRIMARY | INTERNATIONAL_VERIFY | NOT_ACTIONABLE | AUDIT_ONLY",
  "provenance": {
    "sources": ["<source names>"],
    "source_job_ids": {"<source>": "<id or null>"},
    "discovery_query": "<query string>",
    "search_intent_id": "<intent_id>",
    "hypothesis_id": "<hypothesis_id>",
    "retrieved_at": "<ISO-8601>"
  }
}
```

### 12.2 Canonical Deduplication Strategy
- **Identity Key:** `(title.strip().lower(), company.strip().lower(), location.strip().lower())`
- **Merge Behavior:** Union `sources`, keep earliest `date_posted`, keep longest `description`, preserve first valid salary and URL.
- **Fuzzy Dedup Trigger:** RapidFuzz is deferred until audit shows >10% near-duplicate rate among evaluated jobs.

---

## 13. User Constraint Model

### 13.1 Configuration Contract (`config/constraints.json`)

```json
{
  "version": "1.0",
  "employment": {
    "excluded_title_keywords": [
      "intern", "internship", "trainee", "co-op", "apprentice",
      "part-time", "part time", "fellowship"
    ],
    "excluded_type_values": [
      "internship", "part-time", "temporary"
    ]
  },
  "recency": {
    "max_days": 30
  },
  "authorization": {
    "requires_sponsorship": true
  }
}
```

### 13.2 Deterministic Hard Gates
1. **Employment Type Gate:** Excludes internships, apprenticeships, part-time jobs.
2. **Recency Gate:** Excludes postings older than `max_days` (unknown dates pass).
3. **Visa Gate:** Excludes `visa_status: "unavailable"` when candidate `requires_sponsorship: true`. `visa_status: "unknown"` PASSES to `INTERNATIONAL_VERIFY`.

---

## 14. Discovery Iteration & Multi-Wave Model

### 14.1 Wave Lifecycle
- **Wave 1:** Baseline capability hypotheses → search intents → execution → dedup.
- **Coverage Analysis:** Check home-country coverage, unscoped discovery, source distribution.
- **Wave 2 (Conditional):** If unique results < `min_results` (default: 20) or coverage is unbalanced, generate gap-filling intents.
- **Stopping Conditions:** Marginal unique yield < 10%, wave limit (default: 3), or budget limit (`max_results`: 500).

---

## 15. Discovery Metrics

Persisted in `runs/<run-id>/discovery_metrics.json`:
- `hypotheses_generated`, `search_intents_generated`
- `source_requests`, `successful_source_requests`, `failed_source_requests`
- `raw_results`, `normalized_results`, `duplicates_removed`, `unique_results`
- `results_by_source`, `results_by_country`, `results_by_queue` (`PRIMARY`, `INTERNATIONAL_VERIFY`, `NOT_ACTIONABLE`)
- `visa_status_counts` (`not_required`, `available`, `unknown`, `unavailable`)
- `marginal_yield_per_wave`

---

## 16. Immutable Run Artifacts

```
runs/
  <run-id>/                         # Format: YYYYMMDD_HHMMSS
    config_snapshot.json            # Snapshot of candidate, objective, constraints, sources
    candidate_model.json            # Capability model
    opportunity_hypotheses.json     # Generated hypotheses
    search_intents.json             # Search intents
    search_plan.json                # Execution plan
    raw_jobs.json                   # Append-only raw scraped jobs
    normalized_jobs.json            # Deduplicated, normalized & queue-classified jobs
    discovery_metrics.json          # Metrics summary
```

---

## 17. LLM Evaluation Interface

- **Input:** `runs/<run-id>/normalized_jobs.json` filtered to `PRIMARY` and `INTERNATIONAL_VERIFY` queues.
- **Contract with `evaluate.py`:** Unchanged prompt, schema, scoring logic, and retry handlers. `evaluate.py` is invoked with `--jobs runs/<run-id>/normalized_jobs.json`.

---

## 18. Ranking & Presentation

- Ranked by `(recommendation_tier, -overall_score)`.
- Company diversification interleave on top 20 results.
- `PRIMARY` queue presented as default actionable view; `INTERNATIONAL_VERIFY` accessible via secondary view.

---

## 19. Golden Datasets & Regression Testing

### 19.1 Evaluation Golden Dataset
- Uses `human_review.json` to verify that `evaluate.py` evaluation score tiers remain consistent within ±1 tier.

### 19.2 Discovery Validation Dataset
- Independent deterministic test fixture with representative synthetic job payloads:
  - India job → `country_code: "IN"`, `visa_status: "not_required"`, `queue_state: "PRIMARY"`
  - US job + explicit sponsorship → `country_code: "US"`, `visa_status: "available"`, `queue_state: "PRIMARY"`
  - US job + no sponsorship mentioned → `country_code: "US"`, `visa_status: "unknown"`, `queue_state: "INTERNATIONAL_VERIFY"`
  - US job + explicit "no sponsorship" → `country_code: "US"`, `visa_status: "unavailable"`, `queue_state: "NOT_ACTIONABLE"`
  - Indianapolis, IN → `country_code: "US"`

---

## 20. Engineering Guardrails

1. **Inspect before edit:** Read entire file before modifying.
2. **Test before implement:** Write failing unit test first.
3. **No hardcoded taxonomies:** Zero domain, role, company, or country whitelist literals in code.
4. **Preserve working downstream code:** `evaluate.py`, `review_server.py`, `review_ui/`, and existing review data are sacred.
5. **Responsibility-driven modules:** Module boundaries reflect logical cohesion, not arbitrary line counts.
6. **Complexity warning signals:** >50 lines in a function or >500 lines in a file are review flags, not dogmatic slicing rules.

---

## 21. Legacy Code & Migration Strategy

| File / Component | Status | Action |
|------------------|:------:|--------|
| `evaluate.py` | KEEP | Minimal update (~5 lines) to accept `runs/` job path |
| `review_server.py`, `review_ui/` | LEAVE UNTOUCHED | Preserved for human review UI |
| `human_review.json`, `llm_evaluations_full.json` | LEAVE UNTOUCHED | Sacred human decisions & evaluation data |
| `tier1_jobs.json`, `jobs.json` | LEAVE UNTOUCHED | Historical baseline datasets |
| `scout.py` | DEPRECATE | Coexists during validation; archived after 3 successful runs of `discover.py` |
| `career_os/scoring/`, `evaluate_all.py` | DEPRECATE | Superseded by evaluate pipeline |
| `_gate_audit.py`, `debug_*.py` | REMOVE LATER | Dead scratch scripts; remove after implementation |

---

## 22. Module & File Implementation Plan

```
Career OS Root
├── config/
│   ├── candidate.json              [NEW] Candidate home_country & requested_geographies
│   ├── constraints.json            [NEW] Explicit deterministic constraints
│   ├── objective.json              [NEW] User career discovery objective
│   └── sources.json                [NEW] Source capability registry
├── career_os/
│   └── discovery/
│       ├── __init__.py             [NEW]
│       ├── candidate_model.py      [NEW] Capability model extraction from CV
│       ├── hypotheses.py           [NEW] Open-world hypothesis generation
│       ├── intents.py              [NEW] Search intent generation & planner
│       ├── router.py               [NEW] Capability-based source router
│       ├── adapters.py             [NEW] JobSpy/API source adapters
│       ├── normalizer.py           [NEW] Schema mapping & exact deduplication
│       ├── geography.py            [NEW] Token-aware location normalizer
│       ├── visa.py                 [NEW] Contextual visa/relocation analyzer
│       ├── gates.py                [NEW] Constraint & queue classification engine
│       └── metrics.py              [NEW] Metrics aggregation & run manager
├── discover.py                     [NEW] CLI entry point orchestrating discovery pipeline
├── evaluate.py                     [MODIFY] Support runs/<id>/normalized_jobs.json input (~5 lines)
└── tests/
    ├── test_geography.py           [NEW] 15 location normalization test cases
    ├── test_visa.py                [NEW] Contextual visa polarity test cases
    ├── test_gates.py               [NEW] Constraint gate & queue routing test cases
    ├── test_dedup.py               [NEW] Canonical deduplication test cases
    ├── test_router.py              [NEW] Source capability routing test cases
    └── test_golden.py              [NEW] Discovery validation & evaluation regression
```

---

## 23. Test Plan (Pre-Implementation)

1. **Test Geography (`test_geography.py`):**
   - Bengaluru, Gurugram, Mumbai → `IN`
   - Indianapolis, IN → `US` (Indiana state disambiguation)
   - New York, NY; Portland, OR → `US`
   - London, UK → `GB`; Singapore → `SG`; Dubai → `AE`
   - Remote India/US/Global/Alone → `IN`/`US`/`GLOBAL`/`UNKNOWN`
2. **Test Visa Context (`test_visa.py`):**
   - Explicit positive, explicit negative ("We do not sponsor"), conditional ("may be available in exceptional cases"), conflicting signals, home country `not_required`.
3. **Test Queue Classification (`test_gates.py`):**
   - Home country → `PRIMARY`
   - International + sponsorship → `PRIMARY`
   - International + sponsorship unknown → `INTERNATIONAL_VERIFY`
   - International + no sponsorship → `NOT_ACTIONABLE`
4. **Test Router & Isolation (`test_router.py`):**
   - Router uses geographic coverage; adapter failure in one source does not halt others.
5. **Test Deduplication (`test_dedup.py`):**
   - Exact identity key merging across sources; distinct roles at same company preserved.

---

## 24. Success Criteria

1. Candidate home country is configurable via `config/candidate.json` (defaults to `IN`).
2. Home-country search coverage is guaranteed.
3. Unscoped global discovery is supported without a hardcoded country list.
4. No domain, role, company, or target-country whitelists exist in code or prompts.
5. Indianapolis, IN is never parsed as India.
6. Visa sponsorship is contextually analyzed; "We do not sponsor" is parsed as `unavailable`.
7. International jobs with unknown sponsorship route to `INTERNATIONAL_VERIFY` (never silently dropped or cluttering `PRIMARY`).
8. Multiple sources operate independently with failure isolation.
9. Runs are 100% reproducible from `runs/<run-id>/` artifacts.
10. Downstream `evaluate.py`, `review_server.py`, and `human_review.json` are preserved.

---

## 25. DO NOT HARD-CODE List

The implementation agent MUST NOT hardcode:
- Career domains (fintech, payments, trading, risk, AI)
- Job titles (Product Manager, Product Owner, Analyst)
- Target companies
- Target countries or country whitelists (`["US", "UK", "SG", "DE"]`)
- Fixed ratios (e.g. "50% India / 50% US")
- Numeric hypothesis quotas

---

## 26. DO NOT BUILD YET List

- Cutshort / Greenhouse / Lever custom scrapers
- Fragile Workday / Instahyre / Wellfound scrapers
- RapidFuzz fuzzy deduplication (until >10% duplicate trigger is met)
- Vector DBs, LangChain, CrewAI, LangGraph
- Automated job application form fillers

---

## 27. Anti-Bloat Self-Audit

- **Code Replacement:** `discover.py` + modular components replace `scout.py`'s hardcoded queries and monolithic filters.
- **Zero Runtime Dependencies:** Built strictly on standard library + existing `jobspy` + `markitdown` + `requests`. Dev tools: `pytest`, `ruff`, `vulture`.
- **Complexity Reduction:** Eliminates 41 hardcoded keywords in `scout.py` and avoids hardcoded domains.

---

```
ARCHITECTURE STATUS: READY FOR IMPLEMENTATION
```
