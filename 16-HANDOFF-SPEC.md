# Career OS — Credential-Free LinkedIn/ATS Handoff Specification

**Version:** 0.1  
**Date:** 2026-08-16  
**Status:** Draft — For Implementation

---

## 1. Design Principle

**No credentials, no OAuth, no session persistence, no cookies.**

The handoff is a **one-way data transfer** from Career OS → User's Browser. Career OS prepares the data, opens the URL, and optionally injects data via browser automation **running locally under user control**. Career OS never authenticates to LinkedIn or any ATS.

---

## 2. Threat Model

| Threat | Mitigation |
|--------|------------|
| Credential theft | No credentials stored or transmitted |
| Session hijacking | No sessions created |
| Automated application abuse | Human must click "Submit" |
| LinkedIn ToS violation | No scraping, no API abuse, human-in-the-loop |
| Data leakage | All data stays local; only user's browser sends to ATS |

---

## 3. Supported Application Types

| Type | Detection | Handoff Method |
|------|-----------|----------------|
| **LinkedIn Easy Apply** | `linkedin.com/jobs/view/*` + "Apply" button | URL open + optional Playwright data injection |
| **LinkedIn External Apply** | "Apply" → redirects to company ATS | URL open only (no injection) |
| **Greenhouse** | `boards.greenhouse.io/*` | URL open + optional injection |
| **Lever** | `jobs.lever.co/*` | URL open + optional injection |
| **Workday** | `*.myworkdayjobs.com/*` | URL open only (complex, no injection MVP) |
| **Ashby** | `jobs.ashbyhq.com/*` | URL open + optional injection |
| **Generic ATS** | Other career pages | URL open only |

---

## 4. Handoff Methods (Priority Order)

### Method 1: URL Open Only (MVP Baseline)
```python
import webbrowser
webbrowser.open(application_url)
```
- **Pros:** Zero dependencies, works everywhere, no ToS risk
- **Cons:** No data pre-fill

### Method 2: Playwright Data Injection (Enhanced)
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # User sees browser
    context = browser.new_context()
    page = context.new_page()
    page.goto(application_url)
    
    # Wait for page load
    page.wait_for_load_state("networkidle")
    
    # Inject known answers (if form detected)
    if page.locator('input[name="firstName"]').count() > 0:
        page.fill('input[name="firstName"]', "Tushar")
        page.fill('input[name="lastName"]', "Chaand")
        page.fill('input[name="email"]', "tusharchaand8@gmail.com")
        # ... more fields
    
    # Keep browser open for user to review/submit
    page.wait_for_event("close")  # Wait until user closes tab
```
- **Pros:** Pre-fills known fields, user reviews before submit
- **Cons:** Requires Playwright, form selectors brittle, LinkedIn may block

### Method 3: Browser Extension (Future)
- User installs Career OS browser extension
- Extension reads local JSON, fills forms on any page
- **Pros:** Most robust, works on any site
- **Cons:** Requires extension install, maintenance

---

## 5. Data Injection Strategy

### Known Fields Mapping (LinkedIn Easy Apply)

| Career OS Field | LinkedIn Selector (example) | Fallback |
|-----------------|----------------------------|----------|
| First Name | `input[name="firstName"]` | `input[id*="firstName"]` |
| Last Name | `input[name="lastName"]` | `input[id*="lastName"]` |
| Email | `input[name="email"]` | `input[type="email"]` |
| Phone | `input[name="phoneNumber"]` | `input[type="tel"]` |
| Resume | `input[type="file"][accept*="pdf"]` | `input[id*="resume"]` |
| Cover Letter | `textarea[name="coverLetter"]` | `textarea[id*="coverLetter"]` |
| LinkedIn Profile | `input[name="linkedinUrl"]` | `input[id*="linkedin"]` |
| Portfolio | `input[name="portfolioUrl"]` | `input[id*="portfolio"]` |

### Common ATS Fields (Greenhouse, Lever, Ashby)

| Field | Selector Pattern |
|-------|-----------------|
| First Name | `input[name*="first_name"], input[id*="first_name"]` |
| Last Name | `input[name*="last_name"], input[id*="last_name"]` |
| Email | `input[type="email"], input[name*="email"]` |
| Phone | `input[type="tel"], input[name*="phone"]` |
| Resume | `input[type="file"][accept*="pdf"]` |
| Cover Letter | `textarea[name*="cover"], textarea[id*="cover"]` |
| LinkedIn | `input[name*="linkedin"], input[id*="linkedin"]` |
| Portfolio/Website | `input[name*="portfolio"], input[name*="website"]` |
| Gender | `select[name*="gender"], input[name*="gender"]` |
| Race/Ethnicity | `select[name*="race"], select[name*="ethnicity"]` |
| Veteran Status | `select[name*="veteran"]` |
| Disability | `select[name*="disability"]` |
| Sponsorship | `select[name*="sponsor"], input[name*="sponsor"]` |
| Authorization | `select[name*="authorized"], input[name*="authorized"]` |

---

## 6. Injection Algorithm

```python
def inject_known_answers(page, answers: dict, field_map: dict) -> dict:
    """
    Attempt to fill known fields on the current page.
    Returns: {field: "filled" | "not_found" | "error"}
    """
    results = {}
    
    for field, value in answers.items():
        if not value:
            results[field] = "skipped_empty"
            continue
        
        selectors = field_map.get(field, [])
        filled = False
        
        for selector in selectors:
            try:
                element = page.locator(selector).first
                if element.count() > 0:
                    element.fill(value)
                    results[field] = "filled"
                    filled = True
                    break
            except Exception as e:
                results[field] = f"error: {e}"
        
        if not filled:
            results[field] = "not_found"
    
    return results
```

---

## 7. Resume / Cover Letter Handling

| Document | Handling |
|----------|----------|
| **Resume (PDF)** | If `input[type="file"]` found, set file path. User must confirm upload. |
| **Cover Letter (text)** | If `textarea` found, fill text. User reviews. |
| **Portfolio URL** | If field exists, fill URL. |

**Rule:** Never auto-upload files. Always require user to click "Attach" or confirm file selection.

---

## 7. LinkedIn Easy Apply Specifics

### Flow
1. User on job page → clicks "Apply" → Easy Apply modal opens
2. Modal steps: Contact Info → Resume → Questions → Review → Submit
3. Each step is a separate DOM state

### Challenges
- Modal is iframe or shadow DOM in some cases
- Selectors change frequently
- LinkedIn actively detects automation

### MVP Approach
1. Open URL → user manually clicks "Apply"
2. User completes Contact Info step (name, email, phone pre-filled by browser autofill)
4. **Career OS pauses** — user handles Resume upload + Questions manually
5. User clicks Submit

**Rationale:** LinkedIn Easy Apply is the hardest to automate reliably. Credential-free approach = human does the hard parts.

---

## 8. External ATS (Greenhouse, Lever, Ashby, etc.)

### Approach
1. Open URL
2. Detect ATS type from URL/domain
4. Inject known fields (name, email, phone, LinkedIn, portfolio)
5. **Pause for user** — resume upload, custom questions, EEO, submit

### Selector Strategy
- Use multiple fallback selectors per field
- Log which selectors worked for future improvement
- Never fail silently — report what was/wasn't filled

---

## 9. User Interaction Protocol

```
1. career-os queue handoff app_001
   │
   ▼
2. Opens browser (Playwright or webbrowser)
   │
   ▼
3. Injects known fields (if Playwright mode)
   │
   ▼
4. Prints injection report:
   ✓ First Name: filled
   ✓ Last Name: filled
   ✓ Email: filled
   ✓ Phone: filled
   ✗ Resume: not_found (manual upload needed)
   ✗ Q1 "Years of experience": not_found (manual entry needed)
   ✗ Q2 "Visa sponsorship": not_found (manual entry needed)
   │
   ▼
5. Keeps browser open — user reviews, fills gaps, clicks Submit
   │
   ▼
6. User closes tab → Career OS marks handoff_complete
```

---

## 10. Implementation Phases

### Phase 1: URL Open Only (Week 1)
- `webbrowser.open(url)`
- Print application URL to terminal
- User manually applies

### Phase 2: Playwright Injection (Week 2)
- Launch visible Chromium
- Inject known fields (name, email, phone, LinkedIn, portfolio)
- Handle file upload prompts (pause for user)
- Keep browser open until user closes

### Phase 3: Smart Detection (Week 3+)
- Detect ATS type from URL
- Load ATS-specific selector maps
- Handle multi-step forms (Greenhouse, Lever)
- Cache successful selectors per domain

---

## 10. Configuration

```yaml
# config/handoff.yaml
mode: "playwright"  # "webbrowser" | "playwright"

browser:
  headless: false
  slow_mo: 100  # ms between actions
  viewport: {width: 1280, height: 800}

injection:
  enabled: true
  pause_for_user: true
  log_results: true

selectors:
  linkedin:
    first_name: ['input[name="firstName"]', 'input[id*="firstName"]']
    last_name: ['input[name="lastName"]', 'input[id*="lastName"]']
    email: ['input[name="email"]', 'input[type="email"]']
    phone: ['input[name="phoneNumber"]', 'input[type="tel"]']
    resume: ['input[type="file"][accept*="pdf"]']
    cover_letter: ['textarea[name="coverLetter"]', 'textarea[id*="coverLetter"]']
    linkedin_url: ['input[name="linkedinUrl"]']
    portfolio_url: ['input[name="portfolioUrl"]']
  
  greenhouse:
    first_name: ['input[name*="first_name"]', 'input[id*="first_name"]']
    last_name: ['input[name*="last_name"]', 'input[id*="last_name"]']
    email: ['input[type="email"]', 'input[name*="email"]']
    phone: ['input[type="tel"]', 'input[name*="phone"]']
    resume: ['input[type="file"][accept*="pdf"]']
    cover_letter: ['textarea[name*="cover"]', 'textarea[id*="cover"]']
    linkedin_url: ['input[name*="linkedin"]', 'input[id*="linkedin"]']
    portfolio_url: ['input[name*="portfolio"]', 'input[name*="website"]']
  
  lever:
    # similar pattern
    ...
  
  ashby:
    # similar pattern
    ...

default_fallbacks:
  first_name: ['input[name*="first"]', 'input[id*="first"]']
  last_name: ['input[name*="last"]', 'input[id*="last"]']
  email: ['input[type="email"]']
  phone: ['input[type="tel"]']
  resume: ['input[type="file"][accept*="pdf"]']
  cover_letter: ['textarea[name*="cover"]', 'textarea[id*="cover"]']
```

---

## 11. Error Handling

| Error | Handling |
|-------|----------|
| Browser launch fails | Fallback to `webbrowser.open()` |
| Selector not found | Log, continue, report to user |
| Page load timeout | Wait longer, retry once, then report |
| LinkedIn blocks automation | Detect, fallback to URL-only mode |
| File upload dialog | Pause, instruct user to attach manually |

---

## 12. Logging & Audit

```json
{
  "application_id": "app_001",
  "handoff_timestamp": "2026-08-16T15:45:00Z",
  "mode": "playwright",
  "url": "https://www.linkedin.com/jobs/view/4454544359",
  "ats_type": "linkedin_easy_apply",
  "injection_results": {
    "first_name": "filled",
    "last_name": "filled",
    "email": "filled",
    "phone": "filled",
    "resume": "not_found",
    "cover_letter": "not_found",
    "linkedin_url": "filled",
    "portfolio_url": "filled"
  },
  "user_submitted": true,
  "completed_at": "2026-08-16T15:47:30Z"
}
```

---

## 13. Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `playwright` | 1.40+ | Browser automation (optional, Phase 2+) |
| `webbrowser` | stdlib | URL opening (Phase 1) |
| `pyyaml` | 6.0+ | Config loading |

---

## 14. Files to Create

| File | Purpose |
|------|---------|
| `career_os/handoff/__init__.py` | Module entry |
| `career_os/handoff/launcher.py` | URL open + Playwright launch |
| `career_os/handoff/injector.py` | Field injection logic |
| `career_os/handoff/selectors.py` | Selector maps per ATS |
| `career_os/handoff/config.yaml` | Configuration |
| `career_os/handoff/logger.py` | Audit logging |

---

## 15. CLI Interface

```bash
# Phase 1: URL only
career-os handoff --app-id app_001 --mode url

# Phase 2: Playwright injection
career-os handoff --app-id app_001 --mode playwright

# Dry run: show what would be injected
career-os handoff --app-id app_001 --dry-run
```

---

## 16. Questions for Review

1. **Playwright vs Selenium vs CDP?** Playwright chosen for modern API, auto-wait, stealth options.
2. **Headless vs headed?** Headed (visible) required for human review — no headless.
3. **Stealth mode?** Use `playwright-stealth` or `--disable-blink-features=AutomationControlled` for LinkedIn.
4. **Profile persistence?** No — fresh context per handoff. No cookies, no login state.
5. **Mobile vs desktop?** Desktop only for MVP.
6. **Rate limiting?** N/A — human-paced, one application at a time.