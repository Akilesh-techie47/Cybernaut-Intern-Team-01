export default function ReviewFilters({ filters, onChange, onClear }) {
  return (
    <div className="filters card">
      <div className="card-header">
        <h3>Filters</h3>
        {Object.values(filters).some(v => v) && (
          <button className="btn btn-secondary" onClick={onClear} style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}>
            Clear All
          </button>
        )}
      </div>
      <div className="card-body">
        <div className="filter-row">
          <div className="form-group">
            <label className="form-label">Sentiment</label>
            <select className="form-select" value={filters.sentiment || ''} onChange={(e) => onChange('sentiment', e.target.value)}>
              <option value="">All</option>
              <option value="positive">Positive</option>
              <option value="neutral">Neutral</option>
              <option value="negative">Negative</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Rating</label>
            <select className="form-select" value={filters.rating || ''} onChange={(e) => onChange('rating', e.target.value)}>
              <option value="">All</option>
              <option value="5">5 Stars</option>
              <option value="4">4 Stars</option>
              <option value="3">3 Stars</option>
              <option value="2">2 Stars</option>
              <option value="1">1 Star</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );
}