from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from core.monthly_summary_email import send_monthly_summary_email

User = get_user_model()


class Command(BaseCommand):
    help = "Send monthly summary email"

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, required=False)
        parser.add_argument("--year", type=int, required=True)
        parser.add_argument("--month", type=int, required=True)

    def handle(self, *args, **options):
        year = options["year"]
        month = options["month"]
        user_id = options.get("user_id")

        users = User.objects.exclude(email="").exclude(email__isnull=True)
        if user_id:
            users = users.filter(id=user_id)

        for user in users:
            ok, msg = send_monthly_summary_email(user, year, month)
            self.stdout.write(f"{user.username}: {msg}")