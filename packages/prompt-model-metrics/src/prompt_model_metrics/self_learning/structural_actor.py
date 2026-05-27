"""Evaluation metrics for the structural-actor prompt.

Four narrow metrics, one focused judgment each:

  1. StructuralAllowedActionsMetric  — programmatic; emitted actions must be in
     the restricted vocabulary (move_node, delete_node, structural-shell
     insert_node, heading-only rewrite_node).
  2. StructuralDefectRecallMetric    — LLM judge; for each planted defect in
     ground_truth, did the batch include an action that repairs it?
  3. StructuralScopeCreepMetric      — LLM judge; did any action touch a node
     outside the culprit ∪ collateral set?
  4. StructuralPreserveRespectMetric — LLM judge; did any action break a
     preserve-listed property?

Ground-truth schema (JSON string passed as `ground_truth`):

    {
      "defects": [
        {
          "kind": "duplicate_section" | "heading_skip" | "orphan_content" | "wrong_container",
          "culprit_node_ids": ["4", ...],
          "collateral_node_ids": ["2", ...],
          "description": "h2 at id 4 duplicates h2 at id 2"
        },
        ...
      ]
    }

Empty `defects` list means a clean tree — the actor should emit no actions.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from abc import abstractmethod
from typing import Any, ClassVar, cast

from prompt_model import BaseLLMJudgeMetric, HybridMetric, Metric
from prompt_model.config import LiteLLMConfig

__all__ = [
    "StructuralAllowedActionsMetric",
    "StructuralDefectRecallMetric",
    "StructuralScopeCreepMetric",
    "StructuralPreserveRespectMetric",
    "build_structural_actor_metrics",
]


# ---------------------------------------------------------------------------
# Shared parsing helpers
# ---------------------------------------------------------------------------

_PROMPT_BLOCK_RE: re.Pattern[str] = re.compile(r"<prompt>(.*?)</prompt>", re.DOTALL)
_ID_FIELDS: frozenset[str] = frozenset({"id", "host_id", "target"})

# Action-name classification
_ALWAYS_FORBIDDEN_ACTIONS: frozenset[str] = frozenset(
    {
        "add_example",
        "add_guidance",
        "update_example",
        "update_guidance",
        "remove_example",
        "remove_guidance",
    }
)
_UNCONDITIONALLY_ALLOWED_ACTIONS: frozenset[str] = frozenset({"move_node", "delete_node"})
# rewrite_node and insert_node require further inspection.


def _extract_xml_from_input(input_str: str) -> str | None:
    m: re.Match[str] | None = _PROMPT_BLOCK_RE.search(input_str)
    return m.group(1).strip() if m else None


def _node_type_map_from_xml(xml_str: str) -> dict[str, str]:
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


def _parse_output_as_batch(output: str) -> dict[str, Any] | None:
    try:
        parsed: object = json.loads(output)
        if isinstance(parsed, dict):
            return cast(dict[str, Any], parsed)
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _action_touched_ids(action: dict[str, Any]) -> list[str]:
    """IDs the action structurally touches in the input tree (target of mutation + anchor)."""
    touched: list[str] = []
    for field in _ID_FIELDS:
        val: object = action.get(field)
        if isinstance(val, str) and val:
            touched.append(val)
    return touched


def _insert_node_subtree_root_is_section(subtree: object) -> bool:
    """Heuristic: structural-shell insert_node payloads start with a markdown heading line."""
    if not isinstance(subtree, str):
        return False
    for line in subtree.splitlines():
        stripped: str = line.strip()
        if not stripped:
            continue
        return stripped.startswith("#")
    return False


def _classify_action_allowed(action: dict[str, Any], type_map: dict[str, str]) -> tuple[bool, str]:
    """Return (allowed, reason). `type_map` maps existing node id -> xml tag."""
    name: object = action.get("action")
    if not isinstance(name, str):
        return False, "missing 'action' field"
    if name in _ALWAYS_FORBIDDEN_ACTIONS:
        return False, f"action '{name}' is reserved for the content-focused pass"
    if name in _UNCONDITIONALLY_ALLOWED_ACTIONS:
        return True, ""
    if name == "rewrite_node":
        node_id: object = action.get("id")
        if not isinstance(node_id, str):
            return False, "rewrite_node missing 'id'"
        tag: str | None = type_map.get(node_id)
        if tag is None:
            # Unknown id — let the recall/scope metrics handle this; treat as allowed here
            return True, ""
        if tag != "section":
            return False, f"rewrite_node on <{tag}> id {node_id!r} — content edits are out of scope"
        return True, ""
    if name == "insert_node":
        if not _insert_node_subtree_root_is_section(action.get("subtree")):
            return False, "insert_node subtree's first root is not a Section — net-new content is out of scope"
        return True, ""
    return False, f"unknown action '{name}'"


# ---------------------------------------------------------------------------
# Metric 1: StructuralAllowedActionsMetric (programmatic, HybridMetric)
# ---------------------------------------------------------------------------


class StructuralAllowedActionsMetric(HybridMetric):
    """Score = fraction of emitted actions that belong to the restricted allowed set.

    Allowed:
      - move_node, delete_node — always.
      - rewrite_node — only when its target is a <section>.
      - insert_node — only when the subtree's first root is a heading (Section).

    Forbidden:
      - add_example, add_guidance, update_example, update_guidance,
        remove_example, remove_guidance — annotation actions belong to the
        previous pass.
      - rewrite_node on any non-section node — content edits are out of scope.
      - insert_node whose subtree does not start with a heading.

    Score 1.0 on empty batches (no actions = no violations).
    """

    name: ClassVar[str] = "structural_allowed_actions"
    description: ClassVar[str] = "Checks that every emitted action belongs to the restricted action set for the structural cleanup pass."

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
            return 0.0, "Output is not valid JSON; cannot classify actions."

        actions: list[Any] = batch.get("actions", []) or []
        if not actions:
            return 1.0, "Empty batch — no actions to classify."

        xml_str: str | None = _extract_xml_from_input(input)
        type_map: dict[str, str] = _node_type_map_from_xml(xml_str) if xml_str is not None else {}

        violations: list[str] = []
        for i, raw_action in enumerate(actions):
            if not isinstance(raw_action, dict):
                violations.append(f"action[{i}] is not a JSON object")
                continue
            allowed: bool
            reason: str
            allowed, reason = _classify_action_allowed(raw_action, type_map)
            if not allowed:
                violations.append(f"action[{i}] ({raw_action.get('action')!r}): {reason}")

        if not violations:
            return 1.0, f"All {len(actions)} action(s) are in the allowed set."
        score: float = max(0.0, 1.0 - len(violations) / len(actions))
        return score, "Forbidden actions: " + "; ".join(violations)


# ---------------------------------------------------------------------------
# Shared base for LLM-judge metrics on the structural actor
# ---------------------------------------------------------------------------


class _StructuralJudgeMetric(BaseLLMJudgeMetric):
    """Base for LLM-judge metrics evaluating the structural actor's output.

    The judge sees:
      <scenario>      ← the full actor input (<prompt> + <preserve>)
      <actor_output>  ← the ActionBatch JSON the actor emitted
      <ground_truth>  ← the defect spec (verbatim JSON string), if provided
    """

    def build_user_prompt(
        self,
        rendered_prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> str:
        gt_block: str = ground_truth if ground_truth is not None else "(no ground truth provided)"
        return (
            f"<scenario>\n{input}\n</scenario>\n\n<actor_output>\n{output}\n</actor_output>\n\n<ground_truth>\n{gt_block}\n</ground_truth>"
        )

    @abstractmethod
    def build_system_prompt(self) -> str: ...


# ---------------------------------------------------------------------------
# Metric 2: StructuralDefectRecallMetric (LLM judge)
# ---------------------------------------------------------------------------


class StructuralDefectRecallMetric(_StructuralJudgeMetric):
    """Did the batch include at least one action that repairs each planted defect?

    Score: fraction of ground_truth.defects that the batch addresses. A defect
    is addressed if any action in the batch, applied to the input tree, would
    materially fix the defect described — regardless of which specific actions
    the author had in mind. Multiple valid fix shapes for the same defect are
    accepted (e.g. delete_node vs. move_node + delete_node).

    Empty defects list (clean tree) + empty batch → 1.0. Empty defects + non-
    empty batch → 0.0 (the actor fabricated work).
    """

    name: ClassVar[str] = "structural_defect_recall"
    description: ClassVar[str] = "Checks that the actor's batch addresses every planted structural defect from the ground truth."

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        super().__init__(litellm_config)

    def build_system_prompt(self) -> str:
        return (
            "You are an expert evaluator judging whether a structural-cleanup actor LLM addressed every "
            "planted structural defect in a prompt tree.\n\n"
            "You will be given:\n"
            "- <scenario>: the actor's full input — <prompt> (the post-revision tree as XML) and <preserve>.\n"
            "- <actor_output>: the ActionBatch JSON the actor emitted (reasoning + actions list).\n"
            '- <ground_truth>: JSON of the form {"defects": [{"kind": str, "culprit_node_ids": [...], '
            '"collateral_node_ids": [...], "description": str}, ...]}.\n\n'
            "For each defect in ground_truth.defects, decide: does any action in the batch, applied to "
            "the input tree, materially repair this defect? Multiple action shapes can be correct — "
            "a duplicate section can be removed via delete_node, or consolidated via move_node + "
            "delete_node, etc. Accept any shape that achieves the structural goal described.\n\n"
            "Edge cases:\n"
            "- Empty ground_truth.defects + empty actions list → perfect (score 1.0).\n"
            "- Empty ground_truth.defects + non-empty actions list → the actor fabricated work; score 0.0 "
            "(this is a defect-recall failure framed as a false-positive — recall of zero defects requires "
            "zero actions).\n"
            "- Non-empty defects + empty actions → score 0.0 (missed all of them).\n\n"
            "Produce a MetricResult with:\n"
            "- score: fraction of defects addressed (1.0 = all, 0.0 = none); use the special-case rules above.\n"
            "- assessment: concise narrative naming which defects were and weren't fixed.\n"
            "- signals: one IssueSignal per missed defect, citing the section of the actor's prompt "
            "  (e.g. the relevant '## N.' defect description) that should better guide the actor to detect it.\n"
            "- preserve: aspects of the prompt that already produce good recall."
        )


# ---------------------------------------------------------------------------
# Metric 3: StructuralScopeCreepMetric (LLM judge)
# ---------------------------------------------------------------------------


class StructuralScopeCreepMetric(_StructuralJudgeMetric):
    """Did any action touch a node not implicated by a defect?

    For each action, the set of structurally touched IDs is `{id, target, host_id}`
    (those present on the action). An action is in-scope if every touched ID
    belongs to the union of all ground_truth.defects[*].culprit_node_ids and
    collateral_node_ids. An action is creep if any touched ID falls outside
    that union.

    The metric is a judge (not pure programmatic) because legitimate fixes
    sometimes touch IDs the human author didn't list as collateral (e.g.
    the parent of a moved node). The judge applies common-sense leniency
    while still flagging clear scope-creep cases.
    """

    name: ClassVar[str] = "structural_scope_creep"
    description: ClassVar[str] = "Checks that no emitted action touches a node outside the ground-truth defect culprit/collateral set."

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        super().__init__(litellm_config)

    def build_system_prompt(self) -> str:
        return (
            "You are an expert evaluator judging whether a structural-cleanup actor LLM stayed within the "
            "scope of the planted defects, or whether it 'fixed' things that weren't broken.\n\n"
            "You will be given:\n"
            "- <scenario>: the actor's full input (<prompt> tree + <preserve>).\n"
            "- <actor_output>: the ActionBatch JSON.\n"
            '- <ground_truth>: JSON of the form {"defects": [{"culprit_node_ids": [...], '
            '"collateral_node_ids": [...], ...}, ...]}.\n\n'
            "Define the in-scope set as the union of culprit_node_ids and collateral_node_ids across all "
            "defects. For each action in the batch, determine the structurally touched IDs from its fields "
            "(`id`, `target`, `host_id`). An action is in-scope when every touched ID is in the in-scope set "
            "OR is a structurally necessary anchor for a fix (e.g. moving a culprit may require anchoring at "
            "a sibling that is otherwise fine — that's not creep). An action is creep when it edits or moves "
            "a node that has no plausible connection to any listed defect.\n\n"
            "Edge cases:\n"
            "- Empty ground_truth.defects + empty actions → score 1.0 (perfect, nothing to creep on).\n"
            "- Empty ground_truth.defects + non-empty actions → score 0.0 (every action is creep by definition).\n"
            "- Non-empty defects + empty actions → score 1.0 (no creep, but recall fails separately).\n\n"
            "Produce a MetricResult with:\n"
            "- score: fraction of actions that are in-scope (1.0 = no creep).\n"
            "- assessment: concise narrative listing each creep action.\n"
            "- signals: one IssueSignal per scope-creep action, citing the section of the actor's prompt "
            "  (e.g. 'Common false positive' lines, or the 'When in doubt, do nothing' hard rule) that should "
            "  prevent the creep.\n"
            "- preserve: aspects of the prompt that already discourage creep."
        )


# ---------------------------------------------------------------------------
# Metric 4: StructuralPreserveRespectMetric (LLM judge)
# ---------------------------------------------------------------------------


class StructuralPreserveRespectMetric(_StructuralJudgeMetric):
    """Did any action break a preserve-listed property?

    The <preserve> block in the actor input enumerates properties of the prompt
    that must not be broken. An action violates a preserve item if it deletes,
    moves, or rewrites a node such that the named property no longer holds.

    Score: 1.0 if no preserve violations; fraction of compliant actions
    otherwise.
    """

    name: ClassVar[str] = "structural_preserve_respect"
    description: ClassVar[str] = "Checks that no emitted action breaks a property listed in the <preserve> block."

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        super().__init__(litellm_config)

    def build_system_prompt(self) -> str:
        return (
            "You are an expert evaluator judging whether a structural-cleanup actor LLM respected the "
            "preserve list in its input.\n\n"
            "You will be given:\n"
            "- <scenario>: the actor's full input. The <preserve> sub-block enumerates properties of the "
            "  prompt that must not be broken by any edit.\n"
            "- <actor_output>: the ActionBatch JSON.\n"
            "- <ground_truth>: defect spec JSON (for context; not the primary signal for this metric).\n\n"
            "An action violates a preserve item if it:\n"
            "- Deletes a node whose presence the preserve item names.\n"
            "- Moves a node such that a preserve item's structural relationship no longer holds.\n"
            "- Rewrites a heading whose text the preserve item names.\n\n"
            "An action that touches a node merely related to a preserve topic is NOT a violation unless "
            "the action's outcome breaks the named property.\n\n"
            "Edge case: an empty <preserve> block (or '(none)') means the score is 1.0 by default — no "
            "preserve items exist to break.\n\n"
            "Produce a MetricResult with:\n"
            "- score: 1.0 if no preserve violations; otherwise fraction of compliant actions (1 - violations/total).\n"
            "- assessment: concise narrative naming each violating action and which preserve item it breaks.\n"
            "- signals: one IssueSignal per violating action, citing the hard rule in the actor's prompt "
            "  ('Do not break anything in <preserve>') that should have prevented it.\n"
            "- preserve: aspects of the prompt that already communicate the preserve contract well."
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_structural_actor_metrics(judge_llm: LiteLLMConfig) -> list[Metric]:
    """Return all 4 evaluation metrics for the structural-actor target."""
    return [
        StructuralAllowedActionsMetric(judge_llm=judge_llm),
        StructuralDefectRecallMetric(litellm_config=judge_llm),
        StructuralScopeCreepMetric(litellm_config=judge_llm),
        StructuralPreserveRespectMetric(litellm_config=judge_llm),
    ]
