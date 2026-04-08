import calendar
from datetime import date

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from core.monthly_summary_email import send_monthly_summary_email

User = get_user_model()


class Command(BaseCommand):
    help = "Automatically send monthly summary emails on the last day of the month"

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--user-id", type=int, required=False)
        parser.add_argument("--year", type=int, required=False)
        parser.add_argument("--month", type=int, required=False)

    def handle(self, *args, **options):
        today = date.today()

        year = options.get("year") or today.year
        month = options.get("month") or today.month
        force = options.get("force", False)
        user_id = options.get("user_id")

        if not force:
            last_day = calendar.monthrange(today.year, today.month)[1]
            if today.day != last_day:
                self.stdout.write("Today is not the last day of the month. Skipping.")
                return

        users = User.objects.exclude(email="").exclude(email__isnull=True)
        if user_id:
            users = users.filter(id=user_id)

        for user in users:
            ok, msg = send_monthly_summary_email(user, year, month)
            self.stdout.write(f"{user.username}: {msg}")