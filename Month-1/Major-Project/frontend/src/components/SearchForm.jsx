import { useState } from 'react';

export default function SearchForm({ onSearch, loading = false, sources = [] }) {
  const [formData, setFormData] = useState({
    query: '',
    source: sources[0] || 'amazon',
    limit: 50,
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.query.trim()) return;
    onSearch(formData);
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: name === 'limit' ? parseInt(value) || 50 : value }));
  };

  return (
    <form className="search-form card" onSubmit={handleSubmit}>
      <div className="card-header">
        <h2>Search Product Reviews</h2>
      </div>
      <div className="card-body">
        <div className="form-group">
          <label className="form-label" htmlFor="query">Product Name</label>
          <input
            type="text"
            id="query"
            name="query"
            className="form-input"
            placeholder="e.g., Samsung Galaxy S24, iPhone 15, MacBook Pro"
            value={formData.query}
            onChange={handleChange}
            required
            disabled={loading}
          />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label className="form-label" htmlFor="source">Source</label>
            <select
              id="source"
              name="source"
              className="form-select"
              value={formData.source}
              onChange={handleChange}
              disabled={loading}
            >
              {sources.map((s) => (
                <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="limit">Max Reviews</label>
            <input
              type="number"
              id="limit"
              name="limit"
              className="form-input"
              min="1"
              max="200"
              value={formData.limit}
              onChange={handleChange}
              disabled={loading}
            />
          </div>
        </div>

        <button type="submit" className="btn btn-primary" disabled={loading || !formData.query.trim()} style={{ width: '100%' }}>
          {loading ? (
            <>
              <span className="loading-spinner" />
              Searching & Analyzing...
            </>
          ) : (
            'Start Analysis'
          )}
        </button>

        <p className="form-hint">
          This will search for the product, scrape reviews, analyze sentiment, and display results.
        </p>
      </div>
    </form>
  );
}