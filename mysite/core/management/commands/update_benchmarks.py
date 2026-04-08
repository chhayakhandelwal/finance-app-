# core/management/commands/update_benchmarks.py

import csv
import io
import json
import os
from datetime import date, timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from core.models import BenchmarkIndex, BenchmarkIndexDaily


SOURCES_PATH = os.path.join(settings.BASE_DIR, "core", "data", "benchmarks", "index_sources.json")
ARCHIVES_BASE = "https://archives.nseindia.com/content/indices"


def _safe_decimal(x):
    try:
        return Decimal(str(x).strip())
    except Exception:
        return None


def _download_archives_csv(d: date) -> str | None:
    """
    Official NSE archives file:
    https://archives.nseindia.com/content/indices/ind_close_all_DDMMYYYY.csv
    """
    ddmmyyyy = d.strftime("%d%m%Y")
    url = f"{ARCHIVES_BASE}/ind_close_all_{ddmmyyyy}.csv"
    try:
        r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200 or not r.text.strip():
            return None
        return r.text
    except Exception:
        return None


def _parse_indices_from_csv_text(csv_text: str) -> dict:
    """
    Returns: { index_name_lower: close_decimal }
    Works even if NSE slightly changes column names.
    """
    text = csv_text.lstrip("\ufeff")  # handle BOM
    f = io.StringIO(text)

    reader = csv.DictReader(f)
    out = {}

    # Common possible column names in ind_close_all
    name_keys = ["Index Name", "Index", "IndexName", "index"]
    close_keys = ["Closing Index Value", "Close", "Last", "Closing", "close", "last"]

    for row in reader:
        # find name
        name = None
        for k in name_keys:
            if k in row and row[k]:
                name = str(row[k]).strip()
                break

        if not name:
            continue

        # find close
        close = None
        for k in close_keys:
            if k in row and row[k]:
                close = _safe_decimal(row[k])
                if close is not None:
                    break

        if close is None:
            continue

        out[name.strip().lower()] = close

    return out


class Command(BaseCommand):
    help = "Fetch daily benchmark index closes (NSE Archives) and store in DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--backfill_days",
            type=int,
            default=0,
            help="Backfill last N calendar days (weekends will be skipped automatically by missing file).",
        )

    def handle(self, *args, **opts):
        if not os.path.exists(SOURCES_PATH):
            self.stdout.write(self.style.ERROR(f"Missing sources file: {SOURCES_PATH}"))
            return

        with open(SOURCES_PATH, "r", encoding="utf-8") as f:
            sources = json.load(f)

        backfill_days = int(opts.get("backfill_days") or 0)

        # Build date list (oldest -> newest)
        if backfill_days > 0:
            start = date.today() - timedelta(days=backfill_days)
            dates = [start + timedelta(days=i) for i in range((date.today() - start).days + 1)]
        else:
            dates = [date.today()]

        ok = 0
        skip = 0

        for d in dates:
            csv_text = _download_archives_csv(d)
            if not csv_text:
                # holiday/weekend => no file, skip date
                continue

            idx_map = _parse_indices_from_csv_text(csv_text)

            for code, meta in sources.items():
                provider = (meta.get("provider") or "").lower()
                symbol = (meta.get("symbol") or code).strip()
                symbol_key = symbol.lower()

                if provider != "nse_archives":
                    continue

                idx, _ = BenchmarkIndex.objects.get_or_create(
                    code=code, defaults={"name": symbol}
                )

                close_val = idx_map.get(symbol_key)

                if close_val is None:
                    # symbol not present in that day's file
                    skip += 1
                    continue

                BenchmarkIndexDaily.objects.update_or_create(
                    index=idx,
                    date=d,
                    defaults={"close": close_val},
                )
                ok += 1

        self.stdout.write(self.style.SUCCESS(f"Done. OK={ok}, SKIP={skip}"))