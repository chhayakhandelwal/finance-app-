import json
import os
from datetime import datetime

import certifi
import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import FundNavDaily


EQUITY_CATALOG = os.path.join(
    settings.BASE_DIR, "core", "data", "amfi", "equity_catalog.json"
)

DEBT_CATALOG = os.path.join(
    settings.BASE_DIR, "core", "data", "fixed_assets", "debt_catalog.json"
)

MFAPI_URL = "https://api.mfapi.in/mf/{scheme_code}"


def load_all_scheme_codes():
    """
    Read all scheme_code values from:
      - core/data/amfi/equity_catalog.json
      - core/data/fixed_assets/debt_catalog.json

    Returns:
      sorted list[int]
    """
    codes = set()

    def walk(node):
        if isinstance(node, dict):
            if "scheme_code" in node:
                code = node.get("scheme_code")
                if code is not None and str(code).strip():
                    try:
                        codes.add(int(str(code).strip()))
                    except Exception:
                        pass

            for v in node.values():
                walk(v)

        elif isinstance(node, list):
            for item in node:
                walk(item)

    if os.path.exists(EQUITY_CATALOG):
        with open(EQUITY_CATALOG, "r", encoding="utf-8") as f:
            walk(json.load(f))

    if os.path.exists(DEBT_CATALOG):
        with open(DEBT_CATALOG, "r", encoding="utf-8") as f:
            walk(json.load(f))

    return sorted(codes)


def fetch_amfi_latest_map(stdout=None):
    """
    Fetch latest NAV/date from AMFI NAVAll.txt.

    Returns:
      {
        119018: {"nav": 1138.778, "date": date(2026, 3, 24)},
        ...
      }
    """
    urls = [
        "https://portal.amfiindia.com/spages/NAVAll.txt",
        "https://www.amfiindia.com/spages/NAVAll.txt",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/plain,text/html,*/*",
    }

    for base_url in urls:
        for i in range(3):
            try:
                if stdout:
                    stdout.write(f"📡 Fetching AMFI NAVAll (try {i+1}) → {base_url}")

                r = requests.get(
                    base_url,
                    headers=headers,
                    timeout=30,
                    allow_redirects=True,
                    verify=certifi.where(),
                )
                r.raise_for_status()

                text = r.text or ""
                if "Scheme Code;ISIN" not in text and "Scheme Code;ISIN Div" not in text:
                    raise Exception("Invalid AMFI NAVAll content")

                nav_map = {}

                for line in text.splitlines():
                    if ";" not in line:
                        continue

                    parts = [p.strip() for p in line.split(";")]
                    if len(parts) < 6:
                        continue

                    scheme_code = parts[0]
                    nav_str = parts[4]
                    date_str = parts[5]

                    if not scheme_code.isdigit():
                        continue

                    try:
                        nav_val = float(nav_str)
                        date_val = datetime.strptime(date_str, "%d-%b-%Y").date()
                    except Exception:
                        continue

                    nav_map[int(scheme_code)] = {
                        "nav": nav_val,
                        "date": date_val,
                    }

                if stdout:
                    stdout.write(f"✅ AMFI loaded for {len(nav_map)} schemes")

                return nav_map

            except Exception as e:
                if stdout:
                    stdout.write(f"❌ AMFI retry {i+1} failed for {base_url}: {e}")

    if stdout:
        stdout.write("⚠ AMFI NAVAll failed completely")
    return {}


def fetch_mfapi_history(scheme_code):
    """
    Returns:
      list[(date_obj, nav_float)] sorted ascending
    """
    url = MFAPI_URL.format(scheme_code=scheme_code)
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }

    for i in range(3):
        try:
            r = requests.get(
                url,
                headers=headers,
                timeout=30,
                verify=certifi.where(),
            )
            r.raise_for_status()

            payload = r.json()
            rows = []

            for item in payload.get("data", []):
                try:
                    d = datetime.strptime(item["date"], "%d-%m-%Y").date()
                    nav = float(item["nav"])
                    rows.append((d, nav))
                except Exception:
                    continue

            rows.sort(key=lambda x: x[0])
            return rows

        except Exception:
            continue

    return []


class Command(BaseCommand):
    help = "Download NAV history from MFAPI and merge latest AMFI NAV into FundNavDaily for all catalog funds."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Optional: limit number of scheme codes for testing",
        )

    def handle(self, *args, **kwargs):
        scheme_codes = load_all_scheme_codes()

        if not scheme_codes:
            self.stdout.write(self.style.ERROR("No scheme codes found in catalog files."))
            return

        limit = int(kwargs.get("limit") or 0)
        if limit > 0:
            scheme_codes = scheme_codes[:limit]

        self.stdout.write(f"Found {len(scheme_codes)} scheme codes.")

        amfi_map = fetch_amfi_latest_map(self.stdout)

        inserted = 0
        updated = 0
        failed = 0
        amfi_injected = 0

        for idx, scheme_code in enumerate(scheme_codes, start=1):
            history = fetch_mfapi_history(scheme_code)

            if not history:
                failed += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"[{idx}/{len(scheme_codes)}] {scheme_code} MFAPI history unavailable"
                    )
                )
            else:
                local_inserted = 0
                local_updated = 0

                for date_obj, nav in history:
                    _, created = FundNavDaily.objects.update_or_create(
                        scheme_code=scheme_code,
                        date=date_obj,
                        defaults={"nav": nav},
                    )

                    if created:
                        inserted += 1
                        local_inserted += 1
                    else:
                        updated += 1
                        local_updated += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"[{idx}/{len(scheme_codes)}] {scheme_code} MFAPI processed "
                        f"(inserted={local_inserted}, updated={local_updated})"
                    )
                )

            # AMFI latest merge/injection
            amfi_rec = amfi_map.get(scheme_code)
            if amfi_rec:
                try:
                    amfi_date = amfi_rec["date"]
                    amfi_nav = amfi_rec["nav"]

                    latest_db = (
                        FundNavDaily.objects
                        .filter(scheme_code=scheme_code)
                        .order_by("-date")
                        .first()
                    )

                    should_write = False
                    if latest_db is None:
                        should_write = True
                    elif amfi_date > latest_db.date:
                        should_write = True
                    elif amfi_date == latest_db.date and float(latest_db.nav) != float(amfi_nav):
                        should_write = True

                    if should_write:
                        _, created = FundNavDaily.objects.update_or_create(
                            scheme_code=scheme_code,
                            date=amfi_date,
                            defaults={"nav": amfi_nav},
                        )

                        if created:
                            inserted += 1
                        else:
                            updated += 1

                        amfi_injected += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"🔥 AMFI latest injected for {scheme_code} → {amfi_date} nav={amfi_nav}"
                            )
                        )

                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠ AMFI merge failed for {scheme_code}: {e}"
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. inserted={inserted}, updated={updated}, failed_mfapi={failed}, amfi_injected={amfi_injected}"
            )
        )