"""
Chat API 路由层

职责：HTTP 请求/响应处理，参数校验，编排调用 service 层。
所有业务逻辑已下沉至：
- chat_orchestrator  (问答编排：路由→检索→生成→安全)
- answer_formatter   (LLM 输出清洗、答案校验)
- session_service    (会话创建/查询/删除、消息持久化)
- knowledge_service  (知识库校验、文档白名单)
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import StreamingResponse

from backend.models.chat import ChatRequest
from backend.services.knowledge_service import get_or_resolve_kb, get_kb_allowed_doc_ids
from backend.services.session_service import (
    get_or_create_session,
    get_user_session_or_404,
    save_user_message,
    save_assistant_message,
    delete_session_cascade,
)
from backend.services.chat_orchestrator import orchestrator
from backend.services.agent.memory import memory_manager, ConversationTurn
from backend.core.logger_config import setup_logger
from backend.core.security import get_current_user
from backend.database.session import get_db
from pydantic import BaseModel
from backend.database.models import ChatSession, ChatMessage

import logging
import json
from datetime import datetime

logger = setup_logger(__name__, logging.INFO)
router = APIRouter()

# ============================================================
# 请求模型
# ============================================================

class DeleteChatSessionRequest(BaseModel):
    session_id: str

class UpdateChatSessionTitleRequest(BaseModel):
    session_id: str
    title: str

# ============================================================
# 公用辅助
# ============================================================

def _empty_kb_response(session_id: str = "") -> dict:
    return {"answer": "知识库未收录相关内容。", "sources": []}

# ============================================================
# 会话管理路由
# ============================================================

@router.post("/chat/session/title")
def update_chat_session_title(
    payload: UpdateChatSessionTitleRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    session = get_user_session_or_404(db, payload.session_id, current_user.id)
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标题不能为空")
    session.title = title[:50]
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return {
        "status": "success", "message": "标题已更新",
        "session": {
            "id": session.id, "session_id": session.session_id,
            "title": session.title,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        },
    }


@router.get("/chat/sessions")
def list_chat_sessions(current_user=Depends(get_current_user), db=Depends(get_db)):
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
                "id": s.id, "session_id": s.session_id,
                "title": s.title or "新对话", "status": s.status,
                "knowledge_base_id": s.knowledge_base_id,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ],
    }


@router.delete("/chat/session")
def delete_chat_session(
    payload: DeleteChatSessionRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    session = get_user_session_or_404(db, payload.session_id, current_user.id)
    try:
        delete_session_cascade(db, session, current_user.id)
        return {"status": "success", "message": "会话已删除"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"删除会话失败: {str(e)}")


@router.get("/chat/messages")
def list_chat_messages(
    session_id: str = Query(..., description="会话ID"),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    session = get_user_session_or_404(db, session_id, current_user.id)
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id, ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )
    return {
        "status": "success",
        "session": {
            "id": session.id, "session_id": session.session_id,
            "title": session.title or "新对话", "status": session.status,
            "knowledge_base_id": session.knowledge_base_id,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        },
        "messages": [
            {
                "id": m.id, "role": m.role, "content": m.content,
                "metadata_json": m.metadata_json,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


# ============================================================
# 问答路由
# ============================================================

@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """非流式问答 — 统一走 ChatOrchestrator + MedicalAgent"""
    try:
        if not request.question or not request.question.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问题不能为空")

        question = request.question.strip()
        logger.info("[chat] question=%s user_id=%s", question, getattr(current_user, 'id', None))

        # ── 预处理 ──
        kb = get_or_resolve_kb(db, request.knowledge_base_id, current_user)
        session = get_or_create_session(db, current_user.id, request.session_id, question, kb.id)
        save_user_message(db, session, current_user.id, question)

        allowed_doc_ids = get_kb_allowed_doc_ids(db, current_user.id, kb.id)
        retrieval_kb_id = None if allowed_doc_ids else kb.id

        if not allowed_doc_ids:
            return _empty_kb_response(session.session_id)

        # ── 编排执行 ──
        result = orchestrator.execute(
            question=question,
            user_id=current_user.id,
            session_id=session.session_id,
            knowledge_base_id=retrieval_kb_id,
            allowed_doc_ids=allowed_doc_ids,
            document_id=request.document_id,
            db=db,
        )

        # ── 后处理 ──
        answer = getattr(result, "answer", "")
        sources = getattr(result, "sources", [])
        query_type = getattr(result, "query_type", "other")

        if answer:
            save_assistant_message(db, session, current_user.id, answer, sources)
            memory_manager.add_turn(
                session.session_id,
                ConversationTurn(
                    user_question=question, assistant_answer=answer,
                    query_type=query_type, sources=sources,
                ),
            )

        result.session_id = session.session_id
        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[chat] internal error: %s", repr(exc), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误，请稍后重试")


# ============================================================
# 流式问答路由
# ============================================================

@router.post("/chat-stream")
async def chat_stream(
    request: ChatRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """流式问答 — 统一走 ChatOrchestrator 流式管道"""

    async def generate():
        try:
            if not request.question or not request.question.strip():
                yield f"data: {json.dumps({'type': 'message', 'data': '问题不能为空'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            question = request.question.strip()

            # ── 预处理 ──
            kb = get_or_resolve_kb(db, request.knowledge_base_id, current_user)
            session = get_or_create_session(db, current_user.id, request.session_id, question, kb.id)
            save_user_message(db, session, current_user.id, question)

            allowed_doc_ids = get_kb_allowed_doc_ids(db, current_user.id, kb.id)
            retrieval_kb_id = None if allowed_doc_ids else kb.id

            if not allowed_doc_ids:
                yield f"data: {json.dumps({'type': 'message', 'data': '知识库未收录相关内容。'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            # ── 路由分流：非医疗直接返回 ──
            route_type = orchestrator._route(question)
            if route_type in {"high_risk", "chitchat", "out_of_scope"}:
                result = orchestrator._non_medical_response(route_type, question)
                answer = getattr(result, "answer", "") or "我是思医医疗知识库助手。"
                yield f"data: {json.dumps({'type': 'chunk', 'data': answer}, ensure_ascii=False)}\n\n"
                yield "data: {json.dumps({'type': 'sources', 'data': []}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            # ── 流式编排执行 ──
            final_answer = ""
            final_sources = []
            final_query_type = "other"
            final_question = question

            async for event in orchestrator.execute_stream(
                question=question,
                user_id=current_user.id,
                session_id=session.session_id,
                knowledge_base_id=retrieval_kb_id,
                allowed_doc_ids=allowed_doc_ids,
                document_id=request.document_id,
                db=db,
            ):
                event_type = event.get("type", "")
                event_data = event.get("data", "")

                if event_type == "chunk":
                    final_answer += event_data
                elif event_type == "done":
                    final_answer = event_data.get("answer", final_answer)
                    final_sources = event_data.get("sources", [])
                    final_query_type = event_data.get("query_type", "other")
                    final_question = event_data.get("question", question)
                else:
                    # message / followup — pass through as SSE
                    pass

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            yield "data: [DONE]\n\n"

            # ── 后处理：保存 ──
            if final_answer:
                save_assistant_message(db, session, current_user.id, final_answer, final_sources)
                memory_manager.add_turn(
                    session.session_id,
                    ConversationTurn(
                        user_question=final_question,
                        assistant_answer=final_answer,
                        query_type=final_query_type,
                        sources=final_sources,
                    ),
                )

        except Exception as e:
            logger.error("[chat_stream] error: %s", repr(e), exc_info=True)
            yield f"data: {json.dumps({'type': 'message', 'data': '生成回答时发生错误，请稍后重试'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
