from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Protocol, runtime_checkable

from .._llm import acomplete
from .._prompt import parse_from_string
from ..config import LiteLLMConfig
from .result import MetricResult

if TYPE_CHECKING:
    from .._prompt import Document


@runtime_checkable
class RenderPromptStrategy(Protocol):
    """Renders a Document as the string the judge LLM reads.

    Mirrors the protocol in `_actor._render_prompt_strategy`; redefined here to
    avoid a circular import through `_actor.__init__` → `revise` → `_candidate` → `_metrics`.
    The two protocols are structurally compatible — any `_actor` render strategy satisfies both.
    """

    def render(self, tree: Document, focus_ids: set[str] | None) -> str: ...


class BaseLLMJudgeMetric(ABC):
    """Abstract base for LLM-judge metrics that issue a single structured call per case.

    The base class:
    - Parses the prompt string and renders it via the injected `RenderPromptStrategy`
      (default: `MarkdownRenderPromptStrategy`, which adds `<!-- id -->` comment overlays
      so the judge LLM can cite culprit node IDs in `IssueSignal.culprit_node_id`).
    - Calls `acomplete` with `response_format=MetricResult` — no raw text parsing.
    - Stamps `metric_name` on the returned result.

    Subclasses must implement `build_system_prompt()`.
    Subclasses may override `build_user_prompt()` for custom layouts.
    """

    name: ClassVar[str]
    description: ClassVar[str]

    def __init__(
        self,
        litellm_config: LiteLLMConfig,
        render_strategy: RenderPromptStrategy | None = None,
    ) -> None:
        self.litellm_config: LiteLLMConfig = litellm_config
        if render_strategy is None:
            # Lazy import to avoid circular: _metrics → _actor.__init__ → revise → _candidate → _metrics
            from .._actor._render_prompt_strategy import MarkdownRenderPromptStrategy

            render_strategy = MarkdownRenderPromptStrategy()
        self.render_strategy: RenderPromptStrategy = render_strategy

    @abstractmethod
    def build_system_prompt(self) -> str:
        """Return the system prompt the judge LLM will see."""

    def build_user_prompt(
        self,
        rendered_prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> str:
        """Return the user message the judge LLM sees.

        Default layout: `<prompt>`, `<input>`, `<output>`, and optionally `<ground_truth>` blocks.
        Override for custom layouts.
        """
        gt_block: str = f"\n\n<ground_truth>\n{ground_truth}\n</ground_truth>" if ground_truth is not None else ""
        return f"<prompt>\n{rendered_prompt}\n</prompt>\n\n<input>\n{input}\n</input>\n\n<output>\n{output}\n</output>{gt_block}"

    async def evaluate(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> MetricResult:
        document = parse_from_string(prompt)
        rendered: str = self.render_strategy.render(document, focus_ids=None)
        system: str = self.build_system_prompt()
        user: str = self.build_user_prompt(rendered, input, output, ground_truth)
        result: MetricResult = await acomplete(
            system_prompt=system,
            user_prompt=user,
            config=self.litellm_config,
            response_format=MetricResult,
            log_name=self.name,
        )
        if result.metric_name != self.name:
            return result.model_copy(update={"metric_name": self.name})
        return result
