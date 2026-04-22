"""文档处理器 - 解析 → 分块 → embedding → 存储"""

import logging
import os
from datetime import datetime
from typing import Dict, Any

from backend.services.document_parser import parse_document
from backend.services.text_chunker import split_text_into_chunks
from backend.core.embedding_client import embed_texts, EMBEDDING_MODEL
from backend.core.logger_config import setup_logger
from backend.repositories.vector_repository import vector_repository
from backend.services.knowledge_registry import calculate_file_hash, registry_add

# logger
_is_dev = os.getenv("ENVIRONMENT", "development") == "development"
logger = setup_logger(__name__, level=logging.DEBUG if _is_dev else logging.INFO)
debug_logger = setup_logger(
    f"{__name__}.debug",
    level=logging.DEBUG if _is_dev else logging.WARNING
)


def process_document(
    file_path: str,
    filename: str,
    document_id: str,
    user_id: int | None = None,
    kb_id: int | None = None,
    doc_db_id: int | None = None,
) -> Dict[str, Any]:
    try:
        # 1️⃣ 文档解析
        logger.info(f"[document_processor] 开始解析文档: {filename}")
        raw_text = parse_document(file_path)

        logger.info(f"[document_processor] 解析完成，文本长度: {len(raw_text)}")

        if not raw_text or not raw_text.strip():
            raise ValueError("文档解析结果为空")

        debug_logger.debug(f"[DEBUG] 文本预览: {raw_text[:300]}")

        # 2️⃣ 分块
        chunks = split_text_into_chunks(raw_text, chunk_size=500, overlap=50)

        logger.info(f"[document_processor] 分块完成: {len(chunks)} chunks")

        if not chunks:
            raise ValueError("分块失败")

        # 🔥 标准化 chunks（确保是 dict 且有 text）
        normalized_chunks = []
        for i, c in enumerate(chunks):
            if isinstance(c, dict):
                text = c.get("text")
            else:
                text = str(c)

            if not text:
                continue

            normalized_chunks.append({
                "text": text,
                "chunk_index": i,
            })

        if not normalized_chunks:
            raise ValueError("有效 chunks 为空")

        # 3️⃣ embedding
        chunk_texts = [c["text"] for c in normalized_chunks]
        embeddings = embed_texts(chunk_texts)

        if len(embeddings) != len(normalized_chunks):
            raise ValueError("embedding 数量不一致")

        logger.info(
            "[document_processor] embedding 模型=%s 维度=%s",
            EMBEDDING_MODEL,
            len(embeddings[0]) if embeddings else 0
        )

        # 4️⃣ 构建 metadata（🔥核心修复）
        metadatas = []
        for i, c in enumerate(normalized_chunks):
            metadatas.append({
                "document_id": document_id,
                "filename": filename,
                "chunk_index": i,

                # 🔥 关键三件套
                "user_id": user_id,
                "kb_id": kb_id,
                "doc_id": doc_db_id,
            })

        # 5️⃣ 写入向量库（🔥带 metadata）
        vector_repository.add_chunks(
            document_id=document_id,
            filename=filename,
            chunks=normalized_chunks,
            embeddings=embeddings,
            metadatas=metadatas,  
        )

        # 6️⃣ registry
        file_hash = calculate_file_hash(file_path)

        registry_add(
            file_hash=file_hash,
            metadata={
                "document_id": document_id,
                "filename": filename,
                "user_id": user_id,   
                "kb_id": kb_id,
                "doc_id": doc_db_id,
                "total_chunks": len(normalized_chunks),
                "total_text_length": len(raw_text),
                "created_at": datetime.now().isoformat()
            }
        )

        logger.info("[document_processor] 文档处理完成")

        return {
            "status": "success",
            "document_id": document_id,
            "filename": filename,
            "total_chunks": len(normalized_chunks),
            "total_text_length": len(raw_text),
            "chunks": normalized_chunks,
        }

    except Exception as exc:
        logger.error(f"[document_processor] 处理失败: {repr(exc)}", exc_info=True)
        raise