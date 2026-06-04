import json
import re
from typing import Any, Dict, List, Optional

from app.chunker import build_all_chunks
from app.config import KNOWLEDGE_BASE_DIR
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
- places должен содержать реальные места из контекста или из списка извлечённых мест.
- Если в списке есть координаты, обязательно используй их.
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


def safe_float(value: Any) -> Optional[float]:
    try:
        if isinstance(value, (int, float)):
            return float(value)

        return float(str(value).replace(",", ".").strip())
    except Exception:
        return None


def normalize_city_name(value: Optional[str]) -> str:
    return str(value or "").strip().lower().replace("ё", "е")


def normalize_place_name(value: Optional[str]) -> str:
    return str(value or "").strip().lower().replace("ё", "е")


def normalize_place(
    place: Dict[str, Any],
    default_city: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    name = str(place.get("name") or "").strip()

    if not name:
        return None

    lat = safe_float(place.get("lat"))
    lon = safe_float(place.get("lon"))

    return {
        "name": name,
        "city": place.get("city") or default_city,
        "description": place.get("description") or "",
        "lat": lat,
        "lon": lon,
        "category": place.get("category") or "достопримечательность",
    }


def extract_description_from_block(block: str) -> str:
    description = ""

    description_match = re.search(
        r"Подходит:.*?\n\n(.+)",
        block,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if description_match:
        description = description_match.group(1).strip()
        description = re.split(
            r"\n###|\n##|\nТип:|\nКоординаты:|\nВремя на посещение:|\nПодходит:",
            description,
        )[0].strip()

    if not description:
        lines = []

        for line in block.splitlines():
            line = line.strip()

            if not line:
                continue

            lower = line.lower()

            if line.startswith("#"):
                continue

            if lower.startswith("город:"):
                continue

            if lower.startswith("раздел:"):
                continue

            if lower.startswith("тип:"):
                continue

            if lower.startswith("координаты:"):
                continue

            if lower.startswith("время"):
                continue

            if lower.startswith("подходит:"):
                continue

            lines.append(line)

        description = " ".join(lines[:2])

    return description[:350]


def extract_places_from_text(text: str, city: Optional[str]) -> List[Dict[str, Any]]:
    """
    Ищет в markdown-тексте блоки достопримечательностей с координатами.

    Поддерживает формат:

    ### Плещеево озеро
    Тип: природа
    Координаты: 56.7653, 38.7770
    """

    places: List[Dict[str, Any]] = []

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

        places.append(
            {
                "name": name,
                "city": city,
                "description": extract_description_from_block(block),
                "lat": lat,
                "lon": lon,
                "category": category,
            }
        )

    return places


def deduplicate_places(places: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    seen = set()

    for place in places:
        name = normalize_place_name(place.get("name"))
        city = normalize_city_name(place.get("city"))
        key = f"{city}|{name}"

        if not name or key in seen:
            continue

        seen.add(key)
        result.append(place)

    return result


def extract_places_from_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    places: List[Dict[str, Any]] = []

    for chunk in chunks:
        text = chunk.get("text", "")
        city = chunk.get("city")
        places.extend(extract_places_from_text(text, city))

    return deduplicate_places(places)


def extract_places_for_city_from_knowledge_base(city: Optional[str]) -> List[Dict[str, Any]]:
    """
    Важный резервный механизм.

    Если в top-k чанках оказались только "Маршрут на 1 день" или "Советы",
    там может не быть координат. Тогда мы читаем весь markdown-файл города
    и достаём все места с координатами оттуда.
    """

    if not city:
        return []

    target_city = normalize_city_name(city)

    try:
        all_chunks = build_all_chunks(KNOWLEDGE_BASE_DIR)
    except Exception:
        return []

    city_chunks = [
        chunk
        for chunk in all_chunks
        if normalize_city_name(chunk.get("city")) == target_city
    ]

    return extract_places_from_chunks(city_chunks)


def find_places_mentioned_in_answer(
    answer: str,
    available_places: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Если модель написала в answer названия мест, но не вернула places,
    выбираем из базы те места, которые упоминаются в тексте ответа.
    """

    answer_norm = normalize_place_name(answer)

    mentioned = []

    for place in available_places:
        name = place.get("name", "")
        name_norm = normalize_place_name(name)

        if name_norm and name_norm in answer_norm:
            mentioned.append(place)

    return deduplicate_places(mentioned)


def merge_places(
    model_places: List[Dict[str, Any]],
    available_places: List[Dict[str, Any]],
    answer: str,
    default_city: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Объединяет:
    1. places от модели;
    2. места, найденные в базе знаний;
    3. места, упомянутые в тексте ответа.
    """

    available_by_name = {
        normalize_place_name(place.get("name")): place
        for place in available_places
        if place.get("name")
    }

    merged: List[Dict[str, Any]] = []
    seen = set()

    for raw_place in model_places:
        normalized = normalize_place(raw_place, default_city=default_city)

        if not normalized:
            continue

        key = normalize_place_name(normalized.get("name"))
        fallback = available_by_name.get(key)

        if fallback:
            if normalized.get("lat") is None:
                normalized["lat"] = fallback.get("lat")

            if normalized.get("lon") is None:
                normalized["lon"] = fallback.get("lon")

            if not normalized.get("description"):
                normalized["description"] = fallback.get("description", "")

            if not normalized.get("category"):
                normalized["category"] = fallback.get("category", "достопримечательность")

            if not normalized.get("city"):
                normalized["city"] = fallback.get("city")

        if key and key not in seen:
            seen.add(key)
            merged.append(normalized)

    mentioned_places = find_places_mentioned_in_answer(answer, available_places)

    for place in mentioned_places:
        key = normalize_place_name(place.get("name"))

        if key and key not in seen:
            seen.add(key)
            merged.append(place)

    if not merged:
        for place in available_places:
            key = normalize_place_name(place.get("name"))

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

    places_from_context = extract_places_from_chunks(chunks)
    places_from_city_file = extract_places_for_city_from_knowledge_base(city)

    available_places = deduplicate_places(
        places_from_context + places_from_city_file
    )

    places_hint = json.dumps(available_places, ensure_ascii=False, indent=2)

    user_prompt = f"""
Контекст из базы знаний:
{context}

Доступные места с координатами из базы знаний:
{places_hint}

Запрос пользователя:
{query}

Выбранный город:
{city or "не выбран"}

Сформируй ответ строго в JSON-формате.
Обязательно верни places с координатами из списка доступных мест, если они относятся к маршруту.
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

    answer = parsed.get("answer", raw_text)

    raw_places = parsed.get("places", [])

    if not isinstance(raw_places, list):
        raw_places = []

    places = merge_places(
        model_places=raw_places,
        available_places=available_places,
        answer=answer,
        default_city=parsed.get("city") or city,
    )

    places = await enrich_places_with_photos(places)

    return {
        "answer": answer,
        "city": parsed.get("city") or city,
        "places": places,
        "sources": [],
    }