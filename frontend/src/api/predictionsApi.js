import axios from "axios";

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

export async function fetchFundPredictions(category = "largecap", limit = 20) {
  const token = readToken();

  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  const res = await axios.get(`${API_BASE_URL}/api/investment/predictions/`, {
    headers,
    params: { category, limit },
    timeout: 20000,
  });

  return res.data;
}