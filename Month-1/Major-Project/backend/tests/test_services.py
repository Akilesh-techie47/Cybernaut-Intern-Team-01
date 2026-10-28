import pytest
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.sentiment.service import clean_text, analyze_sentiment, get_sentiment_label
from app.utils.keywords import extract_keywords, extract_positive_negative_keywords
from app.models.product import Product
from app.models.review import Review
from app.models.analysis import Analysis
from datetime import datetime
from bson import ObjectId


class TestSentimentService:
    def test_clean_text_basic(self):
        text = "  Hello   World!  "
        assert clean_text(text) == "Hello World!"
    
    def test_clean_text_html(self):
        text = "<p>Great product!</p>"
        assert clean_text(text) == "Great product!"
    
    def test_clean_text_urls(self):
        text = "Check https://example.com for more"
        assert "https://example.com" not in clean_text(text)
    
    def test_clean_text_empty(self):
        assert clean_text("") == ""
        assert clean_text(None) == ""
    
    def test_analyze_sentiment_positive(self):
        result = analyze_sentiment("This is amazing! Best product ever!")
        assert result["label"] == "positive"
        assert result["score"] > 0.05
    
    def test_analyze_sentiment_negative(self):
        result = analyze_sentiment("Terrible product. Waste of money. Hate it.")
        assert result["label"] == "negative"
        assert result["score"] < -0.05
    
    def test_analyze_sentiment_neutral(self):
        result = analyze_sentiment("It is a product.")
        assert result["label"] == "neutral"
    
    def test_analyze_sentiment_empty(self):
        result = analyze_sentiment("")
        assert result["label"] == "neutral"
        assert result["score"] == 0.0
    
    def test_get_sentiment_label(self):
        assert get_sentiment_label(0.1) == "positive"
        assert get_sentiment_label(-0.1) == "negative"
        assert get_sentiment_label(0.0) == "neutral"
        assert get_sentiment_label(0.04) == "neutral"
        assert get_sentiment_label(-0.04) == "neutral"


class TestKeywords:
    def test_extract_keywords_basic(self):
        texts = [
            "Great battery life and amazing camera",
            "Camera quality is excellent",
            "Battery lasts all day"
        ]
        keywords = extract_keywords(texts, top_n=5)
        assert "battery" in keywords
        assert "camera" in keywords
    
    def test_extract_keywords_stopwords(self):
        texts = ["The product is good and works well"]
        keywords = extract_keywords(texts, top_n=5)
        assert "the" not in keywords
        assert "and" not in keywords
        assert "is" not in keywords
    
    def test_extract_keywords_empty(self):
        assert extract_keywords([]) == []
        assert extract_keywords([""]) == []
    
    def test_extract_positive_negative_keywords(self):
        positive = ["Great battery life", "Amazing camera quality"]
        negative = ["Poor battery life", "Bad camera"]
        result = extract_positive_negative_keywords(positive, negative, top_n=5)
        # "battery" and "camera" appear in both, so should be excluded
        assert "battery" not in result["praised"]
        assert "battery" not in result["criticized"]


class TestModels:
    def test_product_to_dict(self):
        product = Product(
            name="Test Product",
            source="amazon",
            url="https://amazon.com/test",
            rating=4.5,
            review_count=100,
        )
        data = product.to_dict()
        assert data["name"] == "Test Product"
        assert data["source"] == "amazon"
        assert data["rating"] == 4.5
        assert data["review_count"] == 100
    
    def test_product_from_dict(self):
        data = {
            "_id": ObjectId(),
            "name": "Test Product",
            "source": "amazon",
            "url": "https://amazon.com/test",
            "rating": 4.5,
            "review_count": 100,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        product = Product.from_dict(data)
        assert product.name == "Test Product"
        assert product.id == data["_id"]
    
    def test_review_to_dict(self):
        oid = ObjectId()
        review = Review(
            product_id=oid,
            source="amazon",
            review_text="Great product!",
            cleaned_text="Great product!",
            rating=5,
            review_date=datetime.utcnow(),
            sentiment="positive",
            sentiment_score=0.8,
        )
        data = review.to_dict()
        assert data["product_id"] == oid
        assert data["sentiment"] == "positive"
        assert data["sentiment_score"] == 0.8
    
    def test_analysis_to_dict(self):
        oid = ObjectId()
        analysis = Analysis(
            product_id=oid,
            positive_count=70,
            neutral_count=20,
            negative_count=10,
            positive_percentage=70.0,
            neutral_percentage=20.0,
            negative_percentage=10.0,
            average_rating=4.5,
            top_keywords=["battery", "camera"],
        )
        data = analysis.to_dict()
        assert data["positive_count"] == 70
        assert data["top_keywords"] == ["battery", "camera"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])