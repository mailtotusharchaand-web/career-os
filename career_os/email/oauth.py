"""
career_os.email.oauth — Google OAuth2 Flow Manager for Read-Only Gmail Access.

Enforces strict security rules:
- Scope is strictly locked to 'https://www.googleapis.com/auth/gmail.readonly'
- Zero plaintext credential storage in domain models
- Integrates with TokenStore abstraction
- Actionable configuration error messages when environment variables are absent.
- Dynamic canonical redirect URI alignment with active server port.
"""

import os
import urllib.parse
import json
import secrets
from typing import Dict, Any, Optional, Tuple
import requests

from .token_store import TokenStore, LocalSecureFileTokenStore
from career_os.config import load_dotenv, get_canonical_redirect_uri


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
        port: Optional[int] = None,
        token_store: Optional[TokenStore] = None,
    ):
        load_dotenv()
        self.client_id = client_id.strip() if client_id is not None else os.getenv("GMAIL_CLIENT_ID", "").strip()
        self.client_secret = client_secret.strip() if client_secret is not None else os.getenv("GMAIL_CLIENT_SECRET", "").strip()
        self.port = port
        self.redirect_uri = redirect_uri or get_canonical_redirect_uri(port=port)
        self.token_store = token_store or LocalSecureFileTokenStore()

    def get_redirect_uri(self, port: Optional[int] = None) -> str:
        """Returns the active redirect URI, respecting custom port overrides if provided."""
        if port is not None:
            return get_canonical_redirect_uri(port=port)
        return self.redirect_uri

    def validate_configuration(self, port: Optional[int] = None) -> None:
        """Validates that necessary OAuth environment variables or arguments are present."""
        missing = []
        if not self.client_id:
            missing.append("GMAIL_CLIENT_ID")
        if not self.client_secret:
            missing.append("GMAIL_CLIENT_SECRET")
        if missing:
            active_uri = self.get_redirect_uri(port=port)
            raise OAuthConfigurationError(
                f"Missing Google OAuth configuration: {', '.join(missing)}.\n"
                f"Please add them to your .env file or configure GoogleOAuthClient directly.\n"
                f"Redirect URI configured: {active_uri}"
            )

    def get_authorization_url(self, state: Optional[str] = None, port: Optional[int] = None) -> Tuple[str, str]:
        """
        Generates Google OAuth2 authorization URL strictly requesting read-only Gmail access.
        Returns: (authorization_url, state_nonce)
        """
        self.validate_configuration(port=port)
        state_nonce = state or secrets.token_urlsafe(16)
        active_redirect_uri = self.get_redirect_uri(port=port)

        params = {
            "client_id": self.client_id,
            "redirect_uri": active_redirect_uri,
            "response_type": "code",
            "scope": " ".join(ALL_REQUIRED_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state_nonce,
            "include_granted_scopes": "true",
        }
        url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
        return url, state_nonce

    def exchange_code_for_tokens(self, code: str, port: Optional[int] = None) -> Dict[str, Any]:
        """
        Exchanges authorization code for access and refresh tokens.
        """
        self.validate_configuration()
        active_redirect_uri = self.get_redirect_uri(port=port)

        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": active_redirect_uri,
            "grant_type": "authorization_code",
        }

        response = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=10)
        if response.status_code != 200:
            error_details = response.text
            try:
                err_json = response.json()
                error_details = err_json.get("error_description", err_json.get("error", error_details))
            except Exception:
                pass
            raise ValueError(f"Failed to exchange OAuth code: {error_details}")

        token_data = response.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)

        if not access_token:
            raise ValueError("Token response did not contain access_token.")

        # Identify account email via Google userinfo endpoint
        userinfo_resp = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if userinfo_resp.status_code != 200:
            raise ValueError("Failed to retrieve user profile email from Google userinfo endpoint.")

        user_info = userinfo_resp.json()
        account_email = user_info.get("email")
        if not account_email:
            raise ValueError("User profile did not return an email address.")

        # Persist securely in TokenStore
        save_payload = {
            "access_token": access_token,
            "expires_in": expires_in,
        }
        if refresh_token:
            save_payload["refresh_token"] = refresh_token

        self.token_store.save_token("gmail", account_email, save_payload)

        return {
            "account_email": account_email,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
        }

    def refresh_token(self, account_email: str) -> Optional[Dict[str, Any]]:
        """
        Refreshes an expired access token using the stored refresh token.
        """
        token_info = self.token_store.get_token("gmail", account_email)
        if not token_info or not token_info.get("refresh_token"):
            return None

        refresh_token_val = token_info["refresh_token"]
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token_val,
            "grant_type": "refresh_token",
        }

        response = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=10)
        if response.status_code != 200:
            return None

        token_data = response.json()
        new_access_token = token_data.get("access_token")
        if not new_access_token:
            return None

        token_info["access_token"] = new_access_token
        if "expires_in" in token_data:
            token_info["expires_in"] = token_data["expires_in"]

        self.token_store.save_token("gmail", account_email, token_info)
        return token_info
