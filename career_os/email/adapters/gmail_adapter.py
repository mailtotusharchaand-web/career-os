"""
career_os.email.adapters.gmail_adapter — Read-Only Gmail API Provider Adapter.

Connects to Google Gmail REST API using read-only OAuth tokens.
Normalizes raw Gmail JSON payloads into provider-neutral RawEmailMessage instances.
Enforces targeted search queries, data minimization, and privacy standards.
"""

import base64
from datetime import datetime, timezone
import json
import re
import time
from typing import List, Dict, Any, Optional
import requests

from .base import BaseEmailAdapter
from ..models import RawEmailMessage
from ..token_store import TokenStore, LocalSecureFileTokenStore
from ..oauth import GoogleOAuthClient


GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

# Default targeted search query for recruiting & job applications
DEFAULT_RECRUITING_QUERY = (
    '(subject:(application OR applied OR interview OR offer OR assessment OR "status update" OR "next steps" OR recruiter) '
    'OR from:(greenhouse.io OR ghpostings.com OR lever.co OR myworkday.com OR ashbyhq.com OR smartrecruiters.com OR icims.com OR taleo.net))'
)


def _decode_base64url(data: str) -> str:
    """Decodes standard or URL-safe base64 data to UTF-8 text."""
    if not data:
        return ""
    try:
        padded = data + "=" * (-len(data) % 4)
        raw = base64.urlsafe_b64decode(padded)
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_body_text_from_payload(payload: Dict[str, Any]) -> str:
    """Recursively extracts plain text body from multipart MIME payload."""
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime_type == "text/plain" and body_data:
        return _decode_base64url(body_data)

    parts = payload.get("parts", [])
    text_parts = []
    html_fallback = []

    for part in parts:
        part_mime = part.get("mimeType", "")
        part_body = part.get("body", {}).get("data", "")
        if part_mime == "text/plain" and part_body:
            text_parts.append(_decode_base64url(part_body))
        elif part_mime == "text/html" and part_body:
            html_text = _decode_base64url(part_body)
            # Strip basic HTML tags
            clean_text = re.sub(r"<[^>]+>", " ", html_text)
            html_fallback.append(" ".join(clean_text.split()))
        elif "parts" in part:
            nested = _extract_body_text_from_payload(part)
            if nested:
                text_parts.append(nested)

    if text_parts:
        return "\n".join(text_parts)
    if html_fallback:
        return "\n".join(html_fallback)
    if body_data:
        raw_text = _decode_base64url(body_data)
        clean = re.sub(r"<[^>]+>", " ", raw_text)
        return " ".join(clean.split())
    return ""


class GmailEmailAdapter(BaseEmailAdapter):
    """Read-only Gmail API Adapter for Career OS."""

    def __init__(
        self,
        account_email: str,
        token_store: Optional[TokenStore] = None,
        oauth_client: Optional[GoogleOAuthClient] = None,
    ):
        self.provider_name = "gmail"
        self._account_email = account_email
        self.token_store = token_store or LocalSecureFileTokenStore()
        self.oauth_client = oauth_client or GoogleOAuthClient(token_store=self.token_store)

    def is_connected(self) -> bool:
        """Checks if a valid token is available in TokenStore."""
        return self.token_store.has_token("gmail", self._account_email)

    def get_account_email(self) -> Optional[str]:
        return self._account_email if self.is_connected() else None

    def _get_valid_access_token(self) -> str:
        token_data = self.token_store.get_token("gmail", self._account_email)
        if not token_data:
            raise ConnectionError(f"No Gmail credentials stored for {self._account_email}.")

        access_token = token_data.get("access_token")
        # In a production setup with expiry tracking, if expired, refresh token:
        if not access_token and token_data.get("refresh_token"):
            refreshed = self.oauth_client.refresh_token(self._account_email)
            if refreshed:
                access_token = refreshed.get("access_token")

        if not access_token:
            raise ConnectionError(f"Unable to obtain valid access token for {self._account_email}.")
        return access_token

    def build_search_query(self, custom_query: Optional[str] = None, after_date: Optional[str] = None) -> str:
        """Constructs targeted recruiting query with date bounds."""
        base_query = custom_query if custom_query else DEFAULT_RECRUITING_QUERY
        if after_date:
            # after_date can be YYYY-MM-DD or YYYY/MM/DD
            clean_date = after_date[:10].replace("-", "/")
            return f"{base_query} after:{clean_date}"
        return base_query

    def fetch_messages(
        self,
        query: Optional[str] = None,
        max_results: int = 50,
        after_date: Optional[str] = None,
    ) -> List[RawEmailMessage]:
        if not self.is_connected():
            raise ConnectionError(f"Gmail account {self._account_email} is not connected.")

        access_token = self._get_valid_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        search_q = self.build_search_query(custom_query=query, after_date=after_date)

        # 1. List message IDs
        params = {
            "q": search_q,
            "maxResults": min(max_results, 100),
        }

        resp = requests.get(f"{GMAIL_API_BASE}/messages", headers=headers, params=params, timeout=15)
        if resp.status_code == 401:
            # Try token refresh once
            refreshed = self.oauth_client.refresh_token(self._account_email)
            if refreshed and "access_token" in refreshed:
                headers["Authorization"] = f"Bearer {refreshed['access_token']}"
                resp = requests.get(f"{GMAIL_API_BASE}/messages", headers=headers, params=params, timeout=15)

        if resp.status_code != 200:
            raise RuntimeError(f"Gmail API list messages failed: {resp.status_code} - {resp.text}")

        list_data = resp.json()
        message_stubs = list_data.get("messages", [])
        if not message_stubs:
            return []

        # 2. Fetch details for each message
        messages: List[RawEmailMessage] = []
        for stub in message_stubs:
            mid = stub.get("id")
            if not mid:
                continue

            detail_resp = requests.get(
                f"{GMAIL_API_BASE}/messages/{mid}",
                headers=headers,
                params={"format": "full"},
                timeout=10,
            )
            if detail_resp.status_code == 200:
                raw_json = detail_resp.json()
                parsed = self.parse_gmail_message(raw_json)
                if parsed:
                    messages.append(parsed)

        return messages

    def parse_gmail_message(self, raw_json: Dict[str, Any]) -> Optional[RawEmailMessage]:
        """Parses a full Gmail API message JSON object into a RawEmailMessage."""
        mid = raw_json.get("id")
        tid = raw_json.get("threadId", "")
        snippet = raw_json.get("snippet", "")
        labels = raw_json.get("labelIds", [])

        payload = raw_json.get("payload", {})
        headers_list = payload.get("headers", [])
        headers_dict = {h.get("name", "").lower(): h.get("value", "") for h in headers_list}

        subject = headers_dict.get("subject", "")
        sender = headers_dict.get("from", "")
        to_header = headers_dict.get("to", "")
        recipients = [r.strip() for r in to_header.split(",") if r.strip()]

        # Extract timestamp
        internal_date = raw_json.get("internalDate")
        if internal_date:
            try:
                received_dt = datetime.fromtimestamp(int(internal_date) / 1000.0, tz=timezone.utc)
                received_at = received_dt.isoformat()
            except Exception:
                received_at = datetime.now(timezone.utc).isoformat()
        else:
            received_at = datetime.now(timezone.utc).isoformat()

        body_text = _extract_body_text_from_payload(payload)
        if not body_text and snippet:
            body_text = snippet

        return RawEmailMessage(
            provider="gmail",
            account_id=self._account_email,
            message_id=mid,
            thread_id=tid,
            sender=sender,
            recipients=recipients,
            subject=subject,
            body_text=body_text,
            received_at=received_at,
            snippet=snippet,
            labels=labels,
            headers=headers_dict,
        )
