import logging
from typing import List, Dict

from backend.core.llm_client import get_llm_client

logger = logging.getLogger(__name__)


def rerank_with_llm(question: str, results: List[Dict]) -> List[Dict]:
    """
    使用 LLM 对候选结果重新排序（简易 CrossEncoder）
    """

    if not results:
        return results

    client = get_llm_client()

    scored_results = []

    for item in results:
        text = item.get("text", "")

        prompt = f"""
请判断下面内容与问题的相关性（0-10分）：

问题：
{question}

内容：
{text[:300]}

只输出一个数字（0-10），不要解释：
"""

        try:
            response = client.chat.completions.create(
                model="Qwen/Qwen2.5-7B-Instruct",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )

            score_text = response.choices[0].message.content.strip()

            score = float(score_text)

        except Exception:
            score = 0

        item["rerank_score"] = score
        scored_results.append(item)

    # 按分数排序（高→低）
    scored_results.sort(key=lambda x: x["rerank_score"], reverse=True)

    logger.info("[rerank] 排序完成")

    return scored_results