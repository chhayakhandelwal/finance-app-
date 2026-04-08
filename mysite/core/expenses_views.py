import logging
from datetime import datetime

from django.conf import settings
from django.utils import timezone
from rest_framework import generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import Expense, Recommendation
from .serializers import ExpenseSerializer, RecommendationSerializer
from .recommendation_engine import generate_monthly_expense_recommendations

logger = logging.getLogger(__name__)


@api_view(["GET", "POST"])
@permission_classes([permissions.IsAuthenticated])
def recommendation_list(request):
    if request.method == "POST":
        month_str = request.data.get("month")
        budget_limits = request.data.get("budget_limits", {}) or {}
    else:
        month_str = request.query_params.get("month")
        budget_limits = {}

    if month_str:
        try:
            any_date_in_month = datetime.strptime(f"{month_str}-01", "%Y-%m-%d").date()
        except ValueError:
            any_date_in_month = timezone.localdate().replace(day=1)
    else:
        any_date_in_month = timezone.localdate().replace(day=1)

    month_key = f"{any_date_in_month.year:04d}-{any_date_in_month.month:02d}"

    Recommendation.objects.filter(
        user=request.user,
        month_key=month_key,
        is_active=True,
    ).delete()

    generate_monthly_expense_recommendations(
        user=request.user,
        any_date_in_month=any_date_in_month,
        budget_limits=budget_limits,
    )

    qs = Recommendation.objects.filter(
        user=request.user,
        month_key=month_key,
        is_active=True,
    ).order_by("-id")

    return Response(RecommendationSerializer(qs, many=True).data)


class ExpenseListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ExpenseSerializer

    def get_queryset(self):
        return Expense.objects.filter(user=self.request.user).order_by("-expense_date", "-id")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ExpenseUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ExpenseSerializer

    def get_queryset(self):
        return Expense.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        instance.delete()


def detect_category_from_merchant(merchant: str) -> str:
    text = (merchant or "").lower().strip()

    groceries_keywords = [
        "general store", "genral store", "stationary", "stationery", "stationers",
        "juice", "blinkit", "zepto", "instamart", "bigbasket", "grocery",
        "grocers", "mart", "kirana", "provision", "milk", "dairy",
        "departmental", "supermarket", "hypermarket", "food bazaar", "nature's basket",
    ]

    food_keywords = [
        "canteen", "food", "dhaba", "chaap", "chaat", "zomato", "swiggy",
        "mcdonald", "dominos", "pizza hut", "burger king", "kfc", "haldiram",
        "bikaner", "restaurant", "restro", "cafe", "bakery", "tea", "chai",
        "coffee", "eat", "eats", "hotel", "mess",
        "annapurna", "anapurna", "shake", "smoothie", "ice cream", "dessert",
    ]

    shopping_keywords = [
        "myntra", "ajio", "savanna", "amazon", "flipkart", "nykaa", "meesho",
        "shopping", "lifestyle", "pantaloons", "zara",
        "h&m", "hm", "westside", "ecom", "mall", "clothing", "footwear", "apparel",
    ]

    for kw in groceries_keywords:
        if kw in text:
            return "Groceries"

    for kw in food_keywords:
        if kw in text:
            return "Food"

    for kw in shopping_keywords:
        if kw in text:
            return "Shopping"

    return "Other"


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def expense_ocr(request):
    file = request.FILES.get("image") or request.FILES.get("file")
    if not file:
        return Response({"error": "No image/file uploaded"}, status=400)

    try:
        from .ocr_tesseract import configure_tesseract
        configure_tesseract()

        from .bill_ocr import analyze_bill_upload
        result = analyze_bill_upload(file)

    except ValueError as e:
        return Response({"error": str(e)}, status=400)

    except Exception as e:
        logger.exception("expense_ocr failed")

        hint = (
            "OCR failed. Install Tesseract (brew install tesseract), add TESSERACT_CMD if needed, "
            "and pip install -r requirements.txt (pdfplumber, pytesseract, Pillow, opencv-python-headless)."
        )

        detail = str(e) if settings.DEBUG else None

        body = {"error": hint}
        if detail:
            body["detail"] = detail

        return Response(body, status=500)

    if result.get("type") == "bank_statement":
        transactions = result.get("transactions", [])

        preview = []
        total_spent = 0.0

        for txn in transactions:
            txn_type = (txn.get("type") or "debit").lower()
            narr = (txn.get("narration") or "").strip()
            desc = (txn.get("description") or "").strip()
            raw_line = (txn.get("raw") or "").strip()

            merchant_text = " ".join(x for x in [narr, desc, raw_line] if x).strip().lower()
            merchant_text = merchant_text.replace("/", " ").replace("-", " ")
            merchant_text = " ".join(merchant_text.split())[:500]

            amount = txn.get("amount")
            try:
                amt_num = float(amount or 0)
            except (TypeError, ValueError):
                amt_num = 0.0

            raw_date = txn.get("date")
            try:
                parsed_date = datetime.strptime(raw_date, "%d-%m-%Y").date()
            except Exception:
                parsed_date = raw_date

            exists = Expense.objects.filter(
                user=request.user,
                amount=amt_num,
                expense_date=parsed_date,
            ).exists()

            if txn_type == "debit":
                total_spent += amt_num

            preview.append({
                "categoryKey": detect_category_from_merchant(merchant_text),
                "date": raw_date,
                "amount": amount,
                "merchant": merchant_text,
                "note": "Bank statement",
                "paymentMode": "OCR",
                "direction": "CREDIT" if txn_type == "credit" else "DEBIT",
                "source": "STATEMENT",
                "balance": txn.get("balance"),
                "alreadyExists": exists,
            })

        return Response({
            "type": "bank_statement",
            "transactionCount": len(preview),
            "totalSpent": round(total_spent, 2),
            "preview": preview,
            "rawText": (result.get("raw_text") or "")[:50000],
        })

    expense_date = result.get("expense_date")
    if hasattr(expense_date, "isoformat"):
        expense_date = expense_date.isoformat()

    preview = [
        {
            "categoryKey": result.get("category") or detect_category_from_merchant(result.get("merchant") or ""),
            "date": expense_date,
            "amount": result.get("amount"),
            "merchant": result.get("merchant") or "",
            "note": "Bill OCR",
            "paymentMode": "OCR",
            "source": "OCR",
            "direction": "DEBIT",
        }
    ]

    return Response({
        "type": "bill",
        "rawText": result.get("raw_text") or "",
        "preview": preview,
    })