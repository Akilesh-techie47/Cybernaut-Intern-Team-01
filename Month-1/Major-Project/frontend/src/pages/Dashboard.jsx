import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { statsApi } from '../services/api';
import { useToast } from '../hooks/useToast.jsx';
import StatCard from '../components/StatCard';
import SentimentDistributionChart from '../charts/SentimentDistributionChart';
import SentimentTrendChart from '../charts/SentimentTrendChart';
import RatingDistributionChart from '../charts/RatingDistributionChart';
import ProductCard from '../components/ProductCard';
import './Dashboard.css';

export default function Dashboard() {
  const { addToast } = useToast();
  const [stats, setStats] = useState(null);
  const [recentProducts, setRecentProducts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      setLoading(true);
      const response = await statsApi.getGlobal();
      const data = response.data.data;
      setStats(data);
      setRecentProducts(data.recent_products || []);
    } catch (error) {
      addToast(error.message || 'Failed to load dashboard', 'error');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="dashboard">
        <div className="dashboard-hero skeleton-hero">
          <div className="skeleton" style={{ height: '36px', width: '280px', marginBottom: '0.75rem' }} />
          <div className="skeleton" style={{ height: '20px', width: '200px' }} />
        </div>
        <div className="stats-grid">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="stat-card card skeleton" style={{ height: '130px' }} />
          ))}
        </div>
        <div className="charts-grid">
          <div className="chart-card card skeleton" style={{ height: '380px' }} />
          <div className="chart-card card skeleton" style={{ height: '380px' }} />
        </div>
        <div className="charts-grid">
          <div className="chart-card card skeleton" style={{ gridColumn: '1 / -1', height: '380px' }} />
        </div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="dashboard">
        <div className="empty-state card">
          <h2>Failed to load dashboard</h2>
          <p>Could not connect to the backend. Make sure the server is running.</p>
          <button className="btn btn-primary" onClick={loadStats}>Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <header className="dashboard-hero">
        <div>
          <h1>Welcome back 👋</h1>
          <p>Here's your sentiment analysis overview</p>
        </div>
        <Link to="/search" className="btn btn-primary" id="dashboard-analyze-btn">
          + Analyze Product
        </Link>
      </header>

      <div className="stats-grid">
        <StatCard
          title="Total Products"
          value={stats.total_products ?? 0}
          icon="📦"
          color="indigo"
        />
        <StatCard
          title="Total Reviews"
          value={(stats.total_reviews ?? 0).toLocaleString()}
          icon="💬"
          color="blue"
        />
        <StatCard
          title="Positive Sentiment"
          value={`${stats.sentiment_percentages?.positive ?? 0}%`}
          icon="👍"
          color="green"
        />
        <StatCard
          title="Negative Sentiment"
          value={`${stats.sentiment_percentages?.negative ?? 0}%`}
          icon="👎"
          color="red"
        />
      </div>

      <div className="charts-grid">
        <div className="chart-card card">
          <div className="card-header">
            <h3>Sentiment Distribution</h3>
          </div>
          <div className="card-body">
            <SentimentDistributionChart data={stats.sentiment_distribution} />
          </div>
        </div>

        <div className="chart-card card">
          <div className="card-header">
            <h3>Rating Distribution</h3>
          </div>
          <div className="card-body">
            <RatingDistributionChart data={stats.rating_distribution} />
          </div>
        </div>
      </div>

      <div className="charts-grid">
        <div className="chart-card card" style={{ gridColumn: '1 / -1' }}>
          <div className="card-header">
            <h3>Sentiment Trends (Last 30 Days)</h3>
          </div>
          <div className="card-body">
            <SentimentTrendChart data={stats.trends || []} />
          </div>
        </div>
      </div>

      <section className="recent-products">
        <div className="section-header">
          <h2>Recent Analyses</h2>
          <Link to="/history" className="view-all">View All →</Link>
        </div>
        {recentProducts.length === 0 ? (
          <div className="empty-state card">
            <div className="empty-icon">🔍</div>
            <h3>No products analyzed yet</h3>
            <p>Start by searching for a product to analyze its reviews and sentiment.</p>
            <Link to="/search" className="btn btn-primary" id="empty-analyze-btn">Analyze Your First Product</Link>
          </div>
        ) : (
          <div className="products-grid">
            {recentProducts.map((product) => (
              <ProductCard key={product.id || product._id} product={product} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}