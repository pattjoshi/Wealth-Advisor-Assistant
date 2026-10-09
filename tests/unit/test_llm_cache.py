from wealth_advisor.llm.base import LLMResponse
from wealth_advisor.llm.cache import LLMCache


def test_miss_then_hit_round_trip() -> None:
    cache = LLMCache(":memory:")
    key = LLMCache.make_key("mock-llm", {"anomalies": [], "risk_score": 0.0})

    assert cache.get(key) is None

    response = LLMResponse(text="hello", input_tokens=5, output_tokens=5, model="mock-llm")
    cache.set(key, response)

    cached = cache.get(key)
    assert cached is not None
    assert cached.text == "hello"
    assert cached.model == "mock-llm"


def test_make_key_is_stable_for_same_input() -> None:
    payload = {"anomalies": [{"id": "A1"}], "risk_score": 0.5}
    assert LLMCache.make_key("mock-llm", payload) == LLMCache.make_key("mock-llm", payload)


def test_make_key_differs_for_different_model() -> None:
    payload = {"anomalies": [], "risk_score": 0.0}
    assert LLMCache.make_key("mock-llm", payload) != LLMCache.make_key("gpt-4o-mini", payload)


def test_make_key_differs_for_different_findings() -> None:
    assert LLMCache.make_key("mock-llm", {"anomalies": [], "risk_score": 0.0}) != LLMCache.make_key(
        "mock-llm", {"anomalies": [{"id": "A1"}], "risk_score": 0.0}
    )


def test_set_overwrites_existing_key() -> None:
    cache = LLMCache(":memory:")
    key = "same-key"
    cache.set(key, LLMResponse(text="first", input_tokens=1, output_tokens=1, model="m"))
    cache.set(key, LLMResponse(text="second", input_tokens=2, output_tokens=2, model="m"))

    assert cache.get(key).text == "second"
