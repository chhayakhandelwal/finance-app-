from datetime import date

# =====================================================
# BASIC GOAL METRICS (UNCHANGED)
# =====================================================

def get_goal_remaining_amount(goal):
    target_amount = float(getattr(goal, "target_amount", 0) or 0)
    saved_amount = float(getattr(goal, "saved_amount", 0) or 0)
    return max(target_amount - saved_amount, 0.0)

def get_goal_progress_pct(goal):
    target_amount = float(getattr(goal, "target_amount", 0) or 0)
    saved_amount = float(getattr(goal, "saved_amount", 0) or 0)

    if target_amount <= 0:
        return 0.0

    return round((saved_amount / target_amount) * 100.0, 2)

def get_goal_horizon_months(goal, today=None):
    today = today or date.today()
    target_date = getattr(goal, "target_date", None)

    if not target_date:
        return None

    delta_days = (target_date - today).days
    if delta_days <= 0:
        return 0

    return max(delta_days // 30, 1)

def get_goal_required_monthly_investment(goal, today=None):
    months_left = get_goal_horizon_months(goal, today=today)
    remaining_amount = get_goal_remaining_amount(goal)

    if months_left is None or months_left <= 0:
        return 0.0

    if remaining_amount <= 0:
        return 0.0

    return round(remaining_amount / months_left, 2)

# =====================================================
# ✅ NEW: EXPENSE-AWARE INVESTMENT LOGIC
# =====================================================

def get_safety_reserve(monthly_income):
    """
    Minimum buffer user ke paas rehna chahiye
    """
    monthly_income = float(monthly_income or 0)

    if monthly_income <= 0:
        return 0.0

    return round(max(monthly_income * 0.10, 3000.0), 2)

def get_recommendation_pool(monthly_income, last_month_expenses):
    """
    Real investable monthly amount
    """
    monthly_income = float(monthly_income or 0)
    last_month_expenses = float(last_month_expenses or 0)

    free_cashflow = max(monthly_income - last_month_expenses, 0.0)
    reserve = get_safety_reserve(monthly_income)

    pool = max(free_cashflow - reserve, 0.0)

    return {
        "monthly_income": round(monthly_income, 2),
        "last_month_expenses": round(last_month_expenses, 2),
        "free_cashflow": round(free_cashflow, 2),
        "reserve": round(reserve, 2),
        "recommendation_pool": round(pool, 2),
    }

# =====================================================
# ✅ NEW: GOAL PRIORITY SCORING
# =====================================================

def get_goal_priority_score(goal, today=None):
    """
    Priority decide karta hai:
    - urgency (time left)
    - progress gap
    - remaining pressure
    """
    months_left = get_goal_horizon_months(goal, today=today)
    progress_pct = get_goal_progress_pct(goal)
    remaining_amount = get_goal_remaining_amount(goal)
    target_amount = float(getattr(goal, "target_amount", 0) or 0)

    if months_left is None or months_left <= 0 or remaining_amount <= 0:
        return 0.0

    urgency = 1 / max(months_left, 1)
    progress_gap = max(0.0, 100.0 - progress_pct) / 100.0
    remaining_ratio = (remaining_amount / target_amount) if target_amount > 0 else 0.0

    score = (urgency * 0.50) + (progress_gap * 0.30) + (remaining_ratio * 0.20)

    return round(max(score, 0.0001), 6)

# =====================================================
# ✅ NEW: POOL → GOAL ALLOCATION
# =====================================================
def allocate_pool_across_goals(goals, recommendation_pool, today=None):
    valid_goals = []
    total_priority = 0.0

    for goal in goals:
        remaining = get_goal_remaining_amount(goal)
        months_left = get_goal_horizon_months(goal, today=today)

        if remaining <= 0:
            continue

        if months_left is None or months_left <= 0:
            continue

        priority = get_goal_priority_score(goal, today=today)
        required = get_goal_required_monthly_investment(goal, today=today)

        valid_goals.append({
            "goal": goal,
            "priority": priority,
            "required": required,
        })

        total_priority += priority

    if not valid_goals or recommendation_pool <= 0:
        return {}

    allocations = {}

    for item in valid_goals:
        goal = item["goal"]
        priority = item["priority"]
        required = item["required"]

        share = recommendation_pool * (priority / total_priority)

        if share >= required:
            suggested = required
        else:
            suggested = round(share, 2)

        allocations[goal.id] = {
            "required_monthly_amount": round(required, 2),
            "suggested_monthly_amount": round(suggested, 2),
            "priority_score": round(priority, 6),
        }

    return allocations

# =====================================================
# ❌ OLD LOGIC (KEEP FOR BACKWARD COMPATIBILITY)
# =====================================================

def get_goal_income_cap(monthly_income, horizon_months):
    monthly_income = float(monthly_income or 0)

    if monthly_income <= 0:
        return 0.0

    if horizon_months is not None and horizon_months <= 24:
        return round(monthly_income * 0.20, 2)

    if horizon_months is not None and horizon_months <= 60:
        return round(monthly_income * 0.30, 2)

    return round(monthly_income * 0.40, 2)

def get_affordable_monthly_investment(goal, monthly_income, today=None):
    """
    OLD FLOW (still usable if needed)
    """
    required_amount = get_goal_required_monthly_investment(goal, today=today)
    horizon_months = get_goal_horizon_months(goal, today=today)
    income_cap = get_goal_income_cap(monthly_income, horizon_months)

    suggested_amount = min(required_amount, income_cap)

    return {
        "required_monthly_amount": round(required_amount, 2),
        "income_based_cap": round(income_cap, 2),
        "suggested_monthly_amount": round(suggested_amount, 2),
        "is_fully_affordable": suggested_amount >= required_amount if required_amount > 0 else True,
    }

# =====================================================
# EXISTING FUND SPLIT (UNCHANGED)
# =====================================================

def split_goal_amount(total_amount, selected_funds, horizon_months):
    total_amount = float(total_amount or 0)

    if total_amount <= 0 or not selected_funds:
        return {}

    if horizon_months is not None and horizon_months <= 24:
        weights = [1.0]
    elif horizon_months is not None and horizon_months <= 60:
        weights = [0.70, 0.30]
    else:
        weights = [0.60, 0.25, 0.15]

    selected = selected_funds[: len(weights)]
    weights = weights[: len(selected)]

    total_weight = sum(weights) or 1.0
    normalized = [w / total_weight for w in weights]

    result = {}
    used = 0.0

    for i, item in enumerate(selected):
        fund = item["fund"]
        scheme_code = fund.scheme_code

        if i == len(selected) - 1:
            amount = round(total_amount - used, 2)
        else:
            amount = round(total_amount * normalized[i], 2)
            used += amount

        result[scheme_code] = max(amount, 0.0)

    return result