"""
Medical Agent Memory — 混合记忆架构

三层记忆：
  Working Memory  — 最近 N 轮完整原文 → Redis + 本地降级
  Semantic Memory — 关键医疗信息向量化 → ChromaDB 持久化（memory_store）
  Episodic Memory — 超窗口对话摘要 → Redis 缓存

生命周期：
  ┌─ 新对话 ─→ get_context_for_query()
  │              ├── [Semantic] 检索相关历史记忆
  │              ├── [Episodic] 加载摘要
  │              └── [Working]  加载最近 N 轮
  │
  ├─ 每轮结束 ─→ add_turn() → Redis + turn counter
  │
  ├─ 每 5 轮 ──→ trigger_extraction() → LLM 抽取 → MemoryStore
  │
  └─ 服务重启 ─→ 从 MySQL chat_messages 恢复最近 N 轮到 Redis
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from backend.core.redis_client import memory_cache

logger = logging.getLogger(__name__)

# ── 常量 ──

MAX_WORKING_TURNS = 5          # Working Memory 保留最近 N 轮
EXTRACTION_INTERVAL = 5        # 每 N 轮触发一次语义记忆抽取
SESSION_TTL = 86400            # Redis TTL: 24 小时
SUMMARY_TTL = 86400 * 7        # 摘要 TTL: 7 天


# ── 数据结构 ──

@dataclass
class ConversationTurn:
    """单轮对话"""
    user_question: str
    query_type: str = "general"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    sources: list[dict] = field(default_factory=list)
    assistant_answer: Optional[str] = None


@dataclass
class MemoryContext:
    """组装后的三层记忆上下文（注入 LLM prompt）"""
    semantic_memories: list[str]    # 语义记忆列表
    summary: Optional[str]           # 对话摘要
    recent_turns: list[ConversationTurn]  # 最近 N 轮
    turn_count: int                  # 总轮数

    def to_prompt_block(self) -> str:
        """转换为 prompt 文本块"""
        parts = []

        if self.semantic_memories:
            lines = "\n".join(f"  ⚠ {m}" for m in self.semantic_memories)
            parts.append(f"【关键背景 — 历史医疗信息】\n{lines}")

        if self.summary:
            parts.append(f"【对话脉络】\n{self.summary}")

        if self.recent_turns:
            lines = "\n".join(
                f"  用户: {t.user_question}\n  助手: {t.assistant_answer or '(无)'}"
                for t in self.recent_turns
            )
            parts.append(f"【最近交流】\n{lines}")

        return "\n\n".join(parts) if parts else ""


# ── MemoryManager ──

class MemoryManager:
    """
    混合记忆管理器

    Working Memory:  Redis key="session:{sid}:turns" → JSON list of dict
    Episodic Memory: Redis key="session:{sid}:summary" → 压缩摘要文本
    Semantic Memory: memory_store (ChromaDB) → 向量检索
    """

    def __init__(self, max_turns: int = MAX_WORKING_TURNS):
        self.max_turns = max_turns
        self._local_fallback: dict[str, list[ConversationTurn]] = {}  # Redis 不可用时的降级

    # ================================================================
    # Working Memory
    # ================================================================

    def _working_key(self, session_id: str) -> str:
        return f"{session_id}:turns"

    def _load_working(self, session_id: str) -> list[ConversationTurn]:
        """从 Redis 加载 working memory，带降级"""
        data = memory_cache.get_json(self._working_key(session_id))
        if data:
            return [
                ConversationTurn(
                    user_question=t.get("user_question", ""),
                    query_type=t.get("query_type", "general"),
                    timestamp=datetime.fromisoformat(t["timestamp"]) if t.get("timestamp") else datetime.utcnow(),
                    sources=t.get("sources", []),
                    assistant_answer=t.get("assistant_answer"),
                )
                for t in data
            ]
        return self._local_fallback.get(session_id, []).copy()

    def _save_working(self, session_id: str, turns: list[ConversationTurn]) -> None:
        """保存 working memory 到 Redis + 本地降级"""
        data = [
            {
                "user_question": t.user_question,
                "query_type": t.query_type,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                "sources": t.sources,
                "assistant_answer": t.assistant_answer,
            }
            for t in turns
        ]
        memory_cache.set_json(self._working_key(session_id), data, ttl=SESSION_TTL)
        self._local_fallback[session_id] = turns

    # ================================================================
    # Episodic Memory（摘要）
    # ================================================================

    def _summary_key(self, session_id: str) -> str:
        return f"{session_id}:summary"

    def get_summary(self, session_id: str) -> Optional[str]:
        return memory_cache.get(self._summary_key(session_id))

    def set_summary(self, session_id: str, summary: str) -> None:
        memory_cache.set(self._summary_key(session_id), summary, ttl=SUMMARY_TTL)

    # ================================================================
    # Turn Counter（用于触发抽取）
    # ================================================================

    def _counter_key(self, session_id: str) -> str:
        return f"{session_id}:counter"

    def _increment_counter(self, session_id: str) -> int:
        raw = memory_cache.get(self._counter_key(session_id))
        count = (int(raw) if raw else 0) + 1
        memory_cache.set(self._counter_key(session_id), str(count), ttl=SESSION_TTL)
        return count

    # ================================================================
    # 公共 API（兼容旧接口）
    # ================================================================

    def get_session_history(self, session_id: str) -> list[ConversationTurn]:
        """获取完整 working memory"""
        return self._load_working(session_id)

    def get_recent_questions(self, session_id: str, limit: int = 2) -> list[str]:
        """获取最近 N 轮的用户问题"""
        history = self._load_working(session_id)
        return [t.user_question for t in history[-limit:]]

    def get_turn_count(self, session_id: str) -> int:
        return len(self._load_working(session_id))

    def get_session_count(self) -> int:
        return len(self._local_fallback)

    def add_turn(self, session_id: str, turn: ConversationTurn) -> None:
        """追加一轮对话到 working memory"""
        if not session_id:
            return
        turns = self._load_working(session_id)
        turns.append(ConversationTurn(
            user_question=turn.user_question,
            query_type=turn.query_type,
            timestamp=turn.timestamp or datetime.utcnow(),
            sources=turn.sources,
            assistant_answer=turn.assistant_answer,
        ))
        # 只保留最近 N 轮
        if len(turns) > self.max_turns:
            turns = turns[-self.max_turns:]
        self._save_working(session_id, turns)

    def clear_session(self, session_id: str) -> None:
        memory_cache.delete(self._working_key(session_id))
        memory_cache.delete(self._summary_key(session_id))
        memory_cache.delete(self._counter_key(session_id))
        self._local_fallback.pop(session_id, None)

    # ================================================================
    # 核心：三层上下文组装
    # ================================================================

    def get_context_for_query(
        self,
        session_id: str,
        question: str,
        user_id: int,
    ) -> MemoryContext:
        """
        为当前查询组装三层记忆上下文。

        调用顺序：
          1. [Semantic] 用 question 检索 ChromaDB 中最相关的历史记忆
          2. [Episodic] 加载该 session 的摘要
          3. [Working]  加载最近 N 轮完整原文
        """
        # Layer 1: Semantic — 向量检索相关记忆
        semantic: list[str] = []
        try:
            from backend.services.agent.memory_store import get_memory_store
            fragments = get_memory_store().search(
                query=question,
                user_id=user_id,
                top_k=5,
                min_priority=3,
            )
            for f in fragments:
                label = f.category or "general"
                semantic.append(f"[{label}] {f.content}")
        except Exception as exc:
            logger.warning("[memory] semantic retrieval failed: %s", exc)

        # Layer 2: Episodic — 摘要
        summary = self.get_summary(session_id)

        # Layer 3: Working — 最近 N 轮
        recent = self._load_working(session_id)

        return MemoryContext(
            semantic_memories=semantic,
            summary=summary,
            recent_turns=recent,
            turn_count=self.get_turn_count(session_id),
        )

    # ================================================================
    # 语义记忆抽取（异步触发）
    # ================================================================

    def should_extract(self, session_id: str) -> bool:
        """判断是否该触发语义记忆抽取（每 N 轮一次）"""
        count = self._increment_counter(session_id)
        return count % EXTRACTION_INTERVAL == 0

    def trigger_extraction(self, session_id: str, user_id: int) -> list[str]:
        """
        从最近对话中抽取关键医疗信息，存入语义记忆库。

        返回本次抽取到的记忆片段内容列表（用于日志）。
        """
        turns = self._load_working(session_id)
        if not turns:
            return []

        # 格式化对话为 LLM 可读格式
        conversation_turns = []
        for t in turns[-EXTRACTION_INTERVAL:]:
            conversation_turns.append({"role": "user", "content": t.user_question})
            if t.assistant_answer:
                conversation_turns.append({"role": "assistant", "content": t.assistant_answer})

        try:
            from backend.services.agent.memory_store import MemoryFragment, get_memory_store
            store = get_memory_store()
            extracted = store.extract_from_conversation(conversation_turns)

            if not extracted:
                logger.debug("[memory] extraction: no key info found in last %s turns", EXTRACTION_INTERVAL)
                return []

            results = []
            for item in extracted:
                category = item.get("category", "general")
                content = item.get("content", "")
                if not content:
                    continue

                priority = 2
                if category in {"allergy", "severe_history"}:
                    priority = 10
                elif category == "medication":
                    priority = 8
                elif category == "diagnosis":
                    priority = 7

                fragment = MemoryFragment(
                    fragment_id=store.make_fragment_id(user_id, session_id, len(turns), category),
                    session_id=session_id,
                    user_id=user_id,
                    content=content,
                    category=category,
                    priority=priority,
                    source_turn=len(turns),
                )
                store.add(fragment)
                results.append(content)

            logger.info("[memory] extracted %s memories for session=%s", len(results), session_id)

            # 如果旧轮数较多，触发摘要合并
            if len(turns) > self.max_turns * 2:
                self._condense_summary(session_id, turns)

            return results

        except Exception as exc:
            logger.warning("[memory] extraction failed: %s", exc)
            return []

    # ================================================================
    # 摘要压缩
    # ================================================================

    def _condense_summary(self, session_id: str, turns: list[ConversationTurn]) -> None:
        """将窗口外的旧对话压缩为摘要"""
        old_turns = turns[:-self.max_turns]
        if not old_turns:
            return

        existing_summary = self.get_summary(session_id) or ""
        conversation = "\n".join(
            f"用户: {t.user_question}\n助手: {t.assistant_answer or ''}"
            for t in old_turns[-10:]  # 最多取旧 10 轮做摘要
        )

        prompt = f"""将以下医疗对话压缩为 2~3 句中文摘要，只记录关键信息（疾病、用药、症状、建议），不保留闲聊内容。

已有摘要：
{existing_summary or '（无）'}

新增对话：
{conversation}

请输出合并后的摘要（2~3 句）："""

        try:
            from backend.core.llm_client import get_llm_client
            client = get_llm_client()
            response = client.chat.completions.create(
                model=os.getenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=200,
            )
            new_summary = (response.choices[0].message.content or "").strip()
            if new_summary:
                self.set_summary(session_id, new_summary)
                logger.info("[memory] summary updated for session=%s", session_id)
        except Exception as exc:
            logger.warning("[memory] summary condensation failed: %s", exc)

    # ================================================================
    # DB 恢复（服务重启后从 MySQL 回填）
    # ================================================================

    def recover_from_db(self, session_id: str, user_id: int, db) -> int:
        """
        从 MySQL chat_messages 表恢复最近 N 轮到 Redis。

        返回恢复的轮数。
        """
        try:
            from backend.database.models import ChatMessage
            messages = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.session_id == session_id,
                    ChatMessage.user_id == user_id,
                )
                .order_by(ChatMessage.created_at.asc())
                .all()
            )
            if not messages:
                return 0

            # 分组为 user-assistant 对
            turns: list[ConversationTurn] = []
            pending_user: Optional[str] = None

            for msg in messages:
                if msg.role == "user":
                    if pending_user:
                        turns.append(ConversationTurn(user_question=pending_user))
                    pending_user = msg.content
                elif msg.role == "assistant" and pending_user:
                    turns.append(ConversationTurn(
                        user_question=pending_user,
                        assistant_answer=msg.content,
                        query_type="recovered",
                        sources=(msg.metadata_json or {}).get("sources", []),
                        timestamp=msg.created_at or datetime.utcnow(),
                    ))
                    pending_user = None

            if pending_user:
                turns.append(ConversationTurn(user_question=pending_user))

            # 只保留最近 max_turns 轮
            turns = turns[-self.max_turns:]
            self._save_working(session_id, turns)

            logger.info("[memory] recovered %s turns for session=%s from DB", len(turns), session_id)
            return len(turns)

        except Exception as exc:
            logger.warning("[memory] DB recovery failed: %s", exc)
            return 0


# ── 模块级单例（保持兼容）──

memory_manager = MemoryManager(max_turns=MAX_WORKING_TURNS)
