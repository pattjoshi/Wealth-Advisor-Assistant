from __future__ import annotations

from wealth_advisor.llm.base import LLMClient, LLMResponse


class OpenAIClient(LLMClient):
    """Thin adapter over the OpenAI SDK. Retries/timeouts live one layer up (decorators
    around the call site, not here) so this class stays a simple, swappable adapter —
    CLAUDE.md's rule that SDK-level retries are disabled so one layer owns the policy."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_output_tokens: int,
        temperature: float = 0.0,
    ) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, max_retries=0)
        self.model = model
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature

    def generate(self, prompt: str) -> LLMResponse:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self._max_output_tokens,
            temperature=self._temperature,
        )
        choice = response.choices[0]
        usage = response.usage
        return LLMResponse(
            text=choice.message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=self.model,
        )
