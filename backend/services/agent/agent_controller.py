import logging
import os
from typing import Any, Dict, Optional, List

from backend.core.llm_client import get_llm_client
from backend.services.agent.medical_agent import MedicalAgent
from backend.services.agent.smart_router import SmartRouter

logger = logging.getLogger(__name__)


class AgentController:
    CHITCHAT_SYSTEM_PROMPT = (
        "你是“思医”医疗知识库问答助手。"
        "请使用简洁友好的中文回复身份类/闲聊类问题，并优先介绍核心能力："
        "1) 上传医学知识文档；"
        "2) 构建医疗知识库；"
        "3) 基于知识库进行问答并展示来源；"
        "4) 辅助医学学习、知识查询与资料整理。"
        "不要自称其他平台助手，不要扩展为泛陪聊机器人。"
    )

    def __init__(self) -> None:
        self.router = SmartRouter()
        self.medical_agent = MedicalAgent()

    def handle(
        self,
        query: str,
        user_id: int,
        session_id: str,
        document_id: Optional[str] = None,
        knowledge_base_id: Optional[int] = None,
        allowed_doc_ids: Optional[List[int]] = None,
    ) -> dict:
        route = self.router.route(query)
        route_type = route.get("type", "medical")
        is_high_risk = route_type == "high_risk"
        call_medical_agent = route_type == "medical"

        logger.info(
            "[agent-controller] query=%s | route.type=%s | call_medical_agent=%s | is_high_risk=%s",
            query,
            route_type,
            call_medical_agent,
            is_high_risk,
        )

        if route_type == "high_risk":
            return self._safety_response()

        if route_type == "chitchat":
            answer = self._chat_with_llm(query)
            return {
                "answer": answer,
                "type": "chitchat",
                "source": "llm",
            }

        if route_type == "out_of_scope":
            return {
                "answer": (
                    "我是思医，主要用于医学知识文档管理与知识库问答。"
                    "您可以上传医学文档、构建知识库，并基于知识库进行学习和知识查询。"
                ),
                "type": "out_of_scope",
                "source": "llm",
            }

        medical_result = self.medical_agent.process(
            question=query,
            document_id=document_id,
            user_id=user_id,
            session_id=session_id,
            knowledge_base_id=knowledge_base_id,
            allowed_doc_ids=allowed_doc_ids,
        )
        answer = self._extract_answer(medical_result)
        sources = self._extract_sources(medical_result)
        return {
            "answer": answer,
            "type": "medical",
            "source": "rag",
            "sources": sources,
        }

    @staticmethod
    def _safety_response() -> Dict[str, str]:
        return {
            "answer": "该问题涉及潜在风险，请咨询专业医生或医疗机构。",
            "type": "safety",
            "source": "safety",
        }

    @staticmethod
    def _extract_answer(result: Any) -> str:
        if isinstance(result, dict):
            return str(result.get("answer", ""))
        return str(getattr(result, "answer", ""))

    @staticmethod
    def _extract_sources(result: Any) -> list:
        if isinstance(result, dict):
            sources = result.get("sources", [])
            return sources if isinstance(sources, list) else []
        sources = getattr(result, "sources", [])
        return sources if isinstance(sources, list) else []

    def _chat_with_llm(self, query: str) -> str:
        try:
            client = get_llm_client()
            model = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": self.CHITCHAT_SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
                temperature=0.5,
            )
            answer = (response.choices[0].message.content or "").strip()
            return answer or (
                "您好，我是思医。"
                "我可以帮助您上传医学文档、构建知识库，并基于知识库进行问答与来源追溯。"
            )
        except Exception as exc:
            logger.warning("[agent-controller] chitchat llm failed: %s", exc)
            return (
                "您好，我是思医。"
                "我可以帮助您上传医学文档、构建知识库，并基于知识库进行问答与来源追溯。"
            )
