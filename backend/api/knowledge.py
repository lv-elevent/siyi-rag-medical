import logging

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy import func

from backend.repositories.vector_repository import VectorRepository
from backend.core.security import get_current_user
from backend.database.session import get_db
from backend.database.models import (
    KnowledgeBase,
    Document,
    KnowledgeBaseDocument,
    ChatSession,
    ChatMessage,
    RetrievalLog,
)
from backend.models.knowledge import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseUpdateRequest,
    KnowledgeBaseItem,
    KnowledgeBaseListResponse,
    KnowledgeBaseDetailResponse,
)
from backend.services.knowledge_registry import load_registry, save_registry
from backend.services.knowledge_service import get_or_create_default_kb, ensure_document_link

router = APIRouter()
logger = logging.getLogger(__name__)




def _serialize_kb(kb, document_count=0) -> KnowledgeBaseItem:
    return KnowledgeBaseItem(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        status=kb.status,
        document_count=document_count or 0,
        created_at=kb.created_at.isoformat() if kb.created_at else None,
        updated_at=kb.updated_at.isoformat() if kb.updated_at else None,
    )


def _ensure_user_document_links(db, current_user):
    global_kb = get_or_create_default_kb(db, current_user)
    docs = (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .all()
    )
    for doc in docs:
        ensure_document_link(db, global_kb.id, doc.id, current_user.id)
        if doc.knowledge_base_id:
            ensure_document_link(db, doc.knowledge_base_id, doc.id, current_user.id)


@router.post("/knowledge", response_model=KnowledgeBaseDetailResponse)
async def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    name = payload.name.strip()

    existing = (
        db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.user_id == current_user.id,
            func.trim(KnowledgeBase.name) == name,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="知识库名称已存在",
        )

    kb = KnowledgeBase(
        user_id=current_user.id,
        name=name,
        description=payload.description,
        status="active",
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)

    return KnowledgeBaseDetailResponse(
        status="success",
        knowledge_base=_serialize_kb(kb, document_count=0),
    )


@router.get("/knowledge", response_model=KnowledgeBaseListResponse)
async def list_knowledge_bases(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    _ensure_user_document_links(db, current_user)
    rows = (
        db.query(
            KnowledgeBase,
            func.count(KnowledgeBaseDocument.id).label("document_count"),
        )
        .outerjoin(
            KnowledgeBaseDocument,
            (KnowledgeBaseDocument.knowledge_base_id == KnowledgeBase.id)
            & (KnowledgeBaseDocument.user_id == current_user.id),
        )
        .filter(KnowledgeBase.user_id == current_user.id)
        .group_by(KnowledgeBase.id)
        .order_by(KnowledgeBase.updated_at.desc(), KnowledgeBase.id.desc())
        .all()
    )

    items = [
        _serialize_kb(kb, int(document_count or 0))
        for kb, document_count in rows
    ]

    return KnowledgeBaseListResponse(
        status="success",
        knowledge_bases=items,
    )


@router.get("/knowledge/{knowledge_base_id}/files")
async def list_knowledge_base_files(
    knowledge_base_id: int,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    kb = (
        db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.user_id == current_user.id,
        )
        .first()
    )
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在",
        )

    _ensure_user_document_links(db, current_user)
    if (kb.name or "").strip() == "全库":
        docs = (
            db.query(Document)
            .filter(Document.user_id == current_user.id)
            .order_by(Document.created_at.desc(), Document.id.desc())
            .all()
        )
    else:
        docs = (
            db.query(Document)
            .join(
                KnowledgeBaseDocument,
                (KnowledgeBaseDocument.document_id == Document.id)
                & (KnowledgeBaseDocument.user_id == current_user.id),
            )
            .filter(
                Document.user_id == current_user.id,
                KnowledgeBaseDocument.knowledge_base_id == knowledge_base_id,
            )
            .order_by(Document.created_at.desc(), Document.id.desc())
            .all()
        )

    return {
        "status": "success",
        "files": [
            {
                "document_id": d.id,
                "filename": d.filename,
                "status": d.status,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in docs
        ],
    }


@router.put("/knowledge/{knowledge_base_id}", response_model=KnowledgeBaseDetailResponse)
async def update_knowledge_base(
    knowledge_base_id: int,
    payload: KnowledgeBaseUpdateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    kb = (
        db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.user_id == current_user.id,
        )
        .first()
    )
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在",
        )

    if payload.name is not None:
        new_name = payload.name.strip()
        duplicate = (
            db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.user_id == current_user.id,
                KnowledgeBase.id != knowledge_base_id,
                func.trim(KnowledgeBase.name) == new_name,
            )
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="知识库名称已存在",
            )
        kb.name = new_name

    if payload.description is not None:
        kb.description = payload.description

    if payload.status is not None:
        kb.status = payload.status

    db.commit()
    db.refresh(kb)

    document_count = (
        db.query(func.count(KnowledgeBaseDocument.id))
        .filter(
            KnowledgeBaseDocument.user_id == current_user.id,
            KnowledgeBaseDocument.knowledge_base_id == knowledge_base_id,
        )
        .scalar()
        or 0
    )

    return KnowledgeBaseDetailResponse(
        status="success",
        knowledge_base=_serialize_kb(kb, int(document_count)),
    )


@router.post("/knowledge/document/remove")
async def remove_document_from_knowledge_base(
    payload: dict = Body(...),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    document_id = payload.get("document_id")
    current_kb_id = payload.get("knowledge_base_id")

    if not document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="document_id 不能为空",
        )
    try:
        document_id = int(document_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="document_id 非法",
        )

    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在",
        )

    if current_kb_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="knowledge_base_id 不能为空",
        )
    kb = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.id == int(current_kb_id), KnowledgeBase.user_id == current_user.id)
        .first()
    )
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在",
        )
    if (kb.name or "").strip() == "全库":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="全库不支持移除文档",
        )

    link = (
        db.query(KnowledgeBaseDocument)
        .filter(
            KnowledgeBaseDocument.user_id == current_user.id,
            KnowledgeBaseDocument.knowledge_base_id == int(current_kb_id),
            KnowledgeBaseDocument.document_id == doc.id,
        )
        .first()
    )
    if not link:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文档不在当前知识库中",
        )

    try:
        db.delete(link)
        db.commit()
        return {"status": "success", "message": "文档已从当前知识库移除"}
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"移除文档失败: {str(exc)}",
        )


@router.delete("/knowledge/{knowledge_base_id}")
async def delete_knowledge_base(
    knowledge_base_id: int,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    # #endregion
    kb = (
        db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.user_id == current_user.id,
        )
        .first()
    )
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在",
        )

    if (kb.name or "").strip() in {"默认知识库", "全库"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="全库不允许删除",
        )

    session_ids = [
        sid for (sid,) in (
            db.query(ChatSession.id)
            .filter(
                ChatSession.user_id == current_user.id,
                ChatSession.knowledge_base_id == knowledge_base_id,
            )
            .all()
        )
    ]
    document_ids = [
        did for (did,) in (
            db.query(Document.id)
            .filter(
                Document.user_id == current_user.id,
                Document.knowledge_base_id == knowledge_base_id,
            )
            .all()
        )
    ]
    # #endregion

    try:
        # 1) 先删会话链路（仅该知识库）
        if session_ids:
            db.query(RetrievalLog).filter(
                RetrievalLog.user_id == current_user.id,
                RetrievalLog.chat_session_id.in_(session_ids),
            ).delete(synchronize_session=False)

            db.query(ChatMessage).filter(
                ChatMessage.user_id == current_user.id,
                ChatMessage.chat_session_id.in_(session_ids),
            ).delete(synchronize_session=False)

        db.query(ChatSession).filter(
            ChatSession.user_id == current_user.id,
            ChatSession.knowledge_base_id == knowledge_base_id,
        ).delete(synchronize_session=False)

        # 2) 只删除关联关系，不删除文档实体
        db.query(KnowledgeBaseDocument).filter(
            KnowledgeBaseDocument.user_id == current_user.id,
            KnowledgeBaseDocument.knowledge_base_id == knowledge_base_id,
        ).delete(synchronize_session=False)

        # 3) 删除知识库
        db.delete(kb)

        db.commit()

        return {"status": "success", "message": "知识库已删除"}

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除知识库失败: {str(exc)}",
        )


@router.get("/knowledge/files/all")
async def list_all_files(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    docs = (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .all()
    )
    return {
        "status": "success",
        "files": [
            {
                "document_id": d.id,
                "filename": d.filename,
                "status": d.status,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in docs
        ],
    }


@router.post("/knowledge/document/attach")
async def attach_document_to_knowledge_base(
    payload: dict = Body(...),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    document_id = payload.get("document_id")
    knowledge_base_id = payload.get("knowledge_base_id")
    if not document_id or not knowledge_base_id:
        raise HTTPException(status_code=400, detail="document_id 与 knowledge_base_id 不能为空")

    doc = (
        db.query(Document)
        .filter(Document.id == int(document_id), Document.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    kb = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.id == int(knowledge_base_id), KnowledgeBase.user_id == current_user.id)
        .first()
    )
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    ensure_document_link(db, kb.id, doc.id, current_user.id)
    return {"status": "success", "message": "文档已加入知识库"}


@router.delete("/knowledge/clear")
async def clear_knowledge(current_user=Depends(get_current_user)):
    repo = VectorRepository()
    repo.collection.delete(where={"user_id": current_user.id})

    registry = load_registry()
    filtered_registry = {
        key: meta
        for key, meta in registry.items()
        if meta.get("user_id") != current_user.id
    }
    if len(filtered_registry) != len(registry):
        save_registry(filtered_registry)

    return {"status": "success", "message": "当前用户知识库已清空"}