from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import logging
import traceback

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.document import Document
from app.parsers.factory import get_parser
from app.services.extraction_service import create_knowledge_items_from_candidates
from app.core.config import get_settings

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".docx", ".xlsx", ".pdf"}

# Stages for batch import debug (include_results=true); do not expose raw errors or paths.
IMPORT_STAGE_RECEIVED = "received"
IMPORT_STAGE_PARSER_SELECTED = "parser_selected"
IMPORT_STAGE_PARSE_STARTED = "parse_started"
IMPORT_STAGE_PARSE_FINISHED = "parse_finished"
IMPORT_STAGE_DOCUMENT_RECORD_STARTED = "document_record_started"
IMPORT_STAGE_DOCUMENT_RECORD_CREATED = "document_record_created"
IMPORT_STAGE_EXTRACTION_STARTED = "extraction_started"
IMPORT_STAGE_EXTRACTION_FINISHED = "extraction_finished"
IMPORT_STAGE_COMMIT_STARTED = "commit_started"
IMPORT_STAGE_COMMIT_FINISHED = "commit_finished"

IMPORT_STAGES: tuple[str, ...] = (
    IMPORT_STAGE_RECEIVED,
    IMPORT_STAGE_PARSER_SELECTED,
    IMPORT_STAGE_PARSE_STARTED,
    IMPORT_STAGE_PARSE_FINISHED,
    IMPORT_STAGE_DOCUMENT_RECORD_STARTED,
    IMPORT_STAGE_DOCUMENT_RECORD_CREATED,
    IMPORT_STAGE_EXTRACTION_STARTED,
    IMPORT_STAGE_EXTRACTION_FINISHED,
    IMPORT_STAGE_COMMIT_STARTED,
    IMPORT_STAGE_COMMIT_FINISHED,
)


class ImportStageContext:
    """Mutable per-file stage for safe response debug (no exception text or paths)."""

    __slots__ = ("_stage",)

    def __init__(self) -> None:
        self._stage = IMPORT_STAGE_RECEIVED

    @property
    def stage(self) -> str:
        return self._stage

    def at(self, stage: str) -> None:
        self._stage = stage


def _sanitized_failure_message(file_type: str, stage: str) -> str:
    ft = file_type.lower()
    if stage in (
        IMPORT_STAGE_RECEIVED,
        IMPORT_STAGE_PARSER_SELECTED,
        IMPORT_STAGE_PARSE_STARTED,
        IMPORT_STAGE_PARSE_FINISHED,
    ):
        if ft == "docx":
            return "DOCX parsing failed"
        return "File parsing failed"
    if stage in (IMPORT_STAGE_DOCUMENT_RECORD_STARTED, IMPORT_STAGE_DOCUMENT_RECORD_CREATED):
        return "Document record failed"
    if stage in (IMPORT_STAGE_EXTRACTION_STARTED, IMPORT_STAGE_EXTRACTION_FINISHED):
        return "Extraction failed"
    if stage in (IMPORT_STAGE_COMMIT_STARTED, IMPORT_STAGE_COMMIT_FINISHED):
        return "Database save failed"
    return "File import failed"


def _generate_document_code() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = uuid4().hex[:6].upper()
    return f"DOC-{timestamp}-{suffix}"


def _create_document_record(
    db: Session,
    file_type: str,
    imported_by: str | None,
    *,
    debug_docx: bool = False,
    stage_ctx: ImportStageContext | None = None,
) -> Document:
    for _ in range(5):
        document = Document(
            document_code=_generate_document_code(),
            file_type=file_type,
            imported_by=imported_by,
        )
        db.add(document)
        try:
            if debug_docx:
                print("DEBUG: DOCX before document row db.commit()", flush=True)
            db.commit()
            db.refresh(document)
            if debug_docx:
                print("DEBUG: DOCX after document row db.commit()", flush=True)
            if stage_ctx is not None:
                stage_ctx.at(IMPORT_STAGE_DOCUMENT_RECORD_CREATED)
            return document
        except IntegrityError:
            db.rollback()
    raise RuntimeError("Could not allocate unique document code.")


def import_folder(db: Session, folder_path: str, imported_by: str | None) -> tuple[int, int, int, int, int]:
    base = Path(folder_path)
    if not base.exists() or not base.is_dir():
        raise ValueError("Folder path is invalid.")

    documents_processed = 0
    knowledge_items_created = 0
    duplicates_skipped = 0
    duplicates_enriched = 0
    failed_files = 0

    for file_path in base.iterdir():
        if not file_path.is_file() or file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        try:
            created_count, duplicates_count, enriched_count = _process_file_path(
                db=db, file_path=str(file_path), file_type=file_path.suffix.lower().replace(".", ""), imported_by=imported_by
            )
            documents_processed += 1
            knowledge_items_created += created_count
            duplicates_skipped += duplicates_count
            duplicates_enriched += enriched_count
        except Exception:
            failed_files += 1
            logger.exception("Folder import failed for one file.")

    logger.info(
        "Folder import finished. documents_processed=%s knowledge_items_created=%s failed_files=%s",
        documents_processed,
        knowledge_items_created,
        failed_files,
    )
    return documents_processed, knowledge_items_created, duplicates_skipped, duplicates_enriched, failed_files


def _run_llm_enhancement_if_enabled(db: Session, created_items: list) -> None:
    settings = get_settings()
    if not settings.use_llm_enhancement:
        return
    if not created_items:
        return
    import os
    if settings.anthropic_api_key:
        os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
    from app.services.llm_service import enhance_knowledge_items_with_llm
    enhance_knowledge_items_with_llm(db, created_items)


def _process_file_path(db: Session, file_path: str, file_type: str, imported_by: str | None) -> tuple[int, int, int]:
    parser = get_parser(file_type)
    parsed = parser.parse(file_path)
    document = _create_document_record(db, file_type=file_type, imported_by=imported_by)
    created, duplicates_skipped, duplicates_enriched = create_knowledge_items_from_candidates(db, document.id, parsed.candidates)
    _run_llm_enhancement_if_enabled(db, created)
    return len(created), duplicates_skipped, duplicates_enriched


def _process_file_bytes(
    db: Session,
    file_bytes: bytes,
    file_type: str,
    imported_by: str | None,
    *,
    stage_ctx: ImportStageContext | None = None,
) -> tuple[int, int, int]:
    """Batch upload path: parse entirely in memory (no temp files). Avoids Windows temp-file issues."""
    debug_docx = file_type.lower() == "docx"
    parser = get_parser(file_type)
    if stage_ctx is not None:
        stage_ctx.at(IMPORT_STAGE_PARSER_SELECTED)
    if debug_docx:
        print(f"DEBUG: DOCX parser class selected: {type(parser).__name__}", flush=True)
        print("DEBUG: DOCX before parser.parse(...)", flush=True)
    if stage_ctx is not None:
        stage_ctx.at(IMPORT_STAGE_PARSE_STARTED)
    try:
        parsed = parser.parse(file_bytes)
    except Exception:
        if debug_docx:
            print("DEBUG: DOCX exception inside parser.parse(...)", flush=True)
            traceback.print_exc()
        raise
    if stage_ctx is not None:
        stage_ctx.at(IMPORT_STAGE_PARSE_FINISHED)
    if debug_docx:
        print("DEBUG: DOCX immediately after parser.parse(...)", flush=True)
        print(f"DEBUG: DOCX parsed candidate count={len(parsed.candidates)}", flush=True)
    if stage_ctx is not None:
        stage_ctx.at(IMPORT_STAGE_DOCUMENT_RECORD_STARTED)
    document = _create_document_record(
        db, file_type=file_type, imported_by=imported_by, debug_docx=debug_docx, stage_ctx=stage_ctx
    )
    created, duplicates_skipped, duplicates_enriched = create_knowledge_items_from_candidates(
        db, document.id, parsed.candidates, debug_docx=debug_docx, stage_ctx=stage_ctx
    )
    _run_llm_enhancement_if_enabled(db, created)
    return len(created), duplicates_skipped, duplicates_enriched


def import_uploaded_files(
    db: Session,
    uploaded_files: list[tuple[int, str, bytes]],
    imported_by: str | None,
    *,
    include_result_stages: bool = False,
) -> tuple[int, int, int, int, int, list[dict[str, str | int]]]:
    documents_processed = 0
    knowledge_items_created = 0
    duplicates_skipped = 0
    duplicates_enriched = 0
    failed_files = 0
    results: list[dict[str, str | int]] = []

    for file_index, file_type, file_bytes in uploaded_files:
        stage_ctx = ImportStageContext()
        try:
            created_count, duplicates_count, enriched_count = _process_file_bytes(
                db=db,
                file_bytes=file_bytes,
                file_type=file_type,
                imported_by=imported_by,
                stage_ctx=stage_ctx,
            )
            documents_processed += 1
            knowledge_items_created += created_count
            duplicates_skipped += duplicates_count
            duplicates_enriched += enriched_count
            row: dict[str, str | int] = {
                "file_index": file_index,
                "file_type": file_type,
                "status": "processed",
                "message": "File processed successfully",
                "duplicates_skipped": duplicates_count,
                "duplicates_enriched": enriched_count,
            }
            results.append(row)
        except Exception as exc:
            failed_files += 1
            if file_type.lower() == "docx":
                print(f"DEBUG: DOCX batch import except block: {exc!r}", flush=True)
                traceback.print_exc()
            logger.exception("File batch import failed for one file.")
            msg = (
                _sanitized_failure_message(file_type, stage_ctx.stage)
                if include_result_stages
                else f"{file_type.upper()} parsing or extraction failed"
            )
            fail_row: dict[str, str | int] = {
                "file_index": file_index,
                "file_type": file_type,
                "status": "failed",
                "message": msg,
            }
            if include_result_stages:
                fail_row["stage"] = stage_ctx.stage
            results.append(fail_row)

    logger.info(
        "File batch import finished. documents_processed=%s knowledge_items_created=%s failed_files=%s",
        documents_processed,
        knowledge_items_created,
        failed_files,
    )
    return documents_processed, knowledge_items_created, duplicates_skipped, duplicates_enriched, failed_files, results
