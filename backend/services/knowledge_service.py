from typing import List
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, status

from backend.database.models import KnowledgeBase, Document, DocumentChunk, KnowledgeBaseDocument


# ============================================================
# 知识库校验（全项目统一入口）
# ============================================================

def get_user_kb_or_404(db, kb_id: int, user_id: int) -> KnowledgeBase:
    """查询知识库，不存在或不属于当前用户则 404"""
    kb = (
        db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == user_id,
        )
        .first()
    )
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在",
        )
    return kb


def get_or_resolve_kb(db, kb_id: int | None, user) -> KnowledgeBase:
    """有 id 则校验返回，没有则返回用户的默认'全库'"""
    if kb_id is not None:
        return get_user_kb_or_404(db, kb_id, user.id)
    return get_or_create_default_kb(db, user)


def get_or_create_default_kb(db, user):
    kb = (
        db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.user_id == user.id,
            KnowledgeBase.name == "全库",
        )
        .first()
    )
    if not kb:
        # 兼容旧数据：历史“默认知识库”直接复用并重命名为“全库”
        kb = (
            db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.user_id == user.id,
                KnowledgeBase.name == "默认知识库",
            )
            .first()
        )
        if kb:
            kb.name = "全库"
            kb.description = kb.description or "包含所有文档的全局知识库"
            db.add(kb)
            db.commit()
            db.refresh(kb)

    if kb:
        return kb

    kb = KnowledgeBase(
        user_id=user.id,
        name="全库",
        description="包含所有文档的全局知识库",
        created_at=datetime.utcnow()
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def get_kb_allowed_doc_ids(db, user_id: int, knowledge_base_id: int) -> list[int]:
    """获取指定知识库下所有文档的 ID 列表（'全库'返回该用户全部文档）"""
    kb = db.query(KnowledgeBase).filter(
        KnowledgeBase.id == knowledge_base_id,
        KnowledgeBase.user_id == user_id,
    ).first()

    if kb and (kb.name or "").strip() == "全库":
        return [int(x[0]) for x in db.query(Document.id).filter(Document.user_id == user_id).all()]

    # 确保旧数据的关联关系已建立
    docs = db.query(Document).filter(Document.user_id == user_id).all()
    for doc in docs:
        if doc.knowledge_base_id:
            ensure_document_link(db, doc.knowledge_base_id, doc.id, user_id)

    rows = (
        db.query(KnowledgeBaseDocument.document_id)
        .filter(
            KnowledgeBaseDocument.user_id == user_id,
            KnowledgeBaseDocument.knowledge_base_id == knowledge_base_id,
        )
        .all()
    )
    return [int(r[0]) for r in rows if r and r[0] is not None]


def create_document(
    db,
    kb: KnowledgeBase,
    filename: str,
    file_path: str,
    file_hash: str = "",
    file_size: int | None = None,
) -> Document:
    doc = Document(
        knowledge_base_id=kb.id,
        user_id=kb.user_id,
        filename=filename,
        file_path=file_path,
        file_hash=file_hash,
        file_size=file_size,
        file_type=filename.rsplit(".", 1)[-1].lower() if "." in filename else "pdf",
        status="processing",
        created_at=datetime.utcnow(),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    ensure_document_link(db, kb.id, doc.id, kb.user_id)
    return doc


def ensure_document_link(db, knowledge_base_id: int, document_id: int, user_id: int) -> None:
    exists = (
        db.query(KnowledgeBaseDocument)
        .filter(
            KnowledgeBaseDocument.knowledge_base_id == knowledge_base_id,
            KnowledgeBaseDocument.document_id == document_id,
            KnowledgeBaseDocument.user_id == user_id,
        )
        .first()
    )
    if exists:
        return

    db.add(
        KnowledgeBaseDocument(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            user_id=user_id,
            created_at=datetime.utcnow(),
        )
    )
    db.commit()


def update_document_status(db, document: Document, status: str) -> None:
    document.status = status
    db.add(document)
    db.commit()


# 🔥 关键修复：加 chroma_id + 更新 chunk_count
def create_chunks(db, document: Document, chunks: List[str]) -> List[DocumentChunk]:
    created = []

    for idx, text in enumerate(chunks):
        if not text:
            continue

        chunk = DocumentChunk(
            document_id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            user_id=document.user_id,
            chunk_index=idx,
            content=text,
            chroma_id=f"chunk_{uuid4().hex}",  # ✅ 必须加
            created_at=datetime.utcnow()
        )
        db.add(chunk)
        created.append(chunk)

    # ✅ 更新 chunk_count
    document.chunk_count = len(created)
    db.add(document)

    db.commit()

    for c in created:
        db.refresh(c)

    return created