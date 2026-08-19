# Career OS — Job Scout
# Red-Team Architecture

## 1. Executive Verdict

**The previous architecture is massively over-engineered for the MVP.** It proposes 15+ external dependencies, n8n orchestration, multiple browser automation frameworks, and ~1,050 lines of glue code — when the core user need (CV → relevant jobs → ranked results) can be delivered in **<80 lines of Python** using only JobSpy + Ollama + a JSON file.

**Red-team conclusion:**
- **n8n: REMOVE** from MVP. Add back only when scheduling/email monitoring is needed.
- **Firecrawl: REMOVE** from MVP. JobSpy covers 90% of job boards for free locally.
- **Browser Automation: REMOVE** from MVP. Application URLs come with job data; form-fill is optional polish.
- **SQLite: REPLACE** with JSON. Simpler, portable, zero dependencies.
- **Career-Ops Tracker: DEFER**. Adopt its TSV schema ideas, but don't integrate the Go TUI yet.
- **Multiple LLMs: CONSOLIDATE**. Ollama (Nemotron/Llama) handles parsing, matching, classification, generation for .
- **OpenRouter: OPTIONAL**. Only for "power mode" when local quality isn't sufficient.

**The Absolute Minimum is a single Python script (~80 lines) that runs this weekend.**

---

## 2. Current Architecture Being Challenged

From documents 06, 09, 10, the proposed stack:

| Layer | Components |
|-------|------------|
| Orchestration | n8n (self-hosted Docker), 5 workflows |
| Local LLM | Ollama (Llama 3.2 3B, 3.3 70B, Nemotron) |
| Cloud LLM | OpenRouter (Sonnet, Opus, GPT-4o, Gemini, Groq, Cerebras) |
| Job Scraping | JobSpy + SimplifyJobs + Firecrawl API + Arbeitnow + LoopCV + Adzuna |
| Browser Auto | Playwright MCP + Browser Use + mcp-playwright-browser |
| Web Content | Firecrawl API (cloud) |
| Email | n8n Gmail/Outlook nodes (OAuth) |
| Storage | SQLite + TSV (Career-Ops format) |
| Document Gen | fpdf2 / weasyprint |
| Tracking | Career-Ops tracker (Go TUI) + custom tracker.py |
| Config | schema.yaml, routing.yaml, 9 prompt files |
| Adapters | jobspy_adapter.py, simplify_adapter.py, firecrawl_adapter.py |

**Estimated custom code: ~1,050 lines (Python/YAML/Markdown/JSON)**

---

## 3. Component-by-Component Red Team

| Component | Current Role | Decision | Reason | MVP? |
|-----------|--------------|----------|--------|------|
| **n8n** | Orchestration, scheduling, email triggers, workflows | **REMOVE** (A, B) | Overhead for MVP. Python schedule + cron + Gmail API direct is <50 lines. Add back only when visual workflows needed. | ❌ |
| **Ollama** | Local LLM runtime | **KEEP** | Only way to get /month + privacy. Nemotron 3 Ultra handles all tasks. | ✅ A, B |
| **Nemotron 3 Ultra** | Primary local model | **KEEP** | Single model for parsing, matching, classification, generation. Proven quality. | ✅ A, B |
| **JobSpy** | Job board scraping (8 sources) | **KEEP** | Core discovery. Free, local, MIT, active. Covers LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter. | ✅ A, B |
| **SimplifyJobs** | Curated new-grad roles (12K+) | **KEEP** | Free, daily updated, JSON/MD. Git clone + cron pull. High signal for early career. | ✅ A, B |
| **Firecrawl API** | Web search, scraping, JD extraction | **REMOVE** (A) / **OPTIONAL** (B) | JobSpy covers job boards. Firecrawl needed only for company career pages / custom searches.  free tier = 1K credits ≈ 50 jobs. Defeats  guarantee at scale. | ❌ A / ⚠️ B |
| **OpenRouter** | Cloud LLM router (200+ models) | **REMOVE** (A) / **OPTIONAL** (B) | Nemotron/Ollama handles all MVP tasks locally. Only add if local quality fails for generation tasks. | ❌ A / ⚠️ B |
| **Groq / Cerebras** | Free cloud LLM for matching | **REMOVE** (A) / **OPTIONAL** (B) | Nemotron matches locally for free. No need for external API. | ❌ A / ⚠️ B |
| **Playwright MCP** | Browser automation (accessibility tree) | **REMOVE** (A, B) | Apply URLs come with job data. Form-fill is nice-to-have, not MVP. Adds browser dependency. | ❌ |
| **Browser Use** | Agent-driven browser automation | **REMOVE** (A, B) | Same as above. Overkill for MVP. | ❌ |
| **mcp-playwright-browser** | 71 specialized job/form tools | **REMOVE** (A, B) | Specialized tools for problems we don't have yet. | ❌ |
| **Career-Ops Tracker** | Go TUI + TSV + SQLite tracker | **DEFER** / **REPLACE** | Excellent reference schema. But Go TUI adds binary dependency. Use JSON tracker for MVP. Adopt TSV schema later. | ❌ A / ⚠️ B |
| **SQLite** | Job cache + tracker storage | **REPLACE** with JSON | JSON is simpler: human-readable, git-friendly, zero deps, portable. SQLite adds sqlite3 dependency and binary format. For <10K jobs, JSON is fine. | ✅ A, B (as JSON) |
| **TSV** | Career-Ops tracker format | **DEFER** | Adopt schema ideas. Use JSON for MVP. | ❌ A / ⚠️ B |
| **fpdf2 / weasyprint** | PDF generation | **REMOVE** (A) / **OPTIONAL** (B) | MVP shows markdown/HTML. PDF is polish. User can print to PDF from browser. | ❌ A / ⚠️ B |
| **python-docx / pdfplumber / MarkItDown** | CV parsing | **KEEP** (minimal) | Need ONE library. markitdown (Microsoft, 173K★) handles PDF + DOCX + more in one import. | ✅ A, B |
| **Custom Adapters (3)** | Normalize sources → internal schema | **CONSOLIDATE** to 1 | Single 
ormalize_job() function handles JobSpy + SimplifyJobs dict → internal schema. ~30 lines. | ✅ A, B |
| **Custom Schemas (YAML)** | Candidate, Job, Tracker contracts | **KEEP** (minimal) | Python dataclasses / Pydantic models in-code. No separate YAML files needed. | ✅ A, B |
| **Prompt Files (9)** | LLM prompt templates | **CONSOLIDATE** to 3 | parse_cv, match_job, generate_materials cover 90%. Inline in Python as docstrings. | ✅ A, B |
| **Gmail/Outlook Monitoring** | Email classification → tracker update | **DEFER** to B | Requires OAuth setup. MVP (A) works without it. B adds ~50 lines using Gmail API direct (no n8n). | ❌ A / ✅ B |
| **Notifications** | Email/Slack/desktop alerts | **REMOVE** (A) / **SIMPLIFY** (B) | print() + plyer desktop notification is enough. n8n nodes removed. | ❌ A / ⚠️ B |
| **Scheduling** | n8n cron triggers | **REPLACE** | Python schedule library or system cron. 3 lines. | ✅ A, B |
| **Human Approval** | n8n Manual Approval + CLI prompt | **SIMPLIFY** | input("Apply to {job}? [y/N]: ") — 1 line. | ✅ A, B |
| **Docker Compose** | n8n + Ollama orchestration | **REMOVE** (A) / **SIMPLIFY** (B) | Ollama runs as ollama serve (background). No Docker needed for MVP. | ❌ A / ⚠️ B |
## 4. Absolute Minimum Architecture
**Target: <100 lines custom code | $0/month | Works this weekend**
### Data Flow
### Components (5 total)
| Component | Purpose | Lines |
|-----------|---------|-------|
| `markitdown` | PDF/DOCX -> text | 0 (pip install) |
| `python-jobspy` | Scrape 8 job boards | 0 (pip install) |
| `ollama` (Nemotron) | Parse CV, match jobs, rank | 0 (local) |
| `simplify_jobs.py` | Clone/pull SimplifyJobs repo | ~15 |
| `scout.py` | Main script: CV -> jobs -> match -> rank -> display | ~65 |

**Total custom code: ~80 lines**
### File Structure

```
career-os/
+-- scout.py              # Main CLI (~65 lines)
+-- simplify_jobs.py      # SimplifyJobs sync (~15 lines)
+-- candidate.json        # Parsed CV profile
+-- jobs.json             # Cached job listings
+-- requirements.txt      # markitdown, python-jobspy, ollama, requests
+-- .gitignore
```
### The scout.py Core Logic (Pseudocode)

```python
#!/usr/bin/env python3
# scout.py — Absolute Minimum Job Scout (~65 lines)

import json, subprocess, ollama
from jobspy import scrape_jobs
from markitdown import MarkItDown

# 1. LOAD OR PARSE CV
def get_candidate():
    try: return json.load(open("candidate.json"))
    except:
        text = MarkItDown().convert("cv.pdf").text_content
        profile = ollama.chat(model="nemotron3:ultra", messages=[{
            "role": "user", "content": f"Extract JSON: skills, experience_years, roles, location_prefs, salary_min, remote_ok from:\n{text[:8000]}"
        }])["message"]["content"]
        candidate = json.loads(profile)
        json.dump(candidate, open("candidate.json", "w"), indent=2)
        return candidate

# 2. FETCH JOBS (JobSpy + SimplifyJobs)
def fetch_jobs(candidate):
    # JobSpy: LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter
    jobs = scrape_jobs(
        site_name=["linkedin", "indeed", "glassdoor", "google", "zip_recruiter"],
        search_term=" ".join(candidate["skills"][:5]),
        location=candidate.get("location_prefs", "Remote"),
        results_wanted=50
    ).to_dict("records")

    # SimplifyJobs: curated new-grad (sync separately via simplify_jobs.py)
    try:
        jobs += json.load(open("simplify_jobs.json"))
    except: pass

    return jobs

# 3. MATCH & RANK (single LLM call per job)
def match_job(candidate, job):
    prompt = f"""Score 0-100: Candidate vs Job. Return JSON: {"score": int, "reason": "..."}"""
Candidate: {json.dumps(candidate)}
Job: {json.dumps({k: job[k] for k in ["title","company","description","location","salary"]})}"""
    return json.loads(ollama.chat(model="nemotron3:ultra", messages=[{"role": "user", "content": prompt}])["message"]["content"])

# 4. MAIN
candidate = get_candidate()
jobs = fetch_jobs(candidate)
print(f"Found {len(jobs)} jobs. Matching...")

results = []
for job in jobs:
    m = match_job(candidate, job)
    if m["score"] >= 60:  # threshold
        results.append({**job, "match_score": m["score"], "match_reason": m["reason"]})

results.sort(key=lambda x: -x["match_score"])
for i, r in enumerate(results[:20]):
    print(f"{i+1}. [{r[\"match_score\"]}%] {r[\"title\"]} @ {r[\"company\"]} — {r[\"location\"]}")
    print(f"    {r[\"match_reason\"][:120]}...")
    print(f"    Apply: {r.get(\"job_url\", \"N/A\")}\n")

json.dump(results, open("jobs.json", "w"), indent=2)
```
### SimplifyJobs Sync (simplify_jobs.py)

```python
# simplify_jobs.py — Run via cron daily
import json, subprocess, os
repo = "SimplifyJobs/New-Grad-Positions"
if not os.path.exists(repo):
    subprocess.run(["git", "clone", "--depth=1", "https://github.com/{repo}"])
else:
    subprocess.run(["git", "-C", repo, "pull"])
# Parse .md files in repo -> simplify_jobs.json (standard schema)
# ~15 lines using frontmatter + markdown parsing
```
---
## 5. Practical Free MVP Architecture

**Target: <300 lines custom code | /month | Includes Gmail/Outlook monitoring | Daily usable**

### Added Capabilities (vs Absolute Minimum)

1. **Gmail/Outlook monitoring** — OAuth + incremental sync -> classify emails -> update tracker
2. **Persistent tracker** — JSON file with application status, notes, materials
3. **Material generation** — Tailored CV, cover letter, interview prep (on demand)
4. **Scheduled discovery** — Background job fetch (cron or schedule lib)
5. **Human approval gate** — Before any application
### Data Flow

```
+------------+     +------------+     +------------+
|  CV File   |---->| MarkItDown |---->|  Ollama    |----> candidate.json
+------------+     +------------+     +------------+
                        ^                    |
                 +------+------+             |
                 | SimplifyJobs|             |
                 | (cron pull) |             |
                 +-------------+             |
                                          v
+------------+     +------------+     +------------+     +------------+
|  JobSpy    |---->| Normalize  |---->|  Ollama    |---->|  jobs.json  |
|  (cron)    |     |  + Dedup   |     |  (match)   |     |  (cached)   |
+------------+     +------------+     +------------+     +------------+
                                          ^
                                          |
                 +---------------------------+
                 |
                 v
+------------+     +------------+     +------------+     +------------+
|  Gmail/    |---->|  Ollama    |---->|  4-Priority|---->|  tracker    |
|  Outlook   |     |  Classify  |     |  Match     |     |  .json      |
|  (cron)    |     |            |     |            |     |             |
+------------+     +------------+     +------------+     +------------+
                        ^                    ^
                        |                    |
                 +------------+          |
                 |  Desktop   |          |
                 |  Notify    |          |
                 +------------+          |
                                          |
```
### Components (12 total)

| Component | Purpose | Lines |
|-----------|---------|-------|
| markitdown | PDF/DOCX -> text | 0 |
| python-jobspy | Job board scraping | 0 |
| ollama (Nemotron) | All LLM tasks | 0 |
| google-auth + google-api-python-client | Gmail API | 0 |
| requests-oauthlib | Outlook/Graph API | 0 |
| plyer | Desktop notifications | 0 |
| schedule | Background scheduling | 0 |
| scout.py | Main CLI + match + generate + apply flow | ~120 |
| simplify_jobs.py | SimplifyJobs sync | ~15 |
| gmail_sync.py | Gmail OAuth + incremental sync + classify | ~50 |
| outlook_sync.py | Graph API + delta sync + classify | ~50 |
| tracker.py | JSON tracker CRUD + status enum | ~40 |

**Total custom code: ~275 lines**
### Key Differences from Absolute Minimum

| Feature | Implementation |
|---------|----------------|
| Tracker | tracker.json with fields: id, job_id, status, match_score, tailored_cv, cover_letter, interview_prep, notes, created_at, updated_at |
| Status Enum | discovered -> interested -> applied -> screening -> interview -> offer -> rejected -> ghosted |
| Gmail Sync | historyId incremental sync -> fetch new messages -> Ollama classify -> 4-priority match (exact company+role -> fuzzy company -> sender domain -> manual) |
| Outlook Sync | deltaLink incremental sync -> same classification pipeline |
| Material Gen | On-demand: ollama.chat with tailor_cv, cover_letter, interview_prep prompts -> save to tracker |
| Scheduling | schedule.every(4).hours.do(fetch_jobs) + schedule.every(15).minutes.do(sync_emails) |
| Notifications | plyer.notification.notify(title=Job Scout, message=Acme Corp -> screening) |
---
## 6. Power Mode Architecture

**Optional future upgrades — explicitly marked as OPTIONAL**

### Additions (each independently optional)

| Upgrade | When to Add | Cost | Effort |
|---------|-------------|------|--------|
| Firecrawl API | JobSpy misses company career pages; need custom searches | -333/mo | 10 lines adapter |
| OpenRouter | Nemotron quality insufficient for generation tasks | -50/mo | Update routing in prompts |
| Playwright MCP | Need form-fill assistance on complex ATS (Greenhouse, Lever, Workday) |  (local) | Add MCP config + 20 lines |
| Browser Use | Need agent-driven navigation for non-standard apply flows |  (local) | uv add browser-use |
| Career-Ops Tracker (Go TUI) | Want polished Kanban dashboard |  | Download binary |
| SQLite | Job cache >10K records; JSON slow |  | Swap storage backend |
| PDF Generation | Need ATS-compliant PDF output |  | fpdf2 from markdown |
| n8n | Want visual workflow editing, complex branching, non-dev users |  (self-hosted) | Docker compose + workflows |
| Google Sheets Sync | Want mobile access / sharing |  | Add Sheets API to tracker |
| Vector Search | Semantic search across job history |  (local) | chromadb + embeddings |
| Custom LinkedIn Scraper | JobSpy LinkedIn blocking |  | Playwright + selectors |

### Power Mode Data Flow

```
                    +-----------------+
                    |   Firecrawl     | <--- Custom searches, company pages
                    +--------+--------+
                             |
+------------+     +--------v--------+     +------------+
|  JobSpy    |---->|  Normalize +    |---->|  SQLite    |
|  + Simplify|     |  Dedup + Vector |     |  + ChromaDB|
```
---
## 7.  Cost Proof

### Architecture A (Absolute Minimum)

| Component | Cost | Reason |
|-----------|------|--------|
| markitdown |  | MIT, local |
| python-jobspy |  | MIT, local scraping |
| ollama + Nemotron |  | Local, runs on existing hardware |
| simplify_jobs.py |  | GitHub public repo, git clone |
| Python stdlib (json, subprocess, schedule) |  | Built-in |
| **Total** | **/month** | No external APIs, no cloud services |

### Architecture B (Practical Free MVP)

| Component | Cost | Reason |
|-----------|------|--------|
| All from A |  | |
| google-auth + Gmail API |  | Free tier: 1B quota units/day |
| requests-oauthlib + Graph API |  | Free tier: generous |
| plyer |  | MIT, local notifications |
| plyer |  | MIT, local notifications |
| schedule |  | MIT, local scheduling |
| **Total** | **/month** | OAuth APIs are free. No n8n, no Firecrawl, no OpenRouter. |

### Why This Works

- **Job discovery**: JobSpy hits job boards directly (no API key). SimplifyJobs is static files.
- **LLM**: Nemotron 3 Ultra on Ollama runs locally. Zero API calls.
- **Email**: Gmail/Graph APIs are free with OAuth. Processing happens locally via Ollama.
- **Storage**: JSON files on disk.
- **Scheduling**: schedule library or system cron.
- **Notifications**: plyer uses native OS notification system.

**No recurring costs. Ever.** Unless you voluntarily add Firecrawl/OpenRouter.
---
## 8. Custom Code Estimate

| Architecture | Files | Est. Lines | Breakdown |
|--------------|-------|------------|-----------|
| **A. Absolute Minimum** | 2 | **~80** | scout.py (65) + simplify_jobs.py (15) |
| **B. Practical Free MVP** | 6 | **~275** | scout.py (120) + simplify_jobs.py (15) + gmail_sync.py (50) + outlook_sync.py (50) + tracker.py (40) |
| **C. Power Mode** | +8 | **+400** | Adapters, PDF gen, n8n workflows, ChromaDB, TUI integration |

**Both A and B are well under targets (<100 and <300 lines respectively).**
---
---
## 9. Dependencies — Why They Survive Red Team

| Dependency | Architecture | Why It Survives |
|------------|--------------|-----------------|
| python-jobspy | A, B | Only free library covering 8 job boards. Active (July 2026). MIT. No replacement. |
| markitdown | A, B | Microsoft, 173K★. Handles PDF + DOCX + PPTX + more in one import. Replaces 3 libs. |
| ollama | A, B | Only way to run Nemotron locally for . No alternative for privacy + zero cost. |
| nemotron3:ultra | A, B | Single model handles parsing, matching, classification, generation. Proven. |
| SimplifyJobs repo | A, B | Only free curated new-grad dataset. Daily updated. 17K★. |
| google-auth / google-api-python-client | B | Official Gmail API. Free. No n8n needed. |
| requests-oauthlib | B | Standard OAuth for Microsoft Graph. Free. |
| plyer | B | Cross-platform desktop notifications. Pure Python. |
| schedule | B | Pure Python scheduling. No cron dependency. 3 lines to use. |

**Every dependency is: free, local-first, actively maintained, permissive license, and replaces multiple alternatives.**
---
## 10. What We Explicitly Will NOT Build

| Capability | Rejected Approach | Why |
|------------|-------------------|-----|
| Custom resume parser | NLP pipeline | markitdown + Nemotron extracts structured JSON |
| Custom job matching engine | Vector DB + semantic search | Nemotron matches on-demand with reasoning |
| Custom interview question DB | Curated database | Nemotron generates STAR questions contextually |
| Vector database | Pinecone/Weaviate/Qdrant | Not needed — context window fits all jobs |
| RAG pipeline | Custom retrieval | Job data fits in context; Firecrawl for web (Power Mode) |
| Custom job board | Custom aggregator | JobSpy + SimplifyJobs cover 95% |
| Custom ATS tracker | Full-stack app | JSON tracker + Career-Ops schema ideas sufficient |
| Custom browser automation | Selenium/Puppeteer framework | Not needed for MVP; Playwright MCP in Power Mode |
| Custom search engine | Elasticsearch/Meilisearch | JobSpy searches job boards directly |
| Custom email server | IMAP/SMTP handling | Gmail/Graph APIs free with OAuth |
| Custom LLM | Fine-tuned model | Nemotron + prompting sufficient |
| Career knowledge graph | Neo4j + ontology | YAGNI — LLM has knowledge |
| n8n workflows | Visual orchestration | Python schedule + functions = <20 lines |
| PDF generation | fpdf2/weasyprint | Markdown output sufficient; print to PDF from browser |
| Frontend/TUI | React/Go TUI | CLI + chat (Claude Code/OpenCode) is the interface |
---
## 11. Risks and Limitations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| JobSpy breaks on site changes | Medium | High | JobSpy actively maintained; SimplifyJobs backup; Firecrawl in Power Mode |
| Nemotron quality insufficient | Low | High | OpenRouter fallback in Power Mode; prompt tuning |
| Gmail/Outlook OAuth complexity | Low | Medium | Use official libraries; document setup; Power Mode adds n8n for visual OAuth |
| LinkedIn blocking JobSpy | Medium | Medium | SimplifyJobs covers many LinkedIn roles; rotate user-agent; Power Mode adds Playwright |
| JSON performance at scale | Low | Low | Switch to SQLite in Power Mode (>10K jobs) |
| No visual dashboard | N/A | Medium | Career-Ops Go TUI in Power Mode; CLI + chat works for MVP |
| Email sync reliability | Low | Medium | Incremental sync (historyId/deltaLink); retry with backoff |
| Nemotron hallucination in matching | Low | Medium | Structured output + score threshold (60+); user reviews top 20 |
---
## 12. Weekend Build Plan

Goal: Working Absolute Minimum (Architecture A) by Sunday night.

### Saturday Morning (2 hours)
- pip install markitdown python-jobspy ollama
- Write scout.py core: CV parse -> JobSpy fetch -> match -> rank -> display
- Test with your CV + software engineer search

### Saturday Afternoon (2 hours)
- Add SimplifyJobs sync (simplify_jobs.py)
- Add JSON caching (jobs.json, candidate.json)
- Add match threshold + reasoning display
- Test end-to-end: CV -> 20 ranked jobs with apply URLs

### Sunday Morning (1 hour)
- Polish CLI: arguments for role, location, remote, salary
- Add tracker.json minimal (save interested jobs)
- Add human approval: input(Apply? [y/N]: )

### Sunday Afternoon (1 hour)
- Document setup in README.md
- Verify 0 cost: no API keys needed
- Push to GitHub (optional)

Total: ~6 hours. Shippable.
---
## 13. Final Recommendation

What is the smallest system we can build this weekend that can actually find relevant jobs from my CV and show me the results?

Answer: A single Python file (~80 lines) called scout.py that:

1. Parses your CV using markitdown + local Nemotron 3 Ultra via Ollama -> candidate.json
2. Fetches jobs from 8 job boards via python-jobspy + SimplifyJobs repo -> raw job list
3. Matches each job against your profile using Nemotron -> score (0-100) + reasoning
4. Ranks and displays top 20 matches with apply URLs
5. Saves results to jobs.json for reference

Requirements:
- Python 3.10+
- ollama serve running with nemotron3:ultra pulled
- pip install markitdown python-jobspy ollama
- Your CV as cv.pdf
---
## 13. Final Recommendation

What is the smallest system we can build this weekend that can actually find relevant jobs from my CV and show me the results?

Answer: A single Python file (~80 lines) called scout.py that:

1. Parses your CV using markitdown + local Nemotron 3 Ultra via Ollama -> candidate.json
2. Fetches jobs from 8 job boards via python-jobspy + SimplifyJobs repo -> raw job list
3. Matches each job against your profile using Nemotron -> score (0-100) + reasoning
4. Ranks and displays top 20 matches with apply URLs
5. Saves results to jobs.json for reference

Requirements:
- Python 3.10+
- ollama serve running with nemotron3:ultra pulled
- pip install markitdown python-jobspy ollama
- Your CV as cv.pdf

Run: python scout.py --role AI Engineer --location Remote --salary 180000

Output: Ranked list of relevant jobs with match scores, reasoning, and direct apply links.

Cost: 0/month. No API keys. No Docker. No n8n. No Firecrawl. No browser automation. No database.
This is the Absolute Minimum. It works. Build it this weekend.

---
