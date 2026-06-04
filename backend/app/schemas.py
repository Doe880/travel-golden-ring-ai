from typing import List, Optional

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    query: str = Field(..., min_length=2)
    city: Optional[str] = None


class Place(BaseModel):
    name: str
    city: Optional[str] = None
    description: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    category: Optional[str] = None
    photo_url: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    city: Optional[str] = None
    places: List[Place] = []
    sources: List[str] = []