from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from claude_token_tracker.pricing import calculate_cost

if TYPE_CHECKING:
    from claude_token_tracker.config import TrackerConfig
    from claude_token_tracker.db import TokenDB

logger = logging.getLogger("claude_token_tracker")


class TrackedMessageStreamManager:
    """Wraps anthropic MessageStreamManager (sync) to log usage after stream completes."""

    def __init__(
        self,
        inner_manager: object,
        model: str,
        db: TokenDB,
        config: TrackerConfig,
        task_label: str,
        project: str,
    ) -> None:
        self._inner = inner_manager
        self._model = model
        self._db = db
        self._config = config
        self._task_label = task_label
        self._project = project
        self._start_time: float | None = None
        self._stream: object | None = None

    def __enter__(self):
        self._start_time = time.monotonic()
        self._stream = self._inner.__enter__()
        return self._stream

    def __exit__(self, exc_type, exc_val, exc_tb):
        result = self._inner.__exit__(exc_type, exc_val, exc_tb)

        if exc_type is None and self._stream is not None:
            try:
                final = self._stream.get_final_message()
                duration_ms = int((time.monotonic() - self._start_time) * 1000)
                input_tokens = final.usage.input_tokens
                output_tokens = final.usage.output_tokens
                cache_read_tokens = getattr(final.usage, "cache_read_input_tokens", 0) or 0
                cache_creation_tokens = getattr(final.usage, "cache_creation_input_tokens", 0) or 0
                input_cost, output_cost = calculate_cost(
                    self._model, input_tokens, output_tokens,
                    cache_read_tokens=cache_read_tokens,
                    cache_creation_tokens=cache_creation_tokens,
                    overrides=self._config.pricing_overrides,
                )
                row = dict(
                    request_id=getattr(final, "id", None),
                    model=self._model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_read_tokens=cache_read_tokens,
                    cache_creation_tokens=cache_creation_tokens,
                    input_cost=input_cost,
                    output_cost=output_cost,
                    task_label=self._task_label,
                    project=self._project,
                    method="stream",
                    duration_ms=duration_ms,
                )
                self._db.insert_background(**row)
            except Exception:
                logger.debug("Failed to extract stream usage", exc_info=True)

        return result


class TrackedAsyncMessageStreamManager:
    """Wraps anthropic AsyncMessageStreamManager to log usage after stream completes."""

    def __init__(
        self,
        inner_manager: object,
        model: str,
        db: TokenDB,
        config: TrackerConfig,
        task_label: str,
        project: str,
    ) -> None:
        self._inner = inner_manager
        self._model = model
        self._db = db
        self._config = config
        self._task_label = task_label
        self._project = project
        self._start_time: float | None = None
        self._stream: object | None = None

    async def __aenter__(self):
        self._start_time = time.monotonic()
        self._stream = await self._inner.__aenter__()
        return self._stream

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        result = await self._inner.__aexit__(exc_type, exc_val, exc_tb)

        if exc_type is None and self._stream is not None:
            try:
                final = self._stream.get_final_message()
                duration_ms = int((time.monotonic() - self._start_time) * 1000)
                input_tokens = final.usage.input_tokens
                output_tokens = final.usage.output_tokens
                cache_read_tokens = getattr(final.usage, "cache_read_input_tokens", 0) or 0
                cache_creation_tokens = getattr(final.usage, "cache_creation_input_tokens", 0) or 0
                input_cost, output_cost = calculate_cost(
                    self._model, input_tokens, output_tokens,
                    cache_read_tokens=cache_read_tokens,
                    cache_creation_tokens=cache_creation_tokens,
                    overrides=self._config.pricing_overrides,
                )
                row = dict(
                    request_id=getattr(final, "id", None),
                    model=self._model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_read_tokens=cache_read_tokens,
                    cache_creation_tokens=cache_creation_tokens,
                    input_cost=input_cost,
                    output_cost=output_cost,
                    task_label=self._task_label,
                    project=self._project,
                    method="stream",
                    duration_ms=duration_ms,
                )
                await self._db.insert_async(**row)
            except Exception:
                logger.debug("Failed to extract stream usage", exc_info=True)

        return result
