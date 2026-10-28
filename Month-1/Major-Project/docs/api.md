# API Documentation

Base URL: `http://localhost:5000/api`

## Health Check

### GET /health

Check service health and database connectivity.

**Response 200:**
```json
{
  "success": true,
  "message": "Service healthy",
  "database": "connected"
}
```

**Response 503:**
```json
{
  "success": false,
  "message": "Service unhealthy",
  "database": "disconnected",
  "error": "connection error"
}
```

## Scraping

### POST /scrape

Search for a product, scrape reviews, analyze sentiment, and store results.

**Request:**
```json
{
  "query": "Samsung Galaxy S24",
  "source": "amazon",
  "limit": 50
}
```

**Parameters:**
- `query` (string, required): Product search query
- `source` (string, required): `amazon` or `flipkart`
- `limit` (integer, optional): Max reviews to scrape (1-200, default: 50)

**Response 200:**
```json
{
  "success": true,
  "message": "Scraping completed",
  "data": {
    "product_id": "507f1f77bcf86cd799439011",
    "product_name": "Samsung Galaxy S24",
    "reviews_processed": 45,
    "total_reviews": 45
  }
}
```

**Response 400/500:**
```json
{
  "success": false,
  "message": "Product not found",
  "error_code": "SCRAPER_ERROR"
}
```

### GET /scrape/sources

Get list of supported scraping sources.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "sources": ["amazon", "flipkart"]
  }
}
```

## Products

### GET /products

List all analyzed products with pagination.

**Query Parameters:**
- `limit` (integer, default: 50, max: 100)
- `skip` (integer, default: 0)

**Response 200:**
```json
{
  "success": true,
  "data": {
    "products": [...],
    "total": 100,
    "limit": 50,
    "skip": 0
  }
}
```

### GET /products/:id

Get product details by ID.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "_id": "507f1f77bcf86cd799439011",
    "name": "Samsung Galaxy S24",
    "source": "amazon",
    "url": "https://amazon.com/...",
    "rating": 4.3,
    "review_count": 150,
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
}
```

### GET /products/:id/reviews

Get reviews for a product with filtering and pagination.

**Query Parameters:**
- `limit` (integer, default: 50, max: 100)
- `skip` (integer, default: 0)
- `sentiment` (string, optional): `positive`, `neutral`, or `negative`

**Response 200:**
```json
{
  "success": true,
  "data": {
    "reviews": [...],
    "total": 150,
    "limit": 50,
    "skip": 0
  }
}
```

### GET /products/:id/sentiment

Get sentiment analysis summary for a product.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "_id": "507f1f77bcf86cd799439012",
    "product_id": "507f1f77bcf86cd799439011",
    "positive_count": 105,
    "neutral_count": 25,
    "negative_count": 20,
    "positive_percentage": 70.0,
    "neutral_percentage": 16.7,
    "negative_percentage": 13.3,
    "average_rating": 4.3,
    "top_keywords": ["battery", "camera", "display", "performance", "fast"],
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

### GET /products/:id/trends

Get sentiment trends over time.

**Query Parameters:**
- `days` (integer, default: 30, max: 365)

**Response 200:**
```json
{
  "success": true,
  "data": {
    "trends": [
      {
        "date": "2024-01-01",
        "positive": 10,
        "neutral": 3,
        "negative": 2,
        "positive_pct": 66.7,
        "neutral_pct": 20.0,
        "negative_pct": 13.3
      }
    ]
  }
}
```

### GET /products/:id/keywords

Get top keywords for a product.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "top_keywords": ["battery", "camera", "display", "performance", "fast"]
  }
}
```

### DELETE /products/:id

Delete a product and all associated reviews/analysis.

**Response 200:**
```json
{
  "success": true,
  "message": "Product deleted"
}
```

## Statistics

### GET /stats

Get global dashboard statistics.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "total_products": 25,
    "total_reviews": 3500,
    "sentiment_distribution": {
      "positive": 2100,
      "neutral": 800,
      "negative": 600
    },
    "sentiment_percentages": {
      "positive": 60.0,
      "neutral": 22.9,
      "negative": 17.1
    },
    "recent_products": [...]
  }
}
```

## Error Responses

All endpoints return consistent error format:

```json
{
  "success": false,
  "message": "Human-readable error message",
  "error_code": "ERROR_CODE",
  "details": {}
}
```

Common error codes:
- `VALIDATION_ERROR` (422): Request validation failed
- `NOT_FOUND` (404): Resource not found
- `INVALID_ID` (400): Invalid ObjectId format
- `SCRAPER_ERROR` (500): Scraping failed
- `INTERNAL_ERROR` (500): Unexpected server error