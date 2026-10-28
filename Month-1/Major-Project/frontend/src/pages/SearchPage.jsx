import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { scrapingApi } from '../services/api';
import { useToast } from '../hooks/useToast.jsx';
import SearchForm from '../components/SearchForm';
import './Search.css';

const STEPS = [
  { icon: '🔍', label: 'Search product' },
  { icon: '🌐', label: 'Open source' },
  { icon: '📥', label: 'Collect reviews' },
  { icon: '🧹', label: 'Clean data' },
  { icon: '🧠', label: 'Analyze sentiment' },
  { icon: '💾', label: 'Save results' },
];

export default function SearchPage() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [sources, setSources] = useState([]);
  const [loadingSources, setLoadingSources] = useState(true);
  const [searching, setSearching] = useState(false);
  const [currentStep, setCurrentStep] = useState(-1);

  useEffect(() => {
    loadSources();
  }, []);

  const loadSources = async () => {
    try {
      const response = await scrapingApi.getSources();
      setSources(response.data.data.sources || ['amazon', 'flipkart']);
    } catch {
      setSources(['amazon', 'flipkart']);
    } finally {
      setLoadingSources(false);
    }
  };

  const handleSearch = async (formData) => {
    setSearching(true);
    setCurrentStep(0);

    // Simulate step progression for UX feedback during API call
    const stepInterval = setInterval(() => {
      setCurrentStep((prev) => {
        if (prev < STEPS.length - 2) return prev + 1;
        clearInterval(stepInterval);
        return prev;
      });
    }, 2500);

    let succeeded = false;
    try {
      const response = await scrapingApi.scrape(formData);
      clearInterval(stepInterval);
      setCurrentStep(STEPS.length - 1);

      if (response.data.success) {
        succeeded = true;
        const payload = response.data.data || {};
        if (payload.reviews_processed === 0) {
          addToast('Product found, but no reviews were collected. Showing product page.', 'error');
        } else if (payload.is_demo) {
          addToast('Live scrape blocked — analysis completed on demo reviews 🎉', 'success');
        } else {
          addToast('Analysis complete! 🎉', 'success');
        }
        setTimeout(() => {
          navigate(`/product/${payload.product_id}`);
          setSearching(false);
        }, 1200);
      } else {
        addToast(response.data.error || 'Search failed', 'error');
        setCurrentStep(-1);
        setSearching(false);
      }
    } catch (error) {
      clearInterval(stepInterval);
      const msg = error?.data?.message || error.message || 'Search failed. Please try again.';
      addToast(msg, 'error');
      setCurrentStep(-1);
      setSearching(false);
    } finally {
      if (!succeeded) setSearching(false);
    }
  };

  return (
    <div className="search-page">
      <header className="page-header">
        <h1>Analyze Product</h1>
        <p>Search for any product to scrape and analyze customer reviews with AI sentiment analysis</p>
      </header>

      <div className="search-container">
        {loadingSources ? (
          <div className="card">
            <div className="card-body" style={{ textAlign: 'center', padding: '3rem' }}>
              <span className="loading-spinner" />
              <p style={{ marginTop: '1rem', color: 'var(--text-muted)' }}>Loading sources...</p>
            </div>
          </div>
        ) : (
          <SearchForm onSearch={handleSearch} loading={searching} sources={sources} />
        )}

        {searching && currentStep >= 0 && (
          <div className="progress-card card">
            <div className="card-header">
              <h3>Analyzing...</h3>
              <span className="loading-spinner" />
            </div>
            <div className="card-body">
              <div className="progress-steps">
                {STEPS.map((step, index) => (
                  <div
                    key={index}
                    className={`step ${
                      index < currentStep ? 'done' : index === currentStep ? 'active' : ''
                    }`}
                  >
                    <span className="step-icon">{step.icon}</span>
                    <span className="step-label">{step.label}</span>
                    {index < currentStep && <span className="step-check">✓</span>}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        <div className="features-section">
          <h3 className="features-title">Supported Sources</h3>
          <div className="feature-cards">
            <div className="feature-card card">
              <span className="feature-icon">🛒</span>
              <h4>Amazon</h4>
              <p>Scrape and analyze reviews from Amazon product pages with full sentiment scoring</p>
            </div>
            <div className="feature-card card">
              <span className="feature-icon">🛍️</span>
              <h4>Flipkart</h4>
              <p>Scrape and analyze reviews from Flipkart product pages with full sentiment scoring</p>
            </div>
          </div>

          <div className="how-it-works">
            <h3 className="features-title">How it works</h3>
            <div className="steps-row">
              {[
                { n: '1', t: 'Search', d: 'Enter a product name and select a source' },
                { n: '2', t: 'Scrape', d: 'We automatically find and collect reviews' },
                { n: '3', t: 'Analyze', d: 'AI classifies sentiment for each review' },
                { n: '4', t: 'Insights', d: 'View charts, trends, and keywords' },
              ].map((s) => (
                <div className="how-step card" key={s.n}>
                  <div className="how-step-num">{s.n}</div>
                  <h4>{s.t}</h4>
                  <p>{s.d}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}