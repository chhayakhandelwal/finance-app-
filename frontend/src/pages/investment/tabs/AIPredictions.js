import React, { useEffect, useMemo, useState } from "react";
import { fetchFundPredictions } from "../../../api/predictionsApi";

const ACTIVE_CATEGORIES = [
  "largecap",
  "midcap",
  "smallcap",
  "multicap",
  "flexicap",
  "balanced_advantage",
  "multi_asset",
  "hybrid_conservative",
  "hybrid_aggressive",
];

const PASSIVE_CATEGORIES = [
  "nifty50",
  "bse",
  "midcap150",
  "smallcap250",
];

export default function AIPredictions() {
  const [fundType, setFundType] = useState("active");
  const [category, setCategory] = useState("largecap");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const visibleCategories = useMemo(() => {
    return fundType === "active" ? ACTIVE_CATEGORIES : PASSIVE_CATEGORIES;
  }, [fundType]);

  useEffect(() => {
    if (!visibleCategories.includes(category)) {
      setCategory(visibleCategories[0]);
    }
  }, [fundType, visibleCategories, category]);

  const loadData = async (cat = category) => {
    try {
      setLoading(true);
      setErr("");
      const data = await fetchFundPredictions(cat, 20);
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      const detail =
        e?.response?.data?.detail ||
        e?.message ||
        "Failed to load AI predictions.";
      setErr(detail);
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (category) loadData(category);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category]);

  return (
    <div style={wrap}>
      <div style={top}>
        <div>
          <div style={title}>AI Predictions</div>
          <div style={sub}>
            AI forecast of next-week fund returns and probability of beating the benchmark
          </div>
        </div>

        <button type="button" onClick={() => loadData()} style={primaryBtn}>
          Refresh
        </button>
      </div>

      <div style={switchWrap}>
        <div style={switchInner}>
          <button
            type="button"
            onClick={() => setFundType("active")}
            style={{
              ...switchBtn,
              ...(fundType === "active" ? switchBtnActive : {}),
            }}
          >
            Active Funds
          </button>

          <button
            type="button"
            onClick={() => setFundType("passive")}
            style={{
              ...switchBtn,
              ...(fundType === "passive" ? switchBtnActive : {}),
            }}
          >
            Passive Funds
          </button>
        </div>
      </div>

      <div style={chipRow}>
        {visibleCategories.map((c) => {
          const active = category === c;
          return (
            <button
              key={c}
              type="button"
              onClick={() => setCategory(c)}
              style={{
                ...chip,
                ...(active ? chipActive : {}),
              }}
            >
              {labelize(c)}
            </button>
          );
        })}
      </div>

      {err && <div style={errorText}>{err}</div>}
      {!err && loading && <div style={loadingText}>Loading…</div>}

      {!err && !loading && (
        <>
          <div style={meta}>
            Type: <b>{fundType === "active" ? "Active Funds" : "Passive Funds"}</b>
            {" • "}
            Category: <b>{labelize(category)}</b>
            {" • "}
            Rows: <b>{rows.length}</b>
          </div>

          <div style={tableWrap}>
            <table style={table}>
              <thead>
                <tr>
                  <th style={th}>Fund Name</th>
                  <th style={th}>Forecast Date</th>
                  <th style={th}>Prediction Date</th>
                  <th style={th}>Expected Return</th>
                  <th style={th}>Outperform Probability</th>
                  <th style={th}>Recommendation</th>
                </tr>
              </thead>

              <tbody>
                {rows.map((r, idx) => (
                  <tr key={`${r.scheme_code}-${idx}`}>
                    <td style={tdStrong}>{r.scheme_name || r.scheme_code}</td>
                    <td style={td}>{r.as_of || "-"}</td>
                    <td style={td}>{r.pred_for_date || "-"}</td>
                    <td style={td}>
                      {r.pred_nextweek_return != null
                        ? `${(Number(r.pred_nextweek_return) * 100).toFixed(2)}%`
                        : "-"}
                    </td>
                    <td style={td}>
                      {r.prob_outperform != null
                        ? `${(Number(r.prob_outperform) * 100).toFixed(2)}%`
                        : "-"}
                    </td>
                    <td style={td}>
                      <span style={badgeFor(r.recommendation)}>
                        {r.recommendation || "-"}
                      </span>
                    </td>
                  </tr>
                ))}

                {rows.length === 0 && (
                  <tr>
                    <td style={td} colSpan={6}>
                      No predictions available.
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

function labelize(v) {
  if (v === "largecap") return "Large Cap";
  if (v === "midcap") return "Mid Cap";
  if (v === "smallcap") return "Small Cap";
  if (v === "multicap") return "Multi Cap";
  if (v === "flexicap") return "Flexi Cap";
  if (v === "balanced_advantage") return "Balanced Advantage";
  if (v === "multi_asset") return "Multi Asset";
  if (v === "hybrid_conservative") return "Hybrid Conservative";
  if (v === "hybrid_aggressive") return "Hybrid Aggressive";
  if (v === "nifty50") return "Nifty 50";
  if (v === "bse") return "BSE";
  if (v === "midcap150") return "Midcap 150";
  if (v === "smallcap250") return "Smallcap 250";
  return v;
}

function badgeFor(rec) {
  if (rec === "BUY") {
    return {
      ...badge,
      background: "rgba(22,163,74,0.12)",
      color: "#166534",
    };
  }
  if (rec === "HOLD") {
    return {
      ...badge,
      background: "rgba(245,158,11,0.14)",
      color: "#92400e",
    };
  }
  return {
    ...badge,
    background: "rgba(220,38,38,0.12)",
    color: "#991b1b",
  };
}

const wrap = {
  border: "1px solid rgba(0,0,0,0.10)",
  borderRadius: 18,
  padding: 14,
  background: "#fff",
  boxShadow: "0 6px 16px rgba(0,0,0,0.06)",
};

const top = {
  display: "flex",
  justifyContent: "space-between",
  gap: 12,
  flexWrap: "wrap",
  alignItems: "flex-start",
};

const title = {
  fontWeight: 900,
  fontSize: 18,
  color: "#111827",
};

const sub = {
  marginTop: 4,
  fontSize: 12,
  opacity: 0.75,
};

const primaryBtn = {
  border: "1px solid #2563eb",
  background: "#2563eb",
  color: "#fff",
  padding: "10px 12px",
  borderRadius: 12,
  cursor: "pointer",
  fontWeight: 800,
};

const switchWrap = {
  marginTop: 16,
  marginBottom: 14,
  display: "flex",
  justifyContent: "flex-start",
};

const switchInner = {
  display: "inline-flex",
  gap: 12,
  padding: 10,
  borderRadius: 22,
  border: "1px solid rgba(0,0,0,0.10)",
  background: "#f8fafc",
};

const switchBtn = {
  border: "1px solid rgba(0,0,0,0.10)",
  background: "#ffffff",
  color: "#374151",
  padding: "16px 28px",
  borderRadius: 20,
  cursor: "pointer",
  fontWeight: 800,
  fontSize: 15,
  transition: "all 0.2s ease",
};

const switchBtnActive = {
  background: "#2563eb",
  color: "#ffffff",
  border: "1px solid #2563eb",
  boxShadow: "0 8px 20px rgba(37,99,235,0.22)",
};

const chipRow = {
  display: "flex",
  gap: 8,
  flexWrap: "wrap",
  marginTop: 4,
};

const chip = {
  border: "1px solid rgba(0,0,0,0.12)",
  background: "#fff",
  color: "#374151",
  padding: "8px 10px",
  borderRadius: 12,
  cursor: "pointer",
  fontWeight: 800,
};

const chipActive = {
  border: "1px solid #2563eb",
  background: "#2563eb",
  color: "#fff",
};

const errorText = {
  marginTop: 12,
  color: "#b91c1c",
  fontSize: 13,
  fontWeight: 700,
};

const loadingText = {
  marginTop: 12,
  fontSize: 13,
  opacity: 0.75,
};

const meta = {
  marginTop: 12,
  fontSize: 12,
  opacity: 0.8,
};

const tableWrap = {
  overflowX: "auto",
  marginTop: 14,
};

const table = {
  width: "100%",
  borderCollapse: "collapse",
};

const th = {
  padding: "10px 10px",
  borderBottom: "1px solid rgba(0,0,0,0.10)",
  fontSize: 12,
  opacity: 0.8,
  whiteSpace: "nowrap",
  textAlign: "left",
};

const td = {
  padding: "10px 10px",
  borderBottom: "1px solid rgba(0,0,0,0.06)",
  fontSize: 13,
  whiteSpace: "nowrap",
};

const tdStrong = {
  ...td,
  fontWeight: 900,
  color: "#111827",
};

const badge = {
  display: "inline-block",
  padding: "4px 8px",
  borderRadius: 999,
  fontWeight: 800,
  fontSize: 12,
};