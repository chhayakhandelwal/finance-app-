import os
import json
import joblib
import numpy as np
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import FundPrediction, FundNavDaily, BenchmarkIndexDaily


ART_DIR = os.path.join(settings.BASE_DIR, "core", "ml_artifacts")
REG_PATH = os.path.join(ART_DIR, "xgb_nextweek_return_reg.joblib")
CLF_PATH = os.path.join(ART_DIR, "xgb_outperform_clf.joblib")

EQUITY_CATALOG = os.path.join(
    settings.BASE_DIR, "core", "data", "amfi", "equity_catalog.json"
)
DEBT_CATALOG = os.path.join(
    settings.BASE_DIR, "core", "data", "fixed_assets", "debt_catalog.json"
)

CATEGORY_TO_BENCHMARK = {
    "largecap": "NIFTY50",
    "midcap": "NIFTY_MIDCAP_150",
    "smallcap": "NIFTY_SMALLCAP_250",
    "multicap": "NIFTY500",
    "flexicap": "NIFTY500",
    "balanced_advantage": "NIFTY50",
    "multi_asset": "NIFTY50",
    "hybrid_conservative": "NIFTY50",
    "hybrid_aggressive": "NIFTY50",
    "nifty50": "NIFTY50",
    "bse": "NIFTY500",
    "midcap150": "NIFTY_MIDCAP_150",
    "smallcap250": "NIFTY_SMALLCAP_250",
}


def load_scheme_lookup():
    lookup = {}

    def add_row(code, label="", amc="", category_key=""):
        code = str(code or "").strip()
        if not code:
            return

        lookup[code] = {
            "scheme_name": label or "",
            "amc": amc or "",
            "category_key": str(category_key or "").strip().lower(),
        }

    if os.path.exists(EQUITY_CATALOG):
        with open(EQUITY_CATALOG, "r", encoding="utf-8") as f:
            data = json.load(f)

        equity_block = data.get("equity", {})
        for sub_type in equity_block.values():
            if not isinstance(sub_type, dict):
                continue

            for category_key, items in sub_type.items():
                if not isinstance(items, list):
                    continue

                for row in items:
                    add_row(
                        row.get("scheme_code"),
                        row.get("label"),
                        row.get("amc"),
                        category_key,
                    )

    return lookup


def _load_bundle(path: str):
    obj = joblib.load(path)

    if isinstance(obj, dict):
        return obj["model"], obj.get("features")

    return obj, None


def pct_return(curr, prev):
    if not curr or not prev:
        return None
    return (curr / prev) - 1.0


def stddev(values):
    if len(values) < 2:
        return None
    return float(np.std(values))


def get_nav_map(scheme_code):
    rows = (
        FundNavDaily.objects
        .filter(scheme_code=scheme_code)
        .order_by("date")
        .values("date", "nav")
    )
    return {r["date"]: float(r["nav"]) for r in rows}


def get_benchmark_map(code):
    rows = (
        BenchmarkIndexDaily.objects
        .filter(index__code=code)
        .order_by("date")
        .values("date", "close")
    )
    return {r["date"]: float(r["close"]) for r in rows}


def previous_value(dates, values, target, days):
    wanted = target - timedelta(days=days)
    valid = [d for d in dates if d <= wanted]
    return values.get(valid[-1]) if valid else None


class Command(BaseCommand):
    help = "Predict next-week return"

    def handle(self, *args, **opts):

        reg, feats = _load_bundle(REG_PATH)
        clf, _ = _load_bundle(CLF_PATH)

        scheme_lookup = load_scheme_lookup()
        benchmark_cache = {}

        rows = []

        for scheme_code in scheme_lookup.keys():
            meta = scheme_lookup[scheme_code]

            category = meta["category_key"]
            benchmark = CATEGORY_TO_BENCHMARK.get(category)

            if not benchmark:
                continue

            nav_map = get_nav_map(scheme_code)
            if not nav_map:
                continue

            if benchmark not in benchmark_cache:
                benchmark_cache[benchmark] = get_benchmark_map(benchmark)

            bench_map = benchmark_cache[benchmark]

            nav_dates = sorted(nav_map.keys())
            bench_dates = sorted(bench_map.keys())

            as_of = nav_dates[-1]
            nav_now = nav_map[as_of]

            # ✅ FIXED skip logic
            if FundPrediction.objects.filter(
                scheme_code=scheme_code,
                as_of=as_of
            ).exists():
                continue

            bench_now = bench_map.get(bench_dates[-1])

            nav_1w = previous_value(nav_dates, nav_map, as_of, 7)
            nav_1m = previous_value(nav_dates, nav_map, as_of, 30)
            bench_1m = previous_value(bench_dates, bench_map, as_of, 30)

            ret_1w = pct_return(nav_now, nav_1w) or 0
            ret_1m = pct_return(nav_now, nav_1m) or 0
            bench_ret = pct_return(bench_now, bench_1m) or 0

            alpha = ret_1m - bench_ret

            vol = stddev([
                pct_return(nav_map[d], nav_map.get(d)) or 0
                for d in nav_dates[-30:]
            ]) or 0

            rows.append({
                "scheme_code": scheme_code,
                "meta": meta,
                "as_of": as_of,
                "features": [ret_1w, ret_1m, vol, alpha]
            })

        if not rows:
            print("No new predictions")
            return

        X = np.array([r["features"] for r in rows])

        pred_ret = reg.predict(X)
        prob = clf.predict_proba(X)[:, 1]

        for i, r in enumerate(rows):
            recommendation = "BUY" if pred_ret[i] > 0 else "AVOID"

            FundPrediction.objects.update_or_create(
                scheme_code=r["scheme_code"],
                as_of=r["as_of"],
                defaults={
                    "scheme_name": r["meta"]["scheme_name"],
                    "amc": r["meta"]["amc"],
                    "category_key": r["meta"]["category_key"],
                    "benchmark_code": CATEGORY_TO_BENCHMARK.get(r["meta"]["category_key"]),
                    "pred_for_date": r["as_of"] + timedelta(days=7),
                    "pred_nextweek_return": float(pred_ret[i]),
                    "prob_outperform": float(prob[i]),
                    # optional:
                    # "recommendation": recommendation,
                }
            )

        print("✅ Predictions updated")