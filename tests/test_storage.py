"""Unit and integration tests for VectorStore, hybrid search, and tool models."""

import hashlib
from typing import List, Sequence
import pytest

from schemaslim.storage.models import (
    IndexedTool,
    SearchResult,
    build_embedding_text,
    compute_schema_hash,
)
from schemaslim.storage.vector_store import VECTOR_DIMENSION, VectorStore


class DeterministicMockEmbedder:
    """Mock embedder providing deterministic 384-dimensional unit vectors for testing."""

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        results = []
        for text in texts:
            # Generate deterministic floats based on sha256 hash of text
            h = hashlib.sha256(text.encode("utf-8")).digest()
            vec = [(b / 255.0) - 0.5 for b in h]
            # Pad or truncate to VECTOR_DIMENSION
            extended = (vec * (VECTOR_DIMENSION // len(vec) + 1))[:VECTOR_DIMENSION]
            # Normalize vector to unit length
            norm = sum(x * x for x in extended) ** 0.5 or 1.0
            results.append([x / norm for x in extended])
        return results


@pytest.fixture
def mock_embedder() -> DeterministicMockEmbedder:
    return DeterministicMockEmbedder()


@pytest.fixture
def memory_vector_store(mock_embedder: DeterministicMockEmbedder) -> VectorStore:
    store = VectorStore(db_path=":memory:", embedder=mock_embedder)
    yield store
    store.close()


@pytest.fixture
def sample_tools() -> List[IndexedTool]:
    tool1 = IndexedTool.create(
        server_name="fs",
        tool_name="read_file",
        description="Read file contents from local filesystem",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute file path"}
            },
            "required": ["path"],
        },
    )
    tool2 = IndexedTool.create(
        server_name="fs",
        tool_name="write_file",
        description="Write or overwrite contents of a file on local filesystem",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Target path"},
                "content": {"type": "string", "description": "File text content"},
            },
            "required": ["path", "content"],
        },
    )
    tool3 = IndexedTool.create(
        server_name="git",
        tool_name="git_status",
        description="Check git status and modified files in repository working directory",
        parameters={"type": "object", "properties": {}},
    )
    return [tool1, tool2, tool3]


class TestToolModels:
    """Tests for IndexedTool factory, hashing, and formatting."""

    def test_namespaced_name(self):
        tool = IndexedTool.create("github", "create_issue")
        assert tool.namespaced_name == "github__create_issue"
        assert tool.server_name == "github"
        assert tool.tool_name == "create_issue"

    def test_hash_determinism(self):
        h1 = compute_schema_hash("description", {"a": 1, "b": 2})
        h2 = compute_schema_hash("description", {"b": 2, "a": 1})
        h3 = compute_schema_hash("description 2", {"a": 1, "b": 2})
        assert h1 == h2, "Hash must be independent of key insertion order"
        assert h1 != h3, "Different description must produce different hash"

    def test_embedding_text_generation(self):
        text = build_embedding_text(
            "fs__read_file",
            "Read file contents",
            {"properties": {"path": {"type": "string", "description": "file path"}}},
        )
        assert "tool: fs__read_file" in text
        assert "description: Read file contents" in text
        assert "parameters: path (type=string, desc=file path)" in text


class TestVectorStore:
    """Tests for VectorStore operations: upsert, idempotency, search, and deletion."""

    def test_upsert_and_count(
        self, memory_vector_store: VectorStore, sample_tools: List[IndexedTool]
    ):
        assert memory_vector_store.get_total_tools_count() == 0
        upserted = memory_vector_store.upsert_tools(sample_tools)
        assert upserted == 3
        assert memory_vector_store.get_total_tools_count() == 3

    def test_idempotent_upsert_skips_identical_hash(
        self, memory_vector_store: VectorStore, sample_tools: List[IndexedTool]
    ):
        memory_vector_store.upsert_tools(sample_tools)

        # Re-running with same tools must skip embedding
        second_upsert = memory_vector_store.upsert_tools(sample_tools)
        assert second_upsert == 0
        assert memory_vector_store.get_total_tools_count() == 3

    def test_update_modified_tool(
        self, memory_vector_store: VectorStore, sample_tools: List[IndexedTool]
    ):
        memory_vector_store.upsert_tools(sample_tools)

        # Modify description of one tool
        modified_tool = IndexedTool.create(
            server_name="fs",
            tool_name="read_file",
            description="Updated file reader description with new capabilities",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        )

        upserted = memory_vector_store.upsert_tools([modified_tool])
        assert upserted == 1
        assert memory_vector_store.get_total_tools_count() == 3

        # Verify updated description in DB
        all_tools = {t.namespaced_name: t for t in memory_vector_store.get_all_tools()}
        assert "Updated file reader description" in all_tools["fs__read_file"].description

    def test_hybrid_search_retrieval(
        self, memory_vector_store: VectorStore, sample_tools: List[IndexedTool]
    ):
        memory_vector_store.upsert_tools(sample_tools)

        results = memory_vector_store.hybrid_search(
            query="read file contents", limit=2, threshold=0.1
        )
        assert len(results) > 0
        top = results[0]
        assert isinstance(top, SearchResult)
        assert top.score >= 0.1
        assert top.tool.namespaced_name in [
            "fs__read_file",
            "fs__write_file",
        ]

    def test_remove_server_tools(
        self, memory_vector_store: VectorStore, sample_tools: List[IndexedTool]
    ):
        memory_vector_store.upsert_tools(sample_tools)
        assert memory_vector_store.get_total_tools_count() == 3

        deleted = memory_vector_store.remove_server_tools("fs")
        assert deleted == 2
        assert memory_vector_store.get_total_tools_count() == 1

        remaining = memory_vector_store.get_all_tools()
        assert remaining[0].server_name == "git"

    def test_empty_query_returns_empty_results(
        self, memory_vector_store: VectorStore, sample_tools: List[IndexedTool]
    ):
        memory_vector_store.upsert_tools(sample_tools)
        assert memory_vector_store.hybrid_search("   ") == []
