import os
import json
import math
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass


FD_JSON_PATH = os.path.join(
    settings.BASE_DIR, "core", "data", "fixed_assets", "fd_rates.json"
)

DEBT_CATALOG_PATH = os.path.join(
    settings.BASE_DIR, "core", "data", "fixed_assets", "debt_catalog.json"
)

MFAPI_URL = "https://api.mfapi.in/mf/{scheme_code}"


# ---------------------------------------------------
# AMFI latest NAV helper
# ---------------------------------------------------

def _fetch_amfi_nav_map():
    cache_key = "amfi:navall:map"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

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
                print(f"📡 Fetching AMFI NAVAll (try {i+1}) → {base_url}")

                r = requests.get(
                    base_url,
                    headers=headers,
                    timeout=20,
                    allow_redirects=True,
                    verify=True,
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
                    except Exception:
                        continue

                    nav_map[scheme_code] = {
                        "nav": nav_val,
                        "date": date_str,
                    }

                cache.set(cache_key, nav_map, 6 * 60 * 60)
                return nav_map

            except Exception as e:
                print(f"❌ AMFI retry {i+1} failed for {base_url}: {e}")

    print("⚠ AMFI NAVAll failed completely")
    cache.set(cache_key, {}, 15 * 60)
    return {}


# ---------------------------------------------------
# Helpers
# ---------------------------------------------------

def _parse_ddmmyyyy(s: str):
    return datetime.strptime(s, "%d-%m-%Y").date()


def _nav_on_or_before(history, target_date):
    best = None
    for d, nav in history:
        if d <= target_date:
            best = nav
        else:
            break
    return best


def _calc_return_pct(nav_now, nav_then):
    if nav_now is None or nav_then is None or nav_then == 0:
        return None
    return (nav_now / nav_then - 1.0) * 100.0


def _calc_cagr_pct(nav_now, nav_then, years):
    if nav_now is None or nav_then is None or nav_then <= 0 or years <= 0:
        return None
    return (math.pow(nav_now / nav_then, 1.0 / years) - 1.0) * 100.0


# ---------------------------------------------------
# MFAPI history
# ---------------------------------------------------

def _fetch_mfapi_history(scheme_code: int):
    cache_key = f"mfapi:fixed:history:{int(scheme_code)}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url = MFAPI_URL.format(scheme_code=int(scheme_code))

    try:
        resp = requests.get(
            url,
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            verify=True,
        )
        resp.raise_for_status()

        payload = resp.json()

        rows = []
        for it in payload.get("data", []):
            try:
                d = _parse_ddmmyyyy(it["date"])
                nav = float(it["nav"])
                rows.append((d, nav))
            except Exception:
                continue

        rows.sort(key=lambda x: x[0])
        cache.set(cache_key, rows, 6 * 60 * 60)
        return rows

    except Exception as e:
        print(f"❌ MFAPI failed for {scheme_code}: {e}")
        cache.set(cache_key, [], 10 * 60)
        return []


# ---------------------------------------------------
# Returns computation
# ---------------------------------------------------

def _compute_returns(scheme_code: int, amfi_map=None):
    cache_key = f"mfapi:fixed:perf:{scheme_code}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    history = _fetch_mfapi_history(scheme_code)

    # latest AMFI record if available
    amfi_rec = None
    if amfi_map:
        amfi_rec = amfi_map.get(str(int(scheme_code)))

    # Case 1: no history at all -> latest only mode
    if not history:
        if amfi_rec:
            try:
                amfi_date = datetime.strptime(amfi_rec["date"], "%d-%b-%Y").date()
                amfi_nav = float(amfi_rec["nav"])

                out = {
                    "as_of": amfi_date.isoformat(),
                    "history_start_date": None,
                    "latest_nav": amfi_nav,
                    "cagr_1M": None,
                    "cagr_6M": None,
                    "cagr_1Y": None,
                    "cagr_3Y": None,
                    "cagr_5Y": None,
                    "cagr_SI": None,
                    "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "LATEST_ONLY",
                }
                cache.set(cache_key, out, 10 * 60)
                return out
            except Exception as e:
                print(f"⚠ AMFI latest parse failed for {scheme_code}: {e}")

        out = {
            "as_of": None,
            "history_start_date": None,
            "latest_nav": None,
            "cagr_1M": None,
            "cagr_6M": None,
            "cagr_1Y": None,
            "cagr_3Y": None,
            "cagr_5Y": None,
            "cagr_SI": None,
            "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "NO_HISTORY",
        }
        cache.set(cache_key, out, 10 * 60)
        return out

    # Case 2: history exists -> full calculation
    as_of_date, nav_now = history[-1]
    inception_date, nav_inception = history[0]

    if amfi_rec:
        try:
            amfi_date = datetime.strptime(amfi_rec["date"], "%d-%b-%Y").date()
            amfi_nav = float(amfi_rec["nav"])

            if amfi_date >= as_of_date:
                print(f"🔥 Using AMFI latest for debt {scheme_code} → {amfi_date}")
                as_of_date = amfi_date
                nav_now = amfi_nav
        except Exception as e:
            print(f"⚠ AMFI parse error for debt {scheme_code}: {e}")

    d_1m = as_of_date - timedelta(days=30)
    d_6m = as_of_date - timedelta(days=182)
    d_1y = as_of_date - timedelta(days=365)
    d_3y = as_of_date - timedelta(days=365 * 3)
    d_5y = as_of_date - timedelta(days=365 * 5)

    nav_1m = _nav_on_or_before(history, d_1m)
    nav_6m = _nav_on_or_before(history, d_6m)
    nav_1y = _nav_on_or_before(history, d_1y)
    nav_3y = _nav_on_or_before(history, d_3y)
    nav_5y = _nav_on_or_before(history, d_5y)

    si_years = (as_of_date - inception_date).days / 365.0

    out = {
        "as_of": as_of_date.isoformat(),
        "history_start_date": inception_date.isoformat(),
        "latest_nav": nav_now,
        "cagr_1M": _calc_return_pct(nav_now, nav_1m),
        "cagr_6M": _calc_return_pct(nav_now, nav_6m),
        "cagr_1Y": _calc_cagr_pct(nav_now, nav_1y, 1) if nav_1y else None,
        "cagr_3Y": _calc_cagr_pct(nav_now, nav_3y, 3) if nav_3y else None,
        "cagr_5Y": _calc_cagr_pct(nav_now, nav_5y, 5) if nav_5y else None,
        "cagr_SI": _calc_cagr_pct(nav_now, nav_inception, si_years) if si_years >= 1 else None,
        "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "OK",
    }

    cache.set(cache_key, out, 6 * 60 * 60)
    return out


# ---------------------------------------------------
# FD API
# ---------------------------------------------------

class FDRatesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not os.path.exists(FD_JSON_PATH):
            return Response(
                {"detail": "fd_rates.json not found", "path": FD_JSON_PATH},
                status=404,
            )

        try:
            with open(FD_JSON_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            return Response(
                {"detail": "Invalid fd_rates.json", "error": str(e)},
                status=500,
            )

        banks = payload.get("banks")
        if not isinstance(banks, list) or len(banks) == 0:
            return Response(
                {"detail": "fd_rates.json schema invalid (banks missing)"},
                status=500,
            )

        for b in banks:
            bank_name = b.get("bank")
            tenures = b.get("tenures")
            rates = b.get("rates")

            if not bank_name:
                return Response(
                    {"detail": "fd_rates.json schema invalid (bank name missing in a bank entry)"},
                    status=500,
                )
            if not isinstance(tenures, list) or len(tenures) == 0:
                return Response(
                    {"detail": f"fd_rates.json schema invalid (tenures missing for bank {bank_name})"},
                    status=500,
                )
            if not isinstance(rates, dict):
                return Response(
                    {"detail": f"fd_rates.json schema invalid (rates missing for bank {bank_name})"},
                    status=500,
                )

            for t in tenures:
                if not isinstance(t, dict) or not t.get("key") or not t.get("label"):
                    return Response(
                        {"detail": f"fd_rates.json schema invalid (bad tenure entry for bank {bank_name})"},
                        status=500,
                    )

        return Response(payload, status=200)


# ---------------------------------------------------
# Debt Funds API
# ---------------------------------------------------

class DebtFundsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        category = (request.query_params.get("category") or "").strip().lower()
        amc_q = (request.query_params.get("amc") or "").strip().lower()

        if category not in ("debt_govt", "debt_corp"):
            return Response(
                {"detail": "category must be debt_govt or debt_corp"},
                status=400,
            )

        if not os.path.exists(DEBT_CATALOG_PATH):
            return Response(
                {"detail": "debt_catalog.json not found", "path": DEBT_CATALOG_PATH},
                status=404,
            )

        with open(DEBT_CATALOG_PATH, "r", encoding="utf-8") as f:
            catalog = json.load(f)

        funds = (((catalog.get("categories") or {}).get(category) or {}).get("funds")) or []

        try:
            amfi_map = _fetch_amfi_nav_map()
        except Exception as e:
            print(f"⚠ Debt AMFI fetch failed: {e}")
            amfi_map = {}

        out_rows = []

        for fund in funds:
            amc = (fund.get("amc") or "").strip().lower()
            if amc_q and amc != amc_q:
                continue

            label = fund.get("label")
            scheme_code = fund.get("scheme_code")

            if not isinstance(scheme_code, int):
                continue

            try:
                perf = _compute_returns(scheme_code, amfi_map=amfi_map)

                out_rows.append({
                    "bucket": "fixed",
                    "type": "debt",
                    "category": category,
                    "amc": amc,
                    "label": label,
                    "scheme_code": scheme_code,
                    **perf,
                })

            except Exception as e:
                out_rows.append({
                    "bucket": "fixed",
                    "type": "debt",
                    "category": category,
                    "amc": amc,
                    "label": label,
                    "scheme_code": scheme_code,
                    "_error": str(e),
                    "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "ERROR",
                })

        return Response(out_rows, status=200)