from django.db import models
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.conf import settings
from django.db import models
from django.utils import timezone

# =====================================================
# App User (Django Auth User Model) ✅
# =====================================================
class AppUserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("username is required")

        username = username.strip()
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(username=username, password=password, **extra_fields)


class AppUser(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(
        max_length=150,
        unique=True,          # ✅ UNIQUE
        db_index=True,
    )
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
             # ✅

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    groups = models.ManyToManyField(
        "auth.Group",
        blank=True,
        related_name="core_appuser_set",
        related_query_name="appuser",
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        blank=True,
        related_name="core_appuser_permissions_set",
        related_query_name="appuser",
    )

    objects = AppUserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    class Meta:
        swappable = "AUTH_USER_MODEL"

    def __str__(self):
        return self.username
# =====================================================
    # Income
# =====================================================
class Income(models.Model):
    CATEGORY_CHOICES = [
        ("SALARY", "SALARY"),
        ("FREELANCE", "FREELANCE"),
        ("BUSINESS", "BUSINESS"),
        ("RENTAL", "RENTAL"),
        ("INTEREST", "INTEREST"),
        ("OTHER", "OTHER"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="incomes",
    )

    source = models.CharField(max_length=255)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    income_date = models.DateField()
    description = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-income_date", "-id"]

    def __str__(self):
        return f"{self.user} | {self.category} | {self.amount}"

        is_stable = models.BooleanField(default=False)
        is_auto_generated = models.BooleanField(default=False)
        stable_parent = models.ForeignKey(
            "self",
            null=True,
            blank=True,
            on_delete=models.SET_NULL,
            related_name="generated_months",
        )
# =====================================================
# Savings Goal
# =====================================================
class SavingsGoal(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="savings_goals",
    )

    name = models.CharField(max_length=255)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    saved_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    target_date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-target_date", "-id"]

    def __str__(self):
        return f"{self.user} | {self.name}"


# ✅ ADD THESE 2 MODELS BELOW YOUR SavingsGoal

class SavingsContribution(models.Model):
    goal = models.ForeignKey(SavingsGoal, on_delete=models.CASCADE, related_name="contributions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="savings_contributions")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    contribution_date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} | {self.goal.name} | {self.amount}"

class NotificationEvent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_events")
    goal = models.ForeignKey(SavingsGoal, null=True, blank=True, on_delete=models.CASCADE, related_name="notification_events")

    event_key = models.CharField(max_length=80)  # e.g. DEADLINE_D15, NO_CONTRIB_2026_01
    event_date = models.DateField(default=timezone.localdate)

    channel = models.CharField(max_length=10, default="email")   # email
    status = models.CharField(max_length=10, default="sent")     # sent/failed
    meta = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "goal", "event_key"]),
            models.Index(fields=["event_date"]),
        ]

# =====================================================
# Emergency Fund
# =====================================================
class EmergencyFund(models.Model):
    
    INTERVAL_CHOICES = [
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("halfyearly", "Half-Yearly"),
        ("yearly", "Yearly"),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="emergency_funds",
    )

    name = models.CharField(max_length=255)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    saved_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.TextField(blank=True, default="")

    interval = models.CharField(
        max_length=20,
        choices=INTERVAL_CHOICES,
        default="monthly",
    )

    last_contribution_at = models.DateTimeField(null=True, blank=True)
    last_reminder_sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} | {self.name}"

    
    interval = models.CharField(max_length=20, default="monthly")  # you already added choices

    
    created_at = models.DateTimeField(auto_now_add=True)  # strongly recommended
    updated_at = models.DateTimeField(auto_now=True)      # optional but useful

class EmergencyFundContribution(models.Model):
    emergency_fund = models.ForeignKey(
        EmergencyFund,
        on_delete=models.CASCADE,
        related_name="contributions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="emergency_fund_contributions"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    contribution_date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} | {self.emergency_fund.name} | {self.amount}"

# =====================================================
# Loan
# =====================================================
class Loan(models.Model):
    TYPE_CHOICES = [("GIVEN", "GIVEN"), ("TAKEN", "TAKEN")]
    STATUS_CHOICES = [("ONGOING", "ONGOING"), ("PAID", "PAID")]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loans",
    )

    loan_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    person_name = models.CharField(max_length=120)
    title = models.CharField(max_length=255, blank=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.status = "PAID" if self.paid_amount >= self.amount else "ONGOING"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} | {self.loan_type} | {self.amount}"


# =====================================================
# Insurance Policy ✅
# =====================================================
class InsurancePolicy(models.Model):
    PAYMENT_INTERVAL_CHOICES = [
        ("Monthly", "Monthly"),
        ("Quarterly", "Quarterly"),
        ("Half-Yearly", "Half-Yearly"),
        ("Yearly", "Yearly"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="insurance_policies",
    )

    name = models.CharField(max_length=255)
    policy_number = models.CharField(max_length=100)

    start_date = models.DateField()
    end_date = models.DateField()

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_interval = models.CharField(
        max_length=20,
        choices=PAYMENT_INTERVAL_CHOICES,
    )

    note = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "policy_number")
        ordering = ["end_date"]

    def __str__(self):
        return f"{self.user} | {self.name} | {self.policy_number}"


# =====================================================
# Expense ✅ (Manual + OCR + Bank Statement)
# =====================================================
class Expense(models.Model):
    SOURCE_CHOICES = [
        ("MANUAL", "Manual"),
        ("OCR", "OCR"),
        ("STATEMENT", "Statement"),
    ]

    DIRECTION_CHOICES = [
        ("DEBIT", "Debit"),
        ("CREDIT", "Credit"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="expenses",
    )

    category = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField()

    description = models.TextField(blank=True, default="")
    merchant = models.CharField(max_length=140, blank=True, default="")
    payment_mode = models.CharField(max_length=30, blank=True, default="UPI")

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="MANUAL")
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default="DEBIT")

    txn_id = models.CharField(max_length=255, blank=True, null=True)
    raw_text = models.TextField(blank=True, null=True)

    # ✅ NEW: strong OCR dedupe field
    ocr_signature = models.CharField(max_length=255, blank=True, null=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expense_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "direction", "source", "ocr_signature"],
                name="uniq_expense_ocr_signature_per_user",
                condition=models.Q(ocr_signature__isnull=False),
            )
        ]

    def __str__(self):
        return f"{self.user_id} | {self.expense_date} | {self.amount} | {self.category}"
# =====================================================
# Recommendations ✅ (Expense Insights)
# =====================================================
class Recommendation(models.Model):
    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recommendations",
        db_index=True,
    )

    # e.g. expense, budget, subscription, vendor_repeat
    category = models.CharField(max_length=40, default="expense", db_index=True)

    title = models.CharField(max_length=140)
    message = models.TextField()

    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="medium")
    meta = models.JSONField(default=dict, blank=True)

    month_key = models.CharField(max_length=7, db_index=True)  # "2026-02"
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "month_key"]),
            models.Index(fields=["user", "category"]),
        ]

    def __str__(self):
        return f"{self.user} | {self.category} | {self.severity}"
# =====================================================
# Password Reset OTP ✅
# =====================================================
class PasswordResetOTP(models.Model):
    username = models.CharField(max_length=150, db_index=True)
    email = models.EmailField(db_index=True)
    otp_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=10)

    class Meta:
        indexes = [
            models.Index(fields=["username", "email"]),
        ]

    def __str__(self):
        return f"{self.username} | {self.email} | {self.created_at}"

# BENCHMARK

class BenchmarkIndex(models.Model):
    code = models.CharField(max_length=64, unique=True)  # e.g. NIFTY50
    name = models.CharField(max_length=128)

    def __str__(self):
        return self.code

class BenchmarkIndexDaily(models.Model):
    index = models.ForeignKey(BenchmarkIndex, on_delete=models.CASCADE, related_name="daily")
    date = models.DateField()
    close = models.DecimalField(max_digits=16, decimal_places=4)

    class Meta:
        unique_together = ("index", "date")
        indexes = [
            models.Index(fields=["index", "date"]),
        ]

# DB table to store daily fund NAV

class FundNavDaily(models.Model):
    scheme_code = models.IntegerField(db_index=True)
    date = models.DateField(db_index=True)
    nav = models.DecimalField(max_digits=20, decimal_places=6)

    class Meta:
        unique_together = ("scheme_code", "date")
        indexes = [
            models.Index(fields=["scheme_code", "date"]),
        ]

# Create a “training rows” table


class FundMLSample(models.Model):
    scheme_code = models.IntegerField(db_index=True)
    as_of = models.DateField(db_index=True)

    category_key = models.CharField(max_length=50, db_index=True)   # e.g. largecap/midcap/smallcap/debt_govt etc.
    benchmark_code = models.CharField(max_length=50, db_index=True) # e.g. NIFTY50

    # -------- FEATURES (computed at time t = as_of) ----------
    nav = models.DecimalField(max_digits=20, decimal_places=6)
    ret_1w = models.FloatField(null=True, blank=True)
    ret_1m = models.FloatField(null=True, blank=True)
    vol_1m = models.FloatField(null=True, blank=True)      # volatility
    bench_ret_1m = models.FloatField(null=True, blank=True)
    alpha_1m = models.FloatField(null=True, blank=True)    # fund_ret_1m - bench_ret_1m

    # -------- TARGETS (computed from future) ----------
    y_fund_ret_1w = models.FloatField(null=True, blank=True)   # regression target
    y_outperform_1w = models.IntegerField(null=True, blank=True)  # 0/1 label

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("scheme_code", "as_of")
        indexes = [models.Index(fields=["benchmark_code", "as_of"])]

# DB table to store predictions




class FundPredictionDaily(models.Model):
    scheme_code = models.IntegerField(db_index=True)
    as_of = models.DateField(db_index=True)

    # Outputs
    pred_ret_1w = models.FloatField(null=True, blank=True)      # predicted 1-week return (decimal, e.g. 0.012)
    pred_nav_1w = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    prob_outperform_1w = models.FloatField(null=True, blank=True)  # 0..1 probability

    # Metadata
    model_version = models.CharField(max_length=50, default="xgb_v1")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("scheme_code", "as_of")
        indexes = [
            models.Index(fields=["as_of"]),
            models.Index(fields=["scheme_code", "as_of"]),
        ]

    def __str__(self):
        return f"{self.scheme_code} {self.as_of} p={self.prob_outperform_1w}"

# model FundPrediction

class FundPrediction(models.Model):
    scheme_code = models.IntegerField(db_index=True)
    scheme_name = models.CharField(max_length=255, blank=True, default="")
    amc = models.CharField(max_length=100, blank=True, default="")

    category_key = models.CharField(max_length=50, db_index=True)
    benchmark_code = models.CharField(max_length=50, db_index=True)

    as_of = models.DateField(db_index=True)
    pred_for_date = models.DateField(db_index=True)

    pred_nextweek_return = models.FloatField()
    prob_outperform = models.FloatField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("scheme_code", "as_of")
        indexes = [
            models.Index(fields=["category_key", "as_of"]),
            models.Index(fields=["benchmark_code", "as_of"]),
        ]
## DB table to store fund analytics (for recommendation rationale and display)

class FundAnalyticsSnapshot(models.Model):
    scheme_code = models.CharField(max_length=50)
    scheme_name = models.CharField(max_length=255)
    amc = models.CharField(max_length=120, blank=True, default="")
    category_key = models.CharField(max_length=80, blank=True, default="")
    fund_type = models.CharField(max_length=30, blank=True, default="")   # active / passive
    benchmark_code = models.CharField(max_length=50, blank=True, default="")

    as_of = models.DateField()

    latest_nav = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    return_1y = models.FloatField(default=0)
    return_3y = models.FloatField(default=0)
    return_5y = models.FloatField(default=0)

    volatility_1y = models.FloatField(default=0)
    max_drawdown_1y = models.FloatField(default=0)

    alpha_1y = models.FloatField(default=0)
    consistency_score = models.FloatField(default=0)
    stability_score = models.FloatField(default=0)

    expense_ratio = models.FloatField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("scheme_code", "as_of")
        indexes = [
            models.Index(fields=["category_key", "as_of"]),
            models.Index(fields=["fund_type", "as_of"]),
        ]

    def __str__(self):
        return f"{self.scheme_name} ({self.as_of})"


class InvestmentRecommendation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="investment_recommendations"
    )

    # ✅ Goal context
    goal = models.ForeignKey(
        SavingsGoal,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="investment_recommendations",
    )
    goal_name = models.CharField(max_length=255, blank=True, default="")
    goal_target_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    goal_saved_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    goal_remaining_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    goal_target_date = models.DateField(null=True, blank=True)
    # ✅ NEW optional clarity fields
    goal_progress_pct = models.FloatField(default=0)
    goal_priority_score = models.FloatField(default=0)

    # ✅ Fund info
    scheme_code = models.CharField(max_length=50)
    scheme_name = models.CharField(max_length=255)
    amc = models.CharField(max_length=120, blank=True, default="")
    category_key = models.CharField(max_length=80, blank=True, default="")
    fund_type = models.CharField(max_length=30, blank=True, default="")
    benchmark_code = models.CharField(max_length=50, blank=True, default="")

    # ✅ Recommendation scoring
    score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    suitability = models.CharField(max_length=30, blank=True, default="")

    # ✅ Monthly amount details
    required_monthly_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    income_based_cap = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    suggested_monthly_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # ✅ Horizon / explanation
    suggested_horizon_months = models.PositiveIntegerField(default=36)
    summary = models.TextField(blank=True, default="")
    rationale = models.JSONField(default=dict, blank=True)

    # ✅ Snapshot (🔥 NEW + IMPORTANT)
    monthly_income_snapshot = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    last_month_expense_snapshot = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    free_cashflow_snapshot = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    recommendation_pool_snapshot = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # ✅ Date
    as_of = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "as_of"]),
            models.Index(fields=["scheme_code", "as_of"]),
            models.Index(fields=["goal", "as_of"]),
            models.Index(fields=["user", "goal", "as_of"]),
        ]

    def __str__(self):
        goal_part = f" | {self.goal_name}" if self.goal_name else ""
        return f"{self.user} - {self.scheme_name}{goal_part}"


#-----monthly email--------

class MonthlySummaryEmailLog(models.Model):
    STATUS_CHOICES = (
        ("success", "Success"),
        ("failed", "Failed"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    year = models.IntegerField()
    month = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    subject = models.CharField(max_length=255, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "year", "month")

    def __str__(self):
        return f"{self.user} - {self.month}/{self.year} - {self.status}"
