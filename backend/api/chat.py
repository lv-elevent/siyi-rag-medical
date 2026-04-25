from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import StreamingResponse

from backend.models.chat import ChatRequest, ChatResponse
from backend.services.agent.medical_agent import MedicalAgent
from backend.services.agent.agent_controller import AgentController
from backend.services.retrieval_service import semantic_search
from backend.services.knowledge_service import get_or_create_default_kb, ensure_document_link
from backend.core.llm_client import generate_answer_with_llm
from backend.services.query_classifier import classify_medical_question
from backend.services.safety_guard import safety_filter
from backend.core.logger_config import setup_logger
from backend.services.agent.memory import memory_manager, ConversationTurn
from backend.core.llm_client import generate_answer_with_llm_stream
from backend.core.security import get_current_user
from backend.database.session import get_db
from fastapi import Body
from pydantic import BaseModel
from backend.database.models import ChatSession, ChatMessage, RetrievalLog, KnowledgeBase, KnowledgeBaseDocument, Document

import logging
import json
import asyncio
from openai import APITimeoutError, APIConnectionError

from datetime import datetime
import uuid
import re

logger = setup_logger(__name__, logging.INFO)
router = APIRouter()


def normalize_llm_answer(text: str) -> str:
    if not text:
        return text

    text = str(text).replace("\r\n", "\n").replace("\r", "\n").strip()

    # 统一中英文引号
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")

    # 去掉 markdown 标题符号
    text = re.sub(r'^\s*###\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*##\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*#\s*', '', text, flags=re.MULTILINE)

    # 把四级标题转成更自然的中文小节格式
    text = re.sub(r'^\s*####\s*(.+?)\s*$', r'\1：', text, flags=re.MULTILINE)

    # 去掉单独一行的无意义粗体包裹
    text = re.sub(r'^\s*\*\*(.+?)\*\*\s*$', r'\1', text, flags=re.MULTILINE)

    # 清理粗体符号，但保留内容
    text = text.replace("**", "")

    # 把 markdown 无序列表统一成中文编号/普通列表
    text = re.sub(r'^\s*[\-\*]\s+', '• ', text, flags=re.MULTILINE)

    # 修复一些异常编号开头
    text = re.sub(r'^[\"\']+\.\s*', '2. ', text, flags=re.MULTILINE)
    text = re.sub(r'^[”’]+\.?\s*', '2. ', text, flags=re.MULTILINE)
    text = re.sub(r'^\*\*\.\s*', '2. ', text, flags=re.MULTILINE)

    # 修复类似 **1. xxx** 的写法
    text = re.sub(
        r'^\s*\*\*(\d+)\.\s*([^\n*]+?)\s*\*\*\s*$',
        lambda m: f"{m.group(1)}. {m.group(2).strip()}",
        text,
        flags=re.MULTILINE
    )

    # 修复类似 1. **xxx** 的写法
    text = re.sub(
        r'^\s*(\d+)\.\s*\*\*([^\n*]+?)\*\*\s*$',
        lambda m: f"{m.group(1)}. {m.group(2).strip()}",
        text,
        flags=re.MULTILINE
    )

    # 把“二.”、“三.”这种尽量统一一下
    text = re.sub(r'^\s*一[\.、]\s*', '1. ', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*二[\.、]\s*', '2. ', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*三[\.、]\s*', '3. ', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*四[\.、]\s*', '4. ', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*五[\.、]\s*', '5. ', text, flags=re.MULTILINE)

    # 清理流式拼接中偶发的角色残片行（如 "用户" / "user" / "assistant"）
    text = re.sub(
        r'^\s*(\d+\s*)?(user|assistant|用户|助手)\s*$',
        '',
        text,
        flags=re.IGNORECASE | re.MULTILINE
    )

    # 清理中文之间被异常插入的空白（如 "眼 肌麻痹" -> "眼肌麻痹"）
    text = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', text)

    # 清理行尾多余空格
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)

    # 清理多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()

def is_valid_rag_query(question: str, query_type: str) -> bool:
    q = question.strip()

    if len(q) <= 2:
        return False

    if q.isdigit():
        return False

    invalid_patterns = [
        "天气", "你好", "你是谁", "几点", "今天几号",
        "讲个笑话", "翻译", "写代码"
    ]

    for p in invalid_patterns:
        if p in q:
            return False

    return True


def generate_session_title(question: str, max_len: int = 20) -> str:
    q = (question or "").strip().replace("\n", " ")
    if not q:
        return "新对话"
    return q[:max_len] + ("..." if len(q) > max_len else "")


def get_kb_allowed_doc_ids(db, user_id: int, knowledge_base_id: int) -> list[int]:
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == knowledge_base_id, KnowledgeBase.user_id == user_id).first()
    if kb and (kb.name or "").strip() == "全库":
        return [int(x[0]) for x in db.query(Document.id).filter(Document.user_id == user_id).all()]

    docs = db.query(Document).filter(Document.user_id == user_id).all()
    for doc in docs:
        if doc.knowledge_base_id:
            ensure_document_link(db, doc.knowledge_base_id, doc.id, user_id)

    rows = (
        db.query(KnowledgeBaseDocument.document_id)
        .filter(
            KnowledgeBaseDocument.user_id == user_id,
            KnowledgeBaseDocument.knowledge_base_id == knowledge_base_id,
        )
        .all()
    )
    return [int(r[0]) for r in rows if r and r[0] is not None]


def get_or_create_session(
    db,
    user_id: int,
    session_id: str | None,
    first_question: str | None = None,
    knowledge_base_id: int | None = None,
):
    if session_id:
        session = db.query(ChatSession).filter_by(session_id=session_id).first()
        if session:
            if session.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="会话不存在"
                )

            if (
                knowledge_base_id is not None
                and session.knowledge_base_id is not None
                and session.knowledge_base_id != knowledge_base_id
            ):
                logger.info(
                    "[chat] 会话切换知识库 session_id=%s user_id=%s old_kb_id=%s new_kb_id=%s",
                    session.session_id,
                    user_id,
                    session.knowledge_base_id,
                    knowledge_base_id,
                )
                session.knowledge_base_id = knowledge_base_id
                session.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(session)
                return session

            if session.knowledge_base_id is None and knowledge_base_id is not None:
                session.knowledge_base_id = knowledge_base_id
                session.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(session)
            return session

    new_session_id = session_id or f"session_{uuid.uuid4().hex[:12]}"

    session = ChatSession(
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        session_id=new_session_id,
        title=generate_session_title(first_question),
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session


def save_user_message(db, session: ChatSession, user_id: int, question: str):
    msg = ChatMessage(
        chat_session_id=session.id,
        session_id=session.session_id,
        user_id=user_id,
        role="user",
        content=question,
        metadata_json=None,
        created_at=datetime.utcnow()
    )
    db.add(msg)

    # 自动标题：如果还是默认标题，则用首条问题生成
    if not session.title or session.title == "新对话":
        session.title = generate_session_title(question)

    session.updated_at = datetime.utcnow()
    db.commit()


def save_assistant_message(db, session: ChatSession, user_id: int, answer: str, sources=None):
    msg = ChatMessage(
        chat_session_id=session.id,
        session_id=session.session_id,
        user_id=user_id,
        role="assistant",
        content=answer,
        metadata_json={"sources": sources or []},
        created_at=datetime.utcnow()
    )
    db.add(msg)
    session.updated_at = datetime.utcnow()
    db.commit()

class DeleteChatSessionRequest(BaseModel):
    session_id: str

class UpdateChatSessionTitleRequest(BaseModel):
    session_id: str
    title: str

@router.post("/chat/session/title")
def update_chat_session_title(
    payload: UpdateChatSessionTitleRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.session_id == payload.session_id,
            ChatSession.user_id == current_user.id,
        )
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="标题不能为空"
        )

    # 最长 50，避免太长撑坏左侧 UI
    session.title = title[:50]
    session.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(session)

    return {
        "status": "success",
        "message": "标题已更新",
        "session": {
            "id": session.id,
            "session_id": session.session_id,
            "title": session.title,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        }
    }

@router.get("/chat/sessions")
def list_chat_sessions(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        .all()
    )

    return {
        "status": "success",
        "sessions": [
            {
                "id": s.id,
                "session_id": s.session_id,
                "title": s.title or "新对话",
                "status": s.status,
                "knowledge_base_id": s.knowledge_base_id,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ]
    }

@router.delete("/chat/session")
def delete_chat_session(
    payload: DeleteChatSessionRequest = Body(...),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.session_id == payload.session_id,
            ChatSession.user_id == current_user.id,
        )
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    try:
        # 1. 先删 retrieval_logs（依赖 chat_session_id / message_id）
        db.query(RetrievalLog).filter(
            RetrievalLog.chat_session_id == session.id,
            RetrievalLog.user_id == current_user.id,
        ).delete(synchronize_session=False)

        # 2. 再删 chat_messages
        db.query(ChatMessage).filter(
            ChatMessage.chat_session_id == session.id,
            ChatMessage.session_id == payload.session_id,
            ChatMessage.user_id == current_user.id,
        ).delete(synchronize_session=False)

        # 3. 最后删 chat_session
        db.delete(session)

        db.commit()

        return {
            "status": "success",
            "message": "会话已删除"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除会话失败: {str(e)}"
        )

@router.get("/chat/messages")
def list_chat_messages(
    session_id: str = Query(..., description="会话ID"),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.id,
        )
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    messages = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id == session_id,
            ChatMessage.user_id == current_user.id,
        )
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )

    return {
        "status": "success",
        "session": {
            "id": session.id,
            "session_id": session.session_id,
            "title": session.title or "新对话",
            "status": session.status,
            "knowledge_base_id": session.knowledge_base_id,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        },
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "metadata_json": m.metadata_json,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
) -> ChatResponse:
    try:
        if not request.question or not request.question.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="问题不能为空"
            )

        question = request.question.strip()
        logger.info(f"[chat] 用户问题: {question} user_id={getattr(current_user, 'id', None)}")

        if request.knowledge_base_id is not None:
            kb = (
                db.query(KnowledgeBase)
                .filter(
                    KnowledgeBase.id == request.knowledge_base_id,
                    KnowledgeBase.user_id == current_user.id,
                )
                .first()
            )
            if not kb:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="知识库不存在"
                )
        else:
            kb = get_or_create_default_kb(db, current_user)

        session = get_or_create_session(
            db,
            current_user.id,
            request.session_id,
            question,
            knowledge_base_id=kb.id,
        )
        save_user_message(db, session, current_user.id, question)
        allowed_doc_ids = get_kb_allowed_doc_ids(db, current_user.id, kb.id)
        if not allowed_doc_ids:
            return ChatResponse(
                answer="知识库未收录相关内容。",
                query_type="other",
                rewritten_query="",
                sources=[],
                needs_followup=False,
                followup_question="",
                status="success",
                session_id=session.session_id,
            )

        # 方案一：有白名单时禁用 kb_id 向量过滤，仅按 allowed_doc_ids 检索
        retrieval_kb_id = None if allowed_doc_ids else kb.id
        logger.info(
            "[chat] retrieval filter | session_id=%s kb_id=%s allowed_doc_ids=%s retrieval_kb_id=%s",
            session.session_id,
            kb.id,
            len(allowed_doc_ids or []),
            retrieval_kb_id,
        )

        if request.use_agent:
            agent = MedicalAgent()
            result = agent.process(
                question=question,
                document_id=request.document_id,
                session_id=session.session_id,
                stream=False,
                user_id=current_user.id,
                knowledge_base_id=retrieval_kb_id,
                allowed_doc_ids=allowed_doc_ids,
            )

            if result and getattr(result, "answer", None):
                save_assistant_message(
                    db,
                    session,
                    current_user.id,
                    result.answer,
                    getattr(result, "sources", []),
                )

                memory_manager.add_turn(
                    session.session_id,
                    ConversationTurn(
                        user_question=question,
                        assistant_answer=result.answer,
                        query_type=getattr(result, "query_type", "other"),
                        sources=getattr(result, "sources", []),
                    )
                )

            result.session_id = session.session_id
            return result

        query_type = classify_medical_question(question)
        logger.info("[medical-agent] classify result | question=%s | query_type=%s", question, query_type)
        logger.info(f"[chat] query_type: {query_type}")

        def reject_answer() -> ChatResponse:
            return ChatResponse(
                answer="知识库未收录相关内容。",
                query_type="other",
                rewritten_query="",
                sources=[],
                needs_followup=False,
                followup_question="",
                status="success",
                session_id=session.session_id,
            )

        if not is_valid_rag_query(question, query_type):
            logger.warning("[chat] Query Gate 拦截")
            return reject_answer()

        matched_results = semantic_search(
            question=question,
            top_k=3,
            document_id=request.document_id,
            query_type=query_type,
            user_id=current_user.id,
            knowledge_base_id=retrieval_kb_id,
            allowed_doc_ids=allowed_doc_ids,
        )

        logger.info(f"[chat] 命中 chunk 数量: {len(matched_results)}")

        if not matched_results:
            logger.warning("[chat] 无相关知识，返回拒答")
            return reject_answer()

        sources = []
        for item in matched_results:
            meta = item.get("metadata", {})
            sources.append({
                "filename": meta.get("filename", "未知文件"),
                "chunk_index": meta.get("chunk_index", 0),
                "distance": item.get("distance", 0)
            })

        context = "\n\n".join([item["text"] for item in matched_results if item.get("text")])

        answer_body = generate_answer_with_llm(
            question=question,
            context=context,
            query_type=query_type
        )

        if not answer_body:
            logger.warning("[chat] LLM 返回为空")
            return reject_answer()

        answer_body = normalize_llm_answer(answer_body.strip())

        answer_body, is_safe, warnings = safety_filter(
            answer_body,
            query_type
        )

        if warnings:
            logger.warning(f"[chat] 安全过滤 warnings: {warnings}")

        if not is_safe:
            logger.warning("[chat] safety_filter 判定不安全")
            return reject_answer()

        if (
            not answer_body
            or len(answer_body.strip()) < 3
            or "知识库未收录相关内容" in answer_body
            or "未找到" in answer_body
        ):
            logger.warning("[chat] 最终判定为无有效回答")
            return reject_answer()

        if session.session_id:
            memory_manager.add_turn(
                session.session_id,
                ConversationTurn(
                    user_question=question,
                    assistant_answer=answer_body,
                    query_type=query_type,
                    sources=sources,
                )
            )

        save_assistant_message(
            db,
            session,
            current_user.id,
            answer_body,
            sources
        )

        return ChatResponse(
            answer=answer_body,
            query_type=query_type,
            rewritten_query=question,
            sources=sources,
            needs_followup=False,
            followup_question="",
            status="success",
            session_id=session.session_id,
        )

    except HTTPException as http_exc:
        raise http_exc

    except (APITimeoutError, APIConnectionError):
        logger.error("[chat] LLM 调用超时或连接失败")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="回答请求超时，请稍后重试"
        )

    except Exception as exc:
        logger.error(f"[chat] 服务器内部错误: {repr(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )


@router.post("/chat-stream")
async def chat_stream(
    request: ChatRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    async def generate():
        accumulated_answer = ""
        has_streamed_chunk = False
        prepare_result = None

        try:
            if not request.question or not request.question.strip():
                yield f"data: {json.dumps({'type': 'message', 'data': '问题不能为空'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            question = request.question.strip()

            if request.knowledge_base_id is not None:
                kb = (
                    db.query(KnowledgeBase)
                    .filter(
                        KnowledgeBase.id == request.knowledge_base_id,
                        KnowledgeBase.user_id == current_user.id,
                    )
                    .first()
                )
                if not kb:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="知识库不存在"
                    )
            else:
                kb = get_or_create_default_kb(db, current_user)

            session = get_or_create_session(
                db,
                current_user.id,
                request.session_id,
                question,
                knowledge_base_id=kb.id,
            )
            save_user_message(db, session, current_user.id, question)
            allowed_doc_ids = get_kb_allowed_doc_ids(db, current_user.id, kb.id)
            if not allowed_doc_ids:
                yield f"data: {json.dumps({'type': 'message', 'data': '知识库未收录相关内容。'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 方案一：有白名单时禁用 kb_id 向量过滤，仅按 allowed_doc_ids 检索
            retrieval_kb_id = None if allowed_doc_ids else kb.id
            logger.info(
                "[chat_stream] retrieval filter | session_id=%s kb_id=%s allowed_doc_ids=%s retrieval_kb_id=%s",
                session.session_id,
                kb.id,
                len(allowed_doc_ids or []),
                retrieval_kb_id,
            )

            agent_controller = AgentController()
            # 先做路由分流，避免非医疗问题进入医疗检索链路
            route_result = agent_controller.router.route(question)
            route_type = route_result.get("type", "medical")
            logger.info("[chat_stream] route_type=%s", route_type)

            if route_type in {"high_risk", "chitchat", "out_of_scope"}:
                controller_result = agent_controller.handle(
                    query=question,
                    user_id=current_user.id,
                    session_id=session.session_id,
                    document_id=request.document_id,
                    knowledge_base_id=kb.id,
                    allowed_doc_ids=allowed_doc_ids,
                )
                answer = controller_result.get("answer", "") or "我是思医医疗知识库助手。"

                # 按现有 SSE 协议输出
                yield f"data: {json.dumps({'type': 'chunk', 'data': answer}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'sources', 'data': controller_result.get('sources', []) or []}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return
            agent = MedicalAgent()
            prepare_result = agent.prepare(
                question=question,
                document_id=request.document_id,
                session_id=session.session_id,
                user_id=current_user.id,
                knowledge_base_id=retrieval_kb_id,
                allowed_doc_ids=allowed_doc_ids,
            )

            logger.info(
                "[chat_stream] prepare_result | status=%s | question=%s | query_type=%s | rewritten_query=%s | retrieval_query=%s | sources_count=%s",
                prepare_result.status,
                question,
                prepare_result.query_type,
                prepare_result.rewritten_query,
                getattr(prepare_result, "retrieval_query", None),
                len(prepare_result.sources or [])
            )

            logger.info(
                "[chat_stream] full_context_length=%s",
                len(prepare_result.full_context or "")
            )

            if prepare_result.status == "error":
                error_message = prepare_result.error_message or "系统异常"

                save_assistant_message(
                    db,
                    session,
                    current_user.id,
                    error_message,
                    []
                )

                yield f"data: {json.dumps({'type': 'message', 'data': error_message}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            if prepare_result.status == "followup":
                yield f"data: {json.dumps({'type': 'followup', 'data': {'question': prepare_result.followup_question or '请补充更多信息。'}}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            if prepare_result.status == "empty":
                fallback_message = prepare_result.error_message or "知识库未收录相关内容。"

                save_assistant_message(
                    db,
                    session,
                    current_user.id,
                    fallback_message,
                    []
                )

                yield f"data: {json.dumps({'type': 'message', 'data': fallback_message}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            # ✅ 统一生成阶段使用的 query，和 process() 保持一致
            answer_question = (
                prepare_result.retrieval_query
                or prepare_result.rewritten_query
                or prepare_result.question
            )

            logger.debug("[chat_stream] answer_question=%s", answer_question)

            for token in generate_answer_with_llm_stream(
                question=answer_question,
                context=prepare_result.full_context,
                query_type=prepare_result.query_type
            ):
                if token == "[DONE]":
                    break

                accumulated_answer += token
                has_streamed_chunk = True
                yield f"data: {json.dumps({'type': 'chunk', 'data': token}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)

            final_answer = normalize_llm_answer(accumulated_answer.strip())
            logger.info("[chat_stream] final_answer length=%s", len(final_answer.strip()) if final_answer else 0)

            # ===== 流式答案有效性校验 =====
            if not final_answer:
                if has_streamed_chunk:
                    logger.warning("[chat_stream] 已有流式输出，跳过 fallback 覆盖")
                    yield "data: [DONE]\n\n"
                    return
                else:
                    yield f"data: {json.dumps({'type': 'message', 'data': '知识库未收录相关内容。'}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

            final_answer, is_safe, warnings = safety_filter(
                final_answer,
                prepare_result.query_type
            )
            logger.info("[chat_stream] after safety_filter | is_safe=%s | warnings=%s", is_safe, warnings)

            if warnings:
                logger.warning("[chat_stream] 安全过滤 warnings: %s", warnings)

            logger.debug(
                "[chat_stream] fallback_check | is_safe=%s | empty=%s | too_short=%s | has_reject_text=%s",
                is_safe,
                (not final_answer),
                (len(final_answer.strip()) < 8 if final_answer else True),
                (
                    ("知识库未收录相关内容" in final_answer)
                    or ("未找到" in final_answer)
                    or ("暂无相关内容" in final_answer)
                ) if final_answer else False
            )

            normalized_answer = final_answer.strip()

            fallback_exact_texts = {
                "知识库未收录相关内容",
                "知识库未收录相关内容。",
                "未找到",
                "未找到相关内容",
                "暂无相关内容",
                "暂无相关内容。"
            }

            if (
                not is_safe
                or not normalized_answer
                or len(normalized_answer) < 8
                or normalized_answer in fallback_exact_texts
            ):
                fallback_message = "知识库未收录相关内容。"

                save_assistant_message(
                    db,
                    session,
                    current_user.id,
                    fallback_message,
                    []
                )

                yield f"data: {json.dumps({'type': 'message', 'data': fallback_message}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            # ===== 只有有效答案才保存 + 返回来源 =====
            memory_manager.add_turn(
                session.session_id,
                ConversationTurn(
                    user_question=prepare_result.question,
                    assistant_answer=final_answer,
                    query_type=prepare_result.query_type,
                    sources=prepare_result.sources
                )
            )

            save_assistant_message(
                db,
                session,
                current_user.id,
                final_answer,
                prepare_result.sources
            )

            yield f"data: {json.dumps({'type': 'sources', 'data': prepare_result.sources or []}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"[chat_stream] 异常: {repr(e)}", exc_info=True)
            yield f"data: {json.dumps({'type': 'message', 'data': '生成回答时发生错误，请稍后重试'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
