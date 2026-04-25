from pathlib import Path

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.core import config
from backend.database.session import SessionLocal

router = APIRouter()


@router.get("/health")
def health() -> dict:
    # 仅存活检查：不访问 DB/Chroma/LLM
    return {
        "status": "ok",
        "service": "rag-knowledgebase",
        "version": "dev",
    }


def _check_database() -> dict:
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return {"status": "ok"}
        finally:
            db.close()
    except Exception:
        # 不暴露连接串或详细敏感信息
        return {"status": "error", "message": "database connection failed"}


def _check_dir(path_str: str, check_name: str) -> dict:
    try:
        p = Path(path_str)
        p.mkdir(parents=True, exist_ok=True)

        if not p.exists() or not p.is_dir():
            return {"status": "error", "message": f"{check_name} is not a directory"}

        # 写权限检测
        probe = p / ".healthcheck_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)

        return {"status": "ok", "path": path_str}
    except Exception:
        return {"status": "error", "message": f"{check_name} not writable", "path": path_str}


@router.get("/health/ready")
def health_ready():
    checks = {
        "database": _check_database(),
        "upload_dir": _check_dir(config.UPLOAD_DIR, "upload_dir"),
        "chroma_dir": _check_dir(config.CHROMA_PERSIST_DIR, "chroma_dir"),
        "llm_config": {
            "openai_api_key_configured": bool(config.OPENAI_API_KEY),
            "openai_base_url_configured": bool(config.OPENAI_BASE_URL),
            "llm_model_configured": bool(config.LLM_MODEL),
            "embedding_model_configured": bool(config.EMBEDDING_MODEL),
        },
    }

    all_ok = (
        checks["database"]["status"] == "ok"
        and checks["upload_dir"]["status"] == "ok"
        and checks["chroma_dir"]["status"] == "ok"
    )

    payload = {
        "status": "ok" if all_ok else "error",
        "checks": checks,
    }

    if all_ok:
        return payload

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload,
    )