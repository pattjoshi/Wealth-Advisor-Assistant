from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMClient(ABC):
    """Every model call in the system goes through this interface (Strategy pattern) —
    OpenAI and Mock are interchangeable, and nothing above this layer knows which one
    it's talking to."""

    model: str

    @abstractmethod
    def generate(self, prompt: str) -> LLMResponse:
        """Generate text for a prompt. May raise on a real API/network error — the
        caller (InsightAgent) decides what to do about it (falls back to the
        template)."""
