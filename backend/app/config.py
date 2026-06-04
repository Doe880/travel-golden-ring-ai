import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


# =========================
# RouterAI
# =========================

ROUTERAI_API_KEY = os.getenv("ROUTERAI_API_KEY", "")

ROUTERAI_CHAT_MODEL = os.getenv(
    "ROUTERAI_CHAT_MODEL",
    "deepseek/deepseek-v4-pro",
)

ROUTERAI_CHAT_URL = os.getenv(
    "ROUTERAI_CHAT_URL",
    "https://routerai.ru/api/v1/chat/completions",
)


# =========================
# Generation settings
# =========================

LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.4"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1800"))


# =========================
# Local embeddings
# =========================

EMBEDDING_PROVIDER = os.getenv(
    "EMBEDDING_PROVIDER",
    "local",
)

LOCAL_EMBEDDING_MODEL = os.getenv(
    "LOCAL_EMBEDDING_MODEL",
    "intfloat/multilingual-e5-small",
)


# =========================
# CORS
# Для связи frontend GitHub Pages → backend Render
# =========================

ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "*")

if ALLOWED_ORIGINS_RAW.strip() == "*":
    ALLOWED_ORIGINS = ["*"]
else:
    ALLOWED_ORIGINS = [
        origin.strip()
        for origin in ALLOWED_ORIGINS_RAW.split(",")
        if origin.strip()
    ]


# =========================
# RAG settings
# =========================

TOP_K = int(os.getenv("TOP_K", "6"))

KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
VECTOR_INDEX_PATH = BASE_DIR / "vector_index" / "index.json"