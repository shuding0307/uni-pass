from datetime import date
from typing import Optional
from pydantic import BaseModel


class RegulationCreate(BaseModel):
    title: str
    content: str
    major: Optional[str] = None
    source_tag: Optional[str] = None
    effective_date: date


class RegulationResponse(BaseModel):
    id: str
    title: str
    content: str
    major: Optional[str] = None
    source_tag: Optional[str] = None
    effective_date: date
    is_active: bool
