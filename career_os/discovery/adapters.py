"""
career_os.discovery.adapters — Isolated source adapter execution.
Translates search plan items into JobSpy, JobsPipe, Greenhouse, and Lever API/scraper calls with strict failure isolation and observable health tracking.
"""

import json
import logging
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import jobspy

log = logging.getLogger("career_os.discovery.adapters")

# Source execution status constants
STATUS_SUCCESS_WITH_RESULTS = "SUCCESS_WITH_RESULTS"
STATUS_SUCCESS_EMPTY = "SUCCESS_EMPTY"
STATUS_BLOCKED = "BLOCKED"
STATUS_ERROR = "ERROR"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_UNAVAILABLE = "UNAVAILABLE"


def _load_env_if_needed(path: str = ".env") -> None:
    """Helper to ensure .env variables are loaded into os.environ."""
    env_file = Path(path)
    if not env_file.exists():
        return
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if val and not os.environ.get(key):
                        os.environ[key] = val
    except Exception:
        pass


class _LogCaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: List[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


def execute_jobspy_adapter(source_name: str, params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str, Optional[str]]:
    """
    Executes JobSpy scraper for a specific source (indeed, linkedin, naukri, etc.).
    Captures internal library errors (like Naukri 406 recaptcha or 403 bot challenges).
    Returns (records, status, error_message).
    """
    log_capture = _LogCaptureHandler()
    root_logger = logging.getLogger()
    root_logger.addHandler(log_capture)

    # JobSpy loggers do not propagate by default, so attach handler to all JobSpy loggers
    jobspy_loggers = [
        logging.getLogger(name) for name in list(logging.root.manager.loggerDict.keys())
        if "jobspy" in name.lower()
    ]
    # Also explicitly add the target source logger
    src_logger = logging.getLogger(f"JobSpy:{source_name.capitalize()}")
    if src_logger not in jobspy_loggers:
        jobspy_loggers.append(src_logger)

    for lg in jobspy_loggers:
        lg.addHandler(log_capture)

    try:
        df = jobspy.scrape_jobs(site_name=[source_name], **params)
        records = df.to_dict("records") if (df is not None and not df.empty) else []

        # Check if JobSpy logged internal block/recaptcha errors during execution
        captured_errors = [
            r.getMessage() for r in log_capture.records
            if r.levelno >= logging.WARNING and (source_name.lower() in r.getMessage().lower() or "jobspy" in r.name.lower() or "jobspy" in r.getMessage().lower())
        ]

        if records:
            for r in records:
                r["_discovered_via_provider"] = "jobspy"
            return records, STATUS_SUCCESS_WITH_RESULTS, None
        else:
            for err_text in captured_errors:
                err_lower = err_text.lower()
                if "recaptcha" in err_lower or "406" in err_lower or "403" in err_lower or "challenge" in err_lower:
                    return [], STATUS_BLOCKED, f"Blocked: {err_text}"
                elif "429" in err_lower or "rate limit" in err_lower:
                    return [], STATUS_UNAVAILABLE, f"Rate limited: {err_text}"
                elif "timeout" in err_lower:
                    return [], STATUS_TIMEOUT, f"Timed out: {err_text}"

            return [], STATUS_SUCCESS_EMPTY, None
    except Exception as e:
        err_msg = str(e)
        err_lower = err_msg.lower()
        if "403" in err_lower or "blocked" in err_lower or "captcha" in err_lower or "406" in err_lower:
            status = STATUS_BLOCKED
        elif "429" in err_lower or "rate limit" in err_lower or "404" in err_lower:
            status = STATUS_UNAVAILABLE
        elif "timeout" in err_lower or "timed out" in err_lower:
            status = STATUS_TIMEOUT
        else:
            status = STATUS_ERROR
        return [], status, err_msg
    finally:
        root_logger.removeHandler(log_capture)
        for lg in jobspy_loggers:
            lg.removeHandler(log_capture)


def execute_jobspipe_adapter(
    search_term: str,
    country_code: str = "IN",
    location: str = "India",
    limit: int = 10,
    use_sandbox: bool = False,
    api_key: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], str, Optional[str]]:
    """
    Executes JobsPipe search API (sandbox or live).
    Request payload adheres strictly to official schema:
    { "job_title_or": [...], "job_country_code_or": [...], "job_location_or": [...], "limit": ... }
    Returns (records, status, error_message).
    """
    _load_env_if_needed()
    resolved_api_key = api_key or os.environ.get("JOBSPIPE_API_KEY")
    is_sandbox = use_sandbox or not bool(resolved_api_key)

    if is_sandbox:
        url = "https://api.jobspipe.dev/v1/sandbox/jobs/search"
    else:
        url = "https://api.jobspipe.dev/v1/jobs/search"

    payload: Dict[str, Any] = {
        "job_title_or": [search_term] if search_term else [],
        "job_country_code_or": [country_code] if country_code else ["IN"],
        "limit": limit,
    }
    if location and location.lower() != "india":
        payload["job_location_or"] = [location]

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "CareerOS/1.0 (JobDiscoveryBot)",
    }
    if not is_sandbox and resolved_api_key:
        headers["Authorization"] = f"Bearer {resolved_api_key}"

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            if response.status != 200:
                return [], STATUS_ERROR, f"HTTP {response.status}"
            raw_body = response.read().decode("utf-8")
            data = json.loads(raw_body)

        jobs_list = data.get("data", [])
        records = []

        for j in jobs_list:
            title = j.get("job_title") or j.get("title", "")
            company = j.get("company", "")
            loc = j.get("location", "")
            desc = j.get("description") or j.get("job_description") or f"{title} at {company}. Location: {loc}"
            url_val = j.get("final_url") or j.get("url") or j.get("apply_url", "")
            source_dom = j.get("source_domain") or j.get("source") or "jobspipe"
            job_id = str(j.get("id", ""))
            date_posted = (j.get("date_posted") or "")[:10]
            is_remote = bool(j.get("remote", False))

            min_salary = j.get("min_annual_salary_usd") or j.get("salary_min")
            max_salary = j.get("max_annual_salary_usd") or j.get("salary_max")
            currency = j.get("salary_currency") or j.get("currency")
            if not currency and (j.get("min_annual_salary_usd") or j.get("max_annual_salary_usd")):
                currency = "USD"

            records.append({
                "title": title,
                "company": company,
                "location": loc,
                "description": desc,
                "job_url": url_val,
                "site": "jobspipe",
                "source_job_id": job_id,
                "date_posted": date_posted,
                "job_type": "fulltime",
                "is_remote": is_remote,
                "min_amount": min_salary,
                "max_amount": max_salary,
                "currency": currency,
                "source_domain": source_dom,
                "_discovered_via_provider": "jobspipe",
                "_discovered_via_source": source_dom,
            })

        if records:
            return records, STATUS_SUCCESS_WITH_RESULTS, None
        else:
            return [], STATUS_SUCCESS_EMPTY, None

    except urllib.error.HTTPError as e:
        if e.code == 401:
            return [], STATUS_UNAVAILABLE, "JobsPipe Authentication Error (401)"
        elif e.code == 402:
            return [], STATUS_UNAVAILABLE, "JobsPipe Monthly Quota Exhausted (402)"
        elif e.code == 429:
            return [], STATUS_UNAVAILABLE, "JobsPipe Rate Limit Exceeded (429)"
        elif e.code == 403:
            return [], STATUS_BLOCKED, f"JobsPipe Forbidden (403): {e.reason}"
        return [], STATUS_ERROR, f"JobsPipe HTTP {e.code}: {e.reason}"
    except Exception as e:
        err_msg = str(e)
        if "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
            return [], STATUS_TIMEOUT, f"JobsPipe timeout: {err_msg}"
        return [], STATUS_ERROR, f"JobsPipe error: {err_msg}"


def execute_greenhouse_adapter(board_token: str, search_term: str = "", location_filter: str = "") -> Tuple[List[Dict[str, Any]], str, Optional[str]]:
    """
    Executes Greenhouse public board API: https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
    Translates response into canonical raw opportunity records.
    Returns (records, status, error_message).
    """
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    headers = {"User-Agent": "CareerOS/1.0 (JobDiscoveryBot)"}
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            if response.status != 200:
                return [], STATUS_ERROR, f"HTTP {response.status}"
            data = json.loads(response.read().decode("utf-8"))
            jobs = data.get("jobs", [])

        records = []
        term_lower = search_term.strip().lower()
        loc_lower = location_filter.strip().lower()

        for j in jobs:
            title = j.get("title", "")
            content = j.get("content", "")
            loc_obj = j.get("location", {})
            location_name = loc_obj.get("name", "") if isinstance(loc_obj, dict) else str(loc_obj)

            # Match search_term in title or content if specified
            if term_lower and term_lower not in title.lower() and term_lower not in content.lower():
                continue

            # Match location if specified
            if loc_lower and loc_lower not in location_name.lower():
                continue

            records.append({
                "title": title,
                "company": board_token.capitalize(),
                "location": location_name,
                "description": content,
                "job_url": j.get("absolute_url", ""),
                "site": "greenhouse",
                "source_job_id": str(j.get("id", "")),
                "date_posted": (j.get("updated_at") or "")[:10],
                "job_type": "fulltime",
                "is_remote": "remote" in location_name.lower() or "remote" in title.lower(),
                "_discovered_via_provider": "greenhouse",
            })

        if records:
            return records, STATUS_SUCCESS_WITH_RESULTS, None
        else:
            return [], STATUS_SUCCESS_EMPTY, None

    except urllib.error.HTTPError as e:
        if e.code == 403:
            return [], STATUS_BLOCKED, f"HTTP 403 Forbidden on Greenhouse board '{board_token}'"
        elif e.code in (404, 429):
            return [], STATUS_UNAVAILABLE, f"HTTP {e.code} on Greenhouse board '{board_token}'"
        return [], STATUS_ERROR, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        err_msg = str(e)
        if "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
            return [], STATUS_TIMEOUT, err_msg
        return [], STATUS_ERROR, err_msg


def execute_lever_adapter(company_token: str, search_term: str = "", location_filter: str = "") -> Tuple[List[Dict[str, Any]], str, Optional[str]]:
    """
    Executes Lever public postings API: https://api.lever.co/v0/postings/{company}?mode=json
    Translates response into canonical raw opportunity records.
    Returns (records, status, error_message).
    """
    url = f"https://api.lever.co/v0/postings/{company_token}?mode=json"
    headers = {"User-Agent": "CareerOS/1.0 (JobDiscoveryBot)"}
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            if response.status != 200:
                return [], STATUS_ERROR, f"HTTP {response.status}"
            jobs = json.loads(response.read().decode("utf-8"))

        records = []
        term_lower = search_term.strip().lower()
        loc_lower = location_filter.strip().lower()

        for j in jobs:
            title = j.get("text", "")
            desc = j.get("descriptionPlain") or j.get("description", "")
            categories = j.get("categories", {})
            location_name = categories.get("location", "")
            workplace_type = categories.get("workplaceType", "")
            commitment = categories.get("commitment", "")

            # Match search_term if specified
            if term_lower and term_lower not in title.lower() and term_lower not in desc.lower():
                continue

            # Match location if specified
            if loc_lower and loc_lower not in location_name.lower() and loc_lower not in workplace_type.lower():
                continue

            salary_range = j.get("salaryRange") or {}
            min_amt = salary_range.get("min")
            max_amt = salary_range.get("max")
            interval = salary_range.get("interval", "")
            currency = salary_range.get("currency", "")

            created_at_ms = j.get("createdAt")
            date_posted = ""
            if created_at_ms:
                try:
                    date_posted = time.strftime("%Y-%m-%d", time.gmtime(created_at_ms / 1000.0))
                except Exception:
                    pass

            records.append({
                "title": title,
                "company": company_token.capitalize(),
                "location": location_name,
                "description": desc,
                "job_url": j.get("hostedUrl") or j.get("applyUrl", ""),
                "site": "lever",
                "source_job_id": str(j.get("id", "")),
                "date_posted": date_posted,
                "job_type": commitment.lower() if commitment else "fulltime",
                "min_amount": min_amt,
                "max_amount": max_amt,
                "interval": interval,
                "currency": currency,
                "is_remote": workplace_type.lower() == "remote" or "remote" in location_name.lower(),
                "_discovered_via_provider": "lever",
            })

        if records:
            return records, STATUS_SUCCESS_WITH_RESULTS, None
        else:
            return [], STATUS_SUCCESS_EMPTY, None

    except urllib.error.HTTPError as e:
        if e.code == 403:
            return [], STATUS_BLOCKED, f"HTTP 403 Forbidden on Lever company '{company_token}'"
        elif e.code in (404, 429):
            return [], STATUS_UNAVAILABLE, f"HTTP {e.code} on Lever company '{company_token}'"
        return [], STATUS_ERROR, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        err_msg = str(e)
        if "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
            return [], STATUS_TIMEOUT, err_msg
        return [], STATUS_ERROR, err_msg


def execute_source_plan(
    execution_plan: List[Dict[str, Any]],
    return_health_records: bool = False
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Executes a list of source plan items with strict failure isolation and observable health tracking.
    If return_health_records is False (default for backward compatibility with existing tests),
    returns (raw_jobs, error_records) where error_records only contains failed attempts.
    If return_health_records is True, returns (raw_jobs, all_health_records).
    """
    raw_jobs = []
    health_records = []
    error_records = []

    for item in execution_plan:
        source_name = item["source"]
        params = item.get("params", {})
        intent = item.get("intent", {})
        adapter_type = item.get("adapter", "jobspy")

        start_time = time.time()
        log.info(f"Executing search on source [{source_name}] (adapter: {adapter_type}) with query: '{intent.get('search_query', '')}'")

        try:
            if adapter_type == "jobspipe":
                _load_env_if_needed()
                api_key = params.get("api_key") or os.environ.get("JOBSPIPE_API_KEY")
                use_sandbox = params.get("use_sandbox", False) or not bool(api_key)
                records, status, err_msg = execute_jobspipe_adapter(
                    search_term=params.get("search_term", intent.get("search_query", "")),
                    country_code=params.get("country_indeed", intent.get("country_code", "IN")),
                    location=params.get("location", intent.get("location_intent", "India")),
                    limit=params.get("results_wanted", 10),
                    use_sandbox=use_sandbox,
                    api_key=api_key,
                )
            elif adapter_type == "greenhouse":
                board_token = params.get("board_token", source_name)
                records, status, err_msg = execute_greenhouse_adapter(
                    board_token=board_token,
                    search_term=params.get("search_term", intent.get("search_query", "")),
                    location_filter=params.get("location", "India"),
                )
            elif adapter_type == "lever":
                company_token = params.get("company_token", source_name)
                records, status, err_msg = execute_lever_adapter(
                    company_token=company_token,
                    search_term=params.get("search_term", intent.get("search_query", "")),
                    location_filter=params.get("location", "India"),
                )
            else:
                # Default JobSpy adapter
                records, status, err_msg = execute_jobspy_adapter(source_name, params)

            duration_ms = int((time.time() - start_time) * 1000)

            for r in records:
                r["_discovered_via_source"] = source_name
                r["_search_intent"] = intent

            raw_jobs.extend(records)
            log.info(f"Source [{source_name}] status: {status}, results: {len(records)} ({duration_ms}ms)")

            health_record = {
                "source": source_name,
                "adapter": adapter_type,
                "intent": intent,
                "params": params,
                "status": status,
                "results_count": len(records),
                "duration_ms": duration_ms,
                "error": err_msg,
            }
            health_records.append(health_record)

            if err_msg or status in (STATUS_BLOCKED, STATUS_ERROR, STATUS_TIMEOUT, STATUS_UNAVAILABLE):
                error_records.append({
                    "source": source_name,
                    "intent": intent,
                    "params": params,
                    "status": status,
                    "error": err_msg or status,
                })

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            err_msg = str(e)
            log.error(f"Source [{source_name}] unhandled failure: {err_msg}")
            rec = {
                "source": source_name,
                "adapter": adapter_type,
                "intent": intent,
                "params": params,
                "status": STATUS_ERROR,
                "results_count": 0,
                "duration_ms": duration_ms,
                "error": err_msg,
            }
            health_records.append(rec)
            error_records.append({
                "source": source_name,
                "intent": intent,
                "params": params,
                "status": STATUS_ERROR,
                "error": err_msg,
            })

    if return_health_records:
        return raw_jobs, health_records
    return raw_jobs, error_records
