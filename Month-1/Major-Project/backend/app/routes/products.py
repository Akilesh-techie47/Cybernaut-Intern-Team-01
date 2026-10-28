from flask import Blueprint, request, jsonify
from bson import ObjectId
from app.database.repositories import ProductRepository, ReviewRepository, AnalysisRepository
from app.utils.responses import (
    success_response, error_response, not_found_response, validation_error_response
)
import logging

logger = logging.getLogger(__name__)

products_bp = Blueprint("products", __name__)

product_repo = ProductRepository()
review_repo = ReviewRepository()
analysis_repo = AnalysisRepository()


@products_bp.route("/products", methods=["GET"])
def get_products():
    try:
        limit = min(int(request.args.get("limit", 50)), 100)
        skip = int(request.args.get("skip", 0))
        products = product_repo.find_all(limit=limit, skip=skip)
        total = product_repo.count()
        return success_response({
            "products": [p.to_dict() for p in products],
            "total": total,
            "limit": limit,
            "skip": skip,
        })
    except Exception as e:
        logger.error(f"Get products failed: {e}")
        return error_response("Failed to fetch products")


@products_bp.route("/products/<product_id>", methods=["GET"])
def get_product(product_id):
    try:
        oid = ObjectId(product_id)
    except Exception:
        return error_response("Invalid product ID", "INVALID_ID", 400)

    product = product_repo.find_by_id(oid)
    if not product:
        return not_found_response("Product")

    return success_response(product.to_dict())


@products_bp.route("/products/<product_id>/reviews", methods=["GET"])
def get_reviews(product_id):
    try:
        oid = ObjectId(product_id)
    except Exception:
        return error_response("Invalid product ID", "INVALID_ID", 400)

    product = product_repo.find_by_id(oid)
    if not product:
        return not_found_response("Product")

    try:
        limit = min(int(request.args.get("limit", 50)), 100)
        skip = int(request.args.get("skip", 0))
        sentiment = request.args.get("sentiment")
        if sentiment and sentiment not in ["positive", "neutral", "negative"]:
            sentiment = None
    except ValueError:
        return validation_error_response({"limit": "Invalid limit", "skip": "Invalid skip"})

    reviews = review_repo.find_by_product_id(oid, limit=limit, skip=skip, sentiment=sentiment)
    total = review_repo.count_by_product_id(oid, sentiment=sentiment)

    return success_response({
        "reviews": [r.to_dict() for r in reviews],
        "total": total,
        "limit": limit,
        "skip": skip,
    })


@products_bp.route("/products/<product_id>/sentiment", methods=["GET"])
def get_sentiment(product_id):
    try:
        oid = ObjectId(product_id)
    except Exception:
        return error_response("Invalid product ID", "INVALID_ID", 400)

    product = product_repo.find_by_id(oid)
    if not product:
        return not_found_response("Product")

    analysis = analysis_repo.find_by_product_id(oid)
    rating_distribution = review_repo.get_rating_distribution(oid)
    if not analysis:
        return success_response({
            "product_id": product_id,
            "positive_count": 0,
            "neutral_count": 0,
            "negative_count": 0,
            "positive_percentage": 0,
            "neutral_percentage": 0,
            "negative_percentage": 0,
            "average_rating": 0,
            "top_keywords": [],
            "rating_distribution": rating_distribution,
        })

    data = analysis.to_dict()
    data["rating_distribution"] = rating_distribution
    return success_response(data)


@products_bp.route("/products/<product_id>/trends", methods=["GET"])
def get_trends(product_id):
    try:
        oid = ObjectId(product_id)
    except Exception:
        return error_response("Invalid product ID", "INVALID_ID", 400)

    product = product_repo.find_by_id(oid)
    if not product:
        return not_found_response("Product")

    days = min(int(request.args.get("days", 30)), 365)
    trends = review_repo.get_sentiment_trends(oid, days=days)

    formatted = {}
    for t in trends:
        date = t["_id"]["date"]
        sentiment = t["_id"]["sentiment"]
        count = t["count"]
        if date not in formatted:
            formatted[date] = {"positive": 0, "neutral": 0, "negative": 0, "total": 0}
        formatted[date][sentiment] = count
        formatted[date]["total"] += count

    result = []
    for date, data in sorted(formatted.items()):
        total = data["total"]
        result.append({
            "date": date,
            "positive": data["positive"],
            "neutral": data["neutral"],
            "negative": data["negative"],
            "positive_pct": round(data["positive"] / total * 100, 1) if total else 0,
            "neutral_pct": round(data["neutral"] / total * 100, 1) if total else 0,
            "negative_pct": round(data["negative"] / total * 100, 1) if total else 0,
        })

    return success_response({"trends": result})


@products_bp.route("/products/<product_id>/keywords", methods=["GET"])
def get_keywords(product_id):
    try:
        oid = ObjectId(product_id)
    except Exception:
        return error_response("Invalid product ID", "INVALID_ID", 400)

    product = product_repo.find_by_id(oid)
    if not product:
        return not_found_response("Product")

    analysis = analysis_repo.find_by_product_id(oid)
    if not analysis:
        return success_response({"praised": [], "criticized": []})

    return success_response({
        "top_keywords": analysis.top_keywords,
    })


@products_bp.route("/products/<product_id>", methods=["DELETE"])
def delete_product(product_id):
    try:
        oid = ObjectId(product_id)
    except Exception:
        return error_response("Invalid product ID", "INVALID_ID", 400)

    product = product_repo.find_by_id(oid)
    if not product:
        return not_found_response("Product")

    review_repo.delete_by_product_id(oid)
    product_repo.delete(oid)

    logger.info(f"Deleted product {product_id} and associated reviews")
    return success_response(None, "Product deleted")