from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS
from app.rag import ask_travel_agent
from app.schemas import AskRequest, AskResponse
from app.vector_store import vector_store


app = FastAPI(
    title="Golden Ring Travel AI",
    description="AI-помощник по маршрутам Золотого кольца России",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Golden Ring Travel AI backend is running",
        "chunks_loaded": len(vector_store.items),
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "chunks_loaded": len(vector_store.items),
    }

@app.get("/debug/cors")
def debug_cors():
    return {
        "allowed_origins": ALLOWED_ORIGINS,
    }


@app.get("/cities")
def cities():
    return {
        "cities": [
            "Сергиев Посад",
            "Переславль-Залесский",
            "Ростов Великий",
            "Ярославль",
            "Кострома",
            "Иваново",
            "Суздаль",
            "Владимир",
        ]
    }


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    try:
        result = await ask_travel_agent(
            query=request.query,
            city=request.city,
        )

        return result

    except Exception as e:
        error_text = str(e).lower()

        if "routerai chat error" in error_text:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Ошибка при обращении к RouterAI. "
                    f"Подробности: {str(e)}"
                ),
            )

        raise HTTPException(
            status_code=500,
            detail=f"Ошибка AI-ассистента: {str(e)}",
        )