# Product Sentiment Analyzer & Review Dashboard

A full-stack web application for scraping product reviews from e-commerce websites, analyzing sentiment using NLP, and visualizing results through an interactive dashboard.

## Features

- **Product Search**: Search for products on Amazon and Flipkart
- **Review Scraping**: Automated scraping of product reviews using Selenium
- **Sentiment Analysis**: VADER-based sentiment classification (Positive/Neutral/Negative)
- **Data Storage**: MongoDB for persistent storage of products, reviews, and analyses
- **Interactive Dashboard**: Real-time charts and visualizations using Recharts
- **Review Explorer**: Filter and paginate through individual reviews
- **Historical Tracking**: Track sentiment trends over time
- **Keyword Extraction**: Identify frequently praised and criticized terms
- **Responsive UI**: Works on desktop, tablet, and mobile

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Frontend   │────▶│  Backend    │────▶│  Database   │
│  (React)    │     │  (Flask)    │     │  (MongoDB)  │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │  Scrapers   │
                    │ (Selenium)  │
                    └─────────────┘
                           │
                    ┌──────┴──────┐
                    │   NLP       │
                    │  (VADER)    │
                    └─────────────┘
```

## Technology Stack

### Frontend
- React 18 + Vite
- React Router v6
- Axios for API calls
- Recharts for visualizations
- date-fns for date formatting

### Backend
- Flask 3.0
- PyMongo for MongoDB
- Selenium + ChromeDriver for scraping
- BeautifulSoup4 for HTML parsing
- VADER Sentiment for NLP
- pandas/numpy for data processing

### Database
- MongoDB (local or Atlas)

## Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB 6+
- Google Chrome (for Selenium)

## Installation

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Install ChromeDriver (matches your Chrome version)
# Or use webdriver-manager (included in requirements)
```

Create `.env` file:
```env
MONGODB_URI=mongodb://localhost:27017
DATABASE_NAME=sentiment_analyzer
FLASK_ENV=development
FRONTEND_URL=http://localhost:5173
SECRET_KEY=your-secret-key
PORT=5000
```

### Frontend

```bash
cd frontend
npm install
```

### Database

Start MongoDB locally:
```bash
mongod
```

Or use MongoDB Atlas and update `MONGODB_URI` in `.env`.

## Running Locally

### Development Mode

Terminal 1 - Backend:
```bash
cd backend
source venv/bin/activate
python run.py
```

Terminal 2 - Frontend:
```bash
cd frontend
npm run dev
```

Open http://localhost:5173

### Docker

```bash
docker-compose up --build
```

Open http://localhost:5173

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/scrape` | Scrape and analyze product |
| GET | `/api/scrape/sources` | Get supported sources |
| GET | `/api/products` | List all products |
| GET | `/api/products/:id` | Get product details |
| GET | `/api/products/:id/reviews` | Get product reviews |
| GET | `/api/products/:id/sentiment` | Get sentiment analysis |
| GET | `/api/products/:id/trends` | Get sentiment trends |
| GET | `/api/products/:id/keywords` | Get top keywords |
| DELETE | `/api/products/:id` | Delete product |
| GET | `/api/stats` | Global dashboard stats |

## Scraping

Supported sources:
- **Amazon** (amazon.com)
- **Flipkart** (flipkart.com)

The scraper uses Selenium with headless Chrome. It respects rate limits and implements:
- Random delays between requests
- Retry handling
- Timeout handling
- Duplicate detection
- Graceful error handling

## Sentiment Analysis

Uses VADER (Valence Aware Dictionary and sEntiment Reasoner) optimized for social media text.

Thresholds (configurable in `backend/app/config/settings.py`):
- Positive: compound ≥ 0.05
- Neutral: -0.05 < compound < 0.05
- Negative: compound ≤ -0.05

## Project Structure

```
product-sentiment-analyzer/
├── backend/
│   ├── app/
│   │   ├── config/          # Configuration
│   │   ├── database/        # MongoDB connection & repositories
│   │   ├── models/          # Data models
│   │   ├── routes/          # API routes
│   │   ├── scrapers/        # Scraper implementations
│   │   ├── sentiment/       # NLP sentiment service
│   │   ├── services/        # Business logic
│   │   └── utils/           # Utilities
│   ├── tests/               # Backend tests
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── components/      # Reusable UI components
│   │   ├── charts/          # Recharts components
│   │   ├── hooks/           # Custom React hooks
│   │   ├── layouts/         # Page layouts
│   │   ├── pages/           # Page components
│   │   ├── services/        # API services
│   │   ├── utils/           # Utilities
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── docker-compose.yml
├── .gitignore
└── README.md
```

## Deployment

### Backend (Render)
1. Create a new Web Service on Render
2. Connect your repository
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn run:app`
5. Add environment variables

### Frontend (Vercel/Netlify)
1. Connect your repository
2. Build command: `npm run build`
3. Output directory: `dist`
4. Add environment variables

### Database (MongoDB Atlas)
1. Create a cluster on MongoDB Atlas
2. Get connection string
3. Add to `MONGODB_URI` environment variable

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `MONGODB_URI` | MongoDB connection string | Yes |
| `DATABASE_NAME` | Database name | No (default: sentiment_analyzer) |
| `FLASK_ENV` | Flask environment | No (default: development) |
| `FRONTEND_URL` | Frontend URL for CORS | Yes |
| `SECRET_KEY` | Flask secret key | Yes |
| `PORT` | Backend port | No (default: 5000) |

## Testing

### Backend
```bash
cd backend
pytest tests/ -v
```

### Frontend
```bash
cd frontend
npm run lint
npm run build
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- VADER Sentiment Analysis
- Recharts for visualizations
- Selenium for web scraping