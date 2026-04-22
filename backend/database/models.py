from datetime import datetime

from sqlalchemy import (
	Column,
	BigInteger,
	String,
	Text,
	Integer,
	Boolean,
	DateTime,
	ForeignKey,
	JSON,
	UniqueConstraint,
)
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import relationship

from backend.database.session import Base
from sqlalchemy.types import Text as SA_Text


class User(Base):
	__tablename__ = "users"

	id = Column(BigInteger, primary_key=True, autoincrement=True)
	username = Column(String(64), unique=True, nullable=False, index=True)
	phone = Column(String(20), unique=True, nullable=True, index=True)
	password_hash = Column(String(255), nullable=False)
	role = Column(String(32), nullable=False, default="user")
	is_active = Column(Boolean, nullable=False, default=True)
	created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
	updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

	knowledge_bases = relationship("KnowledgeBase", back_populates="owner")
	documents = relationship("Document", back_populates="owner")
	chat_sessions = relationship("ChatSession", back_populates="user")


class KnowledgeBase(Base):
	__tablename__ = "knowledge_bases"
	__table_args__ = (
		UniqueConstraint("user_id", "name", name="uq_user_kb_name"),
	)

	id = Column(BigInteger, primary_key=True, autoincrement=True)
	user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
	name = Column(String(128), nullable=False)
	description = Column(Text, nullable=True)
	status = Column(String(32), nullable=False, default="active")
	created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
	updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

	owner = relationship("User", back_populates="knowledge_bases")
	documents = relationship("Document", back_populates="knowledge_base", passive_deletes=True)
	document_links = relationship("KnowledgeBaseDocument", back_populates="knowledge_base")


class Document(Base):
	__tablename__ = "documents"

	id = Column(BigInteger, primary_key=True, autoincrement=True)
	knowledge_base_id = Column(BigInteger, ForeignKey("knowledge_bases.id"), nullable=True, index=True)
	user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
	filename = Column(String(255), nullable=False)
	file_path = Column(String(512), nullable=False)
	file_type = Column(String(32), nullable=False, default="pdf")
	file_size = Column(BigInteger, nullable=True)
	file_hash = Column(String(128), nullable=True, index=True)
	status = Column(String(32), nullable=False, default="uploaded")
	chunk_count = Column(Integer, nullable=False, default=0)
	error_message = Column(Text, nullable=True)
	created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
	updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

	owner = relationship("User", back_populates="documents")
	knowledge_base = relationship("KnowledgeBase", back_populates="documents")
	chunks = relationship("DocumentChunk", back_populates="document")
	knowledge_base_links = relationship("KnowledgeBaseDocument", back_populates="document")


class KnowledgeBaseDocument(Base):
	__tablename__ = "knowledge_base_documents"
	__table_args__ = (
		UniqueConstraint("knowledge_base_id", "document_id", name="uq_kb_document"),
	)

	id = Column(BigInteger, primary_key=True, autoincrement=True)
	knowledge_base_id = Column(BigInteger, ForeignKey("knowledge_bases.id"), nullable=True, index=True)
	document_id = Column(BigInteger, ForeignKey("documents.id"), nullable=False, index=True)
	user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
	created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

	knowledge_base = relationship("KnowledgeBase", back_populates="document_links")
	document = relationship("Document", back_populates="knowledge_base_links")


class DocumentChunk(Base):
	__tablename__ = "document_chunks"
	__table_args__ = (
		UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
	)

	id = Column(BigInteger, primary_key=True, autoincrement=True)
	document_id = Column(BigInteger, ForeignKey("documents.id"), nullable=False, index=True)
	knowledge_base_id = Column(BigInteger, ForeignKey("knowledge_bases.id"), nullable=True, index=True)
	user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
	chunk_index = Column(Integer, nullable=False)
	content = Column(SA_Text().with_variant(MEDIUMTEXT, "mysql"), nullable=False)
	token_count = Column(Integer, nullable=True)
	char_count = Column(Integer, nullable=True)
	chroma_id = Column(String(128), unique=True, nullable=False, index=True)
	page_number = Column(Integer, nullable=True)
	section_title = Column(String(255), nullable=True)
	created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

	document = relationship("Document", back_populates="chunks")


class ChatSession(Base):
	__tablename__ = "chat_sessions"

	id = Column(BigInteger, primary_key=True, autoincrement=True)
	user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
	knowledge_base_id = Column(BigInteger, ForeignKey("knowledge_bases.id"), nullable=True, index=True)
	session_id = Column(String(64), unique=True, nullable=False, index=True)
	title = Column(String(255), nullable=True)
	status = Column(String(32), nullable=False, default="active")
	created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
	updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

	user = relationship("User", back_populates="chat_sessions")
	messages = relationship(
		"ChatMessage",
		back_populates="chat_session",
		cascade="all, delete-orphan"
	)


class ChatMessage(Base):
	__tablename__ = "chat_messages"

	id = Column(BigInteger, primary_key=True, autoincrement=True)
	chat_session_id = Column(BigInteger, ForeignKey("chat_sessions.id"), nullable=False, index=True)
	session_id = Column(String(64), nullable=False, index=True)
	user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
	role = Column(String(32), nullable=False)
	content = Column(SA_Text().with_variant(MEDIUMTEXT, "mysql"), nullable=False)
	metadata_json = Column(JSON, nullable=True)
	created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

	chat_session = relationship("ChatSession", back_populates="messages")


class RetrievalLog(Base):
	__tablename__ = "retrieval_logs"

	id = Column(BigInteger, primary_key=True, autoincrement=True)
	user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
	chat_session_id = Column(BigInteger, ForeignKey("chat_sessions.id"), nullable=False, index=True)
	message_id = Column(BigInteger, ForeignKey("chat_messages.id"), nullable=True, index=True)
	query = Column(Text, nullable=False)
	rewritten_query = Column(Text, nullable=True)
	query_type = Column(String(64), nullable=True)
	top_k = Column(Integer, nullable=True)
	retrieved_chunks_json = Column(JSON, nullable=True)
	reranked_chunks_json = Column(JSON, nullable=True)
	final_context = Column(SA_Text().with_variant(MEDIUMTEXT, "mysql"), nullable=True)
	answer_message_id = Column(BigInteger, ForeignKey("chat_messages.id"), nullable=True, index=True)
	created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

