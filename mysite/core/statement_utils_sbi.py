import re
from datetime import datetime
from decimal import Decimal, InvalidOperation


SBI_DATE_RE = r"\d{1,2}\s+[A-Za-z]{3}\s+\d{4}"
SBI_ENTRY_START_RE = re.compile(
    rf"^\s*(?P<txn_date>{SBI_DATE_RE})\s+(?P<value_date>{SBI_DATE_RE})\s+(?P<rest>.*)$",
    re.IGNORECASE,
)

AMOUNT_RE = re.compile(r"(?<!\d)(\d[\d,]*\.\d{1,2})(?!\d)")
REF_RE = re.compile(r"\b[A-Z]{2,}[A-Z0-9/:-]{4,}|\b\d{6,}\b")

OUTFLOW_HINTS = [
    "to transfer",
    "transfer to",
    "upi/dr",
    "debit",
    "dr.",
    "withdrawal",
    "atm",
    "cash wd",
    "purchase",
    "pos",
    "billpay",
    "debit card",
    "imps",
    "neft",
    "payment",
    "ecom",
    "pur",
    "atm wdl",
    "by debit card",
]

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
]


def parse_sbi_transactions(text: str, debit_only: bool = False):
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    in_transactions = False
    entries = []
    current = []

    for line in lines:
        lower = line.lower()

        if not in_transactions and "txn date" in lower and "description" in lower:
            in_transactions = True
            continue

        if not in_transactions:
            continue

        if "statement summary" in lower:
            break

        if SBI_ENTRY_START_RE.match(line):
            if current:
                entries.append(" ".join(current))
            current = [line]
        elif current:
            current.append(line)

    if current:
        entries.append(" ".join(current))

    parsed = []
    for entry in entries:
        txn = _parse_sbi_entry(entry)
        if txn and (not debit_only or txn["direction"] == "DEBIT"):
            parsed.append(txn)

    return parsed


def _parse_sbi_entry(entry: str):
    match = SBI_ENTRY_START_RE.match(entry)
    if not match:
        return None

    txn_date = _parse_date(match.group("txn_date"))
    value_date = _parse_date(match.group("value_date")) or txn_date
    rest = _cleanup_entry_text(match.group("rest"))

    amounts = [_to_decimal(x) for x in AMOUNT_RE.findall(rest)]
    amounts = [x for x in amounts if x is not None]
    if len(amounts) < 2:
        return None

    amount, balance = _pick_amount_pair(amounts)
    if amount is None or balance is None:
        return None

    direction = _infer_direction(rest)
    description = _strip_amounts(rest)
    reference = _extract_reference(description)
    merchant = _guess_merchant(description)
    category = _categorize(description, merchant)

    return {
        "txn_date": txn_date,
        "value_date": value_date,
        "description": description,
        "reference": reference,
        "merchant": merchant,
        "amount": amount,
        "balance": balance,
        "direction": direction,
        "category": category,
        "raw": entry,
    }


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

    for fmt in ("%d %b %Y", "%d %B %Y"):
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


def _pick_amount_pair(amounts):
    if len(amounts) < 2:
        return None, None

    if len(amounts) >= 3 and amounts[-1] == Decimal("0.00"):
        return amounts[-3], amounts[-2]

    return amounts[-2], amounts[-1]


def _infer_direction(text: str) -> str:
    lower = text.lower()
    if any(token in lower for token in INFLOW_HINTS):
        return "CREDIT"
    if any(token in lower for token in OUTFLOW_HINTS):
        return "DEBIT"
    return "DEBIT"


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