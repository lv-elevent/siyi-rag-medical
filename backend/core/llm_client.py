import os
import logging
from openai import OpenAI
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()


def get_llm_client():
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")

    if not api_key:
        raise RuntimeError("缺少 OPENAI_API_KEY")

    return OpenAI(api_key=api_key, base_url=base_url)


def build_prompt(
    question: str,
    context: str,
    query_type: str = "other",
    user_info: dict = None
) -> str:
    context = (context or "").strip()
    question = (question or "").strip()

    personalized_prompt = ""
    if user_info:
        age = user_info.get("age", "")
        gender = user_info.get("gender", "")
        medical_history = user_info.get("medical_history", "")

        if age:
            personalized_prompt += f"【用户年龄】{age}\n"
        if gender:
            personalized_prompt += f"【用户性别】{gender}\n"
        if medical_history:
            personalized_prompt += f"【病史】{medical_history}\n"

    if query_type == "emergency":
        return f"""
你是专业医疗问诊助手，请严格依据知识库回答，不允许补充外部知识，不允许推测。

【知识库内容】
{context}

【用户问题】
{question}

{personalized_prompt}

【回答要求】
1. 第一行明确告知紧急程度。
2. 第二部分给出具体应对建议。
3. 强调及时就医的重要性。
4. 语言简洁明确，控制在3到5句。
5. 若知识库整体信息不足，仅输出：知识库未收录相关内容
"""

    if query_type == "drug":
        return f"""
你是专业医疗问诊助手，请严格依据知识库回答，不允许补充外部知识，不允许推测。

【知识库内容】
{context}

【用户问题】
{question}

{personalized_prompt}

【回答要求】
1. 优先回答药物用途、用法、注意事项。
2. 如知识库提及副作用或风险，要明确说明。
3. 强调遵医嘱，不要自行调整剂量。
4. 语言专业清晰，控制在3到5句。
5. 若知识库整体信息不足，仅输出：知识库未收录相关内容
"""

    if query_type == "followup":
        return f"""
你是专业医疗问诊助手，请严格依据知识库回答，不允许补充外部知识，不允许猜测。

【知识库内容】
{context}

【用户问题】
{question}

{personalized_prompt}

【回答要求】
1. 第一行直接给出结论。
2. 后续补充必要解释和处理建议。
3. 必须保持专业、自然、简洁。
4. 禁止重复用户问题。
5. 禁止输出标题。
6. 控制在3到5句。
7. 若知识库整体信息不足，仅输出：知识库未收录相关内容
"""

    if query_type in {"disease", "symptom", "general", "medical", "knowledge"}:
        summary_keywords = [
            "危害", "症状", "原因", "并发症", "影响",
            "治疗", "治疗方法", "预防", "防范",
            "注意事项", "表现", "诊断", "定义",
            "概述", "介绍", "是什么", "什么是",
            "概念", "什么意思", "什么叫", "解释", "说明",
            "要素", "作用", "用途", "特点", "特征",
            "机制", "原理", "分类", "分型", "包括什么", "有哪些", "组成", "构成"
        ]
        is_summary = any(word in question for word in summary_keywords)

        list_keywords = [
            "要素", "组成", "构成", "包括", "包含", "有哪些",
            "分类", "分型", "种类", "类型", "分几种", "分几类"
        ]
        is_list_question = any(word in question for word in list_keywords)

        impact_keywords = ["危害", "影响", "风险", "并发症"]
        is_impact_question = any(word in question for word in impact_keywords)

        definition_keywords = [
            "是什么", "什么是", "什么意思", "什么叫", "概念", "定义", "解释", "说明", "介绍"
        ]
        is_definition_question = any(word in question for word in definition_keywords)

        if is_summary:
            # 1) 列举 / 组成 / 分类型
            if is_list_question:
                return f"""
你是专业医疗知识库智能问答助手。

你必须严格依据【知识库内容】回答，不允许补充外部知识，不允许推测。

【知识库内容】
{context}

【用户问题】
{question}

{personalized_prompt}

【回答规则】
1. 使用三级标题。
2. 按列举型方式回答，优先直接列出知识库中明确提到的项目。
3. 每个要点单独成段，语言简洁、专业、清晰。
4. 不要输出“简要概括定义”“补充特点说明”之类模板提示语。
5. 不要套用“风险 / 影响”或“处理建议”这类不适合当前问题的分段。
6. 如果知识库只支持列出2项或3项，就只列这些，不要凑数量。
7. 只有当整个问题都无法根据知识库回答时，才单独输出：知识库未收录相关内容。

【输出要求】
1. 使用三级标题。
2. 使用阿拉伯数字编号列表。
3. 每一项都必须严格按照下面格式输出：
   1. **项目名称**：项目说明
4. 不要输出“第一项名称”“这一项的具体含义”这类模板提示语。
5. 不要输出奇怪符号，不要把编号写成引号或特殊字符。
6. 如果知识库只明确提到 2 项，就只输出 2 项，不要凑第 3 项。
7. 只有当整个问题都无法根据知识库回答时，才单独输出：知识库未收录相关内容。

【标准格式示例】
### {question}

1. **项目A**：项目A的具体说明。
2. **项目B**：项目B的具体说明。
3. **项目C**：仅当知识库明确提到时再写；没有就省略。
"""

            # 2) 危害 / 影响型
            if is_impact_question:
                return f"""
你是专业医疗知识库智能问答助手。

你必须严格依据【知识库内容】回答，不允许补充外部知识，不允许推测。

【知识库内容】
{context}

【用户问题】
{question}

{personalized_prompt}

【回答规则】
1. 使用三级标题。
2. 优先输出2到3个最关键分点。
3. 每个分点不超过2句话。
4. 语言专业、自然、简洁。
5. 禁止重复原问题。
6. 只写知识库中明确能支持的内容。
7. 如果某个分点缺少足够依据，就直接省略，不要写“知识库未收录相关内容”。
8. 只有当整个问题都无法根据知识库回答时，才单独输出：知识库未收录相关内容。

【输出示例要求】
请严格仿照下面的结构形式输出，但不要照抄示例文字内容：

### {question}

**1. 核心危害**
概括最主要的危害或不良后果。

**2. 风险 / 影响**
补充风险、公共卫生影响、并发症或长期影响。

**3. 补充说明（如有）**
仅当知识库中确实有相关内容时再写；如果没有，这一部分直接省略。
"""

            # 3) 定义 / 概念型
            if is_definition_question:
                return f"""
你是专业医疗知识库智能问答助手。

你必须严格依据【知识库内容】回答，不允许补充外部知识，不允许推测。

【知识库内容】
{context}

【用户问题】
{question}

{personalized_prompt}

【回答规则】
1. 使用三级标题。
2. 优先输出2到3个最关键分点。
3. 每个分点不超过2句话。
4. 语言专业、自然、简洁。
5. 禁止重复原问题。
6. 只写知识库中明确能支持的内容。
7. 如果某个分点缺少足够依据，就直接省略，不要写“知识库未收录相关内容”。
8. 只有当整个问题都无法根据知识库回答时，才单独输出：知识库未收录相关内容。

【输出示例要求】
请严格仿照下面的结构形式输出，但不要照抄示例文字内容：

### {question}

**1. 核心内容**
简要概括定义、概念、主要内容或基本结论。

**2. 关键说明**
补充特点、作用、分类或重要说明。

**3. 补充说明（如有）**
仅当知识库中确实有相关内容时再写；如果没有，这一部分直接省略。
"""

            # 4) 其他总结型
            return f"""
你是专业医疗知识库智能问答助手。

你必须严格依据【知识库内容】回答，不允许补充外部知识，不允许推测。

【知识库内容】
{context}

【用户问题】
{question}

{personalized_prompt}

【回答规则】
1. 使用三级标题。
2. 优先输出2到3个最关键分点。
3. 每个分点不超过2句话。
4. 语言专业、自然、简洁。
5. 禁止重复原问题。
6. 只写知识库中明确能支持的内容。
7. 如果某个分点缺少足够依据，就直接省略，不要写“知识库未收录相关内容”。
8. 只有当整个问题都无法根据知识库回答时，才单独输出：知识库未收录相关内容。

【输出示例要求】
请严格仿照下面的结构形式输出，但不要照抄示例文字内容：

### {question}

**1. 核心内容**
简要概括主要结论。

**2. 关键说明**
补充特点、影响、机制或重要说明。

**3. 补充说明（如有）**
仅当知识库中确实有相关内容时再写；如果没有，这一部分直接省略。
"""

        # 非总结型 medical / knowledge 问题
        return f"""
你是专业医疗知识库智能问答助手。

你必须严格依据【知识库内容】回答，不允许补充外部知识，不允许推测。

【知识库内容】
{context}

【用户问题】
{question}

{personalized_prompt}

【回答规则】
1. 先直接回答核心结论。
2. 使用自然、专业、清晰的医生式表达。
3. 控制在2到4句话。
4. 禁止重复问题。
5. 禁止输出标题。
6. 只回答知识库中明确支持的内容。
7. 若知识库整体信息不足，仅输出：知识库未收录相关内容
"""

    # other
    return f"""
你是专业医疗知识库智能问答助手。

你必须严格依据【知识库内容】回答，不允许补充外部知识，不允许推测。

【知识库内容】
{context}

【用户问题】
{question}

{personalized_prompt}

【回答规则】
1. 先直接回答核心结论。
2. 语言自然、专业、简洁。
3. 控制在2到4句话。
4. 只回答知识库中明确支持的内容。
5. 若知识库整体信息不足，仅输出：知识库未收录相关内容
"""


def generate_answer_with_llm(
    question: str,
    context: str,
    query_type: str = "other"
) -> str:
    client = get_llm_client()
    model = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")

    logger.info(f"[LLM] model={model}")
    logger.info(f"[LLM] base_url={os.getenv('OPENAI_BASE_URL')}")

    prompt = build_prompt(question, context, query_type=query_type)
    logger.info("[llm] generate_answer_with_llm | query_type=%s | question=%s", query_type, question)
    logger.info("[llm] prompt preview:\n%s", prompt[:2000])

    try:
        logger.info("[llm] 开始生成")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "你是专业医疗RAG知识库助手，禁止脱离上下文回答。"
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
        )

        answer = (response.choices[0].message.content or "").strip()

        logger.info("[llm] 生成完成")
        return answer

    except Exception as e:
        logger.error(f"[llm] 调用失败: {e}", exc_info=True)
        return ""


def generate_answer_with_llm_stream(
    question: str,
    context: str,
    query_type: str = "other"
):
    client = get_llm_client()
    model = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")

    prompt = build_prompt(question, context, query_type=query_type)
    logger.info("[llm] generate_answer_with_llm | query_type=%s | question=%s", query_type, question)
    logger.info("[llm] prompt preview:\n%s", prompt[:2000])

    system_prompt = """
你是专业医疗RAG知识库助手。

回答规则：
1. 只能依据提供的知识库上下文回答，禁止使用上下文之外的知识。
2. 如果上下文不足以回答，必须只输出：知识库未收录相关内容。
3. 输出必须使用纯文本自然段格式。
4. 不要使用 Markdown 标题，不要使用 ###、##、#。
5. 不要使用加粗符号 **。
6. 不要使用无序列表符号 * 或 -。
7. 如果需要分点，请使用阿拉伯数字编号，如：
1. ...
2. ...
3. ...
8. 语言简洁、准确、直接，优先先给核心答案，再给补充说明。
"""

    try:
        logger.info("[llm-stream] 开始流式生成")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            stream=True
        )

        for chunk in response:
            try:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                if delta and delta.content:
                    yield delta.content

            except Exception as e:
                logger.warning(f"[llm-stream] chunk解析异常: {e}")
                continue

        logger.info("[llm-stream] 流式完成")

    except Exception as e:
        logger.error(f"[llm-stream] 调用失败: {e}", exc_info=True)
        yield "系统异常，请稍后重试。"