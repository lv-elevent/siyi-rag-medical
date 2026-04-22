import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.upload import router as upload_router
from backend.api.knowledge_status import router as knowledge_status_router
from backend.api.chat import router as chat_router
from backend.api.delete import router as delete_router
from backend.api.knowledge import router as knowledge_router
from backend.api.auth import router as auth_router
from backend.core.logger_config import setup_logger
from backend.database.session import init_db

logger = setup_logger(__name__, logging.INFO)
logger.info("RAG Knowledge Base API 启动")

app = FastAPI(title="RAG Knowledge Base API")

# ⭐ 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.1.5:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(knowledge_status_router)
app.include_router(chat_router)
app.include_router(delete_router)
app.include_router(knowledge_router)
app.include_router(auth_router)


@app.on_event("startup")
def _startup_init_db():
    init_db()


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Backend is running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}