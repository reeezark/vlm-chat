"""RAG MVP 的最小 SQLite 数据模型与检索骨架。"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

from src.config import RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE, RAG_EMBEDDING_DIM
from src.embeddings import EmbeddingProvider, HashEmbeddingProvider


class RagManager:
    """知识库 / 文档 / 切片管理器。

    当前版本提供可落地的数据模型和关键词检索骨架，后续可替换为 Embedding + 向量库。
    """

    def __init__(self, db_path: str = "data/sessions/sessions.db", embedding_provider: EmbeddingProvider | None = None) -> None:
        self.db_path = db_path
        self.embedding_provider = embedding_provider or HashEmbeddingProvider(RAG_EMBEDDING_DIM)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_collections (
                    collection_id TEXT PRIMARY KEY,
                    name          TEXT,
                    description   TEXT,
                    created_at    REAL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_documents (
                    document_id   TEXT PRIMARY KEY,
                    collection_id TEXT,
                    filename      TEXT,
                    content_type  TEXT,
                    status        TEXT,
                    owner_user_id TEXT,
                    created_at    REAL,
                    FOREIGN KEY (collection_id) REFERENCES rag_collections(collection_id) ON DELETE CASCADE
                )
                """
            )
            self._ensure_column(conn, "rag_documents", "owner_user_id", "TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    chunk_id    TEXT PRIMARY KEY,
                    document_id TEXT,
                    chunk_index INTEGER,
                    content     TEXT,
                    embedding   TEXT,
                    metadata    TEXT,
                    created_at  REAL,
                    FOREIGN KEY (document_id) REFERENCES rag_documents(document_id) ON DELETE CASCADE
                )
                """
            )
            self._ensure_column(conn, "rag_chunks", "embedding", "TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_chunks_doc ON rag_chunks(document_id, chunk_index)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_chunks_content ON rag_chunks(content)")

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """清理 PDF 提取中可能出现的非法 Unicode 代理字符，避免 embedding/SQLite 编码失败。"""
        return (text or "").encode("utf-8", errors="replace").decode("utf-8", errors="replace").strip()

    def get_or_create_collection(self, name: str, description: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT collection_id FROM rag_collections WHERE name = ?",
                (name,),
            ).fetchone()
            if row:
                return row["collection_id"]
        return self.create_collection(name, description)

    def create_collection(self, name: str, description: str = "") -> str:
        collection_id = uuid.uuid4().hex
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO rag_collections (collection_id, name, description, created_at) VALUES (?, ?, ?, ?)",
                (collection_id, name, description, time.time()),
            )
        return collection_id

    def add_document(
        self,
        collection_id: str,
        filename: str,
        content_type: str = "text/plain",
        owner_user_id: str | None = None,
    ) -> str:
        document_id = uuid.uuid4().hex
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO rag_documents
                   (document_id, collection_id, filename, content_type, status, owner_user_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (document_id, collection_id, filename, content_type, "indexed", owner_user_id, time.time()),
            )
        return document_id

    def add_chunk(self, document_id: str, chunk_index: int, content: str, metadata: str = "{}") -> str:
        chunk_id = uuid.uuid4().hex
        content = self._sanitize_text(content)
        embedding = json.dumps(self.embedding_provider.embed(content), separators=(",", ":"))
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO rag_chunks (chunk_id, document_id, chunk_index, content, embedding, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (chunk_id, document_id, chunk_index, content, embedding, metadata, time.time()),
            )
        return chunk_id

    def ingest_text(
        self,
        collection_name: str,
        filename: str,
        text: str,
        content_type: str = "text/plain",
        owner_user_id: str | None = None,
    ) -> tuple[str, int]:
        """将文档文本切片并写入默认知识库，返回 document_id 和切片数量。"""
        cleaned = self._sanitize_text(text)
        if not cleaned:
            return "", 0
        chunks = self.split_text(cleaned)
        if not chunks:
            return "", 0
        collection_id = self.get_or_create_collection(collection_name)
        document_id = uuid.uuid4().hex
        now = time.time()
        chunk_rows = []
        for idx, chunk in enumerate(chunks):
            sanitized_chunk = self._sanitize_text(chunk)
            embedding = json.dumps(self.embedding_provider.embed(sanitized_chunk), separators=(",", ":"))
            chunk_rows.append((uuid.uuid4().hex, document_id, idx, sanitized_chunk, embedding, "{}", now))
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO rag_documents
                   (document_id, collection_id, filename, content_type, status, owner_user_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (document_id, collection_id, filename, content_type, "indexed", owner_user_id, now),
            )
            conn.executemany(
                """INSERT INTO rag_chunks (chunk_id, document_id, chunk_index, content, embedding, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                chunk_rows,
            )
        return document_id, len(chunks)

    @staticmethod
    def split_text(text: str, chunk_size: int = RAG_CHUNK_SIZE, overlap: int = RAG_CHUNK_OVERLAP) -> list[str]:
        """按字符做轻量切片；后续可替换为 token-aware splitter。"""
        text = (text or "").strip()
        if not text:
            return []
        chunk_size = max(1, chunk_size)
        overlap = max(0, min(overlap, chunk_size - 1))
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(text):
                break
            start = end - overlap
        return chunks

    def keyword_search(self, query: str, limit: int = 5) -> list[dict]:
        query = (query or "").strip()
        if not query:
            return []
        terms = [t for t in query.replace("\n", " ").split(" ") if t]
        like_terms = terms[:5] or [query]
        where = " OR ".join(["c.content LIKE ?"] * len(like_terms))
        params = [f"%{term}%" for term in like_terms]
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT c.*, d.filename, d.collection_id
                   FROM rag_chunks c
                   JOIN rag_documents d ON d.document_id = c.document_id
                   WHERE {where}
                   ORDER BY c.created_at DESC
                   LIMIT ?""",
                (*params, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def semantic_search(self, query: str, limit: int = 5, owner_user_id: str | None = None) -> list[dict]:
        """基于本地 embedding 进行相似度检索。"""
        query = (query or "").strip()
        if not query:
            return []
        query_vector = self.embedding_provider.embed(query)
        with self._connect() as conn:
            sql = """SELECT c.*, d.filename, d.collection_id, d.owner_user_id
                   FROM rag_chunks c
                   JOIN rag_documents d ON d.document_id = c.document_id"""
            params: tuple = ()
            if owner_user_id:
                sql += " WHERE d.owner_user_id = ? OR d.owner_user_id IS NULL OR d.owner_user_id = ''"
                params = (owner_user_id,)
            rows = conn.execute(sql, params).fetchall()

        scored: list[dict] = []
        for row in rows:
            item = dict(row)
            embedding = self._decode_embedding(item.get("embedding"))
            if not embedding:
                embedding = self.embedding_provider.embed(item.get("content") or "")
                self._backfill_embedding(item["chunk_id"], embedding)
            score = HashEmbeddingProvider.cosine_similarity(query_vector, embedding)
            if score >= 0.1:
                item["score"] = score
                scored.append(item)
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def list_documents(
        self,
        collection_name: str | None = None,
        limit: int = 100,
        owner_user_id: str | None = None,
    ) -> list[dict]:
        """列出已入库文档，供管理 UI / 排障使用。"""
        filters = []
        params: list = []
        if collection_name:
            filters.append("c.name = ?")
            params.append(collection_name)
        if owner_user_id:
            filters.append("d.owner_user_id = ?")
            params.append(owner_user_id)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT d.*, c.name AS collection_name,
                          COUNT(ch.chunk_id) AS chunk_count
                   FROM rag_documents d
                   JOIN rag_collections c ON c.collection_id = d.collection_id
                   LEFT JOIN rag_chunks ch ON ch.document_id = d.document_id
                   {where}
                   GROUP BY d.document_id
                   ORDER BY d.created_at DESC
                   LIMIT ?""",
                (*params, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_chunks(self, document_id: str, limit: int = 50, owner_user_id: str | None = None) -> list[dict]:
        """列出某文档切片，供引用来源 UI / 排障使用。"""
        owner_clause = "AND d.owner_user_id = ?" if owner_user_id else ""
        params = (document_id, owner_user_id, limit) if owner_user_id else (document_id, limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT c.*, d.filename, d.collection_id, d.owner_user_id
                   FROM rag_chunks c
                   JOIN rag_documents d ON d.document_id = c.document_id
                   WHERE c.document_id = ?
                   {owner_clause}
                   ORDER BY c.chunk_index ASC
                   LIMIT ?""",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_document(self, document_id: str, owner_user_id: str | None = None) -> bool:
        """删除单个入库文档及其切片。"""
        if not document_id:
            return False
        with self._connect() as conn:
            if owner_user_id:
                row = conn.execute(
                    "SELECT document_id FROM rag_documents WHERE document_id = ? AND owner_user_id = ?",
                    (document_id, owner_user_id),
                ).fetchone()
                if not row:
                    return False
            cur = conn.execute("DELETE FROM rag_chunks WHERE document_id = ?", (document_id,))
            conn.execute("DELETE FROM rag_documents WHERE document_id = ?", (document_id,))
        return cur.rowcount > 0

    def clear_collection(self, collection_name: str | None = None, owner_user_id: str | None = None) -> int:
        """清空知识库，返回删除的文档数量。"""
        filters = []
        params: list = []
        if collection_name:
            filters.append("c.name = ?")
            params.append(collection_name)
        if owner_user_id:
            filters.append("d.owner_user_id = ?")
            params.append(owner_user_id)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT d.document_id
                   FROM rag_documents d
                   JOIN rag_collections c ON c.collection_id = d.collection_id
                   {where}""",
                tuple(params),
            ).fetchall()
            document_ids = [r["document_id"] for r in rows]
            for document_id in document_ids:
                conn.execute("DELETE FROM rag_chunks WHERE document_id = ?", (document_id,))
                conn.execute("DELETE FROM rag_documents WHERE document_id = ?", (document_id,))
        return len(document_ids)

    def cleanup_empty_documents(self, owner_user_id: str | None = None) -> int:
        """清理历史异常中遗留的无切片文档，避免 UI 展示不可检索的知识库条目。"""
        owner_clause = "AND d.owner_user_id = ?" if owner_user_id else ""
        params = (owner_user_id,) if owner_user_id else ()
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT d.document_id
                   FROM rag_documents d
                   LEFT JOIN rag_chunks c ON c.document_id = d.document_id
                   WHERE c.chunk_id IS NULL
                   {owner_clause}""",
                params,
            ).fetchall()
            document_ids = [row["document_id"] for row in rows]
            for document_id in document_ids:
                conn.execute("DELETE FROM rag_documents WHERE document_id = ?", (document_id,))
        return len(document_ids)

    @staticmethod
    def format_references(results: list[dict], max_excerpt_chars: int = 120) -> str:
        """将检索结果格式化为面向用户的引用来源 Markdown。"""
        if not results:
            return ""
        lines = ["\n\n---\n**引用来源**"]
        for idx, item in enumerate(results, start=1):
            filename = item.get("filename") or "unknown"
            chunk_index = item.get("chunk_index")
            score = item.get("score")
            content = " ".join((item.get("content") or "").split())
            if len(content) > max_excerpt_chars:
                content = content[:max_excerpt_chars].rstrip() + "..."
            score_text = f"，相似度 {score:.2f}" if isinstance(score, (float, int)) else ""
            lines.append(f"{idx}. `{filename}` 第 {chunk_index} 段{score_text}: {content}")
        return "\n".join(lines)

    @staticmethod
    def _decode_embedding(value: str | None) -> list[float]:
        if not value:
            return []
        try:
            data = json.loads(value)
            if isinstance(data, list):
                return [float(v) for v in data]
        except Exception:
            return []
        return []

    def _backfill_embedding(self, chunk_id: str, embedding: list[float]) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE rag_chunks SET embedding = ? WHERE chunk_id = ?",
                (json.dumps(embedding, separators=(",", ":")), chunk_id),
            )
