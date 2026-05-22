from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .._utils import pydantic_aliases as py_types

type EffortLevel = Literal["low", "medium", "high"]


class LiteLLMConfig(BaseModel):
    """Shared LiteLLM call configuration used by the batch-testing target call and by LLM-judge metrics.

    Typed fields surface the common knobs. Anything else is passed through via `extra`.
    """

    model_config = ConfigDict(extra="forbid")

    model: py_types.NonBlankStr = Field(
        description="LiteLLM model identifier, e.g. 'anthropic/claude-opus-4-7' or 'openai/gpt-4o'.",
    )
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    timeout: float | None = Field(default=None, gt=0.0)
    effort: EffortLevel | None = Field(
        default=None,
        description="Reasoning effort. Mapped to LiteLLM's `reasoning_effort` kwarg.",
    )
    api_base: str | None = None
    api_key: str | None = None
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Pass-through bag for any LiteLLM completion kwarg not surfaced as a typed field.",
    )

    def to_completion_kwargs(self) -> dict[str, Any]:
        """Flatten this config into the kwargs LiteLLM's `acompletion` accepts."""
        kwargs: dict[str, Any] = {"model": self.model}
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens
        if self.timeout is not None:
            kwargs["timeout"] = self.timeout
        if self.effort is not None:
            kwargs["reasoning_effort"] = self.effort
        if self.api_base is not None:
            kwargs["api_base"] = self.api_base
        if self.api_key is not None:
            kwargs["api_key"] = self.api_key
        for key, value in self.extra.items():
            kwargs[key] = value
        return kwargs
