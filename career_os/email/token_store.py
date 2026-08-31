"""
career_os.email.token_store — TokenStore Abstraction for Secure Credential Isolation.

Enforces clean isolation of OAuth access and refresh tokens.
Keeps sensitive authentication material out of SQLite tables and domain entities.
"""

from abc import ABC, abstractmethod
import base64
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone


class TokenStore(ABC):
    """Abstract interface for managing OAuth credentials securely."""

    @abstractmethod
    def save_token(self, provider: str, account_id: str, token_data: Dict[str, Any]) -> None:
        """Stores token data for a provider and account."""
        pass

    @abstractmethod
    def get_token(self, provider: str, account_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves token data if available."""
        pass

    @abstractmethod
    def delete_token(self, provider: str, account_id: str) -> bool:
        """Deletes stored token for a provider and account."""
        pass

    @abstractmethod
    def has_token(self, provider: str, account_id: str) -> bool:
        """Checks if a valid token exists."""
        pass

    @abstractmethod
    def list_accounts(self, provider: str) -> List[str]:
        """Lists account IDs configured for a given provider."""
        pass


class LocalSecureFileTokenStore(TokenStore):
    """
    Secure file-based TokenStore storing credentials in an isolated local directory.
    Default directory: ~/.career_os/tokens/ (or custom base_dir).
    """

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self.base_dir = Path(base_dir).resolve()
        else:
            self.base_dir = Path.home() / ".career_os" / "tokens"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, provider: str, account_id: str) -> Path:
        safe_provider = "".join(c for c in provider.lower() if c.isalnum() or c in "_-")
        safe_account = base64.urlsafe_b64encode(account_id.lower().encode("utf-8")).decode("ascii")
        return self.base_dir / f"{safe_provider}_{safe_account}.json"

    def save_token(self, provider: str, account_id: str, token_data: Dict[str, Any]) -> None:
        path = self._get_path(provider, account_id)
        payload = {
            "provider": provider,
            "account_id": account_id,
            "token_data": token_data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        # Write atomically via temp file
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        temp_path.replace(path)

    def get_token(self, provider: str, account_id: str) -> Optional[Dict[str, Any]]:
        path = self._get_path(provider, account_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
                return payload.get("token_data")
        except Exception:
            return None

    def delete_token(self, provider: str, account_id: str) -> bool:
        path = self._get_path(provider, account_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def has_token(self, provider: str, account_id: str) -> bool:
        token = self.get_token(provider, account_id)
        return bool(token and (token.get("access_token") or token.get("refresh_token")))

    def list_accounts(self, provider: str) -> List[str]:
        prefix = f"{provider.lower()}_"
        accounts = []
        for file in self.base_dir.glob(f"{prefix}*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                    if payload.get("account_id"):
                        accounts.append(payload["account_id"])
            except Exception:
                continue
        return accounts
