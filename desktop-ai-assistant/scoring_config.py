"""
scoring_config.py — Configurable weights for scoring_engine.py.

Adjust weights to change ranking behavior (must sum ~1.0 for core factors).
"""

WEIGHT_EXACT = 0.30
WEIGHT_FUZZY = 0.22
WEIGHT_KEYWORDS = 0.18
WEIGHT_TYPE = 0.20
WEIGHT_ALIAS = 0.05
WEIGHT_RECENCY = 0.03
WEIGHT_PATH = 0.02

# Confidence thresholds (high / medium / low tiers)
AUTO_OPEN_THRESHOLD = 0.75
MEDIUM_CONFIDENCE_THRESHOLD = 0.50
MIN_CANDIDATE_THRESHOLD = 0.45
CLARIFY_THRESHOLD = 0.38
AMBIGUITY_GAP = 0.08
STRONG_MATCH_THRESHOLD = 0.65
MAX_CHOICES_SHOWN = 5
