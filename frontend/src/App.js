import React, { useEffect, useState } from "react";
import Sidebar from "./components/sidebar";

import Overview from "./pages/overview";
import Savings from "./pages/Savings";
import Emergency from "./pages/emergency";
import Investment from "./pages/investment/InvestmentHome";
import Income from "./pages/Income";
import Profile from "./pages/profile";
import Expenses from "./pages/expenses/index";
import Insurance from "./pages/insurance";
import Lending from "./pages/lending";

import Login from "./pages/Login";
import Register from "./pages/register";
import ForgotPassword from "./pages/forgot";
import FinanceHomepage from "./home"; // homepage file

import "./App.css";

export default function App() {
  const [activePage, setActivePage] = useState("Overview");
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [username, setUsername] = useState("");

  // "home" | "login" | "register" | "forgot"
  const [authView, setAuthView] = useState("home");

  /* =====================
     Restore session on refresh (initial load)
     ===================== */
  useEffect(() => {
    const token = localStorage.getItem("token");
    const savedUsername = localStorage.getItem("username");

    if (token && savedUsername) {
      setIsLoggedIn(true);
      setUsername(savedUsername);
      setActivePage("Overview");
    } else {
      setIsLoggedIn(false);
      setUsername("");
      setActivePage("Overview");
      setAuthView("home");
    }
  }, []);

  /* =====================
     React immediately when token changes (login/logout)
     ===================== */
  useEffect(() => {
    const syncAuth = () => {
      const token = localStorage.getItem("token");
      const savedUsername = localStorage.getItem("username");

      if (token && savedUsername) {
        setIsLoggedIn(true);
        setUsername(savedUsername);
        setActivePage("Overview");
      } else {
        setIsLoggedIn(false);
        setUsername("");
        setActivePage("Overview");
        setAuthView("home");
      }
    };

    window.addEventListener("auth-token-changed", syncAuth);
    return () => window.removeEventListener("auth-token-changed", syncAuth);
  }, []);

  /* =====================
     Login handler
     ===================== */
  const handleLogin = (payload) => {
    const name =
      typeof payload === "string"
        ? payload
        : payload?.name || payload?.username || payload?.user?.name || "";

    if (!name) return;

    setUsername(name);
    setIsLoggedIn(true);
    setActivePage("Overview");
    setAuthView("home");

    localStorage.setItem("username", name);
    window.dispatchEvent(new Event("auth-token-changed"));
  };

  /* =====================
     Logout handler
     ===================== */
  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("username");

    setIsLoggedIn(false);
    setUsername("");
    setActivePage("Overview");
    setAuthView("home");

    window.dispatchEvent(new Event("auth-token-changed"));
  };

  /* =====================
     Detect sidebar logout click
     ===================== */
  useEffect(() => {
    if (activePage === "Logout") handleLogout();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePage]);

  /* =====================
     Page renderer (logged in pages)
     ===================== */
  const renderPage = () => {
    switch (activePage) {
      case "Overview":
        return <Overview />;
      case "Income":
        return <Income />;
      case "Expenses":
        return <Expenses />;
      case "Savings":
        return <Savings />;
      case "Investment":
        return <Investment />;
      case "Emergency":
        return <Emergency />;
      case "Insurance":
        return <Insurance />;
      case "Lending":
        return <Lending />;
      case "Profile":
        return <Profile />;
      default:
        return <Overview />;
    }
  };

  /* =====================
     AUTH GATE (when NOT logged in)
     ===================== */
  if (!isLoggedIn) {
    if (authView === "register") {
      return (
        <Register
          onRegistered={() => setAuthView("login")}
          onBackToLogin={() => setAuthView("login")}
        />
      );
    }

    if (authView === "forgot") {
      return (
        <ForgotPassword
          onDone={() => setAuthView("login")}
          onBackToLogin={() => setAuthView("login")}
        />
      );
    }

    if (authView === "login") {
      return (
        <Login
          onLogin={handleLogin}
          onOpenForgot={() => setAuthView("forgot")}
          onOpenRegister={() => setAuthView("register")}
          onBackToHome={() => setAuthView("home")}
        />
      );
    }

    // default: homepage
    return (
      <FinanceHomepage
        onOpenLogin={() => setAuthView("login")}
        onOpenRegister={() => setAuthView("register")}
      />
    );
  }

  /* =====================
     MAIN DASHBOARD (logged in)
     ===================== */
  return (
    <div className="app-container">
      <Sidebar
        username={username}
        activePage={activePage}
        setActivePage={setActivePage}
      />

      <main className="content-area">
        <header className="top-bar">
          <h1 className="logo">FinGrrow</h1>
        </header>

        <section className="content-inner">{renderPage()}</section>
      </main>
    </div>
  );
}