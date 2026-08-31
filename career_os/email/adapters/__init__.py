"""
career_os.email.adapters — Email Provider Adapters (Mock and Live Gmail).
"""

from .base import BaseEmailAdapter
from .mock_adapter import MockEmailAdapter
from .gmail_adapter import GmailEmailAdapter

__all__ = ["BaseEmailAdapter", "MockEmailAdapter", "GmailEmailAdapter"]
