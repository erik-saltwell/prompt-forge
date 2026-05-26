"""Evaluation metrics for the hybrid-judge prompt.

Five metrics across two tiers:

Structural gate (deterministic + optional judge):
  1. CulpritIdValidityMetric  — culprit_node_id is a real id in the XML prompt or "document"

Semantic metrics (LLM judge against per-scenario criteria from ground_truth):
  2. CulpritLocalizationMetric      — most responsible node cited; no over-hedging to "document"
  3. DiagnosisSpecificityMetric     — rationale names the failure mode, not just restates assessment
  4. ActionabilityMetric            — target_behavior is action-oriented; success_criterion is observable
  5. SuggestedChangeCalibrationMetric — suggested_prompt_change present when fix is clear, null when uncertain
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
    "CulpritIdValidityMetric",
    "CulpritLocalizationMetric",
    "DiagnosisSpecificityMetric",
    "ActionabilityMetric",
    "SuggestedChangeCalibrationMetric",
    "build_hybrid_judge_metrics",
]

# ---------------------------------------------------------------------------
# Helpers for parsing the judge's input and output
# ---------------------------------------------------------------------------

_PROMPT_BLOCK_RE: re.Pattern[str] = re.compile(r"<prompt>(.*?)</prompt>", re.DOTALL)


def _extract_prompt_xml_from_input(input_str: str) -> str | None:
    """Extract the XML tree from between <prompt>…</prompt> in the judge input."""
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


def _parse_diagnosis(output: str) -> dict[str, Any] | None:
    """Try to parse the judge output as a JudgeDiagnosis dict. Returns None on failure."""
    try:
        parsed: object = json.loads(output)
        if isinstance(parsed, dict):
            return cast(dict[str, Any], parsed)
    except (json.JSONDecodeError, ValueError):
        pass
    return None


# ---------------------------------------------------------------------------
# Structural gate: CulpritIdValidityMetric
# ---------------------------------------------------------------------------


class CulpritIdValidityMetric(HybridMetric):
    """The culprit_node_id in the JudgeDiagnosis must be a real node id from the XML prompt or "document".

    Score: 1.0 if the id is valid (exists in the XML or is "document"), 0.0 otherwise.
    0.0 also if the output cannot be parsed as JSON.
    """

    name: ClassVar[str] = "culprit_id_validity"
    description: ClassVar[str] = "Checks that culprit_node_id is either a node id from the XML prompt or the literal string 'document'."

    def __init__(self, judge_llm: LiteLLMConfig | None = None) -> None:
        super().__init__(judge_llm)

    def score_case(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> tuple[float, str]:
        diagnosis: dict[str, Any] | None = _parse_diagnosis(output)
        if diagnosis is None:
            return 0.0, "Output is not valid JSON; cannot validate culprit_node_id."

        culprit: object = diagnosis.get("culprit_node_id")
        if not isinstance(culprit, str) or not culprit:
            return 0.0, "Output is missing culprit_node_id or it is not a string."

        if culprit == "document":
            return 1.0, "culprit_node_id is the valid sentinel 'document'."

        xml_str: str | None = _extract_prompt_xml_from_input(input)
        if xml_str is None:
            return 1.0, "Could not extract prompt XML from input; skipping id check."

        valid_ids: set[str] = _collect_ids_from_xml(xml_str)
        if culprit in valid_ids:
            return 1.0, f"culprit_node_id {culprit!r} is a valid node id in the prompt."

        return (
            0.0,
            f"culprit_node_id {culprit!r} does not exist in the prompt XML. Valid ids: {sorted(valid_ids)}",
        )


# ---------------------------------------------------------------------------
# Shared base for semantic LLM-judge metrics
# ---------------------------------------------------------------------------


class _HybridJudgeEvalMetric(BaseLLMJudgeMetric):
    """Base for semantic evaluation of the judge's JudgeDiagnosis output.

    Each subclass defines:
    - `name`, `description` ClassVars
    - `criteria_key: ClassVar[str]` — key into ground_truth["criteria"]
    - `build_system_prompt()` — judge persona and instructions

    The judge sees:
      <judge_input> … </judge_input>    ← the full hybrid-judge user message
      <judge_output> … </judge_output>  ← the JudgeDiagnosis JSON the judge emitted
      <criteria>                         ← per-scenario criteria extracted from ground_truth
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

        return (
            f"<judge_input>\n{input}\n</judge_input>\n\n"
            f"<judge_output>\n{output}\n</judge_output>\n\n"
            f"<criteria>\n{criteria_lines}\n</criteria>"
        )

    @abstractmethod
    def build_system_prompt(self) -> str: ...


# ---------------------------------------------------------------------------
# Semantic metric 2: CulpritLocalizationMetric
# ---------------------------------------------------------------------------


class CulpritLocalizationMetric(_HybridJudgeEvalMetric):
    """The judge must cite the single most responsible node, not hedge to "document".

    A good localization:
    - Cites a specific node id when the assessment clearly points to one part of the prompt.
    - Uses "document" only when the failure genuinely cannot be traced to an existing node.
    - Prefers a child node (paragraph, list item, annotation) over a vague parent section.
    """

    name: ClassVar[str] = "culprit_localization"
    description: ClassVar[str] = (
        "Checks that the judge cites the most responsible node, avoiding over-hedging to 'document' "
        "or picking a vague parent instead of the specific culprit."
    )
    criteria_key: ClassVar[str] = "culprit_localization"

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        super().__init__(litellm_config)

    def build_system_prompt(self) -> str:
        return (
            "You are an expert evaluator judging whether a prompt-failure diagnostician correctly "
            "localized the fault to the most responsible node.\n\n"
            "You will be given:\n"
            "- A <judge_input> block containing the full context the diagnostician received "
            "(XML prompt, case input, model output, assessment).\n"
            "- A <judge_output> block containing the JudgeDiagnosis JSON the diagnostician emitted.\n"
            "- A <criteria> list describing what correct localization looks like for this scenario.\n\n"
            "Evaluate whether the cited culprit_node_id is the *most responsible* node:\n"
            "- If the assessment clearly points to a specific node, that node (or a more specific child) "
            "should be cited — NOT 'document'.\n"
            "- 'document' is valid only when the failure requires a node that does not yet exist in the prompt.\n"
            "- Citing a section id when the failure lives in a specific paragraph or annotation inside it "
            "is an imprecise localization (partial credit).\n\n"
            "Produce a MetricResult with:\n"
            "- score: 1.0 if the most responsible node is correctly cited; 0.5 for imprecise but reasonable "
            "localization (wrong level); 0.0 for wrong node or unjustified 'document'\n"
            "- assessment: concise narrative of your judgment\n"
            "- signals: one IssueSignal per localization problem, citing the prompt node whose instructions "
            "should guide the diagnostician to pick more precisely\n"
            "- preserve: aspects of the prompt that already encourage correct localization"
        )


# ---------------------------------------------------------------------------
# Semantic metric 3: DiagnosisSpecificityMetric
# ---------------------------------------------------------------------------


class DiagnosisSpecificityMetric(_HybridJudgeEvalMetric):
    """The rationale must name the concrete failure mode, not just restate the assessment.

    Good rationale examples:
    - "The rubric paragraph uses 'human perspective' without defining the factors humans weigh,
      so the model cannot operationalize the judgment."
    - "The example shows correct JSON but uses a field name ('result') that conflicts with the
      output schema ('answer'), causing the model to pick the wrong key."

    Bad rationale (restatement):
    - "The model output was incorrect according to the metric."
    - "The model did not follow the instructions."
    """

    name: ClassVar[str] = "diagnosis_specificity"
    description: ClassVar[str] = "Checks that the rationale names the concrete failure mode rather than restating the assessment."
    criteria_key: ClassVar[str] = "diagnosis_specificity"

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        super().__init__(litellm_config)

    def build_system_prompt(self) -> str:
        return (
            "You are an expert evaluator judging whether a prompt-failure diagnosis is specific.\n\n"
            "You will be given:\n"
            "- A <judge_input> block containing the full context (XML prompt, case input, model output, "
            "assessment).\n"
            "- A <judge_output> block containing the JudgeDiagnosis JSON.\n"
            "- A <criteria> list describing what specific rationale looks like for this scenario.\n\n"
            "Evaluate the `rationale` field:\n"
            "- A specific rationale names the *mechanism* — which aspect of the node (its wording, its "
            "examples, its omitted constraints) caused the model to behave as it did.\n"
            "- A restatement merely echoes the assessment ('the output was wrong') without explaining why "
            "the cited node is at fault.\n"
            "- Also evaluate whether `target_behavior` and `success_criterion` are specific to this "
            "failure scenario, not generic templates.\n\n"
            "Produce a MetricResult with:\n"
            "- score: 1.0 for a concrete, mechanism-naming rationale; 0.5 for partially specific; "
            "0.0 for pure restatement or generic language\n"
            "- assessment: concise narrative\n"
            "- signals: one IssueSignal per specificity gap, citing the prompt node whose instructions "
            "should push the diagnostician to name failure mechanisms\n"
            "- preserve: aspects of the prompt that already elicit specific diagnoses"
        )


# ---------------------------------------------------------------------------
# Semantic metric 4: ActionabilityMetric
# ---------------------------------------------------------------------------


class ActionabilityMetric(_HybridJudgeEvalMetric):
    """target_behavior must be action-oriented; success_criterion must be an observable predicate.

    Good target_behavior:
    - "Instruct the model to name the three factors it must weigh before answering."
    - "Require the model to output a JSON object with exactly the keys 'answer' and 'confidence'."

    Bad target_behavior:
    - "Make the prompt clearer."
    - "Improve the rubric."

    Good success_criterion:
    - "The prompt lists the rubric factors by name and the model applies all of them in the output."
    - "The output JSON contains only 'answer' and 'confidence' keys on the next 5 test cases."

    Bad success_criterion:
    - "The model would have answered correctly."
    - "The output is better."
    """

    name: ClassVar[str] = "actionability"
    description: ClassVar[str] = "Checks that target_behavior is action-oriented and success_criterion is an observable predicate."
    criteria_key: ClassVar[str] = "actionability"

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        super().__init__(litellm_config)

    def build_system_prompt(self) -> str:
        return (
            "You are an expert evaluator judging the actionability of a prompt-failure diagnosis.\n\n"
            "You will be given:\n"
            "- A <judge_input> block (XML prompt, case input, model output, assessment).\n"
            "- A <judge_output> block containing the JudgeDiagnosis JSON.\n"
            "- A <criteria> list for this scenario.\n\n"
            "Evaluate two fields:\n\n"
            "**target_behavior**: Should describe what the *prompt* should make the target LLM *do* — "
            "starting with a verb like 'Require', 'Instruct', 'Name', 'List'. It should not describe "
            "a feeling ('be clearer') or an outcome ('improve accuracy').\n\n"
            "**success_criterion**: Should be an *observable predicate* — something a human or automated "
            "check can verify on the next test run. 'The model would have answered correctly on this case' "
            "is too weak. Prefer conditions like 'The prompt lists X and the model cites it in the output.'\n\n"
            "Produce a MetricResult with:\n"
            "- score: average of target_behavior score and success_criterion score (each 0–1)\n"
            "- assessment: concise narrative covering both fields\n"
            "- signals: one IssueSignal per non-actionable field, citing the prompt node whose "
            "instructions should guide the diagnostician toward concrete, verb-led descriptions\n"
            "- preserve: aspects of the prompt that already elicit actionable diagnoses"
        )


# ---------------------------------------------------------------------------
# Semantic metric 5: SuggestedChangeCalibrationMetric
# ---------------------------------------------------------------------------


class SuggestedChangeCalibrationMetric(_HybridJudgeEvalMetric):
    """suggested_prompt_change should be non-null when the fix is clear, null when it isn't.

    When to include a suggestion:
    - The culprit node is vague text that can be sharpened with a concrete rewrite.
    - A specific example needs to be updated or replaced.
    - A missing rule can be stated in one sentence.

    When to leave null:
    - The failure requires restructuring several sections (actor's job, not diagnostician's).
    - The root cause is a conceptual gap whose best fix is unclear.
    - The diagnostician is uncertain which of several rewrites would work.
    """

    name: ClassVar[str] = "suggested_change_calibration"
    description: ClassVar[str] = "Checks that suggested_prompt_change is non-null when the fix is clear and null when uncertain."
    criteria_key: ClassVar[str] = "suggested_change_calibration"

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        super().__init__(litellm_config)

    def build_system_prompt(self) -> str:
        return (
            "You are an expert evaluator judging whether a diagnostician's suggested_prompt_change "
            "is appropriately calibrated.\n\n"
            "You will be given:\n"
            "- A <judge_input> block (XML prompt, case input, model output, assessment).\n"
            "- A <judge_output> block containing the JudgeDiagnosis JSON.\n"
            "- A <criteria> list for this scenario.\n\n"
            "Two failure modes to detect:\n\n"
            "**Under-confident (null when fix is obvious):** The culprit node is a short paragraph or "
            "example that can be concretely rewritten, but suggested_prompt_change is null. The diagnostician "
            "should have provided a specific edit.\n\n"
            "**Over-speculative (non-null when cause is unclear):** The root cause is complex or systemic, "
            "but the diagnostician invents a specific rewrite anyway. The suggestion should be null.\n\n"
            "Produce a MetricResult with:\n"
            "- score: 1.0 if calibration is appropriate; 0.0 for clear miscalibration\n"
            "- assessment: concise narrative\n"
            "- signals: one IssueSignal per calibration error, citing the prompt node whose instructions "
            "should clarify when to include vs. omit a suggested change\n"
            "- preserve: aspects of the prompt that already calibrate suggestion confidence correctly"
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_hybrid_judge_metrics(judge_llm: LiteLLMConfig) -> list[Metric]:
    """Return all 5 evaluation metrics for the hybrid-judge target."""
    return [
        CulpritIdValidityMetric(judge_llm=judge_llm),
        CulpritLocalizationMetric(litellm_config=judge_llm),
        DiagnosisSpecificityMetric(litellm_config=judge_llm),
        ActionabilityMetric(litellm_config=judge_llm),
        SuggestedChangeCalibrationMetric(litellm_config=judge_llm),
    ]
