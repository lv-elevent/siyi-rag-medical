import logging
import re
from typing import List, Dict

logger = logging.getLogger(__name__)

# 分块参数配置（目标 400~800）
CHUNK_SIZE = 700
OVERLAP = 30

TITLE_RE = re.compile(r"^(第[一二三四五六七八九十]+章|\d+\.|一、|二、|三、)")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])")


def _split_long_paragraph_by_sentence(paragraph: str, max_len: int = 800) -> List[str]:
    paragraph = (paragraph or "").strip()
    if not paragraph:
        return []

    if len(paragraph) <= max_len:
        return [paragraph]

    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(paragraph) if s.strip()]
    if not sentences:
        # 兜底：无句号时硬切
        return [paragraph[i:i + max_len] for i in range(0, len(paragraph), max_len)]

    parts: List[str] = []
    current = ""

    for sent in sentences:
        if not current:
            current = sent
            continue

        candidate = f"{current}{sent}"
        if len(candidate) <= max_len:
            current = candidate
        else:
            parts.append(current)
            current = sent

    if current:
        parts.append(current)

    return parts


def _normalize_paragraphs(text: str) -> List[str]:
    # 1) 优先按空行分段，每段作为最小语义单元
    raw_paras = [p.strip() for p in text.split("\n\n") if p.strip()]

    # 清理段内单换行，避免句子断裂
    paras = [re.sub(r"\s*\n\s*", " ", p).strip() for p in raw_paras if p.strip()]
    if not paras:
        return []

    merged: List[str] = []
    i = 0
    n = len(paras)

    while i < n:
        p = paras[i]

        # 3) 标题段强制与下一段合并，避免标题丢失
        if TITLE_RE.match(p) and i + 1 < n:
            p = f"{p}\n{paras[i + 1]}".strip()
            i += 2
        else:
            i += 1

        # 2) 短段落（<200）与下一段合并
        if len(p) < 200 and i < n:
            p = f"{p}\n{paras[i]}".strip()
            i += 1

        # 2) 长段落（>800）按句号二次切分
        if len(p) > 800:
            merged.extend(_split_long_paragraph_by_sentence(p, max_len=800))
        else:
            merged.append(p)

    return merged


def split_text_into_chunks(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = OVERLAP
) -> List[Dict[str, str | int]]:
    """
    语义优先切分：
    - 先按段落（\\n\\n）
    - 标题与下一段绑定
    - 短段落合并、长段落按句切分
    - 目标 chunk 大小约 400~800，重叠 20~30 字符
    """
    if not text or not text.strip():
        return []

    # 4) overlap 收敛到 20~30
    overlap = max(20, min(overlap, 30))
    chunk_size = max(400, min(chunk_size, 800))

    units = _normalize_paragraphs(text)
    if not units:
        return []

    chunks: List[Dict[str, str | int]] = []
    current = ""
    index = 0

    for unit in units:
        if not current:
            current = unit
            continue

        # 尝试把当前段落拼入当前 chunk
        candidate = f"{current}\n\n{unit}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        # 输出当前 chunk
        chunk_text = current.strip()
        if chunk_text:
            chunks.append({"index": index, "text": chunk_text})
            index += 1

        # 以尾部字符重叠 + 新段落起新块
        tail = chunk_text[-overlap:] if overlap > 0 else ""
        current = f"{tail}\n\n{unit}".strip() if tail else unit

        # 极端情况：current 仍 > chunk_size，继续按句子拆
        if len(current) > chunk_size:
            sub_parts = _split_long_paragraph_by_sentence(current, max_len=chunk_size)
            for part in sub_parts[:-1]:
                if part.strip():
                    chunks.append({"index": index, "text": part.strip()})
                    index += 1
            current = sub_parts[-1] if sub_parts else ""

    if current.strip():
        chunks.append({"index": index, "text": current.strip()})

    # 5) 输出统计日志
    lengths = [len(c["text"]) for c in chunks]
    if lengths:
        avg_len = round(sum(lengths) / len(lengths), 2)
        logger.info(
            "[chunker] total_chunks=%s avg_len=%s min_len=%s max_len=%s",
            len(chunks),
            avg_len,
            min(lengths),
            max(lengths),
        )
    else:
        logger.info("[chunker] total_chunks=0 avg_len=0 min_len=0 max_len=0")

    return chunks