import React, { useEffect, useMemo, useState, useCallback } from "react";
import axios from "axios";
import "./ActivePassiveFunds.css";

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

const API_BASE_URL = (process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000").replace(
  /\/$/,
  ""
);

/* ---------- TOKEN UTILS ---------- */
const TOKEN_KEYS = ["token", "accessToken", "authToken", "jwt", "access_token"];
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

const AMCS = [
  { key: "HDFC", label: "HDFC" },
  { key: "ICICI", label: "ICICI" },
  { key: "AXIS", label: "Axis" },
  { key: "SBI", label: "SBI" },
];

/**
 * ✅ EXACT categories that exist in your mf_cagr_summary.csv / backend
 */
const ACTIVE_CATEGORY_OPTIONS = [
  { key: "largecap", label: "Large Cap" },
  { key: "midcap", label: "Mid Cap" },
  { key: "smallcap", label: "Small Cap" },
  { key: "multicap", label: "Multi Cap" },
  { key: "flexicap", label: "Flexi Cap" },
  { key: "balanced_advantage", label: "Balanced Advantage" },
  { key: "multi_asset", label: "Multi Asset" },
  { key: "hybrid_conservative", label: "Hybrid Conservative" },
  { key: "hybrid_aggressive", label: "Hybrid Aggressive" },
];

const PASSIVE_CATEGORY_OPTIONS = [
  { key: "nifty50", label: "Nifty 50" },
  { key: "bse", label: "BSE (Sensex/500)" },
  { key: "midcap150", label: "Nifty Midcap 150" },
  { key: "smallcap250", label: "Nifty Smallcap 250" },
];

/* ---------- Period selector (maps to API fields) ---------- */
const PERIOD_OPTIONS = [
  { key: "1M", label: "1M", field: "cagr_1M" },
  { key: "6M", label: "6M", field: "cagr_6M" },
  { key: "1Y", label: "1Y", field: "cagr_1Y" },
  { key: "3Y", label: "3Y", field: "cagr_3Y" },
  { key: "5Y", label: "5Y", field: "cagr_5Y" },
  { key: "SI", label: "SI", field: "cagr_SI" },
];

/* ---------- helper: parse "12.34", "12.34%", "-", null -> number or null ---------- */
function parseCagrValue(v) {
  if (v === null || v === undefined) return null;
  const s = String(v).trim();
  if (!s || s === "-" || s.toLowerCase() === "na" || s.toLowerCase() === "nan") return null;
  const cleaned = s.replace("%", "").trim();
  const num = Number(cleaned);
  return Number.isFinite(num) ? num : null;
}

/* ---------- formatting helpers (UI only) ---------- */
function formatPct(v) {
  const n = parseCagrValue(v);
  if (n === null) return "-";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}
function formatNav(v) {
  if (v === null || v === undefined || v === "-") return "-";
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  return n >= 100 ? n.toFixed(2) : n.toFixed(4);
}
function truncLabel(s, max = 22) {
  const t = String(s || "");
  return t.length > max ? `${t.slice(0, max)}…` : t;
}

export default function ActivePassiveFunds() {
  const [mode, setMode] = useState(null); // null | "ACTIVE" | "PASSIVE"
  const [categoryKey, setCategoryKey] = useState(null);
  const [periodKey, setPeriodKey] = useState("1Y");

  /* ---------- mf-cagr-summary data ---------- */
  const [mfRows, setMfRows] = useState([]);
  const [mfLoading, setMfLoading] = useState(false);
  const [mfErr, setMfErr] = useState("");

  const [selectedAmc, setSelectedAmc] = useState(null);

  const categoryOptions = useMemo(() => {
    if (mode === "PASSIVE") return PASSIVE_CATEGORY_OPTIONS;
    if (mode === "ACTIVE") return ACTIVE_CATEGORY_OPTIONS;
    return [];
  }, [mode]);

  useEffect(() => {
    if (!mode) {
      setCategoryKey(null);
      return;
    }
    if (mode === "ACTIVE") setCategoryKey("largecap");
    if (mode === "PASSIVE") setCategoryKey("nifty50");
    setSelectedAmc(null);
  }, [mode]);

  const selectedBucket = mode ? mode.toLowerCase() : null; // active | passive
  const selectedCategory = categoryKey;

  const selectedPeriod = useMemo(() => {
    return PERIOD_OPTIONS.find((p) => p.key === periodKey) || PERIOD_OPTIONS[2];
  }, [periodKey]);

  /* ---------- fetch mf-cagr-summary ---------- */
  const fetchMfCagr = useCallback(async () => {
    const token = readToken();
    if (!token) {
      setMfErr("You are not logged in. Please login first.");
      setMfRows([]);
      return;
    }
    if (!selectedBucket || !selectedCategory) return;

    setMfLoading(true);
    setMfErr("");

    try {
      const res = await axios.get(`${API_BASE_URL}/api/investment/mf-cagr-summary/`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { bucket: selectedBucket, category: selectedCategory },
        timeout: 20000,
      });

      const data = Array.isArray(res.data) ? res.data : res.data?.results || [];
      setMfRows(data);
    } catch (err) {
      const status = err?.response?.status;
      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        err?.message ||
        "Failed to load MF CAGR summary.";
      setMfErr(`${detail}${status ? ` (HTTP ${status})` : ""}`);
      setMfRows([]);
    } finally {
      setMfLoading(false);
    }
  }, [selectedBucket, selectedCategory]);

  useEffect(() => {
    if (!mode || !selectedCategory) return;
    fetchMfCagr();
  }, [mode, selectedCategory, fetchMfCagr]);

  useEffect(() => {
    const handler = () => {
      if (!mode || !selectedCategory) return;
      fetchMfCagr();
    };
    window.addEventListener("auth-token-changed", handler);
    return () => window.removeEventListener("auth-token-changed", handler);
  }, [mode, selectedCategory, fetchMfCagr]);

  /* ---------- filter rows (AMC filter only) ---------- */
  const filteredRows = useMemo(() => {
    if (!mfRows?.length || !selectedBucket || !selectedCategory) return [];
    return mfRows.filter((r) => {
      const okBucket = String(r.bucket || "").toLowerCase() === selectedBucket;
      const okCat = String(r.category || "").toLowerCase() === String(selectedCategory).toLowerCase();
      const okAmc = selectedAmc
        ? String(r.amc || "").toUpperCase() === String(selectedAmc).toUpperCase()
        : true;
      return okBucket && okCat && okAmc;
    });
  }, [mfRows, selectedBucket, selectedCategory, selectedAmc]);

  const latestSyncedAt = useMemo(() => {
    if (!filteredRows.length) return null;
    const values = filteredRows.map((r) => r.synced_at).filter(Boolean);
    return values.length ? values[0] : null;
  }, [filteredRows]);

  /* ---------- chart rows for selected period ---------- */
  const chartRows = useMemo(() => {
    const field = selectedPeriod.field;

    const rows = filteredRows
      .map((r) => ({
        label: r.label || r.scheme_name || "Fund",
        value: parseCagrValue(r[field]),
      }))
      .filter((x) => x.value !== null);

    rows.sort((a, b) => b.value - a.value);
    return rows.slice(0, 10);
  }, [filteredRows, selectedPeriod]);

  const stats = useMemo(() => {
    if (!chartRows.length) return null;
    const vals = chartRows.map((x) => x.value);
    const best = Math.max(...vals);
    const worst = Math.min(...vals);
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    return { best, worst, avg };
  }, [chartRows]);

  /* ---------- chart colors (scriptable) ---------- */
  const barData = useMemo(() => {
    const values = chartRows.map((x) => x.value);
    return {
      labels: chartRows.map((x) => x.label),
      datasets: [
        {
          label: `CAGR ${selectedPeriod.key} (%)`,
          data: values,
          backgroundColor: (ctx) => {
            const v = ctx?.raw;
            if (typeof v !== "number") return "rgba(59, 130, 246, 0.6)";
            return v >= 0 ? "rgba(16, 185, 129, 0.65)" : "rgba(239, 68, 68, 0.65)";
          },
          borderColor: (ctx) => {
            const v = ctx?.raw;
            if (typeof v !== "number") return "rgba(59, 130, 246, 1)";
            return v >= 0 ? "rgba(16, 185, 129, 1)" : "rgba(239, 68, 68, 1)";
          },
          borderWidth: 1,
          borderRadius: 10,
          borderSkipped: false,
          maxBarThickness: 46,
          categoryPercentage: 0.72,
          barPercentage: 0.9,
        },
      ],
    };
  }, [chartRows, selectedPeriod]);

  const barOptions = useMemo(() => {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            boxWidth: 10,
            boxHeight: 10,
            usePointStyle: true,
            pointStyle: "rectRounded",
          },
        },
        tooltip: {
          padding: 10,
          displayColors: false,
          callbacks: {
            title: (items) => (items?.[0]?.label ? truncLabel(items[0].label, 42) : "Fund"),
            label: (ctx) => {
              const v = ctx.parsed.y;
              const sign = v > 0 ? "+" : "";
              return `Return: ${sign}${Number(v).toFixed(2)}%`;
            },
          },
        },
      },
      layout: { padding: { top: 6, right: 10, bottom: 6, left: 6 } },
      scales: {
        y: {
          grid: {
            drawBorder: false,
          },
          ticks: {
            callback: (v) => `${v}%`,
          },
          title: { display: true, text: "Return (%)" },
        },
        x: {
          grid: { display: false, drawBorder: false },
          ticks: {
            maxRotation: 0,
            minRotation: 0,
            callback: function (value) {
              const label = this.getLabelForValue(value);
              return truncLabel(label, 18);
            },
          },
        },
      },
    };
  }, []);

  return (
    <div className="apf-wrap">
      <div className="apf-header">
        <div>
          <h3 className="apf-title">Active vs Passive Funds</h3>
          <div className="apf-subtitle">
            Select fund category, filter by AMC, and view performance across periods.
          </div>
        </div>

        {mode && (
          <button
            className="apf-ghost"
            type="button"
            onClick={() => {
              setMode(null);
              setSelectedAmc(null);
              setCategoryKey(null);
              setMfErr("");
              setMfRows([]);
            }}
          >
            Change Selection
          </button>
        )}
      </div>

      {!mode && (
        <div className="apf-mode-grid">
          <button type="button" className="apf-mode-card" onClick={() => setMode("ACTIVE")}>
            <div className="apf-mode-icon active" aria-hidden="true">
              📈
            </div>
            <div className="apf-mode-content">
              <div className="apf-mode-title">Active Funds</div>
              <div className="apf-mode-desc">Large/Mid/Small/Flexi/Multi + Hybrid categories.</div>
              <div className="apf-mode-cta">Explore Active →</div>
            </div>
          </button>

          <button type="button" className="apf-mode-card" onClick={() => setMode("PASSIVE")}>
            <div className="apf-mode-icon passive" aria-hidden="true">
              🧭
            </div>
            <div className="apf-mode-content">
              <div className="apf-mode-title">Passive Funds</div>
              <div className="apf-mode-desc">Nifty50 / BSE / Midcap150 / Smallcap250</div>
              <div className="apf-mode-cta">Explore Passive →</div>
            </div>
          </button>
        </div>
      )}

      {mode && (
        <div className="apf-panel">
          <div className="apf-panel-top">
            <div className="apf-badge">
              {mode === "ACTIVE" ? "Active Funds" : "Passive Funds"} • Category-based
            </div>

            <div className="apf-cap-segment" role="tablist" aria-label="Categories">
              {categoryOptions.map((c) => (
                <button
                  key={c.key}
                  type="button"
                  className={`apf-cap-btn ${categoryKey === c.key ? "is-active" : ""}`}
                  onClick={() => {
                    setCategoryKey(c.key);
                    setSelectedAmc(null);
                  }}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          {/* AMC FILTER */}
          <div className="apf-amc-grid">
            {AMCS.map((amc) => (
              <button
                key={amc.key}
                type="button"
                className={`apf-amc-card ${selectedAmc === amc.key ? "is-selected" : ""}`}
                onClick={() => setSelectedAmc(amc.key)}
                title={`Filter by ${amc.label}`}
              >
                <div className="apf-amc-logo" aria-hidden="true">
                  {amc.label.slice(0, 1)}
                </div>
                <div className="apf-amc-info">
                  <div className="apf-amc-name">{amc.label}</div>
                  <div className="apf-amc-sub">{selectedAmc === amc.key ? "Selected" : "Click to filter"}</div>
                </div>
                <div className="apf-amc-go" aria-hidden="true">
                  ✓
                </div>
              </button>
            ))}
          </div>

          <div className="apf-note">
            Category key (backend): <b>{selectedCategory}</b>
            {selectedAmc ? ` • AMC: ${selectedAmc}` : ""}
          </div>

          {/* FUND PERFORMANCE SECTION */}
          <div className="apf-panel apf-performance" style={{ marginTop: 14 }}>
            <div className="apf-panel-top">
              <div className="apf-badge">Fund Performance (CAGR) • {selectedCategory}</div>

              <button className="apf-ghost" type="button" onClick={fetchMfCagr} disabled={mfLoading}>
                {mfLoading ? "Refreshing..." : "Refresh CAGR"}
              </button>
            </div>

            {latestSyncedAt && !mfErr && !mfLoading && (
              <div className="apf-note">
                Last synced: <b>{latestSyncedAt}</b>
              </div>
            )}

            {mfErr && <div className="apf-note apf-error">{mfErr}</div>}
            {!mfErr && mfLoading && <div className="apf-note">Loading mf-cagr-summary…</div>}

            {!mfErr && !mfLoading && (
              <>
                <div className="apf-note">
                  Rows: <b>{filteredRows.length}</b>{" "}
                  {selectedAmc ? "(Click another AMC to change filter)" : "(Click an AMC card to filter)"}
                </div>

                {/* PERIOD SELECTOR */}
                <div className="apf-period-row">
                  {PERIOD_OPTIONS.map((p) => (
                    <button
                      key={p.key}
                      type="button"
                      className={`apf-cap-btn ${periodKey === p.key ? "is-active" : ""}`}
                      onClick={() => setPeriodKey(p.key)}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>

                {/* CHART CARD */}
                <div className="apf-chart-card">
                  <div className="apf-chart-head">
                    <div>
                      <div className="apf-chart-title">Top funds by CAGR {selectedPeriod.key}</div>
                      <div className="apf-chart-sub">
                        Bars are <span className="apf-pill pos">green</span> for positive and{" "}
                        <span className="apf-pill neg">red</span> for negative returns.
                      </div>
                    </div>

                    {stats && (
                      <div className="apf-chart-stats">
                        <div className="apf-stat">
                          <div className="apf-stat-label">Avg</div>
                          <div className={`apf-stat-val ${stats.avg >= 0 ? "pos" : "neg"}`}>
                            {stats.avg >= 0 ? "+" : ""}
                            {stats.avg.toFixed(2)}%
                          </div>
                        </div>
                        <div className="apf-stat">
                          <div className="apf-stat-label">Best</div>
                          <div className="apf-stat-val pos">+{stats.best.toFixed(2)}%</div>
                        </div>
                        <div className="apf-stat">
                          <div className="apf-stat-label">Worst</div>
                          <div className="apf-stat-val neg">{stats.worst.toFixed(2)}%</div>
                        </div>
                      </div>
                    )}
                  </div>

                  {chartRows.length === 0 ? (
                    <div className="apf-note apf-warn">
                      Chart is blank because <b>{selectedPeriod.field}</b> values are missing (“-”) OR there are no funds
                      in this category in your CSV.
                    </div>
                  ) : (
                    <div className="apf-chart-wrap">
                      <Bar data={barData} options={barOptions} />
                    </div>
                  )}
                </div>

                {/* TABLE */}
                {filteredRows.length === 0 ? (
                  <div className="apf-note">
                    No data matched for bucket=<b>{selectedBucket}</b> category=<b>{selectedCategory}</b>.
                    <br />
                    Fix: ensure this category exists in your <code>mf_cagr_summary.csv</code>.
                  </div>
                ) : (
                  <div className="apf-table-wrap">
                    <table className="apf-table apf-table-pro">
                      <thead>
                        <tr>
                          <th className="sticky">Fund</th>
                          <th className="num sticky">Latest NAV</th>
                          <th className="num sticky">Updated till</th>
                          <th className="num sticky">Last synced</th>
                          <th className="num sticky">1M</th>
                          <th className="num sticky">6M</th>
                          <th className="num sticky">1Y</th>
                          <th className="num sticky">3Y</th>
                          <th className="num sticky">5Y</th>
                          <th className="num sticky">SI</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredRows.map((r, idx) => {
                          const v1m = parseCagrValue(r.cagr_1M);
                          const v6m = parseCagrValue(r.cagr_6M);
                          const v1y = parseCagrValue(r.cagr_1Y);
                          const v3y = parseCagrValue(r.cagr_3Y);
                          const v5y = parseCagrValue(r.cagr_5Y);
                          const vsi = parseCagrValue(r.cagr_SI);

                          const cls = (n) => (n === null ? "" : n >= 0 ? "pos" : "neg");

                          return (
                            <tr key={`${r.scheme_code || idx}-${idx}`}>
                              <td className="fund">
                                <div className="fund-name">{r.label}</div>
                                <div className="fund-meta">
                                  <span className="chip">{String(r.amc || "").toUpperCase()}</span>
                                  <span className="chip soft">{String(r.category || "").toLowerCase()}</span>
                                </div>
                              </td>

                              <td className="num mono">{formatNav(r.latest_nav)}</td>
                              <td className="num mono">{r.as_of ?? "-"}</td>
                              <td className="num mono">{r.synced_at ?? "-"}</td>

                              <td className={`num mono ${cls(v1m)}`}>{formatPct(r.cagr_1M)}</td>
                              <td className={`num mono ${cls(v6m)}`}>{formatPct(r.cagr_6M)}</td>
                              <td className={`num mono ${cls(v1y)}`}>{formatPct(r.cagr_1Y)}</td>
                              <td className={`num mono ${cls(v3y)}`}>{formatPct(r.cagr_3Y)}</td>
                              <td className={`num mono ${cls(v5y)}`}>{formatPct(r.cagr_5Y)}</td>
                              <td className={`num mono ${cls(vsi)}`}>{formatPct(r.cagr_SI)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}