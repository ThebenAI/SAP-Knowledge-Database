from datetime import datetime

from pydantic import BaseModel


class DocumentRead(BaseModel):
    id: int
    document_code: str
    file_type: str
    imported_by: str | None
    processed_at: datetime

    model_config = {"from_attributes": True}
