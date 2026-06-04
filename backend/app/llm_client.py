import json
from typing import Any, Dict, List, Optional

import httpx

from app.config import (
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    ROUTERAI_API_KEY,
    ROUTERAI_CHAT_MODEL,
    ROUTERAI_CHAT_URL,
)


class RouterAIError(Exception):
    pass


def get_routerai_headers() -> Dict[str, str]:
    if not ROUTERAI_API_KEY:
        raise RuntimeError("Не найден ROUTERAI_API_KEY. Проверь backend/.env")

    return {
        "Authorization": f"Bearer {ROUTERAI_API_KEY}",
        "Content-Type": "application/json",
    }


async def generate_with_routerai(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    response_format: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Генерация ответа через RouterAI.

    RouterAI совместим с OpenAI-style chat completions:
    POST https://routerai.ru/api/v1/chat/completions
    """

    payload: Dict[str, Any] = {
        "model": model or ROUTERAI_CHAT_MODEL,
        "messages": messages,
        "temperature": temperature if temperature is not None else LLM_TEMPERATURE,
        "max_tokens": max_tokens if max_tokens is not None else LLM_MAX_TOKENS,
    }

    if response_format:
        payload["response_format"] = response_format

    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            ROUTERAI_CHAT_URL,
            headers=get_routerai_headers(),
            json=payload,
        )

    if response.status_code >= 400:
        raise RouterAIError(
            f"RouterAI chat error {response.status_code}: {response.text}"
        )

    data = response.json()

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RouterAIError(
            "Неожиданный формат ответа RouterAI chat: "
            f"{json.dumps(data, ensure_ascii=False)}"
        ) from e