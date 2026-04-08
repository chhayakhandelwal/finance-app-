# core/management/commands/train_models.py

import os
import joblib
import numpy as np
import pandas as pd

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import FundMLSample

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, roc_auc_score
from xgboost import XGBRegressor, XGBClassifier


ART_DIR = os.path.join(settings.BASE_DIR, "core", "ml_artifacts")
REG_PATH = os.path.join(ART_DIR, "xgb_nextweek_return_reg.joblib")
CLF_PATH = os.path.join(ART_DIR, "xgb_outperform_clf.joblib")

FEATURES = ["ret_1w", "ret_1m", "vol_1m", "alpha_1m"]  # keep consistent with your build_ml_samples.py


class Command(BaseCommand):
    help = "Train XGBoost models (next-week return regression + outperform classification)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=365, help="Use last N days of ML samples")
        parser.add_argument("--test_size", type=float, default=0.2, help="Test split fraction")

    def handle(self, *args, **opts):
        os.makedirs(ART_DIR, exist_ok=True)

        days = int(opts["days"])
        test_size = float(opts["test_size"])

        cutoff = timezone.now().date() - timezone.timedelta(days=days)

        qs = (
            FundMLSample.objects
            .filter(as_of__gte=cutoff)
            .values("scheme_code", "as_of", *FEATURES, "y_fund_ret_1w", "y_outperform_1w")
        )
        rows = list(qs)

        if not rows:
            self.stdout.write(self.style.ERROR("No FundMLSample rows found for training. Run build_ml_samples first."))
            return

        df = pd.DataFrame(rows)

        # keep only rows where targets exist
        df_reg = df.dropna(subset=FEATURES + ["y_fund_ret_1w"]).copy()
        df_clf = df.dropna(subset=FEATURES + ["y_outperform_1w"]).copy()

        if len(df_reg) < 50:
            self.stdout.write(self.style.ERROR(f"Not enough regression rows: {len(df_reg)}"))
            return
        if len(df_clf) < 50:
            self.stdout.write(self.style.ERROR(f"Not enough classification rows: {len(df_clf)}"))
            return

        # ---------------------------
        # Regression: next-week return
        # ---------------------------
        Xr = df_reg[FEATURES].astype(float)
        yr = df_reg["y_fund_ret_1w"].astype(float)

        Xr_train, Xr_test, yr_train, yr_test = train_test_split(
            Xr, yr, test_size=test_size, random_state=42
        )

        reg = XGBRegressor(
            n_estimators=600,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            random_state=42,
        )
        reg.fit(Xr_train, yr_train)

        pred_r = reg.predict(Xr_test)
        mae = mean_absolute_error(yr_test, pred_r)

        # ---------------------------
        # Classification: outperform?
        # ---------------------------
        Xc = df_clf[FEATURES].astype(float)
        yc = df_clf["y_outperform_1w"].astype(int)

        Xc_train, Xc_test, yc_train, yc_test = train_test_split(
            Xc, yc, test_size=test_size, random_state=42, stratify=yc
        )

        clf = XGBClassifier(
            n_estimators=600,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            eval_metric="logloss",
            random_state=42,
        )
        clf.fit(Xc_train, yc_train)

        proba = clf.predict_proba(Xc_test)[:, 1]
        try:
            auc = roc_auc_score(yc_test, proba)
        except Exception:
            auc = None

        # Save artifacts
        joblib.dump({"model": reg, "features": FEATURES}, REG_PATH)
        joblib.dump({"model": clf, "features": FEATURES}, CLF_PATH)

        self.stdout.write(self.style.SUCCESS(f"✅ Saved: {REG_PATH}"))
        self.stdout.write(self.style.SUCCESS(f"✅ Saved: {CLF_PATH}"))
        self.stdout.write(self.style.SUCCESS(f"REG MAE: {mae:.4f} (return %)"))
        self.stdout.write(self.style.SUCCESS(f"CLF AUC: {auc if auc is not None else 'N/A'}"))