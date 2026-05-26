import os
from datetime import datetime
from typing import Any, cast, overload

import litellm
from pydantic import BaseModel

from ..config import LiteLLMConfig
from ._concurrency import get_llm_semaphore
from ._ollama_schema import build_ollama_response_format
from ._response_format import HasOllamaVariant


class StructuredOutputUnsupportedError(RuntimeError):
    """Raised when a caller asks for structured output from a model that
    LiteLLM reports does not support a response schema.
    """

    def __init__(self, model: str) -> None:
        super().__init__(f"Model {model!r} does not support structured output via response_format.")
        self.model: str = model


@overload
async def acomplete(system_prompt: str, user_prompt: str, config: LiteLLMConfig, *, log_name: str | None = None) -> str: ...


@overload
async def acomplete[T: BaseModel](
    system_prompt: str,
    user_prompt: str,
    config: LiteLLMConfig,
    *,
    response_format: type[T],
    log_name: str | None = None,
) -> T: ...


async def acomplete[T: BaseModel](
    system_prompt: str,
    user_prompt: str,
    config: LiteLLMConfig,
    *,
    response_format: type[T] | None = None,
    log_name: str | None = None,
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
        _set_response_format(kwargs, response_format)
    async with get_llm_semaphore():
        response: Any = await litellm.acompletion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **kwargs,
        )
    if log_name is not None:
        content = response.choices[0].message.content
        if isinstance(content, str):
            _save_log(log_name, system_prompt, user_prompt, content)
    return _parse_response(response, response_format)


@overload
def complete(system_prompt: str, user_prompt: str, config: LiteLLMConfig, *, log_name: str | None = None) -> str: ...


@overload
def complete[T: BaseModel](
    system_prompt: str,
    user_prompt: str,
    config: LiteLLMConfig,
    *,
    response_format: type[T],
    log_name: str | None = None,
) -> T: ...


def complete[T: BaseModel](
    system_prompt: str,
    user_prompt: str,
    config: LiteLLMConfig,
    *,
    response_format: type[T] | None = None,
    log_name: str | None = None,
) -> str | T:
    """Sync LiteLLM completion. See `acomplete` for behavior and errors."""
    kwargs: dict[str, Any] = config.to_completion_kwargs()
    if response_format is not None:
        _set_response_format(kwargs, response_format)
    response: Any = litellm.completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        **kwargs,
    )
    if log_name is not None:
        content = response.choices[0].message.content
        if isinstance(content, str):
            _save_log(log_name, system_prompt, user_prompt, content)
    return _parse_response(response, response_format)


def _save_log(log_name: str, system_prompt: str, user_prompt: str, output: str) -> None:
    logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    file_path = os.path.join(logs_dir, f"{log_name}_{timestamp}.log")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"SYSTEM PROMPT:\n{system_prompt}\n")
        f.write("-" * 40 + "\n")
        f.write(f"USER PROMPT:\n{user_prompt}\n")
        f.write("-" * 40 + "\n")
        f.write(f"OUTPUT:\n{output}\n")


def _is_ollama(model: str) -> bool:
    return model.startswith("ollama_chat/") or model.startswith("ollama/")


def _strip_patterns(obj: object) -> object:
    """Recursively remove ``"pattern"`` keywords from a JSON Schema dict.

    Anthropic's structured-output validator rejects regex pattern constraints
    (e.g. the ``\\S`` shorthand used by ``NonBlankStr``).  Stripping them from
    the *wire* schema is safe because ``_parse_response`` still calls
    ``model_validate_json`` with the full Pydantic model, which enforces every
    constraint on the returned value.
    """
    if isinstance(obj, dict):
        return {k: _strip_patterns(v) for k, v in cast(dict[str, object], obj).items() if k != "pattern"}
    if isinstance(obj, list):
        return [_strip_patterns(v) for v in cast(list[object], obj)]
    return obj


def _set_response_format(kwargs: dict[str, Any], response_format: type[BaseModel]) -> None:
    model: str = kwargs["model"]
    if _is_ollama(model):
        # Ollama's schema validator rejects discriminated unions. If the class declares
        # a hand-tuned Ollama variant via `__ollama_response_format__`, use it for the
        # wire schema; otherwise auto-flatten as a fallback. The response is still
        # parsed against the original strict class in `_parse_response`.
        wire_cls: type[BaseModel] = (
            response_format.__ollama_response_format__() if isinstance(response_format, HasOllamaVariant) else response_format
        )
        kwargs["response_format"] = build_ollama_response_format(wire_cls)
        return
    if not litellm.supports_response_schema(model=model):
        raise StructuredOutputUnsupportedError(model)
    # Strip regex ``pattern`` constraints before sending to the provider.
    # Anthropic rejects patterns like ``\S`` that use Perl-style shorthands
    # unsupported by their JSON Schema validator.  Python-side validation via
    # ``model_validate_json`` in ``_parse_response`` still enforces them.
    raw_schema: dict[str, object] = cast(dict[str, object], _strip_patterns(response_format.model_json_schema()))
    kwargs["response_format"] = {
        "type": "json_schema",
        "json_schema": {"name": response_format.__name__, "schema": raw_schema},
    }


def _parse_response[T: BaseModel](response: Any, response_format: type[T] | None) -> str | T:
    content: Any = response.choices[0].message.content
    if not isinstance(content, str):
        raise ValueError(f"LiteLLM response content is not a string: {type(content).__name__}")
    if response_format is None:
        return content
    return response_format.model_validate_json(content)
