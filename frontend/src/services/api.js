// Single source of truth for the backend origin — configurable via
// VITE_API_BASE_URL so it's never hardcoded per-component.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const ADMIN_TOKEN_KEY = "tef_admin_token";

export function getAdminToken() {
  try {
    return localStorage.getItem(ADMIN_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAdminToken(token) {
  try {
    localStorage.setItem(ADMIN_TOKEN_KEY, token);
  } catch {
    // Storage unavailable (private browsing, disabled site data, etc) — the
    // session just won't survive a reload, which is a reasonable fallback.
  }
}

export function clearAdminToken() {
  try {
    localStorage.removeItem(ADMIN_TOKEN_KEY);
  } catch {
    // Nothing to do if storage isn't available.
  }
}

async function readErrorMessage(response) {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) {
      return data.detail.map((d) => d.msg || JSON.stringify(d)).join(", ");
    }
  } catch {
    // Response wasn't JSON — fall through to a generic message below.
  }
  return `Request failed with status ${response.status}`;
}

/**
 * Thin fetch wrapper: resolves against API_BASE_URL, attaches the admin
 * session token (if any) as a Bearer header, throws a readable Error (from
 * the backend's {"detail": "..."} body) on a non-OK response, and returns
 * parsed JSON otherwise. A 401 clears the stored token and throws an Error
 * flagged `isAuthError` so callers can drop back to the login screen.
 */
export async function apiRequest(path, options = {}) {
  const token = getAdminToken();
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (response.status === 401) {
    clearAdminToken();
    const err = new Error("Your session has expired. Please log in again.");
    err.isAuthError = true;
    throw err;
  }
  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }
  if (response.status === 204) return null;
  return response.json();
}
