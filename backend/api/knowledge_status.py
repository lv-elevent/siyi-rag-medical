from fastapi import APIRouter, HTTPException, status, Depends

from backend.models.knowledge_status import KnowledgeStatusResponse
from backend.services.knowledge_registry import registry_list
from backend.core.security import get_current_user

router = APIRouter()

# 按用户隔离的内存状态
knowledge_state_by_user: dict[str, dict] = {}


def set_knowledge_status_for_user(
    user_id: int,
    has_document: bool,
    filename: str = "",
    status: str = "empty"
) -> None:
    """
    内部使用：按 user_id 更新知识库状态
    """
    knowledge_state_by_user[str(user_id)] = {
        "has_document": has_document,
        "filename": filename,
        "status": status
    }


def get_knowledge_status_for_user(user_id: int) -> dict:
    """
    内部使用：按 user_id 获取知识库状态
    """
    return knowledge_state_by_user.get(
        str(user_id),
        {
            "has_document": False,
            "filename": "",
            "status": "empty"
        }
    )


@router.get("/knowledge/status", response_model=KnowledgeStatusResponse)
async def get_knowledge_status(current_user=Depends(get_current_user)) -> KnowledgeStatusResponse:
    """获取当前用户知识库状态"""
    try:
        state = get_knowledge_status_for_user(current_user.id)

        return KnowledgeStatusResponse(
            has_document=state["has_document"],
            filename=state["filename"],
            status=state["status"]
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取知识库状态失败: {str(exc)}"
        )


@router.get("/knowledge/files")
async def get_knowledge_files(current_user=Depends(get_current_user)):
    """仅返回当前用户的知识库文件"""
    try:
        files = registry_list(user_id=current_user.id)
        return {"files": files}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(exc)}"
        )