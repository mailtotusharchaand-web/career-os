#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
review_server.py — Lightweight Local Review Server for Career OS

Serves:
  1. Evaluation Review Workstation (index.html):
     - GET  /api/data               : Evaluation queue jobs with eligibility & decisions
     - POST /api/decide             : Updates human_review.json
     - GET  /api/summary            : Evaluation review progress summary
  2. Discovery Quality Review View (discovery.html / /discovery):
     - GET  /api/discovery/data     : Returns 129 India discovery opportunities, LLM evaluations & human reviews
     - POST /api/discovery/decide   : Atomically updates discovery_human_review.json
     - GET  /api/discovery/summary  : Returns breakdown stats across types, intents, and sources

Strict Constraints:
  - Read-only on llm_evaluations_full.json, tier1_jobs.json, llm_evaluation_review.json, india_discovery_results.json.
  - Human discovery decisions saved ONLY to discovery_human_review.json.
  - Human evaluation decisions saved ONLY to human_review.json.
  - Zero external database or cloud dependencies.
"""

import os
import sys
import json
import re
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime, timezone
import urllib.parse
from typing import Optional, Dict, Any, List

from career_os.config import load_dotenv, get_server_port, get_canonical_redirect_uri

# Ensure .env is loaded
load_dotenv()

PORT = get_server_port(8080)
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "review_ui"
REVIEW_FILE = BASE_DIR / "llm_evaluation_review.json"
TIER1_FILE = BASE_DIR / "tier1_jobs.json"
FULL_FILE = BASE_DIR / "llm_evaluations_full.json"
HUMAN_DECISIONS_FILE = BASE_DIR / "human_review.json"

# Discovery Quality Review files
DISCOVERY_RESULTS_FILE = BASE_DIR / "india_discovery_results.json"
DISCOVERY_HUMAN_FILE = BASE_DIR / "discovery_human_review.json"
DISCOVERY_EVALUATIONS_FILE = BASE_DIR / "india_discovery_llm_evaluations.json"
SQLITE_DB_FILE = BASE_DIR / "career_os.db"

# Import SQLite Repository & Email Infrastructure
try:
    from career_os.db.repository import CareerOSRepository
    db_repo = CareerOSRepository(db_path=str(SQLITE_DB_FILE))
    db_repo.init_db()
except Exception:
    db_repo = None

try:
    from career_os.email import (
        TokenStore,
        LocalSecureFileTokenStore,
        GoogleOAuthClient,
        OAuthConfigurationError,
        EmailSyncService,
        MockEmailAdapter,
        GmailEmailAdapter,
        EmailClassifier,
        OpportunityMatcher,
        format_dry_run_report,
    )
    token_store = LocalSecureFileTokenStore()
    oauth_client = GoogleOAuthClient(token_store=token_store)
except ImportError:
    token_store = None
    oauth_client = None


def normalize_geography(loc_str: str) -> str:
    if not loc_str or not isinstance(loc_str, str) or not loc_str.strip():
        return "UNKNOWN"
    
    raw = loc_str.strip()
    lower = raw.lower()
    
    # 1. Plain 'remote' or ambiguous without country/global qualifiers -> UNKNOWN
    if lower in ("remote", "remote,", "remote -", "remote/"):
        return "UNKNOWN"
        
    # 2. Remote Global / Worldwide
    if re.search(r"\b(worldwide|global|anywhere)\b", lower):
        return "REMOTE_GLOBAL"
        
    # 3. Explicit India tokens with word boundary
    india_tokens = r"\b(india|bengaluru|bangalore|gurugram|gurgaon|delhi|new delhi|noida|mumbai|hyderabad|pune|chennai|kolkata|ahmedabad|jaipur|kochi|chandigarh)\b"
    has_india = bool(re.search(india_tokens, lower))

    # 4. US state abbreviations, names, tokens, cities
    us_state_abbrs = r"\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b"
    us_state_names = r"\b(alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming)\b"
    us_country_tokens = r"\b(united states|usa|u\.s\.a\.|u\.s\.|us)\b"
    us_cities = r"\b(indianapolis|new york|chicago|san francisco|austin|dallas|seattle|denver|boston|atlanta|miami|los angeles|san jose|palo alto|mountain view|redmond|philadelphia|pittsburgh|charlotte|houston|columbus|deerfield|jersey city|midvale|salt lake city|draper|coral gables|mclean|westchester|overland park|prattville|alpharetta|arlington|bellevue|berkeley heights|brecksville|brentwood|bronx|canandaigua|carlsbad|carmel|carson city|cleveland|colorado springs|davenport|doral|el paso|englewood|frisco|hattiesburg|hornell|horsham|irvine|jacksonville|kingsport|lake mary|lehi|livingston|louisville|mason city|menlo park|nashville|new castle county|o\'fallon|oakbrook terrace|orlando|peachtree corners|peoria|plano|richmond|sacramento|san bruno|scottsdale|somerset|tampa|the woodlands|upland|waldorf|westwood)\b"

    has_us = bool(re.search(us_state_abbrs, raw) or re.search(us_state_names, lower) or re.search(us_country_tokens, lower) or re.search(us_cities, lower))

    if has_india and not has_us:
        return "INDIA"
    if has_us and not has_india:
        return "UNITED_STATES"
    if has_india and has_us:
        if re.search(r"\bindia\b", lower):
            return "INDIA"
        return "UNITED_STATES"

    # Specific country checks
    if re.search(r"\b(uk|united kingdom|london|england|scotland|wales)\b", lower):
        return "UNITED_KINGDOM"
    if re.search(r"\b(singapore)\b", lower):
        return "SINGAPORE"
    if re.search(r"\b(uae|dubai|abu dhabi)\b", lower):
        return "UAE"
    if re.search(r"\b(germany|berlin|france|paris|netherlands|amsterdam|ireland|dublin|switzerland|zurich|spain|madrid|italy|rome|sweden|stockholm)\b", lower):
        return "EUROPE"

    other_tokens = r"\b(canada|toronto|vancouver|australia|sydney|melbourne|tokyo|japan|brazil|mexico)\b"
    if re.search(other_tokens, lower):
        return "OTHER"
        
    return "UNKNOWN"


def analyze_eligibility(job: dict) -> dict:
    location = job.get("location", "")
    description = (job.get("description") or "").lower()
    
    geography = normalize_geography(location)
    is_home_country = (geography == "INDIA")
    international = (geography not in ("INDIA", "UNKNOWN"))

    # 1. Visa Sponsorship Analysis
    pos_visa_patterns = [
        r"\bvisa sponsorship available\b",
        r"\bwill sponsor\b",
        r"\bsponsorship available\b",
        r"\bvisa sponsorship is available\b",
        r"\bemployment pass sponsorship\b",
    ]
    neg_visa_patterns = [
        r"\bno visa sponsorship\b",
        r"\bunable to sponsor\b",
        r"\bnot sponsoring\b",
        r"\bwithout sponsorship\b",
        r"\bmust be authorized to work\b",
        r"\bmust possess valid work authorization\b",
        r"\bno sponsorship available\b",
        r"\bnot provide sponsorship\b",
        r"\bdoes not offer sponsorship\b",
        r"\bwill not sponsor\b",
        r"\bus citizens or permanent residents only\b",
        r"\bvalid work authorization in the united states\b",
        r"\blegally authorized to work in the united states without\b",
    ]
    
    visa_sponsorship = "UNKNOWN"
    if any(re.search(p, description) for p in neg_visa_patterns):
        visa_sponsorship = "UNAVAILABLE"
    elif any(re.search(p, description) for p in pos_visa_patterns):
        visa_sponsorship = "AVAILABLE"

    # 2. Relocation Support Analysis
    pos_reloc_patterns = [
        r"\brelocation assistance provided\b",
        r"\brelocation support available\b",
        r"\brelocation package\b",
        r"\bwill provide relocation\b",
        r"\brelocation assistance is available\b",
    ]
    neg_reloc_patterns = [
        r"\bno relocation assistance\b",
        r"\brelocation is not provided\b",
        r"\bno relocation support\b",
        r"\bnot offering relocation\b",
    ]
    
    relocation_support = "UNKNOWN"
    if any(re.search(p, description) for p in neg_reloc_patterns):
        relocation_support = "UNAVAILABLE"
    elif any(re.search(p, description) for p in pos_reloc_patterns):
        relocation_support = "AVAILABLE"

    # 3. Overall Eligibility Category
    if is_home_country:
        category = "HOME_COUNTRY"
        category_label = "Home Country (India)"
        badge_variant = "success"
    elif international:
        if visa_sponsorship == "AVAILABLE" or relocation_support == "AVAILABLE":
            category = "INTERNATIONAL_ACTIONABLE"
            category_label = "International — Actionable (Sponsorship / Relocation)"
            badge_variant = "accent"
        elif visa_sponsorship == "UNAVAILABLE":
            category = "INTERNATIONAL_EXCLUDED"
            category_label = "International — No Sponsorship (Excluded)"
            badge_variant = "danger"
        else:
            category = "INTERNATIONAL_UNKNOWN"
            category_label = "International — Sponsorship Unknown (Verify)"
            badge_variant = "warning"
    else:
        category = "UNKNOWN_LOCATION"
        category_label = "Location Unknown / Unspecified"
        badge_variant = "muted"

    return {
        "geography": geography,
        "is_home_country": is_home_country,
        "international": international,
        "visa_sponsorship": visa_sponsorship,
        "relocation_support": relocation_support,
        "eligibility_category": category,
        "eligibility_label": category_label,
        "badge_variant": badge_variant
    }


def load_descriptions_map() -> dict:
    d_map = {}
    if FULL_FILE.exists():
        try:
            with open(FULL_FILE, "r", encoding="utf-8") as f:
                f_data = json.load(f)
            for item in f_data.get("evaluations", []):
                jid = item.get("job_id")
                desc = item.get("job_description")
                if jid and desc:
                    d_map[jid] = desc
        except Exception as e:
            print(f"Warning loading full descriptions: {e}")
            
    if TIER1_FILE.exists():
        try:
            with open(TIER1_FILE, "r", encoding="utf-8") as f:
                t1_data = json.load(f)
            for idx, item in enumerate(t1_data):
                jid = item.get("job_id", f"job_{idx:04d}")
                d_map[jid] = item.get("description", "")
                url = item.get("job_url", "")
                if url:
                    d_map[url] = item.get("description", "")
        except Exception as e:
            print(f"Warning loading tier1 descriptions: {e}")
    return d_map


def load_human_decisions() -> dict:
    if HUMAN_DECISIONS_FILE.exists():
        try:
            with open(HUMAN_DECISIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning loading {HUMAN_DECISIONS_FILE}: {e}")
    return {"updated_at": None, "decisions": {}}


def save_human_decisions(data: dict) -> None:
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    temp_file = BASE_DIR / f"human_review_tmp_{os.getpid()}.json"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    temp_file.replace(HUMAN_DECISIONS_FILE)


# ---------------------------------------------------------------------------
# Discovery Quality Review Storage & Helpers
# ---------------------------------------------------------------------------

def load_discovery_evaluations() -> dict:
    """Loads LLM evaluations for discovery opportunities."""
    if not DISCOVERY_EVALUATIONS_FILE.exists():
        return {}
    try:
        with open(DISCOVERY_EVALUATIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        eval_map = {}
        for ev in data.get("evaluations", []):
            jid = ev.get("discovery_id") or ev.get("job_id")
            if jid:
                eval_map[jid] = ev
        return eval_map
    except Exception as e:
        print(f"Warning loading discovery evaluations: {e}")
        return {}


def load_discovery_data() -> dict:
    """Loads all opportunities with stable IDs and attached LLM evaluations from SQLite (or fallback JSON)."""
    if SQLITE_DB_FILE.exists() and db_repo is not None:
        try:
            return db_repo.get_workstation_data()
        except Exception as e:
            print(f"Warning loading workstation data from SQLite: {e}")

    if not DISCOVERY_RESULTS_FILE.exists():
        return {"jobs": [], "total_unique_deduped": 0, "generated_at": None}

    with open(DISCOVERY_RESULTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    eval_map = load_discovery_evaluations()

    results = data.get("results", [])
    jobs = []
    for idx, item in enumerate(results, 1):
        job_copy = dict(item)
        jid = f"disc_{idx:04d}"
        job_copy["job_id"] = jid
        job_copy["rank"] = idx
        if jid in eval_map:
            job_copy["llm_evaluation"] = eval_map[jid].get("llm_evaluation")
            job_copy["gate_failed"] = eval_map[jid].get("gate_failed", False)
            job_copy["gate_failure_reasons"] = eval_map[jid].get("gate_failure_reasons", [])
        jobs.append(job_copy)

    return {
        "jobs": jobs,
        "total_unique_deduped": len(jobs),
        "generated_at": data.get("generated_at"),
        "source_stats": data.get("source_stats", {}),
    }


def load_discovery_decisions(file_path: Path = DISCOVERY_HUMAN_FILE) -> dict:
    """Loads human decisions from SQLite (or fallback JSON when file_path is custom)."""
    if file_path == DISCOVERY_HUMAN_FILE and SQLITE_DB_FILE.exists() and db_repo is not None:
        try:
            decisions = db_repo.list_all_human_reviews()
            return {"updated_at": datetime.now(timezone.utc).isoformat(), "decisions": decisions}
        except Exception as e:
            print(f"Warning loading reviews from SQLite: {e}")

    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning loading {file_path}: {e}")
    return {"updated_at": None, "decisions": {}}


def save_discovery_decisions(data: dict, file_path: Path = DISCOVERY_HUMAN_FILE) -> None:
    """Atomically saves human decisions to discovery_human_review.json."""
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    temp_file = file_path.parent / f"discovery_review_tmp_{os.getpid()}.json"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    temp_file.replace(file_path)


def compute_discovery_summary(jobs: list, decisions: dict) -> dict:
    """Computes aggregate and breakdown statistics across types, intents, and sources."""
    total = len(jobs)
    reviewed = len(decisions)
    unreviewed = max(0, total - reviewed)

    verdicts = {"RELEVANT": 0, "ADJACENT": 0, "WEAK": 0, "IRRELEVANT": 0}
    counterfactuals = {"YES": 0, "PROBABLY": 0, "NO": 0, "UNSURE": 0}
    opportunity_statuses = {"UNKNOWN": 0, "AVAILABLE": 0, "EXPIRED": 0}
    application_statuses = {
        "NOT_APPLIED": 0,
        "READY_TO_APPLY": 0,
        "APPLIED": 0,
        "RECRUITER_CONTACT": 0,
        "INTERVIEW": 0,
        "REJECTED": 0,
        "WITHDRAWN": 0,
        "OFFER": 0,
    }

    by_type = {}
    by_intent = {}
    by_source = {}

    for job in jobs:
        jid = job.get("job_id")
        prov = job.get("provenance", {})
        otype = prov.get("opportunity_type", "unspecified")
        intent = prov.get("search_query", "unspecified")
        src = job.get("source", "unknown")

        decision = decisions.get(jid)
        opp_st = (decision.get("opportunity_status") or "UNKNOWN").upper() if decision else "UNKNOWN"
        if opp_st not in opportunity_statuses:
            opp_st = "UNKNOWN"
        opportunity_statuses[opp_st] += 1

        app_st = (decision.get("application_status") or "NOT_APPLIED").upper() if decision else "NOT_APPLIED"
        if app_st not in application_statuses:
            app_st = "NOT_APPLIED"
        application_statuses[app_st] += 1

        for bucket_dict, key in [(by_type, otype), (by_intent, intent), (by_source, src)]:
            if key not in bucket_dict:
                bucket_dict[key] = {
                    "total": 0,
                    "reviewed": 0,
                    "RELEVANT": 0,
                    "ADJACENT": 0,
                    "WEAK": 0,
                    "IRRELEVANT": 0,
                    "cf_YES": 0,
                    "cf_PROBABLY": 0,
                    "cf_NO": 0,
                    "cf_UNSURE": 0,
                }
            bucket_dict[key]["total"] += 1

            if decision:
                bucket_dict[key]["reviewed"] += 1
                v = decision.get("verdict", "").upper()
                if v in bucket_dict[key]:
                    bucket_dict[key][v] += 1
                cf = decision.get("counterfactual", "").upper()
                cf_key = f"cf_{cf}"
                if cf_key in bucket_dict[key]:
                    bucket_dict[key][cf_key] += 1

    for d in decisions.values():
        v = d.get("verdict", "").upper()
        if v in verdicts:
            verdicts[v] += 1
        cf = d.get("counterfactual", "").upper()
        if cf in counterfactuals:
            counterfactuals[cf] += 1

    return {
        "total_discovered": total,
        "total_reviewed": reviewed,
        "total_unreviewed": unreviewed,
        "verdicts": verdicts,
        "counterfactuals": counterfactuals,
        "opportunity_statuses": opportunity_statuses,
        "application_statuses": application_statuses,
        "by_opportunity_type": by_type,
        "by_search_intent": by_intent,
        "by_source": by_source,
    }


class ReviewRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        
        # Evaluation endpoints
        if parsed.path == "/api/data":
            self.send_api_data()
        elif parsed.path == "/api/summary":
            self.send_api_summary()
            
        # Discovery review endpoints
        elif parsed.path == "/api/discovery/data":
            self.send_discovery_api_data()
        elif parsed.path == "/api/discovery/summary":
            self.send_discovery_api_summary()
            
        # Gmail & Lifecycle endpoints
        elif parsed.path == "/api/gmail/status":
            self.send_gmail_status()
        elif parsed.path == "/api/gmail/auth-url":
            self.send_gmail_auth_url()
        elif parsed.path == "/api/gmail/callback":
            self.handle_gmail_oauth_callback(parsed)
        elif parsed.path == "/api/events":
            self.send_career_events(parsed)
        elif parsed.path == "/api/timeline":
            self.send_opportunity_timeline(parsed)

        # Page views
        elif parsed.path in ("/", "/index.html"):
            self.send_file_content(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        elif parsed.path in ("/discovery", "/discovery.html"):
            self.send_file_content(STATIC_DIR / "discovery.html", "text/html; charset=utf-8")
        else:
            target_path = STATIC_DIR / parsed.path.lstrip("/")
            if target_path.exists() and target_path.is_file():
                content_type = "text/plain"
                if target_path.suffix == ".html": content_type = "text/html; charset=utf-8"
                elif target_path.suffix == ".css": content_type = "text/css; charset=utf-8"
                elif target_path.suffix == ".js": content_type = "application/javascript; charset=utf-8"
                elif target_path.suffix == ".json": content_type = "application/json; charset=utf-8"
                self.send_file_content(target_path, content_type)
            else:
                self.send_error(404, f"File Not Found: {parsed.path}")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        if parsed.path == "/api/gmail/disconnect":
            self.handle_gmail_disconnect(body)
        elif parsed.path == "/api/gmail/sync":
            self.handle_gmail_sync(body)
        elif parsed.path == "/api/events/decide":
            self.handle_event_decision(body)
        elif parsed.path == "/api/decide":
            try:
                payload = json.loads(body.decode("utf-8"))
                job_id = payload.get("job_id")
                verdict = payload.get("verdict", "").upper()
                priority = payload.get("priority", "").upper()
                notes = payload.get("notes", "")

                if not job_id:
                    self.send_json_response({"error": "job_id is required"}, 400)
                    return

                decisions_data = load_human_decisions()
                decisions = decisions_data.setdefault("decisions", {})

                decisions[job_id] = {
                    "job_id": job_id,
                    "verdict": verdict,
                    "priority": priority,
                    "notes": notes,
                    "reviewed_at": datetime.now(timezone.utc).isoformat()
                }

                save_human_decisions(decisions_data)
                self.send_json_response({
                    "status": "success",
                    "job_id": job_id,
                    "decision": decisions[job_id],
                    "total_reviewed": len(decisions)
                })
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)

        elif parsed.path == "/api/discovery/decide":
            try:
                payload = json.loads(body.decode("utf-8"))
                job_id = payload.get("job_id")
                verdict = payload.get("verdict", "").upper()
                counterfactual = payload.get("counterfactual", "").upper()
                priority = payload.get("priority", "").upper()
                opportunity_status = payload.get("opportunity_status", "").upper() or "UNKNOWN"
                if opportunity_status not in ("UNKNOWN", "AVAILABLE", "EXPIRED"):
                    opportunity_status = "UNKNOWN"

                application_status = payload.get("application_status", "").upper() or "NOT_APPLIED"
                if application_status not in (
                    "NOT_APPLIED", "READY_TO_APPLY", "APPLIED",
                    "RECRUITER_CONTACT", "INTERVIEW", "REJECTED",
                    "WITHDRAWN", "OFFER"
                ):
                    application_status = "NOT_APPLIED"

                notes = payload.get("notes", "")
                opportunity_type = payload.get("opportunity_type", "")
                search_query = payload.get("search_query", "")
                source = payload.get("source", "")

                if not job_id:
                    self.send_json_response({"error": "job_id is required"}, 400)
                    return

                review_payload = {
                    "opportunity_id": job_id,
                    "job_id": job_id,
                    "verdict": verdict,
                    "counterfactual": counterfactual,
                    "priority": priority,
                    "opportunity_status": opportunity_status,
                    "application_status": application_status,
                    "notes": notes,
                    "opportunity_type": opportunity_type,
                    "search_query": search_query,
                    "source": source,
                    "reviewed_at": datetime.now(timezone.utc).isoformat()
                }

                if SQLITE_DB_FILE.exists() and db_repo is not None:
                    saved_decision = db_repo.save_human_review(review_payload)
                    all_reviews = db_repo.list_all_human_reviews()
                    self.send_json_response({
                        "status": "success",
                        "job_id": job_id,
                        "decision": saved_decision,
                        "total_reviewed": len(all_reviews)
                    })
                else:
                    decisions_data = load_discovery_decisions()
                    decisions = decisions_data.setdefault("decisions", {})
                    decisions[job_id] = review_payload
                    save_discovery_decisions(decisions_data)
                    self.send_json_response({
                        "status": "success",
                        "job_id": job_id,
                        "decision": decisions[job_id],
                        "total_reviewed": len(decisions)
                    })
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
        else:
            self.send_error(404, "Unknown endpoint")

    def send_file_content(self, path: Path, content_type: str):
        try:
            content = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")

    def send_json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def send_api_data(self):
        items = []
        desc_map = load_descriptions_map()

        if REVIEW_FILE.exists():
            with open(REVIEW_FILE, "r", encoding="utf-8") as f:
                r_data = json.load(f)
            
            queue_mappings = [
                ("Consider", r_data.get("consider_set", [])),
                ("Long Shot", r_data.get("long_shot_set", [])),
                ("Skip Top 20", r_data.get("skip_top20_set", [])),
                ("Skip Random 10", r_data.get("skip_random10_set", [])),
            ]

            for set_label, job_list in queue_mappings:
                for rank, item in enumerate(job_list, 1):
                    item_copy = dict(item)
                    item_copy["review_set"] = set_label
                    item_copy["rank_in_set"] = rank
                    
                    jid = item_copy.get("job_id")
                    url = item_copy.get("application_url")
                    jd_text = desc_map.get(jid) or desc_map.get(url) or item_copy.get("description", "")
                    item_copy["description"] = jd_text

                    # Attach eligibility analysis
                    elig_data = analyze_eligibility(item_copy)
                    item_copy.update(elig_data)
                    items.append(item_copy)

        decisions_data = load_human_decisions()
        
        self.send_json_response({
            "jobs": items,
            "decisions": decisions_data.get("decisions", {}),
            "updated_at": decisions_data.get("updated_at")
        })

    def send_api_summary(self):
        decisions_data = load_human_decisions()
        decisions = decisions_data.get("decisions", {})
        
        verdicts = {"APPLY": 0, "MAYBE": 0, "STRETCH": 0, "SKIP": 0}
        priorities = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        
        for d in decisions.values():
            v = d.get("verdict")
            if v in verdicts:
                verdicts[v] += 1
            p = d.get("priority")
            if p in priorities:
                priorities[p] += 1

        self.send_json_response({
            "total_reviewed": len(decisions),
            "verdicts": verdicts,
            "priorities": priorities,
            "last_updated": decisions_data.get("updated_at")
        })

    def send_discovery_api_data(self):
        discovery_payload = load_discovery_data()
        decisions_data = load_discovery_decisions()

        self.send_json_response({
            "jobs": discovery_payload["jobs"],
            "total_unique": discovery_payload["total_unique_deduped"],
            "decisions": decisions_data.get("decisions", {}),
            "updated_at": decisions_data.get("updated_at"),
            "source_stats": discovery_payload.get("source_stats", {}),
        })

    def send_discovery_api_summary(self):
        discovery_payload = load_discovery_data()
        decisions_data = load_discovery_decisions()
        summary = compute_discovery_summary(
            discovery_payload["jobs"],
            decisions_data.get("decisions", {})
        )
        self.send_json_response(summary)

    # ---------------------------------------------------------
    # Gmail Integration & Lifecycle Endpoints
    # ---------------------------------------------------------
    def send_gmail_status(self):
        """Returns Gmail connection status, active account email, sync metrics, and pending events."""
        accounts = token_store.list_accounts("gmail") if token_store else []
        active_account = accounts[0] if accounts else None
        is_connected = bool(active_account and token_store and token_store.has_token("gmail", active_account))

        checkpoint = None
        pending_events_count = 0

        if db_repo is not None:
            if active_account:
                checkpoint = db_repo.get_or_create_email_sync_checkpoint("gmail", active_account)
            pending_events = db_repo.list_career_events(status="PENDING_CONFIRMATION")
            pending_events_count = len(pending_events)

        active_port = getattr(self.server, 'server_port', PORT) if hasattr(self, 'server') else PORT
        canonical_redirect_uri = get_canonical_redirect_uri(port=active_port)
        oauth_configured = bool(oauth_client and oauth_client.client_id and oauth_client.client_secret)

        self.send_json_response({
            "connected": is_connected,
            "account_email": active_account,
            "provider": "gmail" if is_connected else "mock",
            "oauth_configured": oauth_configured,
            "redirect_uri": canonical_redirect_uri,
            "server_port": active_port,
            "checkpoint": checkpoint,
            "pending_events_count": pending_events_count,
        })

    def send_gmail_auth_url(self):
        """Generates OAuth authorization URL or returns configuration error without exposing secrets."""
        if not oauth_client:
            self.send_json_response({"error": "OAuth client not initialized."}, 500)
            return

        active_port = getattr(self.server, 'server_port', PORT) if hasattr(self, 'server') else PORT
        canonical_redirect_uri = get_canonical_redirect_uri(port=active_port)

        try:
            url, state = oauth_client.get_authorization_url(port=active_port)
            self.send_json_response({
                "auth_url": url,
                "state": state,
                "redirect_uri": canonical_redirect_uri,
            })
        except OAuthConfigurationError as e:
            self.send_json_response({
                "error": str(e),
                "is_config_error": True,
                "redirect_uri": canonical_redirect_uri,
                "hint": f"Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in .env. Ensure '{canonical_redirect_uri}' is added to Authorized redirect URIs in Google Cloud Console."
            }, 400)
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def handle_gmail_oauth_callback(self, parsed):
        """Handles Google OAuth2 redirect callback."""
        query_params = urllib.parse.parse_qs(parsed.query)
        code = query_params.get("code", [None])[0]
        error = query_params.get("error", [None])[0]

        if error:
            self.send_response(302)
            self.send_header("Location", f"/discovery?gmail_error={urllib.parse.quote(error)}")
            self.end_headers()
            return

        if not code:
            self.send_response(302)
            self.send_header("Location", "/discovery?gmail_error=no_code_provided")
            self.end_headers()
            return

        active_port = getattr(self.server, 'server_port', PORT) if hasattr(self, 'server') else PORT
        try:
            res = oauth_client.exchange_code_for_tokens(code, port=active_port)
            account_email = res.get("account_email", "")
            self.send_response(302)
            self.send_header("Location", f"/discovery?gmail_status=connected&email={urllib.parse.quote(account_email)}")
            self.end_headers()
        except Exception as e:
            self.send_response(302)
            self.send_header("Location", f"/discovery?gmail_error={urllib.parse.quote(str(e))}")
            self.end_headers()

    def handle_gmail_disconnect(self, body: bytes):
        """Disconnects active Gmail account."""
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
            account_email = payload.get("account_email")
            if not account_email and token_store:
                accounts = token_store.list_accounts("gmail")
                account_email = accounts[0] if accounts else None

            if account_email and token_store:
                token_store.delete_token("gmail", account_email)

            self.send_json_response({"status": "success", "message": "Gmail account disconnected."})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def handle_gmail_sync(self, body: bytes):
        """
        Executes Gmail sync in dry-run mode (default) or live mutation mode upon explicit approval.
        """
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
            dry_run = payload.get("dry_run", True)  # Hard dry-run default!
            adapter_choice = payload.get("adapter_type", "auto")
            max_results = int(payload.get("max_results", 50))
            after_date = payload.get("after_date")

            accounts = token_store.list_accounts("gmail") if token_store else []
            active_account = accounts[0] if accounts else None

            # Choose adapter
            if adapter_choice == "gmail" or (adapter_choice == "auto" and active_account and token_store.has_token("gmail", active_account)):
                adapter = GmailEmailAdapter(account_email=active_account, token_store=token_store, oauth_client=oauth_client)
            else:
                adapter = MockEmailAdapter()

            if db_repo is None:
                self.send_json_response({"error": "Database repository is not available."}, 500)
                return

            sync_service = EmailSyncService(
                adapter=adapter,
                repository=db_repo,
                classifier=EmailClassifier(),
                matcher=OpportunityMatcher(),
            )

            report = sync_service.run_sync(
                max_results=max_results,
                after_date=after_date,
                dry_run=dry_run,
            )

            formatted_ascii = format_dry_run_report(report)

            self.send_json_response({
                "status": "success",
                "dry_run": dry_run,
                "report": report.to_dict(),
                "formatted_preview": formatted_ascii,
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def send_career_events(self, parsed):
        """Lists CareerEvents with optional filtering by opportunity_id or status."""
        if db_repo is None:
            self.send_json_response({"events": []})
            return

        query_params = urllib.parse.parse_qs(parsed.query)
        opp_id = query_params.get("opportunity_id", [None])[0]
        status = query_params.get("status", [None])[0]

        events = db_repo.list_career_events(opportunity_id=opp_id, status=status)
        self.send_json_response({"events": events, "count": len(events)})

    def send_opportunity_timeline(self, parsed):
        """Returns consolidated application history and career event timeline for an opportunity."""
        query_params = urllib.parse.parse_qs(parsed.query)
        opp_id = query_params.get("opportunity_id", [None])[0]
        if not opp_id or db_repo is None:
            self.send_json_response({"timeline": []})
            return

        timeline = db_repo.get_opportunity_timeline(opp_id)
        self.send_json_response({"opportunity_id": opp_id, "timeline": timeline})

    def handle_event_decision(self, body: bytes):
        """Handles manual confirmation or dismissal of an ambiguous/pending CareerEvent."""
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
            event_id = payload.get("event_id")
            opportunity_id = payload.get("opportunity_id")
            action = payload.get("action", "confirm").lower()
            notes = payload.get("notes", "")

            if not event_id:
                self.send_json_response({"error": "event_id is required"}, 400)
                return

            if db_repo is None:
                self.send_json_response({"error": "Database repository is not available."}, 500)
                return

            if action == "confirm":
                if not opportunity_id:
                    self.send_json_response({"error": "opportunity_id is required to confirm an event."}, 400)
                    return
                success = db_repo.confirm_career_event(event_id=event_id, opportunity_id=opportunity_id, notes=notes)
            elif action == "dismiss":
                success = db_repo.dismiss_career_event(event_id=event_id, notes=notes)
            else:
                self.send_json_response({"error": f"Invalid action: {action}"}, 400)
                return

            self.send_json_response({"status": "success", "event_id": event_id, "action": action, "updated": success})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)


def run_server(port: Optional[int] = None):
    requested_port = port or PORT
    server_address = ("127.0.0.1", requested_port)
    try:
        httpd = HTTPServer(server_address, ReviewRequestHandler)
    except OSError:
        fallback_port = 8081 if requested_port == 8080 else requested_port + 1
        server_address = ("127.0.0.1", fallback_port)
        httpd = HTTPServer(server_address, ReviewRequestHandler)

    actual_port = server_address[1]
    canonical_redirect_uri = get_canonical_redirect_uri(port=actual_port)

    print(f"============================================================")
    print(f"Career OS Review Server running at http://{server_address[0]}:{actual_port}")
    print(f"  • Discovery Review UI   : http://localhost:{actual_port}/discovery")
    print(f"  • Evaluation Review UI  : http://localhost:{actual_port}/")
    print(f"  • Google OAuth Redirect : {canonical_redirect_uri}")
    if actual_port != requested_port:
        print(f"  [!] Note: Port {requested_port} was in use; bound to fallback port {actual_port}.")
        print(f"      Ensure Google Cloud Console includes: {canonical_redirect_uri}")
    print(f"============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer shutting down.")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
