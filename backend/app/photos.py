from typing import Optional
from urllib.parse import quote

import httpx


COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"


async def get_commons_photo_url(query: str) -> Optional[str]:
    """
    Ищет фото в Wikimedia Commons.
    Для MVP берём первое найденное изображение.
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


def build_wikipedia_search_url(query: str) -> str:
    encoded = quote(query)
    return f"https://ru.wikipedia.org/wiki/Special:Search?search={encoded}"