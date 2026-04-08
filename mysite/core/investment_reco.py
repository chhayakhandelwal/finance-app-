# core/services/investment_reco.py

EQUITY_LOW, EQUITY_HIGH = 12.0, 14.0
DEBT_LOW, DEBT_HIGH = 6.5, 8.0
GOLD_LOW, GOLD_HIGH = 6.0, 8.0


def _clip_pct(x: float) -> int:
    return max(0, min(100, int(round(x))))


def _normalize_alloc(equity: float, debt: float, gold: float):
    total = equity + debt + gold
    if total <= 0:
        return {"equity": 0, "debt": 0, "gold": 0}

    e = equity * 100 / total
    d = debt * 100 / total
    g = gold * 100 / total

    e_i, d_i, g_i = _clip_pct(e), _clip_pct(d), _clip_pct(g)
    diff = 100 - (e_i + d_i + g_i)

    buckets = {"equity": e_i, "debt": d_i, "gold": g_i}
    largest = max(buckets, key=buckets.get)
    buckets[largest] = _clip_pct(buckets[largest] + diff)
    return buckets


def _base_allocation(risk: str, horizon_years: float):
    """
    risk: LOW/MEDIUM/HIGH
    horizon buckets: <1, 1-3, 3-7, >7
    """
    y = float(horizon_years)

    if y < 1:
        if risk == "HIGH":
            return _normalize_alloc(35, 55, 10)
        if risk == "MEDIUM":
            return _normalize_alloc(25, 65, 10)
        return _normalize_alloc(15, 75, 10)

    if y < 3:
        if risk == "HIGH":
            return _normalize_alloc(60, 30, 10)
        if risk == "MEDIUM":
            return _normalize_alloc(45, 45, 10)
        return _normalize_alloc(30, 60, 10)

    if y < 7:
        if risk == "HIGH":
            return _normalize_alloc(75, 20, 5)
        if risk == "MEDIUM":
            return _normalize_alloc(60, 30, 10)
        return _normalize_alloc(40, 50, 10)

    if risk == "HIGH":
        return _normalize_alloc(85, 12, 3)
    if risk == "MEDIUM":
        return _normalize_alloc(70, 25, 5)
    return _normalize_alloc(50, 45, 5)


def _apply_goal_tilt(goal: str, alloc: dict):
    """
    Goal tilts:
    - EMERGENCY -> debt dominant
    - HOUSE/EDUCATION -> slightly more debt
    - RETIREMENT/WEALTH -> slightly more equity
    """
    e, d, g = alloc["equity"], alloc["debt"], alloc["gold"]

    if goal == "EMERGENCY":
        return _normalize_alloc(max(5, e - 25), min(95, d + 30), g)

    if goal in ("HOUSE", "EDUCATION"):
        return _normalize_alloc(max(10, e - 10), min(90, d + 12), g)

    if goal in ("RETIREMENT", "WEALTH"):
        return _normalize_alloc(min(95, e + 5), max(0, d - 6), g)

    return alloc


def _expected_return_range(alloc: dict):
    e_w = alloc["equity"] / 100.0
    d_w = alloc["debt"] / 100.0
    g_w = alloc["gold"] / 100.0

    low = e_w * EQUITY_LOW + d_w * DEBT_LOW + g_w * GOLD_LOW
    high = e_w * EQUITY_HIGH + d_w * DEBT_HIGH + g_w * GOLD_HIGH
    return (round(low, 1), round(high, 1))


def _stock_baskets(risk: str, goal: str):
    if goal == "EMERGENCY":
        return []

    base = [
        "Broad-market equity basket (Nifty 50 / Nifty 100 ETF style)",
        "Large-cap quality basket (quality / low volatility theme)",
    ]
    if risk in ("MEDIUM", "HIGH"):
        base.append("Growth tilt basket (Nifty Next 50 / midcap blend theme)")
    if risk == "HIGH":
        base.append("Limited sector tilt basket (e.g., banking/IT)")

    return base[:4]


def _mf_baskets(risk: str, goal: str, horizon_years: float):
    y = float(horizon_years)

    if goal == "EMERGENCY" or y < 1:
        return [
            "Liquid / Overnight fund category",
            "Ultra Short / Money Market fund category",
        ]

    base = ["Index fund category (Nifty 50 / Sensex)"]

    if risk == "LOW":
        base += [
            "Balanced Advantage / Conservative Hybrid category",
            "Short Duration debt fund category",
        ]
    elif risk == "MEDIUM":
        base += [
            "Flexi Cap fund category",
            "Corporate Bond / Banking & PSU debt category",
        ]
    else:
        base += [
            "Flexi Cap / Large & Midcap category",
            "Midcap category (limited allocation)",
        ]

    base += ["Gold ETF / Gold fund category (small allocation)"]
    return base[:5]


def build_investment_recommendation(*, risk: str, horizon: float, amount: float, type_: str, goal: str, mode: str):
    alloc = _base_allocation(risk, horizon)
    alloc = _apply_goal_tilt(goal, alloc)

    low, high = _expected_return_range(alloc)
    expected = f"{low}% - {high}%"

    stocks = _stock_baskets(risk, goal) if type_ in ("STOCK", "BOTH") else []
    mfs = _mf_baskets(risk, goal, horizon) if type_ in ("MF", "BOTH") else []

    note = (
        "Goal + horizon + risk-based allocation suggestion. Returns are indicative (not guaranteed). "
        "Prefer emergency fund + insurance before increasing risk."
        if goal != "EMERGENCY"
        else "Emergency goal: prioritize liquidity and capital safety. Returns are indicative (not guaranteed)."
    )

    return {
        "allocation": alloc,
        "expectedReturn": expected,
        "stocks": stocks,
        "mutualFunds": mfs,
        "note": note,
    }