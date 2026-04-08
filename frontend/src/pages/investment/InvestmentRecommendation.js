import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import "./investmentRecommendation.css";

//recommendation changes
function ScoreSummary({ item }) {
  const breakdown = item?.rationale?.score_breakdown;
  const overview = item?.rationale?.calculation_overview;
  const factors = item?.rationale?.user_friendly_factors || [];

  if (!breakdown && !overview && !factors.length) return null;

  return (
    <div className="invReco-scoreSummary">
      <div className="invReco-scoreSummaryTitle">
        How this score was calculated
      </div>

      {overview && (
        <p className="invReco-scoreSummaryText">{overview}</p>
      )}

      {breakdown && (
        <div className="invReco-scoreMiniGrid">
          <div className="invReco-scoreMiniCard">
            <span>Base Score</span>
            <strong>{breakdown.base_score}</strong>
          </div>

          <div className="invReco-scoreMiniCard">
            <span>Advanced Score</span>
            <strong>{breakdown.advanced_score}</strong>
          </div>

          <div className="invReco-scoreMiniCard">
            <span>Final Score</span>
            <strong>{breakdown.final_score}</strong>
          </div>
        </div>
      )}

      {factors.length > 0 && (
        <ul className="invReco-factorList">
          {factors.map((f, i) => (
            <li key={i}>{f}</li>
          ))}
        </ul>
      )}
    </div>
  );
}




const API_BASE_URL =
  (process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const TOKEN_KEYS = ["access_token", "token", "accessToken", "authToken", "jwt"];

const readToken = () => {
  for (const k of TOKEN_KEYS) {
    const v = localStorage.getItem(k);
    if (v) return v;
  }
  for (const k of TOKEN_KEYS) {
    const v = sessionStorage.getItem(k);
    if (v) return v;
  }
  return null;
};

function inr(x) {
  return Number(x || 0).toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  });
}

function num(x, fallback = 0) {
  const n = Number(x);
  return Number.isFinite(n) ? n : fallback;
}

function formatDate(value) {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return value;
  }
}

function SuitabilityBadge({ value }) {
  const v = String(value || "").toLowerCase();

  let cls = "invReco-badge invReco-badge-neutral";
  if (v === "excellent") cls = "invReco-badge invReco-badge-good";
  else if (v === "good") cls = "invReco-badge invReco-badge-info";
  else if (v === "watch") cls = "invReco-badge invReco-badge-warn";

  return <span className={cls}>{value || "-"}</span>;
}

function ProgressBar({ value }) {
  const pct = Math.max(0, Math.min(num(value, 0), 100));
  return (
    <div className="invReco-progressTrack">
      <div className="invReco-progressFill" style={{ width: `${pct}%` }} />
    </div>
  );
}

function SummaryStrip({ rows }) {
  if (!rows.length) return null;

  const first = rows[0];

  return (
    <div className="invReco-summaryGrid">
      <div className="invReco-summaryCard">
        <div className="invReco-summaryLabel">Monthly Income</div>
        <div className="invReco-summaryValue">{inr(first.monthly_income_snapshot)}</div>
      </div>

      <div className="invReco-summaryCard">
        <div className="invReco-summaryLabel">Last Month Expenses</div>
        <div className="invReco-summaryValue">{inr(first.last_month_expense_snapshot)}</div>
      </div>

      <div className="invReco-summaryCard">
        <div className="invReco-summaryLabel">Free Cashflow</div>
        <div className="invReco-summaryValue">{inr(first.free_cashflow_snapshot)}</div>
      </div>

      <div className="invReco-summaryCard">
        <div className="invReco-summaryLabel">Safe Investment Pool</div>
        <div className="invReco-summaryValue">{inr(first.recommendation_pool_snapshot)}</div>
      </div>
    </div>
  );
}

function FundReasonList({ item }) {
  const rationale = item?.rationale || {};
  const points = [];

  if (rationale.category_fit) points.push(rationale.category_fit);
  if (rationale.horizon_fit) points.push(rationale.horizon_fit);
  if (rationale.progress_fit) points.push(rationale.progress_fit);
  if (rationale.risk_style) points.push(rationale.risk_style);
  if (rationale.cost_fit) points.push(rationale.cost_fit);

  if (!points.length && item?.summary) {
    points.push(item.summary);
  }

  return (
    <div className="invReco-whyBox">
      <div className="invReco-whyTitle">Why this fund</div>
      <ul className="invReco-whyList">
        {points.map((p, idx) => (
          <li key={`${item.id}-why-${idx}`}>{p}</li>
        ))}
      </ul>
    </div>
  );
}

function GoalCard({ goalName, items }) {
  const first = items[0];

  const progressPct =
    first.goal_progress_pct != null
      ? num(first.goal_progress_pct)
      : num(first.goal_target_amount) > 0
      ? (num(first.goal_saved_amount) / num(first.goal_target_amount)) * 100
      : 0;

  const totalSuggestedForGoal = items.reduce(
    (sum, item) => sum + num(item.suggested_monthly_amount),
    0
  );

  const requiredMonthly = num(first.required_monthly_amount);
  const isUnderfunded = totalSuggestedForGoal < requiredMonthly;

  return (
    <div className="invReco-goalCard">
      <div className="invReco-goalHeader">
        <div>
          <h4 className="invReco-goalTitle">{goalName || "Unnamed Goal"}</h4>
          <div className="invReco-goalMeta">
            <span>Target: {inr(first.goal_target_amount)}</span>
            <span>Saved: {inr(first.goal_saved_amount)}</span>
            <span>Remaining: {inr(first.goal_remaining_amount)}</span>
            <span>Target Date: {formatDate(first.goal_target_date)}</span>
            <span>
              Horizon:{" "}
              {first.suggested_horizon_months
                ? `${first.suggested_horizon_months} months`
                : "-"}
            </span>
            <span>Priority: {num(first.goal_priority_score).toFixed(3)}</span>
          </div>
        </div>

        <div className="invReco-progressBox">
          <div className="invReco-progressTop">
            <span>Progress</span>
            <strong>{progressPct.toFixed(2)}%</strong>
          </div>
          <ProgressBar value={progressPct} />
        </div>
      </div>

      <div className="invReco-goalStats">
        <div className="invReco-goalStat">
          <div className="invReco-goalStatLabel">Required Monthly</div>
          <div className="invReco-goalStatValue">{inr(requiredMonthly)}</div>
        </div>

        <div className="invReco-goalStat">
          <div className="invReco-goalStatLabel">Recommended for this Goal</div>
          <div className="invReco-goalStatValue">{inr(totalSuggestedForGoal)}</div>
        </div>
      </div>

      {isUnderfunded && (
        <div className="invReco-warning">
          This goal currently needs more than the realistically affordable monthly amount.
        </div>
      )}

      <div className="invReco-tableWrap">
        <table className="invReco-table">
          <thead>
            <tr>
              <th>Fund</th>
              <th>AMC</th>
              <th>Category</th>
              <th>Type</th>
              <th>Suggested Monthly</th>
              <th>Score</th>
              <th>Suitability</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id}>
                <td>
                    <div className="invReco-fundName">{r.scheme_name || "-"}</div>

                   <div className="invReco-summary">
    
                    {/* ✅ NEW: Score Explanation */}
                     <ScoreSummary item={r} />

                    {/* OLD summary (optional) */}
                     {r.summary && <div>{r.summary}</div>}

                     {/* ✅ Reasons (backend se aaye hue) */}
                    {r?.rationale &&
                      Object.entries(r.rationale)
                        .filter(([key, val]) =>
                          typeof val === "string" &&
                         key !== "calculation_overview"
                       )
                       .map(([key, val], idx) => (
                         <div key={idx}>• {val}</div>
                      ))}
                </div>
                </td>
                <td>{r.amc || "-"}</td>
                <td>{r.category_key || "-"}</td>
                <td>{r.fund_type || "-"}</td>
                <td>{inr(r.suggested_monthly_amount)}</td>
                <td>{r.score ?? "-"}</td>
                <td>
                  <SuitabilityBadge value={r.suitability} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="invReco-whySection">
        <div className="invReco-whySectionTitle">Why these funds?</div>
        <div className="invReco-whyCards">
          {items.map((item) => (
            <FundReasonList key={`reason-${item.id}`} item={item} />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function InvestmentRecommendation() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [msg, setMsg] = useState("");

  const getHeaders = () => {
    const token = readToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const loadLatestRecommendations = async () => {
    const token = readToken();

    if (!token) {
      setMsg("You are not logged in. Please login first.");
      setRows([]);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setMsg("");

      const res = await axios.get(
        `${API_BASE_URL}/api/investment/recommendations/latest/`,
        {
          headers: getHeaders(),
          timeout: 20000,
        }
      );

      setRows(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      console.error("LOAD RECOMMENDATIONS ERROR:", e?.response?.data || e?.message);
      setMsg(
        e?.response?.data?.detail ||
          e?.response?.data?.message ||
          "Failed to load recommendations."
      );
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  const buildRecommendations = async () => {
    const token = readToken();

    if (!token) {
      setMsg("You are not logged in. Please login first.");
      return;
    }

    try {
      setBuilding(true);
      setMsg("");

      await axios.post(
        `${API_BASE_URL}/api/investment/recommendations/build/`,
        {},
        {
          headers: getHeaders(),
          timeout: 30000,
        }
      );

      await loadLatestRecommendations();
      setMsg("Recommendations refreshed successfully.");
    } catch (e) {
      console.error("BUILD RECOMMENDATIONS ERROR:", e?.response?.data || e?.message);
      setMsg(
        e?.response?.data?.detail ||
          e?.response?.data?.message ||
          "Failed to build recommendations."
      );
    } finally {
      setBuilding(false);
    }
  };

  useEffect(() => {
    loadLatestRecommendations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const groupedGoals = useMemo(() => {
    const grouped = {};

    for (const row of rows) {
      const key = row.goal_name || "Unnamed Goal";
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(row);
    }

    return Object.entries(grouped).map(([goalName, items]) => ({
      goalName,
      items,
    }));
  }, [rows]);

  return (
    <div className="invReco-wrap">
      <div className="invReco-top">
        <div>
          <h3 className="invReco-title">Investment Recommendations</h3>
          <p className="invReco-subtitle">
            Goal-based recommendations using your monthly income, previous month
            expenses, goal progress, and available active, passive, and debt funds.
          </p>
        </div>

        <button
          type="button"
          className="invReco-btn"
          onClick={buildRecommendations}
          disabled={building}
        >
          {building ? "Refreshing..." : "Refresh Recommendations"}
        </button>
      </div>

      {msg && <div className="invReco-msg">{msg}</div>}

      {loading ? (
        <div className="invReco-empty">Loading recommendations...</div>
      ) : rows.length === 0 ? (
        <div className="invReco-empty">
          No recommendations available yet. Click “Refresh Recommendations”.
        </div>
      ) : (
        <>
          <SummaryStrip rows={rows} />

          <div className="invReco-goalsWrap">
            {groupedGoals.map((group) => (
              <GoalCard
                key={group.goalName}
                goalName={group.goalName}
                items={group.items}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}