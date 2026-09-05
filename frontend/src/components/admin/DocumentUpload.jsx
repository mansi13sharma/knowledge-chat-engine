import { useState } from "react";
import { MAX_UPLOAD_MB, uploadDocument } from "../../services/knowledgeBaseApi";
import { formatBytes } from "../../utils/format";

function DocumentUpload({ categories, onUploaded, onError }) {
  const [category, setCategory] = useState("");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);

  const canSubmit = !busy && !!file && category.trim().length > 0;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSubmit) return;

    setBusy(true);
    try {
      const result = await uploadDocument(file, category.trim());
      onUploaded(result.document);
      setFile(null);
      e.target.reset();
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="kb-card">
      <h2>Upload Document</h2>
      <form className="upload-form" onSubmit={handleSubmit}>
        <label className="upload-field">
          <span>Category</span>
          <input
            list="kb-category-options"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="e.g. nodejs"
            disabled={busy}
            required
          />
          <datalist id="kb-category-options">
            {categories.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </label>

        <label className="upload-field">
          <span>Document</span>
          <input
            type="file"
            accept=".pdf,.docx,.txt,.md"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            disabled={busy}
            required
          />
        </label>

        {file && (
          <div className="file-preview">
            <span className="file-preview-name">{file.name}</span>
            <span className="file-preview-meta">{formatBytes(file.size)}</span>
            <span className="file-preview-meta">{category.trim() || "no category yet"}</span>
          </div>
        )}

        <p className="upload-hint">
          Supported: PDF, DOCX, TXT, MD · Maximum size: {MAX_UPLOAD_MB} MB
        </p>

        <button type="submit" disabled={!canSubmit}>
          {busy ? "Uploading & indexing…" : "Upload & Index"}
        </button>
      </form>
    </section>
  );
}

export default DocumentUpload;
