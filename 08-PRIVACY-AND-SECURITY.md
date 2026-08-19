# Career OS — Privacy & Security Analysis

**Date:** 2026-08-15  
**Scope:** Data sensitivity evaluation for every external service in Job Scout

---

## Data Sensitivity Classification

| Data Type | Sensitivity | Regulation | Retention |
|-----------|-------------|------------|-----------|
| CV/Resume (full text) | **CRITICAL** | GDPR, CCPA | User-controlled |
| Contact Info (email, phone, address) | **CRITICAL** | GDPR, CCPA | User-controlled |
| Salary Expectations | **HIGH** | — | User-controlled |
| Work History / Experience | **HIGH** | — | User-controlled |
| Skills / Certifications | **MEDIUM** | — | User-controlled |
| Job Preferences (location, remote, visa) | **MEDIUM** | — | User-controlled |
| Job Descriptions (public) | **LOW** | — | Cache only |
| Company Info (public) | **LOW** | — | Cache only |
| Application Status | **MEDIUM** | — | User-controlled |
| Recruiter Emails | **HIGH** | GDPR, CCPA | User-controlled |
| Email Metadata (sender, subject, date) | **MEDIUM** | — | User-controlled |
| LLM Prompts/Responses | **VARIES** | Depends on content | Configurable |

---

## External Service Privacy Assessment

### 1. LLM Providers

| Provider | Data Leaves Machine? | Where? | Self-Hostable? | PII Minimization | Local Option | Training on Data? | Verdict |
|----------|---------------------|--------|----------------|------------------|--------------|-------------------|---------|
| **Ollama (Local)** | **No** | Local RAM/VRAM | Yes | Full control | Native | **No** | **DEFAULT for parsing/classification** |
| **OpenRouter** | Yes | Provider's infra → Model provider | No | Strip names/emails before send | Via OpenRouter | Varies by upstream | **Generation tasks only** |
| **Anthropic (Direct)** | Yes | Anthropic (US) | No | Strip PII | No | **No** (per policy) | Via OpenRouter |
| **OpenAI (Direct)** | Yes | OpenAI (US) | No | Strip PII | No | **No** (per policy) | Via OpenRouter |
| **Google Gemini** | Yes | Google (US) | No | Strip PII | No | **No** (per policy) | Via OpenRouter |
| **Groq** | Yes | Groq (US) | No | Strip PII | No | **No** | Free tier for matching |
| **Cerebras** | Yes | Cerebras (US) | No | Strip PII | No | **No** | Free tier for matching |

**PII Minimization Strategy:**
```
Before sending to cloud LLM:
1. Replace names → "CANDIDATE"
2. Replace emails → "EMAIL_REDACTED"
3. Replace phones → "PHONE_REDACTED"
4. Replace addresses → "LOCATION_REDACTED"
5. Keep: skills, experience, companies, dates, technologies
```

**Routing Enforcement (routing.yaml):**
```yaml
parse_cv: ollama          # Never leaves machine
match_job: groq/ollama    # Free, fast, no PII needed
tailor_cv: openrouter     # Needs quality, PII stripped
cover_letter: openrouter  # Needs quality, PII stripped
app_answers: openrouter   # Needs quality, PII stripped
interview_prep: openrouter # Needs quality, PII stripped
classify_email: ollama    # High volume, sensitive content
company_research: openrouter # Public info mostly
```

---

### 2. Web Scraping / Content APIs

| Service | Data Leaves Machine? | Where? | Self-Hostable? | What Data Sent? | Retention | Verdict |
|---------|---------------------|--------|----------------|-----------------|-----------|---------|
| **Firecrawl Cloud** | Yes | Firecrawl (US) | Yes (AGPL) | URLs + page content | Per policy | **Primary, self-host at scale** |
| **Firecrawl Self-Hosted** | **No** | Local | Yes | URLs only | User-controlled | **At >200 jobs/day** |
| **Apify** | Yes | Apify (EU/US) | No | URLs + page content | Per actor | **Avoid for sensitive** |
| **JobSpy (Library)** | **No** | Direct to job sites | Yes | Search queries only | None | **Primary for job boards** |
| **SimplifyJobs (GitHub)** | **No** | Local clone | Yes | None (static files) | None | **Primary for new grad** |
| **Arbeitnow API** | Yes | Arbeitnow (EU) | No | Search query | Per policy | **Free, EU-based** |
| **LoopCV API** | Yes | LoopCV (EU) | No | Search query | GDPR | **Supplement** |

**Key Insight:** JobSpy + SimplifyJobs = **zero external data transfer** for 90% of job discovery.

---

### 3. Email Services

| Service | Data Leaves Machine? | Where? | Self-Hostable? | Auth | Data Access | Verdict |
|---------|---------------------|--------|----------------|------|-------------|---------|
| **Gmail API** | Yes | Google (US) | No | OAuth2 | Full email content | **Required** |
| **Microsoft Graph** | Yes | Microsoft (US) | No | OAuth2 | Full email content | **Required** |
| **n8n (Cloud)** | Yes | n8n (EU) | **Yes (Docker)** | OAuth2 | Full email content | **Self-host n8n** |
| **n8n (Self-Hosted)** | **No** | Local | Yes | OAuth2 | Full email content | **DEFAULT** |

**Email Processing Flow (Privacy-Preserving):**
```
Gmail/Outlook → n8n (local) → Ollama (local) → Classification → Local Tracker
                    ↓
              Only METADATA to notifications (Slack/email/desktop)
              Full email content NEVER leaves local n8n+Ollama pipeline
```

**OAuth Token Storage:** n8n encrypts at rest. User controls n8n instance.

---

### 4. Browser Automation

| Tool | Data Leaves Machine? | Where? | Self-Hostable? | Session Data | Verdict |
|------|---------------------|--------|----------------|--------------|---------|
| **Playwright MCP** | **No** | Local browser | Yes | Local (cookies, storage) | **DEFAULT** |
| **Browser Use (Local)** | **No** | Local browser | Yes | Local | **DEFAULT** |
| **Browser Use Cloud** | Yes | Browser Use | No | Cloud browser | **Avoid** |
| **mcp-playwright-browser** | **No** | Local browser | Yes | Local (exportable) | **DEFAULT** |

**Session Persistence:** User can export/import storage state (cookies, localStorage) for authenticated sites. Stored locally in `output/` (gitignored).

---

### 5. Document Processing

| Tool | Data Leaves Machine? | Where? | Self-Hostable? | Verdict |
|------|---------------------|--------|----------------|---------|
| **MarkItDown / pdfplumber / python-docx** | **No** | Local | Yes | **DEFAULT** |
| **fpdf2 / weasyprint** | **No** | Local | Yes | **DEFAULT** |
| **Unstructured.io API** | Yes | Unstructured | No | **Avoid** |

---

### 6. Storage

| Storage | Data Leaves Machine? | Encryption | User Controls? | Verdict |
|---------|---------------------|------------|----------------|---------|
| **SQLite (Local)** | **No** | Optional (SQLCipher) | Full | **DEFAULT** |
| **TSV Files (Local)** | **No** | Optional (GPG) | Full | **DEFAULT** |
| **Google Sheets** | Yes | Google-managed | Partial | **OPT-IN ONLY** |
| **n8n Internal DB** | **No** (self-hosted) | n8n-managed | Full | **DEFAULT** |

---

## Privacy Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER'S MACHINE                                │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    ALL SENSITIVE DATA STAYS HERE             │   │
│  │  • CV/Resume (cv.yaml)                                       │   │
│  │  • Email content (processed by local Ollama)                 │   │
│  │  • Tracker data (SQLite, TSV)                                │   │
│  │  • Generated documents (tailored_cvs/)                       │   │
│  │  • OAuth tokens (n8n encrypted)                              │   │
│  │  • Browser sessions (Playwright storage_state)               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│         ┌──────────────────┼──────────────────┐                    │
│         ▼                  ▼                  ▼                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐           │
│  │   OLLAMA    │    │   N8N       │    │  PLAYWRIGHT │           │
│  │  (Local)    │    │  (Local)    │    │  (Local)    │           │
│  └─────────────┘    └─────────────┘    └─────────────┘           │
│         │                  │                  │                    │
│         ▼                  ▼                  ▼                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              MINIMAL EXTERNAL CALLS (PII-STRIPPED)           │   │
│  │  • OpenRouter: Generation tasks only (name/email stripped)  │   │
│  │  • Groq/Cerebras: Matching (no PII needed)                  │   │
│  │  • Firecrawl: Public URLs only (JD, company pages)          │   │
│  │  • JobSpy: Direct to job boards (search queries only)       │   │
│  │  • Gmail/Graph: OAuth only (email processed locally)        │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: What Leaves the Machine (Minimal Set)

| Operation | Data Sent | Destination | PII Stripped? | User Consent |
|-----------|-----------|-------------|---------------|--------------|
| CV Parsing | **None** | Ollama (local) | N/A | Implicit (local) |
| Job Search (JobSpy) | Search keywords | Job boards (direct) | N/A (no PII) | Implicit |
| Job Search (SimplifyJobs) | **None** | Local Git clone | N/A | Implicit |
| Job Search (Firecrawl) | Public URLs | Firecrawl API | N/A (public) | Explicit (API key) |
| Job Matching | CV skills + JD (no name/email) | Groq/Ollama | **Yes** | Explicit |
| CV Tailoring | CV skills + JD (no name/email) | OpenRouter | **Yes** | Explicit per job |
| Cover Letter | CV skills + JD (no name/email) | OpenRouter | **Yes** | Explicit per job |
| App Answers | CV skills + JD + question | OpenRouter | **Yes** | Explicit per job |
| Interview Prep | CV skills + JD + company | OpenRouter | **Yes** | Explicit per job |
| Email Classification | Email body (no headers) | Ollama (local) | **Yes** | Implicit (local) |
| Company Research | Public URL | Firecrawl/OpenRouter | N/A (public) | Explicit |
| Notifications | Job title + company + status | n8n → Slack/email | Minimal | Configurable |

---

## Compliance Considerations

| Regulation | Applicability | Job Scout Approach |
|------------|---------------|-------------------|
| **GDPR** | EU users | Data minimization, local storage, right to export/delete (delete `~/career-os/data/`), no tracking |
| **CCPA** | California users | Same as GDPR. No sale of data. Opt-out = don't use cloud LLMs. |
| **Email Privacy** | All users | OAuth with minimal scopes. Process locally. No email storage beyond tracker metadata. |
| **ToS Compliance** | Job boards | JobSpy respects robots.txt, rate limits. Firecrawl respects ToS. No LinkedIn Easy Apply automation. |

---

## Security Controls

| Control | Implementation |
|---------|----------------|
| **Credential Storage** | n8n encrypted credential store. API keys in `.env` (gitignored, file perms 600). |
| **Network** | n8n binds to 127.0.0.1. No inbound ports. Outbound allowlist in routing.yaml. |
| **Browser Isolation** | Playwright launches isolated contexts. Storage state exported/imported per site. |
| **Input Validation** | All adapters validate external data before writing to SQLite. |
| **Audit Logging** | Structured JSON logs in `~/career-os/logs/`. No PII in logs (hashes only). |
| **Updates** | `docker compose pull && docker compose up -d` for n8n/Ollama. `pip install -U` for Python deps. |
| **Backup** | User owns `~/career-os/data/`. Can sync via Syncthing, rsync, or cloud backup of choice. |

---

## Threat Model

| Threat | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| Cloud LLM logs PII | Low (major providers don't train on API data) | High | PII stripping + local-first routing |
| n8n compromise | Low (local, no inbound) | High | Bind to localhost, update regularly |
| OAuth token theft | Low (encrypted at rest) | High | n8n encryption, short-lived tokens |
| Firecrawl data leak | Low | Medium | Self-host at scale, minimal PII sent |
| Job board blocking | Medium | Low | JobSpy proxies, rate limits, respect ToS |
| Malicious JD injection | Low | Medium | Input validation, sandboxed LLM prompts |

---

## User Privacy Controls (Built-In)

| Control | How |
|---------|-----|
| **Run fully local** | Set `routing.yaml` all tasks → Ollama. No cloud API keys needed. |
| **Delete all data** | `rm -rf ~/career-os/data/` — complete erasure. |
| **Export all data** | `~/career-os/data/` is portable (SQLite, TSV, YAML, PDF). |
| **Disable email monitoring** | Don't configure Gmail/Outlook in n8n. |
| **Disable notifications** | Remove notification nodes from n8n workflows. |
| **Choose LLM per task** | Edit `config/routing.yaml` — full control. |
| **Audit what's sent** | Enable debug logging → see exact prompts to OpenRouter. |

---

## Privacy Verdict

**Job Scout can operate 95% locally with zero external data transfer for sensitive operations.**

| Mode | External Calls | Use Case |
|------|----------------|----------|
| **Maximum Privacy** | Job boards only (JobSpy direct) | User has GPU, runs Ollama |
| **Balanced (Default)** | + OpenRouter (generation), Firecrawl (web), Groq (matching) | Most users |
| **Cloud-First** | All cloud APIs | No GPU, convenience priority |

**No mandatory cloud dependency for core functionality.** User chooses privacy/cost tradeoff via configuration.