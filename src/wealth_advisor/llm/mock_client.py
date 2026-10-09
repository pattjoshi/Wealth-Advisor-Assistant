from __future__ import annotations

from wealth_advisor.llm.base import LLMClient, LLMResponse
from wealth_advisor.llm.prompts import CLOSING_MARKER, FINDINGS_MARKER


class MockLLMClient(LLMClient):
    """Deterministic, offline, zero-cost. Used automatically when no OPENAI_API_KEY is
    set, and always in tests/CI so the suite never needs network or a real key. It
    doesn't paraphrase — it echoes the findings block already in the prompt, which
    means its output is grounded by construction: it can't contain a number that
    wasn't already in the (real, Analyzer-produced) findings."""

    model = "mock-llm"

    def generate(self, prompt: str) -> LLMResponse:
        text = _echo_findings(prompt)
        return LLMResponse(
            text=text,
            input_tokens=len(prompt.split()),
            output_tokens=len(text.split()),
            model=self.model,
        )


def _echo_findings(prompt: str) -> str:
    if FINDINGS_MARKER not in prompt:
        return "[MockLLM — no API key set] No findings summary was provided."
    block = prompt.split(FINDINGS_MARKER, 1)[1]
    if CLOSING_MARKER in block:
        block = block.split(CLOSING_MARKER, 1)[0]
    return f"[MockLLM — no API key set]\n{block}"
