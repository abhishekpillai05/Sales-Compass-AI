from typing import Optional

from pydantic import BaseModel


class SourceResponse(BaseModel):
    chunk_id: Optional[str] = None
    document_id: Optional[int | str] = None
    sku: Optional[str] = None
    filename: Optional[str] = None


class AskResponse(BaseModel):
    query: str
    answer: str
    sources: list[SourceResponse]