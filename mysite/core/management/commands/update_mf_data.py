import json
import os
from datetime import datetime, timedelta

import pandas as pd
import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import FundNavDaily

print("update_mf_data (FINAL + AMFI ROBUST VERSION LOADED)")

CATALOG_PATH = os.path.join(settings.BASE_DIR, "core", "data", "amfi", "equity_catalog.json")
OUT_DIR = os.path.join(settings.BASE_DIR, "core", "data", "mf_out")
CSV_DIR = os.path.join(OUT_DIR, "csv")
CACHE_DIR = os.path.join(OUT_DIR, "cache")

MFAPI_URL = "https://api.mfapi.in/mf/{scheme_code}"

HORIZONS = [
    ("1M", 30),
    ("6M", 182),
    ("1Y", 365),
    ("3Y", 365 * 3),
    ("5Y", 365 * 5),
]


# -------------------------------
# AMFI LATEST NAV FETCH
# -------------------------------
def fetch_amfi_nav_map():
    urls = [
        "https://portal.amfiindia.com/spages/NAVAll.txt",
        "https://www.amfiindia.com/spages/NAVAll.txt",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/plain,text/html,*/*",
    }

    for base_url in urls:
        current_url = base_url

        for i in range(3):
            try:
                print(f"📡 Fetching AMFI (try {i+1}) → {current_url}")

                r = requests.get(current_url, headers=headers, timeout=30, allow_redirects=True)
                r.raise_for_status()

                text = r.text or ""

                if "Scheme Code;ISIN" not in text and "Scheme Code;ISIN Div" not in text:
                    raise Exception("Invalid AMFI response content")

                nav_map = {}
                lines = text.splitlines()

                for line in lines:
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
                    except Exception:
                        continue

                    nav_map[scheme_code] = {
                        "nav": nav_val,
                        "date": date_str,  # e.g. 24-Mar-2026
                    }

                print(f"✅ AMFI loaded for {len(nav_map)} schemes")
                return nav_map

            except Exception as e:
                print(f"❌ AMFI retry {i+1} failed: {e}")

    print("⚠️ AMFI completely failed → using MFAPI/cache only")
    return {}


# -------------------------------
# HELPERS
# -------------------------------
def ensure_dirs():
    for p in [OUT_DIR, CSV_DIR, CACHE_DIR]:
        os.makedirs(p, exist_ok=True)


def load_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_date(s):
    return datetime.strptime(s, "%d-%m-%Y").date()


def fetch_full_history(scheme_code):
    url = MFAPI_URL.format(scheme_code=scheme_code)
    headers = {"User-Agent": "Mozilla/5.0"}

    for i in range(3):
        try:
            print(f"Fetching LIVE history for {scheme_code} (try {i+1})")
            r = requests.get(url, headers=headers, timeout=20)
            r.raise_for_status()

            data = r.json().get("data", [])
            if not data:
                return []

            rows = []
            for item in data:
                try:
                    d = parse_date(item["date"])
                    nav = float(item["nav"])
                    rows.append((d, nav))
                except Exception:
                    continue

            rows.sort(key=lambda x: x[0])
            return rows

        except Exception as e:
            print(f"❌ Live retry {i+1} failed for {scheme_code}: {e}")

    return []


def save_cache(scheme_code, history):
    df = pd.DataFrame(history, columns=["date", "nav"])
    df.to_csv(os.path.join(CACHE_DIR, f"nav_{scheme_code}.csv"), index=False)


def load_cache(scheme_code):
    path = os.path.join(CACHE_DIR, f"nav_{scheme_code}.csv")
    if not os.path.exists(path):
        return None

    df = pd.read_csv(path)
    if df.empty:
        return None

    df["date"] = pd.to_datetime(df["date"]).dt.date
    rows = list(zip(df["date"], df["nav"]))
    rows.sort(key=lambda x: x[0])
    return rows


def nearest_nav(history, target):
    best = None
    for d, nav in history:
        if d <= target:
            best = nav
        else:
            break
    return best


def calc_return(nav_now, nav_then):
    if nav_now is None or nav_then is None or nav_then == 0:
        return None
    return round((nav_now / nav_then - 1) * 100, 2)


def calc_cagr(nav_now, nav_then, years):
    if nav_now is None or nav_then is None or nav_then <= 0 or years <= 0:
        return None
    return round((pow(nav_now / nav_then, 1 / years) - 1) * 100, 2)


# -------------------------------
# MAIN COMMAND
# -------------------------------
class Command(BaseCommand):
    help = "Build CAGR CSV with AMFI latest NAV fix and sync FundNavDaily"

    def add_arguments(self, parser):
        parser.add_argument("--category", type=str, help="Run only for specific category")

    def handle(self, *args, **options):
        print("update_mf_data started")

        category_filter = options.get("category")
        synced_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        ensure_dirs()
        catalog = load_catalog()

        try:
            amfi_map = fetch_amfi_nav_map()
        except Exception as e:
            print(f"⚠️ AMFI fetch failed completely: {e}")
            amfi_map = {}

        all_rows = []

        for bucket, categories in catalog.get("equity", {}).items():
            for cat, funds in categories.items():
                if category_filter and cat.lower() != category_filter.lower():
                    continue

                print(f"\n📊 Processing category: {cat}")

                for f in funds:
                    scheme_code = str(f.get("scheme_code") or "").strip()
                    label = f.get("label")
                    amc = f.get("amc")

                    if not scheme_code:
                        continue

                    history = fetch_full_history(scheme_code)

                    if history:
                        save_cache(scheme_code, history)
                    else:
                        print(f"⚠️ Using CACHE fallback for {scheme_code}")
                        history = load_cache(scheme_code)

                    if not history:
                        print(f"❌ Skipping {scheme_code}")
                        continue

                    # -------------------------------
                    # SAVE FULL HISTORY TO DB
                    # -------------------------------
                    for d, nav in history:
                        try:
                            FundNavDaily.objects.update_or_create(
                                scheme_code=scheme_code,
                                date=d,
                                defaults={"nav": nav},
                            )
                        except Exception as e:
                            print(f"❌ Failed history save for {scheme_code} {d}: {e}")

                    # -------------------------------
                    # MFAPI / CACHE latest
                    # -------------------------------
                    as_of, latest_nav = history[-1]
                    inception_date, inception_nav = history[0]

                    # -------------------------------
                    # AMFI override for latest point
                    # -------------------------------
                    if scheme_code in amfi_map:
                        amfi_nav = amfi_map[scheme_code]["nav"]
                        amfi_date_str = amfi_map[scheme_code]["date"]

                        try:
                            amfi_date = datetime.strptime(amfi_date_str, "%d-%b-%Y").date()

                            if amfi_date >= as_of:
                                print(f"🔥 Using AMFI latest for {scheme_code} → {amfi_date}")
                                as_of = amfi_date
                                latest_nav = amfi_nav

                        except Exception as e:
                            print(f"⚠️ AMFI parse error {scheme_code}: {e}")

                    # -------------------------------
                    # SAVE FINAL LATEST NAV TO DB
                    # -------------------------------
                    try:
                        obj, created = FundNavDaily.objects.update_or_create(
                            scheme_code=scheme_code,
                            date=as_of,
                            defaults={"nav": latest_nav},
                        )
                        print(
                            f"✅ NAV DB SAVE | scheme={scheme_code} | date={as_of} | "
                            f"nav={latest_nav} | created={created}"
                        )
                    except Exception as e:
                        print(f"❌ Failed latest NAV save for {scheme_code}: {e}")

                    # -------------------------------
                    # CAGR calculation
                    # -------------------------------
                    cagr_map = {}

                    for key, days in HORIZONS:
                        start_date = as_of - timedelta(days=days)
                        start_nav = nearest_nav(history, start_date)

                        if key in ["1M", "6M"]:
                            cagr_map[key] = calc_return(latest_nav, start_nav)
                        else:
                            years = days / 365
                            cagr_map[key] = calc_cagr(latest_nav, start_nav, years)

                    years = (as_of - inception_date).days / 365
                    cagr_map["SI"] = calc_cagr(latest_nav, inception_nav, years)

                    all_rows.append({
                        "bucket": str(bucket).strip(),
                        "category": str(cat).strip(),
                        "amc": str(amc).strip() if amc else "",
                        "label": str(label).strip() if label else "",
                        "scheme_code": scheme_code,
                        "as_of": str(as_of),
                        "latest_nav": round(float(latest_nav), 4) if latest_nav is not None else None,
                        "history_start_date": str(inception_date),
                        "cagr_1M": cagr_map.get("1M"),
                        "cagr_6M": cagr_map.get("6M"),
                        "cagr_1Y": cagr_map.get("1Y"),
                        "cagr_3Y": cagr_map.get("3Y"),
                        "cagr_5Y": cagr_map.get("5Y"),
                        "cagr_SI": cagr_map.get("SI"),
                        "synced_at": synced_at,
                    })

        df = pd.DataFrame(all_rows)
        out = os.path.join(CSV_DIR, "mf_cagr_summary.csv")
        df.to_csv(out, index=False)

        print(f"\n✅ CSV Generated: {out}")
        print(f"🕒 Synced at: {synced_at}")