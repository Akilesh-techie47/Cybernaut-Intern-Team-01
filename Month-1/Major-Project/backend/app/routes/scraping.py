from flask import Blueprint, request, jsonify
from app.services.scraping_service import ScrapingService
from app.scrapers.factory import SUPPORTED_SOURCES
from app.utils.responses import success_response, error_response, validation_error_response
import logging

logger = logging.getLogger(__name__)

scraping_bp = Blueprint("scraping", __name__)

scraping_service = ScrapingService()


@scraping_bp.route("/scrape", methods=["POST"])
def scrape_product():
    data = request.get_json()
    if not data:
        return validation_error_response({"body": "Request body required"})

    query = data.get("query", "").strip()
    source = data.get("source", "").lower().strip()
    limit = data.get("limit", 50)

    errors = {}
    if not query:
        errors["query"] = "Product query is required"
    if not source:
        errors["source"] = "Source is required"
    elif source not in SUPPORTED_SOURCES:
        errors["source"] = f"Unsupported source. Supported: {SUPPORTED_SOURCES}"
    if not isinstance(limit, int) or limit < 1 or limit > 200:
        errors["limit"] = "Limit must be between 1 and 200"

    if errors:
        return validation_error_response(errors)

    logger.info(f"Starting scrape: query={query}, source={source}, limit={limit}")
    result = scraping_service.scrape_and_analyze(query, source, limit)

    if result.get("success"):
        return success_response(result, "Scraping completed")
    else:
        return error_response(result.get("error", "Scraping failed"), "SCRAPER_ERROR")


@scraping_bp.route("/scrape/sources", methods=["GET"])
def get_supported_sources():
    return success_response({"sources": SUPPORTED_SOURCES})