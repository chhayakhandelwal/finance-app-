import React, { useState } from "react";
import "./FixedAssets.css";

import FixedDeposits from "./FixedDeposits";
import DebtFunds from "./DebtFunds";

export default function FixedAssets() {
  const [subTab, setSubTab] = useState("fd"); // fd | debt

  return (
    <div className="fa-wrap">
      <div className="fa-head">
        <div>
          <h3 className="fa-title">Fixed Assets</h3>
        </div>

        <div className="fa-pillbar">
          <button
            type="button"
            className={`fa-pill ${subTab === "fd" ? "is-active" : ""}`}
            onClick={() => setSubTab("fd")}
          >
            Fixed Deposit
          </button>
          <button
            type="button"
            className={`fa-pill ${subTab === "debt" ? "is-active" : ""}`}
            onClick={() => setSubTab("debt")}
          >
            Debt Funds
          </button>
        </div>
      </div>

      <div className="fa-body">
        {subTab === "fd" && <FixedDeposits />}
        {subTab === "debt" && <DebtFunds />}
      </div>
    </div>
  );
}