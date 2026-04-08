import React from "react";
import "./home.css";
import logo from "./logo.png";
import { motion } from "framer-motion";
import {
  ArrowRight,
  ShieldCheck,
  LineChart,
  Wallet,
  Target,
  Bell,
  PieChart,
} from "lucide-react";

export default function FinanceHomepage({ onOpenLogin, onOpenRegister }) {
  return (
    <div className="home-page">
      <div className="home-bg-orb home-bg-orb-1" />
      <div className="home-bg-orb home-bg-orb-2" />

      <div className="home-shell">
        <header className="home-navbar">
          <div className="brand-wrap">
            <div className="brand-logo-box">
              <img src={logo} alt="FinGrrow Logo" className="brand-logo" />
            </div>
            <div>
              <h1 className="brand-title">FinGrrow</h1>
          
            </div>
          </div>

          <nav className="home-nav-links">
            <a href="#about">About</a>
            <a href="#features">Features</a>
          </nav>
        </header>

        <section className="hero-section">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7 }}
          >
            <div className="hero-badge">
              Smart money management for everyday users
            </div>

            <h2 className="hero-title">
              Track, plan, and grow your money with a
              <span> finance dashboard </span>
              built for real life.
            </h2>

            <p className="hero-description">
              Manage income, expenses, savings goals, loans, insurance,
              investments, and AI-powered fund predictions in one secure
              platform.
            </p>

            <div className="hero-actions" id="auth">
              <button
                type="button"
                onClick={onOpenLogin}
                className="primary-btn"
              >
                Login <ArrowRight size={18} />
              </button>

              <button
                type="button"
                onClick={onOpenRegister}
                className="secondary-btn"
              >
                Register
              </button>
            </div>


          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.1 }}
          >
            
           
          </motion.div>
        </section>

        <section id="about" className="about-section">
          <div className="about-main-card">
            <p className="section-tag">About FinGrrow</p>
            <h3 className="section-title">
              A complete finance manager for smarter decisions
            </h3>
            <p className="section-text">
              FinGrrow helps users organize every important part of personal
              finance in one place. From daily transaction tracking to long-term
              wealth planning, the platform combines structured finance records
              with intelligent recommendations so users can stay informed,
              disciplined, and financially confident.
            </p>
          </div>

          <div id="security" className="security-card">
            <div className="security-head">
              <ShieldCheck size={24} />
              <span>Security First</span>
            </div>
            <p className="section-text">
              Your finance records, goals, and investment data stay protected
              with authenticated access, secure APIs, and controlled
              user-specific views.
            </p>
          </div>
        </section>

        <section id="features" className="features-section">
          <div className="features-heading">
            <p className="section-tag center">Core Features</p>
            <h3 className="section-title center">
              Everything needed to manage personal finance better
            </h3>
          </div>

          <div className="features-grid">
            {features.map((item) => (
              <motion.div
                key={item.title}
                whileHover={{ y: -4 }}
                className="feature-card"
              >
                <div className="feature-icon">{item.icon}</div>
                <h4 className="feature-title">{item.title}</h4>
                <p className="feature-desc">{item.desc}</p>
              </motion.div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function DashboardCard({ title, value, sub, icon }) {
  return (
    <div className="dashboard-stat-card">
      <div className="dashboard-stat-top">
        <span className="dashboard-stat-title">{title}</span>
        <span className="dashboard-stat-icon">{icon}</span>
      </div>
      <div className="dashboard-stat-value">{value}</div>
      <div className="dashboard-stat-sub">{sub}</div>
    </div>
  );
}

const features = [
  {
    title: "Income & Expense Tracking",
    desc: "Monitor daily cash flow, categorize spending, and understand where money is going every month.",
    icon: <Wallet size={20} />,
  },
  {
    title: "Savings & Emergency Goals",
    desc: "Create financial targets, monitor contributions, and build a safer emergency reserve over time.",
    icon: <Target size={20} />,
  },
  {
    title: "Investment Intelligence",
    desc: "Compare funds, monitor portfolio performance, and view AI-based return and outperform predictions.",
    icon: <LineChart size={20} />,
  },
  {
    title: "Loan & Insurance Management",
    desc: "Track obligations, payment timelines, and important financial commitments in one unified dashboard.",
    icon: <ShieldCheck size={20} />,
  },
  {
    title: "Smart Alerts & Recommendations",
    desc: "Receive timely suggestions for spending control, investment decisions, and better financial planning.",
    icon: <Bell size={20} />,
  },
  {
    title: "Analytics & Visual Insights",
    desc: "Use charts, summaries, and trend views to make faster and more confident money decisions.",
    icon: <PieChart size={20} />,
  },
];