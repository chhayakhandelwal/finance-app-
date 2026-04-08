from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from .models import Recommendation
from .models import Income, SavingsGoal, Loan, EmergencyFund, InsurancePolicy, Expense

User = get_user_model()

# =====================================================
# ✅ Profile Serializer (GET + PATCH)
# =====================================================
class ProfileSerializer(serializers.ModelSerializer):
    # Frontend-friendly read-only joined string
    joined = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            "user_id",     # read-only in UI (identifier)
            "username",    # editable
            "email",       # editable if you use it
            "joined",      # read-only
        ]
        read_only_fields = ["user_id", "joined"]

        extra_kwargs = {
            "username": {"required": False, "allow_blank": True},
            "email": {"required": False, "allow_blank": True, "allow_null": True},
        }

    def get_joined(self, obj):
        dj = getattr(obj, "date_joined", None)
        return dj.strftime("%B %Y") if dj else ""

    def validate_username(self, value):
        value = (value or "").strip()
        if value == "":
            raise serializers.ValidationError("Username cannot be empty.")
        return value


class RecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recommendation
        fields = ["id", "category", "title", "message", "severity", "meta", "month_key", "created_at"]
# =====================================================
# ✅ AUTH (Register / Login)
# =====================================================
class RegisterSerializer(serializers.ModelSerializer):
    """
    Expected payload from frontend:
    {
      "username": "Chhavi",
      "user_id": "BV123",
      "password": "password123"
    }
    """
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["username", "user_id", "password"]

    def validate_username(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Username is required.")
        return value

    def validate_user_id(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("User ID is required.")
        return value
    def validate_email(self, value):
        email = value.strip().lower()

        if not email:
            raise serializers.ValidationError("Email is required.")

        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("This email is already registered.")

        return email

    def create(self, validated_data):
        password = validated_data.pop("password")
        # Uses AppUserManager.create_user() -> set_password()
        user = User.objects.create_user(password=password, **validated_data)
        return user


class LoginSerializer(serializers.Serializer):
    """
    Expected payload from frontend:
    {
      "user_id": "BV123",
      "password": "password123"
    }
    """
    user_id = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user_id = (attrs.get("user_id") or "").strip()
        password = attrs.get("password") or ""

        if not user_id or not password:
            raise serializers.ValidationError("User ID and password are required.")

        # Because USERNAME_FIELD = "user_id"
        user = authenticate(username=user_id, password=password)
        if not user:
            raise serializers.ValidationError("Invalid credentials or user not registered.")

        if not getattr(user, "is_active", True):
            raise serializers.ValidationError("User is inactive.")

        attrs["user"] = user
        return attrs


# =====================================================
# Income
# =====================================================
class IncomeSerializer(serializers.ModelSerializer):
    # Frontend sends "date" -> map to model field "income_date"
    date = serializers.DateField(source="income_date", required=True)
    class Meta:
        model = Income
        fields = [
            "id",
            "source",
            "category",
            "amount",
            "date",         # frontend write/read
            "income_date",  # read-only mirror for table display
            "description",
            "created_at",
            "updated_at",
            "date"
        ]
        read_only_fields = [
            "id",
            "income_date",
            "created_at",
            "updated_at",
        ]

    def validate_amount(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate_source(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Source is required.")
        return value


# =====================================================
# Savings Goal
# =====================================================
class SavingsGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavingsGoal
        fields = [
            "id",
            "name",
            "target_amount",
            "saved_amount",
            "target_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        target = attrs.get("target_amount", getattr(self.instance, "target_amount", None))
        saved = attrs.get("saved_amount", getattr(self.instance, "saved_amount", None))

        if target is not None and target <= 0:
            raise serializers.ValidationError({"target_amount": "Target amount must be greater than zero."})

        if saved is not None and saved < 0:
            raise serializers.ValidationError({"saved_amount": "Saved amount cannot be negative."})

        if target is not None and saved is not None and saved > target:
            raise serializers.ValidationError({"saved_amount": "Saved amount cannot exceed target amount."})

        name = attrs.get("name")
        if name is not None and not str(name).strip():
            raise serializers.ValidationError({"name": "Name cannot be empty."})

        return attrs


# =====================================================
# Emergency Fund
# =====================================================
class EmergencyFundSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyFund
        fields = [
            "id",
            "name",
            "target_amount",
            "saved_amount",
            "interval",
            "note",
              "last_contribution_at",
              "last_reminder_sent_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        target = attrs.get("target_amount", getattr(self.instance, "target_amount", None))
        saved = attrs.get("saved_amount", getattr(self.instance, "saved_amount", None))

        name = attrs.get("name")
        if name is not None and not str(name).strip():
            raise serializers.ValidationError({"name": "Fund name is required."})

        if target is not None and target <= 0:
            raise serializers.ValidationError({"target_amount": "Target amount must be greater than zero."})

        if saved is not None and saved < 0:
            raise serializers.ValidationError({"saved_amount": "Saved amount cannot be negative."})

        if target is not None and saved is not None and saved > target:
            raise serializers.ValidationError({"saved_amount": "Saved amount cannot exceed target amount."})

        return attrs


# =====================================================
# Loan
# =====================================================
class LoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = [
            "id",
            "loan_type",
            "person_name",
            "title",
            "amount",
            "paid_amount",
            "status",
            "start_date",
            "due_date",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def validate(self, attrs):
        amount = attrs.get("amount", getattr(self.instance, "amount", None))
        paid = attrs.get("paid_amount", getattr(self.instance, "paid_amount", 0))

        if amount is not None and amount <= 0:
            raise serializers.ValidationError({"amount": "Amount must be greater than zero."})

        if paid is not None and paid < 0:
            raise serializers.ValidationError({"paid_amount": "Paid amount cannot be negative."})

        if amount is not None and paid is not None and paid > amount:
            raise serializers.ValidationError({"paid_amount": "Paid amount cannot exceed amount."})

        person = attrs.get("person_name")
        if person is not None and not str(person).strip():
            raise serializers.ValidationError({"person_name": "Person name is required."})

        title = attrs.get("title")
        if title is not None and not str(title).strip():
            raise serializers.ValidationError({"title": "Title is required."})

        return attrs


# =====================================================
# ✅ Insurance Policy Serializer (camelCase frontend)
# =====================================================
class InsurancePolicySerializer(serializers.ModelSerializer):
    # Frontend -> Model mapping
    policyNumber = serializers.CharField(source="policy_number", required=True)
    startDate = serializers.DateField(source="start_date", required=True)
    endDate = serializers.DateField(source="end_date", required=True)
    interval = serializers.ChoiceField(
        source="payment_interval",
        choices=InsurancePolicy.PAYMENT_INTERVAL_CHOICES,
        required=True,
    )

    class Meta:
        model = InsurancePolicy
        fields = [
            "id",
            "name",
            "policyNumber",
            "startDate",
            "endDate",
            "amount",
            "interval",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        # attrs has MODEL field names because of source= mapping
        name = (attrs.get("name") or "").strip()
        policy_number = (attrs.get("policy_number") or "").strip()
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        amount = attrs.get("amount", getattr(self.instance, "amount", 0))

        errors = {}

        if not name:
            errors["name"] = "Insurance name is required."

        if not policy_number:
            errors["policyNumber"] = "Policy number is required."

        if amount is not None and float(amount) < 0:
            errors["amount"] = "Amount cannot be negative."

        if start and end and end < start:
            errors["endDate"] = "End date must be after start date."

        if errors:
            raise serializers.ValidationError(errors)

        # put trimmed values back
        attrs["name"] = name
        attrs["policy_number"] = policy_number

        return attrs


# =====================================================
# =====================================================
# ✅ Expense Serializer (camelCase frontend mapping)
# Frontend fields: categoryKey, date, note, merchant, amount, paymentMode
# Model fields: category, expense_date, description, merchant, amount, payment_mode
# =====================================================
class ExpenseSerializer(serializers.ModelSerializer):
    # Frontend -> Model mapping
    categoryKey = serializers.CharField(source="category", required=True)
    date = serializers.DateField(source="expense_date", required=True)

    note = serializers.CharField(
        source="description",
        required=False,
        allow_blank=True,
        allow_null=True,
        default="",
    )

    paymentMode = serializers.CharField(
        source="payment_mode",
        required=False,
        allow_blank=True,
        allow_null=True,
        default="UPI",
    )

    merchant = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        default="",
    )

    # Optional OCR/debug fields
    ocr_signature = serializers.CharField(read_only=True)
    balance = serializers.CharField(required=False, allow_blank=True, allow_null=True, write_only=True)

    # Read-only mirrors
    category = serializers.CharField(read_only=True)
    expense_date = serializers.DateField(read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id",
            "categoryKey",
            "amount",
            "date",
            "note",
            "merchant",
            "paymentMode",
            "source",
            "direction",
            "txn_id",
            "raw_text",
            "ocr_signature",
            "balance",
            "category",
            "expense_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "category",
            "expense_date",
            "direction",
            "ocr_signature",
        ]

    # -------- helpers --------
    def _trim(self, s, max_len, empty_as=""):
        if s is None:
            return empty_as
        s = str(s).strip()
        if s == "":
            return empty_as
        return s[:max_len]


    def _normalize_category(self, cat):
        if not cat:
            return "Other"
        return str(cat).strip()[:50]

    # -------- validation --------
    def validate(self, attrs):
        errors = {}

        category = self._normalize_category(attrs.get("category"))
        if not category:
            errors["categoryKey"] = "Category is required."
        attrs["category"] = category

        amount = attrs.get("amount")
        if amount is None or amount <= 0:
            errors["amount"] = "Amount must be greater than zero."

        if not attrs.get("expense_date"):
            errors["date"] = "Date is required."

        # force debit
        attrs["direction"] = "DEBIT"

        # clean fields
        attrs["merchant"] = self._trim(attrs.get("merchant", ""), 140,empty_as="")
        attrs["payment_mode"] = self._trim(attrs.get("payment_mode", "UPI"), 30) or "UPI"
        attrs["txn_id"] = self._trim(attrs.get("txn_id", None), 255)

        desc = attrs.get("description", "")
        attrs["description"] = (desc or "").strip()

        # source normalize
        src = (attrs.get("source") or "MANUAL").upper().strip()
        attrs["source"] = src if src in ["MANUAL", "OCR", "STATEMENT"] else "MANUAL"

        # remove write-only helper if model me field nahi hai
        attrs.pop("balance", None)

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    def create(self, validated_data):
        validated_data["direction"] = "DEBIT"
        validated_data.pop("balance", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data["direction"] = "DEBIT"
        validated_data.pop("balance", None)
        return super().update(instance, validated_data)
        #===================================================
# ✅ Investment Recommendation (Request Serializer)
# React sends:
# {
#   "risk": "MEDIUM",
#   "horizon": 5,
#   "amount": 5000,
#   "type": "BOTH",
#   "goal": "WEALTH",
#   "mode": "SIP"
# }
# =====================================================
class InvestmentRecommendRequestSerializer(serializers.Serializer):
    risk = serializers.ChoiceField(choices=["LOW", "MEDIUM", "HIGH"])
    horizon = serializers.FloatField(min_value=0.1)
    amount = serializers.FloatField(min_value=1)
    type = serializers.ChoiceField(choices=["STOCK", "MF", "BOTH"])

    goal = serializers.ChoiceField(
        choices=["WEALTH", "RETIREMENT", "EDUCATION", "HOUSE", "EMERGENCY"],
        required=False,
        default="WEALTH",
    )

    mode = serializers.ChoiceField(
        choices=["LUMPSUM", "SIP"],
        required=False,
        default="LUMPSUM",
    )