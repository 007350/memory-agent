from typing import Any
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str
    mode: str = "hybrid"
    top_k: int = Field(default=40, ge=1, le=200)
    only_need_context: bool = False


class SourceReference(BaseModel):
    reference_id: str
    file_path: str | None = None
    content: str | None = None


class QueryResponse(BaseModel):
    response: str
    references: list[SourceReference] = []
    response_time: float | None = None


class DocumentInsertRequest(BaseModel):
    text: str
    file_source: str = ""


class DocumentUploadResponse(BaseModel):
    status: str
    message: str
    track_id: str | None = None


class DocumentStatus(BaseModel):
    id: str
    status: str
    content_summary: str | None = None
    chunks_count: int | None = None
    error_msg: str | None = None


class TrackStatusResponse(BaseModel):
    track_id: str
    documents: list[DocumentStatus] = []
    status_summary: dict[str, Any] = {}


class HealthResponse(BaseModel):
    status: str
    core_version: str | None = None
    api_version: str | None = None
    pipeline_busy: bool = False
    llm_model: str | None = None
    embedding_model: str | None = None
