import json
import os
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

                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    content TEXT NOT NULL,
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

    def create_document(self, title: str, source_type: str, chunks: list[str]) -> dict:
        document_id = str(uuid.uuid4())
        timestamp = utc_now()
        normalized_title = title.strip()[:160] or "未命名资料"
        normalized_type = source_type.strip().lower()[:16] or "txt"
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO documents(id, title, source_type, chunk_count, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (document_id, normalized_title, normalized_type, len(chunks), timestamp),
            )
            connection.executemany(
                """
                INSERT INTO knowledge_chunks(document_id, position, content)
                VALUES (?, ?, ?)
                """,
                ((document_id, position, content) for position, content in enumerate(chunks)),
            )
        return self.get_document(document_id)

    def get_document(self, document_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id, title, source_type, chunk_count, created_at
                FROM documents WHERE id = ?
                """,
                (document_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_documents(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    d.id,
                    d.title,
                    d.source_type,
                    d.chunk_count,
                    d.created_at,
                    SUM(CASE WHEN c.embedding IS NOT NULL THEN 1 ELSE 0 END) AS indexed_count
                FROM documents d
                LEFT JOIN knowledge_chunks c ON c.document_id = d.id
                GROUP BY d.id
                ORDER BY d.created_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_document(self, document_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        return cursor.rowcount > 0

    def get_document_chunks(self, document_id: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, document_id, position, content, embedding, embedding_dim
                FROM knowledge_chunks WHERE document_id = ? ORDER BY position
                """,
                (document_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_knowledge_chunks(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    c.id,
                    c.document_id,
                    c.position,
                    c.content,
                    c.embedding,
                    c.embedding_dim,
                    d.title
                FROM knowledge_chunks c
                JOIN documents d ON d.id = c.document_id
                ORDER BY d.created_at DESC, c.position
                """
            ).fetchall()
        return [dict(row) for row in rows]

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
