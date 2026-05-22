from typing import Any

import litellm

from .config import LiteLLMConfig


async def acomplete(config: LiteLLMConfig, messages: list[dict[str, Any]]) -> str:
    """Async LiteLLM completion. Returns the assistant text content of the first choice.

    Raises on hard failure; callers decide how to handle.
    """
    kwargs: dict[str, Any] = config.to_completion_kwargs()
    response: Any = await litellm.acompletion(messages=messages, **kwargs)
    content: Any = response.choices[0].message.content
    if not isinstance(content, str):
        raise ValueError(f"LiteLLM response content is not a string: {type(content).__name__}")
    return content
