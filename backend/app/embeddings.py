from typing import List

from sentence_transformers import SentenceTransformer

from app.config import EMBEDDING_PROVIDER, LOCAL_EMBEDDING_MODEL


_model = None


def get_local_model() -> SentenceTransformer:
    global _model

    if _model is None:
        _model = SentenceTransformer(LOCAL_EMBEDDING_MODEL)

    return _model


def prepare_query_text(text: str) -> str:
    """
    Для E5-моделей запросы нужно подавать с префиксом query:
    """

    text = text.strip()

    if text.lower().startswith("query:"):
        return text

    return f"query: {text}"


def prepare_passage_text(text: str) -> str:
    """
    Для E5-моделей документы/чанки нужно подавать с префиксом passage:
    """

    text = text.strip()

    if text.lower().startswith("passage:"):
        return text

    return f"passage: {text}"


def create_query_embedding(text: str) -> List[float]:
    """
    Embedding для пользовательского запроса.
    """

    if EMBEDDING_PROVIDER != "local":
        raise RuntimeError(
            f"Неподдерживаемый EMBEDDING_PROVIDER={EMBEDDING_PROVIDER}. "
            "Сейчас используется local."
        )

    model = get_local_model()

    vector = model.encode(
        prepare_query_text(text),
        normalize_embeddings=True,
    )

    return vector.tolist()


def create_passage_embedding(text: str) -> List[float]:
    """
    Embedding для одного чанка базы знаний.
    """

    if EMBEDDING_PROVIDER != "local":
        raise RuntimeError(
            f"Неподдерживаемый EMBEDDING_PROVIDER={EMBEDDING_PROVIDER}. "
            "Сейчас используется local."
        )

    model = get_local_model()

    vector = model.encode(
        prepare_passage_text(text),
        normalize_embeddings=True,
    )

    return vector.tolist()


def create_passage_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Embeddings для пачки чанков базы знаний.
    """

    if EMBEDDING_PROVIDER != "local":
        raise RuntimeError(
            f"Неподдерживаемый EMBEDDING_PROVIDER={EMBEDDING_PROVIDER}. "
            "Сейчас используется local."
        )

    if not texts:
        return []

    model = get_local_model()

    prepared_texts = [prepare_passage_text(text) for text in texts]

    vectors = model.encode(
        prepared_texts,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    return [vector.tolist() for vector in vectors]