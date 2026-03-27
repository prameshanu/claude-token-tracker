from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import threading
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from claude_token_tracker.config import TrackerConfig

logger = logging.getLogger("claude_token_tracker")

# ── Column order for inserts ──
COLUMNS = (
    "request_id", "model", "input_tokens", "output_tokens",
    "cache_read_tokens", "cache_creation_tokens",
    "input_cost", "output_cost",
    "task_label", "project", "method", "duration_ms",
)

MYSQL_INSERT = """
INSERT INTO claude_token_usage
    (request_id, model, input_tokens, output_tokens,
     cache_read_tokens, cache_creation_tokens,
     input_cost, output_cost,
     task_label, project, method, duration_ms)
VALUES
    (%(request_id)s, %(model)s, %(input_tokens)s, %(output_tokens)s,
     %(cache_read_tokens)s, %(cache_creation_tokens)s,
     %(input_cost)s, %(output_cost)s,
     %(task_label)s, %(project)s, %(method)s, %(duration_ms)s)
"""

SQLITE_CREATE = """
CREATE TABLE IF NOT EXISTS claude_token_usage (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id            TEXT,
    model                 TEXT NOT NULL,
    input_tokens          INTEGER NOT NULL DEFAULT 0,
    output_tokens         INTEGER NOT NULL DEFAULT 0,
    total_tokens          INTEGER GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,
    cache_read_tokens     INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    input_cost            REAL NOT NULL DEFAULT 0,
    output_cost           REAL NOT NULL DEFAULT 0,
    total_cost            REAL GENERATED ALWAYS AS (input_cost + output_cost) STORED,
    task_label            TEXT,
    project               TEXT,
    method                TEXT NOT NULL,
    duration_ms           INTEGER,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_model ON claude_token_usage(model);
CREATE INDEX IF NOT EXISTS idx_project ON claude_token_usage(project);
CREATE INDEX IF NOT EXISTS idx_created_at ON claude_token_usage(created_at);
"""

SQLITE_INSERT = """
INSERT INTO claude_token_usage
    (request_id, model, input_tokens, output_tokens,
     cache_read_tokens, cache_creation_tokens,
     input_cost, output_cost,
     task_label, project, method, duration_ms)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


# ── SQLite backend ──

class _SQLiteBackend:
    """Zero-config local SQLite storage."""

    def __init__(self, config: TrackerConfig) -> None:
        self._path = os.path.expanduser(config.sqlite_path)
        self._lock = threading.Lock()
        self._initialized = False

    def _get_conn(self) -> sqlite3.Connection:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path)
        if not self._initialized:
            conn.executescript(SQLITE_CREATE)
            self._initialized = True
        return conn

    def insert(self, row: dict[str, Any]) -> None:
        values = tuple(row.get(c) for c in COLUMNS)
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(SQLITE_INSERT, values)
                conn.commit()
            finally:
                conn.close()


# ── MySQL backend ──

class _MySQLBackend:
    """MySQL storage with connection pooling."""

    def __init__(self, config: TrackerConfig) -> None:
        self._config = config
        self._pool = None
        self._init_lock = threading.Lock()
        self._initialized = False

    def _get_pool(self):
        if self._pool is not None:
            return self._pool

        with self._init_lock:
            if self._pool is not None:
                return self._pool

            import mysql.connector.pooling
            self._pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name="claude_tracker",
                pool_size=self._config.pool_size,
                host=self._config.mysql_host,
                port=self._config.mysql_port,
                user=self._config.mysql_user,
                password=self._config.mysql_password,
                database=self._config.mysql_database,
            )

            if self._config.auto_create_table and not self._initialized:
                self._ensure_table()
                self._initialized = True

            return self._pool

    def _ensure_table(self) -> None:
        schema = resources.files("claude_token_tracker").joinpath("schema.sql").read_text()
        conn = self._pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(schema)
            conn.commit()
        finally:
            conn.close()

    def insert(self, row: dict[str, Any]) -> None:
        pool = self._get_pool()
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(MYSQL_INSERT, row)
            conn.commit()
        finally:
            conn.close()


# ── Excel backend ──

class _ExcelBackend:
    """Excel .xlsx file storage."""

    def __init__(self, config: TrackerConfig) -> None:
        self._path = config.excel_path

    def insert(self, row: dict[str, Any]) -> None:
        from claude_token_tracker.excel import append_row
        append_row(self._path, row)


# ── Storage router ──

class TokenDB:
    """Routes inserts to the configured storage backend(s).

    Backends:
        "sqlite" — local file, zero setup (default)
        "mysql"  — MySQL server
        "excel"  — .xlsx file
        "all"    — writes to all backends
    """

    def __init__(self, config: TrackerConfig) -> None:
        self._config = config
        self._backends: list = []
        backend = config.storage_backend.lower()

        if backend in ("sqlite", "all"):
            self._backends.append(_SQLiteBackend(config))
        if backend in ("mysql", "all"):
            self._backends.append(_MySQLBackend(config))
        if backend in ("excel", "all"):
            self._backends.append(_ExcelBackend(config))

        # Fallback: if invalid backend specified, default to sqlite
        if not self._backends:
            logger.warning("Unknown storage_backend %r, falling back to sqlite", backend)
            self._backends.append(_SQLiteBackend(config))

    def insert_sync(self, **row: object) -> None:
        """Blocking insert to all configured backends."""
        for backend in self._backends:
            try:
                backend.insert(row)
            except Exception:
                logger.debug("Failed to write to %s", type(backend).__name__, exc_info=True)

    async def insert_async(self, **row: object) -> None:
        """Non-blocking insert using run_in_executor."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: self.insert_sync(**row))

    def insert_background(self, **row: object) -> None:
        """Fire-and-forget insert in a daemon thread."""
        t = threading.Thread(target=self._safe_insert, kwargs=row, daemon=True)
        t.start()

    def _safe_insert(self, **row: object) -> None:
        try:
            self.insert_sync(**row)
        except Exception:
            logger.exception("Failed to log token usage")
