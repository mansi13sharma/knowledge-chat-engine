// Single source of truth for the backend origin — configurable via
// VITE_API_BASE_URL so it's never hardcoded per-component.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

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
 * Thin fetch wrapper: resolves against API_BASE_URL, throws a readable
 * Error (from the backend's {"detail": "..."} body) on a non-OK response,
 * and returns parsed JSON otherwise.
 */
export async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }
  if (response.status === 204) return null;
  return response.json();
}
