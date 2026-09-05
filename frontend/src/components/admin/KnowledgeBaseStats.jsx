function StatCard({ label, value }) {
  return (
    <div className="stat-card">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

function KnowledgeBaseStats({ stats }) {
  return (
    <div className="kb-stats-row">
      <StatCard label="Total Documents" value={stats.total_documents ?? 0} />
      <StatCard label="Total Chunks" value={stats.total_chunks ?? 0} />
      <StatCard label="Categories" value={stats.categories ?? 0} />
    </div>
  );
}

export default KnowledgeBaseStats;
