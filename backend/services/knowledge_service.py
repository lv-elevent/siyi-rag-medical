from typing import List
from datetime import datetime
from uuid import uuid4

from backend.database.models import KnowledgeBase, Document, DocumentChunk, KnowledgeBaseDocument


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


def get_or_create_global_kb(db, user):
    return get_or_create_default_kb(db, user)


def create_document(db, kb: KnowledgeBase, filename: str, file_path: str) -> Document:
    doc = Document(
        knowledge_base_id=kb.id,
        user_id=kb.user_id,
        filename=filename,
        file_path=file_path,
        status="processing",
        created_at=datetime.utcnow()
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