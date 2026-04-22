from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., description="用户提问的问题")
    document_id: Optional[str] = Field(default=None, description="限制检索的文档ID")
    knowledge_base_id: Optional[int] = Field(default=None, description="指定知识库ID")
    session_id: Optional[str] = Field(default=None, description="会话ID")
    stream: bool = Field(default=False, description="是否流式输出")
    use_agent: bool = Field(default=True, description="是否使用Agent处理")


class ChatResponse(BaseModel):
    answer: str = Field(..., description="AI 回答内容")
    query_type: str = Field(..., description="问题类型：medical/knowledge/other")
    rewritten_query: str = Field(..., description="改写后的查询")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="来源信息列表")
    needs_followup: bool = Field(default=False, description="是否需要后续追问")
    followup_question: Optional[str] = Field(default=None, description="后续追问问题")
    status: str = Field(..., description="响应状态", pattern="^(success|error|empty)$")
    session_id: Optional[str] = Field(default=None, description="会话ID")