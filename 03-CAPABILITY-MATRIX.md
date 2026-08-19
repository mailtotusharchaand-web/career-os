# Career OS — Capability Matrix

**Date:** 2026-08-15  
**Purpose:** Map every Job Scout capability to existing solutions with reuse level

---

## Capability Matrix

| # | Capability | Category | Reuse Level | Primary Solution | Alternative | Integration Effort | Privacy Risk | Cost/Month (50 jobs/day) |
|---|------------|----------|-------------|------------------|-------------|-------------------|--------------|--------------------------|
| A | Candidate/CV Input | Input | 5 | Local file upload + python-docx/pdfplumber | OpenResume | Low | None | $0 |
| B | Candidate Understanding | Intelligence | 0 | LLM (OpenRouter/Ollama) structured extraction | Career-Ops cv.md schema | Low | CV text to LLM | $2-5 |
| C | Job Discovery | Discovery | 3/4/0 | JobSpy + SimplifyJobs + LoopCV API | Adzuna, TheirStack, Fantastic.jobs | Low | Query to API | $0-50 |
| D | Job Aggregation | Processing | 3/5 | JobSpy DataFrame + custom dedup | LoopCV normalized API | Low | None | $0 |
| E | Web Search | Discovery | 0 | Firecrawl /search | Tavily, SerpApi, Brave | Low | Query to API | $5-15 |
| F | Web Scraping | Discovery | 0/2/3 | Firecrawl /scrape + Playwright MCP + JobSpy | Apify, Browser Use | Medium | Page content to API | $10-30 |
| G | Career-Site Discovery | Discovery | 0/4 | Firecrawl /map + Career-Ops portal list | Playwright MCP sitemap | Low | URLs to API | $5 |
| H | JD Extraction | Processing | 0/2 | Firecrawl markdown + Playwright snapshot | Apify specialized actors | Low | JD text to API | $5-10 |
| I | Job Normalization | Processing | 5 | Internal schema + source adapters | LoopCV schema | Low | None | $0 |
| J | Candidate-Job Matching | Intelligence | 0 | LLM (CV+JD+prefs → score) | Resume Matcher, LoopCV API | Low | CV+JD to LLM | $5-15 |
| K | Job Ranking | Intelligence | 0/5 | LLM score + preference filters | — | Low | None | $0 |
| L | Application URL Discovery | Discovery | 3/0 | JobSpy job_url + Firecrawl extract | Career-Ops apply mode | Low | None | $0 |
| M | Company Research | Intelligence | 0 | LLM knowledge + Firecrawl on-demand | Glassdoor API | Low | Query to LLM | $2-5 |
| N | CV Tailoring | Generation | 0/3 | LLM content + fpdf2/weasyprint PDF | Career-Ops HTML→PDF | Medium | CV+JD to LLM | $5-10 |
| O | Application Answers | Generation | 0 | LLM (CV+JD+question → answer) | Career-Ops form drafting | Low | CV+JD to LLM | $2-5 |
| P | Interview Questions | Generation | 0 | LLM (CV+JD+company+stage → Qs) | Career-Ops STAR format | Low | CV+JD to LLM | $2-5 |
| Q | Application Tracking | Tracking | 4 | Career-Ops tracker (TSV + Go TUI) | JobCtrl, JSE, sanathbn27 | Medium | Local only | $0 |
| R | Gmail Monitoring | Tracking | 1 | n8n Gmail trigger + Pub/Sub | Gmail API direct | Low | Email content to n8n/LLM | $0 (n8n self-hosted) |
| S | Outlook Monitoring | Tracking | 1 | n8n Outlook trigger + Graph API | Graph API direct | Low | Email content to n8n/LLM | $0 |
| T | Email Classification | Intelligence | 0 | LLM (email+tracker → classification) | sanathbn27 4-priority, BART | Low | Email to LLM | $2-5 |
| U | Status Detection | Intelligence | 0 | LLM classification | Career-Ops status enum | Low | Email to LLM | $0 (included in T) |
| V | Notifications | Ops | 1/3 | n8n (email/Slack/Discord) + local desktop | ntfy.sh, Gotify | Low | Minimal | $0 |
| W | Scheduling | Ops | 1 | n8n Schedule Trigger | system cron | Low | None | $0 |
| X | Browser Assistance | Automation | 2/4 | Playwright MCP + mcp-playwright-browser | Browser Use cloud | Medium | Page content to LLM | $0 (local) |
| Y | Human Approval | Safety | 1/3 | n8n Manual Approval + CLI prompt | — | Low | None | $0 |
| Z | Data Storage | Infra | 5 | Local SQLite (default) / Google Sheets | Career-Ops TSV | Low | Local only | $0 |
| AA | Privacy/Security | Infra | 3/0 | Ollama local + OpenRouter + keyring | LiteLLM proxy | Low | Configurable | $0-20 |
| AB | LLM Routing | Infra | 0/5 | OpenRouter + routing config YAML | LiteLLM | Low | Per-task routing | $0 (included) |
| AC | Observability | Infra | 1/3 | n8n logs + structlog local | Langtrace, Helicone | Low | Metadata only | $0 |
| AD | Error Handling | Infra | 1/3 | n8n retry/error nodes + tenacity | pybreaker | Low | None | $0 |

---

## Integration Complexity Assessment

| Complexity | Capabilities | Count |
|------------|--------------|-------|
| Trivial (config only) | A, Z, W, V, Y, AA, AC, AD | 8 |
| Low (prompt/library) | B, D, E, H, I, K, L, M, O, P, T, U, AB | 13 |
| Medium (workflow/adapter) | C, F, G, J, N, Q, R, S, X | 9 |
| High (custom integration) | — | 0 |

**Zero high-complexity integrations.**

---

## Data Flow Summary

```
CV (local file)
    → python-docx/pdfplumber → text
    → LLM (Ollama local) → structured profile (cv.yaml)
    → User reviews/edits

Job Discovery (scheduled via n8n)
    → JobSpy (Indeed, LinkedIn, Glassdoor, Google, ZipRecruiter)
    → SimplifyJobs repo (new grad)
    → Firecrawl /search (web)
    → LoopCV/TheirStack API (supplement)
    → Adapter → internal job schema (JSON)
    → Dedup (title+company+location hash)
    → Store in SQLite

Matching (on-demand or batch)
    → For each job: LLM (cv.yaml + JD + prefs) → score + reasoning
    → Rank by score, filter by preferences
    → Present top N to user

User selects job
    → LLM generates tailored CV (markdown) → fpdf2 → PDF
    → LLM generates cover letter
    → LLM answers application questions
    → LLM generates interview prep (STAR)
    → All saved to tracker (SQLite/TSV)

Application
    → User clicks apply URL (from job data)
    → Optional: Playwright MCP assists form fill (HITL)
    → User submits, updates tracker status

Gmail/Outlook (n8n webhook)
    → New email → LLM classifies (type, company, role, status)
    → 4-priority match to tracker entry
    → Auto-update status
    → Notify user (n8n → email/Slack/desktop)
```

---

## External Dependencies Inventory

| Dependency | Type | Self-Hostable? | Free Tier? | Data Leaves Machine? |
|------------|------|----------------|------------|---------------------|
| Ollama | LLM runtime | Yes | Yes | **No** |
| OpenRouter | LLM API | No | Limited | Yes (prompts only) |
| Firecrawl | Scraping API | Yes (AGPL) | 1000 credits/mo | Yes (URLs + content) |
| JobSpy | Python lib | Yes | Yes | No (direct to job sites) |
| SimplifyJobs | GitHub repo | Yes | Yes | No (local clone) |
| n8n | Workflow engine | Yes | Yes (self-hosted) | Configurable |
| Playwright MCP | MCP server | Yes | Yes | No (local browser) |
| Gmail/Outlook API | Email | No | Yes | Yes (OAuth, email content) |
| Google Sheets | Storage | No | Yes | Yes (if enabled) |
| fpdf2/weasyprint | PDF gen | Yes | Yes | No |

**Privacy-first defaults:** Ollama + self-hosted n8n + local SQLite + JobSpy + SimplifyJobs = **zero external data transfer** for core loop.

---

## Reuse Level Distribution

| Level | Capabilities | % of Total |
|-------|--------------|------------|
| 0 (API) | B, C, E, F, G, H, J, K, L, M, O, P, T, U, AB | 15 (50%) |
| 1 (SaaS) | C, R, S, V, W | 5 (17%) |
| 2 (MCP) | F, X | 2 (7%) |
| 3 (Library) | A, F, N, AA | 4 (13%) |
| 4 (App) | C, G, J, N, Q, T, X | 7 (23%) |
| 5 (Glue) | A, D, I, K, Q, Y, Z, AB, AC, AD | 10 (33%) |
| 6 (Build) | — | 0 (0%) |

*Note: Capabilities can use multiple levels; primary level shown in matrix.*