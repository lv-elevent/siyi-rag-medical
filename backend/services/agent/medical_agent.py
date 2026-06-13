"""
MedicalAgent - 医疗 RAG Agent 基础实现
职责：串联医疗 RAG 核心能力，提供统一的 Agent 编排流程
实现：基于现有服务的轻量级编排，不引入额外复杂依赖
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from backend.models.chat import ChatResponse
from backend.services.query_classifier import classify_medical_question
from backend.services.query_rewriter import rewrite_medical_question
from backend.services.retrieval_service import semantic_search
from backend.core.llm_client import generate_answer_with_llm
from backend.services.safety_guard import safety_filter
from backend.services.agent.memory import memory_manager, ConversationTurn
from backend.core.medical_terms import (
    VAGUE_QUESTION,
    PRONOUN,
    CONTEXTUAL_MARKER,
    INVALID_QUERY_PATTERNS,
    GENERIC_HISTORY_QUESTION,
    SHORT_MEDICAL,
    FOLLOWUP_TRIGGER,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentPrepareResult:
    """Agent 前处理结果数据结构"""
    status: str
    question: str
    query_type: str
    contextual_query: str
    rewritten_query: str
    full_context: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    retrieval_query: str = ""
    followup_question: Optional[str] = None
    error_message: Optional[str] = None
    history_turns: int = 0
    followup_reason: Optional[str] = None


class MedicalAgent:
    """
    query classification → query rewrite → retrieval → answer generation → safety guard
    """

    # ── 引用统一词表（全项目唯一来源）──
    VAGUE_QUESTIONS = VAGUE_QUESTION
    PRONOUN_PATTERNS = PRONOUN
    CONTEXTUAL_MARKERS = CONTEXTUAL_MARKER
    INVALID_PATTERNS = INVALID_QUERY_PATTERNS
    GENERIC_HISTORY_QUESTIONS = GENERIC_HISTORY_QUESTION
    SHORT_MEDICAL_TERMS = SHORT_MEDICAL
    FOLLOWUP_TRIGGERS = FOLLOWUP_TRIGGER

    def prepare(
        self,
        question: str,
        document_id: str = None,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None,
        knowledge_base_id: Optional[int] = None,
        allowed_doc_ids: Optional[List[int]] = None,
        db=None,
    ) -> AgentPrepareResult:
        logger.info("[medical-agent] prepare start")

        if not question or not isinstance(question, str) or not question.strip():
            logger.warning("[medical-agent] 问题为空，返回错误")
            return self._build_prepare_result(
                status="error",
                question="",
                query_type="other",
                contextual_query="",
                rewritten_query="",
                full_context="",
                error_message="问题不能为空"
            )

        question = question.strip()
        logger.info("[medical-agent] 用户问题: %s", question)

        query_type = classify_medical_question(question)
        logger.info("[medical-agent] classify result | question=%s | query_type=%s", question, query_type)

        # 强制识别追问问题
        if self._is_followup_question(question):
            query_type = "followup"
            logger.info("[medical-agent] override to followup | question=%s", question)

        logger.info("[medical-agent] after followup check | question=%s | query_type=%s", question, query_type)

        logger.info("[medical-agent] query_type: %s", query_type)

        if not self._is_valid_rag_query(question, query_type):
            logger.warning("[medical-agent] Query Gate 拦截")
            return self._build_prepare_result(
                status="empty",
                question=question,
                query_type=query_type,
                contextual_query="",
                rewritten_query="",
                full_context="",
                error_message="知识库未收录相关内容，你可以上传相关文档。"
            )

        history, history_turns = self._load_history(
            session_id,
            user_id=user_id,
            db=db,
        )

        followup_result = self._analyze_followup_need(question, history, query_type)
        if followup_result["needs_followup"]:
            logger.info(
                "[medical-agent] 需要追问: %s (原因: %s)",
                followup_result["followup_question"],
                followup_result["reason"]
            )
            return self._build_prepare_result(
                status="followup",
                question=question,
                query_type=query_type,
                contextual_query="",
                rewritten_query=question,
                full_context="",
                followup_question=followup_result["followup_question"],
                followup_reason=followup_result["reason"],
                history_turns=history_turns
            )

        contextual_query = self._build_contextual_query(question, history)

        rewrite_result = rewrite_medical_question(contextual_query, query_type)
        logger.info("[medical-agent] rewrite_result=%s", rewrite_result)

        rewritten_query, query_type, rewrite_strategy = self._parse_rewrite_result(
            rewrite_result=rewrite_result,
            fallback_query=contextual_query,
            fallback_query_type=query_type
        )

        logger.info(
            "[medical-agent] rewrite done | contextual=%s | rewritten=%s | strategy=%s | query_type=%s",
            contextual_query,
            rewritten_query,
            rewrite_strategy,
            query_type
        )

        matched_results, retrieval_query = self._retrieval_with_fallback(
            rewritten_query=rewritten_query,
            contextual_query=contextual_query,
            original_question=question,
            document_id=document_id,
            query_type=query_type,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            allowed_doc_ids=allowed_doc_ids,
        )

        if not matched_results:
            logger.warning("[medical-agent] 无相关知识，返回拒答")
            return self._build_prepare_result(
                status="empty",
                question=question,
                query_type=query_type,
                contextual_query=contextual_query,
                rewritten_query=rewritten_query,
                full_context="",
                retrieval_query=retrieval_query,
                error_message="知识库未收录相关内容，你可以上传相关文档入库。",
                history_turns=history_turns
            )

        sources = self._build_sources(matched_results)
        full_context = self._build_full_context(
            matched_results,
            history,
            question,
            session_id=session_id or "",
            user_id=user_id,
        )

        logger.info(
            "[medical-agent] prepare ready | question=%s | query_type=%s | retrieval_query=%s | sources_count=%s | history_turns=%s",
            question,
            query_type,
            retrieval_query,
            len(sources),
            history_turns
        )
        return self._build_prepare_result(
            status="ready",
            question=question,
            query_type=query_type,
            contextual_query=contextual_query,
            rewritten_query=rewritten_query,
            full_context=full_context,
            sources=sources,
            retrieval_query=retrieval_query,
            history_turns=history_turns
        )

    def process(
        self,
        question: str,
        document_id: str = None,
        session_id: Optional[str] = None,
        stream: bool = False,
        user_id: Optional[int] = None,
        knowledge_base_id: Optional[int] = None,
        allowed_doc_ids: Optional[List[int]] = None,
        db=None,
    ) -> ChatResponse:
        logger.info("[medical-agent] process 启动")

        prepare_result = self.prepare(
            question=question,
            document_id=document_id,
            session_id=session_id,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            allowed_doc_ids=allowed_doc_ids,
            db=db,
        )

        if prepare_result.status == "error":
            return self._build_chat_response(
                prepare_result=prepare_result,
                answer=prepare_result.error_message or "问题不能为空",
                status="error"
            )

        if prepare_result.status == "followup":
            return self._build_chat_response(
                prepare_result=prepare_result,
                answer="",
                needs_followup=True,
                followup_question=prepare_result.followup_question
            )

        if prepare_result.status == "empty":
            return self._build_chat_response(
                prepare_result=prepare_result,
                answer=prepare_result.error_message or "知识库未收录相关内容，你可以上传相关文档入库。"
            )

        answer_question = (
            prepare_result.retrieval_query
            or prepare_result.rewritten_query
            or prepare_result.question
        )
        answer_question = self._safe_query_string(
            answer_question,
            fallback=prepare_result.question
        )

        answer_body = generate_answer_with_llm(
            question=answer_question,
            context=prepare_result.full_context,
            query_type=prepare_result.query_type
        )

        if not answer_body:
            return self._build_chat_response(
                prepare_result=prepare_result,
                answer="知识库未收录相关内容，你可以上传相关文档入库。"
            )

        answer_body = answer_body.strip()

        answer_body, is_safe, warnings = safety_filter(
            answer_body,
            prepare_result.query_type
        )

        if warnings:
            logger.warning("[medical-agent] 安全过滤 warnings: %s", warnings)

        if not is_safe:
            logger.warning("[medical-agent] safety_filter 判定不安全，返回兜底答复")
            return self._build_chat_response(
                prepare_result=prepare_result,
                answer="知识库未收录相关内容，你可以上传相关文档入库。"
            )

        if self._should_fallback_empty_answer(answer_body):
            return self._build_chat_response(
                prepare_result=prepare_result,
                answer="知识库未收录相关内容，你可以上传相关文档入库。"
            )

        if session_id:
            self._save_conversation_memory(
                session_id=session_id,
                question=prepare_result.question,
                answer=answer_body,
                query_type=prepare_result.query_type,
                sources=prepare_result.sources,
                user_id=user_id,
            )

        return self._build_chat_response(
            prepare_result=prepare_result,
            answer=answer_body
        )

    def _is_followup_question(self, question: str) -> bool:
        q = question.strip()
        has_followup_trigger = any(k in q for k in self.FOLLOWUP_TRIGGERS)
        hit_medical_term = any(term in q for term in self.SHORT_MEDICAL_TERMS)

        # 短术语不等于追问，命中医学术语且无追问词时明确跳过
        if hit_medical_term and not has_followup_trigger:
            logger.info("[medical-agent] skip followup: recognized medical term | question=%s", q)
            return False

        if has_followup_trigger:
            return True

        return False
    
    def _build_prepare_result(
        self,
        status: str,
        question: str,
        query_type: str,
        contextual_query: str,
        rewritten_query: str,
        full_context: str,
        sources: Optional[List[Dict[str, Any]]] = None,
        retrieval_query: str = "",
        followup_question: Optional[str] = None,
        error_message: Optional[str] = None,
        history_turns: int = 0,
        followup_reason: Optional[str] = None
    ) -> AgentPrepareResult:
        return AgentPrepareResult(
            status=status,
            question=question,
            query_type=query_type,
            contextual_query=contextual_query,
            rewritten_query=rewritten_query,
            full_context=full_context,
            sources=sources or [],
            retrieval_query=retrieval_query,
            followup_question=followup_question,
            error_message=error_message,
            history_turns=history_turns,
            followup_reason=followup_reason
        )

    def _build_chat_response(
        self,
        prepare_result: AgentPrepareResult,
        answer: str,
        status: str = "success",
        needs_followup: bool = False,
        followup_question: Optional[str] = None
    ) -> ChatResponse:
        return ChatResponse(
            answer=answer,
            query_type=prepare_result.query_type,
            rewritten_query=prepare_result.rewritten_query,
            sources=prepare_result.sources,
            needs_followup=needs_followup,
            followup_question=followup_question,
            status=status
        )

    def _load_history(
        self,
        session_id: Optional[str],
        user_id: Optional[int] = None,
        db=None,
    ) -> Tuple[List[ConversationTurn], int]:
        if not session_id:
            return [], 0

        history = memory_manager.get_session_history(session_id)
        history_turns = len(history)

        # 冷启动恢复：如果内存/Redis 中没有数据，尝试从 MySQL 回填
        if history_turns == 0 and db is not None and user_id is not None:
            recovered = memory_manager.recover_from_db(session_id, user_id, db)
            if recovered > 0:
                history = memory_manager.get_session_history(session_id)
                history_turns = len(history)
                logger.info("[medical-agent] cold-start recovered %s turns from DB", history_turns)

        logger.info("[medical-agent] 读取历史对话: %s 轮", history_turns)
        return history, history_turns

    def _parse_rewrite_result(
        self,
        rewrite_result: Any,
        fallback_query: str,
        fallback_query_type: str
    ) -> Tuple[str, str, str]:
        rewritten_query = fallback_query
        query_type = fallback_query_type
        rewrite_strategy = "preserve"

        try:
            if isinstance(rewrite_result, dict):
                rewritten_query = rewrite_result.get("rewritten_query") or fallback_query
                query_type = rewrite_result.get("query_type") or fallback_query_type
                rewrite_strategy = rewrite_result.get("rewrite_strategy") or "preserve"
            elif isinstance(rewrite_result, str):
                rewritten_query = rewrite_result or fallback_query
                rewrite_strategy = "legacy"
            else:
                logger.warning(
                    "[medical-agent] rewrite 返回未知类型: %s",
                    type(rewrite_result)
                )
        except Exception as e:
            logger.warning("[medical-agent] 解析 rewrite_result 异常: %s", e)

        if not isinstance(rewritten_query, str):
            logger.warning("[medical-agent] rewritten_query 不是字符串，回退 fallback_query")
            rewritten_query = fallback_query

        rewritten_query = rewritten_query.strip()
        if not rewritten_query:
            rewritten_query = fallback_query

        if not isinstance(query_type, str) or not query_type.strip():
            query_type = fallback_query_type

        if not isinstance(rewrite_strategy, str) or not rewrite_strategy.strip():
            rewrite_strategy = "preserve"

        return rewritten_query, query_type, rewrite_strategy

    def _safe_query_string(self, value: Any, fallback: str = "") -> str:
        if isinstance(value, str):
            value = value.strip()
            return value if value else fallback

        if isinstance(value, dict):
            candidate = value.get("rewritten_query") or value.get("original_query") or fallback
            if isinstance(candidate, str):
                candidate = candidate.strip()
                return candidate if candidate else fallback

        return fallback

    def _get_dynamic_top_k(self, question: str) -> int:
        q = question.strip()

        summary_keywords = [
            "危害", "症状", "影响", "并发症",
            "原因", "风险", "治疗", "有哪些",
            "是什么", "预防措施"
        ]

        precise_keywords = [
            "会传染吗", "怎么防范", "怎么预防",
            "怎么办", "严重吗", "危险吗",
            "吃什么药", "能治好吗"
        ]

        if any(k in q for k in precise_keywords):
            return 1

        if any(k in q for k in summary_keywords):
            return 3

        return 2

    def _filter_same_topic_results(
        self,
        matched_results: List[Dict[str, Any]],
        question: str
    ) -> List[Dict[str, Any]]:
        q = question.strip()

        disease_keywords = {
            "结核": ["结核", "肺结核", "结核病"],
            "高血压": ["高血压", "血压"],
            "糖尿病": ["糖尿病", "血糖"]
        }

        current_topic = None

        for topic, words in disease_keywords.items():
            if any(w in q for w in words):
                current_topic = topic
                break

        if not current_topic:
            return matched_results

        filtered = []

        for item in matched_results:
            text = item.get("text", "")
            if any(w in text for w in disease_keywords[current_topic]):
                filtered.append(item)

        return filtered if filtered else matched_results[:1]

    def _retrieval_with_fallback(
        self,
        rewritten_query: Any,
        contextual_query: Any,
        original_question: Any,
        document_id: Optional[str],
        query_type: str,
        user_id: Optional[int] = None,
        knowledge_base_id: Optional[int] = None,
        allowed_doc_ids: Optional[List[int]] = None,
    ) -> Tuple[List[Dict[str, Any]], str]:

        if user_id is None:
            raise ValueError("user_id is required for retrieval")

        safe_rewritten = self._safe_query_string(rewritten_query, fallback="")
        safe_contextual = self._safe_query_string(contextual_query, fallback="")
        safe_original = self._safe_query_string(original_question, fallback="")

        queries_to_try: List[Tuple[str, str]] = []

        if safe_rewritten:
            queries_to_try.append(("rewritten", safe_rewritten))
        if safe_contextual and safe_contextual != safe_rewritten:
            queries_to_try.append(("contextual", safe_contextual))
        if safe_original and safe_original not in (safe_rewritten, safe_contextual):
            queries_to_try.append(("original", safe_original))

        logger.info(
            "[retrieval] fallback queries=%s | user_id=%s | document_id=%s | knowledge_base_id=%s",
            [q[0] for q in queries_to_try],
            user_id,
            document_id,
            knowledge_base_id,
        )
        logger.info(
            "[kb_trace][medical_agent] user_id=%s | knowledge_base_id=%s | allowed_doc_ids_count=%s | document_id=%s",
            user_id,
            knowledge_base_id,
            len(allowed_doc_ids or []),
            document_id,
        )

        last_exception = None

        for query_name, query in queries_to_try:
            try:
                logger.info(
                    "[retrieval] trying %s query: %s",
                    query_name,
                    query
                )

                results = semantic_search(
                    question=query,
                    top_k=5,
                    document_id=document_id,
                    query_type=query_type,
                    user_id=user_id,
                    knowledge_base_id=knowledge_base_id,
                    allowed_doc_ids=allowed_doc_ids,
                )

                if results:
                    filtered_results = self._filter_same_topic_results(results, safe_original or query)
                    logger.info(
                        "[retrieval] success | strategy=%s | hits=%s | filtered_hits=%s",
                        query_name,
                        len(results),
                        len(filtered_results)
                    )
                    return filtered_results, query

                logger.info("[retrieval] empty result for %s", query_name)

            except Exception as e:
                logger.warning(
                    "[retrieval] %s 查询异常: %s",
                    query_name,
                    str(e)
                )
                last_exception = e
                continue

        if last_exception is not None:
            logger.error(
                "[retrieval] 所有查询策略异常结束 | last_exception=%s",
                repr(last_exception)
            )
        else:
            logger.info("[retrieval] 各查询策略均无命中")

        return [], safe_rewritten or safe_contextual or safe_original

    def _build_sources(
        self,
        matched_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        sources: List[Dict[str, Any]] = []
        for item in matched_results:
            meta = item.get("metadata", {})
            document_id = meta.get("document_id") or meta.get("doc_id")
            kb_id = meta.get("kb_id") or meta.get("knowledge_base_id")
            page = meta.get("page") or meta.get("page_number")
            title = meta.get("title") or meta.get("document_title")
            source_item = {
                "filename": meta.get("filename", "未知文件"),
                "chunk_index": meta.get("chunk_index", 0),
                "distance": item.get("distance", 0),
                "document_id": document_id,
                "kb_id": kb_id,
                "page": page,
                "title": title,
            }
            sources.append(source_item)
        files = sorted({str(s.get("filename", "未知文件")) for s in sources})
        logger.info("[sources] count=%s | files=%s", len(sources), files)
        return sources

    def _should_use_history(
        self,
        question: str,
        history: List[ConversationTurn]
    ) -> bool:
        if not history:
            return False

        q = question.strip()

        contextual_markers = [
            "这个", "那个", "这种", "那种", "它",
            "这个病", "这种病", "这种情况",
            "这个症状", "这种症状"
        ]

        followup_keywords = [
            "会不会", "是否", "能不能", "可不可以",
            "怎么办", "严重吗", "危险吗",
            "怎么治疗", "吃什么药", "多久",
            "需要住院吗"
        ]

        if any(marker in q for marker in contextual_markers):
            return True

        if any(word in q for word in followup_keywords):
            return True

        return False

    def _build_full_context(
        self,
        matched_results: List[Dict[str, Any]],
        history: List[ConversationTurn],
        question: str = "",
        session_id: str = "",
        user_id: int | None = None,
    ) -> str:
        # ── RAG 知识库上下文 ──
        chunk_texts: List[str] = []
        for idx, item in enumerate(matched_results):
            text = item.get("text")
            if not isinstance(text, str):
                text = str(text or "")
            text = text.strip()
            if text:
                chunk_texts.append(text)

        rag_context = "\n\n".join(chunk_texts).strip()

        # 最小上下文保护
        if matched_results and len(rag_context) < 50:
            top_text = matched_results[0].get("text")
            if not isinstance(top_text, str):
                top_text = str(top_text or "")
            top_text = top_text.strip()
            if top_text:
                rag_context = top_text
                while len(rag_context) < 50:
                    rag_context = f"{rag_context}\n{top_text}".strip()

        # ── 三层记忆上下文 ──
        memory_block = ""
        if session_id and user_id is not None:
            try:
                ctx = memory_manager.get_context_for_query(session_id, question, user_id)
                memory_block = ctx.to_prompt_block()
                if memory_block:
                    logger.info(
                        "[memory] context assembled | semantic=%s summary=%s recent=%s",
                        len(ctx.semantic_memories),
                        "yes" if ctx.summary else "no",
                        len(ctx.recent_turns),
                    )
            except Exception as exc:
                logger.warning("[memory] failed to get context: %s", exc)

        # ── 组装最终上下文 ──
        parts: list[str] = []
        if memory_block:
            parts.append(memory_block)
        if rag_context:
            parts.append(f"【知识库内容】\n{rag_context}")

        final_context = "\n\n".join(parts) if parts else ""

        logger.debug(
            "[context] final | rag_len=%s memory_len=%s total_len=%s",
            len(rag_context), len(memory_block), len(final_context),
        )
        return final_context

    def _save_conversation_memory(
        self,
        session_id: str,
        question: str,
        answer: str,
        query_type: str,
        sources: List[Dict[str, Any]],
        user_id: int | None = None,
    ) -> None:
        turn = ConversationTurn(
            user_question=question,
            assistant_answer=answer,
            query_type=query_type,
            sources=sources,
        )
        memory_manager.add_turn(session_id, turn)

        # 每 5 轮触发一次语义记忆抽取（异步不会阻塞响应）
        if memory_manager.should_extract(session_id) and user_id is not None:
            try:
                extracted = memory_manager.trigger_extraction(session_id, user_id)
                if extracted:
                    logger.info(
                        "[memory] extracted %s memories for session=%s: %s",
                        len(extracted), session_id, [e[:30] for e in extracted],
                    )
            except Exception as exc:
                logger.warning("[memory] extraction skipped: %s", exc)

    def _should_fallback_empty_answer(self, answer_body: str) -> bool:
        if not answer_body:
            return True

        normalized = answer_body.strip()

        if len(normalized) < 8:
            return True

        fallback_exact = {
            "知识库未收录相关内容",
            "未找到",
            "暂无相关内容"
        }

        if normalized in fallback_exact:
            return True

        return False

    def _format_history(
        self,
        history: List[ConversationTurn],
        max_turns: int = 2
    ) -> str:
        if not history:
            return ""

        recent_turns = history[-max_turns:]

        lines = []
        for turn in recent_turns:
            lines.append(turn.user_question.strip())

        return "；".join(lines)

    def _analyze_followup_need(
        self,
        question: str,
        history: List[ConversationTurn],
        query_type: str
    ) -> Dict[str, Any]:
        q = question.strip()
        result = {"needs_followup": False, "followup_question": None, "reason": "none"}
        has_followup_trigger = any(k in q for k in self.FOLLOWUP_TRIGGERS)
        hit_medical_term = any(term in q for term in self.SHORT_MEDICAL_TERMS)

        # 短术语名词型输入默认不追问，优先进入检索与回答
        if hit_medical_term and not has_followup_trigger:
            logger.info("[medical-agent] skip followup: recognized medical term | question=%s", q)
            return result

        if len(q) <= 2:
            result.update({
                "needs_followup": True,
                "followup_question": "请再具体描述一下您的问题。",
                "reason": "too_short"
            })
            return result

        if q in self.VAGUE_QUESTIONS and not history:
            result.update({
                "needs_followup": True,
                "followup_question": "请说明您具体指的是什么疾病、症状或情况。",
                "reason": "vague_no_context"
            })
            return result

        pronoun_count = sum(1 for p in self.PRONOUN_PATTERNS if p in q)
        if pronoun_count > 0 and not history:
            result.update({
                "needs_followup": True,
                "followup_question": "您提到的对象不够明确，请补充具体的疾病、症状或场景。",
                "reason": "pronoun_without_reference"
            })
            return result

        return result

    def _build_contextual_query(self, question, history):
        q = question.strip()

        if not history:
            return q

        latest_question = history[-1].user_question.strip()

        # 只有明显代词型追问，才拼上一轮
        contextual_markers = [
            "这个", "那个", "这种", "那种", "它",
            "这个病", "这种病", "这种情况",
            "这个症状", "这种症状"
        ]

        followup_keywords = [
            "怎么办", "严重吗", "危险吗",
            "会传染吗", "怎么治疗", "吃什么药",
            "多久能好", "需要住院吗"
        ]

        if any(m in q for m in contextual_markers) or any(k in q for k in followup_keywords):
            return f"关于“{latest_question}”，{q}"

        return q

    def _is_valid_rag_query(self, question: str, query_type: str) -> bool:
        q = question.strip()

        if len(q) <= 2:
            return False

        if q.isdigit():
            return False

        return not any(pattern in q for pattern in self.INVALID_PATTERNS)