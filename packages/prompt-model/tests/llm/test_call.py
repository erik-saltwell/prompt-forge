from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from prompt_model._llm.call import StructuredOutputUnsupportedError, acomplete, complete
from prompt_model.config import LiteLLMConfig
from pydantic import BaseModel


class _Echo(BaseModel):
    text: str
    count: int


def _config() -> LiteLLMConfig:
    return LiteLLMConfig(model="anthropic/claude-sonnet-4-6")


def _mock_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


# --- sync complete ---


def test_complete_returns_string_when_no_response_format() -> None:
    with patch("prompt_model._llm.call.litellm.completion", return_value=_mock_response("hi")) as m:
        out = complete("sys", "usr", _config())
    assert out == "hi"
    assert "response_format" not in dict(m.call_args.kwargs)


def test_complete_returns_parsed_model_when_response_format_passed() -> None:
    payload: str = '{"text": "hello", "count": 3}'
    with (
        patch("prompt_model._llm.call.litellm.supports_response_schema", return_value=True),
        patch("prompt_model._llm.call.litellm.completion", return_value=_mock_response(payload)) as m,
    ):
        out: _Echo = complete("sys", "usr", _config(), response_format=_Echo)
    assert isinstance(out, _Echo)
    assert out.text == "hello"
    assert out.count == 3
    assert m.call_args.kwargs["response_format"] is _Echo


def test_complete_raises_when_model_does_not_support_response_schema() -> None:
    with patch("prompt_model._llm.call.litellm.supports_response_schema", return_value=False):
        with pytest.raises(StructuredOutputUnsupportedError) as exc:
            complete("sys", "usr", _config(), response_format=_Echo)
    assert exc.value.model == "anthropic/claude-sonnet-4-6"


# --- async acomplete (wrapped via asyncio.run to avoid pytest-asyncio dep) ---


def test_acomplete_returns_string_when_no_response_format() -> None:
    mock = AsyncMock(return_value=_mock_response("hi"))
    with patch("prompt_model._llm.call.litellm.acompletion", mock):
        out: str = asyncio.run(acomplete("sys", "usr", _config()))
    assert out == "hi"
    assert "response_format" not in dict(mock.call_args.kwargs)


def test_acomplete_returns_parsed_model_when_response_format_passed() -> None:
    payload: str = '{"text": "world", "count": 7}'
    mock = AsyncMock(return_value=_mock_response(payload))
    with (
        patch("prompt_model._llm.call.litellm.supports_response_schema", return_value=True),
        patch("prompt_model._llm.call.litellm.acompletion", mock),
    ):
        out: _Echo = asyncio.run(acomplete("sys", "usr", _config(), response_format=_Echo))
    assert isinstance(out, _Echo)
    assert out.text == "world"
    assert out.count == 7
    assert mock.call_args.kwargs["response_format"] is _Echo


def test_acomplete_raises_when_model_does_not_support_response_schema() -> None:
    with patch("prompt_model._llm.call.litellm.supports_response_schema", return_value=False):
        with pytest.raises(StructuredOutputUnsupportedError):
            asyncio.run(acomplete("sys", "usr", _config(), response_format=_Echo))
