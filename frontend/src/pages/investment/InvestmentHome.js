import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";

import "./investmentHome.css";
import ActivePassiveFunds from "./tabs/ActivePassiveFunds";
import FixedAssets from "./tabs/FixedAssets";
import AIPredictions from "./tabs/AIPredictions";
import InvestmentRecommendation from "./InvestmentRecommendation";

// ✅ Correct import (component)
import OfficialFundLinks from "../../components/OfficialFundLinks";

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

export default function InvestmentHome() {
  const [activeTab, setActiveTab] = useState("funds");
  const [errorMsg, setErrorMsg] = useState("");
  const [loading, setLoading] = useState(false);

  const API_BASE_URL =
    (process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

  const api = useMemo(() => {
    const instance = axios.create({
      baseURL: API_BASE_URL,
      timeout: 20000,
      headers: { "Content-Type": "application/json" },
    });

    instance.interceptors.request.use((config) => {
      const token = readToken();
      if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    instance.interceptors.response.use(
      (res) => res,
      (err) => {
        const status = err?.response?.status;
        if (status === 401) {
          console.warn("401 Unauthorized: Token missing/expired.");
        }
        return Promise.reject(err);
      }
    );

    return instance;
  }, [API_BASE_URL]);

  const ensureLoggedIn = () => {
    const token = readToken();
    if (!token) {
      setErrorMsg("You are not logged in. Please login first.");
      return false;
    }
    return true;
  };

  const refreshAll = useCallback(async () => {
    setLoading(true);
    setErrorMsg("");

    try {
      ensureLoggedIn();
      await Promise.resolve();
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshAll();

    const handler = () => refreshAll();
    window.addEventListener("auth-token-changed", handler);
    return () => window.removeEventListener("auth-token-changed", handler);
  }, [refreshAll]);

  return (
    <div className="inv-wrap">
      <div className="inv-top">
        <div className="inv-title">
          <h2>Investment</h2>
          <div className="inv-subtitle">
            Portfolio, fixed assets, recommendations, and AI predictions
          </div>
        </div>

        
      </div>

      {/* ================= TABS ================= */}
      <div className="inv-tabs">
        <button
          className={`inv-tab ${activeTab === "funds" ? "active" : ""}`}
          onClick={() => setActiveTab("funds")}
          type="button"
        >
          Active/Passive Funds
        </button>

        <button
          className={`inv-tab ${activeTab === "fixed" ? "active" : ""}`}
          onClick={() => setActiveTab("fixed")}
          type="button"
        >
          Fixed Assets
        </button>

        <button
          className={`inv-tab ${activeTab === "recommend" ? "active" : ""}`}
          onClick={() => setActiveTab("recommend")}
          type="button"
        >
          Recommendation
        </button>

        <button
          className={`inv-tab ${
            activeTab === "ai_predictions" ? "active" : ""
          }`}
          onClick={() => setActiveTab("ai_predictions")}
          type="button"
        >
          AI Predictions
        </button>

        {/* ✅ NEW TAB */}
        <button
          className={`inv-tab ${
            activeTab === "officialLinks" ? "active" : ""
          }`}
          onClick={() => setActiveTab("officialLinks")}
          type="button"
        >
          Official Fund Links
        </button>
      </div>

      {errorMsg && <div className="inv-alert">{errorMsg}</div>}

      {/* ================= TAB CONTENT ================= */}
      <div className="inv-tab-content">
        {activeTab === "funds" && <ActivePassiveFunds />}
        {activeTab === "fixed" && <FixedAssets />}
        {activeTab === "recommend" && <InvestmentRecommendation />}
        {activeTab === "ai_predictions" && <AIPredictions />}

        {/* ✅ FIXED LINE (IMPORTANT) */}
        {activeTab === "officialLinks" && <OfficialFundLinks />}
      </div>
    </div>
  );
}