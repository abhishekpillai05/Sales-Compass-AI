from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SourceResponse(BaseModel):
    chunk_id: Optional[str] = None
    document_id: Optional[int | str] = None
    sku: Optional[str] = None
    filename: Optional[str] = None


class SalesStateResponse(BaseModel):
    stage: str = Field(description="Current stage: DISCOVERY, PRODUCT_MATCHING, DEAL_DISCUSSION, DEAL_FINALIZED, POST_SALE")
    product_category: Optional[str] = None
    extracted_requirements: Dict[str, Any] = Field(default_factory=dict)
    candidate_products: List[Dict[str, Any]] = Field(default_factory=list)
    selected_product: Optional[Dict[str, Any]] = None
    agreed_quantity: Optional[int] = None
    agreed_price: Optional[str] = None
    deal_status: str = Field(description="OPEN, PROPOSED, FINALIZED, CANCELLED")
    deal_finalized_at: Optional[datetime] = None
    can_recommend_addons: bool = False
    recommendations: Optional[Dict[str, Any]] = None


class AskResponse(BaseModel):
    query: str
    answer: str
    conversation_id: int
    sources: List[SourceResponse]
    sales_state: Optional[SalesStateResponse] = None
    suggested_questions: Optional[List[str]] = None