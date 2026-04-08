# core/recommendation_engine.py

import calendar
import logging
import threading
from collections import defaultdict
from datetime import date as dt_date

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count, Max, Sum
from django.utils import timezone

from .models import Expense, Recommendation

logger = logging.getLogger(__name__)


# -----------------------------
# Config
# -----------------------------
DEFAULT_CATEGORY_LIMITS = {
    "Food": 5000,
    "Food / Eating Out": 5000,
    "Shopping": 7000,
    "Groceries": 7000,
    "Entertainment": 2500,
    "Travel": 3000,
    "Bills": 4000,
    "Fuel": 3000,
    "Medical": 3000,
    "Other": 5000,
}

ESSENTIAL_CATEGORIES = {"Food", "Groceries", "Bills", "Fuel", "Medical"}
NON_ESSENTIAL_CATEGORIES = {"Shopping", "Entertainment", "Travel"}

SUBSCRIPTION_KEYWORDS = [
    "netflix", "prime", "amazon prime", "spotify", "hotstar",
    "subscription", "renewal", "recharge", "airtel", "jio", "vi",
]

FAST_RULE_PREFIXES = ("share:", "pacing:", "many_small:", "one_big:")
HEAVY_RULE_PREFIXES = ("spike:", "unusual:", "merchant_tip:", "vendor_repeat:", "subscription:")


# -----------------------------
# Helpers
# -----------------------------
def _month_key(dt):
    return f"{dt.year:04d}-{dt.month:02d}"


def _safe_lower(s):
    return (s or "").strip().lower()


def _month_range(d: dt_date):
    start = d.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1)
    else:
        end = start.replace(month=start.month + 1, day=1)
    return start, end


def _prev_month_date(d: dt_date):
    if d.month == 1:
        return d.replace(year=d.year - 1, month=12, day=1)
    return d.replace(month=d.month - 1, day=1)


def _normalize_category(cat: str) -> str:
    text = (cat or "").strip()

    alias_map = {
        "Food / Eating Out": "Food",
        "Eating Out": "Food",
        "Food": "Food",
        "Shopping": "Shopping",
        "Groceries": "Groceries",
        "Bills": "Bills",
        "Fuel": "Fuel",
        "Medical": "Medical",
        "Entertainment": "Entertainment",
        "Travel": "Travel",
        "Other": "Other",
    }

    return alias_map.get(text, text or "Other")


def _build_effective_limits(budget_limits=None):
    """
    Merge caller-provided budget limits over defaults.
    Expected input example:
    {
        "Food": 8000,
        "Shopping": 6000,
        ...
    }
    """
    effective = dict(DEFAULT_CATEGORY_LIMITS)

    if not budget_limits:
        return effective

    for raw_key, raw_value in (budget_limits or {}).items():
        key = _normalize_category(raw_key)
        try:
            val = float(raw_value or 0)
        except (TypeError, ValueError):
            continue

        if val < 0:
            val = 0

        effective[key] = val

    return effective


def _create_once(user, month_key, unique_key, category, title, message, severity="medium", meta=None):
    meta = meta or {}
    meta["unique_key"] = unique_key

    exists = Recommendation.objects.filter(
        user=user,
        month_key=month_key,
        meta__unique_key=unique_key,
        is_active=True,
    ).exists()

    if not exists:
        Recommendation.objects.create(
            user=user,
            month_key=month_key,
            category=category,
            title=title,
            message=message,
            severity=severity,
            meta=meta,
        )


def _delete_rules_by_prefixes(user, month_key, prefixes):
    qs = Recommendation.objects.filter(
        user=user,
        month_key=month_key,
        is_active=True,
    )

    for rec in qs:
        unique_key = (rec.meta or {}).get("unique_key", "")
        if any(unique_key.startswith(prefix) for prefix in prefixes):
            rec.delete()


def _get_current_month_base(user, d):
    month_key = _month_key(d)
    start, end = _month_range(d)

    qs = Expense.objects.filter(
        user=user,
        expense_date__gte=start,
        expense_date__lt=end,
        direction="DEBIT",
    )

    total = float(qs.aggregate(s=Sum("amount"))["s"] or 0)

    by_cat = list(
        qs.values("category").annotate(
            cat_total=Sum("amount"),
            c=Count("id"),
            max_amt=Max("amount"),
        ).order_by("-cat_total")
    )

    normalized_rows = []
    merged_totals = defaultdict(lambda: {"cat_total": 0.0, "c": 0, "max_amt": 0.0})

    for row in by_cat:
        raw_cat = row["category"] or "Other"
        cat = _normalize_category(raw_cat)
        merged_totals[cat]["cat_total"] += float(row["cat_total"] or 0)
        merged_totals[cat]["c"] += int(row["c"] or 0)
        merged_totals[cat]["max_amt"] = max(
            merged_totals[cat]["max_amt"],
            float(row["max_amt"] or 0),
        )

    for cat, data in merged_totals.items():
        normalized_rows.append({
            "category": cat,
            "cat_total": data["cat_total"],
            "c": data["c"],
            "max_amt": data["max_amt"],
        })

    normalized_rows.sort(key=lambda x: x["cat_total"], reverse=True)
    top3 = {row["category"] for row in normalized_rows[:3]}

    return {
        "month_key": month_key,
        "start": start,
        "end": end,
        "qs": qs,
        "total": total,
        "normalized_rows": normalized_rows,
        "top3": top3,
    }


def send_budget_limit_email(user, category_name, spent, limit, extra, month_key):
    to_email = getattr(user, "email", None)
    if not to_email:
        return False

    subject = f"Budget Alert: {category_name} limit exceeded ({month_key})"
    body = (
        f"Hi {getattr(user, 'username', 'there')},\n\n"
        f"Your budget limit has been exceeded for {category_name}.\n\n"
        f"Month: {month_key}\n"
        f"Spent this month: ₹{spent:.0f}\n"
        f"Budget limit: ₹{limit:.0f}\n"
        f"Over limit by: ₹{extra:.0f}\n\n"
        f"Please review your spending in this category.\n\n"
        f"— FinGrrow"
    )

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "no-reply@fingrrow.local"

    send_mail(
        subject=subject,
        message=body,
        from_email=from_email,
        recipient_list=[to_email],
        fail_silently=False,
    )
    return True


def _send_budget_email_bg(user, cat, spent, limit, extra, month_key):
    try:
        send_budget_limit_email(user, cat, spent, limit, extra, month_key)
    except Exception:
        logger.exception(
            "Failed to send budget email for user=%s category=%s month=%s",
            getattr(user, "id", None),
            cat,
            month_key,
        )


# -----------------------------
# Fast engine
# -----------------------------
def generate_fast_monthly_expense_recommendations(user, any_date_in_month=None, budget_limits=None):
    """
    Fast rules:
    - share
    - pacing
    - many small spends
    - one big spend
    - budget exceed email (async mail only)

    budget_limits example:
    {
        "Food": 8000,
        "Shopping": 6000
    }
    """
    today = timezone.localdate()
    d = any_date_in_month or today
    effective_limits = _build_effective_limits(budget_limits)

    base = _get_current_month_base(user, d)
    month_key = base["month_key"]
    total = base["total"]
    normalized_rows = base["normalized_rows"]
    top3 = base["top3"]

    _delete_rules_by_prefixes(user, month_key, FAST_RULE_PREFIXES)

    if total <= 0:
        return

    days_in_month = calendar.monthrange(d.year, d.month)[1]
    day_num = int(d.day)

    for row in normalized_rows:
        cat = row["category"] or "Other"
        spent = float(row["cat_total"] or 0)
        cnt = int(row["c"] or 0)
        max_amt = float(row["max_amt"] or 0)
        avg_amt = (spent / cnt) if cnt else 0.0

        if spent <= 0:
            continue

        limit = float(effective_limits.get(cat, effective_limits.get("Other", 0)) or 0)
        share = (spent / total) if total else 0.0

        if limit and spent > limit:
            extra = spent - limit
            threading.Thread(
                target=_send_budget_email_bg,
                args=(user, cat, spent, limit, extra, month_key),
                daemon=True,
            ).start()

        if cat in NON_ESSENTIAL_CATEGORIES:
            tone_hint = "This is a non-essential category — try to reduce if possible."
        elif cat in ESSENTIAL_CATEGORIES:
            tone_hint = "This is an essential category — try to optimize without hurting basics."
        else:
            tone_hint = "Review this category and adjust if needed."

        if (cat in top3) or (share >= 0.15):
            severity = "high" if share >= 0.30 else "medium"
            _create_once(
                user=user,
                month_key=month_key,
                unique_key=f"share:{cat}:{month_key}",
                category="expense",
                title=f"Spending summary: {cat}",
                message=(
                    f"This month you spent ₹{spent:.0f} on {cat} "
                    f"({(share * 100):.0f}% of total spending). {tone_hint}"
                ),
                severity=severity,
                meta={
                    "rule": "category_share_dynamic",
                    "category_name": cat,
                    "categoryKey": cat,
                    "spent": spent,
                    "share": share,
                    "limit": limit,
                },
            )

        if limit and day_num >= 4:
            allowed_so_far = limit * (day_num / float(days_in_month))
            if spent > allowed_so_far:
                _create_once(
                    user=user,
                    month_key=month_key,
                    unique_key=f"pacing:{cat}:{month_key}",
                    category="expense",
                    title=f"Overspending early in {cat}",
                    message=(
                        f"By day {day_num}/{days_in_month}, a healthy pacing is about ₹{allowed_so_far:.0f} "
                        f"for {cat} (based on your limit ₹{limit:.0f}). "
                        f"You’ve already spent ₹{spent:.0f}. Try slowing down for the rest of the month."
                    ),
                    severity="high" if spent > (allowed_so_far * 1.25) else "medium",
                    meta={
                        "rule": "daily_pacing",
                        "category_name": cat,
                        "categoryKey": cat,
                        "allowed_so_far": allowed_so_far,
                        "limit": limit,
                        "spent": spent,
                    },
                )

        if cnt >= 10 and avg_amt <= 300 and spent >= 800:
            _create_once(
                user=user,
                month_key=month_key,
                unique_key=f"many_small:{cat}:{month_key}",
                category="expense",
                title=f"Many small {cat} spends",
                message=(
                    f"You made {cnt} transactions in {cat} (avg ₹{avg_amt:.0f}). "
                    f"Small spends add up — try setting a mini-cap per day/week."
                ),
                severity="medium",
                meta={
                    "rule": "small_frequent",
                    "category_name": cat,
                    "categoryKey": cat,
                    "count": cnt,
                    "avg": avg_amt,
                    "limit": limit,
                },
            )

        if max_amt >= 2000 or (spent > 0 and max_amt >= 0.45 * spent and max_amt >= 1200):
            _create_once(
                user=user,
                month_key=month_key,
                unique_key=f"one_big:{cat}:{month_key}",
                category="expense",
                title=f"One big {cat} expense drove spending",
                message=(
                    f"Your biggest {cat} transaction is ₹{max_amt:.0f}. "
                    f"Big purchases can spike the month — plan such spends or split across months if possible."
                ),
                severity="medium" if max_amt < 4000 else "high",
                meta={
                    "rule": "few_big",
                    "category_name": cat,
                    "categoryKey": cat,
                    "max_amt": max_amt,
                    "limit": limit,
                },
            )


# -----------------------------
# Heavy engine
# -----------------------------
def generate_heavy_monthly_expense_recommendations(user, any_date_in_month=None, budget_limits=None):
    """
    Heavy rules:
    - spike vs last month
    - unusual rise vs 3 months
    - shopping single merchant
    - repeated vendor
    - subscription detection

    budget_limits is accepted for interface consistency.
    """
    today = timezone.localdate()
    d = any_date_in_month or today
    effective_limits = _build_effective_limits(budget_limits)

    base = _get_current_month_base(user, d)
    month_key = base["month_key"]
    qs = base["qs"]
    total = base["total"]
    normalized_rows = base["normalized_rows"]

    _delete_rules_by_prefixes(user, month_key, HEAVY_RULE_PREFIXES)

    if total <= 0:
        return

    prev_d = _prev_month_date(d)
    prev_start, prev_end = _month_range(prev_d)

    prev_qs = Expense.objects.filter(
        user=user,
        expense_date__gte=prev_start,
        expense_date__lt=prev_end,
        direction="DEBIT",
    )

    prev_totals = defaultdict(float)
    for r in prev_qs.values("category").annotate(s=Sum("amount")):
        cat = _normalize_category(r["category"] or "Other")
        prev_totals[cat] += float(r["s"] or 0)

    last3_ranges = []
    temp = d.replace(day=1)
    for _ in range(3):
        temp = _prev_month_date(temp)
        s, e = _month_range(temp)
        last3_ranges.append((s, e))

    last3_totals_by_cat = defaultdict(list)
    for s, e in last3_ranges:
        m_qs = Expense.objects.filter(
            user=user,
            expense_date__gte=s,
            expense_date__lt=e,
            direction="DEBIT",
        )
        month_map = defaultdict(float)
        for r in m_qs.values("category").annotate(s=Sum("amount")):
            cat = _normalize_category(r["category"] or "Other")
            month_map[cat] += float(r["s"] or 0)
        for cat_name, amt in month_map.items():
            last3_totals_by_cat[cat_name].append(amt)

    for row in normalized_rows:
        cat = row["category"] or "Other"
        spent = float(row["cat_total"] or 0)
        limit = float(effective_limits.get(cat, effective_limits.get("Other", 0)) or 0)

        if spent <= 0:
            continue

        prev_spent = float(prev_totals.get(cat, 0) or 0)
        if prev_spent > 0 and spent > (prev_spent * 1.30) and spent >= 500:
            inc_pct = ((spent - prev_spent) / spent) * 100.0
            _create_once(
                user=user,
                month_key=month_key,
                unique_key=f"spike:{cat}:{month_key}",
                category="expense",
                title=f"{cat} spending spike vs last month",
                message=(
                    f"{cat} increased by {inc_pct:.0f}% vs last month "
                    f"(₹{prev_spent:.0f} → ₹{spent:.0f}). "
                    f"Check what changed and cut unnecessary spends."
                ),
                severity="high" if inc_pct >= 60 else "medium",
                meta={
                    "rule": "prev_month_spike",
                    "category_name": cat,
                    "categoryKey": cat,
                    "inc_pct": inc_pct,
                    "limit": limit,
                },
            )

        hist = last3_totals_by_cat.get(cat, [])
        if len(hist) >= 2:
            avg3 = sum(hist) / float(len(hist)) if hist else 0.0
            if avg3 > 0 and spent >= (2.0 * avg3) and spent >= 1000:
                _create_once(
                    user=user,
                    month_key=month_key,
                    unique_key=f"unusual:{cat}:{month_key}",
                    category="expense",
                    title=f"Unusual rise in {cat}",
                    message=(
                        f"{cat} spending looks unusually high this month (₹{spent:.0f}) "
                        f"vs your recent average (~₹{avg3:.0f}). "
                        f"Review transactions for one-time events or leaks."
                    ),
                    severity="high",
                    meta={
                        "rule": "unusual_category",
                        "category_name": cat,
                        "categoryKey": cat,
                        "avg3": avg3,
                        "limit": limit,
                    },
                )

    shopping_qs = qs.filter(category__in=["Shopping"])
    shopping_by_merchant = list(
        shopping_qs.values("merchant").annotate(
            c=Count("id"),
            s=Sum("amount"),
        ).order_by("-c", "-s")[:10]
    )

    if shopping_by_merchant:
        total_shopping = float(shopping_qs.aggregate(s=Sum("amount"))["s"] or 0)
        hot = []
        for r in shopping_by_merchant:
            m = (r["merchant"] or "").strip()
            if not m:
                continue
            ml = _safe_lower(m)
            if any(k in ml for k in ["amazon", "amzn", "flipkart"]):
                hot.append({"merchant": m, "count": int(r["c"] or 0), "spent": float(r["s"] or 0)})

        if hot and total_shopping > 0:
            best = sorted(hot, key=lambda x: (x["count"], x["spent"]), reverse=True)[0]
            share_m = (best["spent"] / total_shopping) if total_shopping else 0.0

            if best["count"] >= 2 and best["spent"] >= 800:
                _create_once(
                    user=user,
                    month_key=month_key,
                    unique_key=f"merchant_tip:shopping:{best['merchant']}:{month_key}",
                    category="expense",
                    title="Shopping is driven by a single merchant",
                    message=(
                        f"A large chunk of Shopping is from '{best['merchant']}' "
                        f"({best['count']} txns, ₹{best['spent']:.0f}, ~{(share_m * 100):.0f}% of Shopping). "
                        f"Try setting a weekly cap for this merchant."
                    ),
                    severity="medium" if share_m < 0.60 else "high",
                    meta={
                        "rule": "merchant_tip",
                        "merchant": best["merchant"],
                        "merchant_share": share_m,
                        "categoryKey": "Shopping",
                        "limit": float(effective_limits.get("Shopping", 0) or 0),
                    },
                )

    by_vendor = qs.values("merchant", "description").annotate(
        c=Count("id"),
        amt=Sum("amount"),
    ).order_by("-c")

    vendor_map = defaultdict(lambda: {"count": 0, "spent": 0, "examples": set()})
    for v in by_vendor:
        vendor = (v["merchant"] or "").strip() or (v["description"] or "").strip()[:40] or "Unknown"
        vendor_map[vendor]["count"] += int(v["c"] or 0)
        vendor_map[vendor]["spent"] += float(v["amt"] or 0)
        if v["description"]:
            vendor_map[vendor]["examples"].add(v["description"][:60])

    for vendor, info in sorted(vendor_map.items(), key=lambda x: x[1]["count"], reverse=True)[:8]:
        if info["count"] >= 6 and info["spent"] >= 800:
            _create_once(
                user=user,
                month_key=month_key,
                unique_key=f"vendor_repeat:{vendor}:{month_key}",
                category="vendor_repeat",
                title="Repeated spending at the same vendor",
                message=(
                    f"You spent at '{vendor}' {info['count']} times this month, totaling about ₹{info['spent']:.0f}. "
                    f"If this is not essential, consider reducing it."
                ),
                severity="medium",
                meta={
                    "rule": "vendor_repeat",
                    "vendor": vendor,
                    "count": info["count"],
                    "spent": info["spent"],
                },
            )

    top_desc = qs.values("description").annotate(amt=Sum("amount")).order_by("-amt")[:30]
    for row in top_desc:
        desc = _safe_lower(row["description"])
        if not desc:
            continue

        if any(k in desc for k in SUBSCRIPTION_KEYWORDS):
            spent = float(row["amt"] or 0)
            _create_once(
                user=user,
                month_key=month_key,
                unique_key=f"subscription:{desc[:30]}:{month_key}",
                category="subscription",
                title="Possible subscription or recurring charge",
                message=(
                    f"'{row['description']}' looks like a subscription/recurring expense (₹{spent:.0f}). "
                    f"If you don’t use it, cancel it."
                ),
                severity="medium",
                meta={
                    "rule": "subscription_keyword",
                    "description": row["description"],
                    "spent": spent,
                },
            )
            break


# -----------------------------
# Optional compatibility wrapper
# -----------------------------
def generate_monthly_expense_recommendations(user, any_date_in_month=None, budget_limits=None):
    """
    Compatibility wrapper.
    Runs fast + heavy sequentially.

    budget_limits example:
    {
        "Food": 8000,
        "Shopping": 6000,
        "Fuel": 3500
    }
    """
    generate_fast_monthly_expense_recommendations(
        user=user,
        any_date_in_month=any_date_in_month,
        budget_limits=budget_limits,
    )
    generate_heavy_monthly_expense_recommendations(
        user=user,
        any_date_in_month=any_date_in_month,
        budget_limits=budget_limits,
    )