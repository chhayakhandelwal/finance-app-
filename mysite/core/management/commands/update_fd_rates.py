import json
import os
import re
import tempfile
from pathlib import Path
from datetime import date

import requests
import certifi
import pdfplumber
from bs4 import BeautifulSoup

from django.conf import settings
from django.core.management.base import BaseCommand


# -------------------------------------
# CONFIG
# -------------------------------------

OUT_PATH = Path(settings.BASE_DIR) / "core" / "data" / "fixed_assets" / "fd_rates.json"

# Official landing pages (PDF will be discovered from here)
BANK_PAGES = {
    "HDFC": "https://www.hdfcbank.com/personal/save/deposits/fixed-deposit-interest-rate",
    "ICICI": "https://www.icici.bank.in/personal-banking/deposits/fixed-deposit/fd-interest-rates",
    "SBI": "https://sbi.co.in/web/interest-rates/deposit-rates/retail-domestic-term-deposits",
    "AXIS": "https://www.axis.bank.in/deposits/fixed-deposits/fd-interest-rates",
}

TARGET_YEARS = [1, 2, 3, 5, 10]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# -------------------------------------
# HELPERS
# -------------------------------------

def _absolute_url(base: str, href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        root = re.match(r"^(https?://[^/]+)", base)
        return (root.group(1) if root else base.rstrip("/")) + href
    return base.rstrip("/") + "/" + href.lstrip("/")


def _find_pdf_links(page_url: str):
    r = requests.get(page_url, timeout=30, headers=HEADERS, verify=certifi.where(), allow_redirects=True)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    links = []

    # Anchor tags
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" in href.lower():
            links.append(_absolute_url(page_url, href))

    # Raw HTML fallback
    for m in re.findall(r"https?://[^\s\"']+\.pdf", r.text, flags=re.IGNORECASE):
        links.append(m)

    # Deduplicate
    seen = set()
    unique = []
    for x in links:
        if x not in seen:
            unique.append(x)
            seen.add(x)

    return unique


def _pick_best_pdf(pdf_links):
    if not pdf_links:
        return None

    keywords = ["interest", "rate", "deposit", "fd", "schedule", "domestic"]
    scored = []

    for link in pdf_links:
        l = link.lower()
        score = sum(1 for k in keywords if k in l)
        scored.append((score, link))

    scored.sort(reverse=True)
    return scored[0][1]


def _download_pdf(url):
    r = requests.get(
        url,
        timeout=60,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/pdf,*/*"},
        verify=certifi.where(),
    )
    r.raise_for_status()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(r.content)
    tmp.close()
    return Path(tmp.name)


def _extract_text_from_pdf(path: Path):
    texts = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages[:2]:  # usually first 1-2 pages contain rates
            texts.append(page.extract_text() or "")
    return "\n".join(texts)


def _parse_rates_from_text(text: str):
    """
    Extract rates for 1Y,2Y,3Y,5Y,10Y
    Generic but stable pattern-based parsing.
    """
    text = text.replace("\u00a0", " ")
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    patterns = {
        1: [r"\b1\s*(year|yr)\b", r"\b12\s*months?\b"],
        2: [r"\b2\s*(year|yr)\b", r"\b24\s*months?\b"],
        3: [r"\b3\s*(year|yr)\b", r"\b36\s*months?\b"],
        5: [r"\b5\s*(year|yr)\b", r"\b60\s*months?\b"],
        10: [r"\b10\s*(year|yr)\b", r"\b120\s*months?\b"],
    }

    result = {}

    for years, pats in patterns.items():
        for line in lines:
            if any(re.search(p, line, re.IGNORECASE) for p in pats):
                m = re.search(r"(\d{1,2}\.\d{1,2})\s*%?", line)
                if m:
                    result[str(years)] = float(m.group(1))
                    break

    # Ensure keys exist
    for y in TARGET_YEARS:
        result.setdefault(str(y), None)

    return result


def _merge_with_existing(new_blocks):
    old = {}
    if OUT_PATH.exists():
        try:
            old = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        except Exception:
            old = {}

    existing = {
        b["bank"]: b
        for b in (old.get("banks") or [])
        if isinstance(b, dict) and "bank" in b
    }

    for blk in new_blocks:
        existing[blk["bank"]] = blk

    merged = {
        "as_of": date.today().isoformat(),
        "tenures_years": TARGET_YEARS,
        "banks": list(existing.values()),
        "_note": "Auto-updated from official bank PDF rate sheets. If a bank fails, last known rates are retained."
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(merged, indent=2), encoding="utf-8")

    return merged


# -------------------------------------
# MANAGEMENT COMMAND
# -------------------------------------

class Command(BaseCommand):
    help = "Fetch FD rates from official bank PDF rate sheets"

    def handle(self, *args, **options):

        updated_blocks = []

        for bank, page_url in BANK_PAGES.items():
            try:
                pdf_links = _find_pdf_links(page_url)
                pdf_url = _pick_best_pdf(pdf_links)

                if not pdf_url:
                    raise RuntimeError("No PDF found")

                pdf_path = _download_pdf(pdf_url)

                try:
                    text = _extract_text_from_pdf(pdf_path)
                finally:
                    try:
                        pdf_path.unlink(missing_ok=True)
                    except Exception:
                        pass

                rates = _parse_rates_from_text(text)

                updated_blocks.append({
                    "bank": bank,
                    "rates": rates,
                    "_source_pdf": pdf_url,
                    "_source_page": page_url,
                })

                self.stdout.write(self.style.SUCCESS(f"[OK] {bank}"))

            except Exception as e:
                self.stdout.write(self.style.WARNING(f"[WARN] {bank}: {e}"))

        merged = _merge_with_existing(updated_blocks)

        self.stdout.write(self.style.SUCCESS(f"Updated: {OUT_PATH}"))
        self.stdout.write(self.style.SUCCESS(f"as_of: {merged.get('as_of')}"))