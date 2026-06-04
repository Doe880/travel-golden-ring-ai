from typing import Optional
from urllib.parse import quote

import httpx


COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
RU_WIKI_API_URL = "https://ru.wikipedia.org/w/api.php"


async def get_wikipedia_photo_url(query: str) -> Optional[str]:
    """
    Ищет картинку через русскую Wikipedia:
    1. search;
    2. pageimages.
    """

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
    """
    Ищет фото в Wikimedia Commons.
    """

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
    """
    Основная функция получения фото места.
    Сначала ищем в русской Wikipedia, потом в Wikimedia Commons.
    """

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