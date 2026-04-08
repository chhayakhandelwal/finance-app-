from datetime import date
from calendar import monthrange

from django.db.models import Sum

from core.models import (
    Income,
    Expense,
    SavingsGoal,
    InvestmentRecommendation,
)

from core.investment_reco.selectors import (
    get_recommendation_candidates,
    get_recommendation_as_of,
)

from core.investment_reco.scoring import (
    score_fund_for_goal,
    get_allowed_categories_for_horizon,
)

from core.investment_reco.planner import (
    get_goal_remaining_amount,
    get_goal_progress_pct,
    get_goal_horizon_months,
    get_goal_required_monthly_investment,
    get_recommendation_pool,
    allocate_pool_across_goals,
    split_goal_amount,
)


# =========================================
# STEP 1: Latest Monthly Income
# =========================================
def get_latest_monthly_income(user):
    latest = (
        Income.objects
        .filter(user=user)
        .order_by("-income_date", "-id")
        .first()
    )
    if not latest:
        return 0.0
    return float(latest.amount or 0)


# =========================================
# STEP 2: Last Completed Month Range
# =========================================
def get_last_completed_month_range(today=None):
    today = today or date.today()

    year = today.year
    month = today.month - 1

    if month == 0:
        month = 12
        year -= 1

    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])
    return start_date, end_date


# =========================================
# STEP 3: Last Completed Month Expenses
# =========================================
def get_last_month_expenses(user, today=None):
    start_date, end_date = get_last_completed_month_range(today=today)

    total = (
        Expense.objects
        .filter(
            user=user,
            direction="DEBIT",
            expense_date__gte=start_date,
            expense_date__lte=end_date,
        )
        .aggregate(total=Sum("amount"))
        .get("total") or 0
    )

    return float(total or 0)


# =========================================
# STEP 4: Summary (Improved Explanation)
# =========================================
def build_goal_summary(
    goal,
    horizon,
    progress,
    required_monthly,
    suggested_goal_monthly,
    monthly_income,
    last_month_expenses,
    free_cashflow,
    recommendation_pool,
    fund,
):
    return (
        f"Goal: '{goal.name}' | Time left: {horizon} months | Progress: {progress:.2f}%.\n"
        f"Income ₹{monthly_income:,.0f} - Expenses ₹{last_month_expenses:,.0f} = Free ₹{free_cashflow:,.0f}.\n"
        f"Safe investable pool: ₹{recommendation_pool:,.0f}/month.\n"
        f"Required for goal: ₹{required_monthly:,.0f}/month.\n"
        f"Suggested (realistic): ₹{suggested_goal_monthly:,.0f}/month.\n"
        f"Fund '{fund.scheme_name}' selected based on horizon and suitability."
    )


# =========================================
# MAIN ENGINE
# =========================================
def build_user_investment_recommendations(user):

    latest_as_of = get_recommendation_as_of()
    if not latest_as_of:
        return []

    candidates = list(get_recommendation_candidates())
    if not candidates:
        return []

    monthly_income = get_latest_monthly_income(user)
    if monthly_income <= 0:
        InvestmentRecommendation.objects.filter(user=user, as_of=latest_as_of).delete()
        return []

    last_month_expenses = get_last_month_expenses(user)

    # 🔥 CORE LOGIC (INCOME - EXPENSE)
    pool_info = get_recommendation_pool(monthly_income, last_month_expenses)

    free_cashflow = float(pool_info.get("free_cashflow") or 0)
    recommendation_pool = float(pool_info.get("recommendation_pool") or 0)

    # ❌ If no money available → no recommendation
    if recommendation_pool <= 0:
        InvestmentRecommendation.objects.filter(user=user, as_of=latest_as_of).delete()
        return []

    goals = list(SavingsGoal.objects.filter(user=user))
    if not goals:
        InvestmentRecommendation.objects.filter(user=user, as_of=latest_as_of).delete()
        return []

    # 🔥 Split total pool across goals
    goal_allocations = allocate_pool_across_goals(goals, recommendation_pool)

    # clear old data
    InvestmentRecommendation.objects.filter(
        user=user,
        as_of=latest_as_of
    ).delete()

    created = []

    # =========================================
    # LOOP PER GOAL
    # =========================================
    for goal in goals:

        remaining = get_goal_remaining_amount(goal)
        progress = get_goal_progress_pct(goal)
        horizon = get_goal_horizon_months(goal)
        required_monthly = get_goal_required_monthly_investment(goal)

        if remaining <= 0:
            continue

        if horizon is None or horizon <= 0:
            continue

        allocation = goal_allocations.get(goal.id, {})
        suggested_goal_monthly = float(allocation.get("suggested_monthly_amount", 0) or 0)
        priority_score = float(allocation.get("priority_score", 0) or 0)

        if suggested_goal_monthly <= 0:
            continue

        allowed_categories = get_allowed_categories_for_horizon(horizon)

        scored = []

        # =========================================
        # FUND SCORING
        # =========================================
        for fund in candidates:

            if fund.category_key not in allowed_categories:
                continue

            score, suitability, rationale = score_fund_for_goal(
                fund,
                horizon,
                progress,
            )

            if suitability == "avoid":
                continue

            # ✅ RATIONALE ENRICH
            rationale["goal_name"] = goal.name
            rationale["goal_progress_pct"] = progress
            rationale["goal_remaining_amount"] = remaining
            rationale["goal_required_monthly"] = required_monthly
            rationale["goal_priority_score"] = priority_score

            rationale["monthly_income"] = monthly_income
            rationale["last_month_expense"] = last_month_expenses
            rationale["free_cashflow"] = free_cashflow
            rationale["recommendation_pool"] = recommendation_pool

            scored.append({
                "fund": fund,
                "score": score,
                "suitability": suitability,
                "rationale": rationale,
            })

        # sort best funds
        scored.sort(key=lambda x: x["score"], reverse=True)

        if not scored:
            continue

        # =========================================
        # FUND COUNT BASED ON HORIZON
        # =========================================
        if horizon <= 24:
            selected = scored[:1]
        elif horizon <= 60:
            selected = scored[:2]
        else:
            selected = scored[:3]

        # =========================================
        # SPLIT AMOUNT
        # =========================================
        split = split_goal_amount(
            suggested_goal_monthly,
            selected,
            horizon
        )

        # =========================================
        # SAVE RECOMMENDATIONS
        # =========================================
        for item in selected:
            fund = item["fund"]

            allocated_amount = float(split.get(fund.scheme_code, 0) or 0)

            rec = InvestmentRecommendation.objects.create(
                user=user,

                # GOAL
                goal=goal,
                goal_name=goal.name,
                goal_target_amount=goal.target_amount,
                goal_saved_amount=goal.saved_amount,
                goal_remaining_amount=remaining,
                goal_target_date=goal.target_date,
                goal_progress_pct=progress,
                goal_priority_score=priority_score,

                # FUND
                scheme_code=fund.scheme_code,
                scheme_name=fund.scheme_name,
                amc=fund.amc,
                category_key=fund.category_key,
                fund_type=fund.fund_type,
                benchmark_code=getattr(fund, "benchmark_code", ""),

                # SCORING
                score=item["score"],
                suitability=item["suitability"],

                # 💰 MONEY (FIXED)
                required_monthly_amount=required_monthly,
                income_based_cap=recommendation_pool,
                suggested_monthly_amount=allocated_amount,

                suggested_horizon_months=horizon,

                # SNAPSHOTS
                monthly_income_snapshot=monthly_income,
                last_month_expense_snapshot=last_month_expenses,
                free_cashflow_snapshot=free_cashflow,
                recommendation_pool_snapshot=recommendation_pool,

                # EXPLANATION
                summary=build_goal_summary(
                    goal,
                    horizon,
                    progress,
                    required_monthly,
                    allocated_amount,
                    monthly_income,
                    last_month_expenses,
                    free_cashflow,
                    recommendation_pool,
                    fund,
                ),

                rationale=item["rationale"],
                as_of=latest_as_of,
            )

            created.append(rec)

    return created