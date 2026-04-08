# core/views.py

from threading import Thread

from django.db import transaction
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Recommendation, InvestmentRecommendation
from .serializers import RecommendationSerializer, ExpenseSerializer
from .investment_reco.serializers import InvestmentRecommendationSerializer
from .investment_reco.engine import build_user_investment_recommendations
from .recommendation_engine import generate_monthly_expense_recommendations


# =========================================================
# ASYNC HELPERS
# =========================================================
def _run_expense_recommendations(user, any_date_in_month=None):
    try:
        if any_date_in_month:
            generate_monthly_expense_recommendations(
                user,
                any_date_in_month=any_date_in_month,
            )
        else:
            generate_monthly_expense_recommendations(user)
    except Exception as e:
        print("EXPENSE RECOMMENDATION ERROR:", str(e))


def _trigger_expense_recommendations_async(user, any_date_in_month=None):
    def _start():
        Thread(
            target=_run_expense_recommendations,
            args=(user, any_date_in_month),
            daemon=True,
        ).start()

    transaction.on_commit(_start)


# =========================================================
# EXPENSE RECOMMENDATIONS
# =========================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def recommendations_list(request):
    """
    Returns only selected month recommendations.
    Frontend call:
        /api/recommendations/?month_key=YYYY-MM

    If month_key not provided, defaults to current month.
    """
    month_key = request.query_params.get("month_key")
    if not month_key:
        d = timezone.localdate()
        month_key = f"{d.year:04d}-{d.month:02d}"

    qs = (
        Recommendation.objects.filter(
            user=request.user,
            is_active=True,
            month_key=month_key,
        )
        .exclude(category="email")
        .order_by("-created_at")[:200]
    )

    return Response(
        RecommendationSerializer(qs, many=True).data,
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_expense(request):
    """
    Creates expense for logged-in user
    and triggers expense recommendations asynchronously.
    """
    serializer = ExpenseSerializer(
        data=request.data,
        context={"request": request},
    )

    if serializer.is_valid():
        expense = serializer.save(user=request.user)

        # Expense month ke basis par recommendations regenerate karo
        expense_date = getattr(expense, "expense_date", None) or timezone.localdate()

        _trigger_expense_recommendations_async(
            request.user,
            any_date_in_month=expense_date,
        )

        return Response(
            {
                "message": "Expense created successfully. Recommendations will update shortly.",
                "expense": ExpenseSerializer(expense).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# =========================================================
# INVESTMENT RECOMMENDATIONS
# =========================================================
class BuildInvestmentRecommendationsView(APIView):
    """
    POST /api/investment/recommendations/build/
    Builds fresh investment recommendations for logged-in user.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            recs = build_user_investment_recommendations(request.user)

            return Response(
                {
                    "count": len(recs),
                    "message": "Investment recommendations generated successfully",
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {
                    "error": str(e),
                    "message": "Failed to generate investment recommendations",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LatestInvestmentRecommendationsView(generics.ListAPIView):
    """
    GET /api/investment/recommendations/latest/
    Returns latest recommendation set for logged-in user.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InvestmentRecommendationSerializer

    def get_queryset(self):
        latest_as_of = (
            InvestmentRecommendation.objects
            .filter(user=self.request.user)
            .order_by("-as_of")
            .values_list("as_of", flat=True)
            .first()
        )

        if not latest_as_of:
            return InvestmentRecommendation.objects.none()

        return (
            InvestmentRecommendation.objects
            .filter(user=self.request.user, as_of=latest_as_of)
            .order_by("-score", "scheme_name")
        )