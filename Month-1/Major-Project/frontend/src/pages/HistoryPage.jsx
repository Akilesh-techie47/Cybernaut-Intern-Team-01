import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { productsApi } from '../services/api';
import { useToast } from '../hooks/useToast.jsx';
import ProductCard from '../components/ProductCard';
import './History.css';

export default function HistoryPage() {
  const { addToast } = useToast();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({ page: 1, limit: 12, total: 0 });

  useEffect(() => {
    loadProducts();
  }, [pagination.page]);

  const loadProducts = async () => {
    try {
      setLoading(true);
      const response = await productsApi.getAll({
        limit: pagination.limit,
        skip: (pagination.page - 1) * pagination.limit,
      });
      setProducts(response.data.data.products || []);
      setPagination((prev) => ({ ...prev, total: response.data.data.total || 0 }));
    } catch (error) {
      addToast(error.message || 'Failed to load history', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handlePageChange = (newPage) => {
    setPagination((prev) => ({ ...prev, page: newPage }));
  };

  return (
    <div className="history-page">
      <header className="page-header">
        <div>
          <h1>Analysis History</h1>
          <p>All previously analyzed products</p>
        </div>
        <Link to="/search" className="btn btn-primary" id="history-analyze-btn">
          + New Analysis
        </Link>
      </header>

      {loading ? (
        <div className="products-grid">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="product-card card skeleton" style={{ height: '200px' }} />
          ))}
        </div>
      ) : products.length === 0 ? (
        <div className="empty-state card">
          <div className="empty-icon">📭</div>
          <h3>No Analyses Yet</h3>
          <p>Start by searching for a product to analyze its reviews.</p>
          <Link to="/search" className="btn btn-primary" id="empty-history-btn">
            Analyze Your First Product
          </Link>
        </div>
      ) : (
        <>
          <div className="products-grid">
            {products.map((product) => (
              <ProductCard key={product.id || product._id} product={product} />
            ))}
          </div>

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
        </>
      )}
    </div>
  );
}