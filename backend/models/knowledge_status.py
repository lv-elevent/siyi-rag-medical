from pydantic import BaseModel, Field


class KnowledgeStatusResponse(BaseModel):
    has_document: bool = Field(..., description="是否有文档")
    filename: str = Field(..., description="文档名")
    status: str = Field(..., description="状态", pattern="^(empty|processing|ready|error)$")