from typing import Any

import litellm

from ..config import LiteLLMConfig


async def acomplete(system_prompt: str, user_prompt: str, config: LiteLLMConfig) -> str:
    """Async LiteLLM completion. Returns the assistant text content of the first choice.

    Raises on hard failure; callers decide how to handle.
    """
    kwargs: dict[str, Any] = config.to_completion_kwargs()
    response: Any = await litellm.acompletion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        **kwargs,
    )
    content: Any = response.choices[0].message.content
    if not isinstance(content, str):
        raise ValueError(f"LiteLLM response content is not a string: {type(content).__name__}")
    return content


def complete(system_prompt: str, user_prompt: str, config: LiteLLMConfig) -> str:
    """Async LiteLLM completion. Returns the assistant text content of the first choice.

    Raises on hard failure; callers decide how to handle.
    """
    kwargs: dict[str, Any] = config.to_completion_kwargs()
    response: Any = litellm.completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        **kwargs,
    )
    content: Any = response.choices[0].message.content
    if not isinstance(content, str):
        raise ValueError(f"LiteLLM response content is not a string: {type(content).__name__}")
    return content
