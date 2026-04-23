"""
LLM-based confidence enhancement for extracted KnowledgeItems.

Sends newly created items to the Claude API (claude-sonnet-4-6) for evaluation.
Claude returns an improved confidence score (0-1) and a short reasoning string
for each item. Results are written back to extracted_data["llm_confidence"] and
extracted_data["llm_reasoning"]; the item's confidence field is updated in-place.

This module is only active when USE_LLM_ENHANCEMENT=true and ANTHROPIC_API_KEY
is set. All failures are logged and silently swallowed so the import pipeline
continues even if the LLM step is unavailable.
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models.knowledge_item import KnowledgeItem

logger = logging.getLogger(__name__)

_MAX_ITEMS_PER_REQUEST = 20
_MODEL = "claude-sonnet-4-6"

_SYSTEM_PROMPT = """\
You are an expert SAP technical analyst. Your task is to evaluate the quality of automatically extracted SAP knowledge items and return improved confidence scores.

For each item you receive:
- item_type: table_mention | field_mention | relationship_hint
- title: what was extracted
- content: normalized description
- current_confidence: the rule-based confidence score (0.0 to 1.0)
- context: relevant surrounding text from the source document

Evaluate whether the extraction is genuinely a valid SAP entity (table, field, or relationship) based on:
1. Does the name follow SAP naming conventions?
2. Does the context support the extraction?
3. Is it likely a real SAP standard table/field (not a generic abbreviation)?

Return a JSON array with one object per item, in the same order:
[
  {
    "index": 0,
    "llm_confidence": 0.87,
    "llm_reasoning": "EKKO is a well-known SAP purchasing document header table. Context confirms procurement context."
  },
  ...
]

Rules:
- llm_confidence must be a float between 0.0 and 1.0
- llm_reasoning must be a single concise sentence (max 120 chars)
- Return valid JSON only, no markdown, no explanation outside the array
- If an item looks like a false positive (e.g., generic abbreviation, not an SAP entity), set llm_confidence <= 0.3
"""


def _build_items_payload(items: list[KnowledgeItem]) -> list[dict]:
    payload = []
    for idx, item in enumerate(items):
        extracted = item.extracted_data if isinstance(item.extracted_data, dict) else {}
        context = (
            extracted.get("nearby_text")
            or extracted.get("section_title")
            or item.content
        )
        payload.append({
            "index": idx,
            "item_type": item.item_type.value if hasattr(item.item_type, "value") else str(item.item_type),
            "title": item.title,
            "content": item.content,
            "current_confidence": round(item.confidence or 0.0, 2),
            "context": str(context)[:400],
        })
    return payload


def _parse_llm_response(response_text: str, item_count: int) -> list[dict] | None:
    try:
        results = json.loads(response_text.strip())
        if not isinstance(results, list):
            logger.warning("LLM response is not a list")
            return None
        if len(results) != item_count:
            logger.warning(
                "LLM returned %d results for %d items", len(results), item_count
            )
            return None
        for entry in results:
            if not isinstance(entry, dict):
                return None
            if "llm_confidence" not in entry or "llm_reasoning" not in entry:
                return None
            conf = entry["llm_confidence"]
            if not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
                return None
        return results
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Could not parse LLM response: %s", exc)
        return None


def _apply_results(
    items: list[KnowledgeItem], results: list[dict], db: Session
) -> None:
    for entry in results:
        idx = entry.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(items):
            continue
        item = items[idx]
        llm_confidence = round(float(entry["llm_confidence"]), 2)
        llm_reasoning = str(entry.get("llm_reasoning", ""))[:120]

        extracted = item.extracted_data if isinstance(item.extracted_data, dict) else {}
        extracted = dict(extracted)
        extracted["llm_confidence"] = llm_confidence
        extracted["llm_reasoning"] = llm_reasoning
        item.extracted_data = extracted

        # Blend: weighted average (rule-based 40%, LLM 60%)
        rule_confidence = item.confidence or 0.0
        item.confidence = round(0.4 * rule_confidence + 0.6 * llm_confidence, 2)

        db.add(item)


def _enhance_batch(
    items: list[KnowledgeItem], client, db: Session
) -> None:
    payload = _build_items_payload(items)
    user_message = (
        "Evaluate the following SAP knowledge items and return a JSON array "
        "with improved confidence scores:\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )

    response = client.messages.create(
        model=_MODEL,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    response_text = ""
    for block in response.content:
        if block.type == "text":
            response_text += block.text

    results = _parse_llm_response(response_text, len(items))
    if results is None:
        logger.warning("LLM enhancement: skipping batch due to invalid response")
        return

    _apply_results(items, results, db)

    cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
    logger.info(
        "LLM enhancement batch complete. items=%d cache_read_tokens=%d",
        len(items),
        cache_read,
    )


def enhance_knowledge_items_with_llm(
    db: Session,
    items: list[KnowledgeItem],
) -> None:
    """
    Enhance confidence scores of KnowledgeItems using the Claude API.

    Processes items in batches. Updates item.confidence and item.extracted_data
    in-place, then commits. Silently skips on any error.
    """
    if not items:
        return

    try:
        import anthropic  # imported lazily to avoid startup cost when disabled
    except ImportError:
        logger.warning("anthropic package not installed; skipping LLM enhancement")
        return

    try:
        client = anthropic.Anthropic()
    except Exception as exc:
        logger.warning("Could not initialize Anthropic client: %s", exc)
        return

    try:
        batches = [
            items[i: i + _MAX_ITEMS_PER_REQUEST]
            for i in range(0, len(items), _MAX_ITEMS_PER_REQUEST)
        ]
        for batch in batches:
            _enhance_batch(batch, client, db)

        db.commit()
        for item in items:
            db.refresh(item)

        logger.info(
            "LLM enhancement finished. total_items=%d batches=%d",
            len(items),
            len(batches),
        )
    except Exception as exc:
        logger.warning("LLM enhancement failed (non-fatal): %s", exc, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
