# Career OS — Public API Audit

**Date:** 2026-08-15  
**Scope:** APIs capable of providing jobs, company info, salary data, skills, email, documents, LLM inference, search, web data

---

## Job Aggregator APIs

| API | Auth | Free Tier | Rate Limits | Structured Data | Maintenance | Legal/ToS | Better Than Scraping? | Verdict |
|-----|------|-----------|-------------|-----------------|-------------|-----------|----------------------|---------|
| **Arbeitnow** | None | Yes (no key) | Reasonable | Yes (JSON) | Active (2026-08) | Public ATS data | Yes — Greenhouse, SmartRecruiters, Join.com, TeamTailor | **Primary (EU/Remote)** |
| **LoopCV Job Board API** | API Key | Yes (no CC) | Tiered | Yes (unified schema) | Active | 30+ sources, GDPR compliant | Yes — normalized across Greenhouse, Lever, Ashby, Indeed, LinkedIn | **Primary (Global)** |
| **Adzuna** | API Key | Yes | 5000/day | Yes | Active | Global aggregator | Yes | **Supplement** |
| **TheirStack** | API Key | Trial | Paid tiers | Yes (LinkedIn, Glassdoor, Indeed, 16+) | Active | Commercial | Yes — hard-to-scrape sources | **Supplement (if budget)** |
| **Fantastic.jobs** | API Key | Trial | Paid | Yes (8M jobs/mo, ATS) | Active | Commercial | Yes | **Supplement (if budget)** |
| **Careerjet** | API Key | Limited | Limited | Yes | Active | Search engine | Partial | **Backup** |
| **Jooble** | API Key | Partner | Partner | Yes | Active | Search engine | Partial | **Backup** |
| **Findwork** | API Key | Yes | Reasonable | Yes | Active | Dev-focused board | Yes (niche) | **Niche (Dev)** |
| **DevITjobs UK** | None | Yes | No auth | GraphQL | Active | UK tech jobs | Yes | **Niche (UK Dev)** |
| **Jobicy** | None | Yes | No auth | RSS/JSON | Active | Remote jobs | Yes | **Niche (Remote)** |
| **OkJob** | API Key | Yes | Tiered | Yes | Active | 4-day week jobs | Yes | **Niche** |
| **Techmap** | API Key | Yes | Tiered | Yes | Active | International | Yes | **Supplement (Intl)** |
| **The Muse** | API Key | Yes | Tiered | Yes | Active | Company profiles + jobs | Yes | **Supplement** |
| **Reed** | API Key | Yes | Tiered | Yes | Active | UK aggregator | Yes | **Niche (UK)** |
| **Jobs2Careers** | API Key | Spec | Unknown | XML | Unknown | Aggregator | Partial | **Avoid** |
| **Juju** | API Key | Partner | Partner | Yes | Active | Search engine | Partial | **Backup** |
| **USAJOBS** | API Key | Yes | 250/day | Yes | Active | US Govt jobs | Yes | **Niche (Govt)** |
| **GitHub Jobs** | — | **SHUTDOWN** | — | — | **Dead** | — | — | **REJECTED** |
| **Indeed API** | — | **SHUTDOWN** | — | — | **Dead** | Requires publisher account | — | **REJECTED** |

### Recommendation: Job Discovery Stack

```
Primary:  JobSpy (library) → Indeed, LinkedIn, Glassdoor, Google, ZipRecruiter, Naukri, Bayt, BDJobs
          SimplifyJobs/New-Grad-Positions (repo) → 12K+ curated new grad roles
          
Supplement: Arbeitnow API → EU/Remote (free, no key)
            LoopCV API → 30+ normalized sources (free tier)
            Adzuna API → Global supplement (free tier)
            
Niche:     DevITjobs UK / Jobicy / Findwork / USAJOBS → as needed
```

---

## Company Information APIs

| API | Data | Auth | Free Tier | Notes |
|-----|------|------|-----------|-------|
| **Clearbit** | Company enrichment | API Key | 100/mo | Detailed firmographics |
| **Apollo.io** | Company + contacts | API Key | Limited | B2B focused |
| **Crunchbase** | Startup data | API Key | Limited | Funding, investors |
| **LinkedIn Company API** | Company pages | OAuth | Limited | Requires partnership |
| **Glassdoor API** | Reviews, salaries | Partner | No | Partner only |
| **Firecrawl /scrape** | Any company site | API Key | 1000 credits | On-demand, any site |
| **OpenCorporates** | Legal entities | API Key | Free | Open data |

**Recommendation:** Firecrawl on-demand for company research. No persistent company DB.

---

## Salary / Compensation APIs

| API | Data | Auth | Free Tier | Notes |
|-----|------|------|-----------|-------|
| **Levels.fyi** | Tech compensation | API Key | Limited | Crowd-sourced, reliable |
| **Glassdoor** | Salary estimates | Partner | No | Partner only |
| **Payscale** | Salary data | API Key | Paid | Enterprise |
| **LoopCV API** | Salary in job listings | API Key | Free tier | Included in job data |
| **Adzuna** | Salary stats | API Key | Free tier | Market trends |
| **Firecrawl** | Extract from JD | API Key | 1000 credits | On-demand from job page |

**Recommendation:** Extract from JD via Firecrawl + Levels.fyi for benchmarking. No dedicated salary API needed.

---

## Skills / Occupation Taxonomy APIs

| API | Data | Auth | Free Tier | Notes |
|-----|------|------|-----------|-------|
| **Open Skills (Workforce Data Initiative)** | Skills, job titles, relations | None | Yes | GitHub repo + API, open data |
| **O*NET / ESCO** | Occupation classifications | None | Yes | Government standards |
| **Lightcast (Emsi)** | Skills analytics | API Key | Paid | Enterprise |
| **LinkedIn Skills** | Skill graph | Partner | No | Partner only |

**Recommendation:** Open Skills (open source, free) for skill normalization. LLM handles extraction.

---

## Email APIs

| API | Protocol | Auth | Free Tier | Notes |
|-----|----------|------|-----------|-------|
| **Gmail API** | REST | OAuth2 | Yes | Pub/Sub push, historyId incremental sync |
| **Microsoft Graph (Outlook)** | REST | OAuth2 | Yes | Delta queries, webhook notifications |
| **IMAP/SMTP** | Standard | Password/App password | Yes | Legacy, less reliable |
| **n8n Gmail/Outlook nodes** | Wrapper | OAuth2 | Yes (self-hosted) | Visual workflow, built-in triggers |

**Recommendation:** n8n nodes (Level 1) for workflow integration. Direct API (Level 0) only for custom logic.

---

## Document Processing APIs

| API | Function | Auth | Free Tier | Notes |
|-----|----------|------|-----------|-------|
| **Firecrawl /scrape** | URL → Markdown/JSON | API Key | 1000 credits | JS rendering, structured extraction |
| **Firecrawl /extract** | AI structured extraction | API Key | Higher cost | Schema-defined extraction |
| **Apify Actors** | Specialized scrapers | API Key | Pay-per-result | 3000+ actors (Greenhouse, Indeed, LinkedIn) |
| **MarkItDown (Microsoft)** | Files → Markdown | Library | Free (local) | Python lib, 173K★ |
| **pdfplumber / pymupdf** | PDF text extraction | Library | Free (local) | Python libs |
| **python-docx** | DOCX parsing | Library | Free (local) | Python lib |
| **Unstructured.io** | Document parsing | API Key | Free tier | SaaS, many formats |

**Recommendation:** Local libraries (MarkItDown, pdfplumber, python-docx) for CV parsing. Firecrawl for web content.

---

## LLM Inference APIs

| Provider | Models | Auth | Free Tier | Pricing (Input/Output per 1M) | Context | Best For |
|----------|--------|------|-----------|-------------------------------|---------|----------|
| **OpenRouter** | 200+ (all) | API Key | ~30 free models | Model + 1% markup | Up to 1M | **Primary — unified access** |
| **Anthropic** | Claude Opus/Sonnet/Haiku | API Key | Console | $3-5/$15-25 (Sonnet/Opus) | 200K-1M | Coding, reasoning |
| **OpenAI** | GPT-4o, o3, mini | API Key | GPT-3.5 only | $2.50/$10 (4o) | 128K | General |
| **Google Gemini** | 2.5 Pro, Flash | API Key | Flash only | $1.25/$10 (Pro) | 1M | Long context, cost |
| **Mistral** | Large, Nemo | API Key | 1B tok/mo | $2/$6 | 128K | EU, open weights |
| **xAI (Grok)** | Grok 4 | API Key | $25 credits | $0.20/$0.50 | 128K | Cheap frontier |
| **Groq** | Llama, Mixtral | API Key | 30 RPM, 100K/day | **Free** (LPU) | 128K | Speed, free tier |
| **Cerebras** | Llama 3.3 | API Key | Free | **Free** | 128K | Speed, free tier |
| **DeepSeek** | V3, R1 | API Key | Yes | $0.30/$0.50 | 1M | Cheap long-context |
| **Ollama** | Local (any GGUF) | Local | **Free** | **Free** (hardware) | Model-dependent | **Privacy, zero cost** |
| **Together AI** | Open models | API Key | $1 credits | $0.10-0.90 | 128K | Hosted open models |
| **Fireworks AI** | Open models | API Key | $1 credits | Competitive | 128K | Hosted open models |
| **Replicate** | Any model | API Key | Pay-per-sec | Per-second GPU | Various | Custom models |
| **Baseten** | Open models | API Key | Trial | Dedicated infra | Various | Production open models |
| **Cloudflare Workers AI** | Open models | API Key | Free tier | Free/cheap | Various | Edge inference |

### LLM Routing Strategy for Job Scout

| Task | Primary Model | Fallback | Local Option | Reason |
|------|---------------|----------|--------------|--------|
| CV Parsing | Haiku 3.5 / GPT-4o-mini | Gemini Flash | Llama 3.2 3B (Ollama) | Low cost, structured output |
| Job Matching | Sonnet 4 / GPT-4o | Opus 4 | Llama 3.3 70B (Ollama) | Reasoning quality |
| CV Tailoring | Opus 4 / GPT-4o | Sonnet 4 | Llama 3.3 70B | Writing quality |
| Cover Letter | Opus 4 / GPT-4o | Sonnet 4 | Llama 3.3 70B | Persuasive writing |
| App Answers | Sonnet 4 / GPT-4o | Haiku 3.5 | Llama 3.1 8B | Concise, factual |
| Interview Qs | Opus 4 / GPT-4o | Sonnet 4 | Llama 3.3 70B | Depth, STAR format |
| Email Classification | Haiku 3.5 / GPT-4o-mini | Gemini Flash | Llama 3.2 3B | High volume, low cost |
| Company Research | Sonnet 4 / GPT-4o | Opus 4 | — | Knowledge + reasoning |

**Cost Optimization:** Route 80% of tasks to Haiku/Flash/mini/Groq. Reserve Opus/GPT-4o for generation tasks. Use Ollama for all classification/parsing when privacy required.

---

## Search APIs

| API | Type | Auth | Free Tier | Cost | Notes |
|-----|------|------|-----------|------|-------|
| **Firecrawl /search** | Web + content | API Key | 1000 credits | 2 credits/10 results | Markdown included |
| **Tavily** | AI-native search | API Key | 1000 credits | Pay-as-you-go | Optimized for LLMs |
| **SerpApi** | Google SERP | API Key | 100 searches | $50/mo | Rich SERP data |
| **Serper** | Google SERP | API Key | 2500/mo | $50/mo | Fast, cheap |
| **Brave Search** | Independent index | API Key | 2000/mo | $3/1000 | Privacy-focused |
| **Jina AI Reader** | URL → content | API Key | 1M tokens | Free tier | Universal reader |
| **Exa** | Neural search | API Key | 1000/mo | Custom | AI-focused |

**Recommendation:** Firecrawl /search (integrated with scraping) primary. Tavily backup.

---

## Web Data / Scraping APIs

| API | Function | Auth | Free Tier | Pricing | Self-Hostable |
|-----|----------|------|-----------|---------|---------------|
| **Firecrawl** | Scrape, crawl, search, extract, monitor | API Key | 1000 credits/mo | $16-333/mo | Yes (AGPL) |
| **Apify** | Actors (3000+) | API Key | $5 credits | Pay-per-result | No (platform) |
| **Browserless** | Headless Chrome | API Key | Trial | $50-500/mo | Yes (Docker) |
| **ScrapingBee** | Scraping API | API Key | 1000 credits | $49-299/mo | No |
| **ZenRows** | Scraping + anti-bot | API Key | 1000 credits | $49-599/mo | No |
| **Crawl4AI** | Crawl + extract | API Key | Open source | Free (self-host) | Yes (MIT) |
| **ScrapeGraphAI** | AI scraping | API Key | Trial | Custom | No |

**Recommendation:** Firecrawl cloud API (Level 0) for simplicity. Self-host Firecrawl/Crawl4AI if volume > $100/mo or privacy critical.

---

## API Accessibility Summary

| Capability | API Available? | Free Tier Sufficient? | Self-Hostable? | Legal Risk | Recommended Approach |
|------------|----------------|----------------------|----------------|------------|---------------------|
| Job Search | Yes (multiple) | Yes (JobSpy + Arbeitnow + SimplifyJobs) | Yes (JobSpy) | Low | Library + free APIs |
| Company Info | Yes (Firecrawl) | Yes (on-demand) | Yes | Low | Firecrawl on-demand |
| Salary Data | Partial | Yes (extract from JD) | N/A | Low | JD extraction + Levels.fyi |
| Skills Taxonomy | Yes (Open Skills) | Yes | Yes | None | Open Skills local |
| Email (Gmail) | Yes | Yes | No (Google) | Low (OAuth) | n8n Gmail node |
| Email (Outlook) | Yes | Yes | No (Microsoft) | Low (OAuth) | n8n Outlook node |
| Document Parse | Yes (libraries) | Yes (local) | Yes | None | Local libraries |
| LLM Inference | Yes (many) | Yes (Groq/Cerebras/Ollama) | Yes (Ollama) | Varies | OpenRouter + Ollama |
| Web Search | Yes | Yes (Firecrawl/Tavily) | Yes (Crawl4AI) | Low | Firecrawl /search |
| Web Scraping | Yes | Yes (Firecrawl free tier) | Yes (Firecrawl/Crawl4AI) | Medium (ToS) | Firecrawl API → self-host if needed |

---

## Cost Estimate: API Usage at Scale

| Volume | Firecrawl | OpenRouter | LoopCV/Adzuna | Gmail/Outlook | Total/Month |
|--------|-----------|------------|---------------|---------------|-------------|
| 10 jobs/day | $5 | $3 | $0 | $0 | **~$8** |
| 50 jobs/day | $25 | $15 | $0-20 | $0 | **~$40-60** |
| 100 jobs/day | $50 | $30 | $0-50 | $0 | **~$80-130** |
| 500 jobs/day | $200 | $150 | $50-200 | $0 | **~$400-550** |

**With Ollama for 60% of LLM calls:** Reduce OpenRouter by ~60%.
**With self-hosted Firecrawl:** Eliminate Firecrawl cost (hardware only).

---

## Final API Stack Recommendation

```
┌─────────────────────────────────────────────────────────────┐
│                    JOB SCOUT API LAYER                       │
├─────────────────────────────────────────────────────────────┤
│  Job Discovery     │ JobSpy (lib) + SimplifyJobs (repo)      │
│                    │ Arbeitnow API (free)                    │
│                    │ LoopCV API (free tier)                  │
│                    │ Adzuna API (free tier)                  │
├─────────────────────────────────────────────────────────────┤
│  Web Content       │ Firecrawl API (cloud)                   │
│                    │ → Self-host if >$100/mo or privacy      │
├─────────────────────────────────────────────────────────────┤
│  Browser Auto      │ Playwright MCP (local)                  │
│                    │ Browser Use (local/cloud)               │
│                    │ mcp-playwright-browser (specialized)    │
├─────────────────────────────────────────────────────────────┤
│  LLM Inference     │ OpenRouter (unified)                    │
│                    │ Ollama (local, privacy)                 │
│                    │ Groq/Cerebras (free tier, speed)        │
├─────────────────────────────────────────────────────────────┤
│  Email             │ n8n Gmail/Outlook nodes (OAuth)         │
├─────────────────────────────────────────────────────────────┤
│  Document Parse    │ MarkItDown / pdfplumber / python-docx   │
├─────────────────────────────────────────────────────────────┤
│  Skills            │ Open Skills (local dataset)             │
├─────────────────────────────────────────────────────────────┤
│  Search            │ Firecrawl /search + Tavily backup       │
└─────────────────────────────────────────────────────────────┘
```