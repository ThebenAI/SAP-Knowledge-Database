from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    imported_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    knowledge_items = relationship("KnowledgeItem", back_populates="source_document", cascade="all, delete-orphan")
