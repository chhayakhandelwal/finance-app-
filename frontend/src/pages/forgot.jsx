import React, { useMemo, useState } from "react";
import axios from "axios";
import "./forgot.css";
import logo from "./logo.png";
import { FaEye, FaEyeSlash } from "react-icons/fa";

const API_BASE_URL =
  (process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const passwordRegex = /^(?=.*[A-Z])(?=.*\d).{8,}$/;

const Forgot = ({ onDone, onBackToLogin }) => {
  const [step, setStep] = useState(1);

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [errorText, setErrorText] = useState("");
  const [successText, setSuccessText] = useState("");
  const [loading, setLoading] = useState(false);

  const canResend = useMemo(() => step >= 2, [step]);

  const togglePassword = (type) => {
    if (type === "password") {
      setShowPassword((prev) => !prev);
    } else {
      setShowConfirmPassword((prev) => !prev);
    }
  };

  const sendOtp = async () => {
    setErrorText("");
    setSuccessText("");

    const u = username.trim();
    const e = email.trim();

    if (!u || !e) {
      setErrorText("Username and Email are required.");
      return;
    }

    setLoading(true);
    try {
      await axios.post(
        `${API_BASE_URL}/api/forgot/send-otp/`,
        { username: u, email: e },
        {
          headers: { "Content-Type": "application/json" },
          timeout: 15000,
        }
      );

      setSuccessText("OTP sent to your email.");
      setStep(2);
    } catch (err) {
      setErrorText(
        err?.response?.data?.message ||
          err?.response?.data?.detail ||
          "Failed to send OTP"
      );
    } finally {
      setLoading(false);
    }
  };

  const verifyOtp = async () => {
    setErrorText("");
    setSuccessText("");

    const u = username.trim();
    const e = email.trim();
    const o = otp.trim();

    if (!o) {
      setErrorText("OTP is required.");
      return;
    }

    setLoading(true);
    try {
      await axios.post(
        `${API_BASE_URL}/api/forgot/verify-otp/`,
        { username: u, email: e, otp: o },
        {
          headers: { "Content-Type": "application/json" },
          timeout: 15000,
        }
      );

      setSuccessText("OTP verified. You can now set a new password.");
      setStep(3);
    } catch (err) {
      setErrorText(
        err?.response?.data?.message ||
          err?.response?.data?.detail ||
          "Invalid OTP"
      );
    } finally {
      setLoading(false);
    }
  };

  const resetPassword = async () => {
    setErrorText("");
    setSuccessText("");

    if (!passwordRegex.test(password)) {
      setErrorText(
        "Password must be at least 8 characters long and include one uppercase letter and one number."
      );
      return;
    }

    if (password !== confirmPassword) {
      setErrorText("Passwords do not match!");
      return;
    }

    setLoading(true);
    try {
      await axios.post(
        `${API_BASE_URL}/api/forgot/reset-password/`,
        {
          username: username.trim(),
          email: email.trim(),
          otp: otp.trim(),
          new_password: password,
        },
        {
          headers: { "Content-Type": "application/json" },
          timeout: 15000,
        }
      );

      setSuccessText("Password reset successful. Redirecting to Login...");
      setTimeout(() => {
        onDone?.();
      }, 900);
    } catch (err) {
      setErrorText(
        err?.response?.data?.message ||
          err?.response?.data?.detail ||
          "Failed to reset password"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="forgot-page">
      <header className="header">
        <div className="header-brand">
          <div className="logo-box">
            <img src={logo} alt="FinGrrow Logo" className="header-logo" />
          </div>
          <h1>FinGrrow</h1>
        </div>
      </header>

      <div className="forgot-content">
        <main className="form-area">
          <h2>Forgot Password</h2>

          {step === 1 && (
            <>
              <label>Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username"
              />

              <label>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email"
              />

              <button type="button" onClick={sendOtp} disabled={loading}>
                {loading ? "Sending..." : "Send OTP"}
              </button>
            </>
          )}

          {step === 2 && (
            <>
              <label>Enter OTP</label>
              <input
                type="text"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                placeholder="6-digit OTP"
                inputMode="numeric"
              />

              <button type="button" onClick={verifyOtp} disabled={loading}>
                {loading ? "Verifying..." : "Verify OTP"}
              </button>

              {canResend && (
                <button
                  type="button"
                  className="back-to-login"
                  onClick={sendOtp}
                  disabled={loading}
                >
                  Resend OTP
                </button>
              )}
            </>
          )}

          {step === 3 && (
            <>
              <label>New Password</label>
              <div className="password-wrapper">
                <input
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter new password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <span
                  className="eye-icon"
                  onClick={() => togglePassword("password")}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      togglePassword("password");
                    }
                  }}
                >
                  {showPassword ? <FaEyeSlash /> : <FaEye />}
                </span>
              </div>

              <label>Confirm New Password</label>
              <div className="password-wrapper">
                <input
                  type={showConfirmPassword ? "text" : "password"}
                  placeholder="Confirm new password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
                <span
                  className="eye-icon"
                  onClick={() => togglePassword("confirm")}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      togglePassword("confirm");
                    }
                  }}
                >
                  {showConfirmPassword ? <FaEyeSlash /> : <FaEye />}
                </span>
              </div>

              <button type="button" onClick={resetPassword} disabled={loading}>
                {loading ? "Updating..." : "Reset Password"}
              </button>
            </>
          )}

          {errorText && <p className="error">{errorText}</p>}
          {successText && <p className="success">{successText}</p>}

          <button
            type="button"
            className="back-to-login"
            onClick={() => onBackToLogin?.()}
            style={{ marginTop: 10 }}
          >
            Back to Login
          </button>
        </main>
      </div>
    </div>
  );
};

export default Forgot;