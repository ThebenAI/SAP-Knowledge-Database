from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.knowledge_item import KnowledgeItem, KnowledgeItemType
from app.services.sap_module_inference_service import infer_sap_module_with_reason


def _extract_table_name_for_inference(item: KnowledgeItem) -> str | None:
    if item.item_type == KnowledgeItemType.table_mention:
        table_name = item.extracted_data.get("table_name")
        return table_name if isinstance(table_name, str) else None

    if item.item_type == KnowledgeItemType.field_mention:
        field_name = item.extracted_data.get("field_name")
        if isinstance(field_name, str) and "-" in field_name:
            return field_name.split("-", maxsplit=1)[0]
        return None

    if item.item_type == KnowledgeItemType.relationship_hint:
        source_table = item.extracted_data.get("source_table")
        target_table = item.extracted_data.get("target_table")
        if isinstance(source_table, str) and source_table.strip():
            return source_table
        if isinstance(target_table, str) and target_table.strip():
            return target_table
        return None

    return None


def backfill_sap_modules(db: Session) -> tuple[int, int, int, int]:
    candidate_items = (
        db.query(KnowledgeItem)
        .filter(
            KnowledgeItem.item_type.in_(
                [
                    KnowledgeItemType.table_mention,
                    KnowledgeItemType.field_mention,
                    KnowledgeItemType.relationship_hint,
                ]
            ),
            or_(KnowledgeItem.sap_module.is_(None), KnowledgeItem.sap_module == ""),
        )
        .all()
    )

    updated_count = 0
    skipped_count = 0
    local_updated = 0
    web_updated = 0
    run_lookup_cache: dict[str, tuple[str | None, str | None]] = {}

    for item in candidate_items:
        # Manual reviewer values are always protected.
        if item.sap_module_source == "manual":
            skipped_count += 1
            continue

        table_name = _extract_table_name_for_inference(item)
        extracted_data = item.extracted_data if isinstance(item.extracted_data, dict) else {}
        module, source, module_confidence, module_reason = infer_sap_module_with_reason(
            table_name,
            item_type=item.item_type.value,
            content=item.content,
            extracted_data=extracted_data,
            allow_web_lookup=True,
            db=db,
            run_cache=run_lookup_cache,
        )
        if not module or not source:
            skipped_count += 1
            continue

        item.sap_module = module
        item.sap_module_source = source
        if isinstance(item.extracted_data, dict):
            updated_data = dict(item.extracted_data)
            if module_reason:
                updated_data["module_inference_reason"] = module_reason
            updated_data["module_inference_confidence"] = module_confidence
            item.extracted_data = updated_data
        db.add(item)
        updated_count += 1
        if source == "local":
            local_updated += 1
        elif source == "web":
            web_updated += 1

    db.commit()

    return updated_count, skipped_count, local_updated, web_updated
