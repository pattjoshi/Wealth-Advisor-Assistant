from wealth_advisor.llm.cost import estimate_cost_usd


def test_mock_llm_always_costs_zero() -> None:
    assert estimate_cost_usd("mock-llm", 1_000_000, 1_000_000) == 0.0


def test_known_model_uses_its_own_pricing() -> None:
    cost = estimate_cost_usd("gpt-4o-mini", 1_000_000, 0)
    assert cost == 0.15


def test_output_tokens_priced_separately_from_input() -> None:
    input_only = estimate_cost_usd("gpt-4o-mini", 1_000_000, 0)
    output_only = estimate_cost_usd("gpt-4o-mini", 0, 1_000_000)
    assert input_only != output_only


def test_unknown_model_falls_back_to_default_pricing() -> None:
    cost = estimate_cost_usd("some-future-model", 1_000_000, 0)
    assert cost > 0.0


def test_zero_tokens_costs_zero() -> None:
    assert estimate_cost_usd("gpt-4o-mini", 0, 0) == 0.0
