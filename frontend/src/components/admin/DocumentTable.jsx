import { formatBytes, formatDate } from "../../utils/format";

const STATUS_LABEL = { indexed: "Indexed", processing: "Processing", failed: "Failed" };

function DocumentTable({ documents, onDelete, onReindex, reindexingId }) {
  return (
    <div className="kb-table-wrap">
      <table className="kb-table">
        <thead>
          <tr>
            <th>Document</th>
            <th>Category</th>
            <th>Chunks</th>
            <th>Status</th>
            <th>Updated</th>
            <th>Size</th>
            <th aria-label="Actions"></th>
          </tr>
        </thead>
        <tbody>
          {documents.map((doc) => {
            const isBusy = reindexingId === doc.id || doc.status === "processing";
            return (
              <tr key={doc.id}>
                <td>
                  <div className="doc-name">{doc.filename}</div>
                  {doc.status === "failed" && doc.error_message && (
                    <div className="doc-error">{doc.error_message}</div>
                  )}
                </td>
                <td>
                  <span className="category-badge">{doc.category}</span>
                </td>
                <td>{doc.chunks}</td>
                <td>
                  <span className={`status-badge status-${doc.status}`}>
                    {STATUS_LABEL[doc.status] || doc.status}
                  </span>
                </td>
                <td>{formatDate(doc.updated_at)}</td>
                <td>{formatBytes(doc.size)}</td>
                <td className="doc-actions">
                  <button type="button" onClick={() => onReindex(doc)} disabled={isBusy}>
                    {isBusy ? "Processing…" : "Re-index"}
                  </button>
                  <button type="button" className="danger" onClick={() => onDelete(doc)} disabled={isBusy}>
                    Delete
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default DocumentTable;
