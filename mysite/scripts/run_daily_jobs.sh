#!/bin/bash

set -e   # ❗ stop script if any command fails

PROJECT_DIR="/Users/chhavikhandelwal/project12/mysite"
PYTHON="$PROJECT_DIR/venv/bin/python"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/cron.log"
LOCK_FILE="$PROJECT_DIR/.daily_jobs.lock"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR" || exit 1

# 🔒 Prevent overlapping runs
if [ -f "$LOCK_FILE" ]; then
  echo "==== SKIPPED: Another job already running at $(date) ====" >> "$LOG_FILE" 2>&1
  exit 1
fi

touch "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

echo "==================================================" >> "$LOG_FILE"
echo "==== DAILY JOB START $(date) ====" >> "$LOG_FILE"

# 🔹 Ensure correct environment
export DJANGO_SETTINGS_MODULE=mysite.settings

# 1) Update benchmark data
echo "[1/5] update_benchmarks START $(date)" >> "$LOG_FILE"
$PYTHON manage.py update_benchmarks --backfill_days 2 >> "$LOG_FILE" 2>&1
echo "[1/5] update_benchmarks END $(date)" >> "$LOG_FILE"

# 2) Update NAV data
echo "[2/5] update_mf_data START $(date)" >> "$LOG_FILE"
$PYTHON manage.py update_mf_data >> "$LOG_FILE" 2>&1
echo "[2/5] update_mf_data END $(date)" >> "$LOG_FILE"

# ❗ Check NAV updated or not (VERY IMPORTANT)
echo "[CHECK] NAV count:" >> "$LOG_FILE"
$PYTHON manage.py shell -c "from core.models import FundNavDaily; print(FundNavDaily.objects.count())" >> "$LOG_FILE"

# 3) Build ML samples
echo "[3/5] build_ml_samples START $(date)" >> "$LOG_FILE"
$PYTHON manage.py build_ml_samples --lookback_days 365 --limit_funds 1000 >> "$LOG_FILE" 2>&1
echo "[3/5] build_ml_samples END $(date)" >> "$LOG_FILE"

# 4) Weekly retrain (Friday)
DAY_OF_WEEK=$(date +%u)

if [ "$DAY_OF_WEEK" -eq 5 ]; then
  echo "[4/5] WEEKLY RETRAIN START $(date)" >> "$LOG_FILE"
  $PYTHON manage.py train_models --days 365 >> "$LOG_FILE" 2>&1
  echo "[4/5] WEEKLY RETRAIN END $(date)" >> "$LOG_FILE"
else
  echo "[4/5] WEEKLY RETRAIN SKIPPED $(date)" >> "$LOG_FILE"
fi

# 5) Predictions
echo "[5/5] predict_funds START $(date)" >> "$LOG_FILE"
$PYTHON manage.py predict_funds >> "$LOG_FILE" 2>&1
echo "[5/5] predict_funds END $(date)" >> "$LOG_FILE"

# ❗ Check predictions count
echo "[CHECK] Predictions count:" >> "$LOG_FILE"
$PYTHON manage.py shell -c "from core.models import FundPrediction; print(FundPrediction.objects.count())" >> "$LOG_FILE"

echo "==== DAILY JOB END $(date) ====" >> "$LOG_FILE"
echo "==================================================" >> "$LOG_FILE"