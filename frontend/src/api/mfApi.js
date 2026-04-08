import api from "./axiosInstance";

export async function fetchMfCagrSummary() {
  const res = await api.get("investment/mf-cagr-summary/");
  return res.data;
}