import os
import json
import joblib
import numpy as np
import pandas as pd
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import FundMLSample, FundPrediction


ART_DIR = os.path.join(settings.BASE_DIR, "core", "ml_artifacts")
REG_PATH = os.path.join(ART_DIR, "xgb_nextweek_return_reg.joblib")
CLF_PATH = os.path.join(ART_DIR, "xgb_outperform_clf.joblib")

EQUITY_CATALOG = os.path.join(
    settings.BASE_DIR, "core", "data", "amfi", "equity_catalog.json"
)
DEBT_CATALOG = os.path.join(
    settings.BASE_DIR, "core", "data", "fixed_assets", "debt_catalog.json"
)


def load_scheme_lookup():
    """
    Builds:
      {
        "scheme_code": {
          "scheme_name": "...",
          "amc": "...",
          "category_key": "..."
        }
      }

    Works with nested equity_catalog.json structure like:
    {
      "equity": {
        "active": {
          "largecap": [...]
        },
        "passive": {
          "nifty50": [...]
        }
      }
    }
    """
    lookup = {}

    valid_categories = {
        "largecap",
        "midcap",
        "smallcap",
        "multicap",
        "flexicap",
        "balanced_advantage",
        "multi_asset",
        "hybrid_conservative",
        "hybrid_aggressive",
        "nifty50",
        "bse",
        "midcap150",
        "smallcap250",
        "debt_govt",
        "debt_corp",
    }

    def walk(node, current_category=None):
        if isinstance(node, dict):
            if "scheme_code" in node:
                code = str(node.get("scheme_code") or "").strip()
                if code:
                    lookup[code] = {
                        "scheme_name": node.get("label", ""),
                        "amc": node.get("amc", ""),
                        "category_key": current_category or "",
                    }

            for k, v in node.items():
                next_category = current_category
                if k in valid_categories:
                    next_category = k
                walk(v, next_category)

        elif isinstance(node, list):
            for item in node:
                walk(item, current_category)

    if os.path.exists(EQUITY_CATALOG):
        with open(EQUITY_CATALOG, "r", encoding="utf-8") as f:
            walk(json.load(f))

    if os.path.exists(DEBT_CATALOG):
        with open(DEBT_CATALOG, "r", encoding="utf-8") as f:
            walk(json.load(f))

    return lookup


def _load_bundle(path: str) -> tuple:
    obj = joblib.load(path)

    if isinstance(obj, dict):
        model = obj.get("model")
        feats = obj.get("features")
        if model is None:
            raise ValueError(f"Invalid artifact at {path}: missing 'model'")
        if feats is not None and not isinstance(feats, (list, tuple)):
            raise ValueError(f"Invalid artifact at {path}: 'features' must be list/tuple")
        return model, list(feats) if feats else None

    if hasattr(obj, "predict"):
        return obj, None

    raise ValueError(f"Invalid artifact at {path}: expected dict bundle or model")


class Command(BaseCommand):
    help = "Predict next-week return + outperform probability using latest FundMLSample rows."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=365, help="Use last N days of samples")
        parser.add_argument("--limit", type=int, default=1000, help="Max rows to predict")
        parser.add_argument("--as_of", type=str, default=None, help="Force a specific as_of date YYYY-MM-DD")

    def handle(self, *args, **opts):
        days = int(opts["days"])
        limit = int(opts["limit"])
        as_of_str = opts.get("as_of")

        if not os.path.exists(REG_PATH) or not os.path.exists(CLF_PATH):
            self.stdout.write(
                self.style.ERROR("Model artifacts missing. Run: python manage.py train_models")
            )
            return

        scheme_lookup = load_scheme_lookup()

        reg, reg_features = _load_bundle(REG_PATH)
        clf, clf_features = _load_bundle(CLF_PATH)

        FEATURES = reg_features or clf_features or ["ret_1w", "ret_1m", "vol_1m", "alpha_1m"]

        if as_of_str:
            try:
                as_of_date = timezone.datetime.strptime(as_of_str, "%Y-%m-%d").date()
            except Exception:
                self.stdout.write(self.style.ERROR("Invalid --as_of. Use YYYY-MM-DD"))
                return
        else:
            cutoff = timezone.now().date() - timezone.timedelta(days=days)
            as_of_date = (
                FundMLSample.objects
                .filter(as_of__gte=cutoff)
                .order_by("-as_of")
                .values_list("as_of", flat=True)
                .first()
            )

        if not as_of_date:
            self.stdout.write(
                self.style.ERROR("No FundMLSample rows found. Run build_ml_samples first.")
            )
            return

        qs = (
            FundMLSample.objects
            .filter(as_of=as_of_date)
            .values("scheme_code", "category_key", "benchmark_code", "as_of", *FEATURES)
            .order_by("scheme_code")[:limit]
        )
        rows = list(qs)

        if not rows:
            self.stdout.write(self.style.WARNING(f"No samples found for as_of={as_of_date}"))
            return

        df = pd.DataFrame(rows)

        for c in FEATURES:
            if c not in df.columns:
                df[c] = np.nan

        X = df[FEATURES].astype(float).fillna(0.0).values

        pred_ret = reg.predict(X)

        if hasattr(clf, "predict_proba"):
            pred_prob = clf.predict_proba(X)[:, 1]
        else:
            s = clf.decision_function(X)
            pred_prob = 1 / (1 + np.exp(-s))

        out = []

        for i, r in df.iterrows():
            scheme_code = int(r["scheme_code"])
            category_key = r.get("category_key")
            benchmark_code = r.get("benchmark_code")
            as_of = r.get("as_of")

            meta = scheme_lookup.get(str(scheme_code), {})
            scheme_name = meta.get("scheme_name", "")
            amc = meta.get("amc", "")

            pred_return = float(pred_ret[i])
            prob = float(pred_prob[i])

            pred_for_date = as_of + timedelta(days=7)

            FundPrediction.objects.update_or_create(
                scheme_code=scheme_code,
                as_of=as_of,
                defaults={
                    "scheme_name": scheme_name,
                    "amc": amc,
                    "category_key": category_key,
                    "benchmark_code": benchmark_code,
                    "pred_for_date": pred_for_date,
                    "pred_nextweek_return": pred_return,
                    "prob_outperform": prob,
                }
            )

            out.append({
                "scheme_code": scheme_code,
                "scheme_name": scheme_name,
                "amc": amc,
                "category_key": category_key,
                "benchmark_code": benchmark_code,
                "as_of": str(as_of),
                "pred_for_date": str(pred_for_date),
                "pred_nextweek_return": pred_return,
                "prob_outperform": prob,
            })

        out.sort(key=lambda x: (-x["prob_outperform"], -x["pred_nextweek_return"]))

        self.stdout.write(
            self.style.SUCCESS(f"OK: predicted {len(out)} rows for as_of={as_of_date}")
        )
        self.stdout.write(json.dumps(out[:20], indent=2))