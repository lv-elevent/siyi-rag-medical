import json
import logging
from typing import Dict

from backend.core import config
from backend.core.llm_client import get_llm_client
from backend.core.medical_terms import (
    HIGH_RISK,
    CHITCHAT,
    NON_MEDICAL,
    SHORT_MEDICAL,
)

logger = logging.getLogger(__name__)


class SmartRouter:
    # ── 引用统一词表（全项目唯一来源）──
    HIGH_RISK_KEYWORDS = list(HIGH_RISK)
    CHITCHAT_KEYWORDS = list(CHITCHAT)
    OUT_OF_SCOPE_KEYWORDS = list(NON_MEDICAL)
    SHORT_MEDICAL_KEYWORDS = list(SHORT_MEDICAL)

    ROUTER_PROMPT = """你是一个医疗问答分类器，请判断用户问题属于哪一类：

可选类型：
- medical（医疗问题）
- chitchat（日常聊天）
- out_of_scope（非医疗问题）

返回JSON格式：
{"type": "...", "reason": "..."}

禁止返回其他内容"""

    def route(self, query: str) -> Dict[str, str]:
        text = (query or "").strip()
        lowered_text = text.lower()

        if self._contains_any(text, lowered_text, self.HIGH_RISK_KEYWORDS):
            return {
                "type": "high_risk",
                "reason": "matched high-risk keyword rule",
            }

        # 短医疗词优先判定为 medical，避免误落到闲聊/越界
        if self._contains_any(text, lowered_text, self.SHORT_MEDICAL_KEYWORDS):
            return {
                "type": "medical",
                "reason": "matched short-medical keyword rule",
            }

        if self._contains_any(text, lowered_text, self.CHITCHAT_KEYWORDS):
            return {
                "type": "chitchat",
                "reason": "matched chitchat keyword rule",
            }

        if self._contains_any(text, lowered_text, self.OUT_OF_SCOPE_KEYWORDS):
            return {
                "type": "out_of_scope",
                "reason": "matched out-of-scope keyword rule",
            }

        llm_result = self._classify_with_llm(text)
        if llm_result is not None:
            return llm_result

        return {"type": "medical", "reason": "fallback"}

    @staticmethod
    def _contains_any(original: str, lowered: str, keywords) -> bool:
        for keyword in keywords:
            if keyword.lower() in lowered or keyword in original:
                return True
        return False

    def _classify_with_llm(self, query: str) -> Dict[str, str] | None:
        try:
            client = get_llm_client()
            response = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": self.ROUTER_PROMPT},
                    {"role": "user", "content": query},
                ],
                temperature=0,
            )
            content = (response.choices[0].message.content or "").strip()
            parsed = json.loads(content)
        except Exception as exc:
            logger.warning("[smart-router] llm classify failed: %s", exc)
            return None

        router_type = parsed.get("type")
        reason = parsed.get("reason")
        if router_type in {"medical", "chitchat", "out_of_scope"} and isinstance(reason, str):
            return {"type": router_type, "reason": reason}
        return None
