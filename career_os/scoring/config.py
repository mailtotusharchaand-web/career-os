"""
Career OS — Candidate Policy Configuration
User-specific constraints that gate job eligibility.
"""

from dataclasses import dataclass, field
from typing import Optional
import json


# Domain inference (shared utility to avoid circular imports)
PRIMARY_DOMAINS = [
    "payments", "kyc/aml/compliance/risk", "case management", "identity/access/verification",
    "data/analytics", "product"
]

SECONDARY_DOMAINS = [
    "platform/trust & safety", "banking/wealth/credit"
]

ADJACENT_DOMAINS = [
    "platform/trust & safety", "banking/wealth/credit",
    "technical/engineering", "program/project management"
]

PRODUCT_EXCLUDE_KEYWORDS = [
    "project manager", "program manager", "project lead", "delivery manager",
    "scrum master", "agile coach", "product marketing", "product designer",
    "product operations", "product support", "product marketing manager",
    "technical program manager", "tpm", "project coordinator",
    "delivery lead", "release manager", "project lead"
]

EMPLOYMENT_EXCLUDE_KEYWORDS = [
    "intern", "trainee", "co-op", "coop", "apprentice", "part-time", "part time",
    "temporary", "temp ", "contract-to-hire", "contract to hire", "fellowship",
    "apprenticeship", "summer intern", "winter intern"
]

SENIORITY_VP_KEYWORDS = ["vp", "vice president", "director", "principal", "staff", "head of", "dvp", "avp", "srvp", "evp", "svp"]
SENIORITY_SENIOR_KEYWORDS = ["senior", "sr.", "sr ", "lead", "manager"]
SENIORITY_ASSOCIATE_KEYWORDS = ["associate", "assoc", "junior", "jr.", "jr "]


def infer_domain(title: str, description: str = "") -> str:
    """Infer domain from title and description."""
    title_lower = title.lower()
    desc_lower = (description or "").lower()
    
    # Primary domains
    if any(kw in title_lower for kw in ["payments", "payment", "card", "billing", "transaction", "wallet", "tokenization", "rails"]):
        return "payments"
    if any(kw in title_lower for kw in ["kyc", "aml", "compliance", "risk", "fraud", "sanctions", "financial crime", "anti money laundering"]):
        return "kyc/aml/compliance/risk"
    if any(kw in title_lower for kw in ["case management", "client implementation", "onboarding", "case", "dispute", "chargeback"]):
        return "case management"
    if any(kw in title_lower for kw in ["identity", "auth", "authentication", "verification", "access", "tokenization", "profile"]):
        return "identity/access/verification"
    
    # Secondary domains
    if any(kw in title_lower for kw in ["platform", "ecosystem", "risk platform", "trust and safety", "trust & safety"]):
        return "platform/trust & safety"
    if any(kw in title_lower for kw in ["deposit", "treasury", "wealth", "banking", "loan", "mortgage", "credit", "underwriting"]):
        return "banking/wealth/credit"
    
    # Other domains
    if any(kw in title_lower for kw in ["marketing", "growth", "acquisition", "pricing", "strategy"]):
        return "marketing/growth"
    if any(kw in title_lower for kw in ["data", "analytics", "analyst", "data scientist", "insights", "data engineer"]):
        return "data/analytics"
    if any(kw in title_lower for kw in ["engineering", "technical", "technical product", "technical pm", "technical product manager", "software engineer", "devops", "sre"]):
        return "technical/engineering"
    if any(kw in title_lower for kw in ["operations", "ops", "support lead", "support", "customer success", "client success"]):
        return "operations/support"
    if any(kw in title_lower for kw in ["sales", "business development", "relationship manager", "account manager"]):
        return "sales/relationship"
    if any(kw in title_lower for kw in ["legal", "counsel", "compliance", "regulatory"]):
        return "legal/compliance"
    if any(kw in title_lower for kw in ["finance", "financial", "pricing", "pricing manager"]):
        return "finance"
    if any(kw in title_lower for kw in ["program manager", "project manager", "project"]):
        return "program/project management"
    if any(kw in title_lower for kw in ["retail", "merchandise", "stylist", "front desk", "cashier", "guest experience"]):
        return "retail/store operations"
    if any(kw in title_lower for kw in ["consultant", "consulting", "advisory"]):
        return "consulting"
    if any(kw in title_lower for kw in ["healthcare", "pharma", "clinical", "medical"]):
        return "healthcare/pharma"
    if any(kw in title_lower for kw in ["automotive", "auto", "vehicle"]):
        return "automotive"
    if any(kw in title_lower for kw in ["media", "entertainment", "content"]):
        return "media/entertainment"
    if any(kw in title_lower for kw in ["crypto", "blockchain", "web3", "okx"]):
        return "crypto/blockchain"
    if any(kw in title_lower for kw in ["security", "securitas", "identity", "id"]):
        return "security/identity"
    
    # Product domain (for Product Analyst, Product Manager, Product Owner roles)
    if any(kw in title_lower for kw in ["product analyst", "product manager", "product owner", "associate product", "senior product", "principal product", "staff product", "lead product", "group product", "digital product", "technical product manager", "product management", "product lead"]):
        return "product"
    
    return "unknown"


def classify_domain(domain: str, policy=None) -> str:
    """Classify domain into primary/secondary/adjacent/other/excluded."""
    d = domain.lower().strip()
    
    if any(d == x.lower() for x in PRIMARY_DOMAINS):
        return "primary"
    if any(d == x.lower() for x in SECONDARY_DOMAINS):
        return "secondary"
    if any(d == x.lower() for x in ADJACENT_DOMAINS):
        return "adjacent"
    if any(d == x.lower() for x in [
        "data/analytics", "platform/trust & safety", "banking/wealth/credit",
        "technical/engineering", "program/project management",
        "operations/support", "legal/compliance", "finance",
        "marketing/growth", "sales/relationship", "consulting"
    ]):
        return "other"
    return "excluded"


def normalize_domain(domain: str) -> str:
    """Normalize domain string for comparison."""
    return domain.lower().strip()


@dataclass
class CandidatePolicy:
    """User-defined constraints that override scoring defaults."""
    
    # Relocation
    willing_to_relocate_us: bool = False
    willing_to_relocate_other: bool = False
    preferred_india_cities: list = field(default_factory=lambda: ["gurugram", "bangalore", "hyderabad", "pune", "mumbai", "delhi", "noida"])
    
    # Work authorization
    us_citizen_or_green_card: bool = False
    us_work_authorization: bool = False  # H1B, OPT, etc.
    requires_sponsorship: bool = True    # If True, US roles requiring sponsorship are ineligible
    
    # Employment
    contract_acceptable: bool = True
    part_time_acceptable: bool = False
    internship_acceptable: bool = False
    temporary_acceptable: bool = False
    
    # Seniority
    seniority_stretch_acceptable: bool = False  # Allow VP/Director for primary domain
    min_seniority: str = "associate"  # associate, mid, senior
    max_seniority: str = "senior"     # associate, mid, senior, vp
    
    # Domain
    primary_domains: list = field(default_factory=lambda: [
        "payments", "kyc/aml/compliance/risk", "case management", "identity/access/verification"
    ])
    secondary_domains: list = field(default_factory=lambda: [
        "platform/trust & safety", "banking/wealth/credit"
    ])
    excluded_domains: list = field(default_factory=lambda: [
        "retail/store operations", "healthcare/pharma", "automotive", 
        "media/entertainment", "crypto/blockchain", "security/identity",
        "consulting", "sales/relationship", "marketing/growth", "legal/compliance",
        "finance", "operations/support", "technical/engineering", "data/analytics",
        "program/project management"
    ])
    
    # Location
    remote_only: bool = False
    max_commute_minutes: Optional[int] = None
    
    # Recency
    max_job_age_days: int = 30
    
    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "CandidatePolicy":
        return cls(**json.loads(json_str))
    
    @classmethod
    def load(cls, path: str) -> "CandidatePolicy":
        with open(path, "r") as f:
            return cls.from_json(f.read())
    
    def save(self, path: str) -> None:
        with open(path, "w") as f:
            f.write(self.to_json())


# Default policy for the current candidate
DEFAULT_POLICY = CandidatePolicy(
    willing_to_relocate_us=True,  # Willing for strong domain match
    willing_to_relocate_other=True,  # Willing for strong domain match
    us_citizen_or_green_card=False,
    us_work_authorization=False,
    requires_sponsorship=True,
    contract_acceptable=True,
    part_time_acceptable=False,
    internship_acceptable=False,
    temporary_acceptable=False,
    seniority_stretch_acceptable=True,  # Allow VP/Director for primary domain
    min_seniority="associate",
    max_seniority="vp",
    primary_domains=[
        "payments", "kyc/aml/compliance/risk", "case management", "identity/access/verification",
        "data/analytics", "product"  # Added data/analytics and product for Product Analyst roles
    ],
    secondary_domains=[
        "platform/trust & safety", "banking/wealth/credit",
        "data/analytics", "product"
    ],
    excluded_domains=[
        "retail/store operations", "healthcare/pharma", "automotive",
        "media/entertainment", "crypto/blockchain", "security/identity",
        "consulting", "sales/relationship", "marketing/growth", "legal/compliance",
        "finance", "operations/support", "technical/engineering",
        "program/project management"
    ],
    remote_only=False,
    max_job_age_days=30
)