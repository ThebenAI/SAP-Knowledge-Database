import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class VerificationStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    rejected = "rejected"
    needs_revision = "needs_revision"


class KnowledgeItemType(str, enum.Enum):
    table_mention = "table_mention"
    field_mention = "field_mention"
    relationship_hint = "relationship_hint"


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_knowledge_items_dedupe_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    item_type: Mapped[KnowledgeItemType] = mapped_column(
        Enum(KnowledgeItemType, name="knowledge_item_type_enum"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)
    sap_module: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    sap_module_source: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    extracted_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status_enum"),
        nullable=False,
        default=VerificationStatus.pending,
        server_default=VerificationStatus.pending.value,
        index=True,
    )
    verified_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    links_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    source_document = relationship("Document", back_populates="knowledge_items")
