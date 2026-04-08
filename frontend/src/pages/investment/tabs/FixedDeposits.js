import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";

import { Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from "chart.js";

import "./FixedDeposits.css";

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

const BANK_COLORS = {
  HDFC: { bg: "rgba(59,130,246,0.25)", border: "rgba(59,130,246,0.9)" },
  ICICI: { bg: "rgba(249,115,22,0.25)", border: "rgba(249,115,22,0.9)" },
  SBI: { bg: "rgba(34,197,94,0.25)", border: "rgba(34,197,94,0.9)" },
  AXIS: { bg: "rgba(168,85,247,0.25)", border: "rgba(168,85,247,0.9)" },
};

export default function FixedDeposits() {
  const [payload, setPayload] = useState(null);
  const [selectedBank, setSelectedBank] = useState(""); // bank name string
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const fetchFD = async () => {
    const token = readToken();
    if (!token) {
      setErr("You are not logged in. Please login first.");
      setPayload(null);
      return;
    }

    setLoading(true);
    setErr("");

    try {
      const res = await axios.get(`${API_BASE_URL}/api/investment/fixed-assets/fd-rates/`, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 20000,
      });

      const data = res.data;
      setPayload(data);

      const banks = Array.isArray(data?.banks) ? data.banks : [];
      // default selection: first bank if none selected or selection missing
      const exists = banks.some((b) => (b?.bank || "") === selectedBank);
      if (!selectedBank || !exists) {
        setSelectedBank(banks?.[0]?.bank || "");
      }
    } catch (e) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail || e?.message || "Failed to load FD rates.";
      setErr(`${detail}${status ? ` (HTTP ${status})` : ""}`);
      setPayload(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFD();
    const handler = () => fetchFD();
    window.addEventListener("auth-token-changed", handler);
    return () => window.removeEventListener("auth-token-changed", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const banks = useMemo(() => (Array.isArray(payload?.banks) ? payload.banks : []), [payload]);

  const activeBankObj = useMemo(() => {
    if (!banks.length) return null;
    return banks.find((b) => (b?.bank || "") === selectedBank) || banks[0];
  }, [banks, selectedBank]);

  const tenures = useMemo(() => {
    const t = activeBankObj?.tenures;
    return Array.isArray(t) ? t : [];
  }, [activeBankObj]);

  const chart = useMemo(() => {
    if (!activeBankObj) return null;

    const labels = tenures.map((t) => t.label);
    const rates = tenures.map((t) => {
      const v = activeBankObj?.rates?.[t.key];
      return v === null || v === undefined ? null : Number(v);
    });

    const bankName = activeBankObj?.bank || "BANK";
    const c = BANK_COLORS[bankName] || { bg: "rgba(99,102,241,0.25)", border: "rgba(99,102,241,0.9)" };

    return {
      labels,
      datasets: [
        {
          label: bankName,
          data: rates,
          backgroundColor: c.bg,
          borderColor: c.border,
          borderWidth: 1.5,
          borderRadius: 8,
        },
      ],
    };
  }, [activeBankObj, tenures]);

  const options = useMemo(() => {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom" },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y}%`,
          },
        },
      },
      scales: {
        y: {
          title: { display: true, text: "Interest Rate (%)" },
          ticks: { callback: (v) => `${v}%` },
        },
      },
    };
  }, []);

  return (
    <div className="fdCard">
      <div className="fdHeaderRow">
        <div>
          <div className="fdTitle">Fixed Deposit Rates (Official slabs)</div>
          <div className="fdMeta">
            As of: <b>{payload?.as_of || "-"}</b>
            {payload?.slab ? (
              <>
                {" "}• Slab: <b>{payload.slab}</b>
              </>
            ) : null}
          </div>
        </div>

        <button className="fdBtnPrimary" type="button" onClick={fetchFD} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {err ? <div className="fdError">{err}</div> : null}

      {!err && payload && (
        <>
          <div className="fdBankRow">
            <div className="fdBankLabel">Bank:</div>

            <div className="fdBankPills">
              {banks.map((b) => {
                const name = b?.bank || "";
                const active = name === (activeBankObj?.bank || "");
                return (
                  <button
                    key={name}
                    type="button"
                    className={`fdPill ${active ? "active" : ""}`}
                    onClick={() => setSelectedBank(name)}
                  >
                    <span className="dot" />
                    {name}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Chart */}
          {chart ? (
            <div className="fdChartWrap">
              <Bar data={chart} options={options} />
            </div>
          ) : null}

          {/* Table */}
          {activeBankObj ? (
            <div className="fdTableWrap">
              <table className="fdTable">
                <thead>
                  <tr>
                    <th>Tenure</th>
                    <th style={{ textAlign: "right" }}>Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {tenures.map((t) => (
                    <tr key={t.key}>
                      <td>{t.label}</td>
                      <td style={{ textAlign: "right", fontWeight: 800 }}>
                        {activeBankObj?.rates?.[t.key] ?? "-"}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          <div className="fdNote">{payload?.note || "Reference dataset based on official bank rate sheets."}</div>
        </>
      )}
    </div>
  );
}