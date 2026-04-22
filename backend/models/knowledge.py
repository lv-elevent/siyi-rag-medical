from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class DeleteDocumentRequest(BaseModel):
    document_id: int


class DeleteDocumentResponse(BaseModel):
    status: str
    message: str
    document_id: int


class KnowledgeBaseCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name 不能为空")
        if len(v) > 128:
            raise ValueError("name 最大长度为 128")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) > 1000:
            raise ValueError("description 最大长度为 1000")
        return v


class KnowledgeBaseUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name 不能为空")
        if len(v) > 128:
            raise ValueError("name 最大长度为 128")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) > 1000:
            raise ValueError("description 最大长度为 1000")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in {"active", "archived"}:
            raise ValueError('status 仅允许 "active" 或 "archived"')
        return v


class KnowledgeBaseItem(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: str
    document_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class KnowledgeBaseListResponse(BaseModel):
    status: str = "success"
    knowledge_bases: List[KnowledgeBaseItem] = Field(default_factory=list)


class KnowledgeBaseDetailResponse(BaseModel):
    status: str = "success"
    knowledge_base: KnowledgeBaseItem