from sentence_transformers import CrossEncoder
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

# 全局加载（只加载一次）
_model = None


def get_model():
    global _model
    if _model is None:
        logger.info("[reranker] 加载本地 reranker 模型...")
        _model = CrossEncoder("BAAI/bge-reranker-base")
    return _model


def rerank_local(question: str, results: List[Dict]) -> List[Dict]:
    """
    本地 rerank（CrossEncoder）

    Args:
        question: 用户问题
        results: 检索结果 [{"text": "..."}]

    Returns:
        排序后的结果
    """

    if not results:
        return results

    model = get_model()

    pairs = [(question, item["text"]) for item in results]

    scores = model.predict(pairs)

    # 写入分数
    for item, score in zip(results, scores):
        item["rerank_score"] = float(score)

    # 排序（越大越相关）
    results = sorted(results, key=lambda x: x["rerank_score"], reverse=True)

    logger.info("[rerank] 本地 rerank 完成")

    return results