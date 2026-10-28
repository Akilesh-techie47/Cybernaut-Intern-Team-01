from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from bson import ObjectId


@dataclass
class Review:
    product_id: ObjectId
    source: str
    review_text: str
    cleaned_text: str
    rating: int
    review_date: datetime
    reviewer: str = ""
    sentiment: str = "neutral"
    sentiment_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: Optional[ObjectId] = None

    def to_dict(self) -> dict:
        data = {
            "product_id": self.product_id,
            "source": self.source,
            "review_text": self.review_text,
            "cleaned_text": self.cleaned_text,
            "rating": self.rating,
            "review_date": self.review_date,
            "reviewer": self.reviewer,
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
            "created_at": self.created_at,
        }
        if self.id:
            data["_id"] = str(self.id)
            data["id"] = str(self.id)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Review":
        return cls(
            id=data.get("_id"),
            product_id=data.get("product_id"),
            source=data.get("source", ""),
            review_text=data.get("review_text", ""),
            cleaned_text=data.get("cleaned_text", ""),
            rating=data.get("rating", 0),
            review_date=data.get("review_date", datetime.utcnow()),
            reviewer=data.get("reviewer", ""),
            sentiment=data.get("sentiment", "neutral"),
            sentiment_score=data.get("sentiment_score", 0.0),
            created_at=data.get("created_at", datetime.utcnow()),
        )