"""
答案格式化服务

职责：LLM 输出的后处理（Markdown 清洗、答案有效性校验）
"""

import re

from backend.core.medical_terms import INVALID_QUERY_PATTERNS


def normalize_llm_answer(text: str) -> str:
    """清洗 LLM 输出中的 Markdown 格式和异常字符"""
    if not text:
        return text

    text = str(text).replace("\r\n", "\n").replace("\r", "\n").strip()

    # 统一中英文引号
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")

    # 去掉 markdown 标题符号
    text = re.sub(r'^\s*###\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*##\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*#\s*', '', text, flags=re.MULTILINE)

    # 把四级标题转成更自然的中文小节格式
    text = re.sub(r'^\s*####\s*(.+?)\s*$', r'\1：', text, flags=re.MULTILINE)

    # 去掉单独一行的无意义粗体包裹
    text = re.sub(r'^\s*\*\*(.+?)\*\*\s*$', r'\1', text, flags=re.MULTILINE)

    # 清理粗体符号，但保留内容
    text = text.replace("**", "")

    # 把 markdown 无序列表统一成 • 列表
    text = re.sub(r'^\s*[\-\*]\s+', '• ', text, flags=re.MULTILINE)

    # 修复一些异常编号开头
    text = re.sub(r'^[\"\']+\.\s*', '2. ', text, flags=re.MULTILINE)
    text = re.sub(r'^[”’]+\.?\s*', '2. ', text, flags=re.MULTILINE)
    text = re.sub(r'^\*\*\.\s*', '2. ', text, flags=re.MULTILINE)

    # 修复类似 **1. xxx** 的写法
    text = re.sub(
        r'^\s*\*\*(\d+)\.\s*([^\n*]+?)\s*\*\*\s*$',
        lambda m: f"{m.group(1)}. {m.group(2).strip()}",
        text,
        flags=re.MULTILINE
    )

    # 修复类似 1. **xxx** 的写法
    text = re.sub(
        r'^\s*(\d+)\.\s*\*\*([^\n*]+?)\*\*\s*$',
        lambda m: f"{m.group(1)}. {m.group(2).strip()}",
        text,
        flags=re.MULTILINE
    )

    # 把中文序号统一一下
    text = re.sub(r'^\s*一[\.、]\s*', '1. ', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*二[\.、]\s*', '2. ', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*三[\.、]\s*', '3. ', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*四[\.、]\s*', '4. ', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*五[\.、]\s*', '5. ', text, flags=re.MULTILINE)

    # 清理流式拼接中偶发的角色残片行
    text = re.sub(
        r'^\s*(\d+\s*)?(user|assistant|用户|助手)\s*$',
        '',
        text,
        flags=re.IGNORECASE | re.MULTILINE
    )

    # 清理中文之间被异常插入的空白
    text = re.sub(r'(?<=[一-鿿])\s+(?=[一-鿿])', '', text)

    # 清理行尾多余空格
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)

    # 清理多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def is_valid_rag_query(question: str, query_type: str = "") -> bool:
    """判断用户问题是否适合走 RAG 检索"""
    q = question.strip()

    if len(q) <= 2:
        return False

    if q.isdigit():
        return False

    for p in INVALID_QUERY_PATTERNS:
        if p in q:
            return False

    return True


# ── 答案有效性兜底判断 ──

_FALLBACK_EXACT_TEXTS = {
    "知识库未收录相关内容",
    "知识库未收录相关内容。",
    "未找到",
    "未找到相关内容",
    "暂无相关内容",
    "暂无相关内容。",
}


def is_fallback_answer(text: str, min_length: int = 8) -> bool:
    """判断答案是否为无效兜底文本"""
    if not text:
        return True
    normalized = text.strip()
    if len(normalized) < min_length:
        return True
    if normalized in _FALLBACK_EXACT_TEXTS:
        return True
    if "知识库未收录相关内容" in normalized:
        return True
    if "未找到" in normalized or "暂无相关内容" in normalized:
        return True
    return False
