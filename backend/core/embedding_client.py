import os
import math
import logging
from typing import List
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")

if not OPENAI_API_KEY:
    raise ValueError("缺少环境变量 OPENAI_API_KEY")

if not OPENAI_BASE_URL:
    raise ValueError("缺少环境变量 OPENAI_BASE_URL")

client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
)

logger = logging.getLogger(__name__)

# ✅ 最大 batch（关键参数）
MAX_BATCH_SIZE = 32


def _normalize_vector(vector: List[float]) -> List[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return vector
    return [x / norm for x in vector]


def _vector_norm(vector: List[float]) -> float:
    return math.sqrt(sum(x * x for x in vector))


def embed_text(text: str) -> List[float]:
    cleaned_text = text.strip() if text else ""
    if not cleaned_text:
        raise ValueError("embedding 输入文本不能为空")

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=cleaned_text,
    )

    embedding = response.data[0].embedding
    normalized_embedding = _normalize_vector(embedding)

    logger.info(
        "[embedding_client] 单条 embedding 完成 model=%s dim=%s norm_before=%.6f norm_after=%.6f",
        EMBEDDING_MODEL,
        len(embedding),
        _vector_norm(embedding),
        _vector_norm(normalized_embedding),
    )

    return normalized_embedding


def embed_texts(texts: List[str]) -> List[List[float]]:
    cleaned_texts = [t.strip() for t in texts if t and t.strip()]
    if not cleaned_texts:
        return []

    all_embeddings: List[List[float]] = []
    total = len(cleaned_texts)

    logger.info(f"[embedding_client] 开始批量 embedding，总数={total}")

    # ✅ 分批处理
    for i in range(0, total, MAX_BATCH_SIZE):
        batch = cleaned_texts[i:i + MAX_BATCH_SIZE]

        logger.info(f"[embedding_client] 处理 batch: {i} ~ {i + len(batch)}")

        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch,
        )

        embeddings = [item.embedding for item in response.data]
        normalized_embeddings = [_normalize_vector(item) for item in embeddings]

        all_embeddings.extend(normalized_embeddings)

        # 打印第一条用于监控
        if normalized_embeddings:
            logger.info(
                "[embedding_client] batch 完成 size=%s dim=%s norm_before=%.6f norm_after=%.6f",
                len(normalized_embeddings),
                len(normalized_embeddings[0]),
                _vector_norm(embeddings[0]),
                _vector_norm(normalized_embeddings[0]),
            )

    logger.info(f"[embedding_client] 全部 embedding 完成，总数={len(all_embeddings)}")

    return all_embeddings