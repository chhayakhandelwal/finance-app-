import { useEffect, useState } from "react";
import axios from "axios";
import logo from "./logo.png";
import "./login.css";

const API_BASE_URL =
  (process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export default function LoginPage({
  onLogin,
  onOpenForgot,
  onOpenRegister,
  onBackToHome,
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [captcha, setCaptcha] = useState("");
  const [captchaInput, setCaptchaInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [toast, setToast] = useState({
    show: false,
    type: "success",
    message: "",
  });

  const showToast = (message, type = "success") => {
    setToast({ show: true, type, message });

    setTimeout(() => {
      setToast((prev) => ({ ...prev, show: false }));
    }, 2500);
  };

  const generateCaptcha = () => {
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    let result = "";
    for (let i = 0; i < 6; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    setCaptcha(result);
  };

  useEffect(() => {
    generateCaptcha();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;

    const uname = username.trim();
    const pwd = password;

    if (!uname || !pwd) {
      showToast("Username and Password are required!", "error");
      return;
    }

    if (captchaInput.trim().toUpperCase() !== captcha.toUpperCase()) {
      showToast("Invalid captcha", "error");
      generateCaptcha();
      setCaptchaInput("");
      return;
    }

    setIsSubmitting(true);

    try {
      const res = await axios.post(
        `${API_BASE_URL}/api/login/`,
        { username: uname, password: pwd },
        { headers: { "Content-Type": "application/json" }, timeout: 15000 }
      );

      const accessToken =
        res.data?.token ||
        res.data?.access ||
        res.data?.access_token;

      const refreshToken =
        res.data?.refreshToken ||
        res.data?.refresh ||
        res.data?.refresh_token;

      if (!accessToken) throw new Error("Token not received");

      localStorage.setItem("token", accessToken);
      localStorage.setItem("access_token", accessToken);
      localStorage.setItem("accessToken", accessToken);
      localStorage.setItem("authToken", accessToken);
      localStorage.setItem("jwt", accessToken);

      if (refreshToken) {
        localStorage.setItem("refresh_token", refreshToken);
        localStorage.setItem("refreshToken", refreshToken);
      }

      const displayName =
        res.data?.user?.name ||
        res.data?.user?.username ||
        uname;

      localStorage.setItem("username", displayName);

      window.dispatchEvent(new Event("auth-token-changed"));
      showToast("Login successful", "success");

      setTimeout(() => {
        onLogin?.(displayName);
      }, 800);
    } catch (err) {
      console.error("LOGIN ERROR:", err);
      showToast(
        err?.response?.data?.message ||
          err?.response?.data?.detail ||
          "Invalid username or password",
        "error"
      );
      generateCaptcha();
      setCaptchaInput("");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="container">
      {toast.show && (
        <div className={`login-toast login-toast--${toast.type}`}>
          {toast.message}
        </div>
      )}

      <header className="header">
        <div className="header-brand">
          <div className="logo-box">
            <img src={logo} alt="FinGrrow" className="header-logo" />
          </div>
          <h1>FinGrrow</h1>
        </div>
      </header>

      <div className="login-wrapper">
        <div className="login-box">
          <h2>Login</h2>

          <form onSubmit={handleSubmit}>
            <label>Username</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter Username"
              required
            />

            <label>Password</label>
            <div className="password-container">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter Password"
                required
              />
              <span
                className="password-toggle"
                onClick={() => setShowPassword(!showPassword)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setShowPassword(!showPassword);
                  }
                }}
              >
                {showPassword ? "🙈" : "👁️"}
              </span>
            </div>

            <label>Captcha</label>
            <div className="captcha-box">
              <span>{captcha}</span>
              <button type="button" onClick={generateCaptcha}>
                🔄
              </button>
            </div>

            <input
              placeholder="Enter Captcha"
              value={captchaInput}
              onChange={(e) => setCaptchaInput(e.target.value)}
              required
            />

            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Logging in..." : "Login"}
            </button>

            <div className="login-links">
              <button type="button" onClick={onOpenForgot}>
                Forgot Password?
              </button>
              <button type="button" onClick={onOpenRegister}>
                Create Account
              </button>
              <button type="button" onClick={onBackToHome}>
                ← Back to Home
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}