"""
career_os.discovery.normalizer — Canonical schema mapping and deterministic exact deduplication.
"""

import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple


def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, float):
        return "" if val != val else str(val)  # NaN check
    return str(val).strip()


def extract_salary_from_text(text: str) -> Optional[str]:
    """
    Extracts Indian salary representations from job descriptions when structured fields are missing.
    Supports formats like 'Up to 10 LPA', '₹10,00,000 a year', '₹50,000 - ₹70,000 per month', etc.
    """
    if not text:
        return None

    # Clean markdown escape backslashes (\., \-, etc.)
    cleaned = text.replace(r"\.", ".").replace(r"\-", "-").replace(r"\_", "_").replace(r"\*", "*")

    # 1. CTC / Salary headers e.g. **CTC:** Up to 10 LPA or CTC: 12-18 LPA or Salary: ₹10,00,000 a year
    ctc_match = re.search(
        r'(?:\*\*|\b)(?:CTC|Salary|Package|Pay|Compensation)(?:\*\*|\b)?\s*[:\-–]\s*([^\n\r*#_]+)',
        cleaned,
        re.IGNORECASE,
    )
    if ctc_match:
        val = ctc_match.group(1).strip().strip('*_`')
        if re.search(r'(?:LPA|lpa|INR|₹|Rs\.?|lakh|crore|\d+\s*(?:a|per)\s*(?:year|annum|month|yr|mo)|\d{5,})', val, re.IGNORECASE):
            return val

    # 2. Explicit Rupee amount patterns e.g. ₹10,00,000 - ₹20,00,000 a year, ₹50,000 - ₹70,000 a month
    rupee_match = re.search(
        r'(₹\s*[\d,]+(?:\.\d{2})?(?:\s*-\s*₹?\s*[\d,]+(?:\.\d{2})?)?(?:\s*(?:a|per)\s*(?:year|month|annum|yr|mo))?)',
        cleaned,
        re.IGNORECASE,
    )
    if rupee_match:
        return rupee_match.group(1).strip()

    # 3. LPA standalone pattern e.g. 10-15 LPA, Up to 10 LPA, 12 LPA
    lpa_match = re.search(r'((?:Up to\s+)?\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?\s*LPA)', cleaned, re.IGNORECASE)
    if lpa_match:
        return lpa_match.group(1).strip()

    return None


def parse_salary_details(raw: Dict[str, Any]) -> Tuple[Optional[int], Optional[int], str, Optional[str], str]:
    """
    Parses structured bounds, interval, currency, and raw string from scraper/API payloads or descriptions.
    Returns (salary_min, salary_max, salary_interval, currency, salary_raw).
    """
    min_amt = raw.get("min_amount") or raw.get("salary_min")
    max_amt = raw.get("max_amount") or raw.get("salary_max")
    interval = _safe_str(raw.get("interval") or raw.get("salary_interval") or "")
    currency = raw.get("currency") or None
    raw_salary = _safe_str(raw.get("salary") or raw.get("raw_salary") or raw.get("pay") or "")

    desc = _safe_str(raw.get("description", ""))

    # If min/max already numeric from scraper
    if min_amt is not None or max_amt is not None:
        try:
            min_val = int(float(min_amt)) if min_amt is not None else None
            max_val = int(float(max_amt)) if max_amt is not None else min_val
            if not currency and (min_val or max_val):
                currency = "INR"
            if not raw_salary:
                if min_val and max_val and min_val != max_val:
                    raw_salary = f"₹{min_val:,} - ₹{max_val:,} {interval}".strip()
                elif min_val:
                    raw_salary = f"₹{min_val:,} {interval}".strip()
            return min_val, max_val, interval, currency, raw_salary
        except (ValueError, TypeError):
            pass

    # If not structured, look in raw_salary string or description
    text = raw_salary or extract_salary_from_text(desc) or ""
    if not text:
        return None, None, "", None, ""

    salary_raw = text
    if not currency:
        currency = "INR" if ("₹" in text or "lpa" in text.lower() or "inr" in text.lower() or "rs" in text.lower() or "lakh" in text.lower()) else None

    # Check LPA format e.g. 'Up to 10 LPA', '8-12 LPA', '10 LPA'
    lpa_m = re.search(r'(?:(?:from|up to)\s+)?(\d+(?:\.\d+)?)(?:\s*[-–]\s*(\d+(?:\.\d+)?))?\s*LPA', text, re.IGNORECASE)
    if lpa_m:
        val1 = int(float(lpa_m.group(1)) * 100000)
        val2 = int(float(lpa_m.group(2)) * 100000) if lpa_m.group(2) else val1
        return val1, val2, "yearly", "INR", salary_raw

    # Check Lakhs format e.g. '10-15 Lakhs'
    lakh_m = re.search(r'(\d+(?:\.\d+)?)(?:\s*[-–]\s*(\d+(?:\.\d+)?))?\s*Lakhs?', text, re.IGNORECASE)
    if lakh_m:
        val1 = int(float(lakh_m.group(1)) * 100000)
        val2 = int(float(lakh_m.group(2)) * 100000) if lakh_m.group(2) else val1
        return val1, val2, "yearly", "INR", salary_raw

    # Check numeric amounts in text e.g. ₹10,00,000 a year, ₹50,000/month
    nums = re.findall(r'[\d,]+(?:\.\d+)?', text)
    clean_nums = []
    for n in nums:
        try:
            clean_nums.append(float(n.replace(",", "")))
        except ValueError:
            pass

    intvl = "yearly" if re.search(r'year|annum|yr', text, re.IGNORECASE) else ("monthly" if re.search(r'month|mo', text, re.IGNORECASE) else interval)
    if clean_nums:
        min_v = int(clean_nums[0])
        max_v = int(clean_nums[1]) if len(clean_nums) > 1 else min_v
        return min_v, max_v, intvl, currency, salary_raw

    return None, None, intvl, currency, salary_raw


def normalize_job(raw: Dict[str, Any], query_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Maps raw scraper/API records to canonical Career OS opportunity schema with provenance.
    """
    ctx = query_context or {}
    source_domain = _safe_str(raw.get("source_domain") or "")
    site_name = _safe_str(raw.get("site") or raw.get("_discovered_via_source") or "unknown")
    source_name = source_domain if source_domain else site_name

    provider_name = _safe_str(raw.get("_discovered_via_provider") or ("jobspipe" if "jobspipe" in (site_name, source_domain) else "jobspy"))
    search_query = _safe_str(ctx.get("search_query") or (raw.get("_search_intent") or {}).get("search_query") or "")

    description = _safe_str(raw.get("description", ""))
    s_min, s_max, s_interval, s_curr, s_raw = parse_salary_details(raw)
    job_url_val = _safe_str(raw.get("job_url", ""))

    sources_list = []
    if source_domain:
        sources_list.append(source_domain)
    if site_name and site_name not in sources_list:
        sources_list.append(site_name)
    if not sources_list and source_name:
        sources_list.append(source_name)

    return {
        "title": _safe_str(raw.get("title", "")),
        "company": _safe_str(raw.get("company", "")),
        "location": _safe_str(raw.get("location", "")),
        "description": description,
        "job_url": job_url_val,
        "source": source_name,
        "date_posted": _safe_str(raw.get("date_posted", "")),
        "job_type": _safe_str(raw.get("job_type", "")),
        "salary_min": s_min,
        "salary_max": s_max,
        "salary_interval": s_interval,
        "currency": s_curr,
        "salary_raw": s_raw,
        "is_remote": bool(raw.get("is_remote", False)),
        "provenance": {
            "sources": sources_list,
            "providers": [provider_name] if provider_name else [],
            "search_query": search_query,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    }


def dedupe_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicates opportunities based on conservative multi-signal canonical key: (title, company, location).
    Merges sources, providers, keeps earliest date_posted, and preserves longest description.
    """
    seen: Dict[tuple, Dict[str, Any]] = {}

    for j in jobs:
        title = j.get("title", "").strip().lower()
        company = j.get("company", "").strip().lower()
        location = j.get("location", "").strip().lower()
        
        key = (title, company, location)

        if key not in seen:
            # Copy to avoid mutating original dictionary unexpectedly
            item = dict(j)
            item["provenance"] = dict(j.get("provenance", {}))
            item["provenance"]["sources"] = list(j.get("provenance", {}).get("sources", []))
            item["provenance"]["providers"] = list(j.get("provenance", {}).get("providers", []))
            seen[key] = item
        else:
            existing = seen[key]
            # Merge sources list in provenance preserving order and uniqueness
            for s in j.get("provenance", {}).get("sources", []):
                if s and s not in existing["provenance"]["sources"]:
                    existing["provenance"]["sources"].append(s)

            # Merge providers list in provenance preserving order and uniqueness
            for p in j.get("provenance", {}).get("providers", []):
                if p and p not in existing["provenance"].get("providers", []):
                    if "providers" not in existing["provenance"]:
                        existing["provenance"]["providers"] = []
                    existing["provenance"]["providers"].append(p)

            # Preserve earliest date_posted
            if j.get("date_posted") and (not existing.get("date_posted") or j["date_posted"] < existing["date_posted"]):
                existing["date_posted"] = j["date_posted"]

            # Preserve longest description
            if len(j.get("description", "")) > len(existing.get("description", "")):
                existing["description"] = j["description"]

            # Preserve salary if missing in existing
            if not existing.get("salary_min") and j.get("salary_min"):
                existing["salary_min"] = j["salary_min"]
                existing["salary_max"] = j.get("salary_max")
                existing["salary_interval"] = j.get("salary_interval")
                existing["currency"] = j.get("currency")

            if not existing.get("salary_raw") and j.get("salary_raw"):
                existing["salary_raw"] = j["salary_raw"]

            # Preserve URL if missing in existing
            if not existing.get("job_url") and j.get("job_url"):
                existing["job_url"] = j["job_url"]

    return list(seen.values())
