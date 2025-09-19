"""Memory tools for the vending bench environment.

Provides scratchpad, key-value store, and vector database functionality
with summarization workflows to manage long-horizon memory as specified
in the design requirements.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from .runtime import get_env, get_memory_store, increment_tool_count

if TYPE_CHECKING:
    from inspect_ai.tool._tool import Tool


class BaseMemoryParams(BaseModel):
    """Base class for memory tool parameters."""

    model_config = {"extra": "forbid"}  # Reject unknown fields


class ScratchpadEntry(BaseModel):
    """Individual scratchpad entry."""

    id: str
    content: str
    timestamp: float
    day: int
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScratchpadResult(BaseModel):
    """Result from scratchpad operations."""

    entries: list[ScratchpadEntry]
    total_count: int
    operation: str


class KeyValueResult(BaseModel):
    """Result from key-value operations."""

    key: str | None = None
    value: Any = None
    found: bool = False
    keys: list[str] = Field(default_factory=list)
    operation: str = ""


class VectorEntry(BaseModel):
    """Vector store entry."""

    id: str
    content: str
    metadata: dict[str, Any]
    timestamp: float
    similarity: float = 0.0


class VectorResult(BaseModel):
    """Result from vector operations."""

    entries: list[VectorEntry]
    operation: str
    query: str = ""


class MemoryStore:
    """In-memory storage for all memory operations."""

    def __init__(self):
        self.scratchpad: list[ScratchpadEntry] = []
        self.key_value: dict[str, dict[str, Any]] = {}  # key -> {value, timestamp, ttl_days}
        self.vector_store: list[VectorEntry] = []
        self._next_id = 1

    def _generate_id(self) -> str:
        """Generate unique ID."""
        id_str = f"mem_{self._next_id:06d}"
        self._next_id += 1
        return id_str

    def _cleanup_expired_kv(self) -> None:
        """Remove expired key-value entries."""
        current_time = time.time()
        expired_keys = []

        for key, data in self.key_value.items():
            if "timestamp" in data and "ttl_days" in data:
                expiry_time = data["timestamp"] + (data["ttl_days"] * 24 * 3600)
                if current_time > expiry_time:
                    expired_keys.append(key)

        for key in expired_keys:
            del self.key_value[key]

    def _simple_similarity(self, text1: str, text2: str) -> float:
        """Simple similarity calculation based on word overlap."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0


def _log_memory_event(
    name: str,
    phase: str,
    args: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
    t0: float | None = None,
) -> float:
    """Log memory tool events for observability."""
    if t0 is None:
        t0 = time.time()

    logger = logging.getLogger(__name__)
    log_data = {
        "memory_tool": name,
        "phase": phase,
        "timestamp": time.time(),
    }

    if args:
        log_data["args"] = args
    if extra:
        log_data["extra"] = extra
    if phase == "end" and t0:
        log_data["duration_ms"] = (time.time() - t0) * 1000

    if phase == "start":
        increment_tool_count(f"memory:{name}")

    logger.info(f"Memory tool event: {json.dumps(log_data)}")
    return t0 if phase == "start" else time.time()


def scratchpad_append() -> Tool:
    """Append entry to scratchpad memory."""

    from inspect_ai.tool._tool import tool

    @tool(name="scratchpad_append")
    def scratchpad_append_impl(
        content: str, tags: list[str] = None, metadata: dict[str, Any] = None
    ) -> ScratchpadResult:
        """Append entry to scratchpad for daily notes and observations.

        Args:
            content: Text content to store in scratchpad
            tags: Optional list of tags for categorization
            metadata: Optional metadata dictionary
        """

        tags = tags or []
        metadata = metadata or {}

        t0 = _log_memory_event(
            name="scratchpad_append", phase="start", args={"content_length": len(content), "tags": tags}
        )

        try:
            memory_store = get_memory_store()

            # Get current environment day for context
            try:
                current_day = get_env().state.day
            except Exception:
                current_day = 0

            entry = ScratchpadEntry(
                id=memory_store._generate_id(),
                content=content,
                timestamp=time.time(),
                day=current_day,
                tags=tags,
                metadata=metadata,
            )

            memory_store.scratchpad.append(entry)

            result = ScratchpadResult(entries=[entry], total_count=len(memory_store.scratchpad), operation="append")

            _log_memory_event(
                name="scratchpad_append",
                phase="end",
                extra={"entry_id": entry.id, "total_entries": result.total_count},
                t0=t0,
            )

            return result

        except Exception as e:
            _log_memory_event(name="scratchpad_append", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return scratchpad_append_impl


def scratchpad_read() -> Tool:
    """Read entries from scratchpad memory."""

    from inspect_ai.tool._tool import tool

    @tool(name="scratchpad_read")
    def scratchpad_read_impl(limit: int = 50, tags: list[str] = None, days_back: int = 7) -> ScratchpadResult:
        """Read entries from scratchpad with filtering by tags and time.

        Args:
            limit: Maximum number of entries to return
            tags: Optional list of tags to filter by
            days_back: Number of days back to look for entries
        """

        tags = tags or []

        t0 = _log_memory_event(
            name="scratchpad_read", phase="start", args={"limit": limit, "tags": tags, "days_back": days_back}
        )

        try:
            memory_store = get_memory_store()

            # Get current day for filtering
            try:
                current_day = get_env().state.day
            except Exception:
                current_day = 999999  # If no env, return all

            # Filter entries
            filtered_entries = []
            for entry in memory_store.scratchpad:
                # Day filter
                if current_day - entry.day > days_back:
                    continue

                # Tag filter
                if tags and not any(tag in entry.tags for tag in tags):
                    continue

                filtered_entries.append(entry)

            # Sort by timestamp (newest first) and limit
            filtered_entries.sort(key=lambda x: x.timestamp, reverse=True)
            limited_entries = filtered_entries[:limit]

            result = ScratchpadResult(entries=limited_entries, total_count=len(filtered_entries), operation="read")

            _log_memory_event(
                name="scratchpad_read",
                phase="end",
                extra={"returned_entries": len(limited_entries), "total_matches": len(filtered_entries)},
                t0=t0,
            )

            return result

        except Exception as e:
            _log_memory_event(name="scratchpad_read", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return scratchpad_read_impl


def kv_set() -> Tool:
    """Set key-value data in memory store."""

    from inspect_ai.tool._tool import tool

    @tool(name="kv_set")
    def kv_set_impl(key: str, value: Any, ttl_days: int = 30) -> KeyValueResult:
        """Store key-value data with expiration for supplier info and notes.

        Args:
            key: Storage key (max 100 chars)
            value: Value to store
            ttl_days: Time to live in days before expiration
        """

        if not key.strip():
            raise ValueError("Key cannot be empty")
        if len(key) > 100:
            raise ValueError("Key too long (max 100 chars)")
        key = key.strip()

        t0 = _log_memory_event(name="kv_set", phase="start", args={"key": key, "ttl_days": ttl_days})

        try:
            memory_store = get_memory_store()
            memory_store._cleanup_expired_kv()

            memory_store.key_value[key] = {"value": value, "timestamp": time.time(), "ttl_days": ttl_days}

            result = KeyValueResult(key=key, value=value, found=True, operation="set")

            _log_memory_event(
                name="kv_set", phase="end", extra={"key": key, "total_keys": len(memory_store.key_value)}, t0=t0
            )

            return result

        except Exception as e:
            _log_memory_event(name="kv_set", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return kv_set_impl


def kv_get() -> Tool:
    """Get key-value data from memory store."""

    from inspect_ai.tool._tool import tool

    @tool(name="kv_get")
    def kv_get_impl(key: str) -> KeyValueResult:
        """Retrieve value by key from memory store.

        Args:
            key: Storage key to retrieve
        """

        t0 = _log_memory_event(name="kv_get", phase="start", args={"key": key})

        try:
            memory_store = get_memory_store()
            memory_store._cleanup_expired_kv()

            data = memory_store.key_value.get(key)
            if data:
                result = KeyValueResult(key=key, value=data["value"], found=True, operation="get")
            else:
                result = KeyValueResult(key=key, found=False, operation="get")

            _log_memory_event(name="kv_get", phase="end", extra={"key": key, "found": result.found}, t0=t0)

            return result

        except Exception as e:
            _log_memory_event(name="kv_get", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return kv_get_impl


def kv_list() -> Tool:
    """List keys in memory store."""

    from inspect_ai.tool._tool import tool

    @tool(name="kv_list")
    def kv_list_impl(prefix: str = "", limit: int = 100) -> KeyValueResult:
        """List all keys in memory store with optional prefix filter.

        Args:
            prefix: Optional prefix to filter keys by
            limit: Maximum number of keys to return
        """

        t0 = _log_memory_event(name="kv_list", phase="start", args={"prefix": prefix, "limit": limit})

        try:
            memory_store = get_memory_store()
            memory_store._cleanup_expired_kv()

            keys = list(memory_store.key_value.keys())
            if prefix:
                keys = [k for k in keys if k.startswith(prefix)]

            keys.sort()
            limited_keys = keys[:limit]

            result = KeyValueResult(keys=limited_keys, operation="list")

            _log_memory_event(
                name="kv_list",
                phase="end",
                extra={"returned_keys": len(limited_keys), "total_matches": len(keys)},
                t0=t0,
            )

            return result

        except Exception as e:
            _log_memory_event(name="kv_list", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return kv_list_impl


def vector_store() -> Tool:
    """Store content in vector database for semantic search."""

    from inspect_ai.tool._tool import tool

    @tool(name="vector_store")
    def vector_store_impl(content: str, metadata: dict[str, Any] = None) -> VectorResult:
        """Store content in vector database for later semantic search.

        Args:
            content: Text content to store
            metadata: Optional metadata dictionary
        """

        metadata = metadata or {}

        t0 = _log_memory_event(name="vector_store", phase="start", args={"content_length": len(content)})

        try:
            memory_store = get_memory_store()

            entry = VectorEntry(
                id=memory_store._generate_id(), content=content, metadata=metadata, timestamp=time.time()
            )

            memory_store.vector_store.append(entry)

            result = VectorResult(entries=[entry], operation="store")

            _log_memory_event(
                name="vector_store",
                phase="end",
                extra={"entry_id": entry.id, "total_entries": len(memory_store.vector_store)},
                t0=t0,
            )

            return result

        except Exception as e:
            _log_memory_event(name="vector_store", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return vector_store_impl


def vector_search() -> Tool:
    """Search vector database for similar content."""

    from inspect_ai.tool._tool import tool

    @tool(name="vector_search")
    def vector_search_impl(query: str, limit: int = 10, similarity_threshold: float = 0.7) -> VectorResult:
        """Search vector database for semantically similar content.

        Args:
            query: Search query text
            limit: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0.0-1.0)
        """

        if similarity_threshold < 0.0 or similarity_threshold > 1.0:
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")

        t0 = _log_memory_event(
            name="vector_search",
            phase="start",
            args={"query": query, "limit": limit, "similarity_threshold": similarity_threshold},
        )

        try:
            memory_store = get_memory_store()

            # Calculate similarities and filter
            scored_entries = []
            for entry in memory_store.vector_store:
                similarity = memory_store._simple_similarity(query, entry.content)
                if similarity >= similarity_threshold:
                    entry_copy = VectorEntry(**entry.dict())
                    entry_copy.similarity = similarity
                    scored_entries.append(entry_copy)

            # Sort by similarity (highest first) and limit
            scored_entries.sort(key=lambda x: x.similarity, reverse=True)
            limited_entries = scored_entries[:limit]

            result = VectorResult(entries=limited_entries, operation="search", query=query)

            _log_memory_event(
                name="vector_search",
                phase="end",
                extra={"query": query, "returned_entries": len(limited_entries), "total_matches": len(scored_entries)},
                t0=t0,
            )

            return result

        except Exception as e:
            _log_memory_event(name="vector_search", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return vector_search_impl


def memory_tools() -> list[Tool]:
    """Return all memory management tools."""
    return [
        scratchpad_append(),
        scratchpad_read(),
        kv_set(),
        kv_get(),
        kv_list(),
        vector_store(),
        vector_search(),
    ]


def supervisor_memory_tools() -> list[Tool]:
    """Return memory tools suitable for supervisor agent."""
    return [
        scratchpad_append(),
        scratchpad_read(),
        kv_set(),
        kv_get(),
        kv_list(),
        vector_store(),
        vector_search(),
    ]
