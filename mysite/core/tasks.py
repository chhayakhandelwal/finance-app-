# core/tasks.py

from __future__ import annotations

import calendar
from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone

from .models import SavingsGoal, SavingsContribution, NotificationEvent
from .services import build_detailed_body


def _sent(user, goal, key: str) -> bool:
    return NotificationEvent.objects.filter(user=user, goal=goal, event_key=key).exists()


def _log(user, goal, key: str, meta=None, status: str = "sent"):
    NotificationEvent.objects.create(
        user=user,
        goal=goal,
        event_key=key,
        event_date=timezone.localdate(),
        channel="email",
        status=status,
        meta=meta or {},
    )


@shared_task
def daily_deadline_reminders():
    """
    Sends target-date reminders when days_left is in:
    30 / 15 / 5 / 4 / 3 / 2 / 1
    """
    today = timezone.localdate()
    reminder_days = {30, 15, 5, 4, 3, 2, 1}

    goals = SavingsGoal.objects.select_related("user").all()

    for goal in goals:
        if not goal.target_date:
            continue

        days_left = (goal.target_date - today).days
        if days_left not in reminder_days:
            continue

        user = goal.user
        if not getattr(user, "email", None):
            continue

        key = f"DEADLINE_D{days_left}"
        if _sent(user, goal, key):
            continue

        subject = f'Reminder: {days_left} day(s) left for "{goal.name}"'
        headline = f"Target date reminder: {days_left} day(s) remaining."
        extra = [f"Reminder type: D-{days_left}"]

        body = build_detailed_body(goal, headline=headline, extra_lines=extra)

        try:
            send_mail(subject, body, None, [user.email])
            _log(user, goal, key, meta={"days_left": days_left})
        except Exception as e:
            _log(user, goal, key, meta={"error": str(e)}, status="failed")


@shared_task
def month_end_no_contribution_alert():
    """
    Runs on days 28-31 (via Celery Beat), but ONLY sends on the actual LAST day of the month.
    Checks whether the CURRENT month had ZERO contributions for each goal.
    """
    today = timezone.localdate()

    # ✅ Only proceed if today is the last day of this month
    last_day = calendar.monthrange(today.year, today.month)[1]
    if today.day != last_day:
        return "Not month end. Skipped."

    month_start = today.replace(day=1)
    month_key = f"{today.year}_{today.month:02d}"

    goals = SavingsGoal.objects.select_related("user").all()

    for goal in goals:
        user = goal.user
        if not getattr(user, "email", None):
            continue

        key = f"NO_CONTRIB_MONTHEND_{month_key}"
        if _sent(user, goal, key):
            continue

        contributed = SavingsContribution.objects.filter(
            goal=goal,
            contribution_date__gte=month_start,
            contribution_date__lte=today,
        ).exists()

        if contributed:
            continue

        subject = f'No saving added in {today.strftime("%B %Y")} for "{goal.name}"'
        headline = f"No contribution recorded in {today.strftime('%B %Y')}."
        extra = [
            "Month-end alert: you did not add any savings this month.",
            "Next step: add a contribution tomorrow to stay consistent.",
        ]

        body = build_detailed_body(goal, headline=headline, extra_lines=extra)

        try:
            send_mail(subject, body, None, [user.email])
            _log(user, goal, key, meta={"month": month_key})
        except Exception as e:
            _log(user, goal, key, meta={"error": str(e)}, status="failed")

    return "Month-end alerts processed."