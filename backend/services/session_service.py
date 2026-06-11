"""
会话管理服务

职责：会话创建、消息持久化、会话查询/删除
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status

from backend.database.models import ChatSession, ChatMessage, RetrievalLog


# ============================================================
# 标题生成
# ============================================================

def generate_session_title(question: str | None) -> str:
    """用首条问题前 20 字生成会话标题"""
    q = (question or "").strip().replace("\n", " ")
    if not q:
        return "新对话"
    return q[:20] + ("..." if len(q) > 20 else "")


# ============================================================
# 会话查询（统一权限校验）
# ============================================================

def get_user_session_or_404(db, session_id: str, user_id: int) -> ChatSession:
    """按 session_id 查询会话，不存在或不属于当前用户则 404"""
    session = db.query(ChatSession).filter_by(session_id=session_id).first()
    if not session or session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在",
        )
    return session


# ============================================================
# 会话创建/获取
# ============================================================

def get_or_create_session(
    db,
    user_id: int,
    session_id: str | None,
    first_question: str | None = None,
    knowledge_base_id: int | None = None,
) -> ChatSession:
    """按 session_id 获取已有会话，不存在则创建新的"""
    if session_id:
        session = db.query(ChatSession).filter_by(session_id=session_id).first()
        if session:
            if session.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="会话不存在",
                )
            # 更新知识库关联
            if (
                knowledge_base_id is not None
                and session.knowledge_base_id != knowledge_base_id
            ):
                session.knowledge_base_id = knowledge_base_id
                session.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(session)
            elif session.knowledge_base_id is None and knowledge_base_id is not None:
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
        updated_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


# ============================================================
# 消息保存
# ============================================================

def save_user_message(db, session: ChatSession, user_id: int, question: str) -> None:
    """保存用户消息，自动更新会话标题"""
    msg = ChatMessage(
        chat_session_id=session.id,
        session_id=session.session_id,
        user_id=user_id,
        role="user",
        content=question,
        metadata_json=None,
        created_at=datetime.utcnow(),
    )
    db.add(msg)

    # 自动标题：如果还是默认标题，则用首条问题生成
    if not session.title or session.title == "新对话":
        session.title = generate_session_title(question)

    session.updated_at = datetime.utcnow()
    db.commit()


def save_assistant_message(
    db,
    session: ChatSession,
    user_id: int,
    answer: str,
    sources: list | None = None,
) -> None:
    """保存 AI 回答消息及其来源"""
    msg = ChatMessage(
        chat_session_id=session.id,
        session_id=session.session_id,
        user_id=user_id,
        role="assistant",
        content=answer,
        metadata_json={"sources": sources or []},
        created_at=datetime.utcnow(),
    )
    db.add(msg)
    session.updated_at = datetime.utcnow()
    db.commit()


# ============================================================
# 会话删除（级联清理）
# ============================================================

def delete_session_cascade(db, session: ChatSession, user_id: int) -> None:
    """级联删除会话的检索日志、消息和会话本身"""
    try:
        db.query(RetrievalLog).filter(
            RetrievalLog.chat_session_id == session.id,
            RetrievalLog.user_id == user_id,
        ).delete(synchronize_session=False)

        db.query(ChatMessage).filter(
            ChatMessage.chat_session_id == session.id,
            ChatMessage.session_id == session.session_id,
            ChatMessage.user_id == user_id,
        ).delete(synchronize_session=False)

        db.delete(session)
        db.commit()
    except Exception:
        db.rollback()
        raise
