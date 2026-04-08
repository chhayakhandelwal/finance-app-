from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import OuterRef, Subquery
from core.models import FundPrediction

class FundPredictionsAPIView(APIView):
    permission_classes = []

    def get(self, request):

        print("🔥 NEW API HIT")

        category = (request.query_params.get("category") or "").strip().lower()
        limit = int(request.query_params.get("limit", 20))

        base_qs = FundPrediction.objects.all()

        if category:
            base_qs = base_qs.filter(category_key=category)

        # ✅ latest per scheme (IMPORTANT FIX)
        latest_subquery = (
            FundPrediction.objects
            .filter(scheme_code=OuterRef("scheme_code"))
            .order_by("-as_of")
            .values("as_of")[:1]
        )

        qs = base_qs.filter(as_of=Subquery(latest_subquery))

        qs = qs.order_by("-prob_outperform", "-pred_nextweek_return")[:limit]

        data = []

        for r in qs:
            recommendation = "AVOID"

            if r.prob_outperform >= 0.70 and r.pred_nextweek_return > 0:
                recommendation = "BUY"
            elif r.prob_outperform >= 0.50:
                recommendation = "HOLD"

            data.append({
                "scheme_code": r.scheme_code,
                "scheme_name": r.scheme_name,
                "as_of": r.as_of,
                "pred_for_date": r.pred_for_date,
                "pred_nextweek_return": r.pred_nextweek_return,
                "prob_outperform": r.prob_outperform,
                "recommendation": recommendation,
            })

        return Response(data)