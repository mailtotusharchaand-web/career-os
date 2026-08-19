# Career OS — Application Queue Specification

**Version:** 0.1  
**Date:** 2026-08-16  
**Status:** Draft — For Implementation

---

## 1. Purpose

The **Application Queue** bridges the gap between job evaluation and actual application submission. It transforms "I want to apply" into a structured, auditable, human-reviewed workflow that can eventually feed outcome data back into the scoring model.

**Core principle:** The queue is a **decision-support tool**, not an auto-apply bot. Every submission requires explicit human approval.

---

## 2. Queue Entry (Application Card)

Each job that reaches the queue becomes an **Application Card** — a structured record containing everything needed to review, complete, and submit an application.

### JSON Schema

```json
{
  "application_id": "app_20260816_0001",
  "job": {
    "job_id": "job_abc123",
    "title": "Product Manager, Ecosystem Risk",
    "company": "Stripe",
    "location": "New York, NY, US",
    "source": "linkedin",
    "application_url": "https://www.linkedin.com/jobs/view/4454544359",
    "application_type": "linkedin_easy_apply",
    "date_posted": "2026-08-14",
    "salary_min": null,
    "salary_max": null,
    "salary_interval": "",
    "is_remote": false,
    "eligibility": "us_onsite"
  },
  "match": {
    "overall_score": 72,
    "category": "B",
    "role_fit": 85,
    "seniority_fit": 70,
    "domain_fit": 95,
    "experience_fit": 70,
    "skill_fit": 65,
    "location_fit": 60,
    "why_it_matches": "Product role + Risk domain + top-tier fintech. Senior PM stretch but domain compensates.",
    "major_gaps": "Senior PM stretch, US on-site",
    "recommendation": "Worth considering - good domain match, minor gaps in seniority/location"
  },
  "candidate": {
    "cv_version": "Tushar_PM_Fintech_v3.pdf",
    "cv_hash": "sha256:abc123...",
    "cover_letter_version": "cover_stripe_v1.md",
    "cover_letter_hash": "sha256:def456..."
  },
  "application_questions": [
    {
      "question_id": "q_001",
      "question_text": "Do you have payments experience?",
      "question_type": "boolean",
      "required": true,
      "detected_from": "ats_form",
      "career_os_answer": {
        "answer": "Yes",
        "confidence": 0.98,
        "evidence": [
          "Payments Product Manager at Amex (Jan 2023–Present)",
          "Dispute/chargeback workflows on CLIC platform",
          "RBST/PBST compliance for payments cases"
        ],
        "needs_user_review": false
      }
    },
    {
      "question_id": "q_002",
      "question_text": "Do you have risk/compliance experience?",
      "question_type": "boolean",
      "required": true,
      "detected_from": "ats_form",
      "career_os_answer": {
        "answer": "Yes",
        "confidence": 0.99,
        "evidence": [
          "RBST/PBST compliance ownership at Amex",
          "250K-300K monthly case flows validated",
          "Belgium KYC automation rollout (3-system)",
          "40+ pre-launch defects caught"
        ],
        "needs_user_review": false
      }
    },
    {
      "question_id": "q_003",
      "question_text": "Years of product management experience?",
      "question_type": "numeric",
      "required": true,
      "detected_from": "ats_form",
      "career_os_answer": {
        "answer": "3",
        "confidence": 0.82,
        "evidence": [
          "Associate Digital PM at Amex: Jan 2023–Present (~2.5 years)",
          "Product ownership in Independent Initiative: Jun–Jul 2026",
          "Amazon analyst role had product-adjacent work: Aug 2020–Dec 2022"
        ],
        "needs_user_review": true,
        "user_guidance": "Direct PM title ~2.5 years. Adjacent experience ~5 years. You decide how to represent."
      }
    },
    {
      "question_id": "q_004",
      "question_text": "Are you authorized to work in the US?",
      "question_type": "boolean",
      "required": true,
      "detected_from": "ats_form",
      "career_os_answer": {
        "answer": null,
        "confidence": 0,
        "evidence": [],
        "needs_user_review": true,
        "user_guidance": "Career OS cannot determine visa status. You must answer this."
      }
    },
    {
      "question_id": "q_005",
      "question_text": "Will you require visa sponsorship?",
      "question_type": "boolean",
      "required": true,
      "detected_from": "ats_form",
      "career_os_answer": {
        "answer": null,
        "confidence": 0,
        "evidence": [],
        "needs_user_review": true,
        "user_guidance": "Career OS cannot determine visa status. You must answer this."
      }
    }
  ],
  "status": "pending_review",
  "status_history": [
    {
      "status": "queued",
      "timestamp": "2026-08-16T15:30:00Z",
      "source": "llm_evaluation"
    },
    {
      "status": "pending_review",
      "timestamp": "2026-08-16T15:30:05Z",
      "source": "user_action"
    }
  ],
  "created_at": "2026-08-16T15:30:00Z",
  "updated_at": "2026-08-16T15:30:05Z",
  "user_decisions": {},
  "submission": null
}
```

---

## 3. Application Question Types

| Type | Description | Example |
|------|-------------|---------|
| `boolean` | Yes/No | "Are you authorized to work in the US?" |
| `choice` | Single select from options | "Years of experience: 0-1, 2-3, 4-5, 5+" |
| `multi_choice` | Multiple select | "Which tools: Jira, Confluence, Rally, Other" |
| `numeric` | Number input | "Years of PM experience" |
| `text_short` | Short text (< 200 chars) | "Describe a challenging project" |
| `text_long` | Long text (200+ chars) | "Cover letter / essay question" |
| `date` | Date input | "Earliest start date" |
| `salary` | Salary expectation | "Expected annual compensation" |
| `file_upload` | Resume, portfolio, etc. | "Upload portfolio" |

---

## 4. Question Detection & Answering Pipeline

```
Job Application Page (HTML)
         │
         ▼
   Question Extractor (LLM + DOM parsing)
         │
         ▼
   Question Classification (type, required, context)
         │
         ▼
   Answer Generator (per question)
         │
         ├───▶ Known Answer (high confidence, evidence-based) ──▶ Auto-fill
         ├───▶ Review Needed (medium confidence, ambiguous) ──▶ User review
         └───▶ Ask User (no confidence, personal/legal) ──▶ Mandatory user input
```

### Confidence Thresholds

| Confidence | Action |
|------------|--------|
| ≥ 0.90 | Auto-fill, show evidence, allow override |
| 0.70 – 0.89 | Pre-fill, flag for review |
| < 0.70 | Leave blank, require user input |
| N/A (personal/legal) | Mandatory user input |

---

## 5. Application Status Lifecycle

```
queued
    │
    ▼ (user opens queue)
pending_review
    │
    ├─▶ user answers pending questions
    │
    ├─▶ user reviews auto-filled answers
    │
    ▼ (user clicks "Prepare Application")
ready_to_submit
    │
    ▼ (user clicks "Open Application Page")
handoff_initiated
    │
    ▼ (browser opens, data pre-filled via handoff)
awaiting_user_submission
    │
    ▼ (user clicks submit on ATS page)
submitted
    │
    ▼ (user confirms in Career OS)
application_complete
```

### Status Definitions

| Status | Meaning | Next Action |
|--------|---------|-------------|
| `queued` | Added to queue, not yet reviewed | User opens queue |
| `pending_review` | Questions need answers, auto-fills need review | User answers/reviews |
| `ready_to_submit` | All questions answered, user approved | User initiates handoff |
| `handoff_initiated` | Browser opened, data injected | User submits on ATS |
| `awaiting_user_submission` | Waiting for user to click submit | User submits |
| `submitted` | User confirmed submission | Track outcome |
| `application_complete` | Outcome recorded (response/interview/reject) | Archive |
| `withdrawn` | User decided not to apply | Archive |
| `expired` | Job posting closed/removed | Archive |

---

## 5. Storage

### File Structure

```
~/career-os/
├── queue/
│   ├── index.json                 # List of all application_ids + status
│   ├── pending_review/            # Symlinks or copies for quick access
│   ├── ready_to_submit/
│   ├── submitted/
│   └── archive/
├── applications/
│   └── app_20260816_0001.json     # Full application card
├── documents/
│   ├── cv/
│   │   ├── Tushar_PM_Fintech_v3.pdf
│   │   └── Tushar_PM_Fintech_v3.json
│   └── cover_letters/
│       ├── cover_stripe_v1.md
│       └── cover_stripe_v1.json
└── question_bank/
    └── common_questions.json      # Cached question patterns
```

### Index Format (`queue/index.json`)

```json
{
  "applications": [
    {
      "application_id": "app_20260816_0001",
      "job_title": "Product Manager, Ecosystem Risk",
      "company": "Stripe",
      "status": "pending_review",
      "match_score": 72,
      "category": "B",
      "created_at": "2026-08-16T15:30:00Z",
      "application_url": "https://www.linkedin.com/jobs/view/4454544359",
      "application_type": "linkedin_easy_apply"
    }
  ],
  "summary": {
    "total": 12,
    "pending_review": 3,
    "ready_to_submit": 5,
    "submitted": 2,
    "application_complete": 2
  }
}
```

---

## 6. Integration Points

| Module | Interface |
|--------|-----------|
| **Job Scout** | Emits `evaluated_jobs` with `category A/B` → Queue ingestion |
| **Candidate OS** | Provides `cv`, `cover_letter`, `profile` for auto-fill |
| **LLM Question Engine** | Consumes `job.description + application_page` → produces `application_questions[]` |
| **Handoff Layer** | Consumes `application_questions[] + user_decisions` → injects into browser |
| **Outcome Tracker** | Updates `status` → `application_complete` with outcome |

---

## 7. MVP Scope (First Implementation)

### In Scope
- [ ] Queue data model (JSON schema + file storage)
- [ ] `queue add <job_id>` CLI command
- [ ] `queue list` with status filters
- [ ] `queue show <app_id>` — display card
- [ ] `queue review <app_id>` — interactive question review
- [ ] Question detection from saved job descriptions (no live scraping)
- [ ] Answer generation with evidence + confidence
- [ ] Question review TUI (text-based)
- [ ] `queue handoff <app_id>` — opens URL in browser

### Out of Scope (Defer)
- Live DOM question extraction from ATS pages
- Auto-form-fill injection (credential-free handoff only)
- LinkedIn OAuth / session management
- Outcome tracking (Gmail/Outlook integration)
- Multi-device queue sync
- Team/shared queue

---

## 8. CLI Interface (Proposed)

```bash
# Add evaluated job to queue
career-os queue add --job-id job_abc123 --score 72 --category B

# List queue
career-os queue list --status pending_review
career-os queue list --status ready_to_submit

# Review specific application
career-os queue review app_20260816_0001

# Open application page (handoff)
career-os queue handoff app_20260816_0001

# Mark as submitted
career-os queue submit app_20260816_0001

# Update outcome
career-os queue outcome app_20260816_0001 --result response --stage screening
```

---

## 9. Questions for Next Design Review

1. **Question deduplication**: Should common questions across applications be cached in `question_bank/` and answers reused?
2. **Cover letter generation**: Integrated here or separate module?
3. **CV versioning**: How many tailored CVs to keep per application?
4. **Duplicate application prevention**: Check if already applied (Gmail/Outcome tracker)?
5. **Deadline tracking**: Jobs with `date_posted` > 30 days → auto-expire?

---

## 9. Dependencies

| Dependency | Purpose |
|------------|---------|
| `question_bank/common_questions.json` | Cached question patterns for faster detection |
| `documents/cv/*.pdf` | Resume files for upload |
| `documents/cover_letters/*.md` | Cover letters for text fields |
| `evaluated_jobs.json` | Source of truth for job metadata |
| `candidate_profile.json` | Skills, experience for answer generation |