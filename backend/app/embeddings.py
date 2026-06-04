from typing import Any, Dict, List, Union

import httpx

from app.config import (
    EMBEDDING_PROVIDER,
    ROUTERAI_API_KEY,
    ROUTERAI_EMBEDDING_MODEL,
    ROUTERAI_EMBEDDING_URL,
)


class EmbeddingError(Exception):
    pass


def get_routerai_headers() -> Dict[str, str]:
    if not ROUTERAI_API_KEY:
        raise RuntimeError("Не найден ROUTERAI_API_KEY. Проверь backend/.env")

    return {
        "Authorization": f"Bearer {ROUTERAI_API_KEY}",
        "Content-Type": "application/json",
    }


async def request_routerai_embeddings(
    input_data: Union[str, List[str]],
) -> List[List[float]]:
    """
    Получает embeddings через RouterAI.

    RouterAI endpoint:
    POST https://routerai.ru/api/v1/embeddings

    Payload:
    {
      "model": "sentence-transformers/all-minilm-l12-v2",
      "input": "...",
      "encoding_format": "float"
    }
    """

    if EMBEDDING_PROVIDER != "routerai":
        raise RuntimeError(
            f"Неподдерживаемый EMBEDDING_PROVIDER={EMBEDDING_PROVIDER}. "
            "Сейчас используется routerai."
        )

    payload: Dict[str, Any] = {
        "model": ROUTERAI_EMBEDDING_MODEL,
        "input": input_data,
        "encoding_format": "float",
    }

    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            ROUTERAI_EMBEDDING_URL,
            headers=get_routerai_headers(),
            json=payload,
        )

    if response.status_code >= 400:
        raise EmbeddingError(
            f"RouterAI embeddings error {response.status_code}: {response.text}"
        )

    data = response.json()

    try:
        embeddings = [item["embedding"] for item in data["data"]]
    except (KeyError, TypeError) as e:
        raise EmbeddingError(
            f"Неожиданный формат ответа RouterAI embeddings: {data}"
        ) from e

    if not embeddings:
        raise EmbeddingError("RouterAI вернул пустой список embeddings")

    return embeddings


async def create_query_embedding_async(text: str) -> List[float]:
    """
    Embedding для пользовательского запроса.
    """

    embeddings = await request_routerai_embeddings(text)

    return embeddings[0]


async def create_passage_embedding_async(text: str) -> List[float]:
    """
    Embedding для одного чанка базы знаний.
    """

    embeddings = await request_routerai_embeddings(text)

    return embeddings[0]


async def create_passage_embeddings_batch_async(texts: List[str]) -> List[List[float]]:
    """
    Embeddings для пачки чанков базы знаний.
    """

    if not texts:
        return []

    embeddings = await request_routerai_embeddings(texts)

    if len(embeddings) != len(texts):
        raise EmbeddingError(
            f"Количество embeddings не совпадает: "
            f"ожидали {len(texts)}, получили {len(embeddings)}"
        )

    return embeddings