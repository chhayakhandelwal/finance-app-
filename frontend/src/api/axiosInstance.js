import axios from "axios";

const API_BASE_URL =
  (process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/`,
  timeout: 20000,
});

// ✅ Automatically attach Bearer token on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token") || localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;