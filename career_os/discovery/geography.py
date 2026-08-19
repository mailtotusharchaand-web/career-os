"""
career_os.discovery.geography — Token-aware geography parser and country normalization.
"""

import re
from typing import Dict, Any, Optional

# Standard 50 US State 2-letter postal abbreviations (infrastructure constants)
US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC"
}

# Standard Indian State/UT 2-letter codes frequently emitted by JobSpy/Indeed
INDIA_STATE_CODES = {
    "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "DN", "GA",
    "GJ", "HP", "HR", "JH", "JK", "KA", "KL", "LA", "LD", "MH",
    "ML", "MN", "MP", "MZ", "NL", "OD", "PB", "PY", "RJ", "SK",
    "TN", "TR", "TS", "UK", "UP", "WB"
}


def normalize_location(raw_loc: Optional[str]) -> Dict[str, Any]:
    """
    Normalizes a location string into structured country and remote metadata.
    Does NOT use a fragile city whitelist.
    """
    if not raw_loc or not isinstance(raw_loc, str) or not raw_loc.strip():
        return {
            "raw": "",
            "city": None,
            "state": None,
            "country_code": "UNKNOWN",
            "is_remote": False,
            "is_india": False,
        }

    raw = raw_loc.strip()
    loc_lower = raw.lower()
    is_remote = "remote" in loc_lower

    # 1. Check for explicit "India" or ", India" or " - India"
    if re.search(r"\bindia\b", loc_lower):
        return {
            "raw": raw,
            "city": None,
            "state": None,
            "country_code": "IN",
            "is_remote": is_remote,
            "is_india": True,
        }

    # 2. Check for JobSpy Indeed India pattern: "<StateCode>, IN" (e.g. "KA, IN", "TS, IN", "MH, IN", "Remote, IN")
    match_jobspy_india = re.search(r"\b([A-Z]{2}|Remote),\s*IN\b", raw, re.IGNORECASE)
    if match_jobspy_india:
        first_token = match_jobspy_india.group(1).upper()
        # If first token is an Indian state code or Remote, it's definitely India!
        if first_token in INDIA_STATE_CODES or first_token == "REMOTE":
            return {
                "raw": raw,
                "city": None,
                "state": first_token if first_token != "REMOTE" else None,
                "country_code": "IN",
                "is_remote": is_remote,
                "is_india": True,
            }

    # 3. Disambiguate US States: "<City>, <US_STATE_CODE>" (e.g. "Indianapolis, IN", "Austin, TX", "New York, NY")
    match_us_state = re.search(r",\s*([A-Z]{2})\b", raw)
    if match_us_state:
        state_code = match_us_state.group(1).upper()
        if state_code in US_STATE_CODES:
            return {
                "raw": raw,
                "city": None,
                "state": state_code,
                "country_code": "US",
                "is_remote": is_remote,
                "is_india": False,
            }

    # 4. Standard international markers
    if re.search(r"\b(united states|usa|u\.s\.a\.)\b", loc_lower):
        return {"raw": raw, "city": None, "state": None, "country_code": "US", "is_remote": is_remote, "is_india": False}
    if re.search(r"\b(united kingdom|uk|great britain|london)\b", loc_lower):
        return {"raw": raw, "city": None, "state": None, "country_code": "GB", "is_remote": is_remote, "is_india": False}
    if re.search(r"\bsingapore\b", loc_lower):
        return {"raw": raw, "city": None, "state": None, "country_code": "SG", "is_remote": is_remote, "is_india": False}
    if re.search(r"\b(dubai|uae|united arab emirates)\b", loc_lower):
        return {"raw": raw, "city": None, "state": None, "country_code": "AE", "is_remote": is_remote, "is_india": False}
    if "remote - global" in loc_lower or "global remote" in loc_lower:
        return {"raw": raw, "city": None, "state": None, "country_code": "GLOBAL", "is_remote": True, "is_india": False}

    # 5. Fallback to UNKNOWN
    return {
        "raw": raw,
        "city": None,
        "state": None,
        "country_code": "UNKNOWN",
        "is_remote": is_remote,
        "is_india": False,
    }


def is_india_location(raw_loc: Optional[str]) -> bool:
    """Returns True if the location is definitively identified as India."""
    return normalize_location(raw_loc)["is_india"]
