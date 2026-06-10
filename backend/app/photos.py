from typing import Dict, Optional
from urllib.parse import quote

import httpx


COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
RU_WIKI_API_URL = "https://ru.wikipedia.org/w/api.php"


PLACE_PHOTO_FALLBACKS: Dict[str, str] = {
    # Суздаль
    "суздальский кремль": "https://commons.wikimedia.org/wiki/Special:FilePath/Suzdal%20Kremlin%202012.jpg",
    "музей деревянного зодчества": "https://commons.wikimedia.org/wiki/Special:FilePath/Suzdal%20Museum%20of%20Wooden%20Architecture%202012.jpg",
    "спасо-евфимиев монастырь": "https://commons.wikimedia.org/wiki/Special:FilePath/Spaso-Evfimiev%20Monastery%20Suzdal.jpg",
    "торговая площадь": "https://commons.wikimedia.org/wiki/Special:FilePath/Suzdal%20Trading%20Rows.jpg",

    # Переславль-Залесский
    "плещеево озеро": "https://commons.wikimedia.org/wiki/Special:FilePath/Lake%20Pleshcheyevo.jpg",
    "спасо-преображенский собор": "https://commons.wikimedia.org/wiki/Special:FilePath/Pereslavl-Zalessky%20Transfiguration%20Cathedral.jpg",
    "синий камень": "https://commons.wikimedia.org/wiki/Special:FilePath/Blue%20Stone%20Pereslavl.jpg",

    # Ростов Великий
    "ростовский кремль": "https://commons.wikimedia.org/wiki/Special:FilePath/Rostov%20Kremlin%202012.jpg",
    "озеро неро": "https://commons.wikimedia.org/wiki/Special:FilePath/Lake%20Nero%20Rostov.jpg",

    # Ярославль
    "стрелка": "https://commons.wikimedia.org/wiki/Special:FilePath/Yaroslavl%20Strelka.jpg",
    "церковь ильи пророка": "https://commons.wikimedia.org/wiki/Special:FilePath/Church%20of%20Elijah%20the%20Prophet%20Yaroslavl.jpg",
    "спасо-преображенский монастырь": "https://commons.wikimedia.org/wiki/Special:FilePath/Yaroslavl%20Spaso-Preobrazhensky%20Monastery.jpg",

    # Кострома
    "ипатьевский монастырь": "https://commons.wikimedia.org/wiki/Special:FilePath/Ipatiev%20Monastery%20Kostroma.jpg",
    "сусанинская площадь": "https://commons.wikimedia.org/wiki/Special:FilePath/Susaninskaya%20Square%20Kostroma.jpg",

    # Владимир
    "золотые ворота": "https://commons.wikimedia.org/wiki/Special:FilePath/Golden%20Gate%20Vladimir.jpg",
    "успенский собор": "https://commons.wikimedia.org/wiki/Special:FilePath/Dormition%20Cathedral%20Vladimir.jpg",
    "дмитриевский собор": "https://commons.wikimedia.org/wiki/Special:FilePath/Demetrius%20Cathedral%20Vladimir.jpg",
}


def normalize_key(value: Optional[str]) -> str:
    return str(value or "").strip().lower().replace("ё", "е")


def find_fallback_photo(name: str) -> Optional[str]:
    key = normalize_key(name)

    if key in PLACE_PHOTO_FALLBACKS:
        return PLACE_PHOTO_FALLBACKS[key]

    for place_name, url in PLACE_PHOTO_FALLBACKS.items():
        if place_name in key or key in place_name:
            return url

    return None


async def get_wikipedia_photo_url(query: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            search_response = await client.get(
                RU_WIKI_API_URL,
                params={
                    "action": "query",
                    "format": "json",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": 1,
                    "origin": "*",
                },
            )

            search_response.raise_for_status()
            search_data = search_response.json()

            search_results = search_data.get("query", {}).get("search", [])

            if not search_results:
                return None

            page_id = search_results[0].get("pageid")

            if not page_id:
                return None

            image_response = await client.get(
                RU_WIKI_API_URL,
                params={
                    "action": "query",
                    "format": "json",
                    "pageids": page_id,
                    "prop": "pageimages",
                    "pithumbsize": 800,
                    "origin": "*",
                },
            )

            image_response.raise_for_status()
            image_data = image_response.json()

            page = image_data.get("query", {}).get("pages", {}).get(str(page_id), {})
            thumbnail = page.get("thumbnail", {})

            return thumbnail.get("source")

    except Exception:
        return None


async def get_commons_photo_url(query: str) -> Optional[str]:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",
        "gsrlimit": "1",
        "prop": "imageinfo",
        "iiprop": "url",
        "origin": "*",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(COMMONS_API_URL, params=params)
            response.raise_for_status()
            data = response.json()

        pages = data.get("query", {}).get("pages", {})

        for page in pages.values():
            imageinfo = page.get("imageinfo", [])

            if imageinfo:
                return imageinfo[0].get("url")

    except Exception:
        return None

    return None


async def get_place_photo_url(name: str, city: Optional[str] = None) -> Optional[str]:
    fallback_url = find_fallback_photo(name)

    if fallback_url:
        return fallback_url

    queries = []

    if city:
        queries.append(f"{name} {city}")
        queries.append(f"{name} {city} Россия")

    queries.append(name)

    for query in queries:
        photo_url = await get_wikipedia_photo_url(query)

        if photo_url:
            return photo_url

    for query in queries:
        photo_url = await get_commons_photo_url(query)

        if photo_url:
            return photo_url

    return None


def build_wikipedia_search_url(query: str) -> str:
    encoded = quote(query)
    return f"https://ru.wikipedia.org/wiki/Special:Search?search={encoded}"