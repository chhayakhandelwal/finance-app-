







"""
Bill / receipt OCR: extract date, total amount, and category from image or PDF.








Optional ML: place category_model.pkl + vectorizer.pkl in core/ml/ (see core/ml/README.txt).
Requires Tesseract on the host (e.g. brew install tesseract).
"""
from __future__ import annotations








import re
import tempfile
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from .statement_parser import is_bank_statement, extract_transactions








# --- App category keys (must match frontend CATEGORY_MASTER keys) ---
BILL_CATEGORIES = (
 "Shopping",
 "Food",
 "Groceries",
 "Medical",
 "Fuel",
 "Bills",
 "Other",
)
















def _casefold(s: str) -> str:
 """
 Normalize for case-insensitive matching across OCR output: ALL CAPS, Title Case,
 mixed-case, and Unicode (stronger than lower() for comparisons).
 """
 return (s or "").casefold()
















def _norm_line(s: str) -> str:
 """Collapse whitespace + casefold for line-based keyword matching."""
 return re.sub(r"\s+", " ", _casefold(s).strip())
















ML_DIR = Path(__file__).resolve().parent / "ml"








_model = None
_vectorizer = None
_ml_attempted = False
















def _load_ml():
 global _model, _vectorizer, _ml_attempted
 if _ml_attempted:
     return _model, _vectorizer
 _ml_attempted = True
 try:
     import joblib








     mp = ML_DIR / "category_model.pkl"
     vp = ML_DIR / "vectorizer.pkl"
     if mp.is_file() and vp.is_file():
         _model = joblib.load(mp)
         _vectorizer = joblib.load(vp)
 except Exception:
     _model = None
     _vectorizer = None
 return _model, _vectorizer
















def _classify_category_ml(text: str) -> str | None:
 model, vectorizer = _load_ml()
 if not model or not vectorizer:
     return None
 try:
     X = vectorizer.transform([text])
     raw = model.predict(X)[0]
     return normalize_ml_category(str(raw))
 except Exception:
     return None
















# Substring keywords: prefer multi-word / brand names (short tokens like "eat" stay in FOOD_* regex only).
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
 "Shopping": (
     "amazon", "amazon pay", "flipkart", "myntra", "ajio", "nykaa", "meesho", "snapdeal",
     "tatacliq", "shopclues", "paytm mall", "jiomart", "jiomart.com",
     "croma", "reliance digital", "vijay sales", "vijaysales", "poorvika", "sangeetha mobiles",
     "decathlon", "nike", "adidas", "puma", "reebok", "under armour", "zara", "h&m",
     "lifestyle", "shoppers stop", "westside", "pantaloons", "max fashion", "lenskart",
     "firstcry", "hopscotch", "babyoye", "pepperfry", "urban ladder", "ikea", "ddecor",
     "electronics", "mobiles", "smartphone", "laptop", "headphones", "earbuds", "watch",
     "fashion", "apparel", "clothing", "footwear", "sneakers", "handbag", "jewellery",
     "jewelry", "cosmetics", "beauty", "skincare", "perfume", "gift", "toys", "books",
     "kindle", "stationery", "sports", "fitness", "online order", "order id", "order no",
     "retail", "department store", "mall", "showroom", "outlet sale",
 ),
 "Groceries": (
     "dmart", "d-mart", "reliance fresh", "reliance smart", "bigbasket", "big basket",
     "blinkit", "grofers", "instamart", "jiomart grocery", "nature's basket", "natures basket",
     "spar", "more supermarket", "more retail", "hypercity", "star bazaar", "foodhall",
     "food hall", "nilgiris", "heritage fresh", "ratnadeep", "vishal mega mart", "vishal",
     "metro cash", "best price", "supermarket", "hypermarket", "kirana", "provision",
     "grocery", "groceries", "vegetable", "fruits", "dairy", "milk", "curd", "paneer",
     "organic", "staples", "atta", "rice", "dal", "pulses", "spices", "masala", "oil",
     "ration", "fmcg", "biscuits", "snacks packet", "cold storage", "frozen food",
     "apple", "apples", "orange", "oranges", "banana", "bananas", "tomato", "onion",
     "potato", "mango", "grapes", "carrot", "spinach", "papaya", "pomegranate",
 ),
 "Medical": (
     "hospital", "pharmacy", "medical", "clinic", "medicine", "laboratory", "diagnostic",
     "apollo", "apollo pharmacy", "netmeds", "pharmeasy", "1mg", "medplus", "wellness forever",
     "fortis", "max healthcare", "manipal", "medanta", "narayana", "aster", "rainbow",
     "rainbow hospital", "sankara nethralaya", "lvpei", "eye hospital", "dental", "dentist",
     "physiotherapy", "vaccination", "immunization", "health check", "master health",
     "doctor", "surgeon", "nursing home", "multispeciality", "multi-speciality", "scan centre",
     "mri", "ct scan", "ultrasound", "xray", "path lab", "blood test", "collection centre",
 ),
 "Fuel": (
     "petrol", "diesel", "fuel", "cng", "hp petrol", "hpcl", "iocl", "indian oil",
     "bharat petroleum", "bpcl", "shell", "essar", "nayara", "reliance petroleum",
     "jio-bp", "jio bp", "petrol pump", "fuel station", "filling station", "gas station",
     "speed", "power", "miles", "lubricant", "engine oil", "hp lubricants",
 ),
 "Bills": (
     "electricity", "power bill", "bescom", "mseb", "mahadiscom", "tata power", "adani",
     "torrent power", "water bill", "water tax", "sewage", "property tax", "municipal",
     "broadband", "fiber", "fibre", "wifi", "internet bill", "act fibernet", "hathway",
     "airtel", "jio fiber", "jio postpaid", "vodafone", "vi ", "idea", "bsnl", "dth",
     "tata sky", "tatasky", "dish tv", "airtel dth", "sun direct", "videocon d2h",
     "postpaid", "prepaid", "recharge", "mobile bill", "utility", "gas cylinder", "lpg",
     "indane", "hp gas", "bharat gas", "subscription", "netflix", "spotify", "prime video",
     "hotstar", "youtube premium", "icloud", "google one", "software license", "hosting",
     "domain", "society maintenance", "maintenance bill", "cam charges", "rent receipt",
     "housing society", "insurance premium", "lic ", "policy premium", "emi reminder",
 ),
}








# Weighted medical phrases (hospital / lab OCR)
MEDICAL_PHRASES_WEIGHT: tuple[tuple[str, int], ...] = (
 ("hospital", 5),
 ("pharmacy", 4),
 ("patient", 3),
 ("medical", 3),
 ("clinic", 3),
 ("blood sugar", 2),
 ("blood urea", 2),
 ("creatinine", 3),
 ("liver function", 2),
 ("kidney", 2),
 ("thyroid", 2),
 ("lipid", 2),
 ("cholesterol", 2),
 ("hba1c", 2),
 ("vitamin", 2),
 ("uric acid", 2),
 ("electrolyte", 2),
 ("ecg", 2),
 ("ekg", 2),
 ("echo", 2),
 ("x-ray", 2),
 ("xray", 2),
 ("mri", 3),
 ("ct scan", 3),
 ("ultrasound", 2),
 ("sonography", 2),
 ("radiology", 2),
 ("pathology", 2),
 ("histopathology", 2),
 ("biopsy", 2),
 ("culture", 2),
 ("sensitivity", 2),
 ("diagnostic", 2),
 ("prescription", 2),
 ("doctor", 2),
 ("consultation", 2),
 ("nursing", 2),
 ("mrs.", 1),
 ("mr.", 1),
 ("dr.", 2),
 ("opd", 2),
 ("ipd", 2),
 ("icu", 2),
 ("ot charges", 2),
 ("specimen", 2),
 ("particulars", 1),
 ("platelet", 2),
 ("hemoglobin", 2),
 ("wbc", 1),
 ("rbc", 1),
 ("urine", 1),
 ("stool", 1),
 ("prothrombin", 2),
 ("pt inr", 2),
 ("coombs", 2),
 ("chest", 1),
 ("surgery", 2),
 ("ward", 1),
 ("medicine", 2),
 ("laboratory", 2),
 ("lab report", 2),
 ("discharge", 2),
 ("apollo", 2),
 ("netmeds", 2),
 ("pharmeasy", 2),
 ("dental", 2),
 ("physiotherapy", 2),
 ("vaccine", 2),
 ("immunization", 2),
)








# Food: word-boundary only (never substring "eat" in "creatinine")
FOOD_WORD_RE = re.compile(
 r"\b(zomato|swiggy|restaurants?|cafes?|dining|pizzas?|burgers?|dominos?|kfc|"
 r"mcdonalds?|mc\s*donald|uber\s*eats|food\s*court|biryani|dosa|idli|vada|uttapam|"
 r"paratha|naan|kebab|shawarma|rolls?|momos?|canteen|mess|tiffin|takeaway|take\s*away|"
 r"lunch|dinner|breakfast|brunch|snacks?|eat\s*out|dine\s*in|grubhub|doordash|talabat|"
 r"faasos|oven\s*stories|starbucks|subway|haldiram|chaayos|wow\s*momo|barista|costa|"
 r"pizza\s*hut|burger\s*king|taco\s*bell|wendy|chipotle|panera|dunkin|tim\s*hortons|"
 r"saravana\s*bhavan|aadhar\s*kudil|sagar\s*ratna|barbeque\s*nation|absolute\s*barbecues|"
 r"mainland\s*china|beijing\s*express|behrouz|ovenstory|oven\s*story|behrouz\s*biryani)\b",
 re.IGNORECASE,
)








FOOD_BRAND_RE = re.compile(
 r"\b(food|eat|meal|kitchen|outlet|chef|menu|fssai|packaging|service\s*charge|"
 r"table\s*no|waiter|tip|buffet|a\s*la\s*carte|thali|platter|gravy|curry)\b",
 re.IGNORECASE,
)








# Fresh produce on supermarket line items (not hospitals)
GROCERY_PRODUCE_RE = re.compile(
 r"\b(?:apples?|oranges?|bananas?|grapes?|mang(?:o|oes)|tomatoes?|onions?|potatoes?|"
 r"carrots?|spinach|lettuce|cabbage|cucumber|lemons?|limes?|pears?|peaches?|plums?|"
 r"strawberr(?:y|ies)|watermelon|papaya|pomegranates?|ginger|garlic|broccoli|cauliflower|"
 r"capsicum|bell\s*peppers?|beans?|peas?|berries)\b",
 re.IGNORECASE,
)








# Filename stem hints (upload name before extension)
FILENAME_MEDICAL = (
 "hospital", "medical", "pharmacy", "clinic", "lab", "pathology", "doctor", "prescription",
 "rx", "diagnostic", "health", "dental", "scan", "report",
)
FILENAME_FOOD = (
 "zomato", "swiggy", "food", "restaurant", "cafe", "dominos", "kfc", "pizza", "lunch",
 "dinner", "burger", "meal", "biryani",
)
FILENAME_GROCERIES = (
 "dmart", "grocery", "grocer", "bigbasket", "blinkit", "mart", "supermarket", "kirana",
 "vegetable", "milk", "ration",
)
FILENAME_FUEL = (
 "petrol", "diesel", "fuel", "hp", "iocl", "shell", "cng", "pump", "bunk",
)
FILENAME_BILLS = (
 "electricity", "power", "water", "broadband", "wifi", "airtel", "jio", "vodafone",
 "dth", "rent", "society", "utility", "recharge", "subscription", "bescom", "mseb",
)
FILENAME_SHOPPING = (
 "amazon", "flipkart", "myntra", "shopping", "online", "purchase", "nykaa", "croma",
)








# Lines containing these phrases (plus a number) are treated as final-total candidates.
TOTAL_AMOUNT_LINE_KEYWORDS: tuple[str, ...] = (
 "grand total",
 "gross total",
 "net total",
 "net amount",
 "net amt",
 "net payable",
 "net bill",
 "final total",
 "final amount",
 "invoice total",
 "invoice amount",
 "bill total",
 "bill amount",
 "total amount",
 "total payable",
 "total payment",
 "total due",
 "total:",
 "total to pay",
 "amount total",
 "amount payable",
 "payable amount",
 "amount due",
 "due amount",
 "amount to pay",
 "balance due",
 "balance payable",
 "outstanding amount",
 "outstanding balance",
 "payment due",
 "payable total",
 "you pay",
 "pay now",
 "net value",
 "total value",
 "total (incl",
 "total(incl",
 "inclusive total",
 "amount charged",
 "charge amount",
 "settlement amount",
)








# Prefer these over generic "Total …" lines (e.g. Total Qty vs Grand Total).
TOTAL_AMOUNT_PRIMARY_KEYWORDS: tuple[str, ...] = (
 "grand total",
 "gross total",
 "net total",
 "net amount",
 "net amt",
 "net payable",
 "net bill",
 "final total",
 "final amount",
 "amount due",
 "due amount",
 "total due",
 "balance due",
 "balance payable",
 "outstanding amount",
 "payable amount",
 "amount payable",
 "total payable",
 "total payment",
 "total to pay",
 "amount to pay",
 "invoice total",
 "invoice amount",
 "bill total",
 "bill amount",
 "total amount",
 "payment due",
 "you pay",
 "pay now",
)








# Lines like "Total Qty: 5" — count/units, not the payable total (even though they contain "total").
_QTY_OR_COUNT_TOTAL_LINE = re.compile(
 r"\b(?:total\s+(?:qty|quantity|quantities|items?|pcs|pieces|units?|nos\.?|nos)|"
 r"(?:qty|quantity)\s+total|no\.?\s*of\s*(?:pcs|pieces|items?)|"
 r"number\s+of\s+(?:items?|pcs|pieces|units?))\b",
 re.IGNORECASE,
)
















def _line_is_footer_or_payment_terms(low: str) -> bool:
 """
 T&C / signatory blocks and payment-window lines (e.g. 'pay within 18 days').
 These often contain substrings like 'due amount' but the number is days, not ₹.
 """
 if any(
     x in low
     for x in (
         "terms & conditions",
         "terms and conditions",
         "authorised signatory",
         "authorized signatory",
         "authorised signatory for",
         "authorized signatory for",
     )
 ):
     return True
 if "notes" in low and "terms" in low:
     return True
 if re.search(r"\b\d{1,4}\s*(?:days?|cays|months?)\b", low):
     return True
 if "within" in low and re.search(r"\b\d{1,4}\s*(?:days?|cays|months?)\b", low):
     return True
 if "due amount" in low and re.search(r"\b\d{1,4}\s*(?:days?|cays)\b", low):
     return True
 return False
















# Layout / phrase patterns (not brand lists): infer category from document structure alone.
_STRUCTURE_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
 "Medical": (
     re.compile(r"\bpatient\s*(?:name|no\.?|id|#)\b", re.I),
     re.compile(r"\b(?:date\s*)?(?:admitted|discharge)\b", re.I),
     re.compile(r"\b(?:room|ward)\s*no\.?\b", re.I),
     re.compile(r"\battending\s+physician\b", re.I),
     re.compile(r"\bstatement\s+of\s+account\b", re.I),
     re.compile(r"\b(?:operating|recovery)\s+room\b", re.I),
     re.compile(r"\b(?:hospital|pharmacy)\s+bills?\b", re.I),
     re.compile(r"\b(?:lab|pathology)\s+(?:report|charges?|tests?)\b", re.I),
     re.compile(r"\bamount\s+due\s*[-–]\s*(?:hospital\s+)?bill\b", re.I),
     re.compile(r"\b(?:nursing\s+care|oxygen|emergency\s+room)\b", re.I),
 ),
 "Fuel": (
     re.compile(r"\b(?:petrol|diesel|fuel)\s*(?:pump|station|outlet|price|rate)?\b", re.I),
     re.compile(r"\b\d+(?:\.\d+)?\s*(?:l|ltr|litres?)\b", re.I),
     re.compile(r"\brate\s*/\s*(?:l|ltr|litre)\b", re.I),
     re.compile(r"\b(?:nozzle|filling\s+station|fuel\s+pump)\b", re.I),
 ),
 "Bills": (
     re.compile(r"\b(?:kwh|units?)\s*(?:consumed|charged|used)\b", re.I),
     re.compile(r"\b(?:electricity|power)\s*(?:bill|charges?)\b", re.I),
     re.compile(r"\b(?:water|broadband|fiber|fibre)\s*(?:bill|charges?)\b", re.I),
     re.compile(r"\bmeter\s*reading\b", re.I),
     re.compile(r"\b(?:postpaid|prepaid)\s+(?:mobile|plan|bill)\b", re.I),
 ),
 "Shopping": (
     re.compile(r"\border\s*(?:id|no\.?|number)\b", re.I),
     re.compile(r"\b(?:shipping|delivery)\s+address\b", re.I),
     re.compile(r"\b(?:sold\s*by|sold\s*on)\b", re.I),
     re.compile(r"\bgstin\s*[:\s]?\s*[0-9]{10,15}\b", re.I),
 ),
 "Groceries": (
     re.compile(r"\bfssai\s*(?:lic|license|no\.?)\b", re.I),
     re.compile(r"\b(?:mrp|selling\s*price)\s*[:\s]?\s*₹?\s*\d", re.I),
     re.compile(r"\b(?:kg|gms?|grams?)\s*(?:\d|@)\b", re.I),
 ),
}
















def _structure_category_scores(text: str) -> dict[str, int]:
 """Points per category from layout patterns only (each match +2)."""
 out: dict[str, int] = {c: 0 for c in BILL_CATEGORIES if c != "Other"}
 if not (text or "").strip():
     return out
 for cat, patterns in _STRUCTURE_PATTERNS.items():
     for rx in patterns:
         if rx.search(text):
             out[cat] = out.get(cat, 0) + 2
 return out
















def _infer_category_from_document_structure(text: str) -> str | None:
 """
 Guess category from receipt layout (phrases/regex), without filename or keyword lists.
 Returns None when signals are weak or ambiguous.
 """
 if not (text or "").strip():
     return None
 t = _casefold(text)
 sc = _structure_category_scores(text)
 med = sc["Medical"]
 fuel = sc["Fuel"]
 bills = sc["Bills"]
 shop = sc["Shopping"]
 groc = sc["Groceries"]








 if med >= 4:
     return "Medical"
 if med >= 2 and re.search(r"\bpatient\b", t) and re.search(
     r"\b(?:discharge|admitted|room no|room)\b", t
 ):
     return "Medical"








 if fuel >= 4 and med < 2:
     return "Fuel"
 if bills >= 4 and med < 2:
     return "Bills"
 if shop >= 6 and med < 2:
     return "Shopping"
 if groc >= 4 and med < 2:
     return "Groceries"
 return None
















def _medical_phrase_matches(phrase: str, t: str) -> bool:
 """
 Match medical phrases without substring false positives (e.g. culture in agriculture,
 ward in reward, vitamin in multivitamin, invoice on every receipt).
 """
 tcf = _casefold(t)
 pcf = _casefold((phrase or "").strip())
 if not pcf:
     return False
 if " " in pcf:
     return pcf in tcf
 if "-" in pcf:
     return bool(re.search(r"\b" + re.escape(pcf) + r"\b", tcf))
 if pcf.endswith("."):
     return bool(re.search(r"\b" + re.escape(pcf) + r"(?=\s|$)", tcf))
 return bool(re.search(r"\b" + re.escape(pcf) + r"\b", tcf))
















def _medical_weight_score(t: str) -> int:
 s = 0
 for phrase, w in MEDICAL_PHRASES_WEIGHT:
     if _medical_phrase_matches(phrase, t):
         s += w
 return s
















def _food_word_score(t: str) -> int:
 t = t or ""
 return len(FOOD_WORD_RE.findall(t)) + len(FOOD_BRAND_RE.findall(t))
















def classify_category_keywords(text: str) -> str:
 """Bag-of-substrings fallback (Food uses word-boundary helpers above, not raw 'eat')."""
 t = _casefold(text)
 scores: dict[str, int] = {c: 0 for c in BILL_CATEGORIES if c != "Other"}
 for cat, keys in CATEGORY_KEYWORDS.items():
     for word in keys:
         if word in t:
             scores[cat] = scores.get(cat, 0) + 1
 scores["Food"] = scores.get("Food", 0) + _food_word_score(t)
 best = max(scores.values()) if scores else 0
 if best == 0:
     return "Other"
 return max(scores, key=scores.get)
















def normalize_ml_category(raw: str) -> str:
 s = _casefold((raw or "").strip()).replace("/", " ").replace("-", " ")
 mapping = {
     "food": "Food",
     "eating": "Food",
     "restaurant": "Food",
     "dining": "Food",
     "shopping": "Shopping",
     "retail": "Shopping",
     "ecommerce": "Shopping",
     "grocery": "Groceries",
     "groceries": "Groceries",
     "supermarket": "Groceries",
     "medical": "Medical",
     "health": "Medical",
     "healthcare": "Medical",
     "hospital": "Medical",
     "pharma": "Medical",
     "fuel": "Fuel",
     "petrol": "Fuel",
     "diesel": "Fuel",
     "transport": "Fuel",
     "bills": "Bills",
     "utilities": "Bills",
     "utility": "Bills",
     "telecom": "Bills",
     "rent": "Bills",
     "other": "Other",
 }
 for k, v in mapping.items():
     if k in s:
         return v
 for cat in BILL_CATEGORIES:
     if _casefold(cat) == s:
         return cat
 return "Other"
















def classify_bill_category(text: str, filename: str = "") -> str:
 """
 Order: (1) document layout / phrases from OCR text — works without filename keywords;
 (2) filename stem hints; (3) weighted medical/food; (4) ML; (5) substring keywords.
 """
 t = _casefold(text)
 fn = _casefold(filename)








 # --- Structure-first: hospital bills, fuel slips, utilities, e-commerce layout ---
 struct = _infer_category_from_document_structure(text)
 if struct:
     return struct








 # --- Filename hints (specific tokens in uploaded file name) ---
 if any(w in fn for w in FILENAME_MEDICAL):
     return "Medical"
 if any(w in fn for w in FILENAME_FOOD):
     return "Food"
 if any(w in fn for w in FILENAME_GROCERIES):
     return "Groceries"
 if any(w in fn for w in FILENAME_FUEL):
     return "Fuel"
 if any(w in fn for w in FILENAME_BILLS):
     return "Bills"
 if any(w in fn for w in FILENAME_SHOPPING):
     return "Shopping"








 med = _medical_weight_score(t)
 food = _food_word_score(t)
 produce_n = len(GROCERY_PRODUCE_RE.findall(t))








 # Supermarket line items (e.g. apple + orange) — not medical even if "Vitamin C" on label
 if produce_n >= 2 and med < 4:
     return "Groceries"








 if med >= 4:
     return "Medical"
 if re.search(r"\bhospital\b", t) or re.search(r"\bpharmacy\b", t):
     return "Medical"
 if med >= 2 and food <= 1:
     return "Medical"
 if med >= 1 and food == 0 and (
     re.search(r"\bpatient\b", t)
     or re.search(r"\b(?:mr|mrs|dr)\.\b", t)
 ):
     return "Medical"








 if food >= 1:
     return "Food"








 ml = _classify_category_ml(text)
 if ml and ml in BILL_CATEGORIES:
     if ml == "Food" and med >= 3:
         return "Medical"
     if ml == "Medical" and food >= 2 and med <= 1:
         return "Food"
     # ML often misreads GST invoices with produce lines as medical
     if ml == "Medical" and produce_n >= 2 and med < 5:
         return "Groceries"
     return ml








 return classify_category_keywords(text)
















def _parse_date_token(ds: str):
 from .statement_utils import parse_stmt_date








 return parse_stmt_date(ds)
















def _bill_date_line_priority(line: str) -> int:
 """Lower = try first (hospital bills: discharge / final bill date before admit)."""
 ll = _casefold(line)
 if "discharge" in ll and ("date" in ll or "discharge:" in ll):
     return 1
 if "amount due" in ll or "total due" in ll or "grand total" in ll:
     return 2
 if "invoice" in ll or "bill date" in ll or "statement of" in ll:
     return 3
 if "admitted" in ll and "date" in ll:
     return 4
 if "date" in ll and any(
     k in ll for k in ("receipt", "issued", "printed", "created", "service")
 ):
     return 5
 if any(
     k in ll
     for k in (
         "invoice",
         "bill date",
         "inv date",
         "inv dt",
         "date:",
         "dated",
         "date of",
         "invoice date",
         "bill no",
         "receipt",
         "dt.",
         "d.o.",
         "issued",
         "on:",
     )
 ):
     return 6
 return 20
















def extract_bill_date(text: str):
  """
  Stable date extraction (DO NOT TOUCH OTHER LOGIC)
  """
  from .statement_utils import DATE_REGEXES




  raw = text or ""
  lines = [ln for ln in raw.splitlines() if ln.strip()]




  def scan_string(s: str):
      for rx in DATE_REGEXES:   # ✅ SINGLE LOOP ONLY
          try:
              for m in rx.finditer(s):
                  token = m.group(1)
                  d = _parse_date_token(token)
                  if d:
                      return d
          except Exception:
              continue
      return None




  # priority lines first
  ordered = sorted(lines, key=_bill_date_line_priority)




  for line in ordered:
      d = scan_string(line)
      if d:
          return d




  return scan_string(raw)








def _to_float_amount(s: str) -> float | None:
 s = (s or "").strip().replace("₹", "").replace(",", "").replace(" ", "")
 s = re.sub(r"(CR|DR)$", "", s, flags=re.IGNORECASE)
 if not s or s in (".", "-"):
     return None
 try:
     return float(Decimal(s))
 except (InvalidOperation, ValueError):
     return None
















def extract_total_amount(text: str) -> float | None:
 """
 Find the most likely grand/net total on a bill (skips GST %, qty columns, and
 Total Qty vs Grand Total confusion).
 """
 lines = (text or "").splitlines()
 num_pat = re.compile(r"\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+\.\d{2}")
 primary: list[float] = []
 secondary: list[float] = []
 weak: list[float] = []








 def _line_amounts(raw: str) -> list[float]:
     out = []
     for m in num_pat.finditer(raw):
         val = _to_float_amount(m.group(0))
         if val is not None and val >= 1:
             out.append(val)
     return out








 for line in lines:
     low = _norm_line(line)
     if _line_is_footer_or_payment_terms(low):
         continue
     if _QTY_OR_COUNT_TOTAL_LINE.search(line):
         continue
     if "%" in line and "gst" in low:
         continue
     # Line-item columns: skip unless the line clearly names a final total.
     if any(skip in low for skip in ("qty", "rate", "mrp", "cgst", "sgst", "cess")):
         if "total" not in low and "amount" not in low and "due" not in low:
             continue








     strong_kw = any(kw in low for kw in TOTAL_AMOUNT_LINE_KEYWORDS)
     weak_total = "total" in low and not any(x in low for x in ("sub total", "subtotal"))
     weak_net = (
         re.search(r"\bnet(?:t)?\b", low)
         and not re.search(r"\b(?:internet|intranet|subnet)\b", low)
         and any(x in low for x in ("amount", "pay", "payable", "due", "bill", "value"))
     )








     if not (strong_kw or weak_total or weak_net):
         continue








     nums = _line_amounts(line)
     if not nums:
         continue
     line_max = max(nums)








     if any(kw in low for kw in TOTAL_AMOUNT_PRIMARY_KEYWORDS):
         primary.append(line_max)
     elif strong_kw:
         secondary.append(line_max)
     else:
         weak.append(line_max)








 if primary:
     return max(primary)
 if secondary:
     return max(secondary)
 if weak:
     return max(weak)








 # Fallback: largest currency-like number (skip T&C / payment-term lines)
 all_nums = []
 for line in lines:
     low = _norm_line(line)
     if _line_is_footer_or_payment_terms(low):
         continue
     for m in num_pat.finditer(line):
         v = _to_float_amount(m.group(0))
         if v is not None and v >= 10:
             all_nums.append(v)
 return max(all_nums) if all_nums else None
















def _cv2_ocr_image_path(image_path: Path) -> str:
 from .ocr_tesseract import configure_tesseract








 import cv2
 import pytesseract








 configure_tesseract()
 img = cv2.imread(str(image_path))
 if img is None:
     raise FileNotFoundError("Could not read image for OCR")
 gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
 gray = cv2.medianBlur(gray, 3)
 gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 2)
 return pytesseract.image_to_string(gray, config="--oem 3 --psm 6")
















def extract_text_from_upload(upload) -> str:
 """Use statement_utils.extract_text; for poor image results, retry with OpenCV preprocessing."""
 from . import statement_utils as su








 name = _casefold(getattr(upload, "name", "") or "")








 if hasattr(upload, "seek"):
     upload.seek(0)
 primary = su.extract_text(upload)








 if len(primary.strip()) >= 40:
     return primary








 if name.endswith((".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp")):
     try:
         if hasattr(upload, "seek"):
             upload.seek(0)
         raw = upload.read()
         with tempfile.NamedTemporaryFile(suffix=Path(name).suffix or ".png", delete=False) as tmp:
             tmp.write(raw)
             tmp.flush()
             path = Path(tmp.name)
         try:
             secondary = _cv2_ocr_image_path(path)
             if len(secondary.strip()) > len(primary.strip()):
                 return secondary
         finally:
             path.unlink(missing_ok=True)
     except Exception:
         pass








 return primary
















def analyze_bill_upload(upload) -> dict:
 """
 Returns:
   raw_text, category (key), amount (float|None), expense_date (date|None), merchant hint
 """
 _load_ml()
 raw_text = extract_text_from_upload(upload)
 if not raw_text or len(raw_text.strip()) < 3:
     raise ValueError("Could not read text from file. Install Tesseract and ensure the image/PDF is readable.")








 if is_bank_statement(raw_text):
      transactions = extract_transactions(raw_text)




      return {
          "type": "bank_statement",
          "transactions": transactions,
          "raw_text": raw_text[:50000],
      }




  # ✅ OLD bill logic (unchanged)
 total = extract_total_amount(raw_text)
 fname = (getattr(upload, "name", "") or "bill").strip() or "bill"
 stem = Path(fname).stem




 cat = classify_bill_category(raw_text, filename=stem)
 d = extract_bill_date(raw_text)
 expense_date = d if d else date.today()




 return {
      "type": "bill",
      "raw_text": raw_text,
      "category": cat,
      "amount": total,
      "expense_date": expense_date,
      "merchant": stem[:120],
  }





















