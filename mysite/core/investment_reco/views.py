from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.models import InvestmentRecommendation
from core.investment_reco.engine import build_user_investment_recommendations
from core.investment_reco.serializers import InvestmentRecommendationSerializer
from core.investment_reco.selectors import get_recommendation_as_of


# =========================================
# GET → FETCH LATEST RECOMMENDATIONS
# =========================================
class InvestmentRecommendationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        latest_as_of = get_recommendation_as_of()

        # ❌ No data case
        if not latest_as_of:
            return Response([], status=200)

        qs = (
            InvestmentRecommendation.objects
            .filter(
                user=request.user,
                as_of=latest_as_of   # ✅ IMPORTANT FIX
            )
            .order_by("-score", "scheme_name")
        )

        serializer = InvestmentRecommendationSerializer(qs, many=True)
        return Response(serializer.data, status=200)


# =========================================
# POST → REBUILD + RETURN LATEST
# =========================================
class InvestmentRecommendationRebuildAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 🔥 Step 1: rebuild recommendations
        build_user_investment_recommendations(request.user)

        # 🔥 Step 2: fetch latest snapshot
        latest_as_of = get_recommendation_as_of()

        if not latest_as_of:
            return Response([], status=200)

        qs = (
            InvestmentRecommendation.objects
            .filter(
                user=request.user,
                as_of=latest_as_of   # ✅ IMPORTANT FIX
            )
            .order_by("-score", "scheme_name")
        )

        serializer = InvestmentRecommendationSerializer(qs, many=True)
        return Response(serializer.data, status=200)