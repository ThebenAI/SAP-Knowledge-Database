from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.knowledge_item import KnowledgeItemType, VerificationStatus


class KnowledgeItemRead(BaseModel):
    id: int
    item_type: KnowledgeItemType
    title: str
    content: str
    source_document_id: int
    document_code: str | None = None
    source_ref: str
    confidence: float | None
    extracted_data: dict[str, Any]
    verification_status: VerificationStatus
    verified_by: str | None
    verified_at: datetime | None
    review_comment: str | None
    links_note: str | None
    sap_module: str | None
    sap_module_source: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeItemCleanupResult(BaseModel):
    deleted_count: int


class KnowledgeItemBackfillResult(BaseModel):
    updated_count: int
    skipped_count: int
    local_updated: int = 0
    web_updated: int = 0
