from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    session_id: str | None = None
    retrieval_mode: Literal["hybrid", "vector"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=50)
    return_context: bool = True


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class UserPermissionsUpdate(BaseModel):
    enabled: bool | None = Field(default=None, strict=True)
    can_upload: bool = Field(strict=True)
    can_switch_models: bool = Field(strict=True)

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=6, max_length=200)
    display_name: str = Field(default="", max_length=80)


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1)
    retrieval_mode: Literal["hybrid", "vector"] = "hybrid"
    k: int = Field(default=10, ge=1, le=50)
    rerank: bool = True


class BatchIngestRequest(BaseModel):
    path: str = Field(min_length=1)
    include_noise_html: bool = False
    dry_run: bool = False
    operator: str = "小虎"


class ModelSwitchRequest(BaseModel):
    mode: Literal["cloudflare", "dashscope"]


class SessionTitleUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=80)


class DocumentQueryParams(BaseModel):
    doc_type: str | None = None
    keyword: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)


class UploadResponse(BaseModel):
    filename: str
    status: str
    message: str
    chunk_count: int | None = None
