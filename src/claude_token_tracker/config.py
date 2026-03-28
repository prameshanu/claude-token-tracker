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
        - "mssql"   — requires a MSSQL / Azure SQL Edge server
        - "excel"   — logs to an .xlsx file only
        - "all"     — logs to all enabled backends simultaneously
    """

    # Storage backend: "json" | "sqlite" | "mysql" | "mssql" | "excel" | "all"
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

    # MSSQL / Azure SQL Edge (only needed if storage_backend is "mssql" or "all")
    mssql_host: str = "localhost"
    mssql_port: int = 1433
    mssql_user: str = ""
    mssql_password: str = ""
    mssql_database: str = "claude_tracker"

    # Excel logging (only needed if storage_backend is "excel" or "all")
    excel_path: str = "claude_token_usage.xlsx"

    # Defaults applied to every log entry (overridable per-call)
    default_project: str = ""
    default_task_label: str = ""

    # Pricing auto-refresh & model discovery
    pricing_url: str = "https://raw.githubusercontent.com/prameshanu/claude-token-tracker/main/pricing.json"
    pricing_cache_path: str = "~/.claude_token_tracker/pricing_cache.json"
    pricing_refresh_days: int = 7
    auto_discover_models: bool = True
    anthropic_api_key: str = ""  # used for model discovery; auto-set by TrackedAnthropic

    # Email alerts (for pricing fetch failures)
    alert_email: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # Behavior
    log_errors: bool = True
    async_logging: bool = True
    auto_create_table: bool = True
    pool_size: int = 5

    # Custom pricing overrides (highest priority — overrides remote + hardcoded)
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
            mssql_host=os.getenv("CLAUDE_TRACKER_MSSQL_HOST", "localhost"),
            mssql_port=int(os.getenv("CLAUDE_TRACKER_MSSQL_PORT", "1433")),
            mssql_user=os.getenv("CLAUDE_TRACKER_MSSQL_USER", ""),
            mssql_password=os.getenv("CLAUDE_TRACKER_MSSQL_PASSWORD", ""),
            mssql_database=os.getenv("CLAUDE_TRACKER_MSSQL_DATABASE", "claude_tracker"),
            excel_path=os.getenv("CLAUDE_TRACKER_EXCEL_PATH", "claude_token_usage.xlsx"),
            pricing_url=os.getenv("CLAUDE_TRACKER_PRICING_URL", "https://raw.githubusercontent.com/prameshanu/claude-token-tracker/main/pricing.json"),
            pricing_cache_path=os.getenv("CLAUDE_TRACKER_PRICING_CACHE_PATH", "~/.claude_token_tracker/pricing_cache.json"),
            pricing_refresh_days=int(os.getenv("CLAUDE_TRACKER_PRICING_REFRESH_DAYS", "7")),
            auto_discover_models=os.getenv("CLAUDE_TRACKER_AUTO_DISCOVER_MODELS", "true").lower() == "true",
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            alert_email=os.getenv("CLAUDE_TRACKER_ALERT_EMAIL", ""),
            smtp_host=os.getenv("CLAUDE_TRACKER_SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(os.getenv("CLAUDE_TRACKER_SMTP_PORT", "587")),
            smtp_user=os.getenv("CLAUDE_TRACKER_SMTP_USER", ""),
            smtp_password=os.getenv("CLAUDE_TRACKER_SMTP_PASSWORD", ""),
            default_project=os.getenv("CLAUDE_TRACKER_DEFAULT_PROJECT", ""),
            default_task_label=os.getenv("CLAUDE_TRACKER_DEFAULT_TASK_LABEL", ""),
            log_errors=os.getenv("CLAUDE_TRACKER_LOG_ERRORS", "true").lower() == "true",
            async_logging=os.getenv("CLAUDE_TRACKER_ASYNC_LOGGING", "true").lower() == "true",
            auto_create_table=os.getenv("CLAUDE_TRACKER_AUTO_CREATE_TABLE", "true").lower() == "true",
            pool_size=int(os.getenv("CLAUDE_TRACKER_POOL_SIZE", "5")),
        )
