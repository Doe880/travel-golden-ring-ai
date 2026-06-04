import json
import re
from typing import Any, Dict, List, Optional

from app.llm_client import generate_with_routerai
from app.photos import get_place_photo_url
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
9. В поле answer можно использовать markdown: заголовки, списки, выделение.
10. Обязательно верни массив places, если в контексте есть достопримечательности с координатами.

Верни СТРОГО JSON без markdown-блоков ``` и без пояснений до или после JSON.

Формат ответа:
{
  "answer": "Основной текст ответа в markdown",
  "city": "Город или null",
  "places": [
    {
      "name": "Название места",
      "city": "Город",
      "description": "Краткое описание",
      "lat": 56.0,
      "lon": 40.0,
      "category": "достопримечательность | еда | сувенир | прогулка | музей | природа | архитектура"
    }
  ]
}

Важно:
- places должен содержать реальные места из контекста.
- Если в контексте есть строки "Координаты: 56.0000, 40.0000", обязательно используй их.
- lat и lon должны быть числами, а не строками.
- Не добавляй sources в ответ.
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


def safe_float(value: str) -> Optional[float]:
    try:
        return float(value.replace(",", ".").strip())
    except Exception:
        return None


def normalize_place(place: Dict[str, Any], default_city: Optional[str] = None) -> Optional[Dict[str, Any]]:
    name = str(place.get("name") or "").strip()

    if not name:
        return None

    lat = place.get("lat")
    lon = place.get("lon")

    if isinstance(lat, str):
        lat = safe_float(lat)

    if isinstance(lon, str):
        lon = safe_float(lon)

    normalized = {
        "name": name,
        "city": place.get("city") or default_city,
        "description": place.get("description") or "",
        "lat": lat if isinstance(lat, (int, float)) else None,
        "lon": lon if isinstance(lon, (int, float)) else None,
        "category": place.get("category") or "достопримечательность",
    }

    return normalized


def extract_places_from_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Резервный механизм.
    Если модель не вернула places, backend сам достаёт места из markdown-чанков.

    Ищет блоки вида:

    ### Ростовский кремль

    Тип: достопримечательность
    Координаты: 57.1840, 39.4160
    ...
    """

    places: List[Dict[str, Any]] = []
    seen = set()

    for chunk in chunks:
        text = chunk.get("text", "")
        city = chunk.get("city")

        blocks = re.split(r"\n(?=###\s+)", text)

        for block in blocks:
            title_match = re.search(r"###\s+(.+)", block)
            coords_match = re.search(
                r"Координаты:\s*([0-9.\-]+)\s*,\s*([0-9.\-]+)",
                block,
                flags=re.IGNORECASE,
            )

            if not title_match or not coords_match:
                continue

            name = title_match.group(1).strip()
            lat = safe_float(coords_match.group(1))
            lon = safe_float(coords_match.group(2))

            if lat is None or lon is None:
                continue

            type_match = re.search(r"Тип:\s*(.+)", block, flags=re.IGNORECASE)
            category = type_match.group(1).strip() if type_match else "достопримечательность"

            description = ""

            description_match = re.search(
                r"Подходит:.*?\n\n(.+)",
                block,
                flags=re.IGNORECASE | re.DOTALL,
            )

            if description_match:
                description = description_match.group(1).strip()
                description = re.split(r"\n###|\n##|\nТип:|\nКоординаты:", description)[0].strip()

            if not description:
                lines = [
                    line.strip()
                    for line in block.splitlines()
                    if line.strip()
                    and not line.startswith("###")
                    and not line.lower().startswith("тип:")
                    and not line.lower().startswith("координаты:")
                    and not line.lower().startswith("время")
                    and not line.lower().startswith("подходит:")
                ]
                description = " ".join(lines[:2])

            key = f"{city}|{name}".lower()

            if key in seen:
                continue

            seen.add(key)

            places.append(
                {
                    "name": name,
                    "city": city,
                    "description": description[:350],
                    "lat": lat,
                    "lon": lon,
                    "category": category,
                }
            )

    return places


def merge_places(
    model_places: List[Dict[str, Any]],
    fallback_places: List[Dict[str, Any]],
    default_city: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Объединяет places от модели и places, извлечённые из базы.
    Если модель вернула место без координат, пытаемся дополнить координатами из fallback.
    """

    fallback_by_name = {
        str(place.get("name", "")).strip().lower(): place
        for place in fallback_places
        if place.get("name")
    }

    merged: List[Dict[str, Any]] = []
    seen = set()

    for raw_place in model_places:
        normalized = normalize_place(raw_place, default_city=default_city)

        if not normalized:
            continue

        key = normalized["name"].lower()
        fallback = fallback_by_name.get(key)

        if fallback:
            if normalized.get("lat") is None:
                normalized["lat"] = fallback.get("lat")
            if normalized.get("lon") is None:
                normalized["lon"] = fallback.get("lon")
            if not normalized.get("description"):
                normalized["description"] = fallback.get("description", "")
            if not normalized.get("category"):
                normalized["category"] = fallback.get("category", "достопримечательность")

        if key not in seen:
            seen.add(key)
            merged.append(normalized)

    if not merged:
        for place in fallback_places:
            key = str(place.get("name", "")).lower()

            if key and key not in seen:
                seen.add(key)
                merged.append(place)

    return merged[:8]


async def enrich_places_with_photos(places: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched = []

    for place in places:
        name = place.get("name")
        city = place.get("city")

        if name and not place.get("photo_url"):
            place["photo_url"] = await get_place_photo_url(name=name, city=city)

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
    fallback_places = extract_places_from_chunks(chunks)

    places_hint = json.dumps(fallback_places, ensure_ascii=False, indent=2)

    user_prompt = f"""
Контекст из базы знаний:
{context}

Извлечённые из базы места с координатами:
{places_hint}

Запрос пользователя:
{query}

Выбранный город:
{city or "не выбран"}

Сформируй ответ строго в JSON-формате.
Обязательно верни places с координатами, если они есть в списке извлечённых мест.
Не возвращай sources.
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

    raw_places = parsed.get("places", [])

    if not isinstance(raw_places, list):
        raw_places = []

    places = merge_places(
        model_places=raw_places,
        fallback_places=fallback_places,
        default_city=parsed.get("city") or city,
    )

    places = await enrich_places_with_photos(places)

    return {
        "answer": parsed.get("answer", raw_text),
        "city": parsed.get("city") or city,
        "places": places,
        "sources": [],
    }