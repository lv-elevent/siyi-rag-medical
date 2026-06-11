import os
import hashlib
import logging

from backend.core import config
from fastapi import APIRouter, File, HTTPException, UploadFile, status, Depends, Form

from backend.models.upload import UploadResponse
from backend.services.document_processor import process_document
from backend.core.security import get_current_user
from backend.database.session import get_db
from backend.database.models import Document
from backend.services.knowledge_service import (
    get_or_create_default_kb,
    get_or_resolve_kb,
    create_document,
    update_document_status,
    create_chunks,
    ensure_document_link,
)
from backend.core.logger_config import setup_logger

logger = setup_logger(__name__, logging.INFO)

router = APIRouter()

UPLOAD_DIR = config.UPLOAD_DIR

# ✅ 支持的文件类型
ALLOWED_EXTENSIONS = [".pdf", ".txt", ".md", ".docx"]


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    knowledge_base_id: int | None = Form(default=None),
    force_upload: bool = Form(default=False),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
) -> UploadResponse:
    # 1️⃣ 基础校验
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名不能为空",
        )

    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 PDF / TXT / MD / DOCX 文件",
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    try:
        # =========================
        # 2️⃣ 读取文件（不落盘）
        # =========================
        contents = await file.read()

        # =========================
        # 3️⃣ 计算 hash（去重 — 直接查 MySQL）
        # =========================
        file_hash = hashlib.sha256(contents).hexdigest()

        if not force_upload:
            existing_doc = (
                db.query(Document)
                .filter(
                    Document.file_hash == file_hash,
                    Document.user_id == current_user.id,
                )
                .first()
            )
            if existing_doc:
                logger.info("[upload] 文件已存在 doc_id=%s", existing_doc.id)
                return UploadResponse(
                    document_id=f"doc_{existing_doc.id}",
                    filename=existing_doc.filename,
                    status="success",
                    message="文件已存在，直接使用已有知识库",
                )
        logger.info("[upload] hash=%s", file_hash[:16])

        # =========================
        # 4️⃣ 先创建 DB 记录（获取 ID 用于文件命名和向量 ID）
        # =========================
        kb = get_or_resolve_kb(db, knowledge_base_id, current_user)

        document = create_document(
            db, kb,
            filename=file.filename,
            file_path="",  # 稍后更新
            file_hash=file_hash,
            file_size=len(contents),
        )
        vector_document_id = f"doc_{document.id}"

        global_kb = get_or_create_default_kb(db, current_user)
        ensure_document_link(db, global_kb.id, document.id, current_user.id)
        ensure_document_link(db, kb.id, document.id, current_user.id)

        # =========================
        # 5️⃣ 保存文件到磁盘
        # =========================
        saved_filename = f"{vector_document_id}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, saved_filename)

        with open(file_path, "wb") as f:
            f.write(contents)

        # 更新文件路径
        document.file_path = file_path
        db.commit()

        logger.info(f"[upload] 文件保存完成: {file.filename}")

    except Exception as exc:
        logger.error(f"[upload] 文件处理失败: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件处理失败: {str(exc)}"
        )

    # =========================
    # 6️⃣ 文档处理（解析+embedding+入库）
    # =========================
    try:
        logger.info(f"[upload] 开始处理文档: {file.filename}")

        # 执行解析、分块、embedding 并写入向量库
        process_result = process_document(
            file_path=file_path,
            filename=file.filename,
            document_id=vector_document_id,
            user_id=current_user.id,
            kb_id=kb.id,
            doc_db_id=document.id,
        )

        logger.info(f"[upload] 文档处理完成: {process_result}")

        # 把 chunks 写入数据库的 document_chunks 表
        chunks = process_result.get("chunks", [])

        # 🔥 强制检查
        if not chunks:
            raise Exception("文档解析失败：没有生成任何 chunks")

        texts = []
        for c in chunks:
            if isinstance(c, dict):
                text = c.get("text")
            else:
                text = str(c)

            if text:
                texts.append(text)

        # 写数据库
        create_chunks(db, document, texts)

        logger.info(f"[upload] 写入 chunks 数量: {len(texts)}")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[upload] 文档处理失败: {str(exc)}", exc_info=True)

        # ❗ 出错删除文件
        if os.path.exists(file_path):
            os.remove(file_path)

        # 如果已经创建了 document 记录，将其状态设置为 failed（若可用）
        try:
            if 'document' in locals():
                update_document_status(db, document, "failed")
        except Exception:
            logger.exception("更新 document 状态为 failed 时出错")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文档处理失败: {str(exc)}"
        )

    # 7️⃣ 返回
    return UploadResponse(
        document_id=vector_document_id,
        filename=file.filename,
        status="success",
        message="上传成功",
    )