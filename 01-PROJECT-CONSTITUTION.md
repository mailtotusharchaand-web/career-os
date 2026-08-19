# Career OS — Project Constitution

**Version:** 1.0  
**Date:** 2026-08-15  
**Status:** Active — Governs all architecture and engineering decisions

---

## 1. Mission

Build **Job Scout** — a practical, local-first AI job search assistant that helps individuals discover, evaluate, and apply to relevant jobs with minimal manual effort, while maintaining full data sovereignty.

---

## 2. Non-Negotiable Principles

### REUSE BEFORE BUILD (The Golden Rule)

For every capability, evaluate solutions in this order:

| Level | Source | When to Use |
|-------|--------|-------------|
| 0 | Existing API | Direct integration available |
| 1 | Existing SaaS/Tool | Configure, don't code |
| 2 | Existing MCP Server/Integration | Plug into agent workflow |
| 3 | Existing Open-Source Library | Import, extend minimally |
| 4 | Existing Open-Source Application | Fork/adapt, contribute back |
| 5 | Tiny Custom Glue Code | Only to connect L0-L4 |
| 6 | Build Ourselves | **Only when L0-L5 demonstrably fail** |

**Document the reason** whenever choosing Level 6.

### Valid Reasons to Build (Level 6)
- Existing solution is unreliable, abandoned, incompatible, excessively expensive, insecure, or legally unsuitable
- Proprietary differentiation that creates defensible user value

### Invalid Reasons to Build
- "Because we can"
- "Because it would be cleaner"
- "Because we want to own the stack"
- "Not invented here"

---

## 3. Product Scope — Job Scout (MVP)

### In Scope (Must Deliver)
1. **Candidate Input** — CV upload, career details entry
2. **Candidate Understanding** — LLM extracts skills, experience, preferences
3. **Job Discovery** — Multi-source search (APIs + scraping)
4. **Job Aggregation** — Normalize, deduplicate across sources
5. **Job Understanding** — Extract structured JD data
6. **Matching & Ranking** — LLM compares candidate vs job, scores 0-100
7. **Application URL** — Direct link to apply
8. **Application Materials** — Tailored CV, cover letter, answers on demand
9. **Interview Prep** — Questions generated per JD + company + candidate
10. **Application Tracking** — Local Kanban/status board
11. **Gmail/Outlook Monitoring** — Classify recruiter emails, auto-update status
12. **Notifications** — Alert when action needed
13. **Human Approval** — Every submission requires explicit user consent

### Out of Scope (Explicitly NOT Building)
- Custom resume parser (use LLM + existing libraries)
- Custom job matching engine (use LLM)
- Custom vector database (use LLM context)
- Custom RAG pipeline (use LLM context)
- Custom interview question database (generate on demand)
- Custom ATS / job board / social network
- Custom browser / search engine / email server
- Custom LLM
- Giant career knowledge graph

---

## 4. Architecture Constraints

| Constraint | Decision |
|------------|----------|
| **Frontend** | CLI-first (Claude Code / OpenCode / Codex); optional TUI later |
| **Backend** | None — logic lives in LLM prompts + n8n workflows |
| **Database** | Local files (JSON, SQLite, Google Sheets) — no managed DB |
| **Auth** | OAuth for external services only; no custom auth |
| **Hosting** | Local machine; n8n self-hosted or cloud |
| **LLM** | Multi-provider via OpenRouter; local via Ollama for privacy |
| **Browser** | Playwright MCP + Browser Use for automation |
| **Scraping** | Firecrawl API (cloud) or self-hosted; JobSpy library |

---

## 5. Privacy & Security Mandates

- **CV data never leaves user's machine** unless explicitly sent to LLM
- **Prefer local LLMs** (Ollama/Nemotron) for sensitive operations
- **No telemetry, no analytics, no accounts** by default
- **Credentials stored in OS keyring** or `.env` (gitignored)
- **Email access via OAuth** — tokens encrypted at rest
- **PII minimization** — strip identifiers before external API calls

---

## 6. Quality Gates

Before any code is written:
- [ ] Reuse audit completed for the capability
- [ ] Build vs Buy decision documented
- [ ] Privacy impact assessed
- [ ] Cost estimate at 10/50/100/500 jobs/day
- [ ] Integration test plan defined

Before any PR is merged:
- [ ] Lint passes
- [ ] Typecheck passes
- [ ] Integration test passes (or manual verification documented)

---

## 7. Decision Log Template

Every architectural decision must record:

```markdown
## Decision: [Title]
**Date:** YYYY-MM-DD
**Capability:** [e.g., Job Discovery]
**Options Considered:**
1. [Option A] — [Pros/Cons]
2. [Option B] — [Pros/Cons]
**Chosen:** [Option X]
**Level:** [0-6]
**Reason if Level 6:** [Specific justification]
**Revisit Trigger:** [When to re-evaluate]
```

---

## 8. Success Metrics (MVP)

| Metric | Target |
|--------|--------|
| Time to first relevant job list | < 2 minutes |
| Match score accuracy (user-rated) | > 80% |
| False positive rate (irrelevant jobs) | < 15% |
| Application material quality | User accepts > 70% without edits |
| Email classification accuracy | > 90% |
| Monthly cost at 50 jobs/day | < $20 |
| Setup time (new user) | < 15 minutes |

---

## 9. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-08-15 | Lead Architect | Initial constitution |

---

**This constitution supersedes all prior architectural discussions. Any deviation requires written justification in the Decision Log.**