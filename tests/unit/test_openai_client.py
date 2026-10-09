from types import SimpleNamespace

from wealth_advisor.llm.openai_client import OpenAIClient


def _fake_response(text: str, prompt_tokens: int, completion_tokens: int) -> SimpleNamespace:
    message = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return SimpleNamespace(choices=[choice], usage=usage)


def test_generate_extracts_text_and_token_counts(monkeypatch) -> None:
    client = OpenAIClient(
        api_key="fake-key", model="gpt-4o-mini", max_output_tokens=400, temperature=0.0
    )

    def fake_create(**kwargs):
        assert kwargs["model"] == "gpt-4o-mini"
        assert kwargs["temperature"] == 0.0
        assert kwargs["max_tokens"] == 400
        return _fake_response("hello from the model", prompt_tokens=10, completion_tokens=5)

    monkeypatch.setattr(client._client.chat.completions, "create", fake_create)

    response = client.generate("a prompt")

    assert response.text == "hello from the model"
    assert response.input_tokens == 10
    assert response.output_tokens == 5
    assert response.model == "gpt-4o-mini"


def test_generate_handles_empty_content(monkeypatch) -> None:
    client = OpenAIClient(api_key="fake-key", model="gpt-4o-mini", max_output_tokens=400)

    monkeypatch.setattr(
        client._client.chat.completions,
        "create",
        lambda **_: _fake_response(None, prompt_tokens=1, completion_tokens=0),
    )

    response = client.generate("a prompt")
    assert response.text == ""
