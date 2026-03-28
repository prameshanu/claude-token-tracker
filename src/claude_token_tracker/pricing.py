from __future__ import annotations

import json
import logging
import os
import re
import smtplib
import threading
import time
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.request import urlopen, Request
from urllib.error import URLError

if TYPE_CHECKING:
    from claude_token_tracker.config import TrackerConfig

logger = logging.getLogger("claude_token_tracker")

# ── Hardcoded fallback (used when remote fetch fails and no cache exists) ──

HARDCODED_PRICING: dict[str, dict[str, float]] = {
    # Opus 4.6
    "claude-opus-4-6-20250626": {"input_per_mtok": 5.00, "output_per_mtok": 25.00, "cache_write_per_mtok": 6.25, "cache_read_per_mtok": 0.50},
    # Sonnet 4.6
    "claude-sonnet-4-6-20250626": {"input_per_mtok": 3.00, "output_per_mtok": 15.00, "cache_write_per_mtok": 3.75, "cache_read_per_mtok": 0.30},
    # Haiku 4.5
    "claude-haiku-4-5-20251001": {"input_per_mtok": 1.00, "output_per_mtok": 5.00, "cache_write_per_mtok": 1.25, "cache_read_per_mtok": 0.10},
    # Sonnet 4.5
    "claude-sonnet-4-5-20250514": {"input_per_mtok": 3.00, "output_per_mtok": 15.00, "cache_write_per_mtok": 3.75, "cache_read_per_mtok": 0.30},
    # Opus 4.5
    "claude-opus-4-5-20250514": {"input_per_mtok": 5.00, "output_per_mtok": 25.00, "cache_write_per_mtok": 6.25, "cache_read_per_mtok": 0.50},
    # Opus 4.1
    "claude-opus-4-1-20250414": {"input_per_mtok": 15.00, "output_per_mtok": 75.00, "cache_write_per_mtok": 18.75, "cache_read_per_mtok": 1.50},
    # Sonnet 4
    "claude-sonnet-4-20250514": {"input_per_mtok": 3.00, "output_per_mtok": 15.00, "cache_write_per_mtok": 3.75, "cache_read_per_mtok": 0.30},
    # Opus 4
    "claude-opus-4-20250514": {"input_per_mtok": 15.00, "output_per_mtok": 75.00, "cache_write_per_mtok": 18.75, "cache_read_per_mtok": 1.50},
    # Haiku 4
    "claude-haiku-4-20250414": {"input_per_mtok": 1.00, "output_per_mtok": 5.00, "cache_write_per_mtok": 1.25, "cache_read_per_mtok": 0.10},
    # Claude 3.5 family
    "claude-3-5-sonnet-20241022": {"input_per_mtok": 3.00, "output_per_mtok": 15.00, "cache_write_per_mtok": 3.75, "cache_read_per_mtok": 0.30},
    "claude-3-5-haiku-20241022": {"input_per_mtok": 0.80, "output_per_mtok": 4.00, "cache_write_per_mtok": 1.00, "cache_read_per_mtok": 0.08},
    # Claude 3 family
    "claude-3-opus-20240229": {"input_per_mtok": 15.00, "output_per_mtok": 75.00, "cache_write_per_mtok": 18.75, "cache_read_per_mtok": 1.50},
    "claude-3-sonnet-20240229": {"input_per_mtok": 3.00, "output_per_mtok": 15.00, "cache_write_per_mtok": 3.75, "cache_read_per_mtok": 0.30},
    "claude-3-haiku-20240307": {"input_per_mtok": 0.25, "output_per_mtok": 1.25, "cache_write_per_mtok": 0.30, "cache_read_per_mtok": 0.03},
}

# Backward compat alias
DEFAULT_PRICING = HARDCODED_PRICING

# ── Module-level cache ──
_pricing_cache: dict[str, dict[str, float]] | None = None
_cache_lock = threading.Lock()


def _send_alert_email(config: TrackerConfig, error_msg: str) -> None:
    """Send email alert when pricing fetch fails."""
    if not config.alert_email or not config.smtp_user or not config.smtp_password:
        logger.debug("Email alert skipped — SMTP not configured")
        return

    try:
        subject = "claude-token-tracker: Pricing fetch failed"
        body = (
            f"The claude-token-tracker package failed to refresh pricing data.\n\n"
            f"Error: {error_msg}\n\n"
            f"Pricing URL: {config.pricing_url}\n"
            f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n\n"
            f"The package will continue using cached/hardcoded pricing until this is resolved.\n"
            f"Please update pricing.json in the repository."
        )

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = config.smtp_user
        msg["To"] = config.alert_email

        with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
            server.starttls()
            server.login(config.smtp_user, config.smtp_password)
            server.sendmail(config.smtp_user, [config.alert_email], msg.as_string())

        logger.info("Alert email sent to %s", config.alert_email)
    except Exception:
        logger.debug("Failed to send alert email", exc_info=True)


def _send_new_model_alert(
    config: TrackerConfig,
    new_models: list[str],
    scraped_hints: dict[str, dict[str, float]] | None = None,
) -> None:
    """Send email alert when new models are discovered.

    Includes unverified scraped pricing hints so the user can quickly
    verify and update pricing.json.
    """
    if not config.alert_email or not config.smtp_user or not config.smtp_password:
        logger.debug("New model alert skipped — SMTP not configured")
        return

    try:
        scraped_hints = scraped_hints or {}

        # Build model details
        model_lines = []
        for m in new_models:
            if m in scraped_hints:
                h = scraped_hints[m]
                model_lines.append(
                    f"  - {m}\n"
                    f"    Scraped (UNVERIFIED): input=${h['input_per_mtok']}/MTok, "
                    f"output=${h['output_per_mtok']}/MTok"
                )
            else:
                model_lines.append(f"  - {m}\n    Scraping failed — no pricing found")
        model_details = "\n".join(model_lines)

        # Build ready-to-paste JSON snippet
        json_snippet_entries = {}
        for m in new_models:
            if m in scraped_hints:
                json_snippet_entries[m] = scraped_hints[m]
            else:
                json_snippet_entries[m] = {"input_per_mtok": 0.00, "output_per_mtok": 0.00}
        json_snippet = json.dumps(json_snippet_entries, indent=4)

        subject = "claude-token-tracker: New Claude models detected — pricing update needed"
        body = (
            f"New Claude models were discovered via the Anthropic Models API.\n"
            f"Scraping was attempted but results need manual verification.\n\n"
            f"Models found:\n{model_details}\n\n"
            f"---\n"
            f"Ready-to-paste JSON for pricing.json (VERIFY BEFORE USING):\n\n"
            f"{json_snippet}\n\n"
            f"---\n"
            f"Steps:\n"
            f"1. Verify pricing at https://docs.anthropic.com/en/docs/about-claude/models\n"
            f"2. Update pricing.json in the repo: {config.pricing_url}\n"
            f"3. Commit & push — all users will pick it up within 7 days\n\n"
            f"Timestamp: {datetime.now(timezone.utc).isoformat()}"
        )

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = config.smtp_user
        msg["To"] = config.alert_email

        with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
            server.starttls()
            server.login(config.smtp_user, config.smtp_password)
            server.sendmail(config.smtp_user, [config.alert_email], msg.as_string())

        logger.info("New model alert sent to %s for models: %s", config.alert_email, new_models)
    except Exception:
        logger.debug("Failed to send new model alert email", exc_info=True)


def _discover_models_from_api(api_key: str, timeout: int = 10) -> list[str]:
    """Fetch available model IDs from the Anthropic Models API."""
    req = Request(
        "https://api.anthropic.com/v1/models",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "User-Agent": "claude-token-tracker",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    return [m["id"] for m in data.get("data", [])]


ANTHROPIC_PRICING_URLS = [
    "https://docs.anthropic.com/en/docs/about-claude/models",
    "https://www.anthropic.com/pricing",
]


def _scrape_pricing_for_model(model_id: str, timeout: int = 10) -> dict[str, float] | None:
    """Attempt to scrape pricing from Anthropic's website for a specific model.

    Tries multiple pages and looks for pricing patterns near the model name.
    Returns {"input_per_mtok": X, "output_per_mtok": Y} or None if not found.
    """
    # Extract base model name for matching (e.g., "claude-sonnet-4" from "claude-sonnet-4-20250514")
    # Also try the full model ID
    search_terms = [model_id]
    # Strip date suffix for broader matching
    base = re.sub(r"-\d{8}$", "", model_id)
    if base != model_id:
        search_terms.append(base)

    for url in ANTHROPIC_PRICING_URLS:
        try:
            req = Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; claude-token-tracker/0.1)",
            })
            with urlopen(req, timeout=timeout) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            for term in search_terms:
                # Look for pricing patterns near the model name
                # Common patterns: "$3.00", "$15.00 / MTok", "$3 / million"
                escaped = re.escape(term)
                # Search in a window of ~500 chars around the model name
                for match in re.finditer(escaped, html, re.IGNORECASE):
                    start = max(0, match.start() - 200)
                    end = min(len(html), match.end() + 500)
                    context = html[start:end]

                    # Look for dollar amounts — pattern: $X.XX
                    prices = re.findall(r"\$(\d+(?:\.\d{1,2})?)", context)
                    if len(prices) >= 2:
                        # Typically: input price first, output price second
                        input_price = float(prices[0])
                        output_price = float(prices[1])
                        # Sanity check: output is usually more expensive than input
                        if 0 < input_price <= 100 and 0 < output_price <= 500:
                            logger.info(
                                "Scraped pricing for %s: input=$%.2f/MTok, output=$%.2f/MTok",
                                model_id, input_price, output_price,
                            )
                            return {
                                "input_per_mtok": input_price,
                                "output_per_mtok": output_price,
                            }
        except Exception:
            logger.debug("Failed to scrape %s for pricing", url, exc_info=True)
            continue

    return None


def _scrape_pricing_for_models(
    model_ids: list[str], timeout: int = 10
) -> dict[str, dict[str, float]]:
    """Try to scrape pricing for multiple models. Returns found pricing only."""
    found: dict[str, dict[str, float]] = {}
    for model_id in model_ids:
        pricing = _scrape_pricing_for_model(model_id, timeout)
        if pricing:
            found[model_id] = pricing
    return found


def _fetch_remote_pricing(url: str, timeout: int = 10) -> dict[str, dict[str, float]]:
    """Fetch pricing.json from the remote URL."""
    req = Request(url, headers={"User-Agent": "claude-token-tracker"})
    with urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    return data["models"]


def _read_cache(cache_path: str) -> tuple[dict[str, dict[str, float]] | None, float]:
    """Read cached pricing. Returns (pricing_dict, cache_age_days)."""
    path = Path(os.path.expanduser(cache_path))
    if not path.exists():
        return None, float("inf")

    try:
        data = json.loads(path.read_text())
        cached_at = data.get("cached_at", 0)
        age_days = (time.time() - cached_at) / 86400
        return data.get("models"), age_days
    except Exception:
        return None, float("inf")


def _write_cache(cache_path: str, models: dict[str, dict[str, float]]) -> None:
    """Write pricing to local cache file."""
    path = Path(os.path.expanduser(cache_path))
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "cached_at": time.time(),
        "cached_date": datetime.now(timezone.utc).isoformat(),
        "models": models,
    }
    path.write_text(json.dumps(data, indent=2))


def get_pricing(config: TrackerConfig | None = None) -> dict[str, dict[str, float]]:
    """Get the current pricing dictionary.

    Priority:
        1. config.pricing_overrides (highest — per-user overrides)
        2. Remote pricing.json (fetched every N days, cached locally)
        3. Local cache (if remote fetch fails)
        4. Hardcoded defaults (last resort)

    This function is thread-safe and caches in memory after first load.
    """
    global _pricing_cache

    if _pricing_cache is not None:
        return _pricing_cache

    with _cache_lock:
        if _pricing_cache is not None:
            return _pricing_cache

        if config is None:
            from claude_token_tracker.config import TrackerConfig
            config = TrackerConfig.from_env()

        cache_path = config.pricing_cache_path
        refresh_days = config.pricing_refresh_days

        # Check local cache first
        cached_models, age_days = _read_cache(cache_path)

        if cached_models and age_days < refresh_days:
            # Cache is fresh
            _pricing_cache = cached_models
            return _pricing_cache

        # Cache is stale or missing — try remote fetch
        try:
            remote_models = _fetch_remote_pricing(config.pricing_url)
            _write_cache(cache_path, remote_models)
            _pricing_cache = remote_models
            logger.info("Pricing refreshed from %s", config.pricing_url)
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            logger.warning("Failed to fetch remote pricing: %s", error_msg)

            # Send email alert in background
            threading.Thread(
                target=_send_alert_email,
                args=(config, error_msg),
                daemon=True,
            ).start()

            # Fall back to stale cache if available
            if cached_models:
                logger.info("Using stale cached pricing (%.1f days old)", age_days)
                _pricing_cache = cached_models
            else:
                # Last resort: hardcoded
                logger.info("Using hardcoded pricing as fallback")
                _pricing_cache = HARDCODED_PRICING.copy()

        # ── Model auto-discovery via Anthropic API ──
        if config.auto_discover_models and config.anthropic_api_key:
            try:
                api_models = _discover_models_from_api(config.anthropic_api_key)
                new_models = [m for m in api_models if m not in _pricing_cache]
                if new_models:
                    logger.info("New models discovered: %s", new_models)

                    # Scrape as hints only — never auto-applied
                    scraped_hints = _scrape_pricing_for_models(new_models)
                    if scraped_hints:
                        logger.info("Scraped hints (unverified): %s", scraped_hints)

                    # Email with scraped hints for manual verification
                    logger.info("Sending email with new models + scraped hints for verification")
                    threading.Thread(
                        target=_send_new_model_alert,
                        args=(config, new_models, scraped_hints),
                        daemon=True,
                    ).start()
            except Exception:
                logger.debug("Model auto-discovery failed", exc_info=True)

        return _pricing_cache


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
    overrides: dict[str, dict[str, float]] | None = None,
    config: TrackerConfig | None = None,
) -> tuple[float, float]:
    """Calculate input and output cost in USD.

    Input cost includes: regular input tokens + cache write + cache read.
    Output cost is based on output tokens only.

    Priority: overrides > remote/cached pricing > hardcoded defaults.
    Returns (input_cost, output_cost). Returns (0.0, 0.0) for unknown models.
    """
    # User overrides take highest priority
    if overrides and model in overrides:
        pricing = overrides[model]
    else:
        all_pricing = get_pricing(config)
        pricing = all_pricing.get(model)

    if not pricing:
        return 0.0, 0.0

    # Regular input/output
    input_cost = (input_tokens / 1_000_000) * pricing["input_per_mtok"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_mtok"]

    # Prompt caching costs (added to input cost)
    if cache_creation_tokens and "cache_write_per_mtok" in pricing:
        input_cost += (cache_creation_tokens / 1_000_000) * pricing["cache_write_per_mtok"]
    if cache_read_tokens and "cache_read_per_mtok" in pricing:
        input_cost += (cache_read_tokens / 1_000_000) * pricing["cache_read_per_mtok"]

    return round(input_cost, 6), round(output_cost, 6)
