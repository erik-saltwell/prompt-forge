# Critic Metric Interface

## Overview
A metric is a single, focused judgment applied to one evaluation case — a `(prompt, input, output, ground_truth)` tuple — producing a normalized score, a narrative summary, structured issue signals, and preservation signals. Metrics are the leaf units of the critic subsystem; aggregation across cases or across metrics happens elsewhere.

## Key Concepts

- **Metric** — A protocol with stable identity (`name`, `description`) and one async behavior: `evaluate`. Implementations are typically LLM-judge calls but may be pure-compute.
- **Evaluation Case** — The tuple `(prompt, input, output, ground_truth | None)`. The harness generates `output` from `prompt` + `input` once and fans it out to metrics; metrics never run the model themselves.
- **MetricResult** — The structured output of a single `evaluate` call. Also the schema the judge LLM returns under structured output. Carries `metric_name` (set to the producing metric's `name`), `score`, `assessment`, `signals`, and `preserve`.
- **IssueSignal** — A specific, evidenced complaint about the prompt, localized to exactly one prompt node (or the `"document"` sentinel when not node-localizable). Carries verbatim input/output snippets, a rationale, and the flattened improvement-guidance fields. See `metric-aggregation.md` for the full field list and the dedupe behavior the aggregator applies downstream.
- **Preserve** — Things about the current prompt that are working and should not be broken by edits. Lives at the result level, applies regardless of score.

## Flows

### Evaluating a case
1. Harness assembles `(prompt, input, output, ground_truth | None)`.
2. Harness calls `await metric.evaluate(prompt, input, output, ground_truth)`.
3. If the metric requires `ground_truth` and it is `None`, the metric raises a typed exception; the harness treats this as a configuration or coding error and surfaces the failure.
4. Otherwise the metric returns a `MetricResult` containing score, assessment, signals, and preserve.

### Consuming a result
- Score is the headline figure, always in `[0, 1]`, higher is better.
- Assessment is the prose summary, read first by humans and by the actor LLM.
- Signals are the structured complaints, each with evidence and (optionally) improvement guidance.
- Preserve is the guardrail list — things to keep intact during any prompt edit.

## Behaviors & Rules

### Metric protocol
- Async only: `async def evaluate(...) -> MetricResult`.
- Operates on a single case per call. Batching and cross-case aggregation are out of scope.
- Identity lives in code: `name: ClassVar[str]`, `description: ClassVar[str]`. The `name` is denormalised onto each `MetricResult` as `metric_name` so downstream consumers (reward strategies, the aggregator) can key off it without a parallel registry. `description` does not appear on `MetricResult`.
- Does not generate the model output. Receives it.
- Metrics requiring `ground_truth` raise a typed exception when it is missing. This is not a soft skip: callers should supply compatible evaluation cases for the metrics they configure.
- LLM-judge metrics should accept a `LiteLLMConfig` (see `batch-testing.md`) in their constructor so the same call surface is used by the batch harness and the judge. The provided `BaseLLMJudgeMetric` base class implements this pattern — subclasses supply `build_messages` and `parse_result` and the base wires up the LiteLLM call and stamps `metric_name=cls.name` automatically.

### Score
- Always `[0, 1]`, higher is better. Pass/fail metrics encode as `1.0` / `0.0`. Normalization is the metric author's responsibility and is part of the metric's value judgment.

### Assessment
- Required, non-empty narrative summary of the metric's judgment for this case.
- Present at every score level, not only when there are issues. On a perfect score it describes what the metric saw and approved of.

### Signals
- Zero or more `IssueSignal`s per result. Empty list means no issues found.
- Each signal carries: a single `culprit_node_id` (a real prompt node id, or the `"document"` sentinel when not localizable to a specific node), `rationale`, `target_behavior`, `success_criterion`, optional `suggested_prompt_change`, and verbatim `input_snippet` + `output_snippet` quoted from the case being evaluated.
- `target_behavior` and `success_criterion` are required. `suggested_prompt_change` is optional — a metric may flag a problem without prescribing the fix.
- `seen_in_n_cases` is a field on `IssueSignal` defaulted to `1`; the critic always emits the default. The aggregator increments it when collapsing duplicates across cases (see `metric-aggregation.md`).
- Cross-node issues are expressed as **two independent peer signals**, one per culprit, each with the cross-reference written into its own rationale. The schema does not allow listing multiple suspects on a single signal.

### Preserve
- Top-level `MetricResult.preserve: list[str]`. Single source of truth for "what's working that an edit must not break."
- No per-issue preservation field exists; preservation is not duplicated on `IssueSignal`.

## Open Questions
None surfaced during the brainstorm.
