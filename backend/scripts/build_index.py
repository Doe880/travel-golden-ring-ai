import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent

sys.path.append(str(BACKEND_DIR))

from app.chunker import build_all_chunks
from app.config import KNOWLEDGE_BASE_DIR, LOCAL_EMBEDDING_MODEL, VECTOR_INDEX_PATH
from app.embeddings import create_passage_embeddings_batch


def main():
    print("Читаю базу знаний...")
    chunks = build_all_chunks(KNOWLEDGE_BASE_DIR)

    print(f"Найдено чанков: {len(chunks)}")

    texts = [chunk["text"] for chunk in chunks]

    print(f"Создаю embeddings через модель: {LOCAL_EMBEDDING_MODEL}")
    embeddings = create_passage_embeddings_batch(texts)

    items = []

    for chunk, embedding in zip(chunks, embeddings):
        items.append(
            {
                **chunk,
                "embedding": embedding,
            }
        )

    VECTOR_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

    with VECTOR_INDEX_PATH.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "embedding_provider": "local",
                "embedding_model": LOCAL_EMBEDDING_MODEL,
                "items": items,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Готово. Индекс сохранён: {VECTOR_INDEX_PATH}")


if __name__ == "__main__":
    main()