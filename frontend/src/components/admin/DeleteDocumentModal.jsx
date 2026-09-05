function DeleteDocumentModal({ doc, busy, onCancel, onConfirm }) {
  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="delete-doc-title">
      <div className="modal-card">
        <h3 id="delete-doc-title">Delete "{doc.filename}"?</h3>
        <p>This will remove the file and all of its indexed knowledge chunks.</p>
        <div className="modal-actions">
          <button type="button" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button type="button" className="danger" onClick={onConfirm} disabled={busy}>
            {busy ? "Deleting…" : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default DeleteDocumentModal;
