import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  FaArrowDown,
  FaArrowUp,
  FaChartLine,
  FaInfoCircle,
  FaShieldAlt,
  FaHandHoldingUsd,
  FaCalendarAlt,
} from "react-icons/fa";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import "./overview.css";

const TOKEN_KEYS = ["token", "accessToken", "authToken", "jwt"];

const readToken = () => {
  for (const k of TOKEN_KEYS) {
    const v = localStorage.getItem(k);
    if (v) return v;
  }
  return null;
};

const API_BASE_URL = (
  process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

function inr(x) {
  return Number(x || 0).toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  });
}

function toDate(value) {
  if (!value) return null;

  if (typeof value === "string") {
    const m = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (m) {
      const [, y, mo, d] = m;
      return new Date(Number(y), Number(mo) - 1, Number(d));
    }
  }

  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

function toNumber(value) {
  if (value === null || value === undefined || value === "") return 0;
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;

  const cleaned = String(value).replace(/[₹,\s]/g, "");
  const parsed = parseFloat(cleaned);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatDateShort(value) {
  const d = toDate(value);
  if (!d) return "No date";
  return d.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatMonthYear(value) {
  const d = toDate(value);
  if (!d) return "No target date";
  return d.toLocaleDateString("en-IN", {
    month: "short",
    year: "numeric",
  });
}

function daysUntil(value) {
  const d = toDate(value);
  if (!d) return null;

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate());

  return Math.ceil((target - today) / (1000 * 60 * 60 * 24));
}

function normalizeListResponse(res) {
  if (res.status !== "fulfilled") return [];
  const data = res.value?.data;

  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.results)) return data.results;
  if (Array.isArray(data?.data)) return data.data;

  return [];
}

function getIncomeDate(item) {
  return (
    item?.date ||
    item?.income_date ||
    item?.received_date ||
    item?.transaction_date ||
    item?.month_date ||
    item?.month ||
    item?.entry_date ||
    item?.payment_date ||
    item?.created_at ||
    item?.updated_at ||
    null
  );
}

function getIncomeAmount(item) {
  return toNumber(
    item?.amount ??
      item?.income_amount ??
      item?.monthly_income ??
      item?.salary_amount ??
      item?.salary ??
      item?.income ??
      item?.credited_amount ??
      item?.value ??
      0
  );
}

function getExpenseDate(item) {
  return (
    item?.expense_date ||
    item?.date ||
    item?.created_at ||
    item?.updated_at ||
    null
  );
}

function isExpenseDebit(item) {
  const direction = String(
    item?.direction || item?.entry_type || item?.flow || ""
  ).toUpperCase();
  if (direction) return direction === "DEBIT";

  const type = String(
    item?.type || item?.transaction_type || item?.txn_type || ""
  ).toUpperCase();
  if (type) return type !== "CREDIT";

  return true;
}

function getExpenseAmount(item) {
  const amount =
    toNumber(item?.amount) ||
    toNumber(item?.expense_amount) ||
    toNumber(item?.debit_amount) ||
    toNumber(item?.value);

  return isExpenseDebit(item) ? amount : 0;
}

function getSavingAmount(item) {
  return toNumber(
    item?.current_amount ?? item?.saved_amount ?? item?.amount ?? 0
  );
}

function getSavingTarget(item) {
  return toNumber(
    item?.target_amount ?? item?.goal_amount ?? item?.target ?? 0
  );
}

function getSavingName(item) {
  return item?.goal_name || item?.name || item?.title || "Saving Goal";
}

function getSavingTargetDate(item) {
  return item?.target_date || item?.deadline || item?.due_date || null;
}

function getSavingEntryDate(item) {
  return item?.created_at || item?.updated_at || item?.date || null;
}

function getGoalProgress(item) {
  const saved = getSavingAmount(item);
  const target = getSavingTarget(item);
  if (!target || target <= 0) return 0;
  return Math.min(100, Math.round((saved / target) * 100));
}

function getInsuranceDate(item) {
  return (
    item?.premium_due_date ||
    item?.due_date ||
    item?.renewal_date ||
    item?.next_due_date ||
    item?.next_due ||
    item?.next_premium_date ||
    item?.premium_date ||
    item?.premium_due ||
    item?.insurance_due_date ||
    item?.renew_date ||
    item?.expiry_date ||
    item?.policy_expiry ||
    item?.policy_end_date ||
    item?.end_date ||
    item?.endDate ||
    item?.maturity_date ||
    item?.valid_till ||
    item?.valid_until ||
    item?.date ||
    item?.premiumDate ||
    item?.renewalDate ||
    item?.nextDate ||
    item?.dueDate ||
    item?.startDate ||
    null
  );
}

function getInsuranceName(item) {
  return (
    item?.policy_name ||
    item?.insurance_type ||
    item?.policy_type ||
    item?.provider_name ||
    item?.company_name ||
    item?.insurer_name ||
    item?.plan_name ||
    item?.policy ||
    item?.name ||
    item?.title ||
    "Insurance"
  );
}

function getLendingDate(item) {
  return (
    item?.due_date ||
    item?.return_date ||
    item?.repayment_date ||
    item?.next_due_date ||
    item?.expected_return_date ||
    item?.expected_date ||
    item?.payment_date ||
    item?.collection_date ||
    item?.date ||
    null
  );
}

function getLendingName(item) {
  return (
    item?.borrower_name ||
    item?.person_name ||
    item?.receiver_name ||
    item?.customer_name ||
    item?.name ||
    item?.title ||
    "Lending"
  );
}

function buildLastThreeMonthLabels() {
  const labels = [];
  const now = new Date();

  for (let i = 2; i >= 0; i -= 1) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    labels.push({
      key: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`,
      label: d.toLocaleString("en-IN", { month: "short" }),
    });
  }

  return labels;
}

function getMonthKey(value) {
  const d = toDate(value);
  if (!d) return "";
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function SemiCircleGauge({ progress = 0, saved = 0, target = 0 }) {
  const safeProgress = Math.max(0, Math.min(100, Number(progress || 0)));

  return (
    <div className="ov__semiGauge">
      <svg viewBox="0 0 160 100" className="ov__semiGaugeSvg">
        <path
          d="M 22 78 A 58 58 0 0 1 138 78"
          fill="none"
          stroke="#e7edf5"
          strokeWidth="12"
          strokeLinecap="round"
          pathLength="100"
        />
        <path
          d="M 22 78 A 58 58 0 0 1 138 78"
          fill="none"
          stroke="#4fa792"
          strokeWidth="12"
          strokeLinecap="round"
          pathLength="100"
          strokeDasharray="100"
          strokeDashoffset={100 - safeProgress}
        />
        <line
          x1="80"
          y1="78"
          x2={80 + 34 * Math.cos(((180 - safeProgress * 1.8) * Math.PI) / 180)}
          y2={78 - 34 * Math.sin(((180 - safeProgress * 1.8) * Math.PI) / 180)}
          stroke="#8aa39a"
          strokeWidth="4"
          strokeLinecap="round"
        />
        <circle cx="80" cy="78" r="5" fill="#8aa39a" />
      </svg>

      <div className="ov__semiGaugeValue">
        {saved >= 1000 ? `${Math.round(saved / 1000)}K` : saved}
      </div>

      <div className="ov__semiGaugeScale">
        <span>0</span>
        <span>{target >= 1000 ? `${Math.round(target / 1000)}K` : target}</span>
      </div>

      <div className="ov__semiGaugeCaption">Target vs Achievement</div>
    </div>
  );
}

function HealthScoreRing({ score = 0, label = "Average" }) {
  const safeScore = Math.max(0, Math.min(100, Number(score || 0)));
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (safeScore / 100) * circumference;

  let accentClass = "ov__healthStatus--average";
  let ringColor = "#f59e0b";
  let faceColor = "#b45309";
  let mood = "average";

  if (safeScore >= 80) {
    accentClass = "ov__healthStatus--excellent";
    ringColor = "#22c55e";
    faceColor = "#16a34a";
    mood = "happy";
  } else if (safeScore >= 65) {
    accentClass = "ov__healthStatus--good";
    ringColor = "#22c55e";
    faceColor = "#16a34a";
    mood = "good";
  } else if (safeScore < 45) {
    accentClass = "ov__healthStatus--poor";
    ringColor = "#ef4444";
    faceColor = "#dc2626";
    mood = "sad";
  }

  return (
    <div className="ov__healthCardInner">
      <div className="ov__healthRingWrap">
        <svg viewBox="0 0 120 120" className="ov__healthRingSvg">
          <circle cx="60" cy="60" r="42" fill="none" stroke="#e7f1e7" strokeWidth="10" />
          <circle cx="60" cy="60" r="42" fill="none" stroke="#f5c542" strokeWidth="10" strokeDasharray="38 260" strokeLinecap="round" transform="rotate(140 60 60)" />
          <circle
            cx="60"
            cy="60"
            r="42"
            fill="none"
            stroke={ringColor}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            transform="rotate(-90 60 60)"
          />
          <circle cx="60" cy="60" r="24" fill="#f4fbf4" />
          <text x="60" y="50" textAnchor="middle" className="ov__healthRingScore">
            {safeScore}
          </text>

          <circle cx="52" cy="64" r="2.3" fill={faceColor} />
          <circle cx="68" cy="64" r="2.3" fill={faceColor} />

          {mood === "happy" || mood === "good" ? (
            <path d="M52 74 Q60 80 68 74" fill="none" stroke={faceColor} strokeWidth="2.5" strokeLinecap="round" />
          ) : mood === "sad" ? (
            <path d="M52 78 Q60 70 68 78" fill="none" stroke={faceColor} strokeWidth="2.5" strokeLinecap="round" />
          ) : (
            <line x1="53" y1="75" x2="67" y2="75" stroke={faceColor} strokeWidth="2.5" strokeLinecap="round" />
          )}
        </svg>
      </div>

      <div className="ov__healthContent">
        <div className="ov__healthLabelBig">{label}</div>
        <div className={`ov__healthStatus ${accentClass}`}>
          {label === "Excellent"
            ? "EXCELLENT"
            : label === "Good"
            ? "GOOD"
            : label === "Average"
            ? "AVERAGE"
            : label === "Needs Attention"
            ? "LOW"
            : "NO DATA"}
        </div>
        <p className="ov__healthNote">
          {safeScore >= 80
            ? "You’re doing great with savings and expense control."
            : safeScore >= 65
            ? "You’re on the right track!"
            : safeScore >= 45
            ? "Your finances are stable, but can improve."
            : "Needs attention on spending and savings."}
        </p>
      </div>
    </div>
  );
}

function AlertItem({ icon, title, subtitle, chip, accent = "blue" }) {
  return (
    <div className={`ov__alertItem ov__alertItem--${accent}`}>
      <div className="ov__alertItemIcon">{icon}</div>
      <div className="ov__alertItemContent">
        <div className="ov__alertItemTitle">{title}</div>
        <div className="ov__alertItemSubtitle">{subtitle}</div>
      </div>
      {chip ? <div className="ov__alertChip">{chip}</div> : null}
    </div>
  );
}

export default function Overview() {
  const [income, setIncome] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [savings, setSavings] = useState([]);
  const [insurance, setInsurance] = useState([]);
  const [lending, setLending] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const api = useMemo(() => {
    const instance = axios.create({
      baseURL: API_BASE_URL,
      timeout: 15000,
    });

    instance.interceptors.request.use((config) => {
      const token = readToken();
      if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    return instance;
  }, []);

  useEffect(() => {
    const load = async () => {
      const token = readToken();
      if (!token) {
        setError("Please login to see overview.");
        return;
      }

      setLoading(true);
      setError("");

      try {
        const results = await Promise.allSettled([
          api.get("/api/income/"),
          api.get("/api/expenses/"),
          api.get("/api/saving/"),
          api.get("/api/insurance/"),
          api.get("/api/loan/"),
        ]);

        const [incRes, expRes, savRes, insRes, lendRes] = results;

        setIncome(normalizeListResponse(incRes));
        setExpenses(normalizeListResponse(expRes));
        setSavings(normalizeListResponse(savRes));
        setInsurance(normalizeListResponse(insRes));
        setLending(normalizeListResponse(lendRes));
      } catch (err) {
        setError(
          err?.response?.data?.detail ||
            err?.response?.data?.message ||
            "Could not load overview data."
        );
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [api]);

  const totals = useMemo(() => {
  const now = new Date();
  const currentMonth = now.getMonth();
  const currentYear = now.getFullYear();

  const currentMonthKey = `${currentYear}-${String(currentMonth + 1).padStart(2, "0")}`;

  const totalIncome = income.reduce((sum, item) => {
    const d = toDate(getIncomeDate(item));
    if (!d) return sum;

    if (
      d.getMonth() !== currentMonth ||
      d.getFullYear() !== currentYear
    ) {
      return sum;
    }

    return sum + getIncomeAmount(item);
  }, 0);

  console.log(
  "CURRENT MONTH INCOME ROWS:",
  income.map((item) => {
    const d = toDate(getIncomeDate(item));
    return {
      rawDate: getIncomeDate(item),
      parsed: d,
      amount: getIncomeAmount(item),
      include:
        d &&
        d.getMonth() === currentMonth &&
        d.getFullYear() === currentYear,
    };
  })
);

  console.log(
    "INCOME MONTH CHECK:",
    income.map((item) => ({
      raw: item,
      rawDate: getIncomeDate(item),
      monthKey: getMonthKey(getIncomeDate(item)),
      amount: getIncomeAmount(item),
      currentMonthKey: currentMonthKey,
      include: getMonthKey(getIncomeDate(item)) === currentMonthKey,
    }))
  );

  const totalExpenses = expenses.reduce((sum, item) => {
    const d = toDate(getExpenseDate(item));
    if (
      !d ||
      d.getMonth() !== currentMonth ||
      d.getFullYear() !== currentYear
    ) {
      return sum;
    }
    return sum + getExpenseAmount(item);
  }, 0);

  const totalSavings = savings.reduce((sum, item) => {
    const d = toDate(getSavingEntryDate(item));
    if (
      !d ||
      d.getMonth() !== currentMonth ||
      d.getFullYear() !== currentYear
    ) {
      return sum;
    }
    return sum + getSavingAmount(item);
  }, 0);

  return { totalIncome, totalExpenses, totalSavings };
}, [income, expenses, savings]);
  
  const graphData = useMemo(() => {
    const months = buildLastThreeMonthLabels();
    const monthlyMap = {};

    months.forEach((m) => {
      monthlyMap[m.key] = 0;
    });

    expenses.forEach((item) => {
      const d = toDate(getExpenseDate(item));
      if (!d) return;

      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
      if (Object.prototype.hasOwnProperty.call(monthlyMap, key)) {
        monthlyMap[key] += getExpenseAmount(item);
      }
    });

    return months.map((m) => ({
      month: m.label,
      expense: monthlyMap[m.key] || 0,
    }));
  }, [expenses]);

  const hasAnyData =
    income.length > 0 ||
    expenses.length > 0 ||
    savings.length > 0 ||
    insurance.length > 0 ||
    lending.length > 0;

  const nearestGoal = useMemo(() => {
    if (!Array.isArray(savings) || savings.length === 0) return null;

    const today = new Date();

    const normalized = savings
      .map((item) => {
        const targetDateRaw = getSavingTargetDate(item);
        const targetDate = toDate(targetDateRaw);

        const daysLeft =
          targetDate instanceof Date
            ? Math.ceil(
                (new Date(
                  targetDate.getFullYear(),
                  targetDate.getMonth(),
                  targetDate.getDate()
                ) -
                  new Date(
                    today.getFullYear(),
                    today.getMonth(),
                    today.getDate()
                  )) /
                  (1000 * 60 * 60 * 24)
              )
            : Number.POSITIVE_INFINITY;

        return {
          name: getSavingName(item),
          saved: getSavingAmount(item),
          target: getSavingTarget(item),
          targetDate: targetDateRaw,
          progress: getGoalProgress(item),
          daysLeft,
        };
      })
      .filter((item) => item.target > 0);

    if (normalized.length === 0) return null;

    normalized.sort((a, b) => {
      const aNoDate = !Number.isFinite(a.daysLeft);
      const bNoDate = !Number.isFinite(b.daysLeft);

      if (aNoDate && bNoDate) return b.progress - a.progress;
      if (aNoDate) return 1;
      if (bNoDate) return -1;

      return a.daysLeft - b.daysLeft;
    });

    return normalized[0] || null;
  }, [savings]);

  const upcomingInsurance = useMemo(() => {
    if (!Array.isArray(insurance) || insurance.length === 0) return null;

    const mapped = insurance
      .map((item) => ({
        raw: item,
        rawKeys: Object.keys(item || {}),
        name: getInsuranceName(item),
        date: getInsuranceDate(item),
        amount: toNumber(
          item?.premium_amount ??
            item?.amount ??
            item?.premium ??
            item?.premiumValue
        ),
        daysLeft: daysUntil(getInsuranceDate(item)),
      }))
      .filter((item) => item.date)
      .sort((a, b) => {
        const aDays = a.daysLeft ?? Number.POSITIVE_INFINITY;
        const bDays = b.daysLeft ?? Number.POSITIVE_INFINITY;
        return aDays - bDays;
      });

    return mapped[0] || null;
  }, [insurance]);

  const upcomingLending = useMemo(() => {
    if (!Array.isArray(lending) || lending.length === 0) return null;

    const mapped = lending
      .map((item) => ({
        raw: item,
        name: getLendingName(item),
        date: getLendingDate(item),
        amount: toNumber(item?.amount ?? item?.principal ?? item?.lent_amount),
        daysLeft: daysUntil(getLendingDate(item)),
      }))
      .filter((item) => item.date)
      .sort((a, b) => {
        const aDays = a.daysLeft ?? Number.POSITIVE_INFINITY;
        const bDays = b.daysLeft ?? Number.POSITIVE_INFINITY;
        return aDays - bDays;
      });

    return mapped[0] || null;
  }, [lending]);
  const healthScore = useMemo(() => {
  const incomeTotal = totals.totalIncome || 0;
  const expensesTotal = totals.totalExpenses || 0;

  if (incomeTotal <= 0) {
    return { score: 0, label: "No Data" };
  }

  const expenseRatio = expensesTotal / incomeTotal;
  const surplusRate = (incomeTotal - expensesTotal) / incomeTotal;

  const validGoals = savings.filter((item) => getSavingTarget(item) > 0);
  const avgGoalProgress =
    validGoals.length > 0
      ? validGoals.reduce((sum, item) => sum + getGoalProgress(item), 0) /
        validGoals.length
      : 0;

  let score = 0;

  if (expenseRatio <= 0.4) score += 40;
  else if (expenseRatio <= 0.5) score += 34;
  else if (expenseRatio <= 0.6) score += 28;
  else if (expenseRatio <= 0.7) score += 20;
  else if (expenseRatio <= 0.8) score += 12;
  else if (expenseRatio <= 1) score += 6;
  else score += 0;

  if (surplusRate >= 0.4) score += 35;
  else if (surplusRate >= 0.3) score += 28;
  else if (surplusRate >= 0.2) score += 20;
  else if (surplusRate >= 0.1) score += 12;
  else if (surplusRate >= 0) score += 6;
  else score += 0;

  score += Math.min(avgGoalProgress, 100) * 0.15;

  let alertScore = 10;

  if (upcomingInsurance?.daysLeft != null && upcomingInsurance.daysLeft < 0) {
    alertScore -= 5;
  } else if (
    upcomingInsurance?.daysLeft != null &&
    upcomingInsurance.daysLeft <= 7
  ) {
    alertScore -= 2;
  }

  if (upcomingLending?.daysLeft != null && upcomingLending.daysLeft < 0) {
    alertScore -= 5;
  } else if (
    upcomingLending?.daysLeft != null &&
    upcomingLending.daysLeft <= 7
  ) {
    alertScore -= 2;
  }

  score += Math.max(0, alertScore);

  const finalScore = Math.max(0, Math.min(100, Math.round(score)));

  let label = "Needs Attention";
  if (finalScore >= 80) label = "Excellent";
  else if (finalScore >= 65) label = "Good";
  else if (finalScore >= 45) label = "Average";

  return { score: finalScore, label };
}, [totals, savings, upcomingInsurance, upcomingLending]);

  return (
    <div className="ov">
      <div className="ov__hero">
        <div>
          <h2 className="ov__title">Overview</h2>
          <p className="ov__subtitle">Quick summary of your finance data</p>
        </div>
      </div>

      {error && <div className="ov__alert">{error}</div>}
      {loading && <div className="ov__alert">Loading...</div>}

      <div className="ov__grid ov__grid--three">
        <div className="ov__card">
          <div className="ov__icon ov__icon--green">
            <FaArrowUp />
          </div>
          <div>
            <div className="ov__label">Income</div>
            <div className="ov__value">{inr(totals.totalIncome)}</div>
          </div>
        </div>

        <div className="ov__card">
          <div className="ov__icon ov__icon--red">
            <FaArrowDown />
          </div>
          <div>
            <div className="ov__label">Expenses</div>
            <div className="ov__value">{inr(totals.totalExpenses)}</div>
          </div>
        </div>

        <div className="ov__card ov__card--health ov__card--healthRich">
          <div className="ov__label ov__label--healthTitle">Financial Health</div>
          <HealthScoreRing score={healthScore.score} label={healthScore.label} />
        </div>
      </div>

      <div className="ov__mainGrid">
        <div className="ov__panel ov__panel--chart">
          <div className="ov__panelHeader">
            <h3>
              <FaChartLine /> Monthly Expense Trend
            </h3>
          </div>

          {expenses.length === 0 ? (
            <div className="ov__emptyState">
              <div className="ov__emptyIcon">
                <FaInfoCircle />
              </div>
              <h4>No expense data yet</h4>
              <p>
                Add your first expense and here you will see the expense trend for the last 3 months.
              </p>
            </div>
          ) : (
            <div className="ov__chartWrap">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={graphData}
                  margin={{ top: 10, right: 12, left: 0, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="expenseFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#ef4444" stopOpacity={0.28} />
                      <stop offset="100%" stopColor="#ef4444" stopOpacity={0.04} />
                    </linearGradient>
                  </defs>

                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                    stroke="#e9eef5"
                  />
                  <XAxis
                    dataKey="month"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: "#667085", fontSize: 13 }}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: "#667085", fontSize: 13 }}
                    tickFormatter={(value) => `₹${Math.round(value / 1000)}k`}
                  />
                  <Tooltip
                    formatter={(value) => [inr(value), "Expenses"]}
                    contentStyle={{
                      borderRadius: "12px",
                      border: "1px solid #e5ecf6",
                      boxShadow: "0 10px 25px rgba(15, 23, 42, 0.08)",
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="expense"
                    stroke="#ef4444"
                    strokeWidth={3}
                    fill="url(#expenseFill)"
                    dot={{ r: 4, fill: "#ef4444", strokeWidth: 0 }}
                    activeDot={{ r: 6, fill: "#ef4444", strokeWidth: 0 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="ov__panel ov__panel--side">
          {!hasAnyData ? (
            <div className="ov__welcomeCard">
              <h3>Welcome to FinGrrow</h3>
              <p>
                Start by adding your income, expenses, savings, insurance, or lending details.
              </p>

              <div className="ov__welcomeStats">
                <div>
                  <span>Income</span>
                  <strong>₹0</strong>
                </div>
                <div>
                  <span>Expenses</span>
                  <strong>₹0</strong>
                </div>
                <div>
                  <span>Savings</span>
                  <strong>₹0</strong>
                </div>
              </div>
            </div>
          ) : (
            <div className="ov__sideStack">
              {nearestGoal ? (
                <div className="ov__goalCardCompact">
                  <div className="ov__goalCardHead">
                    <div>
                      <div className="ov__goalCardLabel">Nearest Goal</div>
                      <h3 className="ov__goalCardTitle">{nearestGoal.name}</h3>
                    </div>

                    <div className="ov__goalCardDate">
                      {formatMonthYear(nearestGoal.targetDate)}
                    </div>
                  </div>

                  <div className="ov__goalCardAmount">{inr(nearestGoal.saved)}</div>

                  <div className="ov__goalCardBody">
                    <div className="ov__goalCardInfo">
                      <div className="ov__goalMiniInfo">
                        <span>Target Achieved</span>
                        <strong>{inr(nearestGoal.saved)}</strong>
                      </div>

                      <div className="ov__goalMiniInfo">
                        <span>Total Target</span>
                        <strong>{inr(nearestGoal.target)}</strong>
                      </div>
                    </div>

                    <div className="ov__goalCardGaugeWrap">
                      <SemiCircleGauge
                        progress={nearestGoal.progress}
                        saved={nearestGoal.saved}
                        target={nearestGoal.target}
                      />
                    </div>
                  </div>
                </div>
              ) : null}

              <div className="ov__upcomingCard">
                <div className="ov__upcomingHead">
                  <div className="ov__upcomingTitle">Upcoming Alerts</div>
                  <div className="ov__upcomingBadge">
                    <FaCalendarAlt />
                    <span>Next Dates</span>
                  </div>
                </div>

                <div className="ov__upcomingList">
                  {upcomingInsurance ? (
                    <AlertItem
                      icon={<FaShieldAlt />}
                      title={upcomingInsurance.name}
                      subtitle={`Insurance due on ${formatDateShort(
                        upcomingInsurance.date
                      )}`}
                      chip={
                        upcomingInsurance.daysLeft == null
                          ? "No date"
                          : upcomingInsurance.daysLeft < 0
                          ? "Passed"
                          : `${upcomingInsurance.daysLeft}d`
                      }
                      accent="emerald"
                    />
                  ) : (
                    <AlertItem
                      icon={<FaShieldAlt />}
                      title="No insurance due"
                      subtitle="No upcoming insurance date found"
                      chip="—"
                      accent="muted"
                    />
                  )}

                  {upcomingLending ? (
                    <AlertItem
                      icon={<FaHandHoldingUsd />}
                      title={upcomingLending.name}
                      subtitle={`Lending due on ${formatDateShort(
                        upcomingLending.date
                      )}`}
                      chip={
                        upcomingLending.daysLeft == null
                          ? "No date"
                          : upcomingLending.daysLeft < 0
                          ? "Passed"
                          : `${upcomingLending.daysLeft}d`
                      }
                      accent="blue"
                    />
                  ) : (
                    <AlertItem
                      icon={<FaHandHoldingUsd />}
                      title="No lending due"
                      subtitle="No upcoming lending date found"
                      chip="—"
                      accent="muted"
                    />
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}