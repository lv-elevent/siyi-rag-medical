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
import hashlib

# logger
_is_dev = os.getenv("ENVIRONMENT", "development") == "development"
logger = setup_logger(__name__, level=logging.DEBUG if _is_dev else logging.INFO)
debug_logger = setup_logger(
    f"{__name__}.debug",
    level=logging.DEBUG if _is_dev else logging.WARNING
)


def split_for_embedding(text: str, max_len: int = 400) -> list[str]:
    """
    将长文本进一步切分，保证 embedding 输入不超长。
    使用字符级近似（比 token 更保守）。
    """
    text = (text or "").strip()
    if not text:
        return []

    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + max_len
        part = text[start:end].strip()
        if part:
            chunks.append(part)
        start = end

    return chunks


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

        # 3️⃣ embedding 前做长度保护：避免超过模型输入上限
        chunk_texts = [c["text"] for c in normalized_chunks]

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

        safe_chunks: list[str] = []
        safe_metadatas: list[dict] = []
        safe_chunk_records: list[dict] = []
        safe_chunk_index = 0

        for text, meta in zip(chunk_texts, metadatas):
            split_texts = split_for_embedding(text, max_len=400)
            for idx, t in enumerate(split_texts):
                new_meta = meta.copy()
                new_meta["sub_chunk"] = idx
                new_meta["parent_chunk_index"] = meta.get("chunk_index")
                # 保证向量 chunk_index 全局唯一，避免同文档 ID 冲突
                new_meta["chunk_index"] = safe_chunk_index

                safe_chunks.append(t)
                safe_metadatas.append(new_meta)
                safe_chunk_records.append({
                    "text": t,
                    "chunk_index": safe_chunk_index,
                })
                safe_chunk_index += 1

        logger.info(
            "[embedding_guard] before=%s after=%s",
            len(chunk_texts),
            len(safe_chunks),
        )

        if not safe_chunks:
            raise ValueError("embedding 输入为空（safe_chunks）")

        embeddings = embed_texts(safe_chunks)

        if len(embeddings) != len(safe_chunks):
            raise ValueError("embedding 数量与安全分块数量不一致")

        logger.info(
            "[document_processor] embedding 模型=%s 维度=%s",
            EMBEDDING_MODEL,
            len(embeddings[0]) if embeddings else 0
        )

        # 5️⃣ 写入向量库（🔥带 metadata）
        vector_repository.add_chunks(
            document_id=document_id,
            filename=filename,
            chunks=safe_chunk_records,
            embeddings=embeddings,
            metadatas=safe_metadatas,
        )

        # 6️⃣ 计算文件哈希（用于后续去重查询）
        _file_hash = hashlib.sha256()
        with open(file_path, "rb") as _f:
            for _chunk in iter(lambda: _f.read(8192), b""):
                _file_hash.update(_chunk)
        file_hash = _file_hash.hexdigest()

        # 元数据已通过 MySQL documents 表持久化，无需额外的 JSON registry
        logger.info("[document_processor] 文档处理完成 file_hash=%s", file_hash[:16])

        return {
            "status": "success",
            "document_id": document_id,
            "filename": filename,
            "total_chunks": len(safe_chunk_records),
            "total_text_length": len(raw_text),
            "chunks": safe_chunk_records,
        }

    except Exception as exc:
        logger.error(f"[document_processor] 处理失败: {repr(exc)}", exc_info=True)
        raise