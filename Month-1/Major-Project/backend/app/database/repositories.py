from typing import List, Optional
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from app.database.connection import get_db
from app.models.product import Product
from app.models.review import Review
from app.models.analysis import Analysis
import logging

logger = logging.getLogger(__name__)


class ProductRepository:
    def __init__(self):
        self.collection = get_db()["products"]
        self._create_indexes()

    def _create_indexes(self):
        self.collection.create_index([("source", ASCENDING), ("name", ASCENDING)])
        self.collection.create_index([("created_at", DESCENDING)])

    def create(self, product: Product) -> Product:
        result = self.collection.insert_one(product.to_dict())
        product.id = result.inserted_id
        logger.info(f"Created product: {product.name}")
        return product

    def find_by_id(self, product_id: ObjectId) -> Optional[Product]:
        data = self.collection.find_one({"_id": product_id})
        return Product.from_dict(data) if data else None

    def find_by_source_and_name(self, source: str, name: str) -> Optional[Product]:
        data = self.collection.find_one({"source": source, "name": name})
        return Product.from_dict(data) if data else None

    def find_all(self, limit: int = 50, skip: int = 0) -> List[Product]:
        cursor = self.collection.find().sort("created_at", DESCENDING).skip(skip).limit(limit)
        return [Product.from_dict(doc) for doc in cursor]

    def update(self, product: Product) -> Product:
        product.updated_at = __import__("datetime").datetime.utcnow()
        payload = product.to_dict()
        payload.pop("_id", None)
        payload.pop("id", None)
        self.collection.update_one(
            {"_id": product.id}, {"$set": payload}
        )
        logger.info(f"Updated product: {product.name}")
        return product

    def delete(self, product_id: ObjectId) -> bool:
        result = self.collection.delete_one({"_id": product_id})
        return result.deleted_count > 0

    def count(self) -> int:
        return self.collection.count_documents({})


class ReviewRepository:
    def __init__(self):
        self.collection = get_db()["reviews"]
        self._create_indexes()

    def _create_indexes(self):
        self.collection.create_index([("product_id", ASCENDING)])
        self.collection.create_index([("source", ASCENDING)])
        self.collection.create_index([("sentiment", ASCENDING)])
        self.collection.create_index([("review_date", DESCENDING)])
        self.collection.create_index(
            ["product_id", "source", "review_text", "review_date"],
            unique=True,
            name="review_fingerprint_unique",
        )

    def create(self, review: Review) -> Optional[Review]:
        try:
            result = self.collection.insert_one(review.to_dict())
            review.id = result.inserted_id
            logger.info(f"Created review for product: {review.product_id}")
            return review
        except Exception as e:
            if "duplicate key" in str(e).lower():
                logger.debug("Duplicate review skipped")
                return None
            logger.error(f"Failed to create review: {e}")
            raise

    def bulk_create(self, reviews: List[Review]) -> List[Review]:
        if not reviews:
            return []
        docs = [r.to_dict() for r in reviews]
        try:
            result = self.collection.insert_many(docs, ordered=False)
            for i, review in enumerate(reviews):
                review.id = result.inserted_ids[i]
            logger.info(f"Bulk created {len(reviews)} reviews")
            return reviews
        except Exception as e:
            # ordered=False means some docs may have inserted despite duplicate-key errors.
            # Fall back to per-document inserts so a single duplicate never fails the whole analysis.
            logger.warning(f"Bulk insert hit errors, falling back to individual inserts: {e}")
            inserted: List[Review] = []
            for review in reviews:
                try:
                    created = self.create(review)
                    if created is not None:
                        inserted.append(created)
                except Exception:
                    continue
            return inserted

    def find_by_product_id(
        self, product_id: ObjectId, limit: int = 50, skip: int = 0, sentiment: str = None
    ) -> List[Review]:
        query = {"product_id": product_id}
        if sentiment:
            query["sentiment"] = sentiment
        cursor = self.collection.find(query).sort("review_date", DESCENDING).skip(skip).limit(limit)
        return [Review.from_dict(doc) for doc in cursor]

    def count_by_product_id(self, product_id: ObjectId, sentiment: str = None) -> int:
        query = {"product_id": product_id}
        if sentiment:
            query["sentiment"] = sentiment
        return self.collection.count_documents(query)

    def get_sentiment_counts(self, product_id: ObjectId) -> dict:
        pipeline = [
            {"$match": {"product_id": product_id}},
            {"$group": {"_id": "$sentiment", "count": {"$sum": 1}}},
        ]
        results = self.collection.aggregate(pipeline)
        counts = {"positive": 0, "neutral": 0, "negative": 0}
        for r in results:
            counts[r["_id"]] = r["count"]
        return counts

    def get_rating_distribution(self, product_id: ObjectId) -> dict:
        pipeline = [
            {"$match": {"product_id": product_id}},
            {"$group": {"_id": "$rating", "count": {"$sum": 1}}},
        ]
        results = self.collection.aggregate(pipeline)
        return {str(r["_id"]): r["count"] for r in results}

    def get_sentiment_trends(self, product_id: ObjectId, days: int = 30) -> List[dict]:
        from datetime import datetime, timedelta
        start_date = datetime.utcnow() - timedelta(days=days)
        pipeline = [
            {"$match": {"product_id": product_id, "review_date": {"$gte": start_date}}},
            {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$review_date"}},
                        "sentiment": "$sentiment",
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id.date": 1}},
        ]
        return list(self.collection.aggregate(pipeline))

    def get_reviews_for_keywords(self, product_id: ObjectId, limit: int = 500) -> List[str]:
        cursor = self.collection.find(
            {"product_id": product_id},
            {"cleaned_text": 1, "_id": 0},
        ).limit(limit)
        return [doc["cleaned_text"] for doc in cursor if doc.get("cleaned_text")]

    def delete_by_product_id(self, product_id: ObjectId) -> int:
        result = self.collection.delete_many({"product_id": product_id})
        return result.deleted_count


class AnalysisRepository:
    def __init__(self):
        self.collection = get_db()["analyses"]
        self._create_indexes()

    def _create_indexes(self):
        self.collection.create_index([("product_id", ASCENDING)], unique=True)
        self.collection.create_index([("created_at", DESCENDING)])

    def create(self, analysis: Analysis) -> Analysis:
        result = self.collection.insert_one(analysis.to_dict())
        analysis.id = result.inserted_id
        logger.info(f"Created analysis for product: {analysis.product_id}")
        return analysis

    def find_by_product_id(self, product_id: ObjectId) -> Optional[Analysis]:
        data = self.collection.find_one({"product_id": product_id})
        if not data:
            # Backward compat: some docs stored product_id as string.
            data = self.collection.find_one({"product_id": str(product_id)})
        return Analysis.from_dict(data) if data else None

    def update(self, analysis: Analysis) -> Analysis:
        payload = analysis.to_dict()
        payload.pop("_id", None)
        payload.pop("id", None)
        self.collection.update_one(
            {"product_id": analysis.product_id},
            {"$set": payload},
            upsert=True,
        )
        logger.info(f"Updated analysis for product: {analysis.product_id}")
        return analysis

    def upsert(self, analysis: Analysis) -> Analysis:
        payload = analysis.to_dict()
        payload.pop("_id", None)
        payload.pop("id", None)
        self.collection.update_one(
            {"product_id": analysis.product_id},
            {"$set": payload},
            upsert=True,
        )
        return analysis