from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.knowledge_item import KnowledgeItem, KnowledgeItemType, VerificationStatus
from app.schemas.knowledge_item import KnowledgeItemBackfillResult, KnowledgeItemCleanupResult, KnowledgeItemRead
from app.schemas.review import KnowledgeItemMetadataUpdateRequest, ReviewActionRequest
from app.services.knowledge_item_backfill_service import backfill_sap_modules
from app.services.knowledge_item_cleanup_service import cleanup_rejected_knowledge_items

router = APIRouter(prefix="/knowledge-items", tags=["knowledge-items"])


def _to_read_model(item: KnowledgeItem) -> KnowledgeItemRead:
    return KnowledgeItemRead(
        id=item.id,
        item_type=item.item_type,
        title=item.title,
        content=item.content,
        source_document_id=item.source_document_id,
        document_code=item.source_document.document_code if item.source_document else None,
        source_ref=item.source_ref,
        confidence=item.confidence,
        extracted_data=item.extracted_data,
        verification_status=item.verification_status,
        verified_by=item.verified_by,
        verified_at=item.verified_at,
        review_comment=item.review_comment,
        links_note=item.links_note,
        sap_module=item.sap_module,
        sap_module_source=item.sap_module_source,
        created_at=item.created_at,
    )


@router.get("", response_model=list[KnowledgeItemRead])
def list_knowledge_items(
    verification_status: VerificationStatus | None = None,
    item_type: KnowledgeItemType | None = None,
    document_id: int | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
) -> list[KnowledgeItemRead]:
    query = db.query(KnowledgeItem)
    if verification_status is not None:
        query = query.filter(KnowledgeItem.verification_status == verification_status)
    if item_type is not None:
        query = query.filter(KnowledgeItem.item_type == item_type)
    if document_id is not None:
        query = query.filter(KnowledgeItem.source_document_id == document_id)
    if q is not None and q.strip():
        search = f"%{q.strip()}%"
        query = query.filter(
            or_(
                KnowledgeItem.title.ilike(search),
                KnowledgeItem.content.ilike(search),
                KnowledgeItem.source_ref.ilike(search),
            )
        )
    return [_to_read_model(item) for item in query.order_by(KnowledgeItem.created_at.desc()).all()]


@router.get("/{item_id}", response_model=KnowledgeItemRead)
def get_knowledge_item(item_id: int, db: Session = Depends(get_db)) -> KnowledgeItemRead:
    item = db.query(KnowledgeItem).filter(KnowledgeItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found.")
    return _to_read_model(item)


def _update_review_status(
    db: Session,
    item_id: int,
    status: VerificationStatus,
    verified_by: str | None,
    review_comment: str | None,
    sap_module: str | None = None,
    links_note: str | None = None,
    source_table: str | None = None,
    target_table: str | None = None,
    join_field: str | None = None,
) -> KnowledgeItem:
    item = db.query(KnowledgeItem).filter(KnowledgeItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found.")

    item.verification_status = status
    item.verified_by = verified_by
    item.review_comment = review_comment
    if links_note is not None:
        item.links_note = links_note.strip() or None
    if sap_module is not None:
        normalized_module = sap_module.strip()
        item.sap_module = normalized_module or None
        item.sap_module_source = "manual" if normalized_module else None
    if source_table is not None or target_table is not None or join_field is not None:
        extracted = dict(item.extracted_data or {})
        if source_table is not None:
            normalized_source = source_table.strip()
            extracted["source_table"] = normalized_source or None
        if target_table is not None:
            normalized_target = target_table.strip()
            extracted["target_table"] = normalized_target or None
        if join_field is not None:
            normalized_join = join_field.strip()
            extracted["join_field"] = normalized_join or None
        item.extracted_data = extracted
    item.verified_at = datetime.now(timezone.utc)

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/verify", response_model=KnowledgeItemRead)
def verify_knowledge_item(
    item_id: int,
    payload: ReviewActionRequest,
    db: Session = Depends(get_db),
) -> KnowledgeItemRead:
    updated = _update_review_status(
        db,
        item_id,
        VerificationStatus.verified,
        payload.reviewer,
        payload.comment,
        payload.sap_module,
        payload.links_note,
        payload.source_table,
        payload.target_table,
        payload.join_field,
    )
    return _to_read_model(updated)


@router.post("/{item_id}/reject", response_model=KnowledgeItemRead)
def reject_knowledge_item(
    item_id: int,
    payload: ReviewActionRequest,
    db: Session = Depends(get_db),
) -> KnowledgeItemRead:
    updated = _update_review_status(
        db,
        item_id,
        VerificationStatus.rejected,
        payload.reviewer,
        payload.comment,
        payload.sap_module,
        payload.links_note,
        payload.source_table,
        payload.target_table,
        payload.join_field,
    )
    return _to_read_model(updated)


@router.post("/{item_id}/needs-revision", response_model=KnowledgeItemRead)
def mark_needs_revision(
    item_id: int,
    payload: ReviewActionRequest,
    db: Session = Depends(get_db),
) -> KnowledgeItemRead:
    updated = _update_review_status(
        db,
        item_id,
        VerificationStatus.needs_revision,
        payload.reviewer,
        payload.comment,
        payload.sap_module,
        payload.links_note,
        payload.source_table,
        payload.target_table,
        payload.join_field,
    )
    return _to_read_model(updated)


@router.post("/{item_id}/update-metadata", response_model=KnowledgeItemRead)
def update_knowledge_item_metadata(
    item_id: int,
    payload: KnowledgeItemMetadataUpdateRequest,
    db: Session = Depends(get_db),
) -> KnowledgeItemRead:
    item = db.query(KnowledgeItem).filter(KnowledgeItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found.")

    normalized_module = payload.sap_module.strip() if payload.sap_module is not None else ""
    item.sap_module = normalized_module or None
    item.sap_module_source = "manual" if normalized_module else None
    item.review_comment = payload.comment
    item.links_note = payload.links_note.strip() if payload.links_note is not None and payload.links_note.strip() else None
    if payload.source_table is not None or payload.target_table is not None or payload.join_field is not None:
        extracted = dict(item.extracted_data or {})
        if payload.source_table is not None:
            normalized_source = payload.source_table.strip()
            extracted["source_table"] = normalized_source or None
        if payload.target_table is not None:
            normalized_target = payload.target_table.strip()
            extracted["target_table"] = normalized_target or None
        if payload.join_field is not None:
            normalized_join = payload.join_field.strip()
            extracted["join_field"] = normalized_join or None
        item.extracted_data = extracted
    item.verified_by = payload.reviewer
    item.verified_at = datetime.now(timezone.utc)

    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_read_model(item)


@router.post("/cleanup-rejected", response_model=KnowledgeItemCleanupResult)
def cleanup_rejected_items(db: Session = Depends(get_db)) -> KnowledgeItemCleanupResult:
    deleted_count = cleanup_rejected_knowledge_items(db)
    return KnowledgeItemCleanupResult(deleted_count=deleted_count)


@router.post("/backfill-sap-modules", response_model=KnowledgeItemBackfillResult)
def backfill_sap_module_values(db: Session = Depends(get_db)) -> KnowledgeItemBackfillResult:
    updated_count, skipped_count, local_updated, web_updated = backfill_sap_modules(db)
    return KnowledgeItemBackfillResult(
        updated_count=updated_count,
        skipped_count=skipped_count,
        local_updated=local_updated,
        web_updated=web_updated,
    )
