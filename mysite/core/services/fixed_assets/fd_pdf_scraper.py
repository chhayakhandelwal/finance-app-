# core/services/fixed_assets/fd_pdf_scraper.py
import re
import json
import tempfile
from pathlib import Path
from datetime import date

import requests
import certifi
from bs4 import BeautifulSoup

import pdfplumber


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TENURES = [1, 2, 3, 5, 10]  # years you want in UI


def _abs_url(base: str, href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        # base like https://www.axis.bank.in/...
        root = re.match(r"^(https?://[^/]+)", base)
        return (root.group(1) if root else base.rstrip("/")) + href
    return base.rstrip("/") + "/" + href.lstrip("/")


def _find_pdf_links(page_url: str) -> list[str]:
    """Fetch HTML and return list of absolute .pdf links."""
    r = requests.get(page_url, timeout=30, headers=DEFAULT_HEADERS, verify=certifi.where(), allow_redirects=True)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if ".pdf" in href.lower():
            links.append(_abs_url(page_url, href))

    # also scan raw HTML for pdf URLs (some sites embed pdf in JS)
    raw = r.text
    for m in re.findall(r"https?://[^\s\"']+\.pdf", raw, flags=re.IGNORECASE):
        links.append(m)

    # de-dup while keeping order
    seen = set()
    out = []
    for x in links:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def _download_pdf(url: str) -> Path:
    """Download PDF to a temp file and return Path."""
    r = requests.get(url, timeout=60, headers={**DEFAULT_HEADERS, "Accept": "application/pdf,*/*"}, verify=certifi.where())
    r.raise_for_status()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(r.content)
    tmp.close()
    return Path(tmp.name)


def _extract_text(pdf_path: Path, max_pages: int = 2) -> str:
    """Extract text from first N pages (FD rate PDFs usually have the table early)."""
    texts = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            texts.append(page.extract_text() or "")
    return "\n".join(texts)


def _pick_best_pdf(pdf_links: list[str]) -> str | None:
    """
    Prefer PDFs that look like 'interest rate', 'fd', 'term deposit' etc.
    """
    if not pdf_links:
        return None

    keywords = ["interest", "rate", "fd", "deposit", "term", "schedule", "domestic"]
    scored = []
    for link in pdf_links:
        l = link.lower()
        score = sum(1 for k in keywords if k in l)
        scored.append((score, link))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def _parse_simple_year_buckets(text: str) -> dict[int, float] | None:
    """
    SAFE generic parsing:
    tries to find any lines containing:
      1 year / 1 yr / 12 months
      2 year / 24 months
      3 year / 36 months
      5 year / 60 months
      10 year / 120 months
    and then extracts the FIRST percentage on that line.
    This won’t be perfect for every bank, but works surprisingly often for rate PDFs.
    """
    # normalize
    t = re.sub(r"[ \t]+", " ", text.replace("\u00a0", " "))

    patterns = {
        1: [r"\b1\s*(year|yr)\b", r"\b12\s*months?\b"],
        2: [r"\b2\s*(year|yr)\b", r"\b24\s*months?\b"],
        3: [r"\b3\s*(year|yr)\b", r"\b36\s*months?\b"],
        5: [r"\b5\s*(year|yr)\b", r"\b60\s*months?\b"],
        10: [r"\b10\s*(year|yr)\b", r"\b120\s*months?\b"],
    }

    out: dict[int, float] = {}
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]

    for years, pats in patterns.items():
        for ln in lines:
            if any(re.search(p, ln, flags=re.IGNORECASE) for p in pats):
                # find % like 6.50 or 7.10%
                m = re.search(r"(\d{1,2}\.\d{1,2})\s*%?", ln)
                if m:
                    try:
                        out[years] = float(m.group(1))
                        break
                    except Exception:
                        pass
        # next year bucket
    return out if len(out) >= 3 else None  # require some confidence


def fetch_bank_fd_rates_from_pdf(bank_name: str, landing_page_url: str) -> dict:
    """
    Returns:
      {
        "bank": "HDFC",
        "rates": { "1": 6.9, "2": 7.1, ... },
        "_source_pdf": "https://....pdf",
        "_source_page": "https://....",
      }
    Raises exception on hard failure.
    """
    pdf_links = _find_pdf_links(landing_page_url)
    pdf_url = _pick_best_pdf(pdf_links)
    if not pdf_url:
        raise RuntimeError(f"No PDF link found on page: {landing_page_url}")

    pdf_path = _download_pdf(pdf_url)
    try:
        text = _extract_text(pdf_path, max_pages=2)
    finally:
        try:
            pdf_path.unlink(missing_ok=True)
        except Exception:
            pass

    parsed = _parse_simple_year_buckets(text)
    if not parsed:
        raise RuntimeError("Could not parse required tenure buckets from PDF text")

    # convert to string keys like your current JSON format
    rates = {str(k): float(v) for k, v in parsed.items() if k in TENURES}

    # Ensure all target tenures exist (fill missing with None)
    for y in TENURES:
        rates.setdefault(str(y), None)

    return {
        "bank": bank_name,
        "rates": rates,
        "_source_pdf": pdf_url,
        "_source_page": landing_page_url,
    }


def merge_and_write_fd_json(out_path: Path, new_bank_blocks: list[dict], as_of: str | None = None) -> dict:
    """
    Merge update safely:
    - If bank update fails, keep old rates for that bank.
    - Write atomic file.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    old = {}
    if out_path.exists():
        try:
            old = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            old = {}

    old_banks = {str(b.get("bank", "")).upper(): b for b in (old.get("banks") or []) if isinstance(b, dict)}

    # apply new blocks
    for blk in new_bank_blocks:
        old_banks[str(blk.get("bank", "")).upper()] = {
            "bank": blk["bank"],
            "rates": blk["rates"],
            "_source_pdf": blk.get("_source_pdf"),
            "_source_page": blk.get("_source_page"),
        }

    merged = {
        "as_of": as_of or date.today().isoformat(),
        "tenures_years": TENURES,
        "banks": [old_banks[k] for k in sorted(old_banks.keys())],
        "_note": "FD rates are auto-updated from bank PDFs when available. If a bank fails, last known rates are retained.",
    }

    tmp = out_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    tmp.replace(out_path)
    return merged