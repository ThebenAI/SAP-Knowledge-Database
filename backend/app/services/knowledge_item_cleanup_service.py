from sqlalchemy.orm import Session

from app.models.knowledge_item import KnowledgeItem, VerificationStatus


def cleanup_rejected_knowledge_items(db: Session) -> int:
    deleted_count = (
        db.query(KnowledgeItem).filter(KnowledgeItem.verification_status == VerificationStatus.rejected).delete()
    )
    db.commit()
    return deleted_count
