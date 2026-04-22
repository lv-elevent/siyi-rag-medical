"""
医疗查询改写器（C2完整版）
职责：
- 同义词扩展
- 概念补全
- 基于 query_type 的定向增强
- 标准结构输出
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


# ================= 同义词 =================

SYMPTOM_EXPANSIONS = {
    "头疼": ["头痛", "头部疼痛"],
    "发烧": ["发热", "体温升高"],
    "拉肚子": ["腹泻"],
    "胸口痛": ["胸痛"],
}

DISEASE_EXPANSIONS = {
    "高血压": ["血压升高"],
    "糖尿病": ["高血糖"],
}

DRUG_EXPANSIONS = {
    "布洛芬": ["芬必得"],
    "对乙酰氨基酚": ["泰诺"],
}


# ================= 核心工具 =================

def _expand(query: str) -> str:
    expanded = set()

    for d in [SYMPTOM_EXPANSIONS, DISEASE_EXPANSIONS, DRUG_EXPANSIONS]:
        for k, v in d.items():
            if k in query:
                expanded.update(v)

    if expanded:
        return f"{query} {' '.join(list(expanded)[:3])}"

    return query


def _add_intent_context(query: str, query_type: str) -> str:
    if query_type == "symptom":
        return f"{query} 原因 缓解方法 是否需要就医"

    if query_type == "drug":
        return f"{query} 副作用 禁忌 用法 用量"

    if query_type == "disease":
        return f"{query} 症状 治疗方法 预防"

    return query


def _normalize(query: str) -> str:
    return (
        query.replace("头疼", "头痛 头疼")
        .replace("拉肚子", "腹泻")
    )


def _limit(q: str, max_len: int = 80) -> str:
    return q[:max_len].strip()


# ================= 主函数 =================

def rewrite_medical_question(query: str, query_type: str) -> Dict[str, Any]:

    query = (query or "").strip()

    result = {
        "original_query": query,
        "rewritten_query": query,
        "query_type": query_type,
        "rewrite_strategy": "preserve"
    }

    if not query or len(query) <= 2:
        result["rewrite_strategy"] = "invalid"
        return result

    if query_type == "invalid":
        result["rewrite_strategy"] = "invalid"
        return result

    if query_type == "emergency":
        rewritten = _normalize(query)
        result["rewritten_query"] = _limit(rewritten)
        result["rewrite_strategy"] = "emergency"
        return result

    # ====== C2核心链路 ======
    rewritten = query
    rewritten = _normalize(rewritten)
    rewritten = _expand(rewritten)
    rewritten = _add_intent_context(rewritten, query_type)
    rewritten = _limit(rewritten)

    if rewritten != query:
        result["rewrite_strategy"] = "enhanced"

    result["rewritten_query"] = rewritten
    return result