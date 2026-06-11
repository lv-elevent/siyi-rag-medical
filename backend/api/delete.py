import logging
import os
from fastapi import APIRouter, HTTPException, status, Depends

from backend.core.logger_config import setup_logger
from backend.core.security import get_current_user
from backend.models.knowledge import DeleteDocumentRequest, DeleteDocumentResponse
from backend.repositories.vector_repository import vector_repository
from backend.database.session import get_db
from backend.database.models import Document, DocumentChunk, KnowledgeBaseDocument

logger = setup_logger(__name__, logging.INFO)

router = APIRouter()


@router.post("/knowledge/document/delete", response_model=DeleteDocumentResponse)
async def delete_document(
    request: DeleteDocumentRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
) -> DeleteDocumentResponse:
    document_id = request.document_id  # int

    if document_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="document_id 不能为空"
        )

    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )

    try:
        # 1) 删除向量库（doc.id 即为向量 document_id 的组成部分）
        vector_document_id = f"doc_{doc.id}"
        deleted_count = vector_repository.delete_by_document_id(
            document_id=vector_document_id,
            user_id=current_user.id,
        )

        # 2) 先删依赖子表，避免 ORM 把外键置空触发 NOT NULL 错误
        db.query(KnowledgeBaseDocument).filter(
            KnowledgeBaseDocument.document_id == doc.id,
            KnowledgeBaseDocument.user_id == current_user.id,
        ).delete(synchronize_session=False)

        db.query(DocumentChunk).filter(
            DocumentChunk.document_id == doc.id,
            DocumentChunk.user_id == current_user.id,
        ).delete(synchronize_session=False)

        # 3) 删除本地上传文件（硬删除）
        if doc.file_path and os.path.exists(doc.file_path):
            os.remove(doc.file_path)

        # 4) 再删主表 document
        db.delete(doc)
        db.commit()

        logger.info(
            "[delete] 文档删除完成 doc_id=%s vector_document_id=%s deleted_chunks=%s",
            document_id, vector_document_id, deleted_count,
        )

        return DeleteDocumentResponse(
            status="success",
            message="文档删除成功",
            document_id=document_id
        )

    except HTTPException as http_exc:
        db.rollback()
        raise http_exc
    except Exception as exc:
        db.rollback()
        logger.error(f"[delete] 删除文档失败: {repr(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除文档失败，请稍后重试"
        )