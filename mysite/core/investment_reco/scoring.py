from core.investment_reco.constants import (
    CATEGORY_MIN_HORIZON,
    SHORT_GOAL_MAX_MONTHS,
    MEDIUM_GOAL_MAX_MONTHS,
    SHORT_HORIZON_CATEGORIES,
    MEDIUM_HORIZON_CATEGORIES,
    LONG_HORIZON_CATEGORIES,
    DEBT_CATEGORY_KEYS,
    PROGRESS_STABLE_BIAS_THRESHOLD,
)


def get_allowed_categories_for_horizon(horizon_months):
    if horizon_months is None:
        return LONG_HORIZON_CATEGORIES

    if horizon_months <= SHORT_GOAL_MAX_MONTHS:
        return SHORT_HORIZON_CATEGORIES

    if horizon_months <= MEDIUM_GOAL_MAX_MONTHS:
        return MEDIUM_HORIZON_CATEGORIES

    return LONG_HORIZON_CATEGORIES


def _safe_float(value, default=0.0):
    try:
        if value in (None, "", "-", "null", "None"):
            return default
        return float(value)
    except Exception:
        return default


def advanced_fund_scoring(fund, horizon):
    """
    Extra intelligence layer:
    CAGR + consistency + cost + risk

    Important:
    - Purana logic replace nahi hota
    - Ye sirf additive bonus/penalty layer hai
    """
    total_score = 0.0
    reasons = {}

    category = (getattr(fund, "category_key", "") or "").lower()

    cagr_5y = _safe_float(getattr(fund, "return_5y", None), 0.0)
    cagr_3y = _safe_float(getattr(fund, "return_3y", None), 0.0)
    cagr_1y = _safe_float(getattr(fund, "return_1y", None), 0.0)

    expense = _safe_float(getattr(fund, "expense_ratio", None), 0.0)
    volatility = _safe_float(getattr(fund, "volatility_1y", None), 0.0)
    drawdown = abs(_safe_float(getattr(fund, "max_drawdown_1y", None), 0.0))
    consistency_score = _safe_float(getattr(fund, "consistency_score", None), 0.0)
    stability_score = _safe_float(getattr(fund, "stability_score", None), 0.0)

    cagr_score = 0.0
    consistency_bonus = 0.0
    cost_score = 0.0
    risk_score = 0.0
    core_bonus_score = 0.0

    # 1. CAGR / RETURN SCORE
    if cagr_5y > 0:
        cagr_score += min(cagr_5y / 20.0, 1.0) * 24
        reasons["cagr_5y"] = f"5Y CAGR/return {cagr_5y:.1f}% supports long-term quality."

    if cagr_3y > 0:
        cagr_score += min(cagr_3y / 18.0, 1.0) * 12
        reasons["cagr_3y"] = f"3Y CAGR/return {cagr_3y:.1f}% is supportive."

    if cagr_1y > 0:
        cagr_score += min(cagr_1y / 15.0, 1.0) * 4
        reasons["return_1y"] = f"1Y return {cagr_1y:.1f}% is positive."

    total_score += cagr_score

    # 2. CONSISTENCY SCORE
    consistency_bonus += min(consistency_score, 1.0) * 10
    consistency_bonus += min(stability_score, 1.0) * 10

    if cagr_3y > 0 and cagr_5y > 0:
        diff = abs(cagr_5y - cagr_3y)
        if diff <= 3:
            consistency_bonus += 6
            reasons["consistency"] = "Stable returns across 3Y–5Y."
        elif diff >= 10:
            consistency_bonus -= 4
            reasons["consistency"] = "Return pattern is less stable across periods."

    if consistency_score >= 0.7:
        reasons["consistency_score"] = "Fund has good return consistency."

    if stability_score >= 0.7:
        reasons["stability"] = "Fund has comparatively stable behaviour."

    total_score += consistency_bonus

    # 3. COST SCORE
    if expense > 0:
        if expense < 0.30:
            cost_score += 10
            reasons["cost"] = f"Very low expense ratio ({expense:.2f}%) is a strong positive."
        elif expense < 0.75:
            cost_score += 7
            reasons["cost"] = f"Low expense ratio ({expense:.2f}%) is favorable."
        elif expense < 1.25:
            cost_score += 4
            reasons["cost"] = f"Reasonable expense ratio ({expense:.2f}%)."
        elif expense < 2.0:
            cost_score -= 2
            reasons["cost"] = f"Expense ratio ({expense:.2f}%) is somewhat high."
        else:
            cost_score -= 6
            reasons["cost"] = f"Expense ratio ({expense:.2f}%) is high."

    total_score += cost_score

    # 4. RISK SCORE
    risk_score -= volatility * 12
    risk_score -= drawdown * 10

    if volatility > 0.20:
        reasons["volatility"] = "Higher volatility makes this fund more aggressive."

    if drawdown > 0.15:
        reasons["drawdown"] = "Recent drawdown risk is on the higher side."

    if horizon is not None and horizon <= 24:
        if category in {"midcap", "midcap150", "smallcap", "smallcap250"}:
            risk_score -= 10
            reasons["risk"] = "This category can be too volatile for a short-term goal."
        else:
            risk_score += 4
            reasons["risk"] = "Risk profile is better aligned to a shorter horizon."

    elif horizon is not None and horizon <= 36:
        if category in {"smallcap", "smallcap250"}:
            risk_score -= 8
            reasons["risk"] = "Small-cap exposure can be volatile for a medium horizon."
        elif category in {"largecap", "nifty50", "bse", "balanced_advantage", "multi_asset"}:
            risk_score += 4
            reasons["risk"] = "Risk profile is reasonably aligned to the goal horizon."

    elif horizon is not None and horizon >= 60:
        if category in {"flexicap", "multicap", "midcap", "midcap150", "smallcap", "smallcap250"}:
            risk_score += 4
            reasons["risk"] = "Growth-oriented category fits a long-term goal horizon."
        else:
            risk_score += 2
            reasons["risk"] = "Risk profile remains acceptable for a long-term goal."

    total_score += risk_score

    # 5. SMALL BONUS
    if category in {"nifty50", "bse", "largecap"}:
        core_bonus_score += 3
        reasons["core_category_bonus"] = "Core market category adds portfolio stability."

    total_score += core_bonus_score

    return {
        "total_score": round(total_score, 2),
        "cagr_score": round(cagr_score, 2),
        "consistency_score_component": round(consistency_bonus, 2),
        "cost_score": round(cost_score, 2),
        "risk_score": round(risk_score, 2),
        "core_bonus_score": round(core_bonus_score, 2),
        "reasons": reasons,
    }


def score_fund_for_goal(fund, horizon_months, goal_progress_pct=0.0):
    score = 0.0
    rationale = {}

    base_goal_fit_score = 0.0
    base_performance_score = 0.0

    required_horizon = CATEGORY_MIN_HORIZON.get(
        getattr(fund, "category_key", ""), 36
    )
    allowed_categories = get_allowed_categories_for_horizon(horizon_months)

    # =====================================================
    # 1. EXISTING LOGIC (UNCHANGED)
    # =====================================================

    # Category fit
    if getattr(fund, "category_key", "") in allowed_categories:
        score += 20
        base_goal_fit_score += 20
        rationale["category_fit"] = "Fund category matches the goal horizon."
    else:
        score -= 40
        base_goal_fit_score -= 40
        rationale["category_fit"] = "Fund category is not ideal for this goal horizon."

    # Minimum holding period fit
    if horizon_months is not None and horizon_months >= required_horizon:
        score += 20
        base_goal_fit_score += 20
        rationale["horizon_fit"] = "Holding period is suitable for this fund."
    else:
        score -= 35
        base_goal_fit_score -= 35
        rationale["horizon_fit"] = "This fund generally needs a longer holding period."

    # Progress-based stability preference
    if (
        goal_progress_pct >= PROGRESS_STABLE_BIAS_THRESHOLD
        and horizon_months is not None
        and horizon_months <= 24
    ):
        if getattr(fund, "category_key", "") in DEBT_CATEGORY_KEYS or getattr(
            fund, "category_key", ""
        ) in {
            "hybrid_conservative",
            "balanced_advantage",
        }:
            score += 15
            base_goal_fit_score += 15
            rationale["progress_fit"] = (
                "Goal is already well progressed, so stable categories are preferred."
            )
        else:
            score -= 15
            base_goal_fit_score -= 15
            rationale["progress_fit"] = (
                "Goal is already well progressed, so aggressive categories are less suitable."
            )

    # Debt fund scoring
    if getattr(fund, "fund_type", "") == "debt":
        v1 = _safe_float(getattr(fund, "return_1y", 0)) * 100
        v2 = _safe_float(getattr(fund, "return_3y", 0)) * 60
        v3 = _safe_float(getattr(fund, "stability_score", 0)) * 20
        v4 = _safe_float(getattr(fund, "consistency_score", 0)) * 10
        p1 = max(0, _safe_float(getattr(fund, "volatility_1y", 0))) * 20
        p2 = max(0, abs(_safe_float(getattr(fund, "max_drawdown_1y", 0)))) * 15

        subtotal = v1 + v2 + v3 + v4 - p1 - p2

        score += subtotal
        base_performance_score += subtotal

        rationale["risk_style"] = "Debt funds are being favored for stability-sensitive goals."

    else:
        # Equity / passive / hybrid scoring
        v1 = _safe_float(getattr(fund, "return_3y", 0)) * 100
        v2 = _safe_float(getattr(fund, "return_1y", 0)) * 40
        v3 = _safe_float(getattr(fund, "consistency_score", 0)) * 10
        v4 = _safe_float(getattr(fund, "stability_score", 0)) * 10
        v5 = _safe_float(getattr(fund, "alpha_1y", 0)) * 10
        p1 = max(0, _safe_float(getattr(fund, "volatility_1y", 0))) * 15
        p2 = max(0, abs(_safe_float(getattr(fund, "max_drawdown_1y", 0)))) * 10

        subtotal = v1 + v2 + v3 + v4 + v5 - p1 - p2

        expense_ratio = _safe_float(getattr(fund, "expense_ratio", 0))
        if 0 < expense_ratio < 1.0:
            subtotal += 5
            rationale["base_cost_fit"] = "Reasonable expense ratio."

        score += subtotal
        base_performance_score += subtotal

    base_score = round(score, 2)

    # =====================================================
    # 2. NEW EXTRA LOGIC (ADDITIVE ONLY)
    # =====================================================

    advanced_parts = advanced_fund_scoring(fund, horizon_months)
    advanced_score = advanced_parts["total_score"]

    score += advanced_score
    rationale.update(advanced_parts["reasons"])

    final_score = round(score, 2)

    # =====================================================
    # 3. NEW EXPLANATION LAYER (NON-BREAKING)
    # =====================================================

    rationale["score_breakdown"] = {
        "base_goal_fit_score": round(base_goal_fit_score, 2),
        "base_performance_score": round(base_performance_score, 2),
        "base_score": round(base_score, 2),
        "advanced_cagr_score": round(advanced_parts["cagr_score"], 2),
        "advanced_consistency_score": round(
            advanced_parts["consistency_score_component"], 2
        ),
        "advanced_cost_score": round(advanced_parts["cost_score"], 2),
        "advanced_risk_score": round(advanced_parts["risk_score"], 2),
        "advanced_core_bonus_score": round(
            advanced_parts["core_bonus_score"], 2
        ),
        "advanced_score": round(advanced_score, 2),
        "final_score": round(final_score, 2),
    }

    rationale["calculation_overview"] = (
        "This score combines goal fit, time horizon, historical returns, "
        "consistency, cost, and risk. Higher score means the fund is a better "
        "overall fit for this goal."
    )

    rationale["user_friendly_factors"] = [
        "Goal fit",
        "Time horizon suitability",
        "Historical return / CAGR strength",
        "Consistency of returns",
        "Expense ratio effect",
        "Risk alignment",
    ]

    # =====================================================
    # 4. Suitability Bucket
    # =====================================================

    suitability = "avoid"
    if final_score >= 60:
        suitability = "excellent"
    elif final_score >= 35:
        suitability = "good"
    elif final_score >= 15:
        suitability = "watch"

    return final_score, suitability, rationale