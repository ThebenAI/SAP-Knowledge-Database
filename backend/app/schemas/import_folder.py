from pydantic import BaseModel, ConfigDict, Field


class FolderImportRequest(BaseModel):
    folder_path: str = Field(min_length=1)
    imported_by: str | None = Field(default=None, max_length=120)


class FileImportResult(BaseModel):
    model_config = ConfigDict(ser_json_exclude_none=True)

    file_index: int
    file_type: str
    status: str
    message: str
    stage: str | None = None


class FolderImportResponse(BaseModel):
    documents_processed: int
    knowledge_items_created: int
    duplicates_skipped: int = 0
    failed_files: int
    results: list[FileImportResult] | None = None
