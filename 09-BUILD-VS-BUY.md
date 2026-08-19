# Career OS — Build vs Buy Decisions

**Date:** 2026-08-15  
**Format:** Capability | Best Existing Solution | Alternative | Why | Build Required | Confidence

---

## Decision Matrix

| # | Capability | Best Existing Solution | Alternative | Why This Solution | Build Required | Confidence |
|---|------------|------------------------|-------------|-------------------|----------------|------------|
| A | Candidate/CV Input | Local file + python-docx/pdfplumber | OpenResume | Standard libraries, zero config, local | **Glue only** (50 lines) | 100% |
| B | Candidate Understanding | Ollama (Llama 3.2/3.3) + structured prompt | OpenRouter Haiku | Free, private, local, sufficient for extraction | **Prompt only** | 95% |
| C | Job Discovery | JobSpy + SimplifyJobs + Arbeitnow API | LoopCV, TheirStack, Adzuna | Covers 95% sources, free, local scraping | **Adapters only** (150 lines) | 95% |
| D | Job Aggregation | JobSpy DataFrame + custom dedup | LoopCV normalized API | JobSpy already unifies schema | **Glue only** (50 lines) | 100% |
| E | Web Search | Firecrawl /search | Tavily, SerpApi | Integrated with scraping, markdown output | **Config only** | 90% |
| F | Web Scraping | Firecrawl /scrape + JobSpy | Apify, Browserless | Best DX, self-hostable, handles JS | **Config only** | 90% |
| G | Career-Site Discovery | Firecrawl /map + Career-Ops portal list | Playwright MCP sitemap | Career-Ops has 45 pre-configured | **List adoption** | 95% |
| H | JD Extraction | Firecrawl markdown + Playwright snapshot | Apify actors | Clean markdown, structured data | **Config only** | 90% |
| I | Job Normalization | Internal schema + source adapters | LoopCV schema | Minimal schema, full control | **Schema + adapters** (100 lines) | 100% |
| J | Candidate-Job Matching | LLM (CV+JD+prefs → score) | Resume Matcher, LoopCV API | On-demand, no index, proven by Career-Ops | **Prompt only** | 95% |
| K | Job Ranking | LLM score + preference filters | — | Simple, transparent | **Glue only** | 100% |
| L | Application URL Discovery | JobSpy job_url + Firecrawl extract | Career-Ops apply mode | Comes with job data | **None** | 100% |
| M | Company Research | LLM knowledge + Firecrawl on-demand | Glassdoor API | No persistent DB needed | **Prompt only** | 95% |
| N | CV Tailoring | LLM content + fpdf2/weasyprint PDF | Career-Ops HTML→PDF | ATS-compliant, local generation | **Prompt + PDF lib** | 90% |
| O | Application Answers | LLM (CV+JD+question → answer) | Career-Ops form drafting | On-demand, contextual | **Prompt only** | 95% |
| P | Interview Questions | LLM (CV+JD+company+stage → STAR) | Career-Ops STAR format | No DB needed, generated fresh | **Prompt only** | 95% |
| Q | Application Tracking | Career-Ops tracker (TSV + Go TUI) | JobCtrl, JSE, sanathbn27 | Mature, local-first, portable, 55K★ | **Schema extension** | 95% |
| R | Gmail Monitoring | n8n Gmail node (self-hosted) | Gmail API direct | Visual, OAuth, push, incremental sync | **Workflow config** | 95% |
| S | Outlook Monitoring | n8n Outlook node (self-hosted) | Graph API direct | Same as Gmail | **Workflow config** | 95% |
| T | Email Classification | Ollama (local) + structured prompt | sanathbn27 (Groq), BART | Private, free, 4-priority matching | **Prompt only** | 90% |
| U | Status Detection | LLM classification + Career-Ops enum | — | Included in T | **None** | 95% |
| V | Notifications | n8n nodes + local desktop (plyer) | ntfy.sh, Gotify | Multi-channel, configurable | **Config only** | 100% |
| W | Scheduling | n8n Schedule Trigger | system cron | Visual, timezone-aware, integrated | **Config only** | 100% |
| X | Browser Assistance | Playwright MCP + mcp-playwright-browser | Browser Use cloud | Official Microsoft, 71 specialized job tools | **Config only** | 95% |
| Y | Human Approval | n8n Manual Approval + CLI prompt | — | Mandatory gate, visual + CLI | **Config only** | 100% |
| Z | Data Storage | Local SQLite + TSV (Career-Ops format) | Google Sheets opt-in | Portable, version-controllable, user-owned | **Schema only** | 100% |
| AA | Privacy/Security | Ollama + OpenRouter + keyring + routing.yaml | LiteLLM proxy | Enforceable local-first routing | **Config only** | 95% |
| AB | LLM Routing | OpenRouter + routing.yaml | LiteLLM | 200+ models, 1% markup, task→model map | **Config only** | 95% |
| AC | Observability | n8n logs + structlog local | Langtrace, Helicone | Built-in + local structured | **Config only** | 100% |
| AD | Error Handling | n8n retry/error nodes + tenacity | pybreaker | Visual retry, dead letter, exponential backoff | **Config only** | 100% |

---

## BUILD: Only Things We Genuinely Need to Own

| Component | Description | Lines | Reason |
|-----------|-------------|-------|--------|
| `config/schema.yaml` | Candidate, Job, Tracker schemas | 50 | Single source of truth for all adapters |
| `config/routing.yaml` | Task → model mapping (privacy/cost/quality) | 30 | Enforceable privacy policy |
| `prompts/*.md` (9 files) | LLM prompt templates | 720 | Version-controlled, reviewable, tunable |
| `adapters/*.py` (3 files) | JobSpy, SimplifyJobs, Firecrawl → internal schema | 150 | Normalize diverse sources |
| `tracker/tracker.py` | SQLite/TSV CRUD, matching, export | 100 | Extend Career-Ops with our fields |
| **TOTAL** | | **~1,050 lines** | **All Python/YAML/Markdown — no framework code** |

---

## REUSE: Existing Components We Adopt

| Component | Source | What We Use |
|-----------|--------|-------------|
| **Job Scraping** | JobSpy (speedyapply/JobSpy) | `scrape_jobs()` for 8 job boards |
| **New Grad Data** | SimplifyJobs/New-Grad-Positions | Daily updated 12K+ roles |
| **Application Tracker** | santifer/career-ops | TSV schema, Go TUI, integrity checks |
| **Evaluation Rubric** | santifer/career-ops | 5-dimension + global score 1.0-5.0 |
| **Portal List** | santifer/career-ops | 45 pre-configured AI company career sites |
| **Browser Automation** | microsoft/playwright-mcp | 22 MCP tools, accessibility tree |
| **Specialized Job Tools** | Mhrnqaruni/mcp-playwright-browser | 71 tools: Indeed extractor, form automation, session persistence |
| **Complex Form Automation** | browser-use/browser-use | Agent-driven natural language browser control |
| **Web Content** | firecrawl/firecrawl | Search, scrape, crawl, extract, monitor |
| **Local LLM** | ollama/ollama | Llama 3.2 3B, 3.3 70B, Nemotron — free, private |
| **Cloud LLM Router** | openrouter/openrouter | 200+ models, unified API, auto-failover |
| **Workflow Engine** | n8n-io/n8n | Visual workflows, scheduling, email triggers, retries |
| **PDF Generation** | fpdf2 / weasyprint | ATS-compliant PDF from HTML/markdown |
| **Document Parsing** | markitdown / pdfplumber / python-docx | Local CV text extraction |
| **Email Triggers** | n8n Gmail/Outlook nodes | OAuth, push, incremental sync |
| **Notifications** | n8n nodes + plyer | Email, Slack, Discord, desktop |
| **Skills Taxonomy** | Open Skills (workforce-data-initiative) | Local skill normalization |

---

## CONFIGURE: Existing Platforms We Only Need to Connect

| Platform | Configuration | Effort |
|----------|---------------|--------|
| **n8n** | 5 workflows, OAuth credentials, webhook URLs | 2 hours |
| **Ollama** | `ollama pull llama3.2:3b llama3.3:70b nemotron3:ultra` | 10 min |
| **Playwright MCP** | Add to Claude Code/OpenCode MCP config | 5 min |
| **mcp-playwright-browser** | Add to MCP config, configure profiles | 15 min |
| **Firecrawl** | API key in n8n + routing.yaml | 5 min |
| **OpenRouter** | API key in n8n + routing.yaml | 5 min |
| **Gmail/Outlook** | OAuth in n8n credentials | 10 min |
| **Git (SimplifyJobs)** | Clone repo, add cron pull in n8n | 5 min |
| **Groq/Cerebras** | API keys in n8n (free tier) | 5 min |

---

## DEFER: Things That Can Wait

| Capability | Reason | Trigger to Revisit |
|------------|--------|---------------------|
| Multi-device sync | Single-user MVP | User requests |
| Mobile app / PWA | CLI + TUI sufficient | User requests |
| Team collaboration | Single-user MVP | User requests |
| Custom LinkedIn scraper | ToS risk, JobSpy covers basics | LinkedIn becomes critical gap |
| Salary negotiation engine | Interview prep covers basics | User requests |
| Reference checking | Out of scope | Never (different product) |
| Background check integration | Out of scope | Never |
| Video interview practice | Out of scope | Never |
| Custom ATS integrations | Playwright MCP handles forms | Specific ATS fails |
| Machine learning matching | LLM matching proven sufficient | Accuracy drops below threshold |

---

## REJECT: Things We Explicitly NOT Build

| Capability | Rejected Approach | Reason |
|------------|-------------------|--------|
| Custom Resume Parser | Custom NLP pipeline | LLM + pdfplumber sufficient |
| Custom Job Matching Engine | Vector DB + semantic search | LLM on-demand matching proven |
| Custom Interview Question DB | Curated question database | LLM generates contextual questions |
| Vector Database | Pinecone/Weaviate/Qdrant | Not needed — context window sufficient |
| RAG Pipeline | Custom retrieval | Job data fits in context; Firecrawl for web |
| Custom Job Board | Custom aggregator | JobSpy + APIs + SimplifyJobs cover 95% |
| Custom ATS Tracker | Full-stack app | Career-Ops tracker exists |
| Custom Browser Automation | Selenium/Puppeteer framework | Playwright MCP + Browser Use exist |
| Custom Search Engine | Elasticsearch/Meilisearch | Firecrawl/Tavily/SerpApi exist |
| Custom Email Server | IMAP/SMTP handling | Gmail/Outlook APIs + n8n exist |
| Custom LLM | Fine-tuned model | Not needed — prompting sufficient |
| Giant Career Knowledge Graph | Neo4j + custom ontology | YAGNI — LLM has knowledge |

---

## Confidence Scores Explained

| Score | Meaning |
|-------|---------|
| **100%** | Trivial integration, standard library, zero risk |
| **95%** | Proven pattern, minor adaptation needed |
| **90%** | Good solution, some configuration complexity |
| **85%** | Acceptable, known limitations |
| **80%** | Fallback option, not primary |

**Average confidence: 96%** — extremely high because we're assembling proven components.

---

## Decision Log Template (For Future Decisions)

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
**Confidence:** [XX%]
```

---

## Summary: What We Actually Build

```
┌─────────────────────────────────────────────────────────────────┐
│                     JOB SCOUT MVP CODEBASE                       │
├─────────────────────────────────────────────────────────────────┤
│  config/                                                         │
│  ├── schema.yaml        # 50 lines  — Data contracts            │
│  └── routing.yaml       # 30 lines  — Privacy/cost enforcement  │
│  prompts/                                                           │
│  ├── parse_cv.md        # 80 lines  — CV → structured profile   │
│  ├── match_job.md       # 100 lines — CV+JD+prefs → score       │
│  ├── tailor_cv.md       # 80 lines  — CV+JD → tailored markdown │
│  ├── cover_letter.md    # 60 lines  — CV+JD → cover letter      │
│  ├── app_answers.md     # 60 lines  — CV+JD+Q → answer          │
│  ├── interview_prep.md  # 80 lines  — CV+JD+co+stage → STAR Qs  │
│  ├── classify_email.md  # 80 lines  — Email+tracker → classify  │
│  └── company_research.md # 60 lines  — URL → company intel      │
│  adapters/                                                            │
│  ├── jobspy_adapter.py  # 60 lines  — JobSpy → internal schema  │
│  ├── simplify_adapter.py # 50 lines  — SimplifyJobs → schema     │
│  └── firecrawl_adapter.py # 40 lines  — Firecrawl → schema      │
│  tracker/                                                             │
│  └── tracker.py         # 100 lines — SQLite/TSV CRUD + matching │
│  n8n/                                                                 │
│  └── workflows/         # 5 JSON workflows (exported from n8n)  │
└─────────────────────────────────────────────────────────────────┘
Total: ~1,050 lines of Python/YAML/Markdown/JSON
No framework code. No custom infrastructure. All configuration.
```

**This is the minimum viable code to deliver 80%+ of Job Scout functionality.**