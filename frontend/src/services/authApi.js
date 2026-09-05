import { apiRequest, clearAdminToken, getAdminToken, setAdminToken } from "./api";

const BASE_PATH = "/api/admin/auth";

export async function login(email, password) {
  const result = await apiRequest(`${BASE_PATH}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  setAdminToken(result.token);
  return result;
}

export function logout() {
  clearAdminToken();
}

export function isLoggedIn() {
  return !!getAdminToken();
}
