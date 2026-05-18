"""In-memory cache for parsed Xiaohongshu notes (reuse across PDF/Markdown)."""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30 * 60


@dataclass
class NoteCacheEntry:
    extracted_url: str
    task_id: str
    clean_title: str
    title: str
    content: str
    image_urls: List[str]
    image_paths: List[str]
    pdf_filename: Optional[str] = None
    zip_filename: Optional[str] = None
    created_at: float = field(default_factory=time.time)


_cache: dict[str, NoteCacheEntry] = {}


def make_cache_key(extracted_url: str) -> str:
    normalized = extracted_url.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def get_entry(session_id: str | None, extracted_url: str) -> tuple[NoteCacheEntry | None, str]:
    """Resolve cache entry by session id or URL key."""
    cache_key = make_cache_key(extracted_url)
    if session_id:
        entry = _cache.get(session_id)
        if entry and _is_valid(entry):
            return entry, session_id
    entry = _cache.get(cache_key)
    if entry and _is_valid(entry):
        return entry, cache_key
    return None, cache_key


def save_entry(cache_key: str, entry: NoteCacheEntry) -> None:
    entry.created_at = time.time()
    _cache[cache_key] = entry


def _is_valid(entry: NoteCacheEntry) -> bool:
    return time.time() - entry.created_at <= CACHE_TTL_SECONDS


def entry_has_images(entry: NoteCacheEntry) -> bool:
    if not entry.image_paths:
        return False
    return all(os.path.isfile(path) for path in entry.image_paths)


def evict_expired(cleanup_task_files: Callable[[str], None]) -> None:
    now = time.time()
    for key, entry in list(_cache.items()):
        if now - entry.created_at > CACHE_TTL_SECONDS:
            logger.info("Evicting expired note cache: %s", key)
            cleanup_task_files(entry.task_id)
            del _cache[key]
