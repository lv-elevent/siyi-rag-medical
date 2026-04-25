import os
import logging
from typing import List, Dict, Any, Optional

import chromadb
from backend.core import config

logger = logging.getLogger(__name__)


class VectorRepository:
    def __init__(self) -> None:
        self.client = chromadb.PersistentClient(path=config.CHROMA_PERSIST_DIR)
        collection_name = config.CHROMA_COLLECTION_NAME

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

        logger.info(
            "[vector_repository] collection 初始化完成 name=%s",
            self.collection.name
        )

    def reset_collection(self) -> None:
        """清空整个集合"""
        self.client.delete_collection(name=self.collection.name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection.name,
            metadata={"hnsw:space": "cosine"}
        )

    # 🔥 修复版本（兼容 document_processor）
    def add_chunks(
        self,
        document_id: str,
        filename: str,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,  # 🔥 新增
        user_id: Optional[int] = None,
        kb_id: Optional[int] = None,
        doc_db_id: Optional[int] = None,
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks 数量与 embeddings 数量不一致")

        ids = []
        documents = []
        final_metadatas = []

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # 🔥 兼容两种格式（index 或 chunk_index）
            chunk_index = chunk.get("chunk_index", chunk.get("index", i))
            chunk_text = chunk["text"]

            ids.append(f"{document_id}_chunk_{chunk_index}")
            documents.append(chunk_text)

            # 🔥 优先使用传入的 metadatas（新逻辑）
            if metadatas:
                meta = metadatas[i]
            else:
                # fallback（兼容旧逻辑）
                meta = {
                    "document_id": document_id,
                    "filename": filename,
                    "chunk_index": chunk_index,
                }

                if user_id is not None:
                    meta["user_id"] = user_id
                if kb_id is not None:
                    meta["kb_id"] = kb_id
                if doc_db_id is not None:
                    meta["doc_id"] = doc_db_id

            final_metadatas.append(meta)

        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=final_metadatas,
            ids=ids
        )

        logger.info(
            "[vector_repository] 写入完成 document_id=%s chunks=%s",
            document_id,
            len(documents)
        )

    def query(
        self,
        query_embedding: List[float],
        top_k: int = 3,
        document_id: Optional[str] = None,
        user_id: int = None,
        knowledge_base_id: Optional[int] = None,
        allowed_doc_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:

        if user_id is None:
            raise ValueError("user_id is required for query (multi-tenant isolation)")

        query_kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
        }

        conditions = [{"user_id": user_id}]

        if document_id is not None:
            doc_value = str(document_id).strip()
            if doc_value:
                # 兼容两种前端传值：
                # 1) 向量 document_id（如 doc_xxx） -> 过滤 metadata.document_id
                # 2) DB 主键 document_id（如 31）    -> 过滤 metadata.doc_id
                if doc_value.startswith("doc_"):
                    conditions.append({"document_id": doc_value})
                elif doc_value.isdigit():
                    conditions.append({"doc_id": int(doc_value)})
                else:
                    # 保守兜底：按原字段过滤，避免改变未知旧调用行为
                    conditions.append({"document_id": doc_value})

        if len(conditions) == 1:
            query_kwargs["where"] = conditions[0]
        else:
            query_kwargs["where"] = {"$and": conditions}

        results = self.collection.query(**query_kwargs)

        distances = results.get("distances", [])
        metadatas = results.get("metadatas", [])

        if distances and distances[0]:
            for i, distance in enumerate(distances[0]):
                metadata = metadatas[0][i] if metadatas and metadatas[0] else {}
                logger.debug(
                    "[vector_repository] rank=%s distance=%s doc=%s chunk=%s user=%s",
                    i + 1,
                    distance,
                    metadata.get("document_id"),
                    metadata.get("chunk_index"),
                    metadata.get("user_id"),
                )

        return results

    def delete_by_document_id(self, document_id: str, user_id: int) -> int:
        if user_id is None:
            raise ValueError("user_id is required for delete_by_document_id")

        results = self.collection.get(
            where={
                "$and": [
                    {"document_id": document_id},
                    {"user_id": user_id},
                ]
            }
        )

        ids = results.get("ids", [])

        if not ids:
            logger.info("[sources_cleanup] removed chunks count=0 document_id=%s", document_id)
            return 0

        self.collection.delete(
            where={
                "$and": [
                    {"document_id": document_id},
                    {"user_id": user_id},
                ]
            }
        )

        logger.info(
            "[sources_cleanup] removed chunks count=%s document_id=%s",
            len(ids),
            document_id,
        )

        return len(ids)


vector_repository = VectorRepository()


def query_similar_chunks(
    query_embedding: List[float],
    top_k: int = 3,
    document_id: Optional[str] = None,
    user_id: Optional[int] = None,  # 🔥 下一阶段用
    knowledge_base_id: Optional[int] = None,
    allowed_doc_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    results = vector_repository.query(
        query_embedding=query_embedding,
        top_k=top_k,
        document_id=document_id,
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        allowed_doc_ids=allowed_doc_ids,
    )

    documents = results.get("documents", [])
    metadatas = results.get("metadatas", [])
    distances = results.get("distances", [])

    if not documents or not documents[0]:
        return []

    docs = documents[0]
    metas = metadatas[0] if metadatas else []
    dists = distances[0] if distances else []

    combined = []
    for i, doc in enumerate(docs):
        combined.append({
            "text": doc,
            "metadata": metas[i] if i < len(metas) else {},
            "distance": dists[i] if i < len(dists) else None,
        })
    for i, item in enumerate(combined, start=1):
        meta = item.get("metadata", {}) or {}
        preview = (item.get("text", "") or "").replace("\n", " ")[:120]
        logger.debug(
            "[vector_repository] raw_order rank=%s distance=%s filename=%s chunk_index=%s preview=%r",
            i,
            item.get("distance"),
            meta.get("filename"),
            meta.get("chunk_index"),
            preview,
        )

    # 去重
    seen_texts = set()
    unique_results = []

    for item in combined:
        text = item["text"]
        if text not in seen_texts:
            seen_texts.add(text)
            unique_results.append(item)

    # 排序
    unique_results.sort(
        key=lambda x: x["distance"] if x["distance"] is not None else float("inf")
    )
    for i, item in enumerate(unique_results, start=1):
        meta = item.get("metadata", {}) or {}
        preview = (item.get("text", "") or "").replace("\n", " ")[:120]
        logger.debug(
            "[vector_repository] sorted_order rank=%s distance=%s filename=%s chunk_index=%s preview=%r",
            i,
            item.get("distance"),
            meta.get("filename"),
            meta.get("chunk_index"),
            preview,
        )

    return unique_results[:top_k]