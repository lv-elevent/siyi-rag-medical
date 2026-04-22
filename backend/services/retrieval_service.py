from typing import List, Dict, Any, Optional
import logging

from backend.core.embedding_client import embed_text, embed_texts, EMBEDDING_MODEL
from backend.repositories.vector_repository import query_similar_chunks
from backend.services.query_rewriter import rewrite_medical_question

logger = logging.getLogger(__name__)

_query_embedding_cache: Dict[str, List[float]] = {}


def get_cached_embedding(question: str) -> List[float]:
    q = question.strip()

    if q in _query_embedding_cache:
        return _query_embedding_cache[q]

    embedding = embed_text(q)
    _query_embedding_cache[q] = embedding
    return embedding


# ================= C3动态策略 =================

def get_dynamic_top_k(question: str, query_type: str) -> int:
    if query_type == "emergency":
        return 3
    if query_type == "symptom":
        return 8
    if query_type == "disease":
        return 6
    if query_type == "drug":
        return 5
    if query_type == "general":
        return 4
    if query_type == "invalid":
        return 0

    return 4


def get_dynamic_margin(question: str) -> float:
    l = len(question)
    if l < 6:
        return 0.08
    if l <= 15:
        return 0.1
    return 0.12


# ================= D阶段：Rerank =================

def rerank_results(
    question: str,
    results: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    D阶段轻量 rerank：
    综合 distance + 文本长度 + query overlap
    """
    if not results:
        return []

    q_words = set(question.lower().split())

    scored_results = []

    for item in results:
        text = item.get("text", "")
        distance = item.get("distance", 999)

        # 文本长度分
        length_score = min(len(text) / 300, 1.0)

        # query overlap
        overlap = 0
        if text:
            text_lower = text.lower()
            overlap = sum(1 for w in q_words if w and w in text_lower)

        overlap_score = overlap * 0.1

        # distance 越小越好
        semantic_score = max(0, 1 - distance)

        final_score = (
            semantic_score * 0.7
            + length_score * 0.2
            + overlap_score * 0.1
        )

        item["rerank_score"] = round(final_score, 4)
        scored_results.append(item)

    scored_results.sort(
        key=lambda x: x.get("rerank_score", 0),
        reverse=True
    )

    logger.info(
        "[D-rerank] rerank scores=%s",
        [x.get("rerank_score") for x in scored_results[:5]]
    )

    return scored_results


# ================= 新增：基础检索（带 user_id 过滤） =================

def retrieve_chunks(
    query: str,
    user_id: int,
    top_k: int = 5,
    document_id: Optional[str] = None,
    knowledge_base_id: Optional[int] = None,
    allowed_doc_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """
    基础 RAG 检索：
    - 根据 query 生成 embedding
    - 按 user_id 做隔离
    - 可选 document_id 进一步过滤
    """
    if not query or not isinstance(query, str):
        return []

    query = query.strip()
    if not query:
        return []

    embedding = get_cached_embedding(query)

    results = query_similar_chunks(
        query_embedding=embedding,
        top_k=top_k,
        document_id=document_id,
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        allowed_doc_ids=allowed_doc_ids,
    )

    logger.info(
        "[retrieve_chunks] model=%s user_id=%s document_id=%s knowledge_base_id=%s top_k=%s hit=%s",
        EMBEDDING_MODEL,
        user_id,
        document_id,
        knowledge_base_id,
        top_k,
        len(results)
    )

    return results


# ================= 主检索（保留原逻辑 + 增加 user_id） =================

def semantic_search(
    question: str,
    top_k: int = 3,
    document_id: str = None,
    query_type: str = "general",
    user_id: int = None,   # ❗ 改成非 Optional
    knowledge_base_id: Optional[int] = None,
    allowed_doc_ids: Optional[List[int]] = None,
):
    if user_id is None:
        raise ValueError("user_id is required for semantic_search")

    if not question or not isinstance(question, str):
        return []

    question = question.strip()

    # ===== C2：Rewrite =====
    rewrite_result = rewrite_medical_question(question, query_type)
    rewritten = rewrite_result["rewritten_query"]

    logger.info(f"[rewrite] {question} -> {rewritten}")

    # ===== C3：动态策略 =====
    dynamic_top_k = get_dynamic_top_k(rewritten, query_type)
    final_top_k = max(top_k or 0, dynamic_top_k)
    if final_top_k <= 0:
        return []

    # D阶段：召回更多候选给 rerank
    candidate_k = final_top_k + 5

    # ===== embedding =====
    embedding = get_cached_embedding(rewritten)

    results = query_similar_chunks(
        query_embedding=embedding,
        top_k=candidate_k,
        document_id=document_id,
        user_id=user_id,   
        knowledge_base_id=knowledge_base_id,
        allowed_doc_ids=allowed_doc_ids,
    )

    logger.info("=" * 80)
    logger.info("[RETRIEVAL RESULTS START]")
    for i, item in enumerate(results):
        content = item.get("text", "")
        distance = item.get("distance", None)
        metadata = item.get("metadata", {})
        logger.info(
            "[chunk %s] distance=%s document_id=%s chunk_index=%s user_id=%s knowledge_base_id=%s kb_id=%s",
            i,
            distance,
            metadata.get("document_id"),
            metadata.get("chunk_index"),
            metadata.get("user_id"),
            knowledge_base_id,
            metadata.get("kb_id"),
        )
        logger.info(content[:500])
        logger.info("-" * 50)
    logger.info("[RETRIEVAL RESULTS END]")
    logger.info("=" * 80)

    if not results:
        return []

    # ===== Gate =====
    top_distance = results[0].get("distance", 999)

    if query_type in ["symptom", "disease", "drug"]:
        threshold_gate = 0.45
    else:
        threshold_gate = 0.6

    if top_distance > threshold_gate:
        return []

    # ===== 动态过滤 =====
    valid_distances = [
        x["distance"]
        for x in results
        if x.get("distance") is not None
    ]

    if not valid_distances:
        return []

    min_distance = min(valid_distances)

    margin = get_dynamic_margin(rewritten)
    threshold = min_distance + margin

    filtered = [
        x for x in results
        if x.get("distance") is not None
        and x["distance"] <= threshold
    ]

    if not filtered:
        filtered = [results[0]]

    # ===== 去重 =====
    seen = set()
    dedup = []

    for item in filtered:
        key = (
            item.get("metadata", {}).get("document_id"),
            item.get("metadata", {}).get("chunk_index"),
        )
        if key in seen:
            continue
        seen.add(key)
        dedup.append(item)

    # ===== D阶段核心：rerank =====
    reranked = rerank_results(rewritten, dedup)

    return reranked[:final_top_k]