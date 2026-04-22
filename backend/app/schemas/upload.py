from pydantic import BaseModel


class UploadResponse(BaseModel):
    document_id: int
    filename: str
    knowledge_items_created: int
