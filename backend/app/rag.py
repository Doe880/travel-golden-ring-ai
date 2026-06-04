import json
import re
from typing import Any, Dict, List, Optional

from app.llm_client import generate_with_routerai
from app.photos import get_commons_photo_url
from app.vector_store import vector_store


SYSTEM_PROMPT = """
Ты AI-помощник по планированию путешествий по Золотому кольцу России.

Твоя задача:
1. Составлять понятные маршруты.
2. Рекомендовать достопримечательности.
3. Подсказывать, где погулять, что попробовать и какие сувениры купить.
4. Использовать в первую очередь данные из базы знаний.
5. Если в базе нет точных данных, можешь аккуратно добавить общую туристическую информацию, но помечай это как рекомендацию.
6. Не выдумывай точные цены, расписания и часы работы, если их нет в контексте.
7. Если пользователь просит маршрут, пиши по времени и порядку посещения.
8. Ответ должен быть на русском языке.

Верни СТРОГО JSON без markdown-блоков и без пояснений до или после JSON.

Формат ответа:
{
  "answer": "Основной текст ответа",
  "city": "Город или null",
  "places": [
    {
      "name": "Название места",
      "city": "Город",
      "description": "Краткое описание",
      "lat": 56.0,
      "lon": 40.0,
      "category": "достопримечательность | еда | сувенир | прогулка | музей"
    }
  ]
}
"""


def clean_json_text(text: str) -> str:
    text = text.strip()

    text = re.sub(r"^```json", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^```", "", text).strip()
    text = re.sub(r"```$", "", text).strip()

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text


def build_context(chunks: List[Dict[str, Any]]) -> str:
    parts = []

    for chunk in chunks:
        parts.append(
            f"""
Источник: {chunk.get("source_file")}
Город: {chunk.get("city")}
Раздел: {chunk.get("title")}
Релевантность: {round(chunk.get("score", 0), 3)}

{chunk.get("text")}
""".strip()
        )

    return "\n\n---\n\n".join(parts)


async def enrich_places_with_photos(places: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched = []

    for place in places:
        name = place.get("name")
        city = place.get("city")

        if name and not place.get("photo_url"):
            query = f"{name} {city or ''} Россия"
            place["photo_url"] = await get_commons_photo_url(query)

        enriched.append(place)

    return enriched


async def ask_travel_agent(query: str, city: Optional[str] = None) -> Dict[str, Any]:
    search_query = query

    if city:
        search_query = f"{city}. {query}"

    chunks = await vector_store.search(
        query=search_query,
        city=city,
    )

    context = build_context(chunks)

    user_prompt = f"""
Контекст из базы знаний:
{context}

Запрос пользователя:
{query}

Выбранный город:
{city or "не выбран"}

Сформируй ответ строго в JSON-формате.
""".strip()

    raw_text = await generate_with_routerai(
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
    )

    json_text = clean_json_text(raw_text)

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        parsed = {
            "answer": raw_text,
            "city": city,
            "places": [],
        }

    places = parsed.get("places", [])

    if isinstance(places, list):
        places = await enrich_places_with_photos(places)
    else:
        places = []

    sources = []

    for chunk in chunks:
        label = f'{chunk.get("city")} — {chunk.get("title")} ({chunk.get("source_file")})'
        sources.append(label)

    return {
        "answer": parsed.get("answer", raw_text),
        "city": parsed.get("city") or city,
        "places": places,
        "sources": sources,
    }