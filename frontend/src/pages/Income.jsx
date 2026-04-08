import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { FaPlus, FaWallet, FaCalendarAlt } from "react-icons/fa";
import "./Income.css";

/* ---------- TOKEN UTILS ---------- */
const TOKEN_KEYS = ["token", "accessToken", "authToken", "jwt"];
const STABLE_META_KEY = "fin_stable_income_meta_v4";
const API_PATH = "/api/income/";

const readToken = () => {
  for (const k of TOKEN_KEYS) {
    const v = localStorage.getItem(k);
    if (v) return v;
  }
  return null;
};

export default function Income() {
  const [items, setItems] = useState([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [error, setError] = useState("");
  const [stableMeta, setStableMeta] = useState(readStableMeta);

  const [editContext, setEditContext] = useState({
    mode: "add", // add | series | single_month
    targetId: null,
    parentId: null,
    monthKey: null,
  });

  const [form, setForm] = useState({
    source: "",
    category: "SALARY",
    amount: "",
    date: "",
    description: "",
    isStable: false,
  });

  const API_BASE_URL =
    (process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

  /* ---------- AXIOS INSTANCE ---------- */
  const api = useMemo(() => {
    const instance = axios.create({
      baseURL: API_BASE_URL,
      timeout: 15000,
      headers: { "Content-Type": "application/json" },
    });

    instance.interceptors.request.use((config) => {
      const token = readToken();
      if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    return instance;
  }, [API_BASE_URL]);

  const ensureLoggedIn = () => {
    if (!readToken()) {
      setError("Please login to manage income.");
      return false;
    }
    return true;
  };

  /* ---------- FETCH ---------- */
  const fetchIncome = useCallback(async () => {
    if (!ensureLoggedIn()) {
      setItems([]);
      return;
    }

    setError("");
    try {
      const res = await api.get(API_PATH);
      setItems(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      console.error("FETCH INCOME ERROR:", e?.response?.data || e);
      setError(e?.response?.data?.detail || "Failed to load income data.");
    }
  }, [api]);

  useEffect(() => {
    fetchIncome();
  }, [fetchIncome]);

  /* ---------- STABLE META HELPERS ---------- */
  const persistStableMeta = useCallback((nextOrUpdater) => {
    setStableMeta((prev) => {
      const next =
        typeof nextOrUpdater === "function" ? nextOrUpdater(prev) : nextOrUpdater;
      localStorage.setItem(STABLE_META_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const visibleMonths = useMemo(() => getLast12Months(), []);
  const visibleMonthSet = useMemo(() => new Set(visibleMonths), [visibleMonths]);

  /* ---------- REAL ROWS ---------- */
  console.log("RAW INCOME ITEMS:", items);
  console.log(
  "CHECK DUPLICATES:",
  items.map((item) => ({
    id: item.id,
    date: item.date || item.income_date,
    source: item.source,
    category: item.category,
    amount: item.amount,
  }))
);


const realRows = useMemo(() => {
  const seen = new Set();

  return items
    .filter((item) => {
      const monthKey = getMonthKey(item.date || item.income_date);
      return monthKey && visibleMonthSet.has(monthKey);
    })
    .filter((item) => {
      const key = makeMatchKey(
        String(item.source || "").trim(),
        String(item.category || "").trim(),
        getMonthKey(item.date || item.income_date)
      );

      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map((item) => ({
      ...item,
      isVirtual: false,
    }));
}, [items, visibleMonthSet]);

  const realMatchSet = useMemo(() => {
  const s = new Set();

  realRows.forEach((row) => {
    const monthKey = getMonthKey(row.income_date || row.date);
    if (!monthKey) return;

    s.add(
      makeMatchKey(
        String(row.source || "").trim(),
        String(row.category || "").trim(),
        monthKey
      )
    );
  });

  return s;
}, [realRows]);

  /* ---------- AUTO / VIRTUAL ROWS ---------- */
  const virtualRows = useMemo(() => {
    const rows = [];

    items.forEach((item) => {
      const meta = stableMeta[item.id];
      if (!meta) return;

      const startMonth = getMonthKey(meta.startDate || item.date || item.income_date);
      if (!startMonth) return;

      const stopAfterMonth = meta.stopAfterMonth || null;
      const skippedMonths = Array.isArray(meta.skippedMonths) ? meta.skippedMonths : [];
      const dayOfMonth = meta.dayOfMonth || getDayFromDate(item.date || item.income_date) || 1;

      visibleMonths.forEach((monthKey) => {
        if (monthKey < startMonth) return;
        if (!meta.active && stopAfterMonth && monthKey > stopAfterMonth) return;
        if (skippedMonths.includes(monthKey)) return;

        const matchKey = makeMatchKey(
          String(item.source || "").trim(),
          String(item.category || "").trim(),
          monthKey
        );
        // same month me real row already hai to auto row mat dikhao
        if (realMatchSet.has(matchKey)) return;

        const alreadyRealForMonth = items.some((dbRow) => {
          return (
            getMonthKey(dbRow.income_date || dbRow.date) === monthKey &&
            String(dbRow.source || "").trim().toLowerCase() === String(item.source || "").trim().toLowerCase() &&
            String(dbRow.category || "").trim().toLowerCase() === String(item.category || "").trim().toLowerCase()
          );
        });

        if (alreadyRealForMonth) return;

        rows.push({
          id: `virtual-${item.id}-${monthKey}`,
          parentId: item.id,
          source: item.source,
          category: item.category,
          amount: item.amount,
          description: item.description || "",
          date: buildMonthDate(monthKey, dayOfMonth),
          income_date: buildMonthDate(monthKey, dayOfMonth),
          isVirtual: true,
          isStableAuto: true,
          autoMonthKey: monthKey,
        });
      });
    });

    return rows;
  }, [items, stableMeta, visibleMonths, realMatchSet]);

  /* ---------- PUSH AUTO ROWS TO DB ---------- */
  useEffect(() => {
    if (!ensureLoggedIn()) return;
    if (!virtualRows.length) return;

    const missingVirtualRows = virtualRows.filter((row) => {
      return !items.some((item) => {
        return (
          getMonthKey(item.date || item.income_date) === row.autoMonthKey &&
          String(item.source || "").trim().toLowerCase() ===
            String(row.source || "").trim().toLowerCase() &&
          String(item.category || "").trim().toLowerCase() ===
            String(row.category || "").trim().toLowerCase()
        );
      });
    });

    if (!missingVirtualRows.length) return;

    let cancelled = false;

    const pushAutoIncome = async () => {
      try {
        for (const row of missingVirtualRows) {
          if (cancelled) return;

          await api.post(API_PATH, {
            source: row.source,
            category: row.category,
            amount: Number(row.amount),
            date: row.date,
            description: row.description || "",
          });
        }

        if (!cancelled) {
          await fetchIncome();
        }
      } catch (err) {
        console.error("AUTO INCOME PUSH ERROR:", err?.response?.data || err);
      }
    };

    pushAutoIncome();

    return () => {
      cancelled = true;
    };
  }, [virtualRows, items, api, fetchIncome]);

  /* ---------- FINAL TABLE ROWS ---------- */
  const tableRows = useMemo(() => {
    const merged = [...realRows, ...virtualRows];

    merged.sort((a, b) => {
      const da = new Date(a.date || a.income_date).getTime();
      const db = new Date(b.date || b.income_date).getTime();
      return db - da;
    });

    return merged;
  }, [realRows, virtualRows]);

  /* ---------- SUMMARY ---------- */
  const summary = useMemo(() => {
    const currentMonth = getMonthKey(new Date());

    const total = tableRows.reduce((sum, item) => {
      const mk = getMonthKey(item.date || item.income_date);
      return mk === currentMonth ? sum + Number(item.amount || 0) : sum;
    }, 0);

    return { total };
  }, [tableRows]);

  /* ---------- MODAL HANDLERS ---------- */
  const resetModal = () => {
    setModalOpen(false);
    setEditContext({
      mode: "add",
      targetId: null,
      parentId: null,
      monthKey: null,
    });
    setForm({
      source: "",
      category: "SALARY",
      amount: "",
      date: "",
      description: "",
      isStable: false,
    });
  };

  const openAdd = () => {
    if (!ensureLoggedIn()) return;

    setEditContext({
      mode: "add",
      targetId: null,
      parentId: null,
      monthKey: null,
    });

    setForm({
      source: "",
      category: "SALARY",
      amount: "",
      date: todayISO(),
      description: "",
      isStable: false,
    });

    setModalOpen(true);
  };

  const openEdit = (row) => {
    if (row.isVirtual) {
      setEditContext({
        mode: "single_month",
        targetId: null,
        parentId: row.parentId,
        monthKey: row.autoMonthKey,
      });

      setForm({
        source: row.source || "",
        category: row.category || "SALARY",
        amount: row.amount ?? "",
        date: row.date || row.income_date || todayISO(),
        description: row.description || "",
        isStable: false,
      });

      setModalOpen(true);
      return;
    }

    const meta = stableMeta[row.id];
    const isCurrentlyStable = !!meta?.active;

    setEditContext({
      mode: "series",
      targetId: row.id,
      parentId: row.id,
      monthKey: null,
    });

    setForm({
      source: row.source || "",
      category: row.category || "SALARY",
      amount: row.amount ?? "",
      date: row.date || row.income_date || todayISO(),
      description: row.description || "",
      isStable: isCurrentlyStable,
    });

    setModalOpen(true);
  };

  /* ---------- SAVE ---------- */
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!ensureLoggedIn()) return;

    const payload = {
      source: (form.source || "").trim(),
      category: form.category,
      amount: Number(form.amount),
      date: form.date,
      description: (form.description || "").trim(),
    };

    try {
      if (editContext.mode === "series" && editContext.targetId) {
        await api.put(`${API_PATH}${editContext.targetId}/`, payload);

        persistStableMeta((prev) => {
          const next = { ...prev };
          const oldMeta = prev[editContext.targetId];

          if (form.isStable) {
            next[editContext.targetId] = {
              active: true,
              startDate: oldMeta?.startDate || payload.date,
              dayOfMonth: getDayFromDate(payload.date),
              stopAfterMonth: null,
              skippedMonths: oldMeta?.skippedMonths || [],
            };
          } else if (oldMeta) {
            next[editContext.targetId] = {
              ...oldMeta,
              active: false,
              dayOfMonth: getDayFromDate(payload.date),
              stopAfterMonth: getMonthKey(new Date()),
            };
          } else {
            delete next[editContext.targetId];
          }

          return next;
        });
      } else if (editContext.mode === "single_month" && editContext.parentId && editContext.monthKey) {
        await api.post(API_PATH, payload);

        persistStableMeta((prev) => {
          const next = { ...prev };
          const oldMeta = next[editContext.parentId] || {};
          const oldSkipped = Array.isArray(oldMeta.skippedMonths) ? oldMeta.skippedMonths : [];

          next[editContext.parentId] = {
            ...oldMeta,
            skippedMonths: Array.from(new Set([...oldSkipped, editContext.monthKey])),
          };

          return next;
        });
      } else {
        const res = await api.post(API_PATH, payload);
        const created = res?.data;

        if (created?.id) {
          persistStableMeta((prev) => {
            const next = { ...prev };

            if (form.isStable) {
              next[created.id] = {
                active: true,
                startDate: payload.date,
                dayOfMonth: getDayFromDate(payload.date),
                stopAfterMonth: null,
                skippedMonths: [],
              };
            }

            return next;
          });
        }
      }

      resetModal();
      await fetchIncome();
    } catch (e2) {
      console.error("SAVE INCOME ERROR:", e2?.response?.data || e2);
      setError(e2?.response?.data?.detail || "Could not save income.");
    }
  };

  /* ---------- DELETE ---------- */
  const handleDelete = async (row) => {
    if (!ensureLoggedIn()) return;

    try {
      if (row?.isVirtual) {
        persistStableMeta((prev) => {
          const next = { ...prev };
          const oldMeta = next[row.parentId] || {};
          const oldSkipped = Array.isArray(oldMeta.skippedMonths) ? oldMeta.skippedMonths : [];

          next[row.parentId] = {
            ...oldMeta,
            skippedMonths: Array.from(new Set([...oldSkipped, row.autoMonthKey])),
          };

          return next;
        });
        return;
      }

      await api.delete(`${API_PATH}${row.id}/`);

      persistStableMeta((prev) => {
        const next = { ...prev };
        delete next[row.id];
        return next;
      });

      await fetchIncome();
    } catch (e) {
      console.error("DELETE INCOME ERROR:", e?.response?.data || e);
      setError(e?.response?.data?.detail || "Could not delete income.");
    }
  };

  const modalTitle =
    editContext.mode === "single_month"
      ? "Edit This Month Income"
      : editContext.mode === "series"
      ? "Edit Income"
      : "Add Income";

  return (
    <div className="inc">
      <div className="inc-head">
        <div>
          <h2>Income</h2>
          <p>Track income from all sources</p>
        </div>
        <div className="inc-actions">
          <button className="inc-btn primary" onClick={openAdd}>
            <FaPlus /> Add Income
          </button>
        </div>
      </div>

      {error && <div className="inc-alert">{error}</div>}

      <div className="inc-summary">
        <div className="inc-kpi">
          <FaWallet />
          <div>
            <div className="k">Total Income</div>
            <div className="v">{inr(summary.total)}</div>
          </div>
        </div>
      </div>

      <div className="inc-table">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Source</th>
              <th>Category</th>
              <th className="right">Amount</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {tableRows.map((row) => {
              const meta = !row.isVirtual ? stableMeta[row.id] : null;
const showStableBadge = !!meta?.active;

const showAutoBadge =
  row.isVirtual ||
  (!showStableBadge &&
    Object.values(stableMeta).some((m) => {
      const rowMonth = getMonthKey(row.date || row.income_date);
      const startMonth = getMonthKey(m?.startDate);
      const skipped = Array.isArray(m?.skippedMonths) ? m.skippedMonths : [];

      return (
        m?.active &&
        rowMonth &&
        startMonth &&
        rowMonth >= startMonth &&
        !skipped.includes(rowMonth)
      );
    }));

              return (
                <tr
                  key={row.id}
                  className={row.isVirtual ? "inc-auto-row" : ""}
                >
                  <td>
                    <FaCalendarAlt /> {row.date || row.income_date}
                    {row.isVirtual && <span className="inc-row-badge">Auto</span>}
{showStableBadge && <span className="inc-row-badge stable">Stable</span>}
                  </td>
                  <td>{row.source}</td>
                  <td>{row.category}</td>
                  <td className="right">{inr(row.amount)}</td>
                  <td>
                    {row.isVirtual ? (
                      <>
                        <button onClick={() => openEdit(row)}>Edit This Month</button>
                        <button onClick={() => handleDelete(row)}>Delete This Month</button>
                      </>
                    ) : (
                      <>
                        <button onClick={() => openEdit(row)}>Edit</button>
                        <button onClick={() => handleDelete(row)}>Delete</button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}

            {!tableRows.length && (
              <tr>
                <td colSpan="5" className="empty">
                  No income added yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {modalOpen && (
        <div className="inc-overlay" onClick={resetModal}>
          <div className="inc-modal" onClick={(e) => e.stopPropagation()}>
            <h3>{modalTitle}</h3>

            <form onSubmit={handleSubmit}>
              <input
                placeholder="Name"
                value={form.source}
                onChange={(e) => setForm({ ...form, source: e.target.value })}
                required
              />

              <select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              >
                <option value="SALARY">SALARY</option>
                <option value="FREELANCE">FREELANCE</option>
                <option value="BUSINESS">BUSINESS</option>
                <option value="RENTAL">RENTAL</option>
                <option value="INTEREST">INTEREST</option>
                <option value="OTHER">OTHER</option>
              </select>

              <input
                type="number"
                placeholder="Amount"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
                required
              />

              <input
                type="date"
                value={form.date}
                onChange={(e) => setForm({ ...form, date: e.target.value })}
                required
              />

              <textarea
                placeholder="Optional description"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />

              {editContext.mode !== "single_month" && (
                <>
                  <label className="inc-check">
                    <input
                      type="checkbox"
                      checked={form.isStable}
                      onChange={(e) =>
                        setForm((prev) => ({ ...prev, isStable: e.target.checked }))
                      }
                    />
                    <span>This is stable income. Add it automatically every month.</span>
                  </label>

                  <div className="inc-modal-hint">
                    If you remove stable income and save, it will stop auto-adding from next month.
                  </div>
                </>
              )}

              {editContext.mode === "single_month" && (
                <div className="inc-modal-hint">
                  This will create a separate income entry only for this month. The stable series will remain unchanged for other months.
                </div>
              )}

              <div className="inc-modal-actions">
                <button type="button" onClick={resetModal}>
                  Cancel
                </button>
                <button type="submit" className="primary">
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------- HELPERS ---------- */

function inr(x) {
  return Number(x || 0).toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  });
}

function todayISO() {
  return new Date().toISOString().split("T")[0];
}

function getMonthKey(dateInput) {
  if (!dateInput) return "";
  const d = new Date(dateInput);
  if (Number.isNaN(d.getTime())) return "";
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
}

function getDayFromDate(dateInput) {
  const d = new Date(dateInput);
  if (Number.isNaN(d.getTime())) return 1;
  return d.getDate();
}

function buildMonthDate(monthKey, day = 1) {
  const [year, month] = monthKey.split("-").map(Number);
  const maxDays = new Date(year, month, 0).getDate();
  const safeDay = Math.min(day, maxDays);

  return `${year}-${String(month).padStart(2, "0")}-${String(safeDay).padStart(2, "0")}`;
}

function makeMatchKey(source, category, monthKey) {
  return `${String(source || "").trim().toLowerCase()}__${String(category || "")
    .trim()
    .toLowerCase()}__${String(monthKey || "").trim()}`;
}

function getLast12Months() {
  const arr = [];
  const now = new Date();

  for (let i = 11; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    arr.push(getMonthKey(d));
  }

  return arr;
}

function readStableMeta() {
  try {
    const raw = localStorage.getItem(STABLE_META_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}