from decimal import Decimal
from datetime import date, timedelta

from django.db import models
from django.db.models import Sum, Value, DecimalField
from django.db.models.functions import Coalesce

from core.models import (
    Income,
    Expense,
    SavingsGoal,
    EmergencyFund,
    SavingsContribution,
    EmergencyFundContribution,
    Loan,
    InsurancePolicy,
)


DECIMAL_OUTPUT = DecimalField(max_digits=14, decimal_places=2)


def decimal_coalesce_sum(field_name):
    return Coalesce(
        Sum(field_name),
        Value(Decimal("0.00")),
        output_field=DECIMAL_OUTPUT,
    )


def get_month_date_range(year, month):
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)
    return start_date, end_date


def get_previous_month(year, month):
    if month == 1:
        return year - 1, 12
    return year, month - 1


# ================= BASIC METRICS =================

def build_basic_metrics(user, year, month):
    start_date, end_date = get_month_date_range(year, month)

    income_total = (
        Income.objects.filter(
            user=user,
            income_date__range=[start_date, end_date],
        ).aggregate(total=decimal_coalesce_sum("amount"))["total"]
    )

    expense_qs = Expense.objects.filter(
        user=user,
        expense_date__range=[start_date, end_date],
        direction="DEBIT",
    )

    expense_total = expense_qs.aggregate(
        total=decimal_coalesce_sum("amount")
    )["total"]

    expense_count = expense_qs.count()

    savings_total = (
        SavingsContribution.objects.filter(
            user=user,
            contribution_date__range=[start_date, end_date],
        ).aggregate(total=decimal_coalesce_sum("amount"))["total"]
    )

    savings_updates_count = SavingsContribution.objects.filter(
        user=user,
        contribution_date__range=[start_date, end_date],
    ).count()

    emergency_total = (
        EmergencyFundContribution.objects.filter(
            user=user,
            contribution_date__range=[start_date, end_date],
        ).aggregate(total=decimal_coalesce_sum("amount"))["total"]
    )

    goals_completed_count = SavingsGoal.objects.filter(
        user=user,
        target_amount__gt=0,
        saved_amount__gte=models.F("target_amount"),
        updated_at__date__range=[start_date, end_date],
    ).count()

    return {
        "income_total": float(income_total or 0),
        "expense_total": float(expense_total or 0),
        "savings_total": float(savings_total or 0),
        "emergency_total": float(emergency_total or 0),
        "expense_count": expense_count,
        "savings_updates_count": savings_updates_count,
        "goals_completed_count": goals_completed_count,
    }


# ================= INSIGHTS =================

def build_insight_metrics(user, year, month):
    start_date, end_date = get_month_date_range(year, month)

    expense_qs = Expense.objects.filter(
        user=user,
        expense_date__range=[start_date, end_date],
        direction="DEBIT",
    )

    top_category_row = (
        expense_qs.values("category")
        .annotate(
            total=Coalesce(
                Sum("amount"),
                Value(Decimal("0.00")),
                output_field=DECIMAL_OUTPUT,
            )
        )
        .order_by("-total")
        .first()
    )

    highest_expense = expense_qs.order_by("-amount").first()

    savings_total = (
        SavingsContribution.objects.filter(
            user=user,
            contribution_date__range=[start_date, end_date],
        ).aggregate(total=decimal_coalesce_sum("amount"))["total"]
    ) or 0

    income_total = (
        Income.objects.filter(
            user=user,
            income_date__range=[start_date, end_date],
        ).aggregate(total=decimal_coalesce_sum("amount"))["total"]
    ) or 0

    savings_rate = (float(savings_total) / float(income_total) * 100) if income_total else 0

    remaining_goal_amount = 0
    for goal in SavingsGoal.objects.filter(user=user):
        target = float(goal.target_amount or 0)
        saved = float(goal.saved_amount or 0)
        if target > saved:
            remaining_goal_amount += (target - saved)

    savings_goals_total_saved = SavingsGoal.objects.filter(user=user).aggregate(
        total=decimal_coalesce_sum("saved_amount")
    )["total"] or 0

    emergency_funds_total_saved = EmergencyFund.objects.filter(user=user).aggregate(
        total=decimal_coalesce_sum("saved_amount")
    )["total"] or 0

    active_lendings_count = Loan.objects.filter(user=user).exclude(
        status__iexact="PAID"
    ).count()

    insurance_qs = InsurancePolicy.objects.filter(user=user).order_by("name")
    insurance_policies_count = insurance_qs.count()

    insurance_items = [
        {
            "name": policy.name,
            "policy_number": policy.policy_number,
        }
        for policy in insurance_qs
    ]

    return {
        "top_expense_category": top_category_row["category"] if top_category_row else None,
        "top_expense_category_amount": float(top_category_row["total"]) if top_category_row else 0,
        "highest_single_expense": float(highest_expense.amount) if highest_expense else 0,
        "highest_single_expense_note": (
            (getattr(highest_expense, "description", "") or "") if highest_expense else ""
        ),
        "savings_rate": round(savings_rate, 2),
        "remaining_goal_amount": round(remaining_goal_amount, 2),
        "savings_goals_total_saved": float(savings_goals_total_saved),
        "emergency_funds_total_saved": float(emergency_funds_total_saved),
        "active_lendings_count": active_lendings_count,
        "insurance_policies_count": insurance_policies_count,
        "insurance_items": insurance_items,
    }


# ================= COMPARISON =================

def build_previous_month_comparison(user, year, month):
    prev_year, prev_month = get_previous_month(year, month)

    current = build_basic_metrics(user, year, month)
    previous = build_basic_metrics(user, prev_year, prev_month)

    def pct_change(curr, prev):
        curr = float(curr or 0)
        prev = float(prev or 0)

        if prev == 0:
            return 100 if curr > 0 else 0

        return round(((curr - prev) / prev) * 100, 2)

    return {
        "income_change_pct": pct_change(current["income_total"], previous["income_total"]),
        "expense_change_pct": pct_change(current["expense_total"], previous["expense_total"]),
        "savings_change_pct": pct_change(current["savings_total"], previous["savings_total"]),
        "emergency_change_pct": pct_change(current["emergency_total"], previous["emergency_total"]),
        "previous_month": {
            "year": prev_year,
            "month": prev_month,
            **previous,
        },
    }


# ================= RECOMMENDATIONS =================

def build_recommendations(user, year, month, basic_metrics, insight_metrics, comparison_metrics):
    recommendations = []

    top_category = insight_metrics.get("top_expense_category")
    top_category_amount = float(insight_metrics.get("top_expense_category_amount", 0) or 0)
    savings_rate = float(insight_metrics.get("savings_rate", 0) or 0)
    expense_change_pct = float(comparison_metrics.get("expense_change_pct", 0) or 0)

    if top_category and top_category_amount > 0:
        reduce_by = round(top_category_amount * 0.10, 2)
        recommendations.append(
            f"Try reducing {str(top_category).lower()} by ₹{reduce_by:.0f} next month."
        )

    if basic_metrics["expense_total"] > basic_metrics["income_total"]:
        recommendations.append(
            "You spent more than you earned this month. Urgent attention needed."
        )

    emergency_fund = EmergencyFund.objects.filter(user=user).first()
    if emergency_fund:
        target = float(getattr(emergency_fund, "target_amount", 0) or 0)
        current = float(getattr(emergency_fund, "saved_amount", 0) or 0)
        if target > 0:
            progress = (current / target) * 100
            if 70 <= progress < 100:
                recommendations.append("You are close to completing your emergency fund.")

    prev = comparison_metrics.get("previous_month", {})
    prev_income = float(prev.get("income_total", 0) or 0)
    prev_savings = float(prev.get("savings_total", 0) or 0)

    prev_rate = (prev_savings / prev_income * 100) if prev_income else 0

    if savings_rate > prev_rate:
        recommendations.append("Your monthly savings rate improved.")

    if expense_change_pct > 15:
        recommendations.append("Your expenses increased noticeably compared to last month.")

    return recommendations[:3]


# ================= FINAL =================

def build_monthly_summary(user, year, month):
    basic_metrics = build_basic_metrics(user, year, month)
    insight_metrics = build_insight_metrics(user, year, month)
    comparison_metrics = build_previous_month_comparison(user, year, month)
    recommendations = build_recommendations(
        user,
        year,
        month,
        basic_metrics,
        insight_metrics,
        comparison_metrics,
    )

    return {
        "month": month,
        "year": year,
        "month_label": date(year, month, 1).strftime("%B %Y"),
        **basic_metrics,
        **insight_metrics,
        **comparison_metrics,
        "financial_health": (
            "Excellent" if basic_metrics["savings_total"] > basic_metrics["expense_total"]
            else "Moderate" if basic_metrics["expense_total"] < basic_metrics["income_total"]
            else "Needs Attention"
        ),
        "recommendations": recommendations,
    }