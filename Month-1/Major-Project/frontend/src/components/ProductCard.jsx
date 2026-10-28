import { Link } from 'react-router-dom';
import { format } from 'date-fns';

export default function ProductCard({ product }) {
  // Products from the list API may not have sentiment percentages — gracefully handle
  const pos = product.positive_percentage ?? null;
  const neg = product.negative_percentage ?? null;

  const getOverall = () => {
    if (pos !== null && neg !== null) {
      if (pos > neg) return 'positive';
      if (neg > pos) return 'negative';
      return 'neutral';
    }
    // Fallback: derive from rating
    const r = product.rating ?? 0;
    if (r >= 4) return 'positive';
    if (r <= 2) return 'negative';
    return 'neutral';
  };

  const overall = getOverall();

  const BADGE_STYLES = {
    positive: { bg: 'rgba(16,185,129,0.15)', color: '#34d399', border: 'rgba(16,185,129,0.3)' },
    neutral:  { bg: 'rgba(245,158,11,0.15)', color: '#fbbf24', border: 'rgba(245,158,11,0.3)' },
    negative: { bg: 'rgba(239,68,68,0.15)',  color: '#f87171', border: 'rgba(239,68,68,0.3)'  },
  };

  const bs = BADGE_STYLES[overall];

  return (
    <Link
      to={`/product/${product.id || product._id}`}
      className="product-card card"
      id={`product-card-${product.id || product._id}`}
    >
      <div className="product-header">
        <div>
          <h3 className="product-name">{product.name}</h3>
          <span className="product-source">{product.source}</span>
        </div>
        <span
          className="badge"
          style={{ background: bs.bg, color: bs.color, border: `1px solid ${bs.border}` }}
        >
          {overall}
        </span>
      </div>

      <div className="product-stats">
        <div className="stat">
          <span className="stat-value">{product.rating?.toFixed(1) ?? '—'}</span>
          <span className="stat-label">Avg Rating</span>
        </div>
        <div className="stat">
          <span className="stat-value">{product.review_count ?? 0}</span>
          <span className="stat-label">Reviews</span>
        </div>
        {pos !== null ? (
          <div className="stat">
            <span className="stat-value" style={{ color: '#34d399' }}>{pos.toFixed(0)}%</span>
            <span className="stat-label">Positive</span>
          </div>
        ) : (
          <div className="stat">
            <span className="stat-value" style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>
              {overall === 'positive' ? '✓' : overall === 'negative' ? '✗' : '~'}
            </span>
            <span className="stat-label">Sentiment</span>
          </div>
        )}
      </div>

      <div className="product-meta">
        <span>
          {product.created_at
            ? format(new Date(product.created_at), 'MMM d, yyyy')
            : 'Recently analyzed'}
        </span>
        <span className="view-link">View Details →</span>
      </div>
    </Link>
  );
}