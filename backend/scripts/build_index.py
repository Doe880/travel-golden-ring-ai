import asyncio
import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent

sys.path.append(str(BACKEND_DIR))

from app.chunker import build_all_chunks
from app.config import (
    KNOWLEDGE_BASE_DIR,
    ROUTERAI_EMBEDDING_MODEL,
    VECTOR_INDEX_PATH,
)
from app.embeddings import create_passage_embeddings_batch_async


BATCH_SIZE = 8


async def main():
    print("Читаю базу знаний...")
    chunks = build_all_chunks(KNOWLEDGE_BASE_DIR)

    print(f"Найдено чанков: {len(chunks)}")

    items = []

    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        texts = [chunk["text"] for chunk in batch]

        print(
            f"Создаю embeddings: {start + 1}–{start + len(batch)} "
            f"из {len(chunks)} через {ROUTERAI_EMBEDDING_MODEL}"
        )

        embeddings = await create_passage_embeddings_batch_async(texts)

        for chunk, embedding in zip(batch, embeddings):
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
                "embedding_provider": "routerai",
                "embedding_model": ROUTERAI_EMBEDDING_MODEL,
                "items": items,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Готово. Индекс сохранён: {VECTOR_INDEX_PATH}")


if __name__ == "__main__":
    asyncio.run(main())