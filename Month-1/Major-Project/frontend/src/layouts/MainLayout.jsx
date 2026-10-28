import { Link, useLocation } from 'react-router-dom';
import { useState } from 'react';
import './MainLayout.css';

export default function MainLayout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Dashboard', icon: '📊' },
    { path: '/search', label: 'Search Products', icon: '🔍' },
    { path: '/history', label: 'Analysis History', icon: '📜' },
  ];

  return (
    <div className="layout">
      <header className="header">
        <button
          className="hamburger"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          aria-label="Toggle menu"
          id="sidebar-toggle"
        >
          {sidebarOpen ? '✕' : '☰'}
        </button>
        <h1 className="logo">
          <Link to="/">
            <span className="logo-icon">⚡</span>
            <span>SentimentAI</span>
          </Link>
        </h1>
        <div className="header-actions">
          <Link to="/search" className="btn btn-primary header-cta" id="header-analyze-btn">
            + Analyze Product
          </Link>
        </div>
      </header>

      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`} id="main-sidebar">
        <div className="sidebar-brand">
          <span className="sidebar-brand-icon">⚡</span>
          <span>SentimentAI</span>
        </div>
        <nav className="nav">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
              onClick={() => setSidebarOpen(false)}
              id={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="sidebar-status">
            <span className="status-dot" />
            <span>API Connected</span>
          </div>
        </div>
      </aside>

      {sidebarOpen && (
        <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />
      )}

      <main className="main" id="main-content">
        {children}
      </main>
    </div>
  );
}