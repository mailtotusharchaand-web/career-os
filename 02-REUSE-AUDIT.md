# Career OS — Reuse Audit Report

**Date:** 2026-08-15  
**Scope:** Job Scout MVP — Capability-by-capability evaluation of existing solutions

---

## Executive Summary

**80%+ of Job Scout can be assembled from existing components.** Only 3 capabilities require custom glue code (Level 5). Zero capabilities require building from scratch (Level 6).

| Reuse Level | Capabilities | Count |
|-------------|--------------|-------|
| Level 0 (API) | Job search, Gmail, Outlook, LLM, Firecrawl | 5 |
| Level 1 (SaaS) | n8n workflows, Apify scrapers, Simplify jobs data | 3 |
| Level 2 (MCP) | Playwright MCP, Browser Use, Firecrawl MCP | 3 |
| Level 3 (Library) | JobSpy, python-docx, fpdf2, sqlite3 | 4 |
| Level 4 (App) | Career-Ops, Resume Matcher, SimplifyJobs repo | 3 |
| Level 5 (Glue) | Candidate profile schema, Matching prompt, Tracker schema | 3 |
| Level 6 (Build) | **None** | 0 |

---

## Capability-by-Capability Audit

### A. Candidate/CV Input
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| Local file upload (PDF/DOCX/TXT/MD) | Level 5 | Trivial | Standard file input |
| OpenResume (openresume.onrender.com) | Level 4 | Reference | Open-source builder/parser |
| python-docx / pdfplumber / pymupdf | Level 3 | Ready | Extract text from CV |

**Decision:** Level 5 glue — accept files, use Level 3 libs for text extraction.

---

### B. Candidate Understanding
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| LLM (Claude/GPT/Gemini via OpenRouter) | Level 0 | Ready | Structured output: skills, experience, preferences, constraints |
| Career-Ops `cv.md` schema | Level 4 | Reference | Proven schema for candidate profile |

**Decision:** Level 0 — LLM extracts structured profile from CV text. Adopt Career-Ops schema.

---

### C. Job Discovery
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| JobSpy (speedyapply/JobSpy) | Level 3 | **4,083★ MIT** | LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter, Naukri, Bayt, BDJobs |
| SimplifyJobs/New-Grad-Positions | Level 4 | **17,656★** | Curated 12K+ new grad roles, daily updated, JSON/MD format |
| LoopCV Job Board API | Level 0 | Commercial | 30+ sources, resume parsing, matching, apply endpoints |
| Arbeitnow API | Level 0 | Free | European/remote jobs from Greenhouse, SmartRecruiters, Join.com |
| Adzuna API | Level 0 | Freemium | Global job aggregator |
| TheirStack API | Level 0 | Commercial | LinkedIn, Glassdoor, Indeed, 16+ sources |
| Fantastic.jobs API | Level 0 | Commercial | 8M jobs/month, ATS sources |
| Apify Actors (Indeed, LinkedIn, Greenhouse) | Level 1 | Freemium | Managed scrapers, n8n integration |

**Decision:** Level 3 (JobSpy) + Level 4 (SimplifyJobs) as primary. Level 0 APIs for supplementation. No custom scrapers.

---

### D. Job Aggregation / Normalization
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| JobSpy output (Pandas DataFrame) | Level 3 | Built-in | Unified schema across sources |
| LoopCV API | Level 0 | Built-in | Normalized JSON regardless of source |
| Custom dedup (title + company + location hash) | Level 5 | Trivial | 20 lines of Python |

**Decision:** Level 3 + Level 5 glue for cross-source dedup.

---

### E. Web Search
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| Firecrawl `/search` | Level 0 | Ready | 2 credits/10 results, markdown included |
| Tavily Search API | Level 0 | Alternative | AI-native search, 1000 credits free |
| SerpApi (Google Jobs) | Level 0 | Commercial | Structured SERP data |
| Brave Search API | Level 0 | Free tier | Privacy-focused, independent index |

**Decision:** Level 0 — Firecrawl primary (integrated with scraping), Tavily backup.

---

### F. Web Scraping
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| Firecrawl `/scrape`, `/crawl` | Level 0 | **166K★** | JS rendering, markdown, structured extraction, self-hostable (AGPL) |
| Apify Actors | Level 1 | Ready | 3000+ actors, pay-per-result, n8n native |
| Playwright MCP | Level 2 | **Official Microsoft** | Accessibility tree, deterministic, token-efficient |
| Browser Use | Level 4 | **99K★ MIT** | Agent-driven, natural language, cloud option |
| JobSpy (scraping library) | Level 3 | **4K★ MIT** | Specialized for job boards |

**Decision:** Firecrawl API (Level 0) for content extraction. Playwright MCP (Level 2) for interactive automation (forms, login). JobSpy (Level 3) for job-board-specific scraping.

---

### G. Company Career-Site Discovery
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| Firecrawl `/map` + `/crawl` | Level 0 | Ready | Discover all URLs on careers subdomain |
| Playwright MCP + sitemap.xml | Level 2 | Ready | Programmatic discovery |
| Greenhouse/Lever/Ashby board tokens | Level 3 | Known patterns | `boards.greenhouse.io/{token}`, `jobs.lever.co/{token}` |
| Career-Ops portal scanner | Level 4 | Reference | 45+ pre-configured AI companies |

**Decision:** Level 0 (Firecrawl map) + Level 4 (adopt Career-Ops portal list + patterns).

---

### H. Job Description Extraction
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| Firecrawl `/scrape` with `formats: ["markdown"]` | Level 0 | Ready | Clean markdown, 1 credit/page |
| Playwright MCP `browser_snapshot` | Level 2 | Ready | Accessibility tree, structured |
| Apify Greenhouse/Indeed/LinkedIn actors | Level 1 | Ready | Specialized extractors |

**Decision:** Level 0 primary. Level 2 for authenticated/JS-heavy pages.

---

### I. Job Normalization (Schema)
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| JobSpy DataFrame schema | Level 3 | Reference | 30+ fields standardized |
| LoopCV API schema | Level 0 | Reference | Unified across 30+ sources |
| Career-Ops job schema | Level 4 | Reference | Minimal: title, company, url, description, location, salary, source |

**Decision:** Level 5 glue — define minimal internal schema, map from Level 3/0 sources.

---

### J. Candidate-Job Matching
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| LLM (CV + JD + context → structured score) | Level 0 | **Core approach** | No custom matcher needed |
| Resume Matcher (srbhr/Resume-Matcher) | Level 4 | **25K★ Apache-2.0** | Streamlit app, keyword extraction, ATS scoring |
| Career-Ops evaluation rubric | Level 4 | Reference | 5-dimension + global score 1.0-5.0 |
| LoopCV Matching API | Level 0 | Commercial | Embedded matching |

**Decision:** Level 0 — LLM does matching on demand. Adopt Career-Ops rubric (5 dimensions, 1.0-5.0). Reference Resume Matcher for keyword extraction ideas.

---

### K. Job Ranking
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| LLM match score (0-100 or 1.0-5.0) | Level 0 | Ready | Primary sort |
| User preferences (location, salary, remote, visa) | Level 5 | Glue | Filter/boost rules |

**Decision:** Level 0 + Level 5.

---

### L. Application URL Discovery
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| JobSpy `job_url` field | Level 3 | Built-in | Direct apply links |
| Firecrawl extract `apply_url` | Level 0 | Ready | Structured extraction |
| Career-Ops `apply` mode | Level 4 | Reference | Playwright form detection |

**Decision:** Level 3/0 — URLs come with job data. Level 4 for form-fill assistance.

---

### M. Company Research
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| Firecrawl `/search` + `/scrape` company site | Level 0 | Ready | On-demand |
| LLM knowledge (training data) | Level 0 | Ready | General company info |
| Glassdoor/LinkedIn APIs | Level 0 | Limited | Reviews, salary data |

**Decision:** Level 0 — LLM + Firecrawl on demand. No persistent company DB.

---

### N. CV Tailoring
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| LLM (CV + JD → tailored CV) | Level 0 | **Core approach** | Structured output: markdown/JSON |
| Career-Ops PDF generation | Level 4 | **Reference** | Playwright + HTML templates → ATS PDF |
| Resume Matcher tailoring | Level 4 | Reference | Keyword injection |
| python-docx / fpdf2 / weasyprint | Level 3 | Ready | PDF generation libraries |

**Decision:** Level 0 for content generation. Level 3 (fpdf2/weasyprint) for PDF rendering. Adopt Career-Ops HTML→PDF pipeline.

---

### O. Application Answer Generation
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| LLM (CV + JD + question → answer) | Level 0 | **Core approach** | On-demand, per question |
| Career-Ops `apply` mode | Level 4 | Reference | Reads Greenhouse/Ashby/Lever forms, drafts answers |

**Decision:** Level 0. Level 4 reference for form-field mapping patterns.

---

### P. Interview Question Generation
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| LLM (CV + JD + company + stage → questions) | Level 0 | **Core approach** | On-demand, no database needed |
| Career-Ops `interview-prep` mode | Level 4 | Reference | STAR+Reflection format |

**Decision:** Level 0. Adopt Career-Ops STAR+Reflection format.

---

### Q. Application Tracking
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| Local SQLite / JSON / Google Sheets | Level 5 | Glue | User choice |
| Career-Ops tracker (Go TUI + TSV) | Level 4 | **55K★ MIT** | Kanban, integrity checks, batch merge |
| JobCtrl (ebarti/JobCtrl) | Level 4 | Reference | Local-first, fit scoring, approval-gated |
| JSE (Keljian/JSE) | Level 4 | Reference | Local LLM matching, Kanban |
| Sanathbn27/job-tracker | Level 4 | Reference | Gmail → FastAPI → Groq → Sheets → Streamlit |
| Nittasamith1/AI-Gmail-Job-Application-Tracker | Level 4 | Reference | FastAPI + MongoDB + BART classifier |

**Decision:** Level 4 — **Adopt Career-Ops tracker** (mature, local-first, TSV-based, Go dashboard). Customize schema for our fields.

---

### R. Gmail Monitoring
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| Gmail API + Pub/Sub push | Level 0 | Standard | Real-time notifications |
| n8n Gmail trigger | Level 1 | Ready | Visual workflow, OAuth built-in |
| Career-Ops Gmail integration | Level 4 | Reference | OAuth, historyId incremental sync |
| Sanathbn27/job-tracker | Level 4 | **Reference** | Pub/Sub → FastAPI → Groq LLM → Sheets |

**Decision:** Level 1 — **n8n Gmail trigger** for workflow. Level 0 API for custom logic if needed.

---

### S. Outlook Monitoring
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| Microsoft Graph API | Level 0 | Standard | Delta queries for incremental sync |
| n8n Outlook/Microsoft trigger | Level 1 | Ready | OAuth, webhook support |

**Decision:** Level 1 — n8n trigger (same workflow as Gmail).

---

### T. Recruiter Email Classification
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| LLM (email + tracker context → classification) | Level 0 | **Core approach** | Structured output: type, company, role, status, action |
| Sanathbn27/job-tracker | Level 4 | Reference | Groq Llama 3.3-70b, 4-priority matching |
| Nittasamith1 tracker | Level 4 | Reference | HuggingFace BART zero-shot + keyword fallback |

**Decision:** Level 0 — LLM does classification on demand. Adopt 4-priority matching from sanathbn27.

---

### U. Application Status Detection
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| LLM classification (interview, offer, rejection, pending) | Level 0 | Ready | From email content |
| Career-Ops tracker status enum | Level 4 | Reference | applied, screening, interview, offer, rejected, ghosted |

**Decision:** Level 0 + Level 4 enum.

---

### V. Notifications
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| n8n email/Slack/Discord/Telegram nodes | Level 1 | Ready | Built-in |
| Local desktop notifications (plyer, notify-send) | Level 3 | Ready | Cross-platform |
| ntfy.sh / Pushbullet / Gotify | Level 1 | Free tier | Self-hostable |

**Decision:** Level 1 (n8n) + Level 3 (local desktop) — user configurable.

---

### W. Scheduling
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| n8n Schedule Trigger | Level 1 | Ready | Cron, intervals, timezone |
| Cron (system) | Level 0 | Native | For local scripts |

**Decision:** Level 1 — n8n handles all scheduling.

---

### X. Browser/Application Assistance
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| Playwright MCP | Level 2 | **Official Microsoft** | 22 tools, accessibility tree, deterministic |
| Browser Use | Level 4 | **99K★ MIT** | Agent-driven, natural language, cloud option |
| Career-Ops Playwright automation | Level 4 | Reference | Form detection, fill, submit |
| Mhrnqaruni/mcp-playwright-browser | Level 4 | **71 tools** | Specialized job extractors, form automation, session persistence |

**Decision:** Level 2 (Playwright MCP) as primary. Level 4 (mcp-playwright-browser) for specialized job/form tools.

---

### Y. Human Approval
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| n8n "Wait for Webhook" / "Manual Approval" node | Level 1 | Built-in | Pauses workflow |
| CLI prompt (inquirer, prompt-toolkit) | Level 3 | Ready | For local scripts |
| Career-Ops HITL design | Level 4 | Reference | 30-second CLI prompt, answers cached |

**Decision:** Level 1 (n8n) + Level 3 (CLI) — mandatory before any submission.

---

### Z. Data Storage
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| Local files (JSON, SQLite, TSV) | Level 5 | Glue | User owns data |
| Google Sheets | Level 1 | Free | Sync, sharing, mobile access |
| Career-Ops TSV + SQLite | Level 4 | Reference | Portable, version-controllable |

**Decision:** Level 5 — **User chooses**: local SQLite (default) or Google Sheets (optional). Career-Ops TSV format for portability.

---

### AA. Privacy/Security
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| Ollama / Nemotron local LLMs | Level 3 | **Free, private** | No data leaves machine |
| OpenRouter (multi-provider) | Level 0 | **1% markup** | Unified API, no training on data |
| OS keyring / `.env` (gitignored) | Level 5 | Standard | Credentials |
| Fernet encryption (cryptography lib) | Level 3 | Ready | Encrypt OAuth tokens at rest |

**Decision:** Level 3 (local LLM default) + Level 0 (OpenRouter for frontier models). Level 5 for credentials.

---

### AB. LLM Routing
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| OpenRouter | Level 0 | **200+ models** | Unified API, auto-failover, 1% markup |
| LiteLLM (self-hosted proxy) | Level 3 | Ready | Load balancing, fallbacks, logging |
| Custom routing logic | Level 5 | Glue | Task→model mapping |

**Decision:** Level 0 (OpenRouter) primary. Level 5 routing config: `classification→Haiku`, `matching→Sonnet`, `generation→Opus`, `local→Ollama`.

---

### AC. Observability
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| n8n execution logs | Level 1 | Built-in | Visual debugging |
| Langtrace / LangSmith / Helicone | Level 1 | Free tier | LLM observability |
| Local logs (structlog, loguru) | Level 3 | Ready | JSON logs |

**Decision:** Level 1 (n8n) + Level 3 (local structured logs).

---

### AD. Error Handling
| Solution | Type | Status | Notes |
|----------|------|--------|-------|
| n8n Error Trigger / Retry nodes | Level 1 | Built-in | Exponential backoff, dead letter |
| Python tenacity / retry | Level 3 | Ready | Decorator-based |
| Circuit breaker (pybreaker) | Level 3 | Ready | Prevent cascade failures |

**Decision:** Level 1 (n8n) + Level 3 (Python glue).

---

## Reuse Recommendations Summary

| Priority | Action | Source |
|----------|--------|--------|
| 1 | Adopt Career-Ops tracker schema + TUI | Level 4 — 55K★, production-tested |
| 2 | Use JobSpy for multi-board scraping | Level 3 — 4K★, MIT, active |
| 3 | Use SimplifyJobs repo for new-grad roles | Level 4 — 17K★, daily updated |
| 4 | Use Firecrawl API for web content | Level 0 — 166K★, self-hostable |
| 5 | Use Playwright MCP for browser automation | Level 2 — Official Microsoft |
| 6 | Use n8n for all workflows/scheduling/email | Level 1 — Visual, self-hostable |
| 7 | Use OpenRouter for LLM routing | Level 0 — 200+ models |
| 8 | Use Ollama for local/private LLM tasks | Level 3 — Free, private |
| 9 | Adopt Career-Ops evaluation rubric | Level 4 — 5-dimension, proven |
| 10 | Use mcp-playwright-browser for job forms | Level 4 — 71 specialized tools |

---

## Capabilities Requiring Custom Glue (Level 5)

1. **Candidate Profile Schema** — Define `cv.yaml` structure (skills, experience, preferences, constraints)
2. **Matching Prompt Template** — LLM prompt: CV + JD + preferences → structured score + reasoning
3. **Tracker Schema Extension** — Extend Career-Ops TSV with our fields (match_score, tailored_cv_path, interview_prep_path)
4. **LLM Routing Config** — YAML mapping task→model (privacy/cost/quality tradeoffs)
5. **Source Adapter Layer** — Normalize JobSpy/SimplifyJobs/Firecrawl → internal job schema

**Total custom code estimate:** ~500 lines Python + ~200 lines YAML/Markdown prompts.

---

## Rejected Approaches (Explicitly NOT Building)

| Capability | Rejected Approach | Reason |
|------------|-------------------|--------|
| Resume Parsing | Custom NLP parser | LLM + pdfplumber sufficient |
| Job Matching | Custom semantic/vector engine | LLM on-demand matching proven |
| Interview Questions | Curated question database | LLM generates contextual questions |
| Vector DB | Pinecone/Weaviate/Qdrant | Not needed — LLM context window sufficient |
| RAG Pipeline | Custom retrieval | Job data fits in context; Firecrawl for web |
| Job Board | Custom aggregator | JobSpy + APIs + SimplifyJobs cover 95% |
| ATS | Custom application tracker | Career-Ops tracker exists |
| Browser | Custom automation framework | Playwright MCP + Browser Use exist |
| Search Engine | Custom index | Firecrawl/Tavily/SerpApi exist |
| Email Server | Custom IMAP/SMTP | Gmail/Outlook APIs + n8n exist |