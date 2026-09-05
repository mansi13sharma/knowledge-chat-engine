import { apiRequest } from "./api";

const BASE_PATH = "/api/admin/knowledge-base";

// Display-only default — the backend (KB_MAX_UPLOAD_MB) is the real,
// enforced limit; keep this in sync with backend/.env.example.
export const MAX_UPLOAD_MB = 10;

export function listDocuments() {
  return apiRequest(`${BASE_PATH}/documents`);
}

export function getStats() {
  return apiRequest(`${BASE_PATH}/stats`);
}

export function uploadDocument(file, category) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("category", category);
  return apiRequest(`${BASE_PATH}/documents`, { method: "POST", body: formData });
}

export function deleteDocument(documentId) {
  return apiRequest(`${BASE_PATH}/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" });
}

export function reindexDocument(documentId) {
  return apiRequest(`${BASE_PATH}/documents/${encodeURIComponent(documentId)}/reindex`, { method: "POST" });
}
