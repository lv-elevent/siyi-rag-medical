import os
import logging
from openai import OpenAI
from dotenv import load_dotenv
from backend.core import config

logger = logging.getLogger(__name__)

load_dotenv()


def get_llm_client():
    api_key = config.OPENAI_API_KEY
    base_url = config.OPENAI_BASE_URL

    if not api_key:
        raise RuntimeError("缺少 OPENAI_API_KEY")

    return OpenAI(api_key=api_key, base_url=base_url)


import os
from typing import Dict, Optional

# =========================
# 🧠 Prompt 构建（最终版）
# =========================

def build_prompt(
    question: str,
    context: str,
    query_type: str = "general",
    user_info: Optional[Dict] = None
) -> str:
    context = (context or "").strip()
    question = (question or "").strip()

    # ===== 用户信息增强（轻量，不干扰结构）=====
    user_block = ""
    if user_info:
        parts = []
        if user_info.get("age"):
            parts.append(f"年龄：{user_info['age']}")
        if user_info.get("gender"):
            parts.append(f"性别：{user_info['gender']}")
        if user_info.get("medical_history"):
            parts.append(f"病史：{user_info['medical_history']}")

        if parts:
            user_block = "【用户信息】\n" + "，".join(parts) + "\n"

    q = question
    list_keywords = ["有哪些", "包括", "分类", "组成", "构成", "分型", "类型"]
    impact_keywords = ["危害", "影响", "风险", "并发症"]
    definition_keywords = ["是什么", "什么是", "定义", "概念", "解释", "说明"]

    answer_focus = "请用自然聊天语气回答，先直接给结论，再简要解释。"
    if query_type == "emergency":
        answer_focus = "请先判断紧急程度，再给2到4条可执行建议，并提醒何时尽快就医。"
    elif query_type == "drug":
        answer_focus = "请优先说明用途、用法和注意事项；如知识库有风险或副作用要明确写出。"
    elif query_type == "followup":
        answer_focus = "这是追问场景，请直接承接上文给结论，再补充必要解释。"
    elif any(k in q for k in list_keywords):
        answer_focus = "这是列举型问题，请用最多4条精炼要点回答，不要凑数量。"
    elif any(k in q for k in impact_keywords):
        answer_focus = "这是影响/危害型问题，请先讲核心影响，再给关键风险点。"
    elif any(k in q for k in definition_keywords):
        answer_focus = "这是定义型问题，请先一句话解释概念，再补充关键理解点。"

    return f"""
你是专业医疗知识库智能助手。

【核心约束】
1. 必须严格依据“知识库内容”回答，不允许补充外部知识，不允许推测或编造。
2. 如果知识库不足以回答，且无法给出有效内容时，仅输出：知识库未收录相关内容
3. 不要输出多级标题（如##、###），不要使用“核心内容/关键要点/补充说明”这类模板词。

【目标风格（必须）】
1. 用自然语言聊天风格回答，不要写成教科书或PPT。
2. 开头先用一句话直接回答问题。
3. 中间给一小段解释，控制在2到3行。
4. 如需列点，使用简短列表（最多4条），每条尽量短。
5. 结尾可用一句通俗总结（可选）。
6. 全文保持轻量、顺畅、可读，不要堆砌分块与格式。

【当前问题重点】
{answer_focus}

【知识库内容】
{context}

【用户问题】
{question}

{user_block}
"""



# =========================
# 🧠 非流式调用
# =========================

def generate_answer_with_llm(
    question: str,
    context: str,
    query_type: str = "general"
) -> str:
    client = get_llm_client()
    model = config.LLM_MODEL

    prompt = build_prompt(question, context, query_type=query_type)

    system_prompt = """
你是专业医疗知识库智能助手。

必须遵守：
1. 严格基于知识库内容回答，不得使用外部知识，不得编造。
2. 当知识库整体信息不足且无法有效回答时，只输出：知识库未收录相关内容
3. 风格要自然、轻量、像聊天，不要教科书腔。
4. 禁止使用多级标题（##/###）和模板化分段词（如“核心内容/关键要点/补充说明”）。
5. 结构优先：一句直答 + 一小段解释（2-3行）+ 最多4条短列表（必要时）。
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
        )

        return (response.choices[0].message.content or "").strip()

    except Exception:
        return "系统异常，请稍后重试。"



# =========================
# 🧠 流式调用（优化版）
# =========================

def generate_answer_with_llm_stream(
    question: str,
    context: str,
    query_type: str = "general"
):
    client = get_llm_client()
    model = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")

    prompt = build_prompt(question, context, query_type=query_type)

    system_prompt = """
你是专业医疗知识库智能助手。

必须遵守：
1. 严格基于知识库内容回答，不得使用外部知识，不得编造。
2. 当知识库整体信息不足且无法有效回答时，只输出：知识库未收录相关内容
3. 风格要自然、轻量、像聊天，不要教科书腔。
4. 禁止使用多级标题（##/###）和模板化分段词（如“核心内容/关键要点/补充说明”）。
5. 结构优先：一句直答 + 一小段解释（2-3行）+ 最多4条短列表（必要时）。
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            stream=True
        )

        for chunk in response:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    except Exception:
        yield "系统异常，请稍后重试。"