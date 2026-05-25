# Metric Library

## Overview

The metric library is a set of LLM-judge metrics that evaluate a single `(prompt, input, output, ground_truth)` case and return a `MetricResult` — a normalized score, a narrative assessment, a list of `IssueSignal`s localized to prompt node IDs, and a `preserve` list of things working well. Metrics are the leaf units of the critic subsystem; aggregation across cases happens upstream. The library ships five concrete metrics derived from deepeval's evaluation patterns, adapted to produce actionable, node-localized feedback for the prompt optimizer's actor.

## Key Concepts

**Metric** — An async callable that takes `(prompt, input, output, ground_truth | None)` and returns a `MetricResult`. Each metric is a focused, single-concern judge.

**MetricResult** — The structured output of one `evaluate` call. Contains `score` ([0,1], higher is better), `assessment` (narrative), `signals` (list of `IssueSignal`s), and `preserve` (guardrail list).

**IssueSignal** — A specific evidenced complaint about the prompt, localized to one `culprit_node_id` (a real prompt node ID or the `"document"` sentinel). Carries `rationale`, `target_behavior`, `success_criterion`, optional `suggested_prompt_change`, and verbatim `input_snippet` / `output_snippet`.

**Critic markdown rendering** — Before the judge LLM sees the prompt, it is rendered with `<!-- id -->` HTML comment overlays (one per addressable node). This is what enables `culprit_node_id` to reference real tree nodes rather than defaulting to the `"document"` sentinel. Rendering is handled by an injected `RenderPromptStrategy`; the default is `MarkdownRenderPromptStrategy` (critic form).

**Claim** — An atomic factual assertion extracted from the model output. Used by `BaseClaimMetric` as the unit of per-claim verdict evaluation.

**Reference points** — The trusted facts or key points against which claims are checked. Source depends on the metric: `input` for alignment, `ground_truth` for coverage.

## Base Classes

Three base classes cover the distinct evaluation patterns:

### `BaseLLMJudgeMetric`
Single structured LLM call → `MetricResult`. The base class:
- Parses the prompt string, renders it via the injected `RenderPromptStrategy` (default: critic markdown with ID overlays)
- Calls `acomplete` with `response_format=MetricResult` (structured output — no raw text parsing)
- Stamps `metric_name` on the result

Subclasses provide:
- `build_system_prompt() -> str` (required)
- `build_user_prompt(rendered_prompt, input, output, ground_truth) -> str` (optional override; base supplies a standard `<prompt>`, `<input>`, `<output>`, `<ground_truth>` layout)

### `BaseClaimMetric`
Four-step pipeline for claim-by-claim evaluation. Proven approach for summarization metrics; preserves the decomposed precision that single-call evaluation loses.

Steps:
1. **Extract claims** — LLM call extracts atomic assertions from `output`
2. **Extract reference points** — LLM call extracts trusted facts/key points from `input` (alignment) or `ground_truth` (coverage)
3. **Verdicts** — LLM call checks each claim against reference points; each failing verdict carries a reason
4. **Node attribution** — single batched LLM call receives all failing verdicts + the critic-markdown-rendered prompt; returns `(claim, culprit_node_id)` pairs

Score = fraction of passing verdicts. Each failing verdict becomes one `IssueSignal`.

Subclasses provide template methods for each step's prompt:
- `claim_extraction_prompt(output) -> str`
- `reference_extraction_prompt(input, ground_truth) -> str`
- `verdict_prompt(claims, references) -> str`

### `HybridMetric`
Existing base class. Deterministic score + optional LLM judge. Used for `json_correctness` where validity can be checked programmatically and the judge only fires on failure.

## Concrete Metrics

| Metric | Base | ground_truth required | Context source |
|---|---|---|---|
| `AlignmentMetric` | `BaseClaimMetric` | No | Reference = `input` |
| `CoverageMetric` | `BaseClaimMetric` | Yes | Reference = `ground_truth` |
| `HallucinationMetric` | `BaseLLMJudgeMetric` | No | Context = `input` |
| `GEvalMetric` | `BaseLLMJudgeMetric` | Optional | Criterion-dependent |
| `JsonCorrectnessMetric` | `HybridMetric` | No | — |

**AlignmentMetric** — Checks whether claims in the output are faithful to the source text (`input`). Semantics tuned and validated for summarization. "Alignment" here means the output does not contradict or fabricate relative to the input.

**CoverageMetric** — Checks whether the output covers the key points in the reference (`ground_truth`). Semantics tuned and validated for summarization. Measures omission rather than contradiction.

**HallucinationMetric** — General-purpose grounding check. Checks whether the output contains facts not supported by `input`. Not summarization-specific; applicable to any context-grounded generation task.

**GEvalMetric** — Configurable single-criterion judge. Constructed with one `criteria: str` that describes what to evaluate. Multiple criteria → multiple `GEvalMetric` instances. Does not attempt to replicate the domain knowledge baked into the named metrics.

**JsonCorrectnessMetric** — Deterministic validity check (is the output parseable JSON?) plus optional schema conformance. Judge fires only on failure to produce a node-localized `IssueSignal`.

## Behaviors & Rules

- **All metrics populate `preserve` opportunistically.** If the judge observes something clearly working (e.g. 9/10 claims are valid), it notes those in `preserve`. No metric is expected to populate it exhaustively.
- **`RenderPromptStrategy` is injected, not hardcoded.** Default is `MarkdownRenderPromptStrategy`. Subclasses or callers may substitute XML or JSON rendering.
- **`BaseClaimMetric` node attribution is batched.** All failing verdicts for one case are attributed in a single LLM call, not one call per verdict.
- **`HallucinationMetric` never requires `ground_truth`.** Its context is `input`; `ground_truth` is unused.
- **`CoverageMetric` raises a typed exception when `ground_truth` is `None`.** This is a configuration error, not a soft skip.
- **`GEvalMetric` takes exactly one criterion.** For multi-criteria evaluation, instantiate multiple `GEvalMetric`s.
- **Multiple `IssueSignal`s per case are expected.** `signals` is a list; claim-based metrics produce one signal per failing claim; judge-based metrics produce as many as the LLM identifies.
- **`culprit_node_id` defaults to `"document"` when localization fails.** The node attribution step makes a best-effort attempt; the sentinel is the fallback.
- **`goal_accuracy` is not in scope.** It is a conversational/multi-turn metric and does not fit the single-turn `(prompt, input, output, ground_truth)` contract.

## Open Questions

- **Alignment vs. hallucination overlap in non-summarization tasks.** For tasks where `input` is both the source document and the context, alignment and hallucination may produce redundant signals. Whether to deduplicate upstream or leave it to the aggregator is unresolved.
- **Single-call quality for `HallucinationMetric`.** Unlike alignment and coverage, hallucination uses a single structured call. Whether this matches multi-step precision for grounding tasks has not been benchmarked.
