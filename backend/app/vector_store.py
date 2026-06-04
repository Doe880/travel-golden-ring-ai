import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import TOP_K, VECTOR_INDEX_PATH
from app.embeddings import create_query_embedding_async


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


class VectorStore:
    def __init__(self, index_path: Path = VECTOR_INDEX_PATH):
        self.index_path = index_path
        self.items: List[Dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        if not self.index_path.exists():
            self.items = []
            return

        with self.index_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self.items = data.get("items", [])

    async def search(
        self,
        query: str,
        city: Optional[str] = None,
        top_k: int = TOP_K,
    ) -> List[Dict[str, Any]]:
        if not self.items:
            return []

        query_vector = await create_query_embedding_async(query)

        results = []

        for item in self.items:
            if city and item.get("city", "").lower() != city.lower():
                continue

            score = cosine_similarity(query_vector, item.get("embedding", []))

            results.append(
                {
                    **item,
                    "score": score,
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:top_k]


vector_store = VectorStore()