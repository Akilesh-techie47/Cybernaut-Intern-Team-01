from flask import Blueprint, jsonify
from app.database.repositories import ProductRepository, ReviewRepository
from app.utils.responses import success_response, error_response
import logging

logger = logging.getLogger(__name__)

stats_bp = Blueprint("stats", __name__)

product_repo = ProductRepository()
review_repo = ReviewRepository()


@stats_bp.route("/stats", methods=["GET"])
def get_global_stats():
    try:
        total_products = product_repo.count()
        total_reviews = review_repo.collection.count_documents({})

        pipeline = [
            {"$group": {"_id": "$sentiment", "count": {"$sum": 1}}},
        ]
        sentiment_results = review_repo.collection.aggregate(pipeline)
        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
        for r in sentiment_results:
            sentiment_counts[r["_id"]] = r["count"]

        total_sentiment = sum(sentiment_counts.values())
        percentages = {}
        for k, v in sentiment_counts.items():
            percentages[k] = round(v / total_sentiment * 100, 1) if total_sentiment else 0

        # Global rating distribution
        rating_pipeline = [
            {"$group": {"_id": "$rating", "count": {"$sum": 1}}},
        ]
        rating_results = review_repo.collection.aggregate(rating_pipeline)
        rating_distribution = {str(r["_id"]): r["count"] for r in rating_results}

        # Global trends
        from datetime import datetime, timedelta
        start_date = datetime.utcnow() - timedelta(days=30)
        trend_pipeline = [
            {"$match": {"review_date": {"$gte": start_date}}},
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
        raw_trends = list(review_repo.collection.aggregate(trend_pipeline))
        formatted_trends = {}
        for t in raw_trends:
            date = t["_id"]["date"]
            sentiment = t["_id"]["sentiment"]
            count = t["count"]
            if date not in formatted_trends:
                formatted_trends[date] = {"positive": 0, "neutral": 0, "negative": 0, "total": 0}
            formatted_trends[date][sentiment] = count
            formatted_trends[date]["total"] += count

        trends = []
        for date, data in sorted(formatted_trends.items()):
            tot = data["total"]
            trends.append({
                "date": date,
                "positive": data["positive"],
                "neutral": data["neutral"],
                "negative": data["negative"],
                "positive_pct": round(data["positive"] / tot * 100, 1) if tot else 0,
                "neutral_pct": round(data["neutral"] / tot * 100, 1) if tot else 0,
                "negative_pct": round(data["negative"] / tot * 100, 1) if tot else 0,
            })

        recent_products = product_repo.find_all(limit=5)

        return success_response({
            "total_products": total_products,
            "total_reviews": total_reviews,
            "sentiment_distribution": sentiment_counts,
            "sentiment_percentages": percentages,
            "rating_distribution": rating_distribution,
            "trends": trends,
            "recent_products": [p.to_dict() for p in recent_products],
        })
    except Exception as e:
        logger.error(f"Get stats failed: {e}")
        return error_response("Failed to fetch statistics")