import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.document import Document
from app.parsers.factory import get_parser
from app.schemas.upload import UploadResponse
from app.services.extraction_service import create_knowledge_items_from_candidates

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    uploaded_by: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    file_suffix = Path(file.filename).suffix.lower()
    if file_suffix not in {".docx", ".xlsx", ".pdf"}:
        raise HTTPException(status_code=400, detail="Unsupported file type. Allowed: .docx, .xlsx, .pdf")

    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid4()}{file_suffix}"
    storage_path = upload_dir / stored_name
    file_content = await file.read()
    storage_path.write_bytes(file_content)

    document = Document(
        filename=file.filename,
        file_type=file_suffix.replace(".", ""),
        title=title,
        uploaded_by=uploaded_by,
        storage_path=os.fspath(storage_path),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    parser = get_parser(document.file_type)
    parsed = parser.parse(document.storage_path)
    created_items = create_knowledge_items_from_candidates(db, document.id, parsed.candidates)

    return UploadResponse(
        document_id=document.id,
        filename=document.filename,
        knowledge_items_created=len(created_items),
    )
