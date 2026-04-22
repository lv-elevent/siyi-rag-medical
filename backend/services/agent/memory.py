"""
Medical Agent Memory - 基础内存实现
职责：按 session_id 保存最近几轮用户问题历史
实现：进程内存存储，不依赖外部存储
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """单轮对话结构"""
    user_question: str
    query_type: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    assistant_answer: Optional[str] = None


class MemoryManager:
    """按 session_id 管理多轮对话历史"""

    def __init__(self, max_turns: int = 3):
        self.max_turns = max_turns
        self._memory: Dict[str, List[ConversationTurn]] = {}

    def get_session_history(self, session_id: str) -> List[ConversationTurn]:
        if not session_id or session_id not in self._memory:
            return []
        return self._memory[session_id].copy()

    def get_recent_questions(self, session_id: str, limit: int = 2) -> List[str]:
        history = self.get_session_history(session_id)
        return [turn.user_question for turn in history[-limit:]]

    def add_turn(self, session_id: str, turn: ConversationTurn) -> None:
        if not session_id:
            return

        if session_id not in self._memory:
            self._memory[session_id] = []

        clean_turn = ConversationTurn(
            user_question=turn.user_question,
            query_type=turn.query_type,
            timestamp=turn.timestamp,
            sources=turn.sources,
            assistant_answer=turn.assistant_answer,
        )

        self._memory[session_id].append(clean_turn)

        if len(self._memory[session_id]) > self.max_turns:
            self._memory[session_id] = self._memory[session_id][-self.max_turns:]

    def clear_session(self, session_id: str) -> None:
        if session_id in self._memory:
            del self._memory[session_id]

    def get_session_count(self) -> int:
        return len(self._memory)

    def get_turn_count(self, session_id: str) -> int:
        return len(self._memory.get(session_id, []))


memory_manager = MemoryManager(max_turns=3)