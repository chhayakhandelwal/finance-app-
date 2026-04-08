CATEGORY_MIN_HORIZON = {
    "debt_govt": 6,
    "debt_corp": 6,
    "hybrid_conservative": 12,
    "balanced_advantage": 24,
    "nifty50": 36,
    "bse": 36,
    "largecap": 36,
    "multi_asset": 36,
    "flexicap": 48,
    "multicap": 48,
    "midcap150": 60,
    "midcap": 60,
    "smallcap250": 84,
    "smallcap": 84,
}

SHORT_GOAL_MAX_MONTHS = 24
MEDIUM_GOAL_MAX_MONTHS = 60

SHORT_HORIZON_CATEGORIES = {
    "debt_govt",
    "debt_corp",
    "hybrid_conservative",
}

MEDIUM_HORIZON_CATEGORIES = {
    "balanced_advantage",
    "multi_asset",
    "nifty50",
    "bse",
    "largecap",
    "flexicap",
}

LONG_HORIZON_CATEGORIES = {
    "nifty50",
    "bse",
    "largecap",
    "flexicap",
    "multicap",
    "midcap150",
    "midcap",
    "smallcap250",
    "smallcap",
}

ACTIVE_CATEGORY_KEYS = {
    "largecap",
    "midcap",
    "smallcap",
    "multicap",
    "flexicap",
    "balanced_advantage",
    "multi_asset",
    "hybrid_conservative",
    "hybrid_aggressive",
}

PASSIVE_CATEGORY_KEYS = {
    "nifty50",
    "bse",
    "midcap150",
    "smallcap250",
}

DEBT_CATEGORY_KEYS = {
    "debt_govt",
    "debt_corp",
}

PROGRESS_STABLE_BIAS_THRESHOLD = 70.0