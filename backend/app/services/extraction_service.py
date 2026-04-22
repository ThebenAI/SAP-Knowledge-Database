import re
import traceback
from hashlib import sha256
from json import dumps
import os

from sqlalchemy.orm import Session

from app.models.knowledge_item import KnowledgeItem, KnowledgeItemType, VerificationStatus
from app.parsers.base import CandidateItem
from app.services.sap_module_inference_service import infer_sap_module_with_reason

SAP_TABLE_PATTERN = re.compile(r"\b([A-Z][A-Z0-9_]{2,})\b")
SAP_FIELD_PATTERN = re.compile(r"\b([A-Z][A-Z0-9_]{2,}-[A-Z][A-Z0-9_]{1,})\b")
RELATIONSHIP_PATTERN = re.compile(
    r"\b(join|joins|joined|linked\s+to|mapped\s+to|reference|references|related\s+to)\b",
    re.IGNORECASE,
)
FRAGMENT_PATTERN = re.compile(r"^fragment_\d{3}$")
KNOWN_RELATIONSHIPS: dict[frozenset[str], str] = {
    frozenset(("EKKO", "EKPO")): "EBELN",
    frozenset(("VBAK", "VBAP")): "VBELN",
    frozenset(("MARA", "MARC")): "MATNR",
    frozenset(("BKPF", "BSEG")): "BELNR",
    frozenset(("MKPF", "MSEG")): "MBLNR",
    frozenset(("EKKO", "LFA1")): "LIFNR",
    frozenset(("VBAK", "KNA1")): "KUNNR",
    frozenset(("MARA", "MARD")): "MATNR",
    frozenset(("MARC", "MARD")): "MATNR",
}
RELATIONSHIP_DEBUG = os.getenv("SAP_RELATIONSHIP_DEBUG", "").lower() in {"1", "true", "yes", "on"}
STRUCTURED_TABLE_NAME_HEADERS = {
    "table",
    "table name",
    "sap table",
    "sap table name",
    "table_name",
    "tablename",
}
STRUCTURED_FIELD_HEADERS = {
    "field",
    "fields",
    "field name",
    "field names",
    "sap field",
    "sap fields",
    "key field",
    "key fields",
    "important field",
    "important fields",
}


def _estimate_confidence(item_type: KnowledgeItemType) -> float:
    if item_type == KnowledgeItemType.table_mention:
        return 0.75
    if item_type == KnowledgeItemType.field_mention:
        return 0.8
    if item_type == KnowledgeItemType.relationship_hint:
        return 0.65
    return 0.5


def _relationship_confidence(
    *,
    has_known_mapping: bool,
    has_shared_field: bool,
    has_explicit_wording: bool,
    table_count: int,
) -> float:
    if has_known_mapping and has_shared_field:
        confidence = 0.92
    elif has_shared_field:
        confidence = 0.76
    elif has_known_mapping and has_explicit_wording:
        confidence = 0.61
    else:
        confidence = 0.5
    if table_count > 2:
        confidence += 0.02
    return round(min(confidence, 0.95), 2)


def _build_item(
    source_document_id: int,
    item_type: KnowledgeItemType,
    title: str,
    content: str,
    source_ref: str,
    extracted_data: dict,
    dedupe_key: str,
    sap_module: str | None = None,
    sap_module_source: str | None = None,
    confidence_override: float | None = None,
) -> KnowledgeItem:
    return KnowledgeItem(
        item_type=item_type,
        title=title,
        content=content,
        source_document_id=source_document_id,
        source_ref=source_ref,
        dedupe_key=dedupe_key,
        sap_module=sap_module,
        sap_module_source=sap_module_source,
        confidence=round(confidence_override, 2) if confidence_override is not None else round(_estimate_confidence(item_type), 2),
        extracted_data=extracted_data,
        verification_status=VerificationStatus.pending,
    )


def _normalized_table_statement(table_name: str) -> str:
    return f"Table mention {table_name} detected"


def _normalized_field_statement(field_name: str) -> str:
    return f"Field reference {field_name} detected"


def _normalized_relationship_statement(table_mentions: list[str], join_field: str | None) -> str:
    if len(table_mentions) >= 2:
        left, right = table_mentions[0], table_mentions[1]
        if join_field:
            return f"Relationship between {left} and {right} via {join_field} detected"
        return f"Relationship between {left} and {right} detected"
    if len(table_mentions) == 1:
        return f"Relationship hint involving {table_mentions[0]} detected"
    return "Potential relationship between SAP entities detected"


def _extract_join_field(field_mentions: list[str]) -> str | None:
    if not field_mentions:
        return None
    first = field_mentions[0]
    parts = first.split("-", maxsplit=1)
    if len(parts) != 2:
        return None
    return parts[1]


def _parse_field_mentions(field_mentions: list[str]) -> dict[str, set[str]]:
    table_to_fields: dict[str, set[str]] = {}
    for mention in field_mentions:
        parts = mention.split("-", maxsplit=1)
        if len(parts) != 2:
            continue
        table_name = parts[0].strip().upper()
        field_name = parts[1].strip().upper()
        if not table_name or not field_name:
            continue
        table_to_fields.setdefault(table_name, set()).add(field_name)
    return table_to_fields


def _best_relationship_candidate(
    table_mentions: list[str], field_mentions: list[str], has_explicit_wording: bool
) -> tuple[str | None, str | None, str | None, bool, bool] | None:
    if len(table_mentions) < 2:
        return None

    field_map = _parse_field_mentions(field_mentions)
    unique_tables = [t.strip().upper() for t in table_mentions if t.strip()]
    best: tuple[float, str, str, str | None, bool, bool] | None = None

    for idx in range(len(unique_tables)):
        for jdx in range(idx + 1, len(unique_tables)):
            left = unique_tables[idx]
            right = unique_tables[jdx]
            if left == right:
                continue

            known_join = KNOWN_RELATIONSHIPS.get(frozenset((left, right)))
            left_fields = field_map.get(left, set())
            right_fields = field_map.get(right, set())
            shared_fields = sorted(left_fields.intersection(right_fields))
            shared_join = shared_fields[0] if shared_fields else None

            chosen_join = shared_join or known_join
            has_known_mapping = known_join is not None
            has_shared_field = shared_join is not None
            has_known_mapping_support = bool(
                has_known_mapping and (has_explicit_wording or known_join in left_fields or known_join in right_fields)
            )
            # Tight gate:
            # - shared field is strongest signal
            # - known mapping must have supporting evidence
            # - explicit wording alone is not enough
            strong_enough = has_shared_field or has_known_mapping_support
            if not strong_enough:
                if RELATIONSHIP_DEBUG:
                    print(
                        f"DEBUG: relationship skipped pair={left}-{right} reason=weak_evidence "
                        f"known={has_known_mapping} shared={has_shared_field} explicit={has_explicit_wording}",
                        flush=True,
                    )
                continue

            score = 0.0
            if has_shared_field:
                score += 3
            if has_known_mapping:
                score += 2
            if has_known_mapping_support:
                score += 1
            score += 0.1 if chosen_join else 0

            if best is None or score > best[0]:
                best = (score, left, right, chosen_join, has_known_mapping, has_shared_field)
                if RELATIONSHIP_DEBUG:
                    print(
                        f"DEBUG: relationship candidate pair={left}-{right} join={chosen_join} "
                        f"known={has_known_mapping} shared={has_shared_field} supported={has_known_mapping_support} score={score}",
                        flush=True,
                    )

    if best is None:
        return None
    _, left, right, join_field, has_known_mapping, has_shared_field = best
    return left, right, join_field, has_known_mapping, has_shared_field


def _normalize_key_part(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().upper()


def _merge_context_extracted_data(base: dict, extra: dict) -> dict:
    merged = dict(base)
    for key, value in extra.items():
        merged[key] = value
    return merged


def _normalize_header_key(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().lower()
    normalized = normalized.replace("_", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _structured_row_values(extracted_data: dict) -> dict[str, str]:
    table_ctx = extracted_data.get("table_context")
    if not isinstance(table_ctx, dict):
        return {}
    if not table_ctx.get("is_structured_table"):
        return {}
    row_values = table_ctx.get("row_values")
    if not isinstance(row_values, dict):
        return {}
    result: dict[str, str] = {}
    for key, value in row_values.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        header = _normalize_header_key(key)
        text = value.strip()
        if not header or not text:
            continue
        result[header] = text
    return result


def _extract_structured_table_mentions(extracted_data: dict) -> list[str]:
    row_values = _structured_row_values(extracted_data)
    if not row_values:
        return []
    mentions: set[str] = set()
    for header, value in row_values.items():
        if header not in STRUCTURED_TABLE_NAME_HEADERS:
            continue
        for token in SAP_TABLE_PATTERN.findall(value):
            if len(token) > 2:
                mentions.add(token)
    return sorted(mentions)


def _extract_structured_field_mentions(extracted_data: dict, table_mentions: list[str]) -> list[str]:
    row_values = _structured_row_values(extracted_data)
    if not row_values:
        return []
    inferred_table = table_mentions[0] if table_mentions else None
    mentions: set[str] = set()
    for header, value in row_values.items():
        if header not in STRUCTURED_FIELD_HEADERS:
            continue
        # Keep standard TABLE-FIELD patterns if already present.
        for composed in SAP_FIELD_PATTERN.findall(value):
            mentions.add(composed)
        # Convert plain technical field names from field columns into field mentions.
        for token in SAP_TABLE_PATTERN.findall(value):
            if token in table_mentions:
                continue
            if inferred_table:
                mentions.add(f"{inferred_table}-{token}")
            else:
                mentions.add(token)
    return sorted(mentions)


def _candidate_table_mentions(text: str, extracted_data: dict) -> list[str]:
    structured = _structured_row_values(extracted_data)
    if structured:
        # Safeguard: for structured tables, only dedicated table columns may produce table mentions.
        return _extract_structured_table_mentions(extracted_data)
    return sorted(set(SAP_TABLE_PATTERN.findall(text)))


def _candidate_field_mentions(text: str, extracted_data: dict, table_mentions: list[str]) -> list[str]:
    mentions: set[str] = set(SAP_FIELD_PATTERN.findall(text))
    for mention in _extract_structured_field_mentions(extracted_data, table_mentions):
        mentions.add(mention)
    return sorted(mentions)


def _module_confidence_from_extracted_data(extracted_data: dict) -> float | None:
    value = extracted_data.get("module_inference_confidence")
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    return None


def _module_source_rank(source: str | None) -> int:
    if source == "manual":
        return 5
    if source == "document_context":
        return 4
    if source == "semantic_context":
        return 3
    if source == "local":
        return 2
    if source == "web":
        return 1
    return 0


def _should_try_duplicate_enrichment(existing_item: KnowledgeItem) -> bool:
    if existing_item.sap_module_source == "manual":
        return False
    if not (existing_item.sap_module or "").strip():
        return True
    if _module_source_rank(existing_item.sap_module_source) <= 3:
        return True
    existing_data = existing_item.extracted_data if isinstance(existing_item.extracted_data, dict) else {}
    existing_conf = _module_confidence_from_extracted_data(existing_data)
    return existing_conf is None or existing_conf < 0.68


def _is_new_module_inference_stronger(
    *,
    existing_item: KnowledgeItem,
    new_module: str | None,
    new_source: str | None,
    new_confidence: float,
) -> bool:
    if not new_module:
        return False

    existing_module = (existing_item.sap_module or "").strip()
    existing_source = existing_item.sap_module_source
    existing_data = existing_item.extracted_data if isinstance(existing_item.extracted_data, dict) else {}
    existing_confidence = _module_confidence_from_extracted_data(existing_data) or 0.0

    if not existing_module:
        return True

    new_rank = _module_source_rank(new_source)
    existing_rank = _module_source_rank(existing_source)
    new_strength = new_confidence + (new_rank * 0.05)
    existing_strength = existing_confidence + (existing_rank * 0.05)

    if new_strength > (existing_strength + 0.03):
        return True
    if existing_confidence < 0.65 and new_confidence >= 0.68:
        return True
    return False


def _merge_enriched_extracted_data(existing_data: dict, incoming_data: dict) -> dict:
    merged = dict(existing_data)
    for key in ("section_title", "parent_section_titles", "nearby_text", "table_context"):
        value = incoming_data.get(key)
        if value:
            merged[key] = value
    if "module_inference_confidence" in incoming_data:
        merged["module_inference_confidence"] = incoming_data["module_inference_confidence"]
    if "module_inference_reason" in incoming_data and incoming_data["module_inference_reason"]:
        merged["module_inference_reason"] = incoming_data["module_inference_reason"]
    return merged


def _safe_fallback_dedupe_key(
    item_type: KnowledgeItemType,
    title: str,
    content: str,
    extracted_data: dict,
) -> str:
    normalized_payload = {
        "item_type": item_type.value,
        "title": title.strip(),
        "content": content.strip(),
        "extracted_data": extracted_data,
    }
    digest = sha256(dumps(normalized_payload, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()
    return f"fallback|{item_type.value}|{digest}"


def _compute_dedupe_key(
    item_type: KnowledgeItemType,
    extracted_data: dict,
    *,
    title: str,
    content: str,
) -> str:
    if item_type == KnowledgeItemType.table_mention:
        table_name = _normalize_key_part(extracted_data.get("table_name"))
        if table_name:
            return f"table_mention|{table_name}"
    elif item_type == KnowledgeItemType.field_mention:
        field_name = _normalize_key_part(extracted_data.get("field_name"))
        if field_name:
            return f"field_mention|{field_name}"
    elif item_type == KnowledgeItemType.relationship_hint:
        source_table = _normalize_key_part(extracted_data.get("source_table"))
        target_table = _normalize_key_part(extracted_data.get("target_table"))
        join_field = _normalize_key_part(extracted_data.get("join_field"))
        if source_table and target_table and join_field:
            return f"relationship_hint|{source_table}|{target_table}|{join_field}"
    return _safe_fallback_dedupe_key(item_type, title, content, extracted_data)


def create_knowledge_items_from_candidates(
    db: Session,
    source_document_id: int,
    candidates: list[CandidateItem],
    *,
    debug_docx: bool = False,
    stage_ctx: object | None = None,
) -> tuple[list[KnowledgeItem], int, int]:
    from app.services.import_service import (
        IMPORT_STAGE_COMMIT_FINISHED,
        IMPORT_STAGE_COMMIT_STARTED,
        IMPORT_STAGE_EXTRACTION_FINISHED,
        IMPORT_STAGE_EXTRACTION_STARTED,
    )

    if stage_ctx is not None:
        stage_ctx.at(IMPORT_STAGE_EXTRACTION_STARTED)
    if debug_docx:
        print("DEBUG: DOCX before extraction service starts (create_knowledge_items_from_candidates)", flush=True)
    created_items: list[KnowledgeItem] = []
    duplicates_skipped = 0
    duplicates_enriched = 0
    existing_items_by_key = {
        item.dedupe_key: item
        for item in db.query(KnowledgeItem).filter(KnowledgeItem.dedupe_key.is_not(None)).all()
    }
    staged_keys: set[str] = set()
    module_lookup_cache: dict[str, tuple[str | None, str | None]] = {}

    for idx, candidate in enumerate(candidates, start=1):
        text = candidate.content
        source_ref = candidate.source_ref if FRAGMENT_PATTERN.match(candidate.source_ref) else f"fragment_{idx:03d}"

        context_data = candidate.extracted_data if isinstance(candidate.extracted_data, dict) else {}
        table_mentions = _candidate_table_mentions(text, context_data)
        for table_name in table_mentions:
            if len(table_name) > 2:
                extracted_data = _merge_context_extracted_data(context_data, {"table_name": table_name})
                title = f"Table mention: {table_name}"
                content = _normalized_table_statement(table_name)
                dedupe_key = _compute_dedupe_key(
                    KnowledgeItemType.table_mention,
                    extracted_data,
                    title=title,
                    content=content,
                )
                if dedupe_key in staged_keys:
                    duplicates_skipped += 1
                    continue
                sap_module, sap_module_source, module_confidence, module_reason = infer_sap_module_with_reason(
                    table_name,
                    item_type=KnowledgeItemType.table_mention.value,
                    content=text,
                    extracted_data=extracted_data,
                    allow_web_lookup=False,
                    run_cache=module_lookup_cache,
                )
                if module_reason:
                    extracted_data["module_inference_reason"] = module_reason
                extracted_data["module_inference_confidence"] = module_confidence
                existing_item = existing_items_by_key.get(dedupe_key)
                if existing_item is not None:
                    if not _should_try_duplicate_enrichment(existing_item):
                        duplicates_skipped += 1
                        continue
                    if _is_new_module_inference_stronger(
                        existing_item=existing_item,
                        new_module=sap_module,
                        new_source=sap_module_source,
                        new_confidence=module_confidence,
                    ):
                        existing_item.sap_module = sap_module
                        existing_item.sap_module_source = sap_module_source
                        existing_data = (
                            existing_item.extracted_data if isinstance(existing_item.extracted_data, dict) else {}
                        )
                        existing_item.extracted_data = _merge_enriched_extracted_data(existing_data, extracted_data)
                        db.add(existing_item)
                        duplicates_enriched += 1
                    else:
                        duplicates_skipped += 1
                    continue
                item = _build_item(
                    source_document_id=source_document_id,
                    item_type=KnowledgeItemType.table_mention,
                    title=title,
                    content=content,
                    source_ref=source_ref,
                    extracted_data=extracted_data,
                    dedupe_key=dedupe_key,
                    sap_module=sap_module,
                    sap_module_source=sap_module_source,
                )
                db.add(item)
                created_items.append(item)
                staged_keys.add(dedupe_key)

        field_mentions = _candidate_field_mentions(text, context_data, table_mentions)
        for field_name in field_mentions:
            extracted_data = _merge_context_extracted_data(context_data, {"field_name": field_name})
            title = f"Field mention: {field_name}"
            content = _normalized_field_statement(field_name)
            dedupe_key = _compute_dedupe_key(
                KnowledgeItemType.field_mention,
                extracted_data,
                title=title,
                content=content,
            )
            if dedupe_key in staged_keys:
                duplicates_skipped += 1
                continue
            field_table = field_name.split("-", maxsplit=1)[0] if "-" in field_name else None
            sap_module, sap_module_source, module_confidence, module_reason = infer_sap_module_with_reason(
                field_table,
                item_type=KnowledgeItemType.field_mention.value,
                content=text,
                extracted_data=extracted_data,
                allow_web_lookup=False,
                run_cache=module_lookup_cache,
            )
            if module_reason:
                extracted_data["module_inference_reason"] = module_reason
            extracted_data["module_inference_confidence"] = module_confidence
            existing_item = existing_items_by_key.get(dedupe_key)
            if existing_item is not None:
                if not _should_try_duplicate_enrichment(existing_item):
                    duplicates_skipped += 1
                    continue
                if _is_new_module_inference_stronger(
                    existing_item=existing_item,
                    new_module=sap_module,
                    new_source=sap_module_source,
                    new_confidence=module_confidence,
                ):
                    existing_item.sap_module = sap_module
                    existing_item.sap_module_source = sap_module_source
                    existing_data = existing_item.extracted_data if isinstance(existing_item.extracted_data, dict) else {}
                    existing_item.extracted_data = _merge_enriched_extracted_data(existing_data, extracted_data)
                    db.add(existing_item)
                    duplicates_enriched += 1
                else:
                    duplicates_skipped += 1
                continue
            item = _build_item(
                source_document_id=source_document_id,
                item_type=KnowledgeItemType.field_mention,
                title=title,
                content=content,
                source_ref=source_ref,
                extracted_data=extracted_data,
                dedupe_key=dedupe_key,
                sap_module=sap_module,
                sap_module_source=sap_module_source,
            )
            db.add(item)
            created_items.append(item)
            staged_keys.add(dedupe_key)

        has_explicit_wording = RELATIONSHIP_PATTERN.search(text) is not None
        relationship_candidate = _best_relationship_candidate(table_mentions, field_mentions, has_explicit_wording)
        if relationship_candidate is not None:
            source_table, target_table, join_field, has_known_mapping, has_shared_field = relationship_candidate
            context_data = candidate.extracted_data if isinstance(candidate.extracted_data, dict) else {}
            extracted_data = _merge_context_extracted_data(
                context_data,
                {"source_table": source_table, "target_table": target_table, "join_field": join_field},
            )
            title = "Relationship hint detected"
            content = _normalized_relationship_statement([source_table, target_table], join_field)
            dedupe_key = _compute_dedupe_key(
                KnowledgeItemType.relationship_hint,
                extracted_data,
                title=title,
                content=content,
            )
            if dedupe_key in staged_keys:
                duplicates_skipped += 1
                continue
            sap_module, sap_module_source, module_confidence, module_reason = infer_sap_module_with_reason(
                source_table or target_table,
                item_type=KnowledgeItemType.relationship_hint.value,
                content=text,
                extracted_data=extracted_data,
                allow_web_lookup=False,
                run_cache=module_lookup_cache,
            )
            if module_reason:
                extracted_data["module_inference_reason"] = module_reason
            extracted_data["module_inference_confidence"] = module_confidence
            existing_item = existing_items_by_key.get(dedupe_key)
            if existing_item is not None:
                if not _should_try_duplicate_enrichment(existing_item):
                    duplicates_skipped += 1
                    continue
                if _is_new_module_inference_stronger(
                    existing_item=existing_item,
                    new_module=sap_module,
                    new_source=sap_module_source,
                    new_confidence=module_confidence,
                ):
                    existing_item.sap_module = sap_module
                    existing_item.sap_module_source = sap_module_source
                    existing_data = existing_item.extracted_data if isinstance(existing_item.extracted_data, dict) else {}
                    existing_item.extracted_data = _merge_enriched_extracted_data(existing_data, extracted_data)
                    db.add(existing_item)
                    duplicates_enriched += 1
                else:
                    duplicates_skipped += 1
                continue
            confidence = _relationship_confidence(
                has_known_mapping=has_known_mapping,
                has_shared_field=has_shared_field,
                has_explicit_wording=has_explicit_wording,
                table_count=len(table_mentions),
            )
            item = _build_item(
                source_document_id=source_document_id,
                item_type=KnowledgeItemType.relationship_hint,
                title=title,
                content=content,
                source_ref=source_ref,
                extracted_data=extracted_data,
                dedupe_key=dedupe_key,
                sap_module=sap_module,
                sap_module_source=sap_module_source,
                confidence_override=confidence,
            )
            db.add(item)
            created_items.append(item)
            staged_keys.add(dedupe_key)

    if stage_ctx is not None:
        stage_ctx.at(IMPORT_STAGE_EXTRACTION_FINISHED)
    if debug_docx:
        print("DEBUG: DOCX after extraction service completes (candidate loop finished, items staged)", flush=True)
    if debug_docx:
        print("DEBUG: DOCX before knowledge items db.commit()", flush=True)
    if stage_ctx is not None:
        stage_ctx.at(IMPORT_STAGE_COMMIT_STARTED)
    try:
        db.commit()
    except Exception:
        if debug_docx:
            print("DEBUG: DOCX exception during knowledge items db.commit()", flush=True)
            traceback.print_exc()
        raise
    if stage_ctx is not None:
        stage_ctx.at(IMPORT_STAGE_COMMIT_FINISHED)
    if debug_docx:
        print("DEBUG: DOCX after knowledge items db.commit()", flush=True)
    for item in created_items:
        db.refresh(item)
    return created_items, duplicates_skipped, duplicates_enriched
