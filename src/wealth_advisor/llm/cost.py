from __future__ import annotations

# Illustrative per-million-token USD pricing (input, output). Check the provider's
# current pricing page before relying on this for real budgeting — rates change
# often, which is exactly why the model name is config (see config.py), not code.
_PRICING_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "mock-llm": (0.0, 0.0),
}
_DEFAULT_PRICING = (0.15, 0.60)


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    input_rate, output_rate = _PRICING_PER_MILLION_TOKENS.get(model, _DEFAULT_PRICING)
    cost = (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate
    return round(cost, 6)
