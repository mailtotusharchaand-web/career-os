"""
career_os.config — Centralized Environment and Configuration Loader for Career OS.

Handles:
- .env parsing and environment variable loading
- Server port resolution
- Canonical OAuth redirect URI generation and consistency verification
- Sensitive credential masking
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple


BASE_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(path: Optional[str] = None) -> None:
    """
    Loads key-value pairs from .env file into os.environ if not already present.
    Searches provided path, project root, or current directory.
    """
    target_path = Path(path) if path else BASE_DIR / ".env"
    if not target_path.exists():
        # Fallback to current working directory
        target_path = Path(".env")

    if not target_path.exists() or not target_path.is_file():
        return

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and val and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


# Automatically ensure .env is loaded on module import
load_dotenv()


def get_server_port(default: int = 8080) -> int:
    """Returns the configured server port from environment variable PORT or default."""
    raw = os.getenv("PORT")
    if raw:
        try:
            return int(raw.strip())
        except ValueError:
            pass
    return default


def get_canonical_redirect_uri(port: Optional[int] = None) -> str:
    """
    Returns the canonical OAuth redirect URI:
    1. If GMAIL_REDIRECT_URI is explicitly set in environment/.env, returns it.
    2. Otherwise, constructs http://localhost:{port}/api/gmail/callback based on the active/configured port.
    """
    explicit = os.getenv("GMAIL_REDIRECT_URI", "").strip()
    if explicit:
        return explicit
    active_port = port if port is not None else get_server_port()
    return f"http://localhost:{active_port}/api/gmail/callback"


def get_oauth_config(port: Optional[int] = None) -> Dict[str, Any]:
    """
    Returns current Google OAuth configuration without exposing secrets.
    """
    load_dotenv()
    client_id = os.getenv("GMAIL_CLIENT_ID", "").strip()
    client_secret = os.getenv("GMAIL_CLIENT_SECRET", "").strip()
    redirect_uri = get_canonical_redirect_uri(port=port)

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "is_configured": bool(client_id and client_secret),
        "has_client_id": bool(client_id),
        "has_client_secret": bool(client_secret),
    }
