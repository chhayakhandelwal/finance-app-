import React, { useState } from "react";
import "./register.css";
import logo from "./logo.png";
import { FaEye, FaEyeSlash } from "react-icons/fa";
import axios from "axios";

const API_BASE_URL =
  (process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const Register = ({ onRegistered, onBackToLogin }) => {
  const [formData, setFormData] = useState({
    username: "",
    firstName: "",
    lastName: "",
    email: "",
    gender: "",
    password: "",
    confirmPassword: "",
  });

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [errors, setErrors] = useState({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
    firstName: "",
    lastName: "",
  });

  const [successMessage, setSuccessMessage] = useState("");
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

  const handleChange = (e) => {
    const { name, value } = e.target;

    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));

    setErrors((prev) => ({
      ...prev,
      [name]: "",
    }));
  };

  const togglePassword = (type) => {
    if (type === "password") {
      setShowPassword((s) => !s);
    } else {
      setShowConfirmPassword((s) => !s);
    }
  };

  const validate = () => {
    const tempErrors = {
      username: "",
      email: "",
      password: "",
      confirmPassword: "",
      firstName: "",
      lastName: "",
    };

    let isValid = true;

    const usernameRegex = /^(?=.*[A-Z])(?=.*\d).+$/;
    const passwordRegex = /^(?=.*[A-Z])(?=.*\d).{8,}$/;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
    const nameRegex = /^[A-Za-z]+$/;

    const username = formData.username.trim();
    const email = formData.email.trim();
    const password = formData.password;
    const confirmPassword = formData.confirmPassword;
    const firstName = formData.firstName.trim();
    const lastName = formData.lastName.trim();

    if (!firstName) {
      tempErrors.firstName = "First name is required.";
      isValid = false;
    } else if (!nameRegex.test(firstName)) {
      tempErrors.firstName = "Only alphabets allowed.";
      isValid = false;
    }

    if (!lastName) {
      tempErrors.lastName = "Last name is required.";
      isValid = false;
    } else if (!nameRegex.test(lastName)) {
      tempErrors.lastName = "Only alphabets allowed.";
      isValid = false;
    }

    if (!username) {
      tempErrors.username = "Username is required.";
      isValid = false;
    } else if (!usernameRegex.test(username)) {
      tempErrors.username =
        "Username must contain at least one uppercase letter and one number.";
      isValid = false;
    }

    if (!email) {
      tempErrors.email = "Email is required.";
      isValid = false;
    } else if (!emailRegex.test(email)) {
      tempErrors.email = "Please enter a valid email address.";
      isValid = false;
    }

    if (!password) {
      tempErrors.password = "Password is required.";
      isValid = false;
    } else if (!passwordRegex.test(password)) {
      tempErrors.password =
        "Password must be at least 8 characters long and include one uppercase letter and one number.";
      isValid = false;
    }

    if (!confirmPassword) {
      tempErrors.confirmPassword = "Confirm Password is required.";
      isValid = false;
    } else if (password !== confirmPassword) {
      tempErrors.confirmPassword = "Passwords do not match.";
      isValid = false;
    }

    setErrors(tempErrors);
    return isValid;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;

    if (!validate()) {
      showToast("Please fix the highlighted errors.", "error");
      return;
    }

    setIsSubmitting(true);
    setSuccessMessage("");

    try {
      const payload = {
        username: formData.username.trim(),
        password: formData.password,
        email: formData.email.trim().toLowerCase(),
        first_name: formData.firstName.trim(),
        last_name: formData.lastName.trim(),
        gender: formData.gender,
      };

      await axios.post(`${API_BASE_URL}/api/register/`, payload, {
        headers: { "Content-Type": "application/json" },
        timeout: 15000,
      });

      setSuccessMessage("Registration successful! Redirecting to login...");
      showToast("Registration successful", "success");

      setTimeout(() => {
        onRegistered?.();
      }, 800);
    } catch (err) {
      console.log("REGISTER STATUS:", err?.response?.status);
      console.log("REGISTER DATA:", err?.response?.data);
      console.log("REGISTER FULL ERROR:", err);

      const msg =
        err?.response?.data?.message ||
        err?.response?.data?.detail ||
        (err?.response?.data ? JSON.stringify(err.response.data) : err.message);

      showToast(msg || "Registration failed", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="register-page">
      {toast.show && (
        <div className={`login-toast login-toast--${toast.type}`}>
          {toast.message}
        </div>
      )}

      <header className="header">
        <div className="header-brand">
          <div className="logo-box">
            <img src={logo} alt="FinGrrow Logo" />
          </div>
          <h1>FinGrrow</h1>
        </div>
      </header>

      <div className="register-card">
        <div className="register-card-head">
          <h2 className="register-title">Create Account</h2>
          <p className="register-subtitle">
            Fill the details below to register. You can login immediately after registration.
          </p>
        </div>

        <div className="register-body">
          <form onSubmit={handleSubmit} noValidate>
            <div className="register-grid">
              <div className="field">
                <label>Username</label>
                <input
                  className="input"
                  type="text"
                  name="username"
                  value={formData.username}
                  onChange={handleChange}
                  required
                  placeholder="Must include uppercase & number"
                />
                {errors.username && (
                  <div className="helper-error">{errors.username}</div>
                )}
              </div>

              <div className="field">
                <label>Email</label>
                <input
                  className="input"
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  required
                  placeholder="Enter your email"
                />
                {errors.email && (
                  <div className="helper-error">{errors.email}</div>
                )}
              </div>

              <div className="field">
                <label>First Name</label>
                <input
                  className="input"
                  type="text"
                  name="firstName"
                  value={formData.firstName}
                  onChange={handleChange}
                  required
                  placeholder="Enter first name"
                />
                {errors.firstName && (
                  <div className="helper-error">{errors.firstName}</div>
                )}
              </div>

              <div className="field">
                <label>Last Name</label>
                <input
                  className="input"
                  type="text"
                  name="lastName"
                  value={formData.lastName}
                  onChange={handleChange}
                  required
                  placeholder="Enter last name"
                />
                {errors.lastName && (
                  <div className="helper-error">{errors.lastName}</div>
                )}
              </div>

              <div className="field full">
                <label>Gender</label>
                <div className="gender-row">
                  {["Male", "Female", "Other"].map((g) => (
                    <label key={g}>
                      <input
                        type="radio"
                        name="gender"
                        value={g}
                        checked={formData.gender === g}
                        onChange={handleChange}
                        required
                      />
                      {g}
                    </label>
                  ))}
                </div>
              </div>

              <div className="field">
                <label>Password</label>
                <div className="password-wrap">
                  <input
                    className="input"
                    type={showPassword ? "text" : "password"}
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    required
                    placeholder="Enter password"
                  />
                  <span
                    className="eye-btn"
                    onClick={() => togglePassword("password")}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        togglePassword("password");
                      }
                    }}
                  >
                    {showPassword ? <FaEyeSlash /> : <FaEye />}
                  </span>
                </div>
                {errors.password && (
                  <div className="helper-error">{errors.password}</div>
                )}
              </div>

              <div className="field">
                <label>Confirm Password</label>
                <div className="password-wrap">
                  <input
                    className="input"
                    type={showConfirmPassword ? "text" : "password"}
                    name="confirmPassword"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    required
                    placeholder="Confirm password"
                  />
                  <span
                    className="eye-btn"
                    onClick={() => togglePassword("confirm")}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        togglePassword("confirm");
                      }
                    }}
                  >
                    {showConfirmPassword ? <FaEyeSlash /> : <FaEye />}
                  </span>
                </div>
                {errors.confirmPassword && (
                  <div className="helper-error">{errors.confirmPassword}</div>
                )}
              </div>
            </div>

            <div className="actions">
              <button type="submit" className="btn-primary" disabled={isSubmitting}>
                {isSubmitting ? "Registering..." : "Register"}
              </button>

              <button type="button" className="btn-secondary" onClick={onBackToLogin}>
                Back to Login
              </button>
            </div>

            {successMessage && <div className="success">{successMessage}</div>}
          </form>
        </div>
      </div>
    </div>
  );
};

export default Register;