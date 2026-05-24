from typing import Any, overload

import litellm
from pydantic import BaseModel

from ..config import LiteLLMConfig


class StructuredOutputUnsupportedError(RuntimeError):
    """Raised when a caller asks for structured output from a model that
    LiteLLM reports does not support a response schema.
    """

    def __init__(self, model: str) -> None:
        super().__init__(f"Model {model!r} does not support structured output via response_format.")
        self.model: str = model


@overload
async def acomplete(system_prompt: str, user_prompt: str, config: LiteLLMConfig) -> str: ...


@overload
async def acomplete[T: BaseModel](
    system_prompt: str,
    user_prompt: str,
    config: LiteLLMConfig,
    *,
    response_format: type[T],
) -> T: ...


async def acomplete[T: BaseModel](
    system_prompt: str,
    user_prompt: str,
    config: LiteLLMConfig,
    *,
    response_format: type[T] | None = None,
) -> str | T:
    """Async LiteLLM completion.

    When `response_format` is omitted, returns the assistant's text content.
    When provided (a Pydantic `BaseModel` subclass), uses the provider's
    constrained generation and returns a parsed instance of that model.

    Raises `StructuredOutputUnsupportedError` if `response_format` is requested
    for a model LiteLLM reports does not support response schemas. Raises on
    any transport or parsing failure.
    """
    kwargs: dict[str, Any] = config.to_completion_kwargs()
    if response_format is not None:
        _ensure_structured_output_supported(kwargs["model"])
        kwargs["response_format"] = response_format
    response: Any = await litellm.acompletion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        **kwargs,
    )
    return _parse_response(response, response_format)


@overload
def complete(system_prompt: str, user_prompt: str, config: LiteLLMConfig) -> str: ...


@overload
def complete[T: BaseModel](
    system_prompt: str,
    user_prompt: str,
    config: LiteLLMConfig,
    *,
    response_format: type[T],
) -> T: ...


def complete[T: BaseModel](
    system_prompt: str,
    user_prompt: str,
    config: LiteLLMConfig,
    *,
    response_format: type[T] | None = None,
) -> str | T:
    """Sync LiteLLM completion. See `acomplete` for behavior and errors."""
    kwargs: dict[str, Any] = config.to_completion_kwargs()
    if response_format is not None:
        _ensure_structured_output_supported(kwargs["model"])
        kwargs["response_format"] = response_format
    response: Any = litellm.completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        **kwargs,
    )
    return _parse_response(response, response_format)


def _ensure_structured_output_supported(model: str) -> None:
    if not litellm.supports_response_schema(model=model):
        raise StructuredOutputUnsupportedError(model)


def _parse_response[T: BaseModel](response: Any, response_format: type[T] | None) -> str | T:
    content: Any = response.choices[0].message.content
    if not isinstance(content, str):
        raise ValueError(f"LiteLLM response content is not a string: {type(content).__name__}")
    if response_format is None:
        return content
    return response_format.model_validate_json(content)
