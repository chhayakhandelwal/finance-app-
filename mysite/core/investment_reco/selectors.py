import csv
import json
import os
from datetime import datetime
from types import SimpleNamespace

from django.conf import settings

from core.models import FundAnalyticsSnapshot


EQUITY_CATALOG_PATH = os.path.join(
    settings.BASE_DIR, "core", "data", "amfi", "equity_catalog.json"
)

DEBT_SUMMARY_CSV_PATH = os.path.join(
    settings.BASE_DIR, "core", "data", "fixed_assets", "debt_fund_summary.csv"
)


def _safe_float(v, default=0.0):
    try:
        if v in ("", None, "-", "null", "None"):
            return default
        return float(v)
    except Exception:
        return default


def _parse_iso_date(v):
    try:
        return datetime.strptime(str(v), "%Y-%m-%d").date()
    except Exception:
        return None


def _collect_scheme_codes_from_json(node, out_set):
    if isinstance(node, dict):
        if "scheme_code" in node:
            try:
                out_set.add(int(str(node.get("scheme_code")).strip()))
            except Exception:
                pass

        for value in node.values():
            _collect_scheme_codes_from_json(value, out_set)

    elif isinstance(node, list):
        for item in node:
            _collect_scheme_codes_from_json(item, out_set)


def get_equity_catalog_scheme_codes():
    codes = set()

    if not os.path.exists(EQUITY_CATALOG_PATH):
        return codes

    with open(EQUITY_CATALOG_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    _collect_scheme_codes_from_json(payload, codes)
    return codes


def get_latest_analytics_as_of():
    return (
        FundAnalyticsSnapshot.objects
        .order_by("-as_of")
        .values_list("as_of", flat=True)
        .first()
    )


def get_latest_analytics_queryset():
    latest_as_of = get_latest_analytics_as_of()
    if not latest_as_of:
        return FundAnalyticsSnapshot.objects.none()

    equity_codes = get_equity_catalog_scheme_codes()
    qs = FundAnalyticsSnapshot.objects.filter(as_of=latest_as_of)

    if equity_codes:
        qs = qs.filter(scheme_code__in=equity_codes)

    return qs


def _build_debt_candidate_from_csv_row(row):
    category_key = (row.get("category") or "").strip().lower()
    scheme_code = int(str(row.get("scheme_code")).strip())
    cagr_1y = _safe_float(row.get("cagr_1Y")) / 100.0
    cagr_3y = _safe_float(row.get("cagr_3Y")) / 100.0
    latest_nav = _safe_float(row.get("latest_nav"))
    as_of = _parse_iso_date(row.get("as_of"))

    positive_years = 0
    for value in (cagr_1y, cagr_3y):
        if value > 0:
            positive_years += 1

    consistency_score = positive_years / 2.0 if positive_years else 0.0

    stability_score = 0.85
    if cagr_1y > 0 and cagr_3y > 0:
        stability_score = 0.95
    elif cagr_1y > 0 or cagr_3y > 0:
        stability_score = 0.88

    return SimpleNamespace(
        scheme_code=scheme_code,
        scheme_name=(row.get("label") or "").strip(),
        amc=(row.get("amc") or "").strip().upper(),
        category_key=category_key,
        fund_type="debt",
        benchmark_code="DEBT",
        latest_nav=latest_nav,
        as_of=as_of,
        return_1y=cagr_1y,
        return_3y=cagr_3y,
        consistency_score=consistency_score,
        stability_score=stability_score,
        alpha_1y=0.0,
        volatility_1y=0.02,
        max_drawdown_1y=0.01,
        expense_ratio=0.0,
    )


def get_latest_debt_candidates():
    if not os.path.exists(DEBT_SUMMARY_CSV_PATH):
        return []

    rows = []

    with open(DEBT_SUMMARY_CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            category_key = (row.get("category") or "").strip().lower()
            if category_key not in {"debt_govt", "debt_corp"}:
                continue

            scheme_code = row.get("scheme_code")
            if not scheme_code:
                continue

            try:
                rows.append(_build_debt_candidate_from_csv_row(row))
            except Exception:
                continue

    return rows


def get_recommendation_candidates():
    equity_candidates = list(get_latest_analytics_queryset())
    debt_candidates = list(get_latest_debt_candidates())
    return equity_candidates + debt_candidates


def get_recommendation_as_of():
    dates = []

    equity_as_of = get_latest_analytics_as_of()
    if equity_as_of:
        dates.append(equity_as_of)

    for debt in get_latest_debt_candidates():
        if getattr(debt, "as_of", None):
            dates.append(debt.as_of)

    if not dates:
        return None

    return max(dates)