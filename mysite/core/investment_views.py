# core/investment_views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes

from .serializers import InvestmentRecommendRequestSerializer
from .investment_reco.engine import build_user_investment_recommendations


class InvestmentRecommendAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = InvestmentRecommendRequestSerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {"message": "Invalid input", "errors": ser.errors},
                status=400,
            )

        data = ser.validated_data

        result = build_user_investment_recommendations(
            risk=data["risk"],
            horizon=data["horizon"],
            amount=data["amount"],
            type_=data["type"],
            goal=data["goal"],
            mode=data["mode"],
        )

        return Response(result, status=200)


# ✅ FIX: Stable APIs (so frontend stops 404)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def portfolio_summary(request):
    """
    Frontend calls:
      GET /api/investment/portfolio/summary/

    Return keys that your InvestmentHome can safely consume.
    Keep it as stub now; later you can compute from DB.
    """
    return Response(
        {
            "invested": 0,
            "value": 0,
            "pnl": 0,
            "pnlPct": 0,
            "holdings": [],
        },
        status=200,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def investment_transactions(request):
    """
    Frontend calls:
      GET /api/investment/transactions/

    Stub for now; later return real transactions.
    """
    return Response([], status=200)