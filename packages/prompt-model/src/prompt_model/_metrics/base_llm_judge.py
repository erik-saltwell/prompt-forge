from abc import ABC, abstractmethod
from typing import Any, ClassVar

from .._llm import acomplete
from ..config import LiteLLMConfig
from .result import MetricResult


class BaseLLMJudgeMetric(ABC):
    """Abstract base for LLM-judge metrics that call a model via LiteLLM.

    Subclasses provide `name` / `description` ClassVars and implement `build_messages` + `parse_result`.
    The base class wires up the LiteLLM call, parses the response, and stamps `metric_name` on the result.
    """

    name: ClassVar[str]
    description: ClassVar[str]

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        self.litellm_config: LiteLLMConfig = litellm_config

    @abstractmethod
    def build_messages(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> list[dict[str, Any]]:
        """Return the LiteLLM `messages` list for this case."""

    @abstractmethod
    def parse_result(self, raw_text: str) -> MetricResult:
        """Parse the LLM's raw text response into a MetricResult. `metric_name` does not need to be set here."""

    async def evaluate(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> MetricResult:
        messages: list[dict[str, Any]] = self.build_messages(prompt, input, output, ground_truth)
        raw: str = await acomplete(self.litellm_config, messages)
        parsed: MetricResult = self.parse_result(raw)
        if parsed.metric_name != self.name:
            return parsed.model_copy(update={"metric_name": self.name})
        return parsed
