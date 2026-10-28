from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from bson import ObjectId


@dataclass
class Product:
    name: str
    source: str
    url: str
    rating: float = 0.0
    review_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    id: Optional[ObjectId] = None

    def to_dict(self) -> dict:
        data = {
            "name": self.name,
            "source": self.source,
            "url": self.url,
            "rating": self.rating,
            "review_count": self.review_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.id:
            data["_id"] = str(self.id)
            data["id"] = str(self.id)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Product":
        return cls(
            id=data.get("_id"),
            name=data.get("name", ""),
            source=data.get("source", ""),
            url=data.get("url", ""),
            rating=data.get("rating", 0.0),
            review_count=data.get("review_count", 0),
            created_at=data.get("created_at", datetime.utcnow()),
            updated_at=data.get("updated_at", datetime.utcnow()),
        )