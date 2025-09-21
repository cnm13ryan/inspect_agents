"""Runtime context helpers for the vending bench harness.

These helpers provide per-run access to the simulator environment and
memory store via context variables so that Inspect tool invocations can
share mutable state without relying on Inspect's StoreModel wiring.
"""

from __future__ import annotations

import os
from collections import Counter
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import-time guard only
    from .env import VendingEnv
    from .memory import MemoryStore


_ENV_CTX: ContextVar[VendingEnv | None] = ContextVar("vending_bench_env", default=None)
_MEMORY_CTX: ContextVar[MemoryStore | None] = ContextVar("vending_bench_memory", default=None)
_TOOL_COUNTER_CTX: ContextVar[Counter[str] | None] = ContextVar("vending_bench_tool_counts", default=None)


def set_runtime_context(*, env: VendingEnv, memory: MemoryStore) -> None:
    """Bind the active environment and memory store for the current run."""

    _ENV_CTX.set(env)
    _MEMORY_CTX.set(memory)
    _TOOL_COUNTER_CTX.set(Counter())


def clear_runtime_context() -> None:
    """Clear runtime bindings (best-effort)."""

    _ENV_CTX.set(None)
    _MEMORY_CTX.set(None)
    _TOOL_COUNTER_CTX.set(None)


def get_env() -> VendingEnv:
    """Return the active environment instance or raise if unset."""

    env = _ENV_CTX.get(None)
    if env is None:
        raise RuntimeError("Vending environment is not initialised for this run")
    return env


def increment_tool_count(name: str) -> None:
    """Record a tool invocation for observability metrics."""

    counter = _TOOL_COUNTER_CTX.get(None)
    if counter is None:
        counter = Counter()
        _TOOL_COUNTER_CTX.set(counter)
    counter[name] += 1


def get_tool_counts() -> dict[str, int]:
    """Return aggregated tool invocation counts for the active run."""

    counter = _TOOL_COUNTER_CTX.get(None)
    if counter is None:
        return {}
    return dict(counter)


def get_memory_store() -> MemoryStore:
    """Return the active memory store, creating one on demand."""

    memory = _MEMORY_CTX.get(None)
    if memory is None:
        from .memory import (
            _CHECKPOINT_DIR_ENV,
            _RESUME_ENV,
            _RUN_ID_ENV,
            MemoryStore,
        )  # Local import to avoid circular import

        run_id = os.environ.get(_RUN_ID_ENV)
        checkpoint_dir_value = os.environ.get(_CHECKPOINT_DIR_ENV)
        resume_flag = os.environ.get(_RESUME_ENV, "0").strip().lower() in {"1", "true", "yes"}

        if run_id and checkpoint_dir_value:
            checkpoint_dir = Path(checkpoint_dir_value)
            memory = None
            if resume_flag:
                memory = MemoryStore.load_checkpoint(directory=checkpoint_dir, run_id=run_id)
            if memory is None:
                memory = MemoryStore()
            memory.configure_checkpoint(directory=checkpoint_dir, run_id=run_id, auto_persist=True)
        else:
            memory = MemoryStore()
        _MEMORY_CTX.set(memory)
    return memory
