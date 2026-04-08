import json
import os
import math
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    FundNavDaily,
    BenchmarkIndex,
    BenchmarkIndexDaily,
    FundMLSample,
)

CATEGORY_TO_BENCH_PATH = os.path.join(
    settings.BASE_DIR, "core", "data", "benchmarks", "fund_to_benchmark.json"
)

SCHEME_TO_CATEGORY_PATH = os.path.join(
    settings.BASE_DIR, "core", "data", "benchmarks", "scheme_to_category.json"
)


def _pct_return(v_now, v_then):
    if v_now is None or v_then is None:
        return None
    v_now = float(v_now)
    v_then = float(v_then)
    if v_then == 0:
        return None
    return (v_now / v_then) - 1.0


def _stddev(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(var)


class Command(BaseCommand):
    help = "Build ML samples by joining fund NAV series with benchmark closes."

    def add_arguments(self, parser):
        parser.add_argument("--limit_funds", type=int, default=200)
        parser.add_argument("--lookback_days", type=int, default=730)

    def handle(self, *args, **opts):
        if not os.path.exists(CATEGORY_TO_BENCH_PATH):
            raise SystemExit(f"Missing {CATEGORY_TO_BENCH_PATH}")
        if not os.path.exists(SCHEME_TO_CATEGORY_PATH):
            raise SystemExit(f"Missing {SCHEME_TO_CATEGORY_PATH}")

        with open(CATEGORY_TO_BENCH_PATH, "r", encoding="utf-8") as f:
            category_to_bench = json.load(f)

        with open(SCHEME_TO_CATEGORY_PATH, "r", encoding="utf-8") as f:
            scheme_to_category = json.load(f)

        # scheme codes from mapping file
        scheme_codes = []
        for k in scheme_to_category.keys():
            if str(k).isdigit():
                scheme_codes.append(int(k))
        scheme_codes = sorted(scheme_codes)[: opts["limit_funds"]]

        ok = 0
        skip = 0

        for sc in scheme_codes:
            category_key = (scheme_to_category.get(str(sc)) or "").strip().lower()
            if not category_key:
                self.stdout.write(self.style.WARNING(f"[SKIP] {sc}: missing category_key"))
                skip += 1
                continue

            benchmark_code = category_to_bench.get(category_key)
            if not benchmark_code:
                self.stdout.write(self.style.WARNING(f"[SKIP] {sc}: category {category_key} has no benchmark mapping"))
                skip += 1
                continue

            idx = BenchmarkIndex.objects.filter(code=benchmark_code).first()
            if not idx:
                self.stdout.write(self.style.WARNING(f"[SKIP] {sc}: benchmark {benchmark_code} not found in DB (run update_benchmarks)"))
                skip += 1
                continue

            nav_qs = FundNavDaily.objects.filter(scheme_code=sc).order_by("date")
            if not nav_qs.exists():
                self.stdout.write(self.style.WARNING(f"[SKIP] {sc}: no NAV data (run update_fund_navs)"))
                skip += 1
                continue

            nav_rows = list(nav_qs.values("date", "nav"))
            nav_map = {r["date"]: r["nav"] for r in nav_rows}

            last_date = nav_rows[-1]["date"]
            start_date = last_date - timedelta(days=opts["lookback_days"])

            # benchmark closes
            bench_rows = list(
                BenchmarkIndexDaily.objects.filter(
                    index=idx,
                    date__gte=start_date,
                    date__lte=last_date + timedelta(days=7),
                )
                .order_by("date")
                .values("date", "close")
            )
            bench_map = {r["date"]: r["close"] for r in bench_rows}

            dates = sorted([d for d in nav_map.keys() if d >= start_date])

            samples = []

            for d in dates:
                d_m7 = d - timedelta(days=7)
                d_m30 = d - timedelta(days=30)
                d_p7 = d + timedelta(days=7)

                # must have fund NAV at these points
                if d not in nav_map or d_m7 not in nav_map or d_m30 not in nav_map or d_p7 not in nav_map:
                    continue

                # must have benchmark closes at these points
                if d not in bench_map or d_m30 not in bench_map or d_p7 not in bench_map:
                    continue

                nav_d = nav_map[d]
                nav_m7 = nav_map[d_m7]
                nav_m30 = nav_map[d_m30]
                nav_p7 = nav_map[d_p7]

                bench_d = bench_map[d]
                bench_m30 = bench_map[d_m30]
                bench_p7 = bench_map[d_p7]

                ret_1w = _pct_return(nav_d, nav_m7)
                ret_1m = _pct_return(nav_d, nav_m30)

                bench_ret_1m = _pct_return(bench_d, bench_m30)
                alpha_1m = None if ret_1m is None or bench_ret_1m is None else (ret_1m - bench_ret_1m)

                # vol from last ~30 daily returns
                rets = []
                for i in range(1, 30):
                    da = d - timedelta(days=i)
                    db = d - timedelta(days=i + 1)
                    if da in nav_map and db in nav_map:
                        rets.append(_pct_return(nav_map[da], nav_map[db]))
                vol_1m = _stddev(rets)

                # targets
                y_fund_ret_1w = _pct_return(nav_p7, nav_d)
                y_bench_ret_1w = _pct_return(bench_p7, bench_d)
                if y_fund_ret_1w is None or y_bench_ret_1w is None:
                    continue

                y_outperform_1w = 1 if y_fund_ret_1w > y_bench_ret_1w else 0

                samples.append(
                    FundMLSample(
                        scheme_code=sc,
                        as_of=d,
                        category_key=category_key,
                        benchmark_code=benchmark_code,
                        nav=nav_d,
                        ret_1w=ret_1w,
                        ret_1m=ret_1m,
                        vol_1m=vol_1m,
                        bench_ret_1m=bench_ret_1m,
                        alpha_1m=alpha_1m,
                        y_fund_ret_1w=y_fund_ret_1w,
                        y_outperform_1w=y_outperform_1w,
                    )
                )

            if not samples:
                self.stdout.write(self.style.WARNING(f"[SKIP] {sc}: no samples built (date alignment issue)"))
                skip += 1
                continue

            with transaction.atomic():
                FundMLSample.objects.filter(scheme_code=sc, as_of__gte=start_date).delete()
                FundMLSample.objects.bulk_create(samples, batch_size=2000)

            ok += 1
            self.stdout.write(self.style.SUCCESS(f"[OK] {sc}: samples={len(samples)} bench={benchmark_code}"))

        self.stdout.write(self.style.SUCCESS(f"Done. OK={ok}, SKIP={skip}"))