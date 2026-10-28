from datetime import datetime, timedelta
from bson import ObjectId
from app.database.connection import get_db
from app.models.product import Product
from app.models.review import Review
from app.models.analysis import Analysis
from app.sentiment.service import analyze_sentiment, clean_text
from app.utils.keywords import extract_keywords
import random
import logging

logger = logging.getLogger(__name__)

DEMO_PRODUCTS = [
    {
        "name": "Samsung Galaxy S24 Ultra",
        "source": "amazon",
        "url": "https://amazon.com/dp/B0CRZ5K9XJ",
        "reviews": [
            {"text": "Amazing phone! The camera quality is incredible and battery lasts all day.", "rating": 5, "days_ago": 5},
            {"text": "Great display and performance. S Pen is very useful for notes.", "rating": 5, "days_ago": 12},
            {"text": "Good phone but expensive. Camera is the best feature.", "rating": 4, "days_ago": 18},
            {"text": "Overheats during gaming. Battery drains fast with 120Hz.", "rating": 2, "days_ago": 25},
            {"text": "Decent upgrade from S23. AI features are hit or miss.", "rating": 3, "days_ago": 30},
        ]
    },
    {
        "name": "iPhone 15 Pro Max",
        "source": "amazon",
        "url": "https://amazon.com/dp/B0CHX1W1XY",
        "reviews": [
            {"text": "Best iPhone ever! Titanium build feels premium. Camera is outstanding.", "rating": 5, "days_ago": 3},
            {"text": "Love the action button and USB-C. Battery life is incredible.", "rating": 5, "days_ago": 10},
            {"text": "Great phone but very heavy. Dynamic Island is useful.", "rating": 4, "days_ago": 15},
            {"text": "Overpriced for what you get. 60Hz on base model is unacceptable.", "rating": 2, "days_ago": 22},
            {"text": "Good but not worth upgrading from 14 Pro.", "rating": 3, "days_ago": 28},
        ]
    },
    {
        "name": "MacBook Pro 16 M3 Max",
        "source": "amazon",
        "url": "https://amazon.com/dp/B0CM5JV2Z6",
        "reviews": [
            {"text": "Incredible performance for video editing. Battery lasts 22 hours!", "rating": 5, "days_ago": 2},
            {"text": "Best laptop I've ever owned. Screen is gorgeous, speakers amazing.", "rating": 5, "days_ago": 8},
            {"text": "Expensive but worth it for professionals. Runs cool and quiet.", "rating": 5, "days_ago": 14},
            {"text": "Heavy to carry around. Charger is bulky.", "rating": 3, "days_ago": 20},
            {"text": "Great machine but macOS has some bugs with external monitors.", "rating": 3, "days_ago": 26},
        ]
    },
    {
        "name": "Sony WH-1000XM5",
        "source": "flipkart",
        "url": "https://flipkart.com/p/sony-wh-1000xm5",
        "reviews": [
            {"text": "Best noise cancellation on the market. Sound quality is superb.", "rating": 5, "days_ago": 1},
            {"text": "Comfortable for long flights. 30 hour battery is accurate.", "rating": 5, "days_ago": 7},
            {"text": "Good but case is bulky. Touch controls can be finicky.", "rating": 4, "days_ago": 13},
            {"text": "ANC hurts my ears after a while. Not worth the premium.", "rating": 2, "days_ago": 19},
            {"text": "Decent headphones but Bose QC45 sounds better to me.", "rating": 3, "days_ago": 24},
        ]
    },
    {
        "name": "Dell XPS 15 9530",
        "source": "flipkart",
        "url": "https://flipkart.com/p/dell-xps-15-9530",
        "reviews": [
            {"text": "Stunning OLED display. Great for creative work.", "rating": 5, "days_ago": 4},
            {"text": "Runs hot and fans are loud. Throttles under load.", "rating": 2, "days_ago": 11},
            {"text": "Good performance but battery life is mediocre.", "rating": 3, "days_ago": 17},
            {"text": "Premium build quality. Keyboard and trackpad are excellent.", "rating": 4, "days_ago": 23},
            {"text": "Overpriced. Many better options for the price.", "rating": 2, "days_ago": 29},
        ]
    },
]


def seed_demo_data():
    db = get_db()
    
    # Clear existing demo data
    demo_product_names = [p["name"] for p in DEMO_PRODUCTS]
    existing_products = list(db.products.find({"name": {"$in": demo_product_names}}))
    existing_ids = [p["_id"] for p in existing_products]
    
    if existing_ids:
        db.reviews.delete_many({"product_id": {"$in": existing_ids}})
        db.analyses.delete_many({"product_id": {"$in": existing_ids}})
        db.products.delete_many({"_id": {"$in": existing_ids}})
        logger.info(f"Cleared {len(existing_ids)} existing demo products")
    
    # Insert new demo data
    for product_data in DEMO_PRODUCTS:
        product = Product(
            name=product_data["name"],
            source=product_data["source"],
            url=product_data["url"],
        )
        result = db.products.insert_one(product.to_dict())
        product.id = result.inserted_id
        
        reviews_to_insert = []
        all_cleaned_texts = []
        positive_texts = []
        negative_texts = []
        
        for i, review_data in enumerate(product_data["reviews"]):
            review_text = review_data["text"]
            cleaned = clean_text(review_text)
            sentiment_result = analyze_sentiment(cleaned)
            
            review = Review(
                product_id=product.id,
                source=product_data["source"],
                review_text=review_text,
                cleaned_text=cleaned,
                rating=review_data["rating"],
                review_date=datetime.utcnow() - timedelta(days=review_data["days_ago"]),
                reviewer=f"User{random.randint(100, 999)}",
                sentiment=sentiment_result["label"],
                sentiment_score=sentiment_result["score"],
            )
            reviews_to_insert.append(review)
            all_cleaned_texts.append(cleaned)
            
            if sentiment_result["label"] == "positive":
                positive_texts.append(cleaned)
            elif sentiment_result["label"] == "negative":
                negative_texts.append(cleaned)
        
        if reviews_to_insert:
            review_docs = [r.to_dict() for r in reviews_to_insert]
            db.reviews.insert_many(review_docs)
        
        # Calculate analysis
        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
        for r in reviews_to_insert:
            sentiment_counts[r.sentiment] += 1
        
        total = len(reviews_to_insert)
        avg_rating = sum(r.rating for r in reviews_to_insert) / total if total > 0 else 0
        
        # Extract keywords
        top_keywords = extract_keywords(all_cleaned_texts, top_n=10)
        
        analysis = Analysis(
            product_id=product.id,
            positive_count=sentiment_counts["positive"],
            neutral_count=sentiment_counts["neutral"],
            negative_count=sentiment_counts["negative"],
            positive_percentage=round(sentiment_counts["positive"] / total * 100, 1) if total else 0,
            neutral_percentage=round(sentiment_counts["neutral"] / total * 100, 1) if total else 0,
            negative_percentage=round(sentiment_counts["negative"] / total * 100, 1) if total else 0,
            average_rating=round(avg_rating, 1),
            top_keywords=top_keywords,
        )
        db.analyses.insert_one(analysis.to_dict())
        
        # Update product
        db.products.update_one(
            {"_id": product.id},
            {"$set": {"rating": round(avg_rating, 1), "review_count": total}}
        )
        
        logger.info(f"Seeded demo product: {product.name} with {total} reviews")
    
    logger.info("Demo data seeding completed")


if __name__ == "__main__":
    import os
    os.environ["FLASK_ENV"] = "development"
    from app.utils.logging import setup_logging
    setup_logging()
    seed_demo_data()