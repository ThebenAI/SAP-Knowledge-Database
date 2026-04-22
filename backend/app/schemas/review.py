from pydantic import BaseModel, Field


class ReviewActionRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=120)
    comment: str | None = Field(default=None, max_length=4000)
    sap_module: str | None = Field(default=None, max_length=64)
    links_note: str | None = Field(default=None, max_length=4000)
    source_table: str | None = Field(default=None, max_length=128)
    target_table: str | None = Field(default=None, max_length=128)
    join_field: str | None = Field(default=None, max_length=128)


class KnowledgeItemMetadataUpdateRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=120)
    comment: str | None = Field(default=None, max_length=4000)
    sap_module: str | None = Field(default=None, max_length=64)
    links_note: str | None = Field(default=None, max_length=4000)
    source_table: str | None = Field(default=None, max_length=128)
    target_table: str | None = Field(default=None, max_length=128)
    join_field: str | None = Field(default=None, max_length=128)
