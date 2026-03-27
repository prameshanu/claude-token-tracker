from __future__ import annotations

# Prices per million tokens (USD) — update as Anthropic changes pricing
DEFAULT_PRICING: dict[str, dict[str, float]] = {
    # Claude 4 / 4.5 / 4.6 family
    "claude-opus-4-20250514": {"input_per_mtok": 15.00, "output_per_mtok": 75.00},
    "claude-opus-4-6-20250626": {"input_per_mtok": 15.00, "output_per_mtok": 75.00},
    "claude-sonnet-4-20250514": {"input_per_mtok": 3.00, "output_per_mtok": 15.00},
    "claude-sonnet-4-6-20250626": {"input_per_mtok": 3.00, "output_per_mtok": 15.00},
    "claude-haiku-4-20250414": {"input_per_mtok": 0.80, "output_per_mtok": 4.00},
    "claude-haiku-4-5-20251001": {"input_per_mtok": 1.00, "output_per_mtok": 5.00},
    # Claude 3.5 family
    "claude-3-5-sonnet-20241022": {"input_per_mtok": 3.00, "output_per_mtok": 15.00},
    "claude-3-5-haiku-20241022": {"input_per_mtok": 0.80, "output_per_mtok": 4.00},
    # Claude 3 family
    "claude-3-opus-20240229": {"input_per_mtok": 15.00, "output_per_mtok": 75.00},
    "claude-3-sonnet-20240229": {"input_per_mtok": 3.00, "output_per_mtok": 15.00},
    "claude-3-haiku-20240307": {"input_per_mtok": 0.25, "output_per_mtok": 1.25},
}


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    overrides: dict[str, dict[str, float]] | None = None,
) -> tuple[float, float]:
    """Calculate input and output cost in USD.

    Returns (input_cost, output_cost). Returns (0.0, 0.0) for unknown models.
    """
    pricing = (overrides or {}).get(model) or DEFAULT_PRICING.get(model)
    if not pricing:
        return 0.0, 0.0
    input_cost = (input_tokens / 1_000_000) * pricing["input_per_mtok"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_mtok"]
    return round(input_cost, 6), round(output_cost, 6)
