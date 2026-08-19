"""
career_os.discovery — Core discovery engine for Career OS.
"""

from .geography import normalize_location, is_india_location
from .router import route_intent, load_source_registry
from .adapters import execute_source_plan
from .normalizer import normalize_job, dedupe_jobs
from .candidate_model import extract_candidate_capabilities, validate_capability_model
from .hypotheses import generate_opportunity_hypotheses, validate_hypotheses
from .intents import generate_search_intents, validate_and_filter_intents, dedupe_intents

__all__ = [
    "normalize_location",
    "is_india_location",
    "route_intent",
    "load_source_registry",
    "execute_source_plan",
    "normalize_job",
    "dedupe_jobs",
    "extract_candidate_capabilities",
    "validate_capability_model",
    "generate_opportunity_hypotheses",
    "validate_hypotheses",
    "generate_search_intents",
    "validate_and_filter_intents",
    "dedupe_intents",
]
