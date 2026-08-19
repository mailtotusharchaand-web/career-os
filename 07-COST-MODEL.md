# Career OS — Cost Model

**Date:** 2026-08-15  
**Scope:** Operating cost estimates for Job Scout MVP at various volumes

---

## Cost Components

| Component | Pricing Model | Unit Cost | Notes |
|-----------|---------------|-----------|-------|
| **Firecrawl (Cloud)** | Credits/month | $16/mo (3K credits), $83/mo (100K), $333/mo (1M) | 1 credit = 1 scrape/crawl/page. Search: 2 credits/10 results. |
| **OpenRouter** | Per-token + 1% | Model-dependent | Haiku 3.5: $0.80/$4.00. Sonnet 4: $3/$15. Opus 4: $5/$25. GPT-4o: $2.50/$10. Gemini Flash: $0.075/$0.30. |
| **Ollama (Local)** | Hardware | $0 (existing) | GPU memory: 3B=4GB, 8B=8GB, 70B=48GB. CPU inference slower but free. |
| **Groq / Cerebras** | Free tier | $0 | 30 RPM, 100K-500K tokens/day. Llama 3.3 70B, Mixtral. |
| **n8n Cloud** | Seat-based | $20-120/mo | **Self-hosted = $0** (Docker on user machine) |
| **JobSpy** | Library | $0 | MIT, local execution |
| **SimplifyJobs** | GitHub repo | $0 | Free, daily updated |
| **Playwright MCP** | Local | $0 | npm package, local browser |
| **Browser Use** | Local/Cloud | $0 local, cloud paid | MIT, local execution |
| **fpdf2 / weasyprint** | Library | $0 | Local PDF generation |
| **SQLite / TSV** | Local | $0 | No server |
| **Google Sheets** | API | $0 | Free tier generous |
| **Gmail/Outlook API** | OAuth | $0 | Free, rate limits generous |

---

## Token Usage Estimates Per Job

| Task | Prompt Tokens | Completion Tokens | Model (Primary) | Cost via OpenRouter |
|------|---------------|-------------------|-----------------|---------------------|
| CV Parsing | 3,000 | 500 | Haiku 3.5 / GPT-4o-mini | $0.003 |
| Job Matching | 4,000 | 800 | Sonnet 4 / GPT-4o | $0.025 |
| CV Tailoring | 5,000 | 2,000 | Opus 4 / GPT-4o | $0.065 |
| Cover Letter | 4,000 | 1,500 | Opus 4 / GPT-4o | $0.050 |
| App Answers (5 Qs) | 3,000 | 1,000 | Sonnet 4 | $0.020 |
| Interview Prep | 5,000 | 2,500 | Opus 4 | $0.080 |
| Email Classification | 2,000 | 300 | Haiku 3.5 / Flash | $0.002 |
| Company Research | 3,000 | 1,000 | Sonnet 4 | $0.020 |

**Average per job (full pipeline):** ~$0.25-0.35 via OpenRouter frontier models  
**With 60% local (Ollama/Groq):** ~$0.10-0.15

---

## Firecrawl Usage Estimates

| Volume | Jobs/Day | Searches/Day | Scrapes/Day (JD + Company) | Credits/Day | Monthly Credits | Plan |
|--------|----------|--------------|----------------------------|-------------|-----------------|------|
| Low | 10 | 5 | 20 | 5*2 + 20*1 = 30 | 900 | Free (1K) |
| Medium | 50 | 20 | 100 | 20*2 + 100*1 = 140 | 4,200 | Hobby $16 (3K) → **Standard $83** |
| High | 100 | 40 | 200 | 40*2 + 200*1 = 280 | 8,400 | Standard $83 |
| Very High | 500 | 100 | 1000 | 100*2 + 1000*1 = 1,200 | 36,000 | Growth $333 |

**Note:** JobSpy handles most job board scraping (free, local). Firecrawl used for: company career sites, custom searches, JD extraction from non-board URLs.

---

## Monthly Cost Scenarios

### Scenario A: Cloud-First (OpenRouter + Firecrawl Cloud)

| Volume | Firecrawl | OpenRouter (70% frontier) | n8n Cloud | Total |
|--------|-----------|---------------------------|-----------|-------|
| 10 jobs/day | $0 (free) | $15 | $20 | **$35** |
| 50 jobs/day | $83 | $75 | $20 | **$178** |
| 100 jobs/day | $83 | $150 | $20 | **$253** |
| 500 jobs/day | $333 | $750 | $120 | **$1,203** |

### Scenario B: Privacy-First (Self-Hosted n8n + Ollama + Firecrawl Cloud)

| Volume | Firecrawl | OpenRouter (30% frontier) | Ollama (Local) | Total |
|--------|-----------|---------------------------|----------------|-------|
| 10 jobs/day | $0 | $5 | $0 | **$5** |
| 50 jobs/day | $83 | $25 | $0 | **$108** |
| 100 jobs/day | $83 | $50 | $0 | **$133** |
| 500 jobs/day | $333 | $250 | $0 | **$583** |

### Scenario C: Maximum Local (Self-Host Firecrawl + Ollama + Groq)

| Volume | Firecrawl (Self) | OpenRouter (10%) | Groq (Free) | Ollama | Hardware | Total |
|--------|------------------|------------------|-------------|--------|----------|-------|
| 10 jobs/day | $0 | $2 | $0 | $0 | Existing | **$2** |
| 50 jobs/day | $0 | $10 | $0 | $0 | Existing | **$10** |
| 100 jobs/day | $0 | $20 | $0 | $0 | Existing | **$20** |
| 500 jobs/day | $0 | $100 | $0 | $0 | Existing | **$100** |

**Hardware for self-host Firecrawl:** ~$50-100/mo VPS (4-8 CPU, 16-32GB RAM) — cheaper than Growth plan at 500 jobs/day.

---

## Cost Optimization Strategies

| Strategy | Savings | Effort |
|----------|---------|--------|
| Route classification/parsing to Ollama (local) | 60% LLM cost | Config only |
| Use Groq/Cerebras free tier for matching | Free matching | Config only |
| Use JobSpy for 90% of scraping | Eliminate Firecrawl for job boards | Already designed |
| Self-host Firecrawl at >100 jobs/day | $83→$50/mo | Docker deploy |
| Cache LLM responses (matching, research) | 20-30% repeat calls | n8n cache / Redis |
| Batch matching (single prompt for 10 jobs) | 50% matching tokens | Prompt engineering |
| Use Gemini Flash for research (1M context, cheap) | 50% vs Sonnet | Routing config |

---

## Break-Even Analysis: Self-Host Firecrawl

| Metric | Cloud (Growth) | Self-Host (VPS) |
|--------|----------------|-----------------|
| Monthly | $333 | ~$60 |
| Credits | 1M | Unlimited (hardware) |
| Maintenance | Zero | Low (Docker, updates) |
| Break-even | — | **~200 jobs/day** |

**Recommendation:** Stay on Cloud until 200+ jobs/day consistently.

---

## Cost per User (Multi-User Future)

| Users | Architecture | Cost/User/Month (50 jobs/day) |
|-------|--------------|-------------------------------|
| 1 (MVP) | Local-first | $10-180 (user chooses tier) |
| 10 | Shared n8n + APIs | $20-50 |
| 100 | Shared infra + queue | $10-30 |
| 1000 | Multi-tenant SaaS | $5-15 |

**MVP is single-user. Multi-user deferred.**

---

## Budget Recommendation for MVP

| Tier | Monthly Budget | Capabilities |
|------|----------------|--------------|
| **Free** | $0 | JobSpy + SimplifyJobs + Ollama (all local) + Groq free tier + Firecrawl free tier (1K credits) |
| **Hobby** | $20 | + Firecrawl Hobby ($16) + OpenRouter minimal ($5) |
| **Pro** | $100 | + Firecrawl Standard ($83) + OpenRouter regular ($20) |
| **Power** | $350 | + Firecrawl Growth ($333) + OpenRouter heavy ($50) |

**Default recommendation:** **Hobby tier ($20/mo)** — covers 50 jobs/day with cloud LLM for generation, local for classification.

---

## Hidden Costs to Monitor

| Cost | Risk | Mitigation |
|------|------|------------|
| OpenRouter rate limits (tier-based) | New accounts start at Tier 1 | Pre-warm with $50 spend or use Groq |
| Firecrawl credit overage | $9/1K credits | Alert at 80% usage |
| Gmail API quota | 250 quota units/sec | n8n built-in throttling |
| Playwright browser memory | Leaks in long runs | Restart browser per batch |
| Ollama model swapping | Slow if VRAM full | Keep 2 models max loaded |

---

## Summary: Cost at 50 Jobs/Day (Recommended Config)

```
┌────────────────────────────────────────────────────────────┐
│  RECOMMENDED: Privacy-First + Cloud Generation             │
├────────────────────────────────────────────────────────────┤
│  Firecrawl Standard (100K credits)     $83/mo              │
│  OpenRouter (30% frontier, 70% local)  $25/mo              │
│  n8n (self-hosted Docker)              $0/mo               │
│  Ollama (local, existing GPU)          $0/mo               │
│  Groq free tier (matching)             $0/mo               │
│  ─────────────────────────────────────────────────         │
│  TOTAL                                  $108/mo            │
│                                                             │
│  WITH OPTIMIZATIONS (batch, cache, Flash):  ~$70/mo        │
└────────────────────────────────────────────────────────────┘
```

**User controls cost via routing.yaml** — can run entirely free (local only) or scale up as needed.