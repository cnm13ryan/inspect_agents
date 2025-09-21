"""Unit tests for the embedding-backed vector memory store."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from examples.vending_bench import memory as memory_module
from examples.vending_bench.memory import (
    DeterministicEmbeddingProvider,
    EmbeddingCache,
    MemoryStore,
    vector_search,
    vector_store,
)


def _build_memory(monkeypatch: pytest.MonkeyPatch, dimensions: int = 64) -> MemoryStore:
    monkeypatch.setenv("VENDING_BENCH_EMBED_CACHE", "off")
    store = MemoryStore(embedding_provider=DeterministicEmbeddingProvider(dimensions=dimensions))
    monkeypatch.setattr("examples.vending_bench.memory.get_memory_store", lambda: store)
    return store


class TestVectorStoreEmbeddings:
    """Validate that embeddings are generated and persisted when storing entries."""

    def test_vector_store_generates_normalised_embedding(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _ = _build_memory(monkeypatch)
        tool = vector_store()

        result = tool("Restock energy drinks and water", metadata={"type": "email"})

        assert result.entries, "vector_store should return the stored entry"
        entry = result.entries[0]
        assert entry.embedding, "embedding must be generated for stored entries"

        norm = math.sqrt(sum(value * value for value in entry.embedding))
        assert norm == pytest.approx(1.0, rel=1e-6, abs=1e-6)


class TestVectorSearch:
    """Validate cosine similarity ranking and thresholding."""

    def test_vector_search_orders_by_similarity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _ = _build_memory(monkeypatch)
        store_tool = vector_store()
        search_tool = vector_search()

        store_tool("Plan restock for beverages", metadata={"id": "inventory"})
        store_tool("Finalize quarterly financial statements", metadata={"id": "finance"})

        result = search_tool("restock beverages plan", limit=2, similarity_threshold=0.0)

        assert len(result.entries) == 2
        top_ids = [entry.metadata.get("id") for entry in result.entries]
        assert top_ids[0] == "inventory"
        assert result.entries[0].similarity >= result.entries[1].similarity

    def test_vector_search_applies_similarity_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _build_memory(monkeypatch)
        store_tool = vector_store()
        search_tool = vector_search()

        store_tool("Prepare snack restock order", metadata={"topic": "inventory"})

        result = search_tool("Completely unrelated topic", limit=5, similarity_threshold=0.95)

        assert not result.entries


class TestEmbeddingProviderResolution:
    """Ensure deterministic fallback is available when OpenAI config is missing."""

    def test_build_embedding_provider_falls_back_without_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("VENDING_BENCH_EMBEDDINGS", raising=False)
        monkeypatch.delenv("VENDING_BENCH_EMBEDDING_DIM", raising=False)
        monkeypatch.delenv("VENDING_BENCH_EMBEDDING_MODEL", raising=False)
        memory_module._FALLBACK_WARNING_EMITTED = False

        provider = memory_module._build_embedding_provider()

        assert isinstance(provider, DeterministicEmbeddingProvider)


class TestEmbeddingCache:
    """Verify global embedding cache behaviour."""

    class _CountingProvider:
        def __init__(self) -> None:
            self.calls = 0

        def embed(self, text: str) -> list[float]:
            self.calls += 1
            return [1.0, 0.0, 0.0]

        @property
        def cache_id(self) -> str:
            return "counting:3"

    def test_cache_reuses_vectors(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VENDING_BENCH_EMBED_CACHE", "off")
        provider = self._CountingProvider()
        cache = EmbeddingCache(path=tmp_path / "cache.sqlite", mode="rw")
        store = MemoryStore(embedding_provider=provider, embedding_cache=cache)

        first = store.embed_text("Cache me once")
        second = store.embed_text("Cache me once")

        assert provider.calls == 1
        assert first == pytest.approx(second)


class TestMemoryCheckpointing:
    """Ensure run checkpoints persist and isolate memory state."""

    def test_checkpoint_round_trip(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VENDING_BENCH_EMBED_CACHE", "off")
        run_id = "checkpoint-run"
        directory = tmp_path / "checkpoints"

        store = MemoryStore(embedding_provider=DeterministicEmbeddingProvider(dimensions=8))
        store.configure_checkpoint(directory=directory, run_id=run_id, auto_persist=False)

        store.scratchpad.append(
            memory_module.ScratchpadEntry(
                id="mem_000001",
                content="Initial note",
                timestamp=1.0,
                day=0,
                tags=["note"],
                metadata={},
            )
        )
        entry = memory_module.VectorEntry(
            id="mem_000002",
            content="Vector entry",
            metadata={},
            timestamp=1.0,
            embedding=store.embed_text("Vector entry"),
        )
        store.vector_store.append(entry)
        store.persist_checkpoint()

        restored = MemoryStore.load_checkpoint(directory=directory, run_id=run_id)
        assert restored is not None
        assert len(restored.vector_store) == 1
        assert restored.vector_store[0].embedding
        assert restored.scratchpad[0].content == "Initial note"

    def test_new_run_starts_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VENDING_BENCH_EMBED_CACHE", "off")
        directory = tmp_path / "checkpoints"

        run_a = MemoryStore(embedding_provider=DeterministicEmbeddingProvider(dimensions=8))
        run_a.configure_checkpoint(directory=directory, run_id="run-a", auto_persist=False)
        run_a.vector_store.append(
            memory_module.VectorEntry(
                id="mem_000010",
                content="Persist me",
                metadata={},
                timestamp=1.0,
                embedding=run_a.embed_text("Persist me"),
            )
        )
        run_a.persist_checkpoint()

        run_b = MemoryStore.load_checkpoint(directory=directory, run_id="run-b")
        assert run_b is None

        fresh = MemoryStore(embedding_provider=DeterministicEmbeddingProvider(dimensions=8))
        fresh.configure_checkpoint(directory=directory, run_id="run-b", auto_persist=True)
        assert fresh.vector_store == []
