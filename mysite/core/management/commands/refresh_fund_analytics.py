import json
import math
import os
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import FundAnalyticsSnapshot, FundNavDaily, BenchmarkIndexDaily


EQUITY_CATALOG = os.path.join(
    settings.BASE_DIR, "core", "data", "amfi", "equity_catalog.json"
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

    if not os.path.exists(EQUITY_CATALOG):
        return lookup

    with open(EQUITY_CATALOG, "r", encoding="utf-8") as f:
        data = json.load(f)

    equity_block = data.get("equity", {})

    if isinstance(equity_block, dict):
        for fund_type, category_map in equity_block.items():  # active / passive
            if not isinstance(category_map, dict):
                continue

            for category_key, items in category_map.items():
                if not isinstance(items, list):
                    continue

                for row in items:
                    code = str(row.get("scheme_code") or row.get("code") or "").strip()
                    if not code:
                        continue

                    lookup[code] = {
                        "scheme_name": row.get("label") or row.get("scheme_name") or row.get("name") or "",
                        "amc": row.get("amc") or "",
                        "category_key": str(category_key).strip().lower(),
                        "fund_type": str(fund_type).strip().lower(),
                        "expense_ratio": float(row.get("expense_ratio") or 0),
                    }

    return lookup


def get_nav_series(scheme_code):
    rows = list(
        FundNavDaily.objects
        .filter(scheme_code=scheme_code)
        .order_by("date")
        .values("date", "nav")
    )
    return [(r["date"], float(r["nav"])) for r in rows]


def get_benchmark_series(code):
    rows = list(
        BenchmarkIndexDaily.objects
        .filter(index__code=code)
        .order_by("date")
        .values("date", "close")
    )
    return [(r["date"], float(r["close"])) for r in rows]


def latest_common_date(nav_dates, bench_dates):
    common = sorted(set(nav_dates) & set(bench_dates))
    return common[-1] if common else None


def value_on_or_before(series, target_date):
    valid = [v for d, v in series if d <= target_date]
    return valid[-1] if valid else None


def compute_return(series, as_of, days_back):
    current = value_on_or_before(series, as_of)
    previous = value_on_or_before(series, as_of - timedelta(days=days_back))
    if current is None or previous in (None, 0):
        return 0.0
    return (current / previous) - 1.0


def get_daily_returns(series, start_date, end_date):
    filtered = [(d, v) for d, v in series if start_date <= d <= end_date]
    vals = []
    for i in range(1, len(filtered)):
        prev = filtered[i - 1][1]
        curr = filtered[i][1]
        if prev and prev != 0:
            vals.append((curr / prev) - 1.0)
    return vals


def annualized_volatility(daily_returns):
    if len(daily_returns) < 2:
        return 0.0
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((x - mean) ** 2 for x in daily_returns) / len(daily_returns)
    return math.sqrt(variance) * math.sqrt(252)


def max_drawdown(series, start_date, end_date):
    filtered = [v for d, v in series if start_date <= d <= end_date]
    if not filtered:
        return 0.0

    peak = filtered[0]
    worst = 0.0
    for x in filtered:
        peak = max(peak, x)
        dd = (x / peak) - 1.0 if peak else 0.0
        worst = min(worst, dd)
    return worst


def compute_alpha_1y(fund_series, bench_series, as_of):
    fund_ret = compute_return(fund_series, as_of, 365)
    bench_ret = compute_return(bench_series, as_of, 365)
    return fund_ret - bench_ret


def compute_consistency_score(return_1y, return_3y, return_5y):
    positive_count = sum(1 for x in [return_1y, return_3y, return_5y] if x > 0)
    return positive_count / 3.0


def compute_stability_score(volatility_1y, max_drawdown_1y):
    vol_penalty = min(max(volatility_1y, 0), 1.0)
    dd_penalty = min(abs(max_drawdown_1y), 1.0)
    score = 1.0 - ((vol_penalty * 0.6) + (dd_penalty * 0.4))
    return max(score, 0.0)


class Command(BaseCommand):
    help = "Build FundAnalyticsSnapshot from raw NAV + benchmark history"

    def handle(self, *args, **options):
        scheme_lookup = load_scheme_lookup()
        if not scheme_lookup:
            self.stdout.write(self.style.ERROR("No scheme lookup found from equity catalog"))
            return

        benchmark_cache = {}
        ok = 0
        skipped = 0

        for scheme_code, meta in scheme_lookup.items():
            category_key = meta.get("category_key", "")
            benchmark_code = CATEGORY_TO_BENCHMARK.get(category_key)

            if not benchmark_code:
                skipped += 1
                continue

            nav_series = get_nav_series(scheme_code)
            if not nav_series:
                skipped += 1
                continue

            if benchmark_code not in benchmark_cache:
                benchmark_cache[benchmark_code] = get_benchmark_series(benchmark_code)

            bench_series = benchmark_cache[benchmark_code]
            if not bench_series:
                skipped += 1
                continue

            nav_dates = [d for d, _ in nav_series]
            bench_dates = [d for d, _ in bench_series]
            as_of = latest_common_date(nav_dates, bench_dates)
            if not as_of:
                skipped += 1
                continue

            latest_nav = value_on_or_before(nav_series, as_of) or 0

            return_1y = compute_return(nav_series, as_of, 365)
            return_3y = compute_return(nav_series, as_of, 365 * 3)
            return_5y = compute_return(nav_series, as_of, 365 * 5)

            one_year_start = as_of - timedelta(days=365)
            daily_returns = get_daily_returns(nav_series, one_year_start, as_of)
            volatility_1y = annualized_volatility(daily_returns)
            max_drawdown_1y = max_drawdown(nav_series, one_year_start, as_of)
            alpha_1y = compute_alpha_1y(nav_series, bench_series, as_of)

            consistency_score = compute_consistency_score(return_1y, return_3y, return_5y)
            stability_score = compute_stability_score(volatility_1y, max_drawdown_1y)

            FundAnalyticsSnapshot.objects.update_or_create(
                scheme_code=str(scheme_code),
                as_of=as_of,
                defaults={
                    "scheme_name": meta.get("scheme_name", ""),
                    "amc": meta.get("amc", ""),
                    "category_key": category_key,
                    "fund_type": meta.get("fund_type", ""),
                    "benchmark_code": benchmark_code,
                    "latest_nav": latest_nav,
                    "return_1y": return_1y,
                    "return_3y": return_3y,
                    "return_5y": return_5y,
                    "volatility_1y": volatility_1y,
                    "max_drawdown_1y": max_drawdown_1y,
                    "alpha_1y": alpha_1y,
                    "consistency_score": consistency_score,
                    "stability_score": stability_score,
                    "expense_ratio": meta.get("expense_ratio", 0),
                },
            )
            ok += 1
            self.stdout.write(f"[OK] {scheme_code} {meta.get('scheme_name', '')[:60]} as_of={as_of}")

        self.stdout.write(self.style.SUCCESS(f"Done. OK={ok}, SKIP={skipped}"))