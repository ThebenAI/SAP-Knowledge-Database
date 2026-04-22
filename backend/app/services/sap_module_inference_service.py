from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from sqlalchemy.orm import Session

from app.services.sap_module_service import suggest_sap_module_for_table, suggest_sap_module_for_table_local_only

MODULE_VALUES: tuple[str, ...] = (
    "FI",
    "CO",
    "MM",
    "SD",
    "PP",
    "WM",
    "EWM",
    "HCM",
    "PM",
    "QM",
    "Basis",
    "PS",
    "Cross-Module",
)

_MODULE_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bcross[-\s]?module\b", re.IGNORECASE), "Cross-Module"),
    (re.compile(r"\bmaterials?\s+management\b|\bsap\s+mm\b|\bmm\b", re.IGNORECASE), "MM"),
    (re.compile(r"\bsales\s+and\s+distribution\b|\bsap\s+sd\b|\bsd\b", re.IGNORECASE), "SD"),
    (re.compile(r"\bfinancial\s+accounting\b|\bsap\s+fi\b|\bfi\b", re.IGNORECASE), "FI"),
    (re.compile(r"\bcontrolling\b|\bsap\s+co\b|\bco\b", re.IGNORECASE), "CO"),
    (re.compile(r"\bproduction\s+planning\b|\bsap\s+pp\b|\bpp\b", re.IGNORECASE), "PP"),
    (re.compile(r"\bextended\s+warehouse\s+management\b|\bewm\b", re.IGNORECASE), "EWM"),
    (re.compile(r"\bwarehouse\s+management\b|\bsap\s+wm\b|\bwm\b", re.IGNORECASE), "WM"),
    (
        re.compile(
            r"\bhuman\s+resources\b|\bhuman\s+capital\s+management\b|\bsap\s+hcm\b|\bhcm\b|\bhr\b",
            re.IGNORECASE,
        ),
        "HCM",
    ),
    (re.compile(r"\bplant\s+maintenance\b|\bsap\s+pm\b|\bpm\b", re.IGNORECASE), "PM"),
    (re.compile(r"\bquality\s+management\b|\bsap\s+qm\b|\bqm\b", re.IGNORECASE), "QM"),
    (re.compile(r"\bproject\s+system\b|\bsap\s+ps\b|\bps\b", re.IGNORECASE), "PS"),
    (re.compile(r"\bbasis\b", re.IGNORECASE), "Basis"),
)

_MODULE_COLUMNS: set[str] = {
    "module",
    "sap module",
    "sap area",
    "application",
    "area",
}

_STRONG_SECTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsap\s+mm\b|\bmaterials?\s+management\b", re.IGNORECASE), "MM"),
    (re.compile(r"\bsap\s+sd\b|\bsales\s+and\s+distribution\b", re.IGNORECASE), "SD"),
    (re.compile(r"\bsap\s+fi\b|\bfinancial\s+accounting\b", re.IGNORECASE), "FI"),
    (re.compile(r"\bsap\s+co\b|\bcontrolling\b", re.IGNORECASE), "CO"),
    (re.compile(r"\bsap\s+pp\b|\bproduction\s+planning\b", re.IGNORECASE), "PP"),
    (re.compile(r"\bsap\s+pm\b|\bplant\s+maintenance\b", re.IGNORECASE), "PM"),
    (re.compile(r"\bsap\s+ps\b|\bproject\s+system\b", re.IGNORECASE), "PS"),
    (re.compile(r"\bsap\s+wm\b|\bwarehouse\s+management\b", re.IGNORECASE), "WM"),
    (
        re.compile(
            r"\bsap\s+hcm\b|\bhuman\s+resources\b|\bhuman\s+capital\s+management\b|\bhr\s+module\b",
            re.IGNORECASE,
        ),
        "HCM",
    ),
)

_MIN_CONFIDENCE = 0.68
_AMBIGUITY_GAP = 0.08


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _normalize_module_name(text: str) -> str | None:
    normalized = _clean_text(text)
    if not normalized:
        return None
    for pattern, module in _MODULE_ALIASES:
        if pattern.search(normalized):
            return module
    return None


def _iter_table_module_values(extracted_data: dict[str, Any]) -> list[str]:
    table_ctx = extracted_data.get("table_context")
    if not isinstance(table_ctx, dict):
        return []
    row_values = table_ctx.get("row_values")
    if not isinstance(row_values, dict):
        return []
    values: list[str] = []
    for key, value in row_values.items():
        key_text = _clean_text(key).lower()
        if key_text in _MODULE_COLUMNS:
            value_text = _clean_text(value)
            if value_text:
                values.append(value_text)
    return values


def _add_score(
    scores: dict[str, float],
    reasons: dict[str, str],
    module: str | None,
    score: float,
    reason: str,
) -> None:
    if not module:
        return
    if module not in MODULE_VALUES:
        return
    if score > scores[module]:
        reasons[module] = reason
    scores[module] = max(scores[module], score)


def _strong_section_module(text: str) -> str | None:
    normalized = _clean_text(text)
    if not normalized:
        return None
    for pattern, module in _STRONG_SECTION_PATTERNS:
        if pattern.search(normalized):
            return module
    return None


def infer_sap_module_with_reason(
    table_name: str | None,
    *,
    item_type: str,
    content: str,
    extracted_data: dict[str, Any],
    allow_web_lookup: bool = False,
    db: Session | None = None,
    run_cache: dict[str, tuple[str | None, str | None]] | None = None,
) -> tuple[str | None, str | None, float, str | None]:
    del item_type  # reserved for future weighting by item type.
    scores: dict[str, float] = defaultdict(float)
    reasons: dict[str, str] = {}

    section_title = _clean_text(extracted_data.get("section_title"))
    parent_titles = extracted_data.get("parent_section_titles")
    if not isinstance(parent_titles, list):
        parent_titles = []
    nearby_text = _clean_text(extracted_data.get("nearby_text"))
    table_ctx = extracted_data.get("table_context")
    is_structured_row = isinstance(table_ctx, dict) and bool(table_ctx.get("is_structured_table"))

    section_modules: set[str] = set()
    section_candidates = [section_title, *[_clean_text(parent) for parent in parent_titles]]
    strong_section_modules = {module for module in (_strong_section_module(text) for text in section_candidates) if module}
    if is_structured_row and len(strong_section_modules) == 1:
        propagated_module = next(iter(strong_section_modules))
        section_modules.add(propagated_module)
        _add_score(
            scores,
            reasons,
            propagated_module,
            0.82,
            f"Section propagation from structured row context matched {propagated_module}",
        )

    if section_title:
        module = _normalize_module_name(section_title)
        _add_score(scores, reasons, module, 0.75, f"Section title '{section_title}' matched {module}")
        if module:
            section_modules.add(module)

    for parent in parent_titles:
        parent_text = _clean_text(parent)
        if not parent_text:
            continue
        module = _normalize_module_name(parent_text)
        _add_score(scores, reasons, module, 0.74, f"Parent section '{parent_text}' matched {module}")
        if module:
            section_modules.add(module)

    for value in _iter_table_module_values(extracted_data):
        module = _normalize_module_name(value)
        _add_score(scores, reasons, module, 0.97, f"Table column module value '{value}' matched {module}")

    if nearby_text:
        module = _normalize_module_name(nearby_text)
        _add_score(scores, reasons, module, 0.82, f"Nearby text context matched {module}")

    content_text = _clean_text(content)
    if content_text:
        module = _normalize_module_name(content_text)
        _add_score(scores, reasons, module, 0.76, f"Content text matched {module}")

    local_module, local_source = suggest_sap_module_for_table_local_only(table_name)
    if local_module and local_source == "local":
        _add_score(scores, reasons, local_module, 0.86, f"Local table mapping matched {local_module}")

    if not scores:
        if allow_web_lookup:
            web_module, web_source = suggest_sap_module_for_table(table_name, db=db, run_cache=run_cache)
            if web_module and web_source:
                return web_module, web_source, 0.7, "SAP web lookup matched module metadata"
        return None, None, 0.0, None

    sorted_scores = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    top_module, top_score = sorted_scores[0]
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0

    if top_module != "Cross-Module" and second_score >= _MIN_CONFIDENCE and (top_score - second_score) <= _AMBIGUITY_GAP:
        return (
            "Cross-Module",
            "document_context",
            round(max(0.7, top_score - 0.05), 2),
            "Multiple modules detected with similar strength; classified as Cross-Module",
        )

    if top_score < _MIN_CONFIDENCE:
        if allow_web_lookup:
            web_module, web_source = suggest_sap_module_for_table(table_name, db=db, run_cache=run_cache)
            if web_module and web_source:
                return web_module, web_source, 0.7, "Web lookup used due to weak contextual confidence"
        return None, None, round(top_score, 2), "Context signals were too weak to assign module safely"

    if top_score >= 0.88:
        source = "document_context"
    elif top_module in strong_section_modules and top_score >= 0.78:
        source = "document_context_section"
    elif top_score >= 0.75:
        source = "semantic_context"
    else:
        source = "local"
    return top_module, source, round(top_score, 2), reasons.get(top_module)


def infer_sap_module(
    table_name: str | None,
    *,
    item_type: str,
    content: str,
    extracted_data: dict[str, Any],
) -> tuple[str | None, str | None, float]:
    module, source, confidence, _ = infer_sap_module_with_reason(
        table_name,
        item_type=item_type,
        content=content,
        extracted_data=extracted_data,
        allow_web_lookup=False,
    )
    return module, source, confidence
