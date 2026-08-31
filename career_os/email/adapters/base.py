"""
career_os.email.adapters.base — Abstract Base Class for Email Adapters.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..models import RawEmailMessage


class BaseEmailAdapter(ABC):
    """Abstract interface for email ingestion providers."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Returns True if adapter is authenticated and ready to fetch emails."""
        pass

    @abstractmethod
    def get_account_email(self) -> Optional[str]:
        """Returns active user account email address."""
        pass

    @abstractmethod
    def fetch_messages(
        self,
        query: Optional[str] = None,
        max_results: int = 50,
        after_date: Optional[str] = None,
    ) -> List[RawEmailMessage]:
        """
        Fetches email messages matching query/window.
        Returns normalized list of RawEmailMessage instances.
        """
        pass
