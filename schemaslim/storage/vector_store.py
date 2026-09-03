"""Local hybrid vector storage combining sqlite-vec (dense) and SQLite FTS5 (sparse/lexical)."""

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import sqlite_vec

from schemaslim.storage.models import IndexedTool, SearchResult
from schemaslim.utils.logger import get_logger

logger = get_logger("storage")

VECTOR_DIMENSION = 384
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


class VectorStore:
    """Hybrid SQLite-based vector store for indexed MCP tool schemas."""

    def __init__(
        self,
        db_path: Union[str, Path] = "~/.schemaslim/index.db",
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        embedder: Optional[Any] = None,
    ) -> None:
        """Initialize SQLite database, load sqlite-vec extension, and prepare tables.

        Args:
            db_path: Path to SQLite database file or ':memory:'.
            embedding_model: HuggingFace model identifier for FastEmbed.
            embedder: Optional pre-instantiated embedder (useful for unit tests/mocking).
        """
        self.raw_db_path = str(db_path)
        self.embedding_model = embedding_model
        self._embedder = embedder

        if self.raw_db_path == ":memory:":
            self.db_path = Path(":memory:")
            self._conn = sqlite3.connect(":memory:")
        else:
            p = Path(self.raw_db_path).expanduser().resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            self.db_path = p
            self._conn = sqlite3.connect(str(self.db_path))

        self._conn.row_factory = sqlite3.Row
        self._load_extensions_and_init_db()

    def _load_extensions_and_init_db(self) -> None:
        """Enable sqlite-vec extension and create necessary tables and indexes."""
        self._conn.enable_load_extension(True)
        try:
            sqlite_vec.load(self._conn)
        finally:
            self._conn.enable_load_extension(False)

        cursor = self._conn.cursor()

        # Performance tuning for disk databases
        if self.raw_db_path != ":memory:":
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")

        # Metadata table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tools_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                namespaced_name TEXT UNIQUE NOT NULL,
                server_name TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                description TEXT NOT NULL,
                raw_schema_json TEXT NOT NULL,
                schema_hash TEXT NOT NULL,
                text_for_embedding TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tools_server ON tools_metadata(server_name);"
        )

        # Vector table using sqlite-vec vec0
        cursor.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_tools USING vec0(
                rowid INTEGER PRIMARY KEY,
                tool_embedding float[{VECTOR_DIMENSION}] distance_metric=cosine
            );
            """
        )

        # Full-text search FTS5 table
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS tools_fts USING fts5(
                namespaced_name UNINDEXED,
                tool_name,
                description
            );
            """
        )
        self._conn.commit()
        logger.debug("Database initialized at %s", self.db_path)

    @property
    def embedder(self) -> Any:
        """Lazy-loaded FastEmbed TextEmbedding instance."""
        if self._embedder is None:
            from fastembed import TextEmbedding

            logger.info("Initializing FastEmbed model: %s", self.embedding_model)
            self._embedder = TextEmbedding(model_name=self.embedding_model)
        return self._embedder

    def _generate_embeddings(self, texts: Sequence[str]) -> List[List[float]]:
        """Generate dense vector embeddings for input strings."""
        if not texts:
            return []
        embeddings = list(self.embedder.embed(texts))
        return [list(map(float, vec)) for vec in embeddings]

    def upsert_tools(self, tools: Sequence[IndexedTool]) -> int:
        """Atomically insert or update tools, skipping tools with identical schema_hash.

        Args:
            tools: Sequence of IndexedTool objects.

        Returns:
            Number of newly inserted or updated tools.
        """
        if not tools:
            return 0

        # Identify existing tools and their current hashes (chunked to prevent SQLite parameter limits)
        names = [t.namespaced_name for t in tools]
        cursor = self._conn.cursor()

        existing_map: Dict[str, Tuple[int, str, str]] = {}
        chunk_size = 500
        for i in range(0, len(names), chunk_size):
            chunk = names[i : i + chunk_size]
            placeholders = ",".join("?" for _ in chunk)
            cursor.execute(
                f"SELECT id, namespaced_name, server_name, schema_hash FROM tools_metadata WHERE namespaced_name IN ({placeholders})",
                chunk,
            )
            for row in cursor.fetchall():
                existing_map[row["namespaced_name"]] = (
                    row["id"],
                    row["server_name"],
                    row["schema_hash"],
                )

        # Filter out tools that haven't changed and protect against Confused Deputy hijacking
        to_upsert: List[Tuple[IndexedTool, Optional[int]]] = []
        for tool in tools:
            if tool.namespaced_name in existing_map:
                existing_id, existing_server, existing_hash = existing_map[tool.namespaced_name]
                if existing_server != tool.server_name:
                    logger.error(
                        "Security violation: server '%s' attempted to overwrite tool '%s' owned by '%s'. Blocked.",
                        tool.server_name,
                        tool.namespaced_name,
                        existing_server,
                    )
                    continue
                if existing_hash == tool.schema_hash:
                    # Content unchanged, skip re-embedding
                    continue
                to_upsert.append((tool, existing_id))
            else:
                to_upsert.append((tool, None))

        if not to_upsert:
            logger.debug("All %d tools are already up to date.", len(tools))
            return 0

        logger.info("Generating embeddings for %d updated/new tools...", len(to_upsert))
        texts_to_embed = [item[0].text_for_embedding for item in to_upsert]
        embeddings = self._generate_embeddings(texts_to_embed)

        with self._conn:
            for (tool, existing_id), embedding in zip(to_upsert, embeddings):
                serialized_vec = sqlite_vec.serialize_float32(embedding)
                serialized_params = json.dumps(
                    tool.parameters, ensure_ascii=False, sort_keys=True
                )

                if existing_id is not None:
                    # Update existing record
                    cursor.execute(
                        """
                        UPDATE tools_metadata
                        SET description = ?, raw_schema_json = ?, schema_hash = ?,
                            text_for_embedding = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (
                            tool.description,
                            serialized_params,
                            tool.schema_hash,
                            tool.text_for_embedding,
                            existing_id,
                        ),
                    )
                    # Refresh vec_tools and FTS
                    cursor.execute("DELETE FROM vec_tools WHERE rowid = ?", (existing_id,))
                    cursor.execute(
                        "INSERT INTO vec_tools(rowid, tool_embedding) VALUES (?, ?)",
                        (existing_id, serialized_vec),
                    )
                    cursor.execute(
                        "DELETE FROM tools_fts WHERE namespaced_name = ?",
                        (tool.namespaced_name,),
                    )
                    cursor.execute(
                        "INSERT INTO tools_fts(namespaced_name, tool_name, description) VALUES (?, ?, ?)",
                        (tool.namespaced_name, tool.tool_name, tool.description),
                    )
                else:
                    # Insert new record
                    cursor.execute(
                        """
                        INSERT INTO tools_metadata(
                            namespaced_name, server_name, tool_name, description,
                            raw_schema_json, schema_hash, text_for_embedding
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            tool.namespaced_name,
                            tool.server_name,
                            tool.tool_name,
                            tool.description,
                            serialized_params,
                            tool.schema_hash,
                            tool.text_for_embedding,
                        ),
                    )
                    new_id = cursor.lastrowid
                    cursor.execute(
                        "INSERT INTO vec_tools(rowid, tool_embedding) VALUES (?, ?)",
                        (new_id, serialized_vec),
                    )
                    cursor.execute(
                        "INSERT INTO tools_fts(namespaced_name, tool_name, description) VALUES (?, ?, ?)",
                        (tool.namespaced_name, tool.tool_name, tool.description),
                    )

        logger.info("Successfully upserted %d tools into vector store.", len(to_upsert))
        return len(to_upsert)

    def _clean_fts_query(self, query: str) -> str:
        """Sanitize raw query string for safe FTS5 MATCH query syntax."""
        tokens = re.findall(r"\w+", query, re.UNICODE)
        if not tokens:
            return ""
        # Match any of the extracted keywords
        return " OR ".join(f'"{t}"*' for t in tokens)

    def hybrid_search(
        self,
        query: str,
        limit: int = 5,
        threshold: float = 0.45,
    ) -> List[SearchResult]:
        """Perform hybrid search combining dense semantic similarity and FTS5 keyword matching.

        Args:
            query: User's intent or query description.
            limit: Maximum results to return.
            threshold: Minimum hybrid score (0.0 to 1.0) to filter out irrelevant tools.

        Returns:
            Ranked list of SearchResult items exceeding threshold.
        """
        stripped_query = query.strip()
        if not stripped_query:
            return []

        cursor = self._conn.cursor()

        # 1. Vector Search
        query_vec = self._generate_embeddings([stripped_query])[0]
        serialized_query_vec = sqlite_vec.serialize_float32(query_vec)

        # Retrieve top candidates by cosine distance
        candidate_k = max(limit * 4, 20)
        cursor.execute(
            """
            SELECT rowid, distance
            FROM vec_tools
            WHERE tool_embedding MATCH ? AND k = ?
            ORDER BY distance ASC
            """,
            (serialized_query_vec, candidate_k),
        )
        vec_matches: Dict[int, float] = {}
        for row in cursor.fetchall():
            dist = float(row["distance"])
            # Cosine distance ranges [0, 2]; map to similarity score [0, 1]
            sim = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
            vec_matches[row["rowid"]] = sim

        # 2. Lexical / FTS5 Search
        fts_query = self._clean_fts_query(stripped_query)
        fts_matches: Dict[str, float] = {}
        if fts_query:
            try:
                cursor.execute(
                    """
                    SELECT namespaced_name, rank
                    FROM tools_fts
                    WHERE tools_fts MATCH ?
                    ORDER BY rank ASC
                    LIMIT ?
                    """,
                    (fts_query, candidate_k),
                )
                for row in cursor.fetchall():
                    # FTS5 rank is negative BM25 score (smaller is better)
                    raw_rank = abs(float(row["rank"]))
                    # Normalize to 0.0 - 1.0 scale
                    fts_score = min(1.0, 1.0 / (1.0 + raw_rank * 0.1))
                    fts_matches[row["namespaced_name"]] = fts_score
            except sqlite3.OperationalError as e:
                logger.warning("FTS query failed for '%s': %s", fts_query, e)

        # 3. Retrieve metadata for all matched rowids (chunked to prevent SQLite variable limits)
        if not vec_matches:
            return []

        all_ids = list(vec_matches.keys())
        metadata_rows: List[sqlite3.Row] = []
        chunk_size = 500
        for i in range(0, len(all_ids), chunk_size):
            chunk = all_ids[i : i + chunk_size]
            placeholders = ",".join("?" for _ in chunk)
            cursor.execute(
                f"""
                SELECT id, namespaced_name, server_name, tool_name, description,
                       raw_schema_json, schema_hash, text_for_embedding
                FROM tools_metadata
                WHERE id IN ({placeholders})
                """,
                chunk,
            )
            metadata_rows.extend(cursor.fetchall())

        # 4. Fuse scores
        results: List[SearchResult] = []
        for row in metadata_rows:
            row_id = row["id"]
            ns_name = row["namespaced_name"]
            v_score = vec_matches.get(row_id, 0.0)
            l_score = fts_matches.get(ns_name, 0.0)

            # Hybrid score: weighted combination with a bonus if matched both
            if l_score > 0.0:
                hybrid_score = (0.70 * v_score) + (0.30 * l_score)
            else:
                # Dense-only match: slightly downweight to favor exact keyword matches
                hybrid_score = v_score * 0.95

            hybrid_score = round(max(0.0, min(1.0, hybrid_score)), 4)

            if hybrid_score < threshold:
                continue

            try:
                params = json.loads(row["raw_schema_json"])
            except Exception:
                params = {}

            tool = IndexedTool(
                server_name=row["server_name"],
                tool_name=row["tool_name"],
                namespaced_name=ns_name,
                description=row["description"],
                parameters=params,
                schema_hash=row["schema_hash"],
                text_for_embedding=row["text_for_embedding"],
            )

            results.append(
                SearchResult(
                    tool=tool,
                    score=hybrid_score,
                    vector_score=round(v_score, 4),
                    lexical_score=round(l_score, 4),
                )
            )

        # Sort descending by hybrid score
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def remove_server_tools(self, server_name: str) -> int:
        """Remove all tools belonging to specified server from metadata, vectors, and FTS."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id, namespaced_name FROM tools_metadata WHERE server_name = ?",
            (server_name,),
        )
        rows = cursor.fetchall()
        if not rows:
            return 0

        ids = [row["id"] for row in rows]
        names = [row["namespaced_name"] for row in rows]

        chunk_size = 500
        with self._conn:
            for i in range(0, len(ids), chunk_size):
                id_chunk = ids[i : i + chunk_size]
                name_chunk = names[i : i + chunk_size]

                id_placeholders = ",".join("?" for _ in id_chunk)
                name_placeholders = ",".join("?" for _ in name_chunk)

                cursor.execute(
                    f"DELETE FROM vec_tools WHERE rowid IN ({id_placeholders})", id_chunk
                )
                cursor.execute(
                    f"DELETE FROM tools_fts WHERE namespaced_name IN ({name_placeholders})",
                    name_chunk,
                )
                cursor.execute(
                    f"DELETE FROM tools_metadata WHERE id IN ({id_placeholders})", id_chunk
                )

        logger.info(
            "Removed %d tools for server '%s' from vector store.", len(rows), server_name
        )
        return len(rows)

    def get_total_tools_count(self) -> int:
        """Return total number of active indexed tools."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM tools_metadata")
        return int(cursor.fetchone()["total"])

    def get_all_tools(self) -> List[IndexedTool]:
        """Fetch all indexed tools ordered by server and name."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT server_name, tool_name, namespaced_name, description,
                   raw_schema_json, schema_hash, text_for_embedding
            FROM tools_metadata
            ORDER BY server_name, tool_name
            """
        )
        tools = []
        for row in cursor.fetchall():
            try:
                params = json.loads(row["raw_schema_json"])
            except Exception:
                params = {}
            tools.append(
                IndexedTool(
                    server_name=row["server_name"],
                    tool_name=row["tool_name"],
                    namespaced_name=row["namespaced_name"],
                    description=row["description"],
                    parameters=params,
                    schema_hash=row["schema_hash"],
                    text_for_embedding=row["text_for_embedding"],
                )
            )
        return tools

    def close(self) -> None:
        """Close SQLite database connection."""
        if hasattr(self, "_conn") and self._conn:
            self._conn.close()

    def __enter__(self) -> "VectorStore":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
