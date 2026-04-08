# core/mf_views.py
print("MF_VIEWS LIVE VERSION LOADED")

import csv
import os

from django.conf import settings
from django.db.models import Max
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import FundPrediction


CSV_PATH = os.path.join(
    settings.BASE_DIR,
    "core",
    "data",
    "mf_out",
    "csv",
    "mf_cagr_summary.csv",
)


def _to_none_if_blank(v):
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.lower() in ("nan", "none", "null", "-"):
        return None
    return v


def _as_float_or_none(v):
    v = _to_none_if_blank(v)
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


class MF_CagrSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bucket = (request.query_params.get("bucket") or "").strip().lower()
        category = (request.query_params.get("category") or "").strip().lower()
        amc = (request.query_params.get("amc") or "").strip().lower()

        if not os.path.exists(CSV_PATH):
            return Response(
                {
                    "detail": "mf_cagr_summary.csv not found.",
                    "expected_path": CSV_PATH,
                },
                status=404,
            )

        rows = []

        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for r in reader:
                r_bucket = (r.get("bucket") or "").strip().lower()
                r_cat = (r.get("category") or "").strip().lower()
                r_amc = (r.get("amc") or "").strip().lower()

                if bucket and r_bucket != bucket:
                    continue
                if category and r_cat != category:
                    continue
                if amc and r_amc != amc:
                    continue

                scheme_code = _as_float_or_none(r.get("scheme_code"))
                if scheme_code is None:
                    continue

                out = {
                    "bucket": r_bucket,
                    "category": r_cat,
                    "amc": r_amc,
                    "label": _to_none_if_blank(r.get("label")),
                    "scheme_code": int(scheme_code),
                    "as_of": _to_none_if_blank(r.get("as_of")),
                    "latest_nav": _as_float_or_none(r.get("latest_nav")),
                    "history_start_date": _to_none_if_blank(r.get("history_start_date")),
                    "cagr_1M": _as_float_or_none(r.get("cagr_1M")),
                    "cagr_6M": _as_float_or_none(r.get("cagr_6M")),
                    "cagr_1Y": _as_float_or_none(r.get("cagr_1Y")),
                    "cagr_3Y": _as_float_or_none(r.get("cagr_3Y")),
                    "cagr_5Y": _as_float_or_none(r.get("cagr_5Y")),
                    "cagr_6Y": _as_float_or_none(r.get("cagr_6Y")),
                    "cagr_8Y": _as_float_or_none(r.get("cagr_8Y")),
                    "cagr_10Y": _as_float_or_none(r.get("cagr_10Y")),
                    "cagr_SI": _as_float_or_none(r.get("cagr_SI")),
                    "synced_at": _to_none_if_blank(r.get("synced_at")),
                }

                rows.append(out)

        return Response(rows, status=200)


class FundPredictionsAPIView(APIView):
    permission_classes = []

    def get(self, request):
        category = (request.query_params.get("category") or "").strip().lower()

        qs = FundPrediction.objects.all()

        if category:
            qs = qs.filter(category_key=category)

        latest_date = qs.aggregate(Max("as_of"))["as_of__max"]

        if not latest_date:
            return Response([])

        qs = qs.filter(as_of=latest_date).order_by("-prob_outperform")

        data = []

        for r in qs:
            recommendation = "AVOID"

            if r.prob_outperform >= 0.70 and r.pred_nextweek_return > 0:
                recommendation = "BUY"
            elif r.prob_outperform >= 0.50:
                recommendation = "HOLD"

            data.append(
                {
                    "scheme_code": r.scheme_code,
                    "scheme_name": r.scheme_name,
                    "as_of": r.as_of,
                    "pred_for_date": r.pred_for_date,
                    "pred_nextweek_return": r.pred_nextweek_return,
                    "prob_outperform": r.prob_outperform,
                    "recommendation": recommendation,
                }
            )

        return Response(data)