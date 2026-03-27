from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from claude_token_tracker.pricing import calculate_cost
from claude_token_tracker.stream import (
    TrackedAsyncMessageStreamManager,
    TrackedMessageStreamManager,
)

if TYPE_CHECKING:
    from claude_token_tracker.config import TrackerConfig
    from claude_token_tracker.db import TokenDB

logger = logging.getLogger("claude_token_tracker")


def _build_row(
    message: Any,
    model: str,
    method: str,
    duration_ms: int,
    task_label: str,
    project: str,
    config: TrackerConfig,
) -> dict[str, Any]:
    """Extract a usage row dict from a Message response."""
    input_tokens = message.usage.input_tokens
    output_tokens = message.usage.output_tokens
    input_cost, output_cost = calculate_cost(
        model, input_tokens, output_tokens, config.pricing_overrides
    )
    return dict(
        request_id=getattr(message, "id", None),
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=getattr(message.usage, "cache_read_input_tokens", 0) or 0,
        cache_creation_tokens=getattr(message.usage, "cache_creation_input_tokens", 0) or 0,
        input_cost=input_cost,
        output_cost=output_cost,
        task_label=task_label,
        project=project,
        method=method,
        duration_ms=duration_ms,
    )


class TrackedMessages:
    """Wraps the sync Messages resource to intercept create() and stream()."""

    def __init__(
        self,
        inner: Any,
        db: TokenDB,
        config: TrackerConfig,
        task_label: str,
        project: str,
    ) -> None:
        self._inner = inner
        self._db = db
        self._config = config
        self._task_label = task_label
        self._project = project

    def create(self, *, task_label: str | None = None, **kwargs: Any) -> Any:
        model = kwargs.get("model", "unknown")
        start = time.monotonic()

        message = self._inner.create(**kwargs)

        duration_ms = int((time.monotonic() - start) * 1000)
        try:
            row = _build_row(
                message, model, "create", duration_ms,
                task_label or self._task_label, self._project, self._config,
            )
            self._db.insert_background(**row)
        except Exception:
            logger.debug("Failed to log token usage", exc_info=True)

        return message

    def stream(self, *, task_label: str | None = None, **kwargs: Any) -> TrackedMessageStreamManager:
        model = kwargs.get("model", "unknown")
        return TrackedMessageStreamManager(
            self._inner.stream(**kwargs),
            model, self._db, self._config,
            task_label or self._task_label, self._project,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class TrackedAsyncMessages:
    """Wraps the async AsyncMessages resource to intercept create() and stream()."""

    def __init__(
        self,
        inner: Any,
        db: TokenDB,
        config: TrackerConfig,
        task_label: str,
        project: str,
    ) -> None:
        self._inner = inner
        self._db = db
        self._config = config
        self._task_label = task_label
        self._project = project

    async def create(self, *, task_label: str | None = None, **kwargs: Any) -> Any:
        model = kwargs.get("model", "unknown")
        start = time.monotonic()

        message = await self._inner.create(**kwargs)

        duration_ms = int((time.monotonic() - start) * 1000)
        try:
            row = _build_row(
                message, model, "create", duration_ms,
                task_label or self._task_label, self._project, self._config,
            )
            if self._config.async_logging:
                await self._db.insert_async(**row)
            else:
                self._db.insert_background(**row)
        except Exception:
            logger.debug("Failed to log token usage", exc_info=True)

        return message

    def stream(self, *, task_label: str | None = None, **kwargs: Any) -> TrackedAsyncMessageStreamManager:
        model = kwargs.get("model", "unknown")
        return TrackedAsyncMessageStreamManager(
            self._inner.stream(**kwargs),
            model, self._db, self._config,
            task_label or self._task_label, self._project,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
