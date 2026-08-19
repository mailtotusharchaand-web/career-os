# Career OS — Architecture Options

**Date:** 2026-08-15  
**Goal:** Minimal architecture delivering CV → Job Discovery → Matching → Application Queue → Gmail Monitoring

---

## Design Principle

**Design around user outcomes, not technologies.**

User Outcome | Architecture Implication
--- | ---
"Give me relevant jobs now" | Scheduled discovery → local cache → instant UI
"Show me why I match" | LLM reasoning on-demand, not pre-computed index
"Generate my application materials" | LLM generation on-demand, not template library
"Track my applications" | Local-first, user-owned data, portable format
"Alert me when something happens" | Email webhook → LLM classification → notification

---

## Architecture Option 1: n8n-Centric (RECOMMENDED)

### Overview
```
┌─────────────────────────────────────────────────────────────────┐
│                        USER MACHINE                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Claude     │  │    n8n       │  │   SQLite /   │          │
│  │   Code /     │  │  (self-      │  │  Google      │          │
│  │   OpenCode   │  │   hosted)    │  │  Sheets      │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│         ▼                 ▼                 ▼                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    LOCAL FILESYSTEM                       │  │
│  │  cv.yaml  jobs.db  tracker.tsv  tailored_cvs/  logs/     │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────────┐ ┌───────────────┐ ┌───────────────┐
│   OLLAMA        │ │  OPENROUTER   │ │  FIRECRAWL    │
│  (Local LLMs)   │ │  (Cloud LLMs) │ │  (Cloud/API)  │
└─────────────────┘ └───────────────┘ └───────────────┘
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────────┐ ┌───────────────┐ ┌───────────────┐
│  PLAYWRIGHT     │ │   GMAIL/      │ │  JOBSPY       │
│  MCP + BROWSER  │ │   OUTLOOK     │ │  (Library)    │
│  USE            │ │   (OAuth)     │ │               │
└─────────────────┘ └───────────────┘ └───────────────┘
```

### Component Mapping

| Layer | Technology | Responsibility |
|-------|------------|----------------|
| **Orchestration** | n8n (self-hosted Docker) | All workflows: scheduling, email triggers, API calls, branching, retries, notifications |
| **User Interface** | Claude Code / OpenCode / Codex | Chat-based control, CV review, job review, material approval |
| **Local Intelligence** | Ollama (Llama 3.2 3B, 3.3 70B, Nemotron) | CV parsing, email classification, matching (privacy-first) |
| **Cloud Intelligence** | OpenRouter (Sonnet, Opus, GPT-4o, Gemini) | CV tailoring, cover letters, interview prep, company research |
| **Browser Automation** | Playwright MCP + Browser Use + mcp-playwright-browser | Form filling, authenticated scraping, career site discovery |
| **Job Scraping** | JobSpy (Python lib) + SimplifyJobs (GitHub sync) | Multi-board scraping, curated new-grad data |
| **Web Content** | Firecrawl API (→ self-host if scale) | JD extraction, company research, web search |
| **Email** | n8n Gmail/Outlook nodes (OAuth) | Push notifications, incremental sync |
| **Storage** | SQLite (default) / Google Sheets (optional) | Jobs, tracker, cache, user data |
| **Document Gen** | fpdf2 / weasyprint (Python) | ATS-compliant PDF from HTML/markdown |

### Data Flow: Core Loop

```
1. SCHEDULED (n8n cron: every 4 hours)
   → JobSpy.scrape_jobs(site_name=[indeed, linkedin, glassdoor, google, zip_recruiter])
   → SimplifyJobs git pull (new grad)
   → Firecrawl /search (custom queries)
   → Adapter → normalize → SQLite jobs table
   → Dedup (hash: title+company+location)

2. ON-DEMAND (User: "find me jobs")
   → Query SQLite (filtered by preferences)
   → For each job: Ollama.match(cv.yaml, job, prefs) → score + reasoning
   → Rank → Present top 20 in Claude Code

3. USER SELECTS JOB
   → OpenRouter.generate_tailored_cv(cv.yaml, job) → markdown
   → fpdf2 → tailored_cvs/job_123.pdf
   → OpenRouter.generate_cover_letter(cv.yaml, job) → markdown
   → OpenRouter.generate_answers(cv.yaml, job, questions) → JSON
   → OpenRouter.generate_interview_prep(cv.yaml, job, company) → markdown
   → All saved to tracker.tsv + SQLite

4. APPLICATION
   → User clicks job.apply_url
   → Optional: Playwright MCP assists form fill (HITL)
   → User submits → updates tracker status="applied"

5. EMAIL MONITORING (n8n Gmail/Outlook webhook)
   → New email → Ollama.classify(email, tracker_context) → {type, company, role, status, action}
   → 4-priority match to tracker entry
   → Auto-update tracker status
   → n8n notification (email/Slack/desktop)
```

### n8n Workflow Inventory

| Workflow | Trigger | Key Nodes | Output |
|----------|---------|-----------|--------|
| **Job Discovery** | Cron (4h) | JobSpy (Execute Command) → SimplifyJobs (Git) → Firecrawl (HTTP) → Adapter (Function) → SQLite (Custom) | Updated jobs.db |
| **Job Matching** | Webhook (from Claude Code) | SQLite (Select) → Ollama (HTTP Request) → Function (rank) → Respond | Ranked jobs |
| **Material Generation** | Webhook (from Claude Code) | OpenRouter (HTTP) → fpdf2 (Execute Command) → SQLite/TSV (Update) | PDFs, markdown |
| **Email Sync** | Gmail/Outlook Trigger | Ollama (HTTP) → Matcher (Function) → SQLite (Update) → Notification (Send) | Updated tracker |
| **Scheduled Cleanup** | Cron (daily) | SQLite (Delete old) → File cleanup (Execute Command) | Maintenance |

---

## Architecture Option 2: Pure Python CLI (Alternative)

### Overview
Replace n8n with APScheduler + custom Python scripts. More control, more code.

```
User CLI (typer/click) → Scheduler (APScheduler) → Workers (asyncio)
    → JobSpy, Firecrawl, Ollama, OpenRouter, Playwright, Gmail API
    → SQLite + TSV tracker
    → Notifications (plyer, ntfy.sh)
```

### Trade-offs

| Factor | n8n-Centric | Pure Python |
|--------|-------------|-------------|
| **Code to write** | ~500 lines (glue + prompts) | ~2000 lines (scheduler, workers, retry, UI) |
| **Visual debugging** | Built-in | Custom |
| **Non-dev usability** | High (visual workflows) | Low (CLI only) |
| **Reliability** | n8n handles retries/DLQ | Must implement |
| **Email triggers** | Native nodes | Custom Pub/Sub handling |
| **Extensibility** | Add nodes | Add Python modules |

**Verdict:** n8n-centric preferred. Less code, better observability, easier for non-dev users.

---

## Architecture Option 3: Local-First with Cloud Sync (Future)

Add optional cloud backup/sync for multi-device.

```
Local (Option 1) ↔ Encrypted sync (Syncthing / Rclone / custom) ↔ Remote (VPS / Cloud)
```

**Defer to post-MVP.** MVP is single-device local-first.

---

## Minimal MVP Architecture (What We Actually Build)

### We USE (Off-the-shelf)
- n8n (Docker compose)
- Ollama (Docker / native)
- Playwright MCP (npm)
- Browser Use (uv/pip)
- JobSpy (pip)
- Firecrawl API (SaaS)
- OpenRouter API (SaaS)
- SQLite / Google Sheets
- fpdf2 / weasyprint (pip)

### We CONFIGURE
- n8n workflows (5 core workflows)
- Ollama models (pull Llama 3.2 3B, 3.3 70B, Nemotron)
- Playwright MCP + mcp-playwright-browser in Claude Code/OpenCode
- Gmail/Outlook OAuth in n8n
- Firecrawl API key
- OpenRouter API key
- SimplifyJobs git repo clone + cron pull

### We ADAPT
- Career-Ops tracker schema (TSV + SQLite) → extend with our fields
- Career-Ops evaluation rubric (5 dimensions) → adopt as matching prompt
- Career-Ops portal list (45 companies) → add to Firecrawl map targets
- n8n workflow templates (12014, 6927, 11215) → customize for our schema
- sanathbn27 Gmail classification prompt → adapt to our tracker schema

### We WRITE (Level 5 Glue — ~700 lines total)

| File | Lines | Purpose |
|------|-------|---------|
| `config/schema.yaml` | 50 | Candidate profile, job, tracker schemas |
| `config/routing.yaml` | 30 | Task → model mapping (privacy/cost/quality) |
| `prompts/parse_cv.md` | 80 | CV → structured profile |
| `prompts/match_job.md` | 100 | CV + JD + prefs → score + reasoning |
| `prompts/tailor_cv.md` | 80 | CV + JD → tailored markdown |
| `prompts/cover_letter.md` | 60 | CV + JD → cover letter |
| `prompts/app_answers.md` | 60 | CV + JD + question → answer |
| `prompts/interview_prep.md` | 80 | CV + JD + company + stage → STAR questions |
| `prompts/classify_email.md` | 80 | Email + tracker → classification + match |
| `adapters/jobspy_adapter.py` | 60 | JobSpy DataFrame → internal job schema |
| `adapters/simplify_adapter.py` | 50 | SimplifyJobs MD/JSON → internal job schema |
| `adapters/firecrawl_adapter.py` | 40 | Firecrawl response → internal job schema |
| `tracker/tracker.py` | 100 | SQLite/TSV CRUD, matching, export |
| `n8n/custom_nodes/` | 50 | Custom n8n nodes for our functions (optional) |

**Total: ~960 lines of Python/YAML/Markdown — no framework code.**

---

## Deployment Topology

```
┌────────────────────────────────────────────────────────────┐
│                    USER'S MACHINE                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Docker     │  │  Ollama     │  │  Claude Code /      │ │
│  │  Compose    │  │  (models)   │  │  OpenCode / Codex   │ │
│  │  - n8n      │  │             │  │  (User Interface)   │ │
│  │  - SQLite   │  └─────────────┘  └─────────────────────┘ │
│  └─────────────┘                                              │
│         │                                                     │
│         ▼                                                     │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                  LOCAL FILESYSTEM                        │ │
│  │  ~/career-os/                                            │ │
│  │  ├── config/          # schema.yaml, routing.yaml        │ │
│  │  ├── prompts/         # *.md prompt templates            │ │
│  │  ├── adapters/        # Python adapters                  │ │
│  │  ├── tracker/         # tracker.py                       │ │
│  │  ├── data/                                                          │ │
│  │  │   ├── cv.yaml                                            │ │
│  │  │   ├── jobs.db           # SQLite                       │ │
│  │  │   ├── tracker.tsv       # Career-Ops format            │ │
│  │  │   └── tailored_cvs/     # Generated PDFs               │ │
│  │  ├── logs/                                                        │ │
│  │  └── n8n/             # n8n data (workflows, creds)       │ │
│  └─────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   ┌─────────┐          ┌─────────┐          ┌─────────┐
   │Firecrawl│          │OpenRouter│         │ Gmail/  │
   │  API    │          │  API     │         │ Outlook │
   └─────────┘          └─────────┘          └─────────┘
```

**Single command startup:**
```bash
cd ~/career-os && docker compose up -d && ollama serve &
```

---

## Security & Privacy Architecture

| Layer | Protection |
|-------|------------|
| **CV Data** | Never leaves machine unless sent to LLM. Ollama default for parsing. |
| **Email Content** | Processed via n8n → Ollama (local) for classification. Only metadata to cloud if user enables. |
| **Credentials** | n8n encrypts at rest. OAuth tokens in n8n credential store. API keys in `.env` (gitignored). |
| **LLM Routing** | `routing.yaml` enforces: parsing/classification → Ollama; generation → OpenRouter. |
| **Network** | n8n binds to localhost. No inbound ports. Outbound only to configured APIs. |
| **Data Portability** | All user data in `~/career-os/data/` — plain SQLite, TSV, YAML, PDF. |
| **Audit** | Structured logs (JSON) in `~/career-os/logs/`. No telemetry. |

---

## Scaling Path (Post-MVP)

| Trigger | Migration |
|---------|-----------|
| Firecrawl cost > $100/mo | Self-host Firecrawl (Docker) |
| n8n becomes bottleneck | Migrate workflows to Python + Celery/Redis |
| Multi-device sync needed | Add Syncthing / encrypted rclone to VPS |
| Team/collaboration features | Add lightweight API (FastAPI) + auth |
| Mobile access needed | PWA wrapper around local API |

**No premature scaling.** Each migration triggered by demonstrated need.

---

## Architecture Decision Log

| Decision | Chosen | Level | Reason |
|----------|--------|-------|--------|
| Orchestration | n8n | 1 | Visual, self-hosted, handles scheduling/email/retries natively |
| Primary UI | Claude Code / OpenCode | 1 | User already has it; chat-based control fits AI workflow |
| Local LLM | Ollama | 3 | Free, private, models for all classification/parsing tasks |
| Cloud LLM | OpenRouter | 0 | 200+ models, unified API, 1% markup, auto-failover |
| Job Scraping | JobSpy + SimplifyJobs | 3/4 | Covers 95% of sources; library + curated data |
| Browser Auto | Playwright MCP + Browser Use | 2/4 | Official Microsoft + 99K★ agent framework |
| Web Content | Firecrawl API | 0 | Best DX, self-hostable, integrated search+scrape |
| Email | n8n Gmail/Outlook nodes | 1 | OAuth, push, incremental sync built-in |
| Storage | SQLite + TSV | 5 | Local, portable, Career-Ops compatible |
| Document Gen | fpdf2 / weasyprint | 3 | Python, ATS-compliant, no external deps |
| Matching | LLM on-demand | 0 | No vector DB, no custom engine, proven by Career-Ops |
| Notifications | n8n + local desktop | 1/3 | Multi-channel, configurable |