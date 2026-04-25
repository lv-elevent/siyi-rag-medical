"""
应用配置文件（统一配置入口）
"""
from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


def _parse_cors_origins(raw: str | None) -> list[str]:
    if not raw:
        return ["http://localhost:5173", "http://127.0.0.1:5173"]
    return [x.strip() for x in raw.split(",") if x.strip()]


# ===== Security / Auth =====
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24)))

# ===== OpenAI-compatible =====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")

# ===== Storage =====
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "rag_docs")
# 兼容旧变量 CHROMA_DIR
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", os.getenv("CHROMA_DIR", "./chroma_db"))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")

# ===== API / CORS =====
API_PORT = int(os.getenv("API_PORT", "8000"))
API_HOST = os.getenv("API_HOST", "0.0.0.0")
CORS_ORIGINS = _parse_cors_origins(os.getenv("CORS_ORIGINS", ""))

# ===== Optional =====
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB