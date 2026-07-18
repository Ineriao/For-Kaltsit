import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self) -> None:
        default_directory = Path(__file__).resolve().parent / ".data"
        self.data_directory = Path(os.environ.get("KALTSIT_DATA_DIR", default_directory)).expanduser().resolve()
        self.path = self.data_directory / "kaltsit.db"
        self.backup_directory = self.data_directory / "backups"

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        self.data_directory.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    text TEXT NOT NULL,
                    sources_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, id);

                CREATE TABLE IF NOT EXISTS knowledge_collections (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    collection_id TEXT REFERENCES knowledge_collections(id) ON DELETE SET NULL,
                    title TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_path TEXT,
                    source_hash TEXT NOT NULL DEFAULT '',
                    source_modified_at TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    locator_text TEXT NOT NULL DEFAULT '',
                    locator_json TEXT NOT NULL DEFAULT '{}',
                    content_hash TEXT NOT NULL DEFAULT '',
                    embedding BLOB,
                    embedding_dim INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document
                ON knowledge_chunks(document_id, position);

                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_session_id TEXT REFERENCES sessions(id) ON DELETE SET NULL,
                    source_excerpt TEXT NOT NULL DEFAULT '',
                    origin TEXT NOT NULL CHECK (origin IN ('automatic', 'manual')),
                    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                    confidence REAL NOT NULL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_unique_content
                ON memories(category, content COLLATE NOCASE);

                CREATE INDEX IF NOT EXISTS idx_memories_enabled
                ON memories(enabled, updated_at DESC);

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            self._migrate_knowledge_schema(connection)

    def create_session(self, title: str, initial_message: str | None = None) -> dict:
        session_id = str(uuid.uuid4())
        timestamp = utc_now()
        normalized_title = title.strip()[:60] or "新对话"
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO sessions(id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, normalized_title, timestamp, timestamp),
            )
            if initial_message and initial_message.strip():
                connection.execute(
                    "INSERT INTO messages(session_id, role, text, created_at) VALUES (?, 'assistant', ?, ?)",
                    (session_id, initial_message.strip(), timestamp),
                )
        return self.get_session(session_id)

    def get_session(self, session_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_sessions(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    s.id,
                    s.title,
                    s.created_at,
                    s.updated_at,
                    COUNT(m.id) AS message_count,
                    COALESCE((
                        SELECT text FROM messages latest
                        WHERE latest.session_id = s.id
                        ORDER BY latest.id DESC LIMIT 1
                    ), '') AS preview
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                GROUP BY s.id
                ORDER BY s.updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_messages(self, session_id: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, session_id, role, text, sources_json, created_at
                FROM messages WHERE session_id = ? ORDER BY id
                """,
                (session_id,),
            ).fetchall()
        return [self._message_from_row(row) for row in rows]

    def append_message(self, session_id: str, role: str, text: str, sources: list[dict] | None = None) -> dict:
        timestamp = utc_now()
        normalized = text.strip()
        with self.connect() as connection:
            session = connection.execute(
                "SELECT title FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if not session:
                raise KeyError(session_id)

            cursor = connection.execute(
                """
                INSERT INTO messages(session_id, role, text, sources_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, role, normalized, json.dumps(sources or [], ensure_ascii=False), timestamp),
            )
            if role == "user" and session["title"] == "新对话":
                title = normalized.replace("\n", " ")[:22] or "新对话"
                connection.execute(
                    "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                    (title, timestamp, session_id),
                )
            else:
                connection.execute(
                    "UPDATE sessions SET updated_at = ? WHERE id = ?",
                    (timestamp, session_id),
                )

            row = connection.execute(
                """
                SELECT id, session_id, role, text, sources_json, created_at
                FROM messages WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        return self._message_from_row(row)

    def rename_session(self, session_id: str, title: str) -> dict | None:
        normalized = title.strip()[:60]
        if not normalized:
            return None
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (normalized, utc_now(), session_id),
            )
        return self.get_session(session_id) if cursor.rowcount else None

    def delete_session(self, session_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return cursor.rowcount > 0

    def create_document(
        self,
        title: str,
        source_type: str,
        chunks: list[dict],
        collection_id: str = "default",
        source_path: str | None = None,
        source_hash: str = "",
        source_modified_at: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        document_id = str(uuid.uuid4())
        timestamp = utc_now()
        normalized_title = title.strip()[:160] or "未命名资料"
        normalized_type = source_type.strip().lower()[:16] or "txt"
        with self.connect() as connection:
            self._require_collection(connection, collection_id)
            connection.execute(
                """
                INSERT INTO documents(
                    id, collection_id, title, source_type, source_path, source_hash,
                    source_modified_at, chunk_count, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    collection_id,
                    normalized_title,
                    normalized_type,
                    source_path,
                    source_hash,
                    source_modified_at,
                    len(chunks),
                    json.dumps(metadata or {}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
            )
            self._insert_knowledge_chunks(connection, document_id, normalized_title, chunks)
        return self.get_document(document_id)

    def upsert_document(
        self,
        title: str,
        source_type: str,
        chunks: list[dict],
        collection_id: str = "default",
        source_path: str | None = None,
        source_hash: str = "",
        source_modified_at: str | None = None,
        metadata: dict | None = None,
    ) -> tuple[dict, str]:
        normalized_path = source_path.strip()[:1024] if source_path and source_path.strip() else None
        if not normalized_path:
            document = self.create_document(
                title,
                source_type,
                chunks,
                collection_id,
                None,
                source_hash,
                source_modified_at,
                metadata,
            )
            return document, "created"

        timestamp = utc_now()
        normalized_title = title.strip()[:160] or "未命名资料"
        normalized_type = source_type.strip().lower()[:16] or "txt"
        with self.connect() as connection:
            self._require_collection(connection, collection_id)
            existing = connection.execute(
                """
                SELECT id, source_hash FROM documents
                WHERE collection_id = ? AND source_path = ?
                """,
                (collection_id, normalized_path),
            ).fetchone()
            if existing and source_hash and existing["source_hash"] == source_hash:
                document_id = existing["id"]
                connection.execute(
                    """
                    UPDATE documents SET source_modified_at = ?, updated_at = ? WHERE id = ?
                    """,
                    (source_modified_at, timestamp, document_id),
                )
                status = "unchanged"
            elif existing:
                document_id = existing["id"]
                connection.execute("DELETE FROM knowledge_fts WHERE document_id = ?", (document_id,))
                connection.execute("DELETE FROM knowledge_chunks WHERE document_id = ?", (document_id,))
                connection.execute(
                    """
                    UPDATE documents SET title = ?, source_type = ?, source_hash = ?,
                        source_modified_at = ?, chunk_count = ?, metadata_json = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        normalized_title,
                        normalized_type,
                        source_hash,
                        source_modified_at,
                        len(chunks),
                        json.dumps(metadata or {}, ensure_ascii=False),
                        timestamp,
                        document_id,
                    ),
                )
                self._insert_knowledge_chunks(connection, document_id, normalized_title, chunks)
                status = "updated"
            else:
                document_id = str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO documents(
                        id, collection_id, title, source_type, source_path, source_hash,
                        source_modified_at, chunk_count, metadata_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        collection_id,
                        normalized_title,
                        normalized_type,
                        normalized_path,
                        source_hash,
                        source_modified_at,
                        len(chunks),
                        json.dumps(metadata or {}, ensure_ascii=False),
                        timestamp,
                        timestamp,
                    ),
                )
                self._insert_knowledge_chunks(connection, document_id, normalized_title, chunks)
                status = "created"
        return self.get_document(document_id), status

    def get_document(self, document_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id, collection_id, title, source_type, source_path, source_hash,
                       source_modified_at, enabled, chunk_count, metadata_json,
                       created_at, updated_at
                FROM documents WHERE id = ?
                """,
                (document_id,),
            ).fetchone()
        return self._document_from_row(row) if row else None

    def list_documents(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    d.id,
                    d.collection_id,
                    c0.name AS collection_name,
                    d.title,
                    d.source_type,
                    d.source_path,
                    d.source_hash,
                    d.source_modified_at,
                    d.enabled,
                    d.chunk_count,
                    d.metadata_json,
                    d.created_at,
                    d.updated_at,
                    SUM(CASE WHEN c.embedding IS NOT NULL THEN 1 ELSE 0 END) AS indexed_count
                FROM documents d
                LEFT JOIN knowledge_collections c0 ON c0.id = d.collection_id
                LEFT JOIN knowledge_chunks c ON c.document_id = d.id
                GROUP BY d.id
                ORDER BY d.updated_at DESC
                """
            ).fetchall()
        return [self._document_from_row(row) for row in rows]

    def set_document_enabled(self, document_id: str, enabled: bool) -> dict | None:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE documents SET enabled = ?, updated_at = ? WHERE id = ?",
                (int(enabled), utc_now(), document_id),
            )
        return self.get_document(document_id) if cursor.rowcount else None

    def delete_document(self, document_id: str) -> bool:
        with self.connect() as connection:
            connection.execute("DELETE FROM knowledge_fts WHERE document_id = ?", (document_id,))
            cursor = connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        return cursor.rowcount > 0

    def get_document_chunks(self, document_id: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, document_id, position, content, locator_text, locator_json,
                       content_hash, embedding, embedding_dim
                FROM knowledge_chunks WHERE document_id = ? ORDER BY position
                """,
                (document_id,),
            ).fetchall()
        return [self._chunk_from_row(row) for row in rows]

    def list_knowledge_chunks(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    c.id,
                    c.document_id,
                    c.position,
                    c.content,
                    c.locator_text,
                    c.locator_json,
                    c.content_hash,
                    c.embedding,
                    c.embedding_dim,
                    d.title,
                    d.collection_id,
                    g.name AS collection_name
                FROM knowledge_chunks c
                JOIN documents d ON d.id = c.document_id
                JOIN knowledge_collections g ON g.id = d.collection_id
                WHERE d.enabled = 1 AND g.enabled = 1
                ORDER BY d.updated_at DESC, c.position
                """
            ).fetchall()
        return [self._chunk_from_row(row) for row in rows]

    def search_knowledge_fts(self, query: str, limit: int = 24) -> list[dict]:
        terms = self._fts_terms(query)
        if not terms:
            return []
        expression = " OR ".join(f'"{term}"' for term in terms[:16])
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT c.id, bm25(knowledge_fts, 1.0, 0.2, 0.1) AS rank,
                       c.document_id, c.position, c.content, c.locator_text,
                       c.locator_json, c.content_hash, c.embedding, c.embedding_dim,
                       d.title, d.collection_id, g.name AS collection_name
                FROM knowledge_fts f
                JOIN knowledge_chunks c ON c.id = f.chunk_id
                JOIN documents d ON d.id = c.document_id
                JOIN knowledge_collections g ON g.id = d.collection_id
                WHERE knowledge_fts MATCH ? AND d.enabled = 1 AND g.enabled = 1
                ORDER BY rank LIMIT ?
                """,
                (expression, max(1, min(limit, 100))),
            ).fetchall()
        results = []
        for row in rows:
            chunk = self._chunk_from_row(row)
            chunk["fts_rank"] = float(row["rank"])
            results.append(chunk)
        return results

    def update_chunk_embeddings(self, embeddings: list[tuple[int, bytes, int]]) -> None:
        if not embeddings:
            return
        with self.connect() as connection:
            connection.executemany(
                """
                UPDATE knowledge_chunks SET embedding = ?, embedding_dim = ? WHERE id = ?
                """,
                ((blob, dimension, chunk_id) for chunk_id, blob, dimension in embeddings),
            )

    def create_collection(self, name: str) -> dict:
        normalized = name.strip()[:60]
        if not normalized:
            raise ValueError("知识分组名称不能为空")
        collection_id = str(uuid.uuid4())
        timestamp = utc_now()
        with self.connect() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO knowledge_collections(id, name, enabled, created_at, updated_at)
                    VALUES (?, ?, 1, ?, ?)
                    """,
                    (collection_id, normalized, timestamp, timestamp),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("同名知识分组已存在") from error
        return self.get_collection(collection_id)

    def get_collection(self, collection_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT g.id, g.name, g.enabled, g.created_at, g.updated_at,
                       COUNT(d.id) AS document_count
                FROM knowledge_collections g
                LEFT JOIN documents d ON d.collection_id = g.id
                WHERE g.id = ? GROUP BY g.id
                """,
                (collection_id,),
            ).fetchone()
        return self._collection_from_row(row) if row else None

    def list_collections(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT g.id, g.name, g.enabled, g.created_at, g.updated_at,
                       COUNT(d.id) AS document_count
                FROM knowledge_collections g
                LEFT JOIN documents d ON d.collection_id = g.id
                GROUP BY g.id ORDER BY CASE WHEN g.id = 'default' THEN 0 ELSE 1 END, g.created_at
                """
            ).fetchall()
        return [self._collection_from_row(row) for row in rows]

    def update_collection(self, collection_id: str, name: str, enabled: bool) -> dict | None:
        normalized = name.strip()[:60]
        if not normalized:
            raise ValueError("知识分组名称不能为空")
        with self.connect() as connection:
            try:
                cursor = connection.execute(
                    """
                    UPDATE knowledge_collections SET name = ?, enabled = ?, updated_at = ? WHERE id = ?
                    """,
                    (normalized, int(enabled), utc_now(), collection_id),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("同名知识分组已存在") from error
        return self.get_collection(collection_id) if cursor.rowcount else None

    def list_memories(self, enabled_only: bool = False, limit: int = 100) -> list[dict]:
        where = "WHERE enabled = 1" if enabled_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT id, category, content, source_session_id, source_excerpt,
                       origin, enabled, confidence, created_at, updated_at
                FROM memories {where}
                ORDER BY updated_at DESC LIMIT ?
                """,
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [self._memory_from_row(row) for row in rows]

    def get_memory(self, memory_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id, category, content, source_session_id, source_excerpt,
                       origin, enabled, confidence, created_at, updated_at
                FROM memories WHERE id = ?
                """,
                (memory_id,),
            ).fetchone()
        return self._memory_from_row(row) if row else None

    def create_memory(
        self,
        category: str,
        content: str,
        source_session_id: str | None = None,
        source_excerpt: str = "",
        origin: str = "manual",
        confidence: float = 1.0,
    ) -> dict:
        timestamp = utc_now()
        memory_id = str(uuid.uuid4())
        existing_id = None
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM memories WHERE category = ? AND content = ? COLLATE NOCASE",
                (category, content),
            ).fetchone()
            if existing:
                existing_id = existing["id"]
                connection.execute(
                    "UPDATE memories SET enabled = 1, updated_at = ? WHERE id = ?",
                    (timestamp, existing_id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO memories(
                        id, category, content, source_session_id, source_excerpt,
                        origin, enabled, confidence, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (
                        memory_id,
                        category,
                        content,
                        source_session_id,
                        source_excerpt,
                        origin,
                        max(0.0, min(float(confidence), 1.0)),
                        timestamp,
                        timestamp,
                    ),
                )
        return self.get_memory(existing_id or memory_id)

    def update_memory(
        self,
        memory_id: str,
        category: str,
        content: str,
        enabled: bool,
    ) -> dict | None:
        with self.connect() as connection:
            try:
                cursor = connection.execute(
                    """
                    UPDATE memories
                    SET category = ?, content = ?, enabled = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (category, content, int(enabled), utc_now(), memory_id),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("相同记忆已存在") from error
        return self.get_memory(memory_id) if cursor.rowcount else None

    def delete_memory(self, memory_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cursor.rowcount > 0

    def get_setting(self, key: str, default=None):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT value_json FROM app_settings WHERE key = ?",
                (key,),
            ).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value_json"])
        except (json.JSONDecodeError, TypeError):
            return default

    def set_setting(self, key: str, value) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO app_settings(key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, json.dumps(value, ensure_ascii=False), utc_now()),
            )

    def create_backup(self, prefix: str = "kaltsit") -> dict:
        self.backup_directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"{prefix}-{timestamp}-{uuid.uuid4().hex[:6]}.db"
        destination = self.backup_directory / filename
        with self.connect() as source, sqlite3.connect(destination) as target:
            source.backup(target)
        return self._backup_info(destination)

    def list_backups(self) -> list[dict]:
        if not self.backup_directory.exists():
            return []
        backups = [self._backup_info(item) for item in self.backup_directory.glob("*.db") if item.is_file()]
        return sorted(backups, key=lambda item: item["created_at"], reverse=True)

    def restore_backup(self, filename: str) -> dict:
        if Path(filename).name != filename or not filename.endswith(".db"):
            raise ValueError("备份文件名无效")
        source_path = (self.backup_directory / filename).resolve()
        if source_path.parent != self.backup_directory.resolve() or not source_path.is_file():
            raise FileNotFoundError(filename)

        with sqlite3.connect(source_path) as verification:
            result = verification.execute("PRAGMA quick_check").fetchone()
            if not result or result[0] != "ok":
                raise ValueError("备份数据库完整性检查失败")

        recovery_backup = self.create_backup("pre-restore")
        with sqlite3.connect(source_path) as source, self.connect() as target:
            source.backup(target)
        self.initialize()
        return {"restored": self._backup_info(source_path), "recovery_backup": recovery_backup}

    def diagnostics(self) -> dict:
        counts = {}
        with self.connect() as connection:
            for table in ("sessions", "messages", "memories", "knowledge_collections", "documents", "knowledge_chunks"):
                counts[table] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
        return {
            "database_size": self.path.stat().st_size if self.path.exists() else 0,
            "integrity": integrity,
            "counts": counts,
            "backups": len(self.list_backups()),
        }

    @staticmethod
    def _message_from_row(row: sqlite3.Row) -> dict:
        message = dict(row)
        try:
            message["sources"] = json.loads(message.pop("sources_json"))
        except (json.JSONDecodeError, TypeError):
            message["sources"] = []
        return message

    @staticmethod
    def _memory_from_row(row: sqlite3.Row) -> dict:
        memory = dict(row)
        memory["enabled"] = bool(memory["enabled"])
        return memory

    @staticmethod
    def _document_from_row(row: sqlite3.Row) -> dict:
        document = dict(row)
        document["enabled"] = bool(document.get("enabled", 1))
        try:
            document["metadata"] = json.loads(document.pop("metadata_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            document["metadata"] = {}
        return document

    @staticmethod
    def _chunk_from_row(row: sqlite3.Row) -> dict:
        chunk = dict(row)
        try:
            chunk["locator"] = json.loads(chunk.pop("locator_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            chunk["locator"] = {}
        return chunk

    @staticmethod
    def _collection_from_row(row: sqlite3.Row) -> dict:
        collection = dict(row)
        collection["enabled"] = bool(collection["enabled"])
        return collection

    def _migrate_knowledge_schema(self, connection: sqlite3.Connection) -> None:
        timestamp = utc_now()
        connection.execute(
            """
            INSERT OR IGNORE INTO knowledge_collections(id, name, enabled, created_at, updated_at)
            VALUES ('default', '默认知识库', 1, ?, ?)
            """,
            (timestamp, timestamp),
        )
        document_columns = {
            "collection_id": "TEXT",
            "source_path": "TEXT",
            "source_hash": "TEXT NOT NULL DEFAULT ''",
            "source_modified_at": "TEXT",
            "enabled": "INTEGER NOT NULL DEFAULT 1",
            "metadata_json": "TEXT NOT NULL DEFAULT '{}'",
            "updated_at": "TEXT",
        }
        chunk_columns = {
            "locator_text": "TEXT NOT NULL DEFAULT ''",
            "locator_json": "TEXT NOT NULL DEFAULT '{}'",
            "content_hash": "TEXT NOT NULL DEFAULT ''",
        }
        for column, definition in document_columns.items():
            self._ensure_column(connection, "documents", column, definition)
        for column, definition in chunk_columns.items():
            self._ensure_column(connection, "knowledge_chunks", column, definition)
        connection.execute(
            """
            UPDATE documents SET collection_id = COALESCE(NULLIF(collection_id, ''), 'default'),
                updated_at = COALESCE(updated_at, created_at)
            """
        )
        connection.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_documents_collection
            ON documents(collection_id, enabled, updated_at DESC);

            CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_source
            ON documents(collection_id, source_path) WHERE source_path IS NOT NULL;

            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                searchable,
                title,
                locator,
                chunk_id UNINDEXED,
                document_id UNINDEXED,
                tokenize = 'unicode61'
            );
            """
        )
        connection.execute("DELETE FROM knowledge_fts")
        rows = connection.execute(
            """
            SELECT c.id, c.document_id, c.content, c.locator_text, d.title
            FROM knowledge_chunks c JOIN documents d ON d.id = c.document_id
            """
        ).fetchall()
        connection.executemany(
            """
            INSERT INTO knowledge_fts(searchable, title, locator, chunk_id, document_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                (
                    self._fts_searchable(row["content"]),
                    row["title"],
                    row["locator_text"],
                    row["id"],
                    row["document_id"],
                )
                for row in rows
            ),
        )

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _require_collection(connection: sqlite3.Connection, collection_id: str) -> None:
        exists = connection.execute(
            "SELECT 1 FROM knowledge_collections WHERE id = ?",
            (collection_id,),
        ).fetchone()
        if not exists:
            raise KeyError(collection_id)

    def _insert_knowledge_chunks(
        self,
        connection: sqlite3.Connection,
        document_id: str,
        title: str,
        chunks: list[dict],
    ) -> None:
        for position, chunk in enumerate(chunks):
            content = str(chunk.get("content", "")).strip()
            locator_text = str(chunk.get("locator_text", "")).strip()[:160]
            locator = chunk.get("locator") if isinstance(chunk.get("locator"), dict) else {}
            cursor = connection.execute(
                """
                INSERT INTO knowledge_chunks(
                    document_id, position, content, locator_text, locator_json, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    position,
                    content,
                    locator_text,
                    json.dumps(locator, ensure_ascii=False),
                    str(chunk.get("content_hash", "")),
                ),
            )
            connection.execute(
                """
                INSERT INTO knowledge_fts(searchable, title, locator, chunk_id, document_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    self._fts_searchable(content),
                    title,
                    locator_text,
                    cursor.lastrowid,
                    document_id,
                ),
            )

    @staticmethod
    def _fts_searchable(text: str) -> str:
        lowered = text.lower()
        tokens = re.findall(r"[a-z0-9_]{2,}", lowered)
        for run in re.findall(r"[\u4e00-\u9fff]+", lowered):
            tokens.extend(run[index:index + 2] for index in range(len(run) - 1))
            tokens.append(run)
            tokens.extend(run)
        return " ".join(tokens)

    @classmethod
    def _fts_terms(cls, text: str) -> list[str]:
        searchable = cls._fts_searchable(text)
        seen = set()
        terms = []
        for term in searchable.split():
            if term not in seen:
                seen.add(term)
                terms.append(term.replace('"', '""'))
        return terms

    @staticmethod
    def _backup_info(backup_path: Path) -> dict:
        stats = backup_path.stat()
        return {
            "name": backup_path.name,
            "size": stats.st_size,
            "created_at": datetime.fromtimestamp(stats.st_mtime, timezone.utc).isoformat(timespec="seconds"),
        }
