"""
career_os.email.oauth — Google OAuth2 Flow Manager for Read-Only Gmail Access.

Enforces strict security rules:
- Scope is strictly locked to 'https://www.googleapis.com/auth/gmail.readonly'
- Zero plaintext credential storage in domain models
- Integrates with TokenStore abstraction
- Actionable configuration error messages when environment variables are absent.
"""

import os
import urllib.parse
import json
import secrets
from typing import Dict, Any, Optional, Tuple
import requests

from .token_store import TokenStore, LocalSecureFileTokenStore


READONLY_GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
USERINFO_EMAIL_SCOPE = "https://www.googleapis.com/auth/userinfo.email"
ALL_REQUIRED_SCOPES = [READONLY_GMAIL_SCOPE, USERINFO_EMAIL_SCOPE]

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


class OAuthConfigurationError(Exception):
    """Raised when OAuth credentials are not properly configured."""
    pass


class GoogleOAuthClient:
    """Manages Google OAuth2 authorization, token exchange, and refresh flows."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        token_store: Optional[TokenStore] = None,
    ):
        self.client_id = client_id or os.getenv("GMAIL_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("GMAIL_CLIENT_SECRET", "")
        self.redirect_uri = redirect_uri or os.getenv("GMAIL_REDIRECT_URI", "http://localhost:8080/api/gmail/callback")
        self.token_store = token_store or LocalSecureFileTokenStore()

    def validate_configuration(self) -> None:
        """Validates that necessary OAuth environment variables or arguments are present."""
        missing = []
        if not self.client_id:
            missing.append("GMAIL_CLIENT_ID")
        if not self.client_secret:
            missing.append("GMAIL_CLIENT_SECRET")
        if missing:
            raise OAuthConfigurationError(
                f"Missing Google OAuth configuration: {', '.join(missing)}.\n"
                f"Please add them to your .env file or configure GoogleOAuthClient directly.\n"
                f"Redirect URI configured: {self.redirect_uri}"
            )

    def get_authorization_url(self, state: Optional[str] = None) -> Tuple[str, str]:
        """
        Generates Google OAuth2 authorization URL strictly requesting read-only Gmail access.
        Returns: (authorization_url, state_nonce)
        """
        self.validate_configuration()
        state_nonce = state or secrets.token_urlsafe(16)

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(ALL_REQUIRED_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state_nonce,
            "include_granted_scopes": "true",
        }
        url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
        return url, state_nonce

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """
        Exchanges authorization code for access and refresh tokens.
        """
        self.validate_configuration()

        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }

        response = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=10)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to exchange OAuth code for tokens: {response.status_code} - {response.text}")

        token_data = response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("Token response missing access_token.")

        # Fetch user's email address
        account_email = self.fetch_user_email(access_token)

        # Store securely in TokenStore
        token_data["client_id"] = self.client_id
        token_data["account_email"] = account_email
        self.token_store.save_token(provider="gmail", account_id=account_email, token_data=token_data)

        return {
            "account_email": account_email,
            "token_data": token_data,
        }

    def fetch_user_email(self, access_token: str) -> str:
        """Fetches the authenticated user's email address from Google UserInfo API."""
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(GOOGLE_USERINFO_URL, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("email", "unknown_user@gmail.com")
        return "unknown_user@gmail.com"

    def refresh_token(self, account_email: str) -> Optional[Dict[str, Any]]:
        """Refreshes access token for a stored account if refresh token exists."""
        self.validate_configuration()
        existing_token = self.token_store.get_token("gmail", account_email)
        if not existing_token or not existing_token.get("refresh_token"):
            return None

        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": existing_token["refresh_token"],
            "grant_type": "refresh_token",
        }

        response = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=10)
        if response.status_code != 200:
            return None

        new_tokens = response.json()
        # Keep original refresh token if not returned
        if "refresh_token" not in new_tokens:
            new_tokens["refresh_token"] = existing_token["refresh_token"]
        new_tokens["client_id"] = self.client_id
        new_tokens["account_email"] = account_email

        self.token_store.save_token("gmail", account_email, new_tokens)
        return new_tokens
