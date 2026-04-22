import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List

REGISTRY_FILE = Path(__file__).parent.parent / "data" / "knowledge_registry.json"


def calculate_file_hash(file_path: str, chunk_size: int = 8192) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def calculate_file_hash_from_bytes(contents: bytes) -> str:
    sha256_hash = hashlib.sha256()
    sha256_hash.update(contents)
    return sha256_hash.hexdigest()


def load_registry() -> Dict[str, Any]:
    if not REGISTRY_FILE.exists():
        return {}

    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_registry(registry: Dict[str, Any]) -> None:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


# =========================
# 🔥 核心：按 user_id 隔离
# =========================

def registry_get(file_hash: str, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    registry = load_registry()

    for key, metadata in registry.items():
        if metadata.get("file_hash") != file_hash:
            continue

        if user_id is not None and metadata.get("user_id") != user_id:
            continue

        return metadata

    return None


def registry_add(file_hash: str, metadata: Dict[str, Any]) -> None:
    """
    metadata 必须包含 user_id
    """
    registry = load_registry()

    user_id = metadata.get("user_id")
    if user_id is None:
        raise ValueError("registry_add 必须包含 user_id")

    # key 改成 user_id + file_hash，避免跨用户冲突
    key = f"{user_id}_{file_hash}"

    registry[key] = {
        "file_hash": file_hash,
        **metadata
    }

    save_registry(registry)


def registry_list(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    registry = load_registry()
    files = []

    for key, metadata in registry.items():
        if user_id is not None and metadata.get("user_id") != user_id:
            continue

        files.append(metadata)

    files.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return files


def registry_delete(document_id: str, user_id: Optional[int] = None) -> bool:
    registry = load_registry()

    target_key = None

    for key, metadata in registry.items():
        if metadata.get("document_id") != document_id:
            continue

        if user_id is not None and metadata.get("user_id") != user_id:
            continue

        target_key = key
        break

    if not target_key:
        return False

    del registry[target_key]
    save_registry(registry)
    return True


def registry_exists(document_id: str, user_id: Optional[int] = None) -> bool:
    registry = load_registry()

    for metadata in registry.values():
        if metadata.get("document_id") != document_id:
            continue

        if user_id is not None and metadata.get("user_id") != user_id:
            continue

        return True

    return False