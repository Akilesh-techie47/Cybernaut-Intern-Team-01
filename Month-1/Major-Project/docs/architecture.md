# Architecture Documentation

## System Overview

The Product Sentiment Analyzer is a three-tier application:

1. **Frontend** - React SPA served by Vite
2. **Backend** - Flask REST API
3. **Database** - MongoDB document store

## Data Flow

```
User Action → Frontend → API → Backend Service → Database
                    ↓
              Scraper (async) → NLP → Database
                    ↓
              Frontend ← API ← Aggregated Data
```

## Components

### Frontend (React + Vite)

- **Pages**: Dashboard, Search, ProductDetail, History
- **Components**: Reusable UI (StatCard, ReviewTable, Charts, Forms)
- **Charts**: Recharts (Pie, Line, Bar)
- **State**: React hooks, context for toasts
- **Routing**: React Router v6

### Backend (Flask)

```
app/
├── config/          # Settings management
├── database/        # MongoDB connection & repositories
├── models/          # Data classes (Product, Review, Analysis)
├── routes/          # API endpoints (health, products, scraping, stats)
├── scrapers/        # Base + Amazon + Flipkart scrapers
├── sentiment/       # VADER sentiment service
├── services/        # Business logic (ScrapingService)
└── utils/           # Responses, logging, keywords
```

### Database (MongoDB)

Collections:
- **products**: Product metadata
- **reviews**: Individual reviews with sentiment
- **analyses**: Aggregated sentiment statistics

Indexes:
- products: (source, name), created_at
- reviews: product_id, sentiment, review_date, unique fingerprint
- analyses: product_id (unique)

### Scrapers

Abstract base class with implementations for:
- **AmazonScraper**: Uses CSS selectors for review elements
- **FlipkartScraper**: Uses CSS selectors for review elements

Both use Selenium with headless Chrome.

### NLP Pipeline

1. **Text Cleaning**: HTML removal, URL removal, whitespace normalization
2. **Sentiment Analysis**: VADER polarity scores
3. **Classification**: Configurable thresholds
4. **Aggregation**: Counts, percentages, trends

## Security

- Environment variables for secrets
- CORS restricted to frontend origin
- Input validation on all endpoints
- No sensitive data in logs

## Scalability Considerations

- Scraping runs synchronously (could be moved to job queue)
- Database indexes on query fields
- Pagination for large datasets
- Connection pooling via PyMongo