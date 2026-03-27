from __future__ import annotations

import asyncio
import logging
import threading
from importlib import resources
from typing import TYPE_CHECKING

import mysql.connector.pooling

if TYPE_CHECKING:
    from claude_token_tracker.config import TrackerConfig

logger = logging.getLogger("claude_token_tracker")

INSERT_SQL = """
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


class TokenDB:
    """MySQL connection pool for logging token usage."""

    def __init__(self, config: TrackerConfig) -> None:
        self._config = config
        self._pool: mysql.connector.pooling.MySQLConnectionPool | None = None
        self._init_lock = threading.Lock()
        self._initialized = False

    def _get_pool(self) -> mysql.connector.pooling.MySQLConnectionPool:
        if self._pool is not None:
            return self._pool

        with self._init_lock:
            if self._pool is not None:
                return self._pool

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
        """Create the tracking table if it doesn't exist."""
        schema = resources.files("claude_token_tracker").joinpath("schema.sql").read_text()
        conn = self._pool.get_connection()  # type: ignore[union-attr]
        try:
            cursor = conn.cursor()
            cursor.execute(schema)
            conn.commit()
        finally:
            conn.close()

    def insert_sync(self, **row: object) -> None:
        """Blocking insert of a usage row to MySQL + Excel (if enabled)."""
        pool = self._get_pool()
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(INSERT_SQL, row)
            conn.commit()
        finally:
            conn.close()

        self._write_excel(row)

    async def insert_async(self, **row: object) -> None:
        """Non-blocking insert using run_in_executor."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: self.insert_sync(**row))

    def insert_background(self, **row: object) -> None:
        """Fire-and-forget insert in a daemon thread."""
        t = threading.Thread(target=self._safe_insert, kwargs=row, daemon=True)
        t.start()

    def _write_excel(self, row: dict) -> None:
        """Write to Excel file if enabled in config."""
        if not self._config.excel_enabled:
            return
        try:
            from claude_token_tracker.excel import append_row
            append_row(self._config.excel_path, row)
        except Exception:
            logger.debug("Failed to write token usage to Excel", exc_info=True)

    def _safe_insert(self, **row: object) -> None:
        try:
            self.insert_sync(**row)
        except Exception:
            logger.exception("Failed to log token usage to MySQL")
