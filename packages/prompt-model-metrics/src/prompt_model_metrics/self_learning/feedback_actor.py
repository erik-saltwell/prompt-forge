"""Evaluation metrics for the feedback-actor prompt.

Eight metrics across two tiers:

Structural gates (deterministic + optional judge):
  1. JsonCorrectnessMetric  — reused from prompt_model_metrics.base
  2. IdValidityMetric       — every id/host_id/target in the batch exists in the input tree
  3. HostTypeCorrectnessMetric — add_example/add_guidance host_ids are Paragraph or ListItem

Semantic metrics (LLM judge against per-scenario criteria from ground_truth):
  4. IssueTraceabilityMetric  — each action maps to a cited feedback issue
  5. ActionTypeFitnessMetric  — action type matches the nature of the issue
  6. ActorCoverageMetric      — all significant issues produced at least one action
  7. PreserveComplianceMetric — no action breaks a preserve item
  8. SpeculativeEditAbsenceMetric — no unmotivated actions
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from abc import abstractmethod
from typing import Any, ClassVar, cast

from prompt_model import BaseLLMJudgeMetric, HybridMetric, Metric
from prompt_model.config import LiteLLMConfig

from prompt_model_metrics.base import JsonCorrectnessMetric

__all__ = [
    "JsonCorrectnessMetric",
    "IdValidityMetric",
    "HostTypeCorrectnessMetric",
    "IssueTraceabilityMetric",
    "ActionTypeFitnessMetric",
    "ActorCoverageMetric",
    "PreserveComplianceMetric",
    "SpeculativeEditAbsenceMetric",
    "build_feedback_actor_metrics",
]

# ---------------------------------------------------------------------------
# Helpers for parsing the actor's input and output
# ---------------------------------------------------------------------------

_PROMPT_BLOCK_RE: re.Pattern[str] = re.compile(r"<prompt>(.*?)</prompt>", re.DOTALL)


def _extract_xml_from_input(input_str: str) -> str | None:
    """Extract the XML tree from between <prompt>…</prompt> in the actor input."""
    m = _PROMPT_BLOCK_RE.search(input_str)
    return m.group(1).strip() if m else None


def _collect_ids_from_xml(xml_str: str) -> set[str]:
    """Parse the XML tree and return all `id` attribute values."""
    try:
        root: ET.Element = ET.fromstring(xml_str)
    except ET.ParseError:
        return set()
    ids: set[str] = set()
    for elem in root.iter():
        node_id: str | None = elem.get("id")
        if node_id:
            ids.add(node_id)
    return ids


def _node_type_map_from_xml(xml_str: str) -> dict[str, str]:
    """Return {id: tag_name} for every element with an id in the XML tree."""
    try:
        root: ET.Element = ET.fromstring(xml_str)
    except ET.ParseError:
        return {}
    result: dict[str, str] = {}
    for elem in root.iter():
        node_id: str | None = elem.get("id")
        if node_id:
            result[node_id] = elem.tag
    return result


_ID_FIELDS: frozenset[str] = frozenset({"id", "host_id", "target"})
_ANNOTATION_ACTION_NAMES: frozenset[str] = frozenset({"add_example", "add_guidance"})

# XML tag names that XmlRenderPromptStrategy uses for each node type
_HOSTABLE_TAGS: frozenset[str] = frozenset({"paragraph", "item"})


def _extract_id_values(batch_dict: dict[str, Any]) -> list[str]:
    """Collect every id/host_id/target value from a parsed ActionBatch dict."""
    values: list[str] = []
    for action in batch_dict.get("actions", []):
        if not isinstance(action, dict):
            continue
        for field in _ID_FIELDS:
            val: object = action.get(field)
            if isinstance(val, str) and val:
                values.append(val)
    return values


def _parse_output_as_batch(output: str) -> dict[str, Any] | None:
    """Try to parse the actor output as an ActionBatch dict. Returns None on failure."""
    try:
        parsed: object = json.loads(output)
        if isinstance(parsed, dict):
            return cast(dict[str, Any], parsed)
    except (json.JSONDecodeError, ValueError):
        pass
    return None


# ---------------------------------------------------------------------------
# Structural gate 2: IdValidityMetric
# ---------------------------------------------------------------------------


class IdValidityMetric(HybridMetric):
    """Every id, host_id, and target in the emitted ActionBatch must exist verbatim in the input tree.

    Score: fraction of referenced IDs that are valid. 1.0 if the batch has no ID references
    or all are valid. 0.0 if the output cannot be parsed as JSON (JSON validity is a separate
    metric; here we treat un-parseable output as score 0.0).
    """

    name: ClassVar[str] = "id_validity"
    description: ClassVar[str] = "Checks that every id/host_id/target in the batch exists in the input prompt tree."

    def __init__(self, judge_llm: LiteLLMConfig | None = None) -> None:
        super().__init__(judge_llm)

    def score_case(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> tuple[float, str]:
        batch: dict[str, Any] | None = _parse_output_as_batch(output)
        if batch is None:
            return 0.0, "Output is not valid JSON; cannot validate IDs."

        xml_str: str | None = _extract_xml_from_input(input)
        if xml_str is None:
            return 1.0, "Could not extract prompt tree from input; skipping ID check."

        valid_ids: set[str] = _collect_ids_from_xml(xml_str)
        used_ids: list[str] = _extract_id_values(batch)
        if not used_ids:
            return 1.0, "Batch contains no ID references."

        hallucinated: list[str] = [uid for uid in used_ids if uid not in valid_ids]
        if not hallucinated:
            return 1.0, f"All {len(used_ids)} ID reference(s) are valid."

        score: float = max(0.0, 1.0 - len(hallucinated) / len(used_ids))
        return (
            score,
            f"{len(hallucinated)} hallucinated ID(s) out of {len(used_ids)}: {hallucinated}. Valid IDs in tree: {sorted(valid_ids)}",
        )


# ---------------------------------------------------------------------------
# Structural gate 3: HostTypeCorrectnessMetric
# ---------------------------------------------------------------------------


class HostTypeCorrectnessMetric(HybridMetric):
    """add_example and add_guidance actions must use a Paragraph or ListItem as host_id.

    Score: fraction of annotation actions whose host_id maps to a hostable node type.
    1.0 if there are no annotation actions.
    """

    name: ClassVar[str] = "host_type_correctness"
    description: ClassVar[str] = (
        "Checks that add_example/add_guidance host_ids refer to Paragraph or ListItem nodes, not Sections or annotation IDs."
    )

    def __init__(self, judge_llm: LiteLLMConfig | None = None) -> None:
        super().__init__(judge_llm)

    def score_case(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> tuple[float, str]:
        batch: dict[str, Any] | None = _parse_output_as_batch(output)
        if batch is None:
            return 0.0, "Output is not valid JSON; cannot check host types."

        xml_str: str | None = _extract_xml_from_input(input)
        if xml_str is None:
            return 1.0, "Could not extract prompt tree from input; skipping host type check."

        type_map: dict[str, str] = _node_type_map_from_xml(xml_str)

        annotation_actions: list[dict[str, Any]] = [
            a for a in batch.get("actions", []) if isinstance(a, dict) and a.get("action") in _ANNOTATION_ACTION_NAMES
        ]
        if not annotation_actions:
            return 1.0, "No add_example/add_guidance actions in batch."

        wrong: list[str] = []
        for action in annotation_actions:
            host_id: object = action.get("host_id")
            if not isinstance(host_id, str):
                wrong.append(f"<missing host_id in {action.get('action')}!>")
                continue
            tag: str | None = type_map.get(host_id)
            if tag is None:
                # ID doesn't exist — IdValidityMetric will catch this separately
                continue
            if tag not in _HOSTABLE_TAGS:
                wrong.append(f"{host_id} (tag={tag!r})")

        if not wrong:
            return 1.0, f"All {len(annotation_actions)} annotation action(s) use valid hostable nodes."
        score: float = max(0.0, 1.0 - len(wrong) / len(annotation_actions))
        return score, f"Wrong host type(s): {wrong}. Must be <paragraph> or <item>."


# ---------------------------------------------------------------------------
# Shared base for semantic LLM-judge metrics
# ---------------------------------------------------------------------------


class _ActorJudgeMetric(BaseLLMJudgeMetric):
    """Base for semantic evaluation of the actor's ActionBatch output.

    Each subclass defines:
    - `name`, `description` ClassVars
    - `criteria_key: ClassVar[str]` — key into ground_truth["criteria"]
    - `build_system_prompt()` — judge persona and instructions

    The judge sees:
      <scenario> … </scenario>        ← the full actor input (tree + feedback + preserve)
      <actor_output> … </actor_output> ← the ActionBatch JSON the actor emitted
      <criteria>                        ← per-scenario criteria extracted from ground_truth
      - criterion 1
      - criterion 2
      </criteria>
    """

    criteria_key: ClassVar[str]

    def build_user_prompt(
        self,
        rendered_prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> str:
        criteria_lines: str = ""
        if ground_truth:
            try:
                gt: dict[str, Any] = json.loads(ground_truth)
                criteria: list[str] = gt.get("criteria", {}).get(self.criteria_key, [])
                criteria_lines = "\n".join(f"- {c}" for c in criteria)
            except (json.JSONDecodeError, AttributeError):
                criteria_lines = "(criteria unavailable)"

        return f"<scenario>\n{input}\n</scenario>\n\n<actor_output>\n{output}\n</actor_output>\n\n<criteria>\n{criteria_lines}\n</criteria>"

    @abstractmethod
    def build_system_prompt(self) -> str: ...


# ---------------------------------------------------------------------------
# Semantic metric 4: IssueTraceabilityMetric
# ---------------------------------------------------------------------------


class IssueTraceabilityMetric(_ActorJudgeMetric):
    """Every emitted action must be traceable to a specific cited feedback issue.

    An action is traceable if there is an issue in the `<feedback>` block that
    motivates it — the action should address the cited rationale, target behavior,
    or evidence described in the issue.
    """

    name: ClassVar[str] = "issue_traceability"
    description: ClassVar[str] = "Checks that each emitted action addresses a specific cited feedback issue."
    criteria_key: ClassVar[str] = "issue_traceability"

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        super().__init__(litellm_config)

    def build_system_prompt(self) -> str:
        return (
            "You are an expert evaluator judging whether the actions emitted by an actor LLM are "
            "justified by the feedback it received.\n\n"
            "You will be given:\n"
            "- A <scenario> block containing the actor's full input (prompt tree + feedback + preserve list).\n"
            "- An <actor_output> block containing the ActionBatch JSON the actor emitted.\n"
            "- A <criteria> list describing what traceability looks like for this scenario.\n\n"
            "For each action in the batch, check: does it directly address a specific issue cited in "
            "the <feedback> section? An action that addresses a real issue is traceable. An action that "
            "targets a node or makes a change not motivated by any cited issue is NOT traceable.\n\n"
            "Produce a MetricResult with:\n"
            "- score: fraction of actions that are traceable to a feedback issue (1.0 = all, 0.0 = none)\n"
            "- assessment: concise narrative of your judgment\n"
            "- signals: one IssueSignal per untraceable action, citing the prompt node that should "
            "  better guide the actor to stay within the feedback scope\n"
            "- preserve: aspects of the prompt that are working well for traceability"
        )


# ---------------------------------------------------------------------------
# Semantic metric 5: ActionTypeFitnessMetric
# ---------------------------------------------------------------------------


class ActionTypeFitnessMetric(_ActorJudgeMetric):
    """The action type chosen must match the nature of the feedback issue.

    Examples of correct mappings:
    - 'target confused by edge cases' → add_example (teach by demonstration)
    - 'prompt is vague/ambiguous' → rewrite_node (sharpen the text)
    - 'missing section for X' (document-level) → insert_node
    - 'target applies wrong rule consistently' → add_guidance (state the rule)
    - 'existing example is wrong' → update_example
    """

    name: ClassVar[str] = "action_type_fitness"
    description: ClassVar[str] = "Checks that each action type matches the nature of its motivating feedback issue."
    criteria_key: ClassVar[str] = "action_type_fitness"

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        super().__init__(litellm_config)

    def build_system_prompt(self) -> str:
        return (
            "You are an expert evaluator judging whether each action type in an actor's ActionBatch "
            "is the right lever for the feedback it received.\n\n"
            "Action type fitness rules:\n"
            "- Target confused by edge cases or specific inputs → add_example (teach by demonstration)\n"
            "- Prompt text is vague, ambiguous, or contradictory → rewrite_node (sharpen the words)\n"
            "- A systematic rule or convention is missing → add_guidance (state the rule explicitly)\n"
            "- A section/paragraph about a topic is entirely absent → insert_node\n"
            "- An existing example demonstrates the wrong behavior → update_example / remove_example\n"
            "- A node is obsolete or actively harmful → delete_node\n\n"
            "You will be given a <scenario> (actor input), <actor_output> (ActionBatch JSON), "
            "and <criteria> (specific fitness expectations for this scenario).\n\n"
            "Produce a MetricResult with:\n"
            "- score: fraction of actions where the action type is the best fit (1.0 = all fit well)\n"
            "- assessment: concise narrative\n"
            "- signals: one IssueSignal per mismatched action, citing the prompt node whose instructions "
            "  should guide the actor to choose the correct action type\n"
            "- preserve: aspects of the prompt that already steer action-type selection well"
        )


# ---------------------------------------------------------------------------
# Semantic metric 6: ActorCoverageMetric
# ---------------------------------------------------------------------------


class ActorCoverageMetric(_ActorJudgeMetric):
    """All significant feedback issues (high seen_in_n_cases) must produce at least one action.

    Minor issues (low sightings) may be skipped without penalty. The actor should
    prioritize — not ignore — the most prevalent issues.
    """

    name: ClassVar[str] = "actor_coverage"
    description: ClassVar[str] = "Checks that all high-priority feedback issues resulted in at least one action."
    criteria_key: ClassVar[str] = "coverage"

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        super().__init__(litellm_config)

    def build_system_prompt(self) -> str:
        return (
            "You are an expert evaluator judging whether an actor's ActionBatch addresses all "
            "significant feedback issues.\n\n"
            "A feedback issue is significant if its 'seen in N cases' count is 3 or higher. "
            "Every significant issue should have at least one action in the batch that addresses it. "
            "Low-sightings issues (1-2 cases) may be skipped without penalty.\n\n"
            "You will be given a <scenario> (actor input), <actor_output> (ActionBatch JSON), "
            "and <criteria> (coverage expectations for this scenario).\n\n"
            "Produce a MetricResult with:\n"
            "- score: fraction of significant issues that were addressed (1.0 = all covered)\n"
            "- assessment: concise narrative listing which issues were and weren't covered\n"
            "- signals: one IssueSignal for each significant issue that was not addressed, "
            "  citing the prompt node whose instructions should encourage the actor to prioritize "
            "  high-sightings issues\n"
            "- preserve: aspects of the prompt that already encourage good coverage"
        )


# ---------------------------------------------------------------------------
# Semantic metric 7: PreserveComplianceMetric
# ---------------------------------------------------------------------------


class PreserveComplianceMetric(_ActorJudgeMetric):
    """No emitted action must break any item in the preserve list.

    An action breaks a preserve item if it rewrites, deletes, or adds content that
    directly contradicts what is listed as protected.
    """

    name: ClassVar[str] = "preserve_compliance"
    description: ClassVar[str] = "Checks that no emitted action contradicts or removes a preserve-listed item."
    criteria_key: ClassVar[str] = "preserve_compliance"

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        super().__init__(litellm_config)

    def build_system_prompt(self) -> str:
        return (
            "You are an expert evaluator judging whether an actor's ActionBatch respects the preserve list.\n\n"
            "The <preserve> section of the actor's input lists properties or nodes that must not be broken "
            "by any edit. An action violates a preserve item if it:\n"
            "- Rewrites or deletes a specifically named node\n"
            "- Adds content that directly contradicts a named behavior or property\n"
            "- Removes structural elements the preserve list says to keep\n\n"
            "An action that targets a *different* node is not a violation, even if the topic overlaps.\n\n"
            "You will be given a <scenario> (actor input including the preserve list), "
            "<actor_output> (ActionBatch JSON), and <criteria>.\n\n"
            "Produce a MetricResult with:\n"
            "- score: 1.0 if no preserve violations, fraction compliant otherwise\n"
            "- assessment: concise narrative\n"
            "- signals: one IssueSignal per violating action, citing the prompt node whose "
            "  instructions should make the preserve contract clearer to the actor\n"
            "- preserve: aspects of the prompt that already communicate the preserve contract well"
        )


# ---------------------------------------------------------------------------
# Semantic metric 8: SpeculativeEditAbsenceMetric
# ---------------------------------------------------------------------------


class SpeculativeEditAbsenceMetric(_ActorJudgeMetric):
    """No emitted action should target nodes or make changes not motivated by the feedback.

    Speculative edits are changes the actor makes 'while it's in there' — fixing
    things not cited as issues. They dilute the batch and can introduce regressions.
    """

    name: ClassVar[str] = "speculative_edit_absence"
    description: ClassVar[str] = "Checks that no action targets a node or makes a change not motivated by the feedback."
    criteria_key: ClassVar[str] = "speculative_edit_absence"

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        super().__init__(litellm_config)

    def build_system_prompt(self) -> str:
        return (
            "You are an expert evaluator judging whether an actor's ActionBatch contains speculative edits.\n\n"
            "A speculative edit is an action that:\n"
            "- Targets a node not mentioned in the feedback\n"
            "- Makes a change not traceable to any cited issue\n"
            "- 'Improves' content opportunistically without a feedback warrant\n\n"
            "The feedback actor's instructions say: 'Almost never: speculative edits. "
            "If no issue in the feedback motivates a change, don't make it.'\n\n"
            "You will be given a <scenario> (actor input), <actor_output> (ActionBatch JSON), "
            "and <criteria> (what counts as speculative for this scenario).\n\n"
            "Produce a MetricResult with:\n"
            "- score: fraction of actions that are non-speculative (1.0 = no speculative edits)\n"
            "- assessment: concise narrative\n"
            "- signals: one IssueSignal per speculative action, citing the prompt node that should "
            "  more firmly tell the actor not to make changes beyond the feedback scope\n"
            "- preserve: aspects of the prompt that already discourage speculative edits"
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_feedback_actor_metrics(judge_llm: LiteLLMConfig) -> list[Metric]:
    """Return all 8 evaluation metrics for the feedback-actor target."""
    return [
        JsonCorrectnessMetric(litellm_config=judge_llm),
        IdValidityMetric(judge_llm=judge_llm),
        HostTypeCorrectnessMetric(judge_llm=judge_llm),
        IssueTraceabilityMetric(litellm_config=judge_llm),
        ActionTypeFitnessMetric(litellm_config=judge_llm),
        ActorCoverageMetric(litellm_config=judge_llm),
        PreserveComplianceMetric(litellm_config=judge_llm),
        SpeculativeEditAbsenceMetric(litellm_config=judge_llm),
    ]
