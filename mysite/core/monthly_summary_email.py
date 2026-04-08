from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from core.models import MonthlySummaryEmailLog
from core.monthly_summary_service import build_monthly_summary

def send_monthly_summary_email(user, year, month):
    if not user.email:
        return False, "User email missing"

    if MonthlySummaryEmailLog.objects.filter(user=user, year=year, month=month).exists():
        return False, "Already sent"

    summary = build_monthly_summary(user, year, month)

    # skip if user had no meaningful activity
    total_activity = (
        summary["income_total"]
        + summary["expense_total"]
        + summary["savings_total"]
        + summary["emergency_total"]
    )
    if total_activity <= 0:
        return False, "No activity"

    subject = f"📊 {summary['month_label']} Report: You spent ₹{int(summary['expense_total'])}"
    
    context = {
        "user": user,
        "summary": summary,
    }

    text_body = render_to_string("emails/monthly_summary.txt", context)
    html_body = render_to_string("emails/monthly_summary.html", context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html_body, "text/html")

    try:
        msg.send(fail_silently=False)
        MonthlySummaryEmailLog.objects.create(
            user=user,
            year=year,
            month=month,
            status="success",
            subject=subject,
        )
        return True, "Sent successfully"
    except Exception as e:
        MonthlySummaryEmailLog.objects.create(
            user=user,
            year=year,
            month=month,
            status="failed",
            subject=subject,
            error_message=str(e),
        )
        return False, str(e)

