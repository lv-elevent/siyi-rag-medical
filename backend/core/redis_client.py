"""
Redis 客户端封装

- Redis 可用时：正常读写，带 TTL
- Redis 不可用时：自动降级到本地内存 dict
- 所有调用方无需感知降级逻辑
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_REDIS_URL = os.getenv("REDIS_URL", "")
_REDIS_AVAILABLE = False
_redis_client = None


def _init_redis():
    global _REDIS_AVAILABLE, _redis_client
    if not _REDIS_URL:
        logger.info("[redis] REDIS_URL 未配置，使用本地内存降级")
        return
    try:
        import redis
        _redis_client = redis.from_url(_REDIS_URL, socket_connect_timeout=3, socket_timeout=3)
        _redis_client.ping()
        _REDIS_AVAILABLE = True
        logger.info("[redis] 连接成功 url=%s", _REDIS_URL.split("@")[-1] if "@" in _REDIS_URL else _REDIS_URL)
    except Exception as exc:
        logger.warning("[redis] 连接失败，降级到本地内存: %s", exc)


# 模块加载时初始化
_init_redis()


class RedisCache:
    """Redis 缓存 + 本地内存降级"""

    def __init__(self, prefix: str = ""):
        self._prefix = prefix
        self._fallback: dict[str, str] = {}

    # ── 基础操作 ──

    def get(self, key: str) -> Optional[str]:
        full_key = f"{self._prefix}{key}"
        if _REDIS_AVAILABLE:
            try:
                val = _redis_client.get(full_key)
                return val.decode("utf-8") if isinstance(val, bytes) else val
            except Exception as exc:
                logger.debug("[redis] get 异常，降级: %s", exc)
        return self._fallback.get(full_key)

    def set(self, key: str, value: str, ttl: int = 3600) -> None:
        full_key = f"{self._prefix}{key}"
        if _REDIS_AVAILABLE:
            try:
                _redis_client.set(full_key, value, ex=ttl)
                return
            except Exception as exc:
                logger.debug("[redis] set 异常，降级: %s", exc)
        self._fallback[full_key] = value

    def delete(self, key: str) -> None:
        full_key = f"{self._prefix}{key}"
        if _REDIS_AVAILABLE:
            try:
                _redis_client.delete(full_key)
                return
            except Exception:
                pass
        self._fallback.pop(full_key, None)

    def exists(self, key: str) -> bool:
        full_key = f"{self._prefix}{key}"
        if _REDIS_AVAILABLE:
            try:
                return bool(_redis_client.exists(full_key))
            except Exception:
                pass
        return full_key in self._fallback

    # ── JSON 便捷方法 ──

    def get_json(self, key: str) -> Any:
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_json(self, key: str, value: Any, ttl: int = 3600) -> None:
        self.set(key, json.dumps(value, ensure_ascii=False, default=str), ttl=ttl)


# ── 全局单例（不同前缀的实例）─

embedding_cache = RedisCache(prefix="emb:")
session_cache = RedisCache(prefix="session:")
memory_cache = RedisCache(prefix="mem:")
retrieval_cache = RedisCache(prefix="ret:")
