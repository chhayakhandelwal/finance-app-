import re
from datetime import datetime


DATE_REGEXES = [
    re.compile(r"\b(\d{2}[-/]\d{2}[-/]\d{4})\b"),
    re.compile(r"\b(\d{4}[-/]\d{2}[-/]\d{2})\b"),
    re.compile(r"\b(\d{2}\s+[A-Za-z]{3,9}\s+\d{4})\b"),
]


def clean_transaction_description(desc: str) -> str:
    d = (desc or "").lower()
    if "upi" in d:
        return "UPI"
    if "paytm" in d:
        return "PAYTM"
    if "atm" in d or "cash" in d:
        return "ATM/CASH"
    if "emi" in d:
        return "EMI"
    if "imps" in d:
        return "IMPS"
    if "ecom" in d or "myntra" in d:
        return "SHOPPING"
    if "salary" in d:
        return "SALARY"
    if "deposit" in d:
        return "DEPOSIT"
    return "OTHER"


def _parse_money(s: str) -> float:
    return float((s or "").replace(",", "").strip())


def _parse_txn_date(date_str: str):
    date_str = (date_str or "").strip()
    for fmt in (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%d %b %Y",
        "%d %B %Y",
    ):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


# =========================
# HDFC / similar
# =========================

_TXN_START = re.compile(r"^(\d{2}[/-]\d{2}[/-](?:\d{4}|\d{2}))\s+(.*)$")
_NEW_TXN_AT_LINE_START = re.compile(r"^\d{2}[/-]\d{2}[/-](?:\d{4}|\d{2})\s+")
_THREE_AMOUNTS_TAIL = re.compile(
    r"\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$"
)
_THREE_AMOUNTS_ONLY = re.compile(
    r"^([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$"
)

_SKIP_LINE_PREFIXES = (
    "txn date",
    "tran date",
    "chq no",
    "particulars",
    "opening balance",
    "closing balance",
    "account relationship",
    "customer email",
    "statement as on",
    "your combined statement",
    "contents of",
    "end of statement",
    "summary",
    "debit count",
    "credit count",
    "total sweep",
    "total withdrawal",
    "page ",
)


def _should_skip_line(line: str) -> bool:
    ll = line.lower().strip()
    if not ll:
        return True
    if any(ll.startswith(p) for p in _SKIP_LINE_PREFIXES):
        return True
    if re.match(r"^page\s+\d+\s+of\s+\d+", ll):
        return True
    if re.search(r"[\d,]+\.\d{2}\s+[\d,]+\.\d{2}\s+[\d,]+\.\d{2}\s+[\d,]+\.\d{2}", ll) and "summary" in ll:
        return True
    return False


def _skip_between_txn_noise(line: str) -> bool:
    ll = line.lower().strip()
    if ll == "urvi gupta":
        return True
    if ll.startswith("customer id") or ll.startswith("account number"):
        return True
    if ll.startswith("joint holders"):
        return True
    if ll.startswith("statement from"):
        return True
    if ll.startswith("account type"):
        return True
    if ll.startswith("currency"):
        return True
    if ll.startswith("nomination"):
        return True
    if ll.startswith("account branch"):
        return True
    if "rtgs/neft" in ll or ll.startswith("micr"):
        return True
    if ll == "savings account details":
        return True
    if ll.startswith("opening balance"):
        return True
    if ll.startswith("vivek vihar") or ll.startswith("hdfc bank ltd"):
        return True
    if ll.startswith("manak vihar") or ll.startswith("new delhi"):
        return True
    return False


def _parse_inline_txn_line(line: str) -> tuple[str, str, str, str, str] | None:
    s = line.strip()
    mt = _THREE_AMOUNTS_TAIL.search(s)
    if not mt:
        return None
    w_s, d_s, b_s = mt.groups()
    head = s[: mt.start()].strip()
    mh = re.match(r"^(\d{2}[/-]\d{2}[/-](?:\d{4}|\d{2}))\s+(.*)$", head)
    if not mh:
        return None
    date_str, narr = mh.groups()
    return (date_str, (narr or "").strip(), w_s, d_s, b_s)


def _append_txn(
    out: list[dict],
    txn_date,
    desc_parts: list[str],
    withdrawal: float,
    deposit: float,
    closing: float,
) -> None:
    if withdrawal > 0:
        txn_type = "debit"
        amt = withdrawal
    elif deposit > 0:
        txn_type = "credit"
        amt = deposit
    else:
        txn_type = "debit"
        amt = 0.0

    raw_desc = re.sub(r"\s+", " ", " ".join(desc_parts)).strip()
    if len(raw_desc) > 800:
        raw_desc = raw_desc[:797] + "..."
    desc_short = clean_transaction_description(raw_desc)

    out.append(
        {
            "date": txn_date.isoformat(),
            "description": desc_short,
            "narration": raw_desc or desc_short,
            "amount": round(amt, 2),
            "withdrawal": round(withdrawal, 2),
            "deposit": round(deposit, 2),
            "balance": round(closing, 2),
            "type": txn_type,
        }
    )


def extract_transactions_hdfc_style(lines: list[str]) -> list[dict]:
    out: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _should_skip_line(line):
            i += 1
            continue

        inline = _parse_inline_txn_line(line)
        if inline:
            date_str, narr_head, w_s, d_s, b_s = inline
            txn_date = _parse_txn_date(date_str)
            if not txn_date:
                i += 1
                continue
            withdrawal = _parse_money(w_s)
            deposit = _parse_money(d_s)
            closing = _parse_money(b_s)
            desc_parts: list[str] = []
            if narr_head:
                desc_parts.append(narr_head)
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if _should_skip_line(nxt):
                    i += 1
                    continue
                if _skip_between_txn_noise(nxt):
                    i += 1
                    continue
                if _skip_txn_date_header_line(nxt):
                    i += 1
                    continue
                if _NEW_TXN_AT_LINE_START.match(nxt.strip()):
                    break
                desc_parts.append(nxt.strip())
                i += 1
            _append_txn(out, txn_date, desc_parts, withdrawal, deposit, closing)
            continue

        m = _TXN_START.match(line)
        if not m:
            i += 1
            continue

        date_str, rest = m.groups()
        txn_date = _parse_txn_date(date_str)
        if not txn_date:
            i += 1
            continue

        desc_parts = [rest.strip()] if rest else []
        j = i + 1
        found = False
        while j < len(lines):
            nxt = lines[j]
            if _should_skip_line(nxt):
                j += 1
                continue

            tm = _THREE_AMOUNTS_ONLY.match(nxt.strip())
            if tm:
                w_s, d_s, b_s = tm.groups()
                withdrawal = _parse_money(w_s)
                deposit = _parse_money(d_s)
                closing = _parse_money(b_s)
                _append_txn(out, txn_date, desc_parts, withdrawal, deposit, closing)
                found = True
                i = j + 1
                break

            if _NEW_TXN_AT_LINE_START.match(nxt.strip()):
                break

            desc_parts.append(nxt.strip())
            j += 1

        if not found:
            i += 1

    return out


def _skip_txn_date_header_line(line: str) -> bool:
    ll = line.lower().strip()
    return ll.startswith("txn date") and "narration" in ll


# =========================
# Axis
# =========================

def _axis_opening_balance(text: str) -> float | None:
    m = re.search(r"OPENING\s+BALANCE\s+([\d,]+\.\d{2})", text, re.I)
    if m:
        return _parse_money(m.group(1))
    return None


_DATE_ONLY_LINE = re.compile(r"^\s*(\d{2}-\d{2}-\d{4})\s*$")
_TWO_MONEY_LINE = re.compile(r"^\s*([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$")
_ONE_MONEY_LINE = re.compile(r"^\s*([\d,]+\.\d{2})\s*$")


def _axis_footer_line(line: str) -> bool:
    ll = line.lower().strip()
    if ll.startswith("transaction total") or ll.startswith("closing balance"):
        return True
    if "end of statement" in ll or "registered office" in ll:
        return True
    if ll.startswith("legends") or "unless the constituent" in ll:
        return True
    return False


def _axis_junk_inline(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if re.match(r"^Init\.?\s*Br", s, re.I):
        return True
    if re.match(r"^\d{3,5}$", s):
        return True
    return False


def _axis_split_narration_and_amounts(block_lines: list[str]) -> tuple[list[str], list[float]]:
    lines = [ln for ln in block_lines if not _axis_junk_inline(ln)]
    if not lines:
        return [], []

    last = lines[-1].strip()
    m2 = _TWO_MONEY_LINE.match(last)
    if m2:
        a, b = _parse_money(m2.group(1)), _parse_money(m2.group(2))
        return lines[:-1], [a, b]

    if len(lines) >= 2:
        l1 = lines[-1].strip()
        l2 = lines[-2].strip()
        if _ONE_MONEY_LINE.match(l1) and _ONE_MONEY_LINE.match(l2):
            amt = _parse_money(_ONE_MONEY_LINE.match(l2).group(1))
            bal = _parse_money(_ONE_MONEY_LINE.match(l1).group(1))
            return lines[:-2], [amt, bal]

    return lines, []


def extract_transactions_axis_style(lines: list[str]) -> list[dict]:
    out: list[dict] = []
    full = "\n".join(lines)
    prev_balance: float | None = _axis_opening_balance(full)

    i = 0
    while i < len(lines):
        line = lines[i]
        if _should_skip_line(line) or _axis_footer_line(line):
            i += 1
            continue

        dm = _DATE_ONLY_LINE.match(line)
        if not dm:
            i += 1
            continue

        date_str = dm.group(1)
        txn_date = _parse_txn_date(date_str)
        if not txn_date:
            i += 1
            continue

        i += 1
        block: list[str] = []
        while i < len(lines):
            nxt = lines[i]
            if _DATE_ONLY_LINE.match(nxt):
                break
            if _axis_footer_line(nxt):
                break
            if _should_skip_line(nxt) and "opening" not in nxt.lower():
                i += 1
                continue
            block.append(nxt)
            i += 1

        narr_lines, nums = _axis_split_narration_and_amounts(block)
        if len(nums) != 2:
            continue

        txn_amt, balance = nums[0], nums[1]
        withdrawal = 0.0
        deposit = 0.0

        if prev_balance is not None:
            d_deb = abs(prev_balance - txn_amt - balance)
            d_cre = abs(prev_balance + txn_amt - balance)
            if d_deb < 0.05:
                withdrawal, deposit = txn_amt, 0.0
            elif d_cre < 0.05:
                deposit, withdrawal = txn_amt, 0.0
            else:
                delta = round(balance - prev_balance, 2)
                if abs(abs(delta) - txn_amt) <= 0.05:
                    if delta > 0:
                        deposit = abs(delta)
                    elif delta < 0:
                        withdrawal = abs(delta)
                    else:
                        withdrawal = txn_amt
                elif min(d_deb, d_cre) < max(txn_amt, 1.0) * 0.01 + 0.05:
                    if d_deb < d_cre:
                        withdrawal, deposit = txn_amt, 0.0
                    else:
                        deposit, withdrawal = txn_amt, 0.0
                else:
                    if delta > 0:
                        deposit = abs(delta)
                    elif delta < 0:
                        withdrawal = abs(delta)
                    else:
                        withdrawal = txn_amt
        else:
            rem = balance - txn_amt
            if rem >= 0 and txn_amt > 0 and rem < txn_amt * 0.25:
                deposit = txn_amt
            else:
                withdrawal = txn_amt

        prev_balance = balance
        desc_parts = [ln.strip() for ln in narr_lines if ln.strip()]
        _append_txn(out, txn_date, desc_parts, withdrawal, deposit, balance)

    return out


# =========================
# Legacy
# =========================

def extract_transactions_legacy_slash_dates(text: str) -> list[dict]:
    pattern = re.compile(
        r"(\d{2}-\d{2}-\d{4})" r"(.*?)" r"(\d+\.\d{2})" r"\s+(\d+\.\d{2})"
    )
    matches = pattern.findall(text)
    transactions: list[dict] = []
    prev_balance = None

    for match in matches:
        date_str, desc_raw, amount_str, balance_str = match
        try:
            txn_date = datetime.strptime(date_str, "%d-%m-%Y").date()
            amount = float(amount_str)
            balance = float(balance_str)
            if amount == balance:
                continue
            if prev_balance is not None:
                txn_type = "credit" if balance > prev_balance else "debit"
            else:
                txn_type = "debit"
            prev_balance = balance
            desc = clean_transaction_description(desc_raw.strip())
            transactions.append(
                {
                    "date": txn_date.isoformat(),
                    "description": desc,
                    "narration": desc_raw.strip()[:800],
                    "amount": amount,
                    "withdrawal": amount if txn_type == "debit" else 0.0,
                    "deposit": amount if txn_type == "credit" else 0.0,
                    "balance": balance,
                    "type": txn_type,
                }
            )
        except Exception:
            continue

    return transactions


# =========================
# SBI SUPPORT
# =========================

_SBI_FULL_DATE = re.compile(r"^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}$")
_SBI_DATE_PREFIX = re.compile(r"^(\d{1,2}\s+[A-Za-z]{3}(?:\s+\d{4})?)\s+(.*)$")
_SBI_AMOUNT = re.compile(r"(\d[\d,]*\.\d{2})")
_SBI_DOUBLE_SHORTDATE_PREFIX = re.compile(
    r"^(\d{1,2}\s+[A-Za-z]{3})\s+(\d{1,2}\s+[A-Za-z]{3})\s+(.*)$"
)


def _is_sbi_statement(text: str) -> bool:
    t = (text or "").lower()
    return (
        "state bank of india" in t
        or "txn date value" in t
        or "description ref no./cheque" in t
        or "debit credit balance" in t
    )


def _sbi_opening_balance(text: str) -> float | None:
    m = re.search(
        r"balance\s+as\s+on\s+\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s*:\s*([\d,]+\.\d{2})",
        text,
        re.I,
    )
    if m:
        return _parse_money(m.group(1))
    return None


def _normalize_sbi_lines(lines: list[str]) -> list[str]:
    out = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if re.match(r"^\d{1,2}\s+[A-Za-z]{3}$", line):
            if i + 1 < len(lines) and re.match(r"^\d{4}$", lines[i + 1].strip()):
                out.append(f"{line} {lines[i + 1].strip()}")
                i += 2
                continue

        out.append(line)
        i += 1

    return out


def _should_skip_sbi_line(line: str) -> bool:
    ll = line.lower().strip()
    if not ll:
        return True
    skip_contains = [
        "account name",
        "address",
        "account number",
        "account description",
        "branch :",
        "drawing power",
        "interest rate",
        "mod balance",
        "cif no",
        "ifs code",
        "micr code",
        "nomination registered",
        "balance as on",
        "account statement from",
        "txn date value",
        "description ref no",
        "please do not share",
        "this is a computer generated statement",
        "rate of interest",
        "sl no.",
        "media. bank never asks",
    ]
    return any(x in ll for x in skip_contains)


def _parse_sbi_date(s: str):
    s = (s or "").strip()
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def extract_transactions_sbi_style(lines: list[str], full_text: str = "") -> list[dict]:
    lines = _normalize_sbi_lines(lines)

    out: list[dict] = []
    current: list[str] = []
    prev_balance = _sbi_opening_balance(full_text)

    def flush_current():
        nonlocal current, out, prev_balance
        if not current:
            return

        block = " ".join(current)
        current = []

        block = re.sub(r"[^\x00-\x7F]+", " ", block)
        block = re.sub(r"\s+", " ", block).strip()

        if not block:
            return

        txn_date_raw = None
        rest = None

        m = re.match(
            r"^(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s+(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s+(.*)$",
            block,
        )
        if m:
            txn_date_raw = m.group(1).strip()
            rest = m.group(3).strip()

        if txn_date_raw is None:
            m = _SBI_DOUBLE_SHORTDATE_PREFIX.match(block)
            if m:
                short = m.group(1).strip()
                tail = m.group(3).strip()
                ym = re.search(r"\b(\d{4})\s+(\d{4})\b", tail)
                if ym:
                    year = ym.group(1)
                    txn_date_raw = f"{short} {year}"
                    tail = re.sub(r"\b\d{4}\s+\d{4}\b", "", tail, count=1).strip()
                    rest = tail

        if txn_date_raw is None:
            m = _SBI_DATE_PREFIX.match(block)
            if m:
                txn_date_raw = m.group(1).strip()
                rest = m.group(2).strip()

        if txn_date_raw is None or rest is None:
            return

        rest = re.split(
            r"(please do not share|computer generated|rate of interest|repo rate)",
            rest,
            flags=re.I,
        )[0].strip()

        if not rest or _should_skip_sbi_line(rest):
            return

        amounts = _SBI_AMOUNT.findall(rest)
        amounts = [a for a in amounts if re.match(r"\d[\d,]*\.\d{2}", a)]

        if len(amounts) < 2:
            return

        amt_str = amounts[-2]
        bal_str = amounts[-1]

        try:
            amount = _parse_money(amt_str)
            balance = _parse_money(bal_str)
        except Exception:
            return

        if amount <= 0 or balance <= 0:
            return

        desc = rest.rsplit(bal_str, 1)[0]
        desc = desc.rsplit(amt_str, 1)[0].strip()
        desc_lower = desc.lower()

        withdrawal = 0.0
        deposit = 0.0

        if any(x in desc_lower for x in ["transfer", "credit", "deposit", "neft", "imps"]):
            deposit = amount
        else:
            withdrawal = amount

        if prev_balance is not None:
            delta = round(balance - prev_balance, 2)
            if abs(abs(delta) - amount) <= 1:
                if delta > 0:
                    deposit = amount
                    withdrawal = 0.0
                elif delta < 0:
                    withdrawal = amount
                    deposit = 0.0

        txn_date = _parse_sbi_date(txn_date_raw)
        if not txn_date:
            return

        _append_txn(out, txn_date, [desc], withdrawal, deposit, balance)
        prev_balance = balance

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if _should_skip_sbi_line(line):
            if current:
                flush_current()
            i += 1
            continue

        if (
            _SBI_DATE_PREFIX.match(line)
            or _SBI_DOUBLE_SHORTDATE_PREFIX.match(line)
            or _SBI_FULL_DATE.match(line)
        ):
            flush_current()
            current = [line]
        else:
            if current:
                current.append(line)

        i += 1

    flush_current()
    return out


def extract_transactions(text: str) -> list[dict]:
    """
    Extract bank transactions from statement text:
    - SBI multiline column layout
    - HDFC-style DD/MM/YYYY + 3-column amounts
    - Axis compressed layout
    - legacy fallback regex
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    text_lower = text.lower()
    text_for_legacy = re.sub(r"page \d+ of \d+", "", text_lower, flags=re.I)

    if _is_sbi_statement(text):
        sbi = extract_transactions_sbi_style(lines, text)
        if len(sbi) >= 3:
            return sbi

    txs = extract_transactions_hdfc_style(lines)

    if len(txs) < 3:
        axis = extract_transactions_axis_style(lines)
        if len(axis) > len(txs):
            txs = axis

    if len(txs) < 3:
        legacy = extract_transactions_legacy_slash_dates(text_for_legacy)
        if len(legacy) > len(txs):
            txs = legacy

    return txs


def is_bank_statement(text: str) -> bool:
    t = (text or "").lower()
    keywords = [
        "statement",
        "account",
        "balance",
        "transaction",
        "opening balance",
        "closing balance",
        "txn date",
        "tran date",
        "narration",
        "particulars",
        "withdrawals",
        "deposits",
        "ifsc",
        "savings account",
        "axis",
        "state bank of india",
        "value date",
        "ref no./cheque no.",
        "debit credit balance",
    ]
    score = sum(1 for k in keywords if k in t)
    return score >= 3