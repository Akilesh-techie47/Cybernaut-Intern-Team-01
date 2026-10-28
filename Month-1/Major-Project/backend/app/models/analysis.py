from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from bson import ObjectId


@dataclass
class Analysis:
    product_id: ObjectId
    positive_count: int = 0
    neutral_count: int = 0
    negative_count: int = 0
    positive_percentage: float = 0.0
    neutral_percentage: float = 0.0
    negative_percentage: float = 0.0
    average_rating: float = 0.0
    top_keywords: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: Optional[ObjectId] = None

    def to_dict(self) -> dict:
        data = {
            "product_id": self.product_id,
            "positive_count": self.positive_count,
            "neutral_count": self.neutral_count,
            "negative_count": self.negative_count,
            "positive_percentage": self.positive_percentage,
            "neutral_percentage": self.neutral_percentage,
            "negative_percentage": self.negative_percentage,
            "average_rating": self.average_rating,
            "top_keywords": self.top_keywords,
            "created_at": self.created_at,
        }
        if self.id:
            data["_id"] = str(self.id)
            data["id"] = str(self.id)
        # Keep product_id as ObjectId in storage; API layer serializes it to str.
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Analysis":
        return cls(
            id=data.get("_id"),
            product_id=data.get("product_id"),
            positive_count=data.get("positive_count", 0),
            neutral_count=data.get("neutral_count", 0),
            negative_count=data.get("negative_count", 0),
            positive_percentage=data.get("positive_percentage", 0.0),
            neutral_percentage=data.get("neutral_percentage", 0.0),
            negative_percentage=data.get("negative_percentage", 0.0),
            average_rating=data.get("average_rating", 0.0),
            top_keywords=data.get("top_keywords", []),
            created_at=data.get("created_at", datetime.utcnow()),
        )