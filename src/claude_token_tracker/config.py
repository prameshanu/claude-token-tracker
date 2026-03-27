from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class TrackerConfig:
    """Configuration for the Claude token tracker.

    Storage backends:
        - "json"    — simplest, no dependencies, JSON lines file
        - "sqlite"  (default) — zero setup, local database, works everywhere
        - "mysql"   — requires a MySQL server
        - "excel"   — logs to an .xlsx file only
        - "all"     — logs to all enabled backends simultaneously
    """

    # Storage backend: "json" | "sqlite" | "mysql" | "excel" | "all"
    storage_backend: str = "sqlite"

    # JSON lines file (simplest — no dependencies at all)
    json_path: str = "~/.claude_token_tracker/usage.jsonl"

    # SQLite (default — no setup required)
    sqlite_path: str = "~/.claude_token_tracker/usage.db"

    # MySQL connection (only needed if storage_backend is "mysql" or "all")
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = ""
    mysql_password: str = ""
    mysql_database: str = "claude_tracker"

    # Excel logging (only needed if storage_backend is "excel" or "all")
    excel_path: str = "claude_token_usage.xlsx"

    # Defaults applied to every log entry (overridable per-call)
    default_project: str = ""
    default_task_label: str = ""

    # Behavior
    log_errors: bool = True
    async_logging: bool = True
    auto_create_table: bool = True
    pool_size: int = 5

    # Custom pricing overrides: model_name -> {input_per_mtok, output_per_mtok}
    pricing_overrides: dict[str, dict[str, float]] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> TrackerConfig:
        """Load configuration from CLAUDE_TRACKER_* environment variables."""
        return cls(
            storage_backend=os.getenv("CLAUDE_TRACKER_STORAGE", "sqlite"),
            json_path=os.getenv("CLAUDE_TRACKER_JSON_PATH", "~/.claude_token_tracker/usage.jsonl"),
            sqlite_path=os.getenv("CLAUDE_TRACKER_SQLITE_PATH", "~/.claude_token_tracker/usage.db"),
            mysql_host=os.getenv("CLAUDE_TRACKER_MYSQL_HOST", "localhost"),
            mysql_port=int(os.getenv("CLAUDE_TRACKER_MYSQL_PORT", "3306")),
            mysql_user=os.getenv("CLAUDE_TRACKER_MYSQL_USER", ""),
            mysql_password=os.getenv("CLAUDE_TRACKER_MYSQL_PASSWORD", ""),
            mysql_database=os.getenv("CLAUDE_TRACKER_MYSQL_DATABASE", "claude_tracker"),
            excel_path=os.getenv("CLAUDE_TRACKER_EXCEL_PATH", "claude_token_usage.xlsx"),
            default_project=os.getenv("CLAUDE_TRACKER_DEFAULT_PROJECT", ""),
            default_task_label=os.getenv("CLAUDE_TRACKER_DEFAULT_TASK_LABEL", ""),
            log_errors=os.getenv("CLAUDE_TRACKER_LOG_ERRORS", "true").lower() == "true",
            async_logging=os.getenv("CLAUDE_TRACKER_ASYNC_LOGGING", "true").lower() == "true",
            auto_create_table=os.getenv("CLAUDE_TRACKER_AUTO_CREATE_TABLE", "true").lower() == "true",
            pool_size=int(os.getenv("CLAUDE_TRACKER_POOL_SIZE", "5")),
        )
