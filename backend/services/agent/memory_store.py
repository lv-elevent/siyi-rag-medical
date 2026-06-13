"""
语义记忆存储（MemoryStore）

职责：
- 从对话中提取关键医疗信息（过敏史/病史/用药/诊断），生成 MemoryFragment
- 将记忆片段向量化存入 ChromaDB（持久化，永不过期）
- 每次新对话时语义检索最相关的历史记忆，注入 LLM 上下文

架构位置：
  Working Memory（最近5轮原文） → memory.py
  Semantic Memory（关键信息向量检索）→ 本模块
  Episodic Memory（对话摘要）→ 本模块 _summarize 方法
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from backend.core import config
from backend.core.embedding_client import embed_text
from backend.core.redis_client import memory_cache

logger = logging.getLogger(__name__)

# ── 记忆类别与优先级 ──

MEMORY_CATEGORIES = {
    "allergy":       {"priority": 10, "label": "过敏史"},
    "severe_history": {"priority": 9, "label": "重大病史"},
    "medication":    {"priority": 8, "label": "当前用药"},
    "diagnosis":     {"priority": 7, "label": "诊断结论"},
    "family_history": {"priority": 6, "label": "家族史"},
    "symptom":       {"priority": 4, "label": "症状描述"},
    "general":       {"priority": 2, "label": "一般信息"},
}


# ── 数据结构 ──

@dataclass
class MemoryFragment:
    """一条语义记忆片段"""
    fragment_id: str
    session_id: str
    user_id: int
    content: str                    # 一句话摘要，如"患者对青霉素过敏，曾出现皮疹反应"
    category: str = "general"
    priority: int = 2
    entities: list[str] = field(default_factory=list)
    source_turn: int = 0            # 来自第几轮对话
    created_at: str = ""

    def to_metadata(self) -> dict:
        return {
            "fragment_id": self.fragment_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "category": self.category,
            "priority": self.priority,
            "entities": ",".join(self.entities),
            "source_turn": self.source_turn,
            "created_at": self.created_at,
        }


# ── LLM 抽取 Prompt ──

EXTRACTION_PROMPT = """你是一个医疗信息提取器。分析以下对话，判断是否包含需要长期记住的关键医疗信息。

需要提取的信息类型（按优先级排序）：
1. 过敏史（allergy）：患者对什么药物/物质过敏
2. 重大病史（severe_history）：高血压、糖尿病、心脏病、手术史等
3. 当前用药（medication）：正在服用的药物名称、剂量
4. 诊断结论（diagnosis）：医生给出的明确诊断
5. 家族史（family_history）：直系亲属的重大疾病
6. 症状描述（symptom）：反复出现的或重要症状

如果对话中**没有任何**上述医疗信息，返回空 JSON。
如果有，将每条信息提取为一句简洁陈述，不超过 30 字。

返回格式（严格的 JSON）：
{"memories":[{"category":"allergy","content":"患者对青霉素过敏"},{"category":"medication","content":"正在服用氨氯地平5mg/日"}]}

对话内容：
{conversation}

只返回 JSON，不要输出其他内容。"""


# ── MemoryStore ──

class MemoryStore:
    """语义记忆存储 — ChromaDB 持久化 + 向量检索

    共享 vector_repository 的 PersistentClient，避免多 client 冲突。
    """

    COLLECTION_NAME = "conversation_memories"

    def __init__(self, chroma_client=None):
        if chroma_client is not None:
            self._chroma_client = chroma_client
        else:
            # 降级：如果没传 client，自己创建（生产环境由 vector_repository 注入）
            self._chroma_client = chromadb.PersistentClient(
                path=config.CHROMA_PERSIST_DIR or "./chroma_db",
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        self._collection = self._chroma_client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("[memory_store] collection=%s ready", self.COLLECTION_NAME)

    # ── 写入 ──

    def add(self, fragment: MemoryFragment) -> None:
        """存入一条语义记忆（向量 + 元数据）"""
        embedding = embed_text(fragment.content)
        fragment.created_at = datetime.utcnow().isoformat()
        meta = fragment.to_metadata()

        self._collection.add(
            documents=[fragment.content],
            embeddings=[embedding],
            metadatas=[meta],
            ids=[fragment.fragment_id],
        )

        # 同时写 Redis 热缓存（最近 50 条）
        cache_key = f"recent:{fragment.user_id}"
        cached = memory_cache.get_json(cache_key) or []
        cached.insert(0, meta)
        memory_cache.set_json(cache_key, cached[-50:], ttl=86400)

        logger.info(
            "[memory_store] added category=%s priority=%s content=%s",
            fragment.category, fragment.priority, fragment.content[:40],
        )

    # ── 检索 ──

    def search(
        self,
        query: str,
        user_id: int,
        top_k: int = 5,
        min_priority: int = 3,
    ) -> list[MemoryFragment]:
        """语义检索最相关的历史记忆"""
        try:
            query_embedding = embed_text(query)
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k * 3, 30),
                where={"user_id": user_id},
            )
        except Exception as exc:
            logger.warning("[memory_store] search failed: %s", exc)
            return []

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        fragments: list[MemoryFragment] = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            priority = int(meta.get("priority", 2))
            if priority < min_priority:
                continue
            fragments.append(MemoryFragment(
                fragment_id=meta.get("fragment_id", ""),
                session_id=meta.get("session_id", ""),
                user_id=int(meta.get("user_id", 0)),
                content=doc,
                category=meta.get("category", "general"),
                priority=priority,
                entities=(meta.get("entities", "") or "").split(",") if meta.get("entities") else [],
                source_turn=int(meta.get("source_turn", 0)),
                created_at=meta.get("created_at", ""),
            ))

        # 按优先级降序，同优先级按 distance 升序
        fragments.sort(key=lambda f: (-f.priority, 0))
        return fragments[:top_k]

    # ── LLM 抽取 ──

    @staticmethod
    def extract_from_conversation(turns: list[dict]) -> list[dict]:
        """
        用 LLM 从多轮对话中抽取关键医疗信息。
        turns: [{"role":"user","content":"..."}, {"role":"assistant","content":"..."}, ...]
        返回: [{"category":"allergy","content":"患者对青霉素过敏"}, ...]
        """
        conversation = "\n".join(
            f"{'用户' if t['role'] == 'user' else '助手'}: {t['content']}"
            for t in turns[-6:]  # 最多取最近 6 轮
        )
        prompt = EXTRACTION_PROMPT.format(conversation=conversation)

        try:
            from backend.core.llm_client import get_llm_client
            client = get_llm_client()
            response = client.chat.completions.create(
                model=os.getenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=300,
            )
            raw = (response.choices[0].message.content or "").strip()
            # 清洗可能的 markdown 代码块包裹
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            result = json.loads(raw)
            return result.get("memories", [])
        except Exception as exc:
            logger.warning("[memory_store] extraction failed: %s", exc)
            return []

    # ── 生成 Fragment ID ──

    @staticmethod
    def make_fragment_id(user_id: int, session_id: str, turn_index: int, category: str) -> str:
        raw = f"{user_id}:{session_id}:{turn_index}:{category}"
        return f"mem_{hashlib.md5(raw.encode()).hexdigest()[:12]}"

    # ── 统计 ──

    def count(self, user_id: int) -> int:
        try:
            results = self._collection.get(where={"user_id": user_id})
            return len(results.get("ids", []))
        except Exception:
            return 0


# ── 模块级单例（延迟初始化，复用 vector_repository 的 client）──

_memory_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    """获取 MemoryStore 单例（延迟初始化，共享 ChromaDB client）"""
    global _memory_store
    if _memory_store is None:
        try:
            from backend.repositories.vector_repository import vector_repository
            _memory_store = MemoryStore(chroma_client=vector_repository.client)
            logger.info("[memory_store] sharing client from vector_repository")
        except Exception as exc:
            logger.warning("[memory_store] cannot share client, standalone: %s", exc)
            _memory_store = MemoryStore()
    return _memory_store
