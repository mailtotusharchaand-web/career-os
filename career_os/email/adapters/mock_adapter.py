"""
career_os.email.adapters.mock_adapter — Deterministic Mock Email Provider Adapter.

Provides deterministic fixtures covering all career event scenarios, edge cases,
multi-turn threads, ambiguous matches, and irrelevant emails.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from .base import BaseEmailAdapter
from ..models import RawEmailMessage


class MockEmailAdapter(BaseEmailAdapter):
    """Deterministic mock email adapter for testing, development, and dry-run validation."""

    def __init__(self, account_email: str = "candidate.tushar@example.com", custom_messages: Optional[List[RawEmailMessage]] = None):
        self._account_email = account_email
        self._custom_messages = custom_messages
        self._connected = True

    def is_connected(self) -> bool:
        return self._connected

    def set_connected(self, connected: bool) -> None:
        self._connected = connected

    def get_account_email(self) -> Optional[str]:
        return self._account_email if self._connected else None

    def fetch_messages(
        self,
        query: Optional[str] = None,
        max_results: int = 50,
        after_date: Optional[str] = None,
    ) -> List[RawEmailMessage]:
        if not self._connected:
            raise ConnectionError("MockEmailAdapter is not connected.")

        if self._custom_messages is not None:
            return self._custom_messages[:max_results]

        return self.get_standard_mock_fixtures()[:max_results]

    def get_standard_mock_fixtures(self) -> List[RawEmailMessage]:
        """Returns standard library of deterministic mock emails."""
        now = datetime.now(timezone.utc)
        t0 = (now - timedelta(days=20)).isoformat()
        t1 = (now - timedelta(days=15)).isoformat()
        t2 = (now - timedelta(days=10)).isoformat()
        t3 = (now - timedelta(days=5)).isoformat()
        t4 = (now - timedelta(days=2)).isoformat()
        t5 = (now - timedelta(days=1)).isoformat()

        return [
            # 1. Application Confirmation (Swiggy)
            RawEmailMessage(
                provider="mock",
                account_id=self._account_email,
                message_id="mock_msg_001",
                thread_id="mock_th_001",
                sender="Swiggy Careers <no-reply@swiggy.in>",
                recipients=[self._account_email],
                subject="Thank you for applying to Swiggy - Product Manager",
                body_text="Hi Tushar,\n\nThank you for applying to Swiggy for the Product Manager position (Req ID: SWG-9921). We have received your application and our team is currently reviewing your profile.\n\nBest,\nSwiggy Talent Acquisition",
                received_at=t0,
                snippet="Thank you for applying to Swiggy for the Product Manager position (Req ID: SWG-9921). We have received your application...",
                labels=["INBOX", "Careers"],
            ),

            # 2. Interview Invitation (Razorpay)
            RawEmailMessage(
                provider="mock",
                account_id=self._account_email,
                message_id="mock_msg_002",
                thread_id="mock_th_002",
                sender="Razorpay Recruiting <talent@razorpay.com>",
                recipients=[self._account_email],
                subject="Invitation to Interview: Principal PM Payments at Razorpay",
                body_text="Dear Tushar,\n\nWe were very impressed with your background and would like to invite you for a 45-minute technical interview for the Principal PM Payments role. Please click the link below to select a slot that works best for you.\n\nBest regards,\nRazorpay Recruiting Team",
                received_at=t1,
                snippet="We were very impressed with your background and would like to invite you for a 45-minute technical interview for the Principal PM Payments role...",
                labels=["INBOX", "Interviews"],
            ),

            # 3. Assessment Request (PhonePe - Amendment 2 Evidence Only)
            RawEmailMessage(
                provider="mock",
                account_id=self._account_email,
                message_id="mock_msg_003",
                thread_id="mock_th_003",
                sender="PhonePe Hiring via HackerRank <support@hackerrank.com>",
                recipients=[self._account_email],
                subject="PhonePe: Complete the Technical Assessment for Senior Product Manager",
                body_text="Hello Tushar,\n\nYou have been invited to complete an online assessment on HackerRank for the Senior Product Manager position at PhonePe. Please complete the test within 48 hours.\n\nGood luck,\nPhonePe Hiring Team",
                received_at=t2,
                snippet="You have been invited to complete an online assessment on HackerRank for the Senior Product Manager position at PhonePe...",
                labels=["INBOX"],
            ),

            # 4. Rejection Notice (CRED)
            RawEmailMessage(
                provider="mock",
                account_id=self._account_email,
                message_id="mock_msg_004",
                thread_id="mock_th_004",
                sender="CRED Talent <careers@cred.club>",
                recipients=[self._account_email],
                subject="Update on your application at CRED",
                body_text="Hi Tushar,\n\nThank you for your interest in CRED and taking the time to apply. After careful consideration, unfortunately we will not be moving forward with your application for this position at this time. We will keep your profile in mind for future opportunities.\n\nBest,\nCRED Team",
                received_at=t3,
                snippet="Thank you for your interest in CRED. After careful consideration, unfortunately we will not be moving forward with your application...",
                labels=["INBOX"],
            ),

            # 5. Offer Letter (Flipkart)
            RawEmailMessage(
                provider="mock",
                account_id=self._account_email,
                message_id="mock_msg_005",
                thread_id="mock_th_005",
                sender="Flipkart Talent Management <offers@flipkart.com>",
                recipients=[self._account_email],
                subject="Offer of Employment - Flipkart - Staff Product Manager",
                body_text="Dear Tushar,\n\nWe are delighted to offer you the position of Staff Product Manager at Flipkart! Attached is your official offer letter and benefits summary. Please review and sign at your earliest convenience.\n\nWelcome to Flipkart!\nFlipkart HR",
                received_at=t4,
                snippet="We are delighted to offer you the position of Staff Product Manager at Flipkart! Attached is your official offer letter...",
                labels=["INBOX", "Important"],
            ),

            # 6. Recruiter Inbound Outreach (Cold outreach - Amendment 3 Evidence Only)
            RawEmailMessage(
                provider="mock",
                account_id=self._account_email,
                message_id="mock_msg_006",
                thread_id="mock_th_006",
                sender="Pooja Sharma <pooja.sharma@zomato.com>",
                recipients=[self._account_email],
                subject="Exploring Opportunities at Zomato",
                body_text="Hi Tushar,\n\nI came across your profile and was really impressed by your product leadership work. We are looking for a Director of Product to lead our core growth initiatives at Zomato and thought of you. Would you be open to a quick 15-minute chat this week?\n\nBest,\nPooja Sharma",
                received_at=t5,
                snippet="I came across your profile and was really impressed by your product leadership work. We are looking for a Director of Product at Zomato...",
                labels=["INBOX"],
            ),

            # 7. Irrelevant Newsletter / Job Alert
            RawEmailMessage(
                provider="mock",
                account_id=self._account_email,
                message_id="mock_msg_007",
                thread_id="mock_th_007",
                sender="Naukri Job Alerts <alerts@naukri.com>",
                recipients=[self._account_email],
                subject="15 New Product Manager Jobs in Bengaluru for you",
                body_text="Top job recommendations matching your profile:\n1. Lead PM at TechCorp\n2. Associate PM at Startup\n\nClick here to unsubscribe from daily job digest.",
                received_at=t5,
                snippet="Top job recommendations matching your profile. 15 new jobs in Bengaluru...",
                labels=["UPDATES"],
            ),

            # 8. Irrelevant Transactional OTP
            RawEmailMessage(
                provider="mock",
                account_id=self._account_email,
                message_id="mock_msg_008",
                thread_id="mock_th_008",
                sender="Google Security <no-reply@accounts.google.com>",
                recipients=[self._account_email],
                subject="Your Google verification code",
                body_text="Your one-time password (OTP) is 482910. Do not share this code with anyone.",
                received_at=t5,
                snippet="Your one-time password (OTP) is 482910...",
                labels=["UPDATES"],
            ),
        ]
