from __future__ import annotations

from typing import Any

import anthropic

from claude_token_tracker.config import TrackerConfig
from claude_token_tracker.db import TokenDB
from claude_token_tracker.messages import TrackedAsyncMessages, TrackedMessages


class TrackedAnthropic:
    """Drop-in replacement for anthropic.Anthropic with automatic token tracking.

    Usage:
        client = TrackedAnthropic(api_key="...", project="my_app")
        message = client.messages.create(model="claude-sonnet-4-20250514", ...)
        # Token usage is automatically logged to MySQL
    """

    def __init__(
        self,
        *args: Any,
        tracker_config: TrackerConfig | None = None,
        task_label: str = "",
        project: str = "",
        **kwargs: Any,
    ) -> None:
        self._inner = anthropic.Anthropic(*args, **kwargs)
        self._tracker_config = tracker_config or TrackerConfig.from_env()
        # Pass the API key to config for model discovery
        if not self._tracker_config.anthropic_api_key:
            self._tracker_config.anthropic_api_key = self._inner.api_key or ""
        self._db = TokenDB(self._tracker_config)
        self._task_label = task_label or self._tracker_config.default_task_label
        self._project = project or self._tracker_config.default_project

    @property
    def messages(self) -> TrackedMessages:
        return TrackedMessages(
            self._inner.messages,
            self._db,
            self._tracker_config,
            self._task_label,
            self._project,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class TrackedAsyncAnthropic:
    """Drop-in replacement for anthropic.AsyncAnthropic with automatic token tracking.

    Usage:
        client = TrackedAsyncAnthropic(api_key="...", project="my_app")
        message = await client.messages.create(model="claude-sonnet-4-20250514", ...)
        # Token usage is automatically logged to MySQL
    """

    def __init__(
        self,
        *args: Any,
        tracker_config: TrackerConfig | None = None,
        task_label: str = "",
        project: str = "",
        **kwargs: Any,
    ) -> None:
        self._inner = anthropic.AsyncAnthropic(*args, **kwargs)
        self._tracker_config = tracker_config or TrackerConfig.from_env()
        # Pass the API key to config for model discovery
        if not self._tracker_config.anthropic_api_key:
            self._tracker_config.anthropic_api_key = self._inner.api_key or ""
        self._db = TokenDB(self._tracker_config)
        self._task_label = task_label or self._tracker_config.default_task_label
        self._project = project or self._tracker_config.default_project

    @property
    def messages(self) -> TrackedAsyncMessages:
        return TrackedAsyncMessages(
            self._inner.messages,
            self._db,
            self._tracker_config,
            self._task_label,
            self._project,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
