import json
import logging
from typing import Dict

from backend.core.llm_client import get_llm_client

logger = logging.getLogger(__name__)


class SmartRouter:
    HIGH_RISK_DRUG_KEYWORDS = ["mg", "剂量", "吃多少", "过量", "几片"]
    HIGH_RISK_DANGER_KEYWORDS = ["自杀", "想死", "不想活", "结束生命"]
    HIGH_RISK_KEYWORDS = HIGH_RISK_DRUG_KEYWORDS + HIGH_RISK_DANGER_KEYWORDS
    CHITCHAT_KEYWORDS = [
        "你好", "hi", "hello", "thanks", "谢谢",
        "你是谁", "你能干什么", "你可以做什么", "你是做什么的", "介绍下你自己",
    ]
    OUT_OF_SCOPE_KEYWORDS = ["天气", "写代码", "写python代码", "编程", "翻译", "股票", "数学题"]
    SHORT_MEDICAL_KEYWORDS = [
        "解剖学", "局部解剖学", "药理学", "生理学", "病理学", "免疫学", "微生物学", "组织学",
        "高血压", "糖尿病", "冠心病", "肺炎", "胃炎", "哮喘", "感冒",
        "头痛", "发热", "咳嗽", "腹泻", "胸闷", "失眠",
        "布洛芬", "阿司匹林", "阿莫西林", "头孢", "胰岛素",
        "动脉", "静脉", "神经", "肌肉", "骨", "关节",
    ]

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
                model="Qwen/Qwen2.5-7B-Instruct",
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
