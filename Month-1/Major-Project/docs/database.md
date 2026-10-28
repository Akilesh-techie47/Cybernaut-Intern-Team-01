# Database Documentation

## Collections

### products

Stores product metadata.

```javascript
{
  "_id": ObjectId,
  "name": "Samsung Galaxy S24",
  "source": "amazon",
  "url": "https://amazon.com/dp/...",
  "rating": 4.3,
  "review_count": 150,
  "created_at": ISODate("2024-01-15T10:30:00Z"),
  "updated_at": ISODate("2024-01-15T10:30:00Z")
}
```

**Indexes:**
- `{ source: 1, name: 1 }` - Unique product lookup
- `{ created_at: -1 }` - Recent products sorting

### reviews

Stores individual reviews with sentiment analysis.

```javascript
{
  "_id": ObjectId,
  "product_id": ObjectId,
  "source": "amazon",
  "review_text": "Great phone! Battery lasts all day.",
  "cleaned_text": "Great phone Battery lasts all day",
  "rating": 5,
  "review_date": ISODate("2024-01-10T00:00:00Z"),
  "reviewer": "John D.",
  "sentiment": "positive",
  "sentiment_score": 0.85,
  "created_at": ISODate("2024-01-15T10:30:00Z")
}
```

**Indexes:**
- `{ product_id: 1 }` - Product reviews
- `{ sentiment: 1 }` - Sentiment filtering
- `{ review_date: -1 }` - Chronological sorting
- `{ product_id: 1, source: 1, review_text: 1, review_date: 1 }` - Unique fingerprint (unique)

**Duplicate Prevention:**
The unique compound index on `(product_id, source, review_text, review_date)` prevents duplicate reviews from being inserted.

### analyses

Stores aggregated sentiment statistics per product.

```javascript
{
  "_id": ObjectId,
  "product_id": ObjectId,
  "positive_count": 105,
  "neutral_count": 25,
  "negative_count": 20,
  "positive_percentage": 70.0,
  "neutral_percentage": 16.7,
  "negative_percentage": 13.3,
  "average_rating": 4.3,
  "top_keywords": ["battery", "camera", "display", "performance", "fast"],
  "created_at": ISODate("2024-01-15T10:30:00Z")
}
```

**Indexes:**
- `{ product_id: 1 }` - Unique (one analysis per product)
- `{ created_at: -1 }` - Sorting

## Relationships

```
products (1) ───< (N) reviews
products (1) ───< (1) analyses
```

## Example Queries

### Get product with reviews and analysis
```javascript
// Product
db.products.findOne({ _id: ObjectId("...") })

// Reviews with pagination
db.reviews.find({ product_id: ObjectId("...") })
  .sort({ review_date: -1 })
  .skip(0).limit(50)

// Analysis
db.analyses.findOne({ product_id: ObjectId("...") })
```

### Sentiment distribution for a product
```javascript
db.reviews.aggregate([
  { $match: { product_id: ObjectId("...") } },
  { $group: { _id: "$sentiment", count: { $sum: 1 } } }
])
```

### Rating distribution
```javascript
db.reviews.aggregate([
  { $match: { product_id: ObjectId("...") } },
  { $group: { _id: "$rating", count: { $sum: 1 } } }
])
```

### Sentiment trends (last 30 days)
```javascript
const startDate = new Date();
startDate.setDate(startDate.getDate() - 30);

db.reviews.aggregate([
  { $match: { product_id: ObjectId("..."), review_date: { $gte: startDate } } },
  {
    $group: {
      _id: {
        date: { $dateToString: { format: "%Y-%m-%d", date: "$review_date" } },
        sentiment: "$sentiment"
      },
      count: { $sum: 1 }
    }
  },
  { $sort: { "_id.date": 1 } }
])
```

### Global statistics
```javascript
// Total products
db.products.countDocuments({})

// Total reviews
db.reviews.countDocuments({})

// Sentiment distribution
db.reviews.aggregate([
  { $group: { _id: "$sentiment", count: { $sum: 1 } } }
])
```

## Data Retention

No automatic data retention policy. Manual cleanup via DELETE endpoints.

## Backup Strategy

Use MongoDB Atlas automated backups or `mongodump` for self-hosted.