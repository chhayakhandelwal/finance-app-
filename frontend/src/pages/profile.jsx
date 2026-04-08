import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import "./profile.css";

const TOKEN_KEYS = ["token", "accessToken", "authToken", "jwt"];

const readToken = () => {
  for (const k of TOKEN_KEYS) {
    const v = localStorage.getItem(k);
    if (v) return v;
  }
  return null;
};

const API_BASE_URL = (
  process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

export default function Profile() {
  const [token] = useState(readToken());

  const authHeaders = useMemo(() => {
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, [token]);

  const [user, setUser] = useState(null);
  const [draft, setDraft] = useState({
    username: "",
    first_name: "",
    last_name: "",
    email: "",
  });

  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const fetchProfile = async () => {
    if (!token) {
      setError("User not logged in");
      setLoading(false);
      return;
    }

    setError("");

    try {
      const res = await axios.get(`${API_BASE_URL}/api/profile/`, {
        headers: authHeaders,
        timeout: 15000,
      });

      const data = res?.data || {};

      setUser(data);
      setDraft({
        username: data.username || "",
        first_name: data.first_name || "",
        last_name: data.last_name || "",
        email: data.email || "",
      });
    } catch (e) {
      setError(
        e?.response?.data?.message ||
          e?.response?.data?.detail ||
          "Failed to load profile"
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDraftChange = (field) => (e) => {
    const value = e.target.value;
    setDraft((prev) => ({ ...prev, [field]: value }));
  };

  const startEditing = () => {
    setEditing(true);
    setOk("");
    setError("");
  };

  const cancelEditing = () => {
    setEditing(false);
    setDraft({
      username: user?.username || "",
      first_name: user?.first_name || "",
      last_name: user?.last_name || "",
      email: user?.email || "",
    });
    setError("");
    setOk("");
  };

  const saveProfile = async () => {
    if (!token) {
      setError("User not logged in");
      return;
    }

    setSaving(true);
    setError("");
    setOk("");

    try {
      const payload = {
        username: draft.username.trim(),
        first_name: draft.first_name.trim(),
        last_name: draft.last_name.trim(),
        email: draft.email.trim(),
      };

      const res = await axios.patch(`${API_BASE_URL}/api/profile/`, payload, {
        headers: authHeaders,
        timeout: 15000,
      });

      const data = res?.data || {};

      setUser(data);
      localStorage.setItem("username", data.username || "");
      setDraft({
        username: data.username || "",
        first_name: data.first_name || "",
        last_name: data.last_name || "",
        email: data.email || "",
      });
      setEditing(false);
      setOk("Profile updated successfully");
    } catch (e) {
      const data = e?.response?.data;
      const msg =
        data?.message ||
        data?.detail ||
        (data ? JSON.stringify(data) : "Failed to update profile");
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="profile-container">Loading profile…</div>;
  }

  if (error && !user) {
    return <div className="profile-container error">{error}</div>;
  }

  const fullName =
    `${user?.first_name || ""} ${user?.last_name || ""}`.trim() || "-";

  return (
    <div className="profile-container">
      <h2>My Profile</h2>

      {error ? <div className="profile-alert error">{error}</div> : null}
      {ok ? <div className="profile-alert ok">{ok}</div> : null}

      <div className="profile-card">
        <p>
          <strong>Member Since:</strong> {user?.joined || "-"}
        </p>

        {!editing ? (
          <>
            <p>
              <strong>Username:</strong> {user?.username || "-"}
            </p>
            <p>
              <strong>First Name:</strong> {user?.first_name || "-"}
            </p>
            <p>
              <strong>Last Name:</strong> {user?.last_name || "-"}
            </p>
            <p>
              <strong>Full Name:</strong> {fullName}
            </p>
            <p>
              <strong>Email:</strong> {user?.email || "-"}
            </p>
          </>
        ) : (
          <>
            <div className="profile-field">
              <label>Username</label>
              <input
                value={draft.username}
                onChange={handleDraftChange("username")}
                placeholder="Username"
              />
            </div>

            <div className="profile-field">
              <label>First Name</label>
              <input
                value={draft.first_name}
                onChange={handleDraftChange("first_name")}
                placeholder="First name"
              />
            </div>

            <div className="profile-field">
              <label>Last Name</label>
              <input
                value={draft.last_name}
                onChange={handleDraftChange("last_name")}
                placeholder="Last name"
              />
            </div>

            <div className="profile-field">
              <label>Email</label>
              <input
                type="email"
                value={draft.email}
                onChange={handleDraftChange("email")}
                placeholder="you@example.com"
              />
            </div>
          </>
        )}
      </div>

      <div className="profile-actions">
        {!editing ? (
          <button onClick={startEditing}>Edit Profile</button>
        ) : (
          <>
            <button onClick={saveProfile} disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </button>

            <button onClick={cancelEditing} disabled={saving}>
              Cancel
            </button>
          </>
        )}
      </div>
    </div>
  );
}