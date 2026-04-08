import React from "react";
import logo from "./logo.png";
import {
  LayoutDashboard,
  Wallet,
  PiggyBank,
  TrendingUp,
  Shield,
  ShieldCheck,
  CreditCard,
  HandCoins,
  User,
  LogOut,
} from "lucide-react";
import "./sidebar.css";

export default function Sidebar({ username, activePage, setActivePage }) {
  const menuItems = [
    { label: "Overview", icon: <LayoutDashboard size={18} /> },
    { label: "Income", icon: <Wallet size={18} /> },
    { label: "Expenses", icon: <CreditCard size={18} /> },
    { label: "Savings", icon: <PiggyBank size={18} /> },
    { label: "Investment", icon: <TrendingUp size={18} /> },
    { label: "Emergency", icon: <Shield size={18} /> },
    { label: "Insurance", icon: <ShieldCheck size={18} /> },
    { label: "Lending", icon: <HandCoins size={18} /> },
    { label: "Profile", icon: <User size={18} /> },
  ];

  const safeName = username?.trim() || "User";
  const initials = safeName
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");

  const isLogoutActive = activePage === "Logout";

  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="sidebar-bg" aria-hidden="true" />

      {/* Brand */}
      <div className="sidebar-brand">
        <img src={logo} alt="FinGrrow" className="brand-logo" />
        <div className="brand-text">
          <div className="brand-title">FinGrrow</div>
          <div className="brand-subtitle">Personal Finance</div>
        </div>
      </div>

      {/* User card */}
      <div className="sidebar-header">
        <div className="avatar" aria-hidden="true">
          {initials}
        </div>

        <div className="user-meta">
          <p className="hello">Hello,</p>
          <h2 className="username" title={safeName}>
            {safeName}
          </h2>
          <p className="caption">Track income, expenses & investments</p>
        </div>
      </div>

      {/* Scrollable Menu Area */}
      <div className="sidebar-menu">
        <nav className="menu" aria-label="Sidebar menu">
          {menuItems.map((item) => {
            const isActive = activePage === item.label;

            return (
              <button
                key={item.label}
                type="button"
                className={`menu-item ${isActive ? "active" : ""}`}
                onClick={() => setActivePage(item.label)}
                aria-current={isActive ? "page" : undefined}
              >
                <span className="menu-icon" aria-hidden="true">
                  {item.icon}
                </span>
                <span className="menu-label">{item.label}</span>
                <span className="menu-pill" aria-hidden="true" />
              </button>
            );
          })}
        </nav>
      </div>

      {/* Logout pinned at bottom */}
      <div className="sidebar-logout">
        <button
          type="button"
          className={`menu-item logout ${isLogoutActive ? "active" : ""}`}
          onClick={() => setActivePage("Logout")}
          aria-current={isLogoutActive ? "page" : undefined}
        >
          <span className="menu-icon" aria-hidden="true">
            <LogOut size={18} />
          </span>
          <span className="menu-label">Logout</span>
          <span className="menu-pill" aria-hidden="true" />
        </button>
      </div>

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="footer-card">
          <div className="dot" aria-hidden="true" />
          <div className="footer-text">
            <div className="footer-title">Secure</div>
            <div className="footer-subtitle">Your data is protected</div>
          </div>
        </div>
      </div>
    </aside>
  );
}