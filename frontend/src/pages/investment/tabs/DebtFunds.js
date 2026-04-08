import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import "./DebtFunds.css";

import { Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

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

const AMCS = ["hdfc", "icici", "axis", "sbi"];

const PERIOD_OPTIONS = [
  { key: "1M", field: "cagr_1M" },
  { key: "6M", field: "cagr_6M" },
  { key: "1Y", field: "cagr_1Y" },
  { key: "3Y", field: "cagr_3Y" },
  { key: "5Y", field: "cagr_5Y" },
  { key: "SI", field: "cagr_SI" },
];

function parseCagrValue(v) {
  if (v === null || v === undefined) return null;
  const s = String(v).trim();
  if (!s || s === "-" || s.toLowerCase() === "na" || s.toLowerCase() === "nan") return null;
  const num = Number(s.replace("%", "").trim());
  return Number.isFinite(num) ? num : null;
}

const fmtPct = (v) => {
  const num = parseCagrValue(v);
  if (num === null) return "-";
  return `${num.toFixed(2)}%`;
};

function dedupeRows(data) {
  const map = new Map();

  for (const row of data || []) {
    const category = String(row?.category || "").toLowerCase();
    const schemeCode = String(row?.scheme_code || "").trim();
    const label = String(row?.label || "").trim().toLowerCase();

    const key = schemeCode
      ? `${category}__${schemeCode}`
      : `${category}__${label}`;

    if (!map.has(key)) {
      map.set(key, row);
      continue;
    }

    const prev = map.get(key);

    const prevScore =
      [
        prev?.cagr_1M,
        prev?.cagr_6M,
        prev?.cagr_1Y,
        prev?.cagr_3Y,
        prev?.cagr_5Y,
        prev?.cagr_SI,
      ].filter((x) => parseCagrValue(x) !== null).length;

    const currScore =
      [
        row?.cagr_1M,
        row?.cagr_6M,
        row?.cagr_1Y,
        row?.cagr_3Y,
        row?.cagr_5Y,
        row?.cagr_SI,
      ].filter((x) => parseCagrValue(x) !== null).length;

    if (currScore >= prevScore) {
      map.set(key, row);
    }
  }

  return Array.from(map.values());
}

export default function DebtFunds() {
  const [category, setCategory] = useState("debt_govt");
  const [periodKey, setPeriodKey] = useState("1Y");
  const [selectedAmc, setSelectedAmc] = useState(null);

  const [rows, setRows] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const period = useMemo(
    () => PERIOD_OPTIONS.find((p) => p.key === periodKey) || PERIOD_OPTIONS[2],
    [periodKey]
  );

  const fetchDebt = useCallback(async () => {
    const token = readToken();

    if (!token) {
      setErr("You are not logged in. Please login first.");
      setRows([]);
      return;
    }

    setLoading(true);
    setErr("");

    try {
      const res = await axios.get(`${API_BASE_URL}/api/investment/fixed-assets/debt-funds/`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { category },
        timeout: 100000,
      });

      const data = Array.isArray(res.data) ? res.data : [];
      const unique = dedupeRows(data);
      setRows(unique);
    } catch (e) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail || e?.message || "Failed to load debt funds.";
      setErr(`${detail}${status ? ` (HTTP ${status})` : ""}`);
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [category]);

  useEffect(() => {
    fetchDebt();
  }, [fetchDebt]);

  const filtered = useMemo(() => {
    let r = rows;

    if (selectedAmc) {
      r = r.filter((x) => String(x.amc || "").toLowerCase() === selectedAmc);
    }

    return r;
  }, [rows, selectedAmc]);

  const chartRows = useMemo(() => {
    const field = period.field;

    const items = filtered
      .map((r) => ({
        label: r.label || "Fund",
        value: parseCagrValue(r[field]),
      }))
      .filter((x) => x.value !== null);

    items.sort((a, b) => b.value - a.value);
    return items.slice(0, 10);
  }, [filtered, period]);

  const barData = useMemo(() => {
    return {
      labels: chartRows.map((x) => x.label),
      datasets: [
        {
          label: `CAGR ${period.key} (%)`,
          data: chartRows.map((x) => x.value),
          borderWidth: 1,
          borderRadius: 14,
          barThickness: 44,
        },
      ],
    };
  }, [chartRows, period]);

  const barOptions = useMemo(() => {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom" },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${Number(ctx.parsed.y).toFixed(2)}%`,
          },
        },
      },
      scales: {
        y: {
          ticks: { callback: (v) => `${v}%` },
          title: { display: true, text: "Return (%)" },
          grid: { color: "rgba(0,0,0,0.08)" },
        },
        x: {
          grid: { display: false },
          ticks: {
            maxRotation: 0,
            minRotation: 0,
            callback: function (value) {
              const label = this.getLabelForValue(value);
              return label.length > 18 ? `${label.slice(0, 18)}…` : label;
            },
          },
        },
      },
    };
  }, [chartRows, period]);

  return (
    <div className="debt-wrap">
      <div className="debt-top">
        <div className="debt-title">
          <h3>Debt Funds (Govt / Corporate)</h3>
          <div className="debt-sub">
            Filter by category, AMC, and period. Returns update from MFAPI (cached).
          </div>
        </div>

        <div className="debt-actions">
          <button
            type="button"
            className="debt-btn primary"
            onClick={fetchDebt}
            disabled={loading}
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      <div className="debt-row">
        <div className="debt-row-label">Type:</div>
        <div className="debt-chips">
          <button
            type="button"
            className={`debt-chip ${category === "debt_govt" ? "is-active" : ""}`}
            onClick={() => {
              setCategory("debt_govt");
              setSelectedAmc(null);
            }}
          >
            Govt Sector
          </button>

          <button
            type="button"
            className={`debt-chip ${category === "debt_corp" ? "is-active" : ""}`}
            onClick={() => {
              setCategory("debt_corp");
              setSelectedAmc(null);
            }}
          >
            Corporate Bond
          </button>
        </div>
      </div>

      <div className="debt-row">
        <div className="debt-row-label">AMC:</div>
        <div className="debt-chips">
          <button
            type="button"
            className={`debt-chip ${!selectedAmc ? "is-active" : ""}`}
            onClick={() => setSelectedAmc(null)}
          >
            All AMC
          </button>

          {AMCS.map((a) => (
            <button
              key={a}
              type="button"
              className={`debt-chip ${selectedAmc === a ? "is-active" : ""}`}
              onClick={() => setSelectedAmc(a)}
            >
              {a.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      <div className="debt-row">
        <div className="debt-row-label">Period:</div>
        <div className="debt-chips">
          {PERIOD_OPTIONS.map((p) => (
            <button
              key={p.key}
              type="button"
              className={`debt-chip ${periodKey === p.key ? "is-active" : ""}`}
              onClick={() => setPeriodKey(p.key)}
            >
              {p.key}
            </button>
          ))}
        </div>
      </div>

      {err && <div className="debt-alert">{err}</div>}
      {!err && loading && <div className="debt-loading">Loading…</div>}

      {!err && !loading && (
        <>
          <div className="debt-meta">
            Rows: <b>{filtered.length}</b> • Showing top 10 by{" "}
            <span className="debt-pill">{period.key}</span>
          </div>

          {chartRows.length > 0 ? (
            <div className="debt-chart">
              <Bar data={barData} options={barOptions} />
            </div>
          ) : (
            <div style={{ marginTop: 12, color: "#b45309", fontSize: 13 }}>
              Chart is blank because data for <b>{period.field}</b> is missing in API response.
            </div>
          )}

          <div className="debt-table-wrap">
            <table className="debt-table">
              <thead>
                <tr>
                  <th className="debt-th">Fund</th>
                  <th className="debt-th">AMC</th>
                  <th className="debt-th">As of</th>
                  <th className="debt-th">1M</th>
                  <th className="debt-th">6M</th>
                  <th className="debt-th">1Y</th>
                  <th className="debt-th">3Y</th>
                  <th className="debt-th">5Y</th>
                  <th className="debt-th">SI</th>
                  <th className="debt-th">Status</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r, idx) => (
                  <tr key={`${r.category || "debt"}-${r.scheme_code || idx}`}>
                    <td className="debt-td debt-td-strong">{r.label || "-"}</td>
                    <td className="debt-td">{String(r.amc || "-").toUpperCase()}</td>
                    <td className="debt-td">{r.as_of || "-"}</td>

                    <td className="debt-td">{fmtPct(r.cagr_1M)}</td>
                    <td className="debt-td">{fmtPct(r.cagr_6M)}</td>
                    <td className="debt-td">{fmtPct(r.cagr_1Y)}</td>
                    <td className="debt-td">{fmtPct(r.cagr_3Y)}</td>
                    <td className="debt-td">{fmtPct(r.cagr_5Y)}</td>
                    <td className="debt-td">{fmtPct(r.cagr_SI)}</td>
                    <td className="debt-td">{r._error ? "Partial" : "OK"}</td>
                  </tr>
                ))}

                {filtered.length === 0 && (
                  <tr>
                    <td className="debt-td" colSpan={10}>
                      No debt fund data found for this filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}