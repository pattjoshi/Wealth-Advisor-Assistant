from wealth_advisor.llm.mock_client import MockLLMClient
from wealth_advisor.llm.prompts import build_insight_prompt


def test_mock_client_echoes_the_findings_block() -> None:
    prompt = build_insight_prompt(
        [
            {
                "id": "A1",
                "type": "large_transfer",
                "severity": "high",
                "evidence": {},
                "explanation": "$45,000.00 moved out.",
                "is_recurring": False,
            }
        ],
        0.9,
    )
    response = MockLLMClient().generate(prompt)

    assert "[MockLLM" in response.text
    assert "$45,000.00 moved out." in response.text
    assert "Write the narrative now" not in response.text  # closing marker stripped
    assert response.model == "mock-llm"


def test_mock_client_handles_prompt_without_marker_gracefully() -> None:
    response = MockLLMClient().generate("a prompt with no findings marker")
    assert "No findings summary" in response.text


def test_mock_client_token_counts_are_word_based_and_nonzero() -> None:
    response = MockLLMClient().generate(build_insight_prompt([], 0.0))
    assert response.input_tokens > 0
    assert response.output_tokens > 0


def test_prompt_never_contains_a_client_identifier() -> None:
    """Regression test: the prompt (and therefore the cached narrative) must never
    embed a client's identity, since the LLM cache is keyed by findings only — two
    different clients with identical findings share a cache entry on purpose, and a
    client-specific string in the cached text would leak one client's identity into
    another client's report."""
    prompt = build_insight_prompt([], 0.0)
    assert "Client:" not in prompt
    assert "client_00" not in prompt
