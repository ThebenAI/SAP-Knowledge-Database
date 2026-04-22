from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.import_folder import FolderImportRequest, FolderImportResponse
from app.services.import_service import (
    IMPORT_STAGE_RECEIVED,
    SUPPORTED_EXTENSIONS,
    import_folder,
    import_uploaded_files,
)

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/folder", response_model=FolderImportResponse, deprecated=True)
def import_folder_endpoint(payload: FolderImportRequest, db: Session = Depends(get_db)) -> FolderImportResponse:
    try:
        documents_processed, knowledge_items_created, duplicates_skipped, failed_files = import_folder(
            db=db, folder_path=payload.folder_path, imported_by=payload.imported_by
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Folder path is invalid.")
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Import setup failed.")
    except Exception:
        raise HTTPException(status_code=500, detail="Folder import failed.")

    return FolderImportResponse(
        documents_processed=documents_processed,
        knowledge_items_created=knowledge_items_created,
        duplicates_skipped=duplicates_skipped,
        failed_files=failed_files,
    )


@router.post("/files", response_model=FolderImportResponse)
async def import_files_endpoint(
    files: list[UploadFile] = File(...),
    imported_by: str | None = Form(default=None),
    include_results: bool = Form(default=False),
    db: Session = Depends(get_db),
) -> FolderImportResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    if any(Path(f.filename or "").suffix.lower() == ".docx" for f in files):
        print("DEBUG: DOCX import_files_endpoint entered", flush=True)

    payloads: list[tuple[int, str, bytes]] = []
    failed_files = 0
    results: list[dict[str, str | int]] = []

    for file_index, file in enumerate(files, start=1):
        suffix = Path(file.filename or "").suffix.lower()
        if suffix == ".docx":
            print(f"DEBUG: DOCX upload part received (file_index={file_index})", flush=True)
        if suffix not in SUPPORTED_EXTENSIONS:
            failed_files += 1
            row: dict[str, str | int] = {
                "file_index": file_index,
                "file_type": suffix.replace(".", "") or "unknown",
                "status": "failed",
                "message": "Unsupported file type",
            }
            if include_results:
                row["stage"] = IMPORT_STAGE_RECEIVED
            results.append(row)
            continue
        file_type = suffix.replace(".", "")
        if suffix == ".docx":
            print(f"DEBUG: DOCX file type normalized suffix={suffix} file_type={file_type}", flush=True)
        file_bytes = await file.read()
        if suffix == ".docx":
            print(f"DEBUG: DOCX bytes length after read={len(file_bytes)}", flush=True)
        if not file_bytes:
            failed_files += 1
            empty_row: dict[str, str | int] = {
                "file_index": file_index,
                "file_type": file_type,
                "status": "failed",
                "message": "Empty file payload",
            }
            if include_results:
                empty_row["stage"] = IMPORT_STAGE_RECEIVED
            results.append(empty_row)
            continue
        payloads.append((file_index, file_type, file_bytes))

    if not payloads:
        return FolderImportResponse(
            documents_processed=0,
            knowledge_items_created=0,
            duplicates_skipped=0,
            failed_files=failed_files,
            results=results if include_results else None,
        )

    if any(ft.lower() == "docx" for _, ft, _ in payloads):
        print(f"DEBUG: DOCX before import_uploaded_files (payload_count={len(payloads)})", flush=True)

    try:
        documents_processed, knowledge_items_created, duplicates_skipped, service_failed, service_results = import_uploaded_files(
            db=db,
            uploaded_files=payloads,
            imported_by=imported_by,
            include_result_stages=include_results,
        )
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Import setup failed.")
    except Exception:
        print("DEBUG: top-level import_files_endpoint exception", flush=True)
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail="File import failed.")

    return FolderImportResponse(
        documents_processed=documents_processed,
        knowledge_items_created=knowledge_items_created,
        duplicates_skipped=duplicates_skipped,
        failed_files=failed_files + service_failed,
        results=(results + service_results) if include_results else None,
    )
