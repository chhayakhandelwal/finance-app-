import re
from datetime import datetime
from decimal import Decimal, InvalidOperation


AXIS_DATE_RE = r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
AXIS_START_RE = re.compile(
    rf"^\s*(?P<txn_date>{AXIS_DATE_RE})\s*(?P<rest>.*)$",
    re.IGNORECASE,
)

AMOUNT_RE = re.compile(r"(?<!\d)(\d[\d,]*\.\d{1,2})(?!\d)")
REF_RE = re.compile(r"\b[A-Z]{2,}[A-Z0-9/:-]{4,}|\b\d{6,}\b")

INFLOW_HINTS = [
    "by transfer",
    "transfer-inb",
    "upi/cr",
    "credit",
    "cr.",
    "cash deposit",
    "salary",
    "refund",
    "credited",
    "mob/tpft",
]


def parse_axis_transactions(text: str, debit_only: bool = False):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    parsed = []

    pending_date = None
    pending_parts = []

    for line in lines:
        lower = line.lower()

        if "opening balance" in lower or "closing balance" in lower or "transaction total" in lower:
            continue
        if "statement of axis account" in lower or "tran date" in lower or "particulars" in lower:
            continue
        if "legends" in lower or "registered office" in lower:
            continue

        start_match = AXIS_START_RE.match(line)
        if start_match:
            first_token = start_match.group("txn_date")
            if _parse_date(first_token):
                if pending_date and pending_parts:
                    row = f"{pending_date} {' '.join(pending_parts)}".strip()
                    txn = _parse_axis_row(row)
                    if txn and (not debit_only or txn["direction"] == "DEBIT"):
                        parsed.append(txn)

                pending_date = first_token
                pending_parts = [start_match.group("rest").strip()]
                continue

        if pending_date:
            pending_parts.append(line.strip())

    if pending_date and pending_parts:
        row = f"{pending_date} {' '.join(pending_parts)}".strip()
        txn = _parse_axis_row(row)
        if txn and (not debit_only or txn["direction"] == "DEBIT"):
            parsed.append(txn)

    # ✅ FINAL DEDUPE FOR AXIS
    final = []
    seen = set()

    for txn in parsed:
        key = (
            str(txn.get("txn_date") or ""),
            str(txn.get("amount") or ""),
            str(txn.get("balance") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        final.append(txn)

    return final


def _parse_axis_row(row: str):
    match = AXIS_START_RE.match(row)
    if not match:
        return None

    txn_date = _parse_date(match.group("txn_date"))
    if not txn_date:
        return None

    rest = _cleanup_entry_text(match.group("rest"))
    amounts = [_to_decimal(x) for x in AMOUNT_RE.findall(rest)]
    amounts = [x for x in amounts if x is not None]

    if len(amounts) < 2:
        return None

    amount, balance, direction = _axis_amount_direction(rest, amounts)
    if amount is None or balance is None:
        return None

    description = _strip_amounts(rest)
    reference = _extract_reference(description)
    merchant = _guess_merchant(description)
    category = _categorize(description, merchant)

    return {
        "txn_date": txn_date,
        "value_date": txn_date,
        "description": description,
        "reference": reference,
        "merchant": merchant,
        "amount": amount,
        "balance": balance,
        "direction": direction,
        "category": category,
        "raw": row,
    }


def _axis_amount_direction(rest: str, amounts):
    if len(amounts) < 2:
        return None, None, None

    lower = rest.lower()
    balance = amounts[-1]
    movement = amounts[-2]

    if movement <= 0 or balance < 0:
        return None, None, None

    if any(token in lower for token in ["salary", "cash deposit", "mob/tpft", "by cash deposit"]):
        return movement, balance, "CREDIT"

    if " dr " in f" {lower} " or "debit" in lower:
        return movement, balance, "DEBIT"

    if " cr " in f" {lower} " or "credit" in lower:
        return movement, balance, "CREDIT"

    if any(token in lower for token in INFLOW_HINTS):
        return movement, balance, "CREDIT"

    return movement, balance, "DEBIT"


def _cleanup_entry_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = text.replace("UPU/", "UPI/")
    text = text.replace("JPUI", "UPI")
    text = text.replace("ERANSEER", "TRANSFER")
    return text


def _strip_amounts(text: str) -> str:
    text = AMOUNT_RE.sub(" ", text)
    text = re.sub(r"\b(?:DR|CR)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -:;/")


def _parse_date(value):
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value.strip())

    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _to_decimal(value):
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _extract_reference(text: str) -> str:
    match = REF_RE.search(text or "")
    return match.group(0) if match else ""


def _guess_merchant(text: str) -> str:
    cleaned = _cleanup_entry_text(text)

    if "/" in cleaned:
        parts = [p.strip() for p in cleaned.split("/") if p.strip()]
        for part in reversed(parts):
            candidate = re.sub(r"[^A-Za-z0-9 &.\-]", "", part).strip()
            if candidate and not candidate.replace(" ", "").isdigit():
                if candidate.lower() not in {"upi", "dr", "cr", "transfer", "to", "by", "payment"}:
                    return candidate[:140]

    tokens = re.findall(r"[A-Za-z][A-Za-z0-9&.\- ]{2,}", cleaned)
    for token in reversed(tokens):
        candidate = token.strip()
        if candidate.lower() not in {"to transfer", "by transfer", "atm", "cash", "payment"}:
            return candidate[:140]

    return "Unknown"


def _categorize(description: str, merchant: str) -> str:
    haystack = f"{description} {merchant}".lower()

    if "atm" in haystack or "cash" in haystack:
        return "Other"

    category_rules = [
        ("Food", ["swiggy", "zomato", "restaurant", "cafe", "pizza", "food", "eats"]),
        ("Groceries", ["mart", "grocery", "supermarket", "dmart", "bigbasket", "jiomart", "blinkit", "zepto"]),
        ("Medical", ["pharma", "hospital", "clinic", "medical", "chemist", "apollo", "1mg"]),
        ("Fuel", ["petrol", "diesel", "fuel", "hpcl", "bpcl", "iocl", "indian oil", "shell"]),
        ("Bills", ["electricity", "recharge", "broadband", "bill", "insurance", "emi", "rent", "loan", "premium", "kissht", "razorpay"]),
        ("Shopping", ["amazon", "flipkart", "myntra", "shopping", "store", "purchase", "ecom", "ajio", "nykaa"]),
    ]

    for category, keywords in category_rules:
        if any(keyword in haystack for keyword in keywords):
            return category

    return "Other"