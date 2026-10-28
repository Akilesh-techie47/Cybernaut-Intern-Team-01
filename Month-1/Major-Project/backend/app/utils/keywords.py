import re
from collections import Counter
from typing import List

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "up", "about", "into", "through", "during", "before", "after",
    "above", "below", "between", "under", "again", "further", "then", "once", "here",
    "there", "when", "where", "why", "how", "all", "each", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "can", "will", "just", "don", "should", "now", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "having", "do", "does", "did",
    "doing", "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your",
    "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she", "her",
    "hers", "herself", "it", "its", "itself", "they", "them", "their", "theirs",
    "themselves", "what", "which", "who", "whom", "this", "that", "these", "those",
    "am", "product", "products", "review", "reviews", "like", "good", "great", "bad",
    "best", "worst", "better", "well", "also", "would", "could", "should", "really",
    "much", "many", "one", "two", "three", "four", "five", "first", "last", "new",
    "old", "item", "items", "buy", "bought", "purchase", "purchased", "order", "ordered",
    "delivery", "delivered", "shipping", "shipped", "quality", "price", "value", "money",
    "worth", "recommend", "recommended", "use", "used", "using", "work", "works",
    "working", "time", "day", "days", "week", "weeks", "month", "months", "year", "years"
}


def extract_keywords(texts: List[str], top_n: int = 10) -> List[str]:
    if not texts:
        return []

    all_words = []
    for text in texts:
        words = re.findall(r"\b[a-z']{3,}\b", text.lower())
        filtered = [w for w in words if w not in STOP_WORDS and not w.isdigit()]
        all_words.extend(filtered)

    if not all_words:
        return []

    counter = Counter(all_words)
    return [word for word, _ in counter.most_common(top_n)]


def extract_positive_negative_keywords(
    positive_texts: List[str], negative_texts: List[str], top_n: int = 10
) -> dict:
    pos_keywords = extract_keywords(positive_texts, top_n * 2)
    neg_keywords = extract_keywords(negative_texts, top_n * 2)

    pos_set = set(pos_keywords)
    neg_set = set(neg_keywords)

    praised = [w for w in pos_keywords if w not in neg_set][:top_n]
    criticized = [w for w in neg_keywords if w not in pos_set][:top_n]

    return {"praised": praised, "criticized": criticized}