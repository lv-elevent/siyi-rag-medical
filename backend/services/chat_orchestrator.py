"""
Chat 编排器 — 全项目唯一的问答处理入口

职责：
1. 路由分流（SmartRouter）
2. 非医疗问题 → 直接 LLM / 安全兜底
3. 医疗问题 → MedicalAgent 全流程（分类→改写→检索→生成→安全）
4. 统一支持流式和非流式两种输出模式

所有 /chat 和 /chat-stream 端点共用此编排器。
"""

import logging
from typing import Optional, List, Dict, Any

from backend.models.chat import ChatResponse
from backend.services.agent.medical_agent import MedicalAgent
from backend.services.agent.smart_router import SmartRouter
from backend.services.answer_formatter import normalize_llm_answer
from backend.services.safety_guard import safety_filter
from backend.core.llm_client import get_llm_client, generate_answer_with_llm_stream
from backend.core import config

logger = logging.getLogger(__name__)


class ChatOrchestrator:
    """统一问答编排器"""

    CHITCHAT_SYSTEM_PROMPT = (
        '你是"思医"医疗知识库问答助手。'
        "请使用简洁友好的中文回复身份类/闲聊类问题，并优先介绍核心能力："
        "1) 上传医学知识文档；"
        "2) 构建医疗知识库；"
        "3) 基于知识库进行问答并展示来源；"
        "4) 辅助医学学习、知识查询与资料整理。"
        "不要自称其他平台助手，不要扩展为泛陪聊机器人。"
    )

    def __init__(self) -> None:
        self.router = SmartRouter()
        self.agent = MedicalAgent()

    # ── 统一入口 ──

    def execute(
        self,
        question: str,
        user_id: int,
        session_id: str,
        knowledge_base_id: int | None = None,
        allowed_doc_ids: list[int] | None = None,
        document_id: str | None = None,
    ) -> ChatResponse:
        """非流式问答"""
        route_type = self._route(question)
        if route_type in {"high_risk", "chitchat", "out_of_scope"}:
            return self._non_medical_response(route_type, question)
        return self._medical_response(
            question=question, user_id=user_id, session_id=session_id,
            knowledge_base_id=knowledge_base_id, allowed_doc_ids=allowed_doc_ids,
            document_id=document_id,
        )

    def execute_stream(
        self,
        question: str,
        user_id: int,
        session_id: str,
        knowledge_base_id: int | None = None,
        allowed_doc_ids: list[int] | None = None,
        document_id: str | None = None,
    ):
        """流式问答 — 返回生成器"""
        return self._medical_stream(
            question=question, user_id=user_id, session_id=session_id,
            knowledge_base_id=knowledge_base_id, allowed_doc_ids=allowed_doc_ids,
            document_id=document_id,
        )

    # ── 路由 ──

    def _route(self, question: str) -> str:
        result = self.router.route(question)
        route_type = result.get("type", "medical")
        logger.info("[orchestrator] route result=%s", route_type)
        return route_type

    # ── 非医疗处理 ──

    def _non_medical_response(self, route_type: str, question: str) -> ChatResponse:
        if route_type == "high_risk":
            return ChatResponse(
                answer="该问题涉及潜在风险，请咨询专业医生或医疗机构。",
                query_type="other", rewritten_query="", sources=[],
                needs_followup=False, followup_question="", status="success",
            )
        if route_type == "chitchat":
            answer = self._chat_with_llm(question)
            return ChatResponse(
                answer=answer, query_type="other", rewritten_query="", sources=[],
                needs_followup=False, followup_question="", status="success",
            )
        # out_of_scope
        return ChatResponse(
            answer=(
                "我是思医，主要用于医学知识文档管理与知识库问答。"
                "您可以上传医学文档、构建知识库，并基于知识库进行学习和知识查询。"
            ),
            query_type="other", rewritten_query="", sources=[],
            needs_followup=False, followup_question="", status="success",
        )

    # ── 医疗处理（非流式）──

    def _medical_response(
        self,
        question: str,
        user_id: int,
        session_id: str,
        knowledge_base_id: int | None,
        allowed_doc_ids: list[int] | None,
        document_id: str | None,
    ) -> ChatResponse:
        result = self.agent.process(
            question=question,
            document_id=document_id,
            session_id=session_id,
            stream=False,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            allowed_doc_ids=allowed_doc_ids,
        )
        result.session_id = session_id
        return result

    # ── 医疗处理（流式）──

    async def _medical_stream(
        self,
        question: str,
        user_id: int,
        session_id: str,
        knowledge_base_id: int | None,
        allowed_doc_ids: list[int] | None,
        document_id: str | None,
    ):
        """async generator: yields structured dicts {type, data}

        Types: 'chunk' (token), 'message' (info/error), 'sources' (final),
               'followup', 'done' (DONE signal with sources+safe_answer)
        """
        import asyncio

        prepare_result = self.agent.prepare(
            question=question, document_id=document_id,
            session_id=session_id, user_id=user_id,
            knowledge_base_id=knowledge_base_id, allowed_doc_ids=allowed_doc_ids,
        )
        logger.info(
            "[orchestrator:stream] status=%s query_type=%s sources=%s",
            prepare_result.status, prepare_result.query_type, len(prepare_result.sources or []),
        )

        if prepare_result.status == "error":
            yield {"type": "message", "data": prepare_result.error_message or "系统异常"}
            return

        if prepare_result.status == "followup":
            yield {"type": "followup", "data": {"question": prepare_result.followup_question or "请补充更多信息。"}}
            return

        if prepare_result.status == "empty":
            yield {"type": "message", "data": prepare_result.error_message or "知识库未收录相关内容。"}
            return

        # ── 流式生成 ──
        answer_question = prepare_result.retrieval_query or prepare_result.rewritten_query or prepare_result.question
        accumulated = ""
        has_chunk = False

        for token in generate_answer_with_llm_stream(
            question=answer_question, context=prepare_result.full_context,
            query_type=prepare_result.query_type,
        ):
            if token == "[DONE]":
                break
            accumulated += token
            has_chunk = True
            yield {"type": "chunk", "data": token}
            await asyncio.sleep(0)

        final_answer = normalize_llm_answer(accumulated.strip())
        if not final_answer:
            if has_chunk:
                return
            yield {"type": "message", "data": "知识库未收录相关内容。"}
            return

        # ── 安全过滤 ──
        final_answer, is_safe, warnings = safety_filter(final_answer, prepare_result.query_type)
        if warnings:
            logger.warning("[orchestrator:stream] safety warnings: %s", warnings)
        if not is_safe or not final_answer or len(final_answer.strip()) < 8:
            yield {"type": "message", "data": "知识库未收录相关内容。"}
            return

        # 返回最终答案 + 来源，供 API 层保存
        yield {
            "type": "done",
            "data": {
                "answer": final_answer,
                "sources": prepare_result.sources or [],
                "query_type": prepare_result.query_type,
                "question": prepare_result.question,
            },
        }

    # ── 闲聊 LLM ──

    def _chat_with_llm(self, query: str) -> str:
        try:
            client = get_llm_client()
            response = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": self.CHITCHAT_SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
                temperature=0.5,
            )
            return (response.choices[0].message.content or "").strip() or (
                "您好，我是思医。我可以帮助您上传医学文档、构建知识库，并基于知识库进行问答与来源追溯。"
            )
        except Exception as exc:
            logger.warning("[orchestrator] chitchat llm failed: %s", exc)
            return "您好，我是思医。我可以帮助您上传医学文档、构建知识库，并基于知识库进行问答与来源追溯。"


# 模块级单例
orchestrator = ChatOrchestrator()
