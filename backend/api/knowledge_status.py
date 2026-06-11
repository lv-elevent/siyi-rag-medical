"""
知识库状态 API

状态查询统一走 MySQL，不再依赖内存 dict 或 JSON registry。
"""

from fastapi import APIRouter, HTTPException, status, Depends

from backend.models.knowledge_status import KnowledgeStatusResponse
from backend.core.security import get_current_user
from backend.database.session import get_db
from backend.database.models import Document

router = APIRouter()


@router.get("/knowledge/status", response_model=KnowledgeStatusResponse)
async def get_knowledge_status(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
) -> KnowledgeStatusResponse:
    """获取当前用户知识库状态（查最新文档）"""
    try:
        doc = (
            db.query(Document)
            .filter(Document.user_id == current_user.id)
            .order_by(Document.created_at.desc())
            .first()
        )
        if doc:
            return KnowledgeStatusResponse(
                has_document=True,
                filename=doc.filename,
                status=doc.status,
            )
        return KnowledgeStatusResponse(
            has_document=False, filename="", status="empty",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取知识库状态失败: {str(exc)}",
        )


@router.get("/knowledge/files")
async def get_knowledge_files(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """仅返回当前用户的知识库文件"""
    try:
        docs = (
            db.query(Document)
            .filter(Document.user_id == current_user.id)
            .order_by(Document.created_at.desc())
            .all()
        )
        return {
            "files": [
                {
                    "document_id": d.id,
                    "filename": d.filename,
                    "status": d.status,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in docs
            ]
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(exc)}",
        )
