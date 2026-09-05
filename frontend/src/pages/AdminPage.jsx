import { useCallback, useEffect, useMemo, useState } from "react";
import KnowledgeBaseStats from "../components/admin/KnowledgeBaseStats";
import DocumentUpload from "../components/admin/DocumentUpload";
import DocumentTable from "../components/admin/DocumentTable";
import DeleteDocumentModal from "../components/admin/DeleteDocumentModal";
import Toast from "../components/admin/Toast";
import AdminLogin from "../components/admin/AdminLogin";
import { deleteDocument, getStats, listDocuments, reindexDocument } from "../services/knowledgeBaseApi";
import { isLoggedIn, logout } from "../services/authApi";
import "./AdminPage.css";

const EMPTY_STATS = { total_documents: 0, total_chunks: 0, categories: 0 };

function AdminPage() {
  const [loggedIn, setLoggedIn] = useState(isLoggedIn());
  const [documents, setDocuments] = useState([]);
  const [stats, setStats] = useState(EMPTY_STATS);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");

  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [reindexingId, setReindexingId] = useState(null);
  const [toast, setToast] = useState(null);

  const showToast = useCallback((type, message) => setToast({ type, message }), []);

  const refresh = useCallback(async () => {
    setLoadError(null);
    try {
      const [docsRes, statsRes] = await Promise.all([listDocuments(), getStats()]);
      setDocuments(docsRes.documents);
      setStats(statsRes);
    } catch (err) {
      if (err.isAuthError) {
        setLoggedIn(false);
      } else {
        setLoadError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (loggedIn) refresh();
  }, [loggedIn, refresh]);

  useEffect(() => {
    if (!toast) return undefined;
    const timer = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(timer);
  }, [toast]);

  const categories = useMemo(
    () => Array.from(new Set(documents.map((d) => d.category))).sort(),
    [documents]
  );

  const filteredDocuments = useMemo(() => {
    const term = search.trim().toLowerCase();
    return documents.filter((d) => {
      const matchesSearch = !term || d.filename.toLowerCase().includes(term);
      const matchesCategory = categoryFilter === "all" || d.category === categoryFilter;
      return matchesSearch && matchesCategory;
    });
  }, [documents, search, categoryFilter]);

  const handleUploaded = (doc) => {
    showToast(
      "success",
      `${doc.filename} indexed successfully. ${doc.chunks} chunk${doc.chunks === 1 ? "" : "s"} created.`
    );
    refresh();
  };

  const handleReindex = async (doc) => {
    setReindexingId(doc.id);
    try {
      const result = await reindexDocument(doc.id);
      showToast("success", `${doc.filename} re-indexed. ${result.document.chunks} chunks.`);
    } catch (err) {
      if (err.isAuthError) {
        setLoggedIn(false);
        return;
      }
      showToast("error", err.message);
    } finally {
      setReindexingId(null);
      refresh();
    }
  };

  const handleDeleteConfirmed = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteDocument(deleteTarget.id);
      showToast("success", `${deleteTarget.filename} deleted.`);
      setDeleteTarget(null);
      refresh();
    } catch (err) {
      if (err.isAuthError) {
        setLoggedIn(false);
        return;
      }
      showToast("error", err.message);
    } finally {
      setDeleting(false);
    }
  };

  const handleLogout = () => {
    logout();
    setLoggedIn(false);
  };

  if (!loggedIn) {
    return <AdminLogin onSuccess={() => setLoggedIn(true)} />;
  }

  return (
    <div className="admin-shell">
      <header className="admin-header">
        <div>
          <h1>Knowledge Base</h1>
          <p>Manage documents used by the AI assistant</p>
        </div>
        <button type="button" className="admin-logout-btn" onClick={handleLogout}>
          Log out
        </button>
      </header>

      <KnowledgeBaseStats stats={stats} />

      <DocumentUpload
        categories={categories}
        onUploaded={handleUploaded}
        onError={(err) => (err.isAuthError ? setLoggedIn(false) : showToast("error", err.message))}
      />

      <section className="kb-card">
        <div className="kb-list-header">
          <h2>Knowledge Base Documents</h2>
          <div className="kb-filters">
            <input
              type="search"
              placeholder="Search by filename…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search documents by filename"
            />
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              aria-label="Filter by category"
            >
              <option value="all">All categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        </div>

        {loading ? (
          <p className="kb-status-text">Loading documents…</p>
        ) : loadError ? (
          <p className="kb-status-text kb-status-error">Could not load documents: {loadError}</p>
        ) : documents.length === 0 ? (
          <div className="kb-empty-state">
            <p>No documents indexed yet.</p>
            <p className="kb-empty-subtext">
              Upload your first document to start building the assistant's knowledge base.
            </p>
          </div>
        ) : filteredDocuments.length === 0 ? (
          <p className="kb-status-text">No documents match your search.</p>
        ) : (
          <DocumentTable
            documents={filteredDocuments}
            onDelete={setDeleteTarget}
            onReindex={handleReindex}
            reindexingId={reindexingId}
          />
        )}
      </section>

      {deleteTarget && (
        <DeleteDocumentModal
          doc={deleteTarget}
          busy={deleting}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={handleDeleteConfirmed}
        />
      )}

      {toast && <Toast type={toast.type} message={toast.message} onDismiss={() => setToast(null)} />}
    </div>
  );
}

export default AdminPage;
