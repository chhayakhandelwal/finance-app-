from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import Sum
from django.utils import timezone

from .models import (
    NotificationEvent,
    SavingsGoal,
    SavingsContribution,
    EmergencyFund,
)


# =========================================================
# COMMON EMAIL HELPER
# =========================================================

def _send_html_email(subject: str, text: str, html: str, to_email: str):
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=[to_email],
    )
    msg.attach_alternative(html, "text/html")
    return msg.send(fail_silently=False)


# =========================================================
# SAVINGS MODULE
# =========================================================

def _already_sent(user, goal, event_key) -> bool:
    return NotificationEvent.objects.filter(
        user=user,
        goal=goal,
        event_key=event_key,
    ).exists()


def _log(user, goal, event_key, meta=None, status="sent"):
    NotificationEvent.objects.create(
        user=user,
        goal=goal,
        event_key=event_key,
        event_date=timezone.localdate(),
        channel="email",
        status=status,
        meta=meta or {},
    )


def goal_stats(goal: SavingsGoal):
    target = Decimal(goal.target_amount or 0)
    saved = Decimal(goal.saved_amount or 0)
    remaining = max(target - saved, Decimal("0"))
    pct = float((saved / target) * 100) if target > 0 else 0.0
    pct = round(pct, 2)
    days_left = (goal.target_date - timezone.localdate()).days if goal.target_date else None
    return target, saved, remaining, pct, days_left


def contribution_summary(goal: SavingsGoal, days: int = 30):
    today = timezone.localdate()
    start = today - timezone.timedelta(days=days)

    qs = SavingsContribution.objects.filter(
        goal=goal,
        contribution_date__gte=start,
        contribution_date__lte=today,
    )

    total = qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
    count = qs.count()
    last_date = qs.order_by("-contribution_date").values_list("contribution_date", flat=True).first()

    return count, total, last_date


def build_detailed_body(goal: SavingsGoal, headline: str, extra_lines=None) -> str:
    user = goal.user
    target, saved, remaining, pct, days_left = goal_stats(goal)

    if days_left is None or days_left <= 0:
        daily_required = None
        monthly_required = None
    else:
        daily_required = (remaining / Decimal(days_left)) if remaining > 0 else Decimal("0")
        monthly_required = daily_required * Decimal("30")

    status_label = "On Track"
    if days_left is not None and days_left > 0:
        if pct < 50 and days_left < 15:
            status_label = "Behind Schedule"

    c7_count, c7_total, c7_last = contribution_summary(goal, days=7)
    c30_count, c30_total, c30_last = contribution_summary(goal, days=30)

    extra_lines = extra_lines or []

    lines = [
        f"Hi {user.get_username()},",
        "",
        headline,
        "",
        "==============================",
        "GOAL DETAILS",
        "==============================",
        f"Goal Name       : {goal.name}",
        f"Target Amount   : ₹{int(target)}",
        f"Saved Amount    : ₹{int(saved)}",
        f"Remaining       : ₹{int(remaining)}",
        f"Progress        : {pct}%",
        f"Target Date     : {goal.target_date}",
        f"Days Left       : {days_left if days_left is not None else 'N/A'}",
        f"Status          : {status_label}",
        "",
        "==============================",
        "PACE & RECOMMENDATION",
        "==============================",
    ]

    if daily_required is None:
        lines.append("Required pace   : N/A")
    else:
        lines.append(f"Required pace   : ~₹{int(daily_required)}/day")
        lines.append(f"Monthly pace    : ~₹{int(monthly_required)}/month")

    lines += [
        "",
        "==============================",
        "RECENT CONTRIBUTIONS SUMMARY",
        "==============================",
        f"Last 7 days  : {c7_count} contributions | Total ₹{int(c7_total)} | Last on {c7_last or '-'}",
        f"Last 30 days : {c30_count} contributions | Total ₹{int(c30_total)} | Last on {c30_last or '-'}",
        "",
    ]

    if extra_lines:
        lines += [
            "==============================",
            "NOTE",
            "==============================",
            *extra_lines,
            "",
        ]

    lines += [
        "Regards,",
        "Finance App",
    ]

    return "\n".join(lines)


def build_goal_card_html(
    goal: SavingsGoal,
    title: str,
    subtitle: str,
    accent_color: str = "#3b82f6",
    footer_note: str = "Stay consistent — every contribution gets you closer to your goal.",
):
    target, saved, remaining, pct, days_left = goal_stats(goal)
    progress_width = min(max(int(pct), 0), 100)

    return f"""
    <div style="font-family: Arial, sans-serif; line-height:1.6; color:#0b1220;">
      <h2 style="margin:0 0 8px;">{title}</h2>
      <p style="margin:0 0 12px;">{subtitle}</p>

      <div style="padding:14px; border:1px solid #e2e8f0; border-radius:12px; background:#f8fafc;">
        <p style="margin:0;"><b>Target:</b> ₹{int(target):,}</p>
        <p style="margin:6px 0 0;"><b>Saved:</b> ₹{int(saved):,}</p>
        <p style="margin:6px 0 0;"><b>Remaining:</b> ₹{int(remaining):,}</p>
        <p style="margin:6px 0 0;"><b>Target Date:</b> {goal.target_date}</p>
        <p style="margin:6px 0 0;"><b>Days Left:</b> {days_left if days_left is not None else 'N/A'}</p>

        <div style="margin-top:10px; background:#e2e8f0; border-radius:999px; overflow:hidden; height:12px;">
          <div style="width:{progress_width}%; background:{accent_color}; height:12px;"></div>
        </div>

        <p style="margin:8px 0 0; font-size:13px; color:#334155;">
          {footer_note}
        </p>
      </div>
    </div>
    """


def send_savings_goal_created_email(goal: SavingsGoal):
    user = goal.user
    if not user or not getattr(user, "email", None):
        return

    key = f"GOAL_CREATED_{goal.id}"
    if _already_sent(user, goal, key):
        return

    target, saved, remaining, pct, _ = goal_stats(goal)

    subject = f'🎯 Savings Goal Created: {goal.name}'
    headline = "Your new savings goal has been created successfully."
    extra = [
        f"Goal Name: {goal.name}",
        f"Target Amount: ₹{int(target)}",
        f"Saved Amount: ₹{int(saved)}",
        f"Remaining: ₹{int(remaining)}",
    ]

    body = build_detailed_body(goal, headline=headline, extra_lines=extra)

    html = build_goal_card_html(
        goal=goal,
        title="🎯 Savings Goal Created!",
        subtitle=f'Your new goal <b>{goal.name}</b> is ready ✅',
        accent_color="#3b82f6",
        footer_note=f"Current progress: {pct}% — start contributing regularly.",
    )

    try:
        sent_count = _send_html_email(subject, body, html, user.email)
        if sent_count != 1:
            _log(user, goal, key, meta={"type": "goal_created", "error": "send returned 0"}, status="failed")
            return

        _log(user, goal, key, meta={"type": "goal_created"}, status="sent")
    except Exception as e:
        _log(user, goal, key, meta={"type": "goal_created", "error": str(e)}, status="failed")


def send_contribution_added(goal: SavingsGoal, added_amount: Decimal):
    user = goal.user
    if not getattr(user, "email", None):
        return

    key = f"CONTRIB_{timezone.localdate().isoformat()}_{goal.id}_{int(added_amount)}"
    if _already_sent(user, goal, key):
        return

    subject = f'Savings updated: ₹{int(added_amount)} added to "{goal.name}"'
    headline = "New saving added successfully."
    extra = [f"Added Amount: ₹{int(added_amount)}"]

    body = build_detailed_body(goal, headline=headline, extra_lines=extra)

    _, _, _, pct, _ = goal_stats(goal)
    html = build_goal_card_html(
        goal=goal,
        title="🎯 Savings Goal Updated!",
        subtitle=f'You added <b>₹{int(added_amount):,}</b> to <b>{goal.name}</b> ✅',
        accent_color="#22c55e",
        footer_note=f"You’re now {pct}% closer to your goal 🚀",
    )

    try:
        sent_count = _send_html_email(subject, body, html, user.email)
        if sent_count != 1:
            _log(user, goal, key, meta={"type": "contribution_added", "error": "send returned 0"}, status="failed")
            return

        _log(user, goal, key, meta={"type": "contribution_added", "added": float(added_amount)}, status="sent")
    except Exception as e:
        _log(user, goal, key, meta={"type": "contribution_added", "error": str(e)}, status="failed")


def maybe_send_thresholds(goal: SavingsGoal):
    user = goal.user
    if not getattr(user, "email", None):
        return

    _, _, _, pct, _ = goal_stats(goal)

    for threshold in (80, 90):
        key = f"PROGRESS_{threshold}"
        if pct >= threshold and not _already_sent(user, goal, key):
            subject = f'You crossed {threshold}% on "{goal.name}"'
            headline = f"You crossed the {threshold}% milestone."
            extra = [f"Milestone reached: {threshold}%", f"Current progress: {pct}%"]

            body = build_detailed_body(goal, headline=headline, extra_lines=extra)

            html = build_goal_card_html(
                goal=goal,
                title=f"🚀 {threshold}% Milestone Reached!",
                subtitle=f'Your goal <b>{goal.name}</b> has crossed <b>{threshold}%</b> progress.',
                accent_color="#f59e0b",
                footer_note=f"Current progress: {pct}% — keep the momentum going.",
            )

            try:
                sent_count = _send_html_email(subject, body, html, user.email)
                if sent_count != 1:
                    _log(user, goal, key, meta={"type": "threshold", "error": "send returned 0"}, status="failed")
                    continue

                _log(user, goal, key, meta={"type": "threshold", "pct": pct, "threshold": threshold}, status="sent")
            except Exception as e:
                _log(user, goal, key, meta={"type": "threshold", "error": str(e)}, status="failed")


def send_goal_achieved(goal: SavingsGoal):
    user = goal.user
    if not getattr(user, "email", None):
        return

    key = "GOAL_ACHIEVED"
    if _already_sent(user, goal, key):
        return

    subject = f'Congratulations! You achieved "{goal.name}"'
    headline = "Congratulations! Your savings goal is achieved."
    extra = [
        "This goal is now completed.",
        f"Achieved Date: {timezone.localdate().isoformat()}",
    ]

    body = build_detailed_body(goal, headline=headline, extra_lines=extra)

    html = build_goal_card_html(
        goal=goal,
        title="🏆 Goal Achieved!",
        subtitle=f'Your savings goal <b>{goal.name}</b> is now complete.',
        accent_color="#16a34a",
        footer_note="Amazing work — this is a big financial milestone.",
    )

    try:
        sent_count = _send_html_email(subject, body, html, user.email)
        if sent_count != 1:
            _log(user, goal, key, meta={"type": "goal_achieved", "error": "send returned 0"}, status="failed")
            return

        _log(user, goal, key, meta={"type": "goal_achieved", "saved": float(goal.saved_amount or 0)}, status="sent")
    except Exception as e:
        _log(user, goal, key, meta={"type": "goal_achieved", "error": str(e)}, status="failed")


# =========================================================
# EMERGENCY FUNDS MODULE
# =========================================================

def _event_model_has_field(field_name: str) -> bool:
    try:
        return any(f.name == field_name for f in NotificationEvent._meta.get_fields())
    except Exception:
        return False


def _goal_field_nullable() -> bool:
    try:
        goal_field = NotificationEvent._meta.get_field("goal")
        return getattr(goal_field, "null", False)
    except Exception:
        return False


def _already_sent_emergency(user, fund: EmergencyFund, event_key: str) -> bool:
    if _event_model_has_field("emergency_fund"):
        return NotificationEvent.objects.filter(
            user=user,
            emergency_fund=fund,
            event_key=event_key
        ).exists()

    try:
        return NotificationEvent.objects.filter(
            user=user,
            event_key=event_key,
            meta__fund_id=fund.id
        ).exists()
    except Exception:
        return False


def _log_emergency(user, fund: EmergencyFund, event_key: str, meta=None, status="sent"):
    meta = meta or {}
    meta.setdefault("module", "emergency")
    meta.setdefault("fund_id", fund.id)
    meta.setdefault("fund_name", getattr(fund, "name", ""))

    try:
        if _event_model_has_field("emergency_fund"):
            return NotificationEvent.objects.create(
                user=user,
                emergency_fund=fund,
                event_key=event_key,
                event_date=timezone.localdate(),
                channel="email",
                status=status,
                meta=meta,
            )

        if _goal_field_nullable():
            return NotificationEvent.objects.create(
                user=user,
                goal=None,
                event_key=event_key,
                event_date=timezone.localdate(),
                channel="email",
                status=status,
                meta=meta,
            )

        return None
    except Exception:
        return None


def emergency_interval_delta(interval: str) -> timedelta:
    s = (interval or "monthly").lower()
    if s == "weekly":
        return timedelta(days=7)
    if s == "monthly":
        return timedelta(days=30)
    if s == "quarterly":
        return timedelta(days=90)
    if s == "halfyearly":
        return timedelta(days=182)
    if s == "yearly":
        return timedelta(days=365)
    return timedelta(days=30)


def _fmt_inr(n: Decimal) -> str:
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def send_emergency_created_email(fund: EmergencyFund):
    user = fund.user
    if not user or not getattr(user, "email", None):
        return

    key = f"EM_CREATED_{fund.id}"
    if _already_sent_emergency(user, fund, key):
        return

    target = Decimal(fund.target_amount or 0)
    saved = Decimal(fund.saved_amount or 0)
    remaining = max(target - saved, Decimal("0"))
    pct = int((saved / target) * 100) if target > 0 else 0

    subject = f"🛡️ Emergency Fund Created: {fund.name}"
    text = (
        f"✅ Your emergency fund is created successfully!\n\n"
        f"Fund: {fund.name}\n"
        f"Target: ₹{_fmt_inr(target)}\n"
        f"Current Saved: ₹{_fmt_inr(saved)}\n"
        f"Remaining: ₹{_fmt_inr(remaining)}\n"
        f"Interval: {fund.interval}\n"
    )

    html = f"""
    <div style="font-family: Arial, sans-serif; line-height:1.6; color:#0b1220;">
      <h2 style="margin:0 0 8px;">🛡️ Emergency Fund Created!</h2>
      <p style="margin:0 0 12px;">Your new fund <b>{fund.name}</b> is ready ✅</p>

      <div style="padding:14px; border:1px solid #e2e8f0; border-radius:12px; background:#f8fafc;">
        <p style="margin:0;"><b>Target:</b> ₹{_fmt_inr(target)}</p>
        <p style="margin:6px 0 0;"><b>Saved:</b> ₹{_fmt_inr(saved)}</p>
        <p style="margin:6px 0 0;"><b>Remaining:</b> ₹{_fmt_inr(remaining)}</p>
        <p style="margin:6px 0 0;"><b>Interval:</b> {fund.interval}</p>

        <div style="margin-top:10px; background:#e2e8f0; border-radius:999px; overflow:hidden; height:12px;">
          <div style="width:{min(pct,100)}%; background:#3b82f6; height:12px;"></div>
        </div>
        <p style="margin:8px 0 0; font-size:13px; color:#334155;">
          Start small — ₹50 today is better than ₹0 tomorrow 💙
        </p>
      </div>
    </div>
    """

    try:
        sent_count = _send_html_email(subject, text, html, user.email)

        if sent_count != 1:
            _log_emergency(
                user,
                fund,
                key,
                meta={"type": "emergency_created", "error": "send returned 0"},
                status="failed",
            )
            return

        _log_emergency(
            user,
            fund,
            key,
            meta={"type": "emergency_created", "sent_count": sent_count},
            status="sent",
        )
    except Exception as e:
        _log_emergency(
            user,
            fund,
            key,
            meta={"type": "emergency_created", "error": str(e)},
            status="failed",
        )


def send_emergency_success_email(fund: EmergencyFund, added_amount: Decimal):
    user = fund.user
    if not getattr(user, "email", None):
        return

    key = f"EM_ADD_{timezone.localdate().isoformat()}_{fund.id}_{int(Decimal(added_amount or 0))}"
    if _already_sent_emergency(user, fund, key):
        return

    target = Decimal(fund.target_amount or 0)
    saved = Decimal(fund.saved_amount or 0)
    remaining = max(target - saved, Decimal("0"))
    pct = int((saved / target) * 100) if target > 0 else 0

    subject = f"✅ Emergency Fund Updated: {fund.name} ({pct}% done)"
    text = (
        f"🎉 Saving added successfully!\n\n"
        f"Fund: {fund.name}\n"
        f"Added: ₹{_fmt_inr(Decimal(added_amount or 0))}\n"
        f"Saved: ₹{_fmt_inr(saved)} / ₹{_fmt_inr(target)}\n"
        f"Remaining: ₹{_fmt_inr(remaining)}\n"
        f"Progress: {pct}%\n"
    )

    html = f"""
    <div style="font-family: Arial, sans-serif; line-height:1.6; color:#0b1220;">
      <h2 style="margin:0 0 8px;">🎉 Saving Added Successfully!</h2>
      <p style="margin:0 0 12px;">You just strengthened your safety net in <b>{fund.name}</b> 🛡️</p>

      <div style="padding:14px; border:1px solid #e2e8f0; border-radius:12px; background:#f8fafc;">
        <p style="margin:0;"><b>Added:</b> ₹{_fmt_inr(Decimal(added_amount or 0))}</p>
        <p style="margin:6px 0 0;"><b>Saved:</b> ₹{_fmt_inr(saved)} / ₹{_fmt_inr(target)}</p>
        <p style="margin:6px 0 0;"><b>Remaining:</b> ₹{_fmt_inr(remaining)}</p>

        <div style="margin-top:10px; background:#e2e8f0; border-radius:999px; overflow:hidden; height:12px;">
          <div style="width:{min(pct,100)}%; background:#22c55e; height:12px;"></div>
        </div>

        <p style="margin:8px 0 0; font-size:13px; color:#334155;">
          🚀 You’re <b>{pct}%</b> close to your target.
        </p>
      </div>
    </div>
    """

    try:
        sent_count = _send_html_email(subject, text, html, user.email)
        if sent_count != 1:
            _log_emergency(
                user,
                fund,
                key,
                meta={"type": "emergency_success", "error": "send returned 0"},
                status="failed",
            )
            return

        _log_emergency(
            user,
            fund,
            key,
            meta={"type": "emergency_success", "added": float(Decimal(added_amount or 0))},
            status="sent",
        )
    except Exception as e:
        _log_emergency(
            user,
            fund,
            key,
            meta={"type": "emergency_success", "error": str(e)},
            status="failed",
        )


def send_emergency_missed_interval_email(fund: EmergencyFund, days_overdue: int):
    user = fund.user
    if not getattr(user, "email", None):
        return

    key = f"EM_MISSED_{timezone.localdate().isoformat()}_{fund.id}"
    if _already_sent_emergency(user, fund, key):
        return

    target = Decimal(fund.target_amount or 0)
    saved = Decimal(fund.saved_amount or 0)
    remaining = max(target - saved, Decimal("0"))
    pct = int((saved / target) * 100) if target > 0 else 0

    subject = f"⏰ Reminder: Add to {fund.name} ({pct}% complete)"
    text = (
        f"⏰ Friendly reminder!\n\n"
        f"You haven’t added savings to '{fund.name}' within your selected interval.\n"
        f"Saved: ₹{_fmt_inr(saved)} / ₹{_fmt_inr(target)}\n"
        f"Remaining: ₹{_fmt_inr(remaining)}\n"
        f"Overdue: {int(days_overdue)} day(s)\n"
    )

    html = text.replace("\n", "<br>")

    try:
        sent_count = _send_html_email(subject, text, html, user.email)
        if sent_count != 1:
            _log_emergency(
                user,
                fund,
                key,
                meta={"type": "emergency_missed", "error": "send returned 0"},
                status="failed",
            )
            return

        _log_emergency(
            user,
            fund,
            key,
            meta={"type": "emergency_missed", "days_overdue": int(days_overdue)},
            status="sent",
        )
    except Exception as e:
        _log_emergency(
            user,
            fund,
            key,
            meta={"type": "emergency_missed", "error": str(e)},
            status="failed",
        )