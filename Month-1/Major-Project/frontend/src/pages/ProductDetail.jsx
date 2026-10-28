import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { format } from 'date-fns';
import { productsApi } from '../services/api';
import { useToast } from '../hooks/useToast.jsx';
import SentimentDistributionChart from '../charts/SentimentDistributionChart';
import SentimentTrendChart from '../charts/SentimentTrendChart';
import RatingDistributionChart from '../charts/RatingDistributionChart';
import KeywordsChart from '../charts/KeywordsChart';
import ReviewTable from '../components/ReviewTable';
import ReviewFilters from '../components/ReviewFilters';
import './ProductDetail.css';

export default function ProductDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { addToast } = useToast();

  const [product, setProduct] = useState(null);
  const [sentiment, setSentiment] = useState(null);
  const [trends, setTrends] = useState([]);
  const [keywords, setKeywords] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reviewsLoading, setReviewsLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [filters, setFilters] = useState({ sentiment: '', rating: '' });
  const [pagination, setPagination] = useState({ page: 1, limit: 20, total: 0 });

  useEffect(() => {
    loadProductData();
  }, [id]);

  useEffect(() => {
    if (!loading && product) {
      loadReviews();
    }
  }, [id, filters, pagination.page, product]);

  const loadProductData = async () => {
    try {
      setLoading(true);
      setNotFound(false);

      const [productRes, sentimentRes, trendsRes, keywordsRes] = await Promise.allSettled([
        productsApi.getById(id),
        productsApi.getSentiment(id),
        productsApi.getTrends(id),
        productsApi.getKeywords(id),
      ]);

      if (productRes.status === 'rejected') {
        const status = productRes.reason?.status;
        if (status === 404 || status === 400 || status === 422) {
          setNotFound(true);
        } else {
          addToast(productRes.reason?.message || 'Failed to load product', 'error');
        }
        return;
      }

      setProduct(productRes.value.data.data);

      if (sentimentRes.status === 'fulfilled') {
        setSentiment(sentimentRes.value.data.data);
        setKeywords(sentimentRes.value.data.data?.top_keywords || []);
      }

      if (trendsRes.status === 'fulfilled') {
        setTrends(trendsRes.value.data.data?.trends || []);
      }

      if (keywordsRes.status === 'fulfilled') {
        setKeywords(keywordsRes.value.data.data?.top_keywords || keywords);
      }

    } catch (error) {
      addToast(error.message || 'Failed to load product', 'error');
    } finally {
      setLoading(false);
    }
  };

  const loadReviews = async () => {
    try {
      setReviewsLoading(true);
      const params = {
        limit: pagination.limit,
        skip: (pagination.page - 1) * pagination.limit,
        ...(filters.sentiment ? { sentiment: filters.sentiment } : {}),
      };
      const response = await productsApi.getReviews(id, params);
      setReviews(response.data.data.reviews || []);
      setPagination((prev) => ({ ...prev, total: response.data.data.total || 0 }));
    } catch (error) {
      addToast(error.message || 'Failed to load reviews', 'error');
    } finally {
      setReviewsLoading(false);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPagination((prev) => ({ ...prev, page: 1 }));
  };

  const handleClearFilters = () => {
    setFilters({ sentiment: '', rating: '' });
    setPagination((prev) => ({ ...prev, page: 1 }));
  };

  const handlePageChange = (newPage) => {
    setPagination((prev) => ({ ...prev, page: newPage }));
  };

  if (loading) {
    return (
      <div className="product-detail">
        <div className="skeleton" style={{ height: '200px', borderRadius: 'var(--radius-lg)', marginBottom: '2rem' }} />
        <div className="stat-cards-row">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="skeleton card" style={{ height: '120px' }} />
          ))}
        </div>
        <div className="charts-grid">
          <div className="skeleton card" style={{ height: '380px' }} />
          <div className="skeleton card" style={{ height: '380px' }} />
        </div>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="product-detail">
        <div className="empty-state card">
          <div className="empty-icon">🔍</div>
          <h2>Product Not Found</h2>
          <p>The product you're looking for doesn't exist or the ID is invalid.</p>
          <Link to="/history" className="btn btn-primary">Browse All Products</Link>
        </div>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="product-detail">
        <div className="empty-state card">
          <div className="empty-icon">⚠️</div>
          <h2>Unable to Load Product</h2>
          <p>Something went wrong. Please try again.</p>
          <button className="btn btn-primary" onClick={loadProductData}>Retry</button>
        </div>
      </div>
    );
  }

  const sentimentLabel = (() => {
    const pos = sentiment?.positive_percentage || 0;
    const neg = sentiment?.negative_percentage || 0;
    if (pos > neg) return 'positive';
    if (neg > pos) return 'negative';
    return 'neutral';
  })();

  const sentimentStyles = {
    positive: { bg: 'linear-gradient(135deg, #059669, #10b981)', shadow: 'rgba(16,185,129,0.4)' },
    neutral:  { bg: 'linear-gradient(135deg, #d97706, #f59e0b)', shadow: 'rgba(245,158,11,0.4)' },
    negative: { bg: 'linear-gradient(135deg, #dc2626, #ef4444)', shadow: 'rgba(239,68,68,0.4)' },
  };
  const ss = sentimentStyles[sentimentLabel];

  return (
    <div className="product-detail">
      <header className="product-page-header">
        <div className="product-page-header-left">
          <button className="back-btn" onClick={() => navigate(-1)} id="back-btn">
            ← Back
          </button>
          <h1>{product.name}</h1>
          <div className="product-meta-row">
            <span className="source-badge">{product.source}</span>
            <span className="meta-sep">•</span>
            <span>{product.review_count ?? 0} reviews</span>
            <span className="meta-sep">•</span>
            <span>
              {product.created_at
                ? `Analyzed ${format(new Date(product.created_at), 'MMM d, yyyy')}`
                : 'Recently analyzed'}
            </span>
          </div>
        </div>
        <div className="product-page-header-right">
          <span
            className="overall-sentiment-badge"
            style={{ background: ss.bg, boxShadow: `0 6px 20px ${ss.shadow}` }}
          >
            {sentimentLabel.charAt(0).toUpperCase() + sentimentLabel.slice(1)}
          </span>
        </div>
      </header>

      {sentiment && (
        <div className="stat-cards-row">
          <div className="pstat-card card">
            <div className="pstat-value" style={{ color: '#34d399' }}>
              {(sentiment.positive_percentage || 0).toFixed(1)}%
            </div>
            <div className="pstat-label">Positive</div>
            <div className="pstat-detail">{sentiment.positive_count || 0} reviews</div>
          </div>
          <div className="pstat-card card">
            <div className="pstat-value" style={{ color: '#fbbf24' }}>
              {(sentiment.neutral_percentage || 0).toFixed(1)}%
            </div>
            <div className="pstat-label">Neutral</div>
            <div className="pstat-detail">{sentiment.neutral_count || 0} reviews</div>
          </div>
          <div className="pstat-card card">
            <div className="pstat-value" style={{ color: '#f87171' }}>
              {(sentiment.negative_percentage || 0).toFixed(1)}%
            </div>
            <div className="pstat-label">Negative</div>
            <div className="pstat-detail">{sentiment.negative_count || 0} reviews</div>
          </div>
          <div className="pstat-card card">
            <div className="pstat-value" style={{ color: '#818cf8' }}>
              {(sentiment.average_rating || 0).toFixed(1)}
            </div>
            <div className="pstat-label">Avg Rating</div>
            <div className="pstat-detail">Out of 5.0</div>
          </div>
        </div>
      )}

      <div className="charts-grid">
        <div className="chart-card card">
          <div className="card-header"><h3>Sentiment Distribution</h3></div>
          <div className="card-body">
            <SentimentDistributionChart data={sentiment} />
          </div>
        </div>
        <div className="chart-card card">
          <div className="card-header"><h3>Rating Distribution</h3></div>
          <div className="card-body">
            <RatingDistributionChart data={sentiment?.rating_distribution} />
          </div>
        </div>
      </div>

      <div className="charts-grid">
        <div className="chart-card card">
          <div className="card-header"><h3>Sentiment Trends</h3></div>
          <div className="card-body">
            <SentimentTrendChart data={trends} />
          </div>
        </div>
        <div className="chart-card card">
          <div className="card-header"><h3>Top Keywords</h3></div>
          <div className="card-body">
            <KeywordsChart keywords={keywords} />
          </div>
        </div>
      </div>

      <section className="reviews-section">
        <div className="section-header">
          <h2>Reviews ({pagination.total})</h2>
        </div>

        <ReviewFilters
          filters={filters}
          onChange={handleFilterChange}
          onClear={handleClearFilters}
        />

        <ReviewTable reviews={reviews} loading={reviewsLoading} />

        {pagination.total > pagination.limit && (
          <div className="pagination">
            <button
              className="btn btn-secondary"
              onClick={() => handlePageChange(pagination.page - 1)}
              disabled={pagination.page === 1}
              id="prev-page-btn"
            >
              ← Previous
            </button>
            <span className="page-info">
              Page {pagination.page} of {Math.ceil(pagination.total / pagination.limit)}
            </span>
            <button
              className="btn btn-secondary"
              onClick={() => handlePageChange(pagination.page + 1)}
              disabled={pagination.page >= Math.ceil(pagination.total / pagination.limit)}
              id="next-page-btn"
            >
              Next →
            </button>
          </div>
        )}
      </section>
    </div>
  );
}