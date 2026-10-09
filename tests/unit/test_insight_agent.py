from wealth_advisor.agents.insight import InsightAgent, render_template_narrative
from wealth_advisor.graph.state import new_state
from wealth_advisor.llm.base import LLMClient, LLMResponse
from wealth_advisor.llm.cache import LLMCache
from wealth_advisor.llm.mock_client import MockLLMClient


class _FakeLLM(LLMClient):
    model = "fake-llm"

    def __init__(self, text: str) -> None:
        self._text = text

    def generate(self, prompt: str) -> LLMResponse:
        return LLMResponse(text=self._text, input_tokens=5, output_tokens=5, model=self.model)


class _ExplodingLLM(LLMClient):
    model = "exploding-llm"

    def generate(self, prompt: str) -> LLMResponse:
        raise RuntimeError("network error")


def _finding(explanation: str, severity: str = "high") -> dict:
    return {
        "id": "A1",
        "type": "t",
        "severity": severity,
        "evidence": {},
        "explanation": explanation,
        "is_recurring": False,
    }


def test_mock_llm_grounded_output_is_used_as_is() -> None:
    state = new_state(run_id="r", client_id="client_001", thread_id="client_001")
    state["anomalies"] = []
    state["risk_score"] = 0.0

    update = InsightAgent(MockLLMClient(), LLMCache(":memory:")).run(state)

    assert "[MockLLM" in update["insights"]
    assert update["llm_cost"]["fallback_reason"] is None
    assert update["llm_cost"]["model"] == "mock-llm"
    assert update["llm_cost"]["estimated_cost_usd"] == 0.0


def test_second_identical_run_hits_the_cache() -> None:
    cache = LLMCache(":memory:")
    state = new_state(run_id="r", client_id="client_001", thread_id="client_001")
    state["anomalies"] = []
    state["risk_score"] = 0.0

    first = InsightAgent(MockLLMClient(), cache).run(state)
    second = InsightAgent(MockLLMClient(), cache).run(state)

    assert first["llm_cost"]["cached"] is False
    assert second["llm_cost"]["cached"] is True
    assert second["llm_cost"]["estimated_cost_usd"] == 0.0
    assert first["insights"] == second["insights"]


def test_ungrounded_llm_output_falls_back_to_template() -> None:
    state = new_state(run_id="r", client_id="client_001", thread_id="client_001")
    state["anomalies"] = []
    state["risk_score"] = 0.0

    llm = _FakeLLM("This client owes $999,999 in surprise fees!")
    update = InsightAgent(llm, LLMCache(":memory:")).run(state)

    assert update["llm_cost"]["fallback_reason"] == "ungrounded_output"
    assert "No notable anomalies" in update["insights"]  # the template, not the fake text


def test_grounded_llm_output_with_matching_numbers_is_accepted() -> None:
    state = new_state(run_id="r", client_id="client_002", thread_id="client_002")
    state["anomalies"] = [_finding("$45,000.00 moved out in one transaction.")]
    state["risk_score"] = 0.9

    llm = _FakeLLM("A $45,000.00 transfer was flagged for client_002.")
    update = InsightAgent(llm, LLMCache(":memory:")).run(state)

    assert update["llm_cost"]["fallback_reason"] is None
    assert "45,000" in update["insights"]


def test_llm_call_failure_falls_back_to_template() -> None:
    state = new_state(run_id="r", client_id="client_001", thread_id="client_001")
    state["anomalies"] = []
    state["risk_score"] = 0.0

    update = InsightAgent(_ExplodingLLM(), LLMCache(":memory:")).run(state)

    assert update["llm_cost"]["fallback_reason"] == "llm_error"
    assert update["llm_cost"]["tokens"] == 0
    assert update["llm_cost"]["estimated_cost_usd"] == 0.0
    assert "No notable anomalies" in update["insights"]


def test_insight_trace_entry_appended_exactly_once() -> None:
    state = new_state(run_id="r", client_id="client_001", thread_id="client_001")
    state["anomalies"] = []
    state["risk_score"] = 0.0
    state["trace"] = [{"agent": "data_fetcher"}]

    update = InsightAgent(MockLLMClient(), LLMCache(":memory:")).run(state)

    insight_entries = [e for e in update["trace"] if e.get("agent") == "insight"]
    assert len(insight_entries) == 1


def test_render_template_narrative_no_anomalies() -> None:
    assert "No notable anomalies" in render_template_narrative("client_001", [], 0.0)


def test_render_template_narrative_sorts_highest_severity_first() -> None:
    narrative = render_template_narrative(
        "c", [_finding("low one", "low"), _finding("high one", "high")], 0.5
    )
    lines = narrative.splitlines()
    high_idx = next(i for i, line in enumerate(lines) if "high one" in line)
    low_idx = next(i for i, line in enumerate(lines) if "low one" in line)
    assert high_idx < low_idx


def test_render_template_narrative_recommends_review_on_high_severity() -> None:
    narrative = render_template_narrative("c", [_finding("Big transfer out.")], 0.9)
    assert "[HIGH] Big transfer out." in narrative
    assert "Recommended action" in narrative
