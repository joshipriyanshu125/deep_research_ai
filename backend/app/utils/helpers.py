import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict


def generate_uuid() -> str:
    return str(uuid.uuid4())


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_string(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def truncate_text(text: str, max_chars: int = 500) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def clean_dict_keys(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}
