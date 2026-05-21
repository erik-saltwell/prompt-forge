# Critic Metric Interface

## Overview
A metric is a single, focused judgment applied to one evaluation case — a `(prompt, input, output, ground_truth)` tuple — producing a normalized score, a narrative summary, structured issue signals, and preservation signals. Metrics are the leaf units of the critic subsystem; aggregation across cases or across metrics happens elsewhere.

## Key Concepts

- **Metric** — A protocol with stable identity (`name`, `description`) and one async behavior: `evaluate`. Implementations are typically LLM-judge calls but may be pure-compute.
- **Evaluation Case** — The tuple `(prompt, input, output, ground_truth | None)`. The harness generates `output` from `prompt` + `input` once and fans it out to metrics; metrics never run the model themselves.
- **MetricResult** — The structured output of a single `evaluate` call. Also the schema the judge LLM returns under structured output.
- **IssueSignal** — A specific, evidenced complaint about the prompt, optionally localized to one or more prompt nodes, optionally accompanied by improvement guidance.
- **ImprovementGuidance** — Per-issue direction for the actor LLM: what good looks like, and (when known) how to change the prompt to get there.
- **Preserve** — Things about the current prompt that are working and should not be broken by edits. Lives at the result level, applies regardless of score.

## Flows

### Evaluating a case
1. Harness assembles `(prompt, input, output, ground_truth | None)`.
2. Harness calls `await metric.evaluate(prompt, input, output, ground_truth)`.
3. If the metric requires `ground_truth` and it is `None`, the metric raises a typed exception; the harness skips and continues.
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
- Identity lives in code, not in the LLM response: `name: ClassVar[str]`, `description: ClassVar[str]`. Neither field appears in `MetricResult`.
- Does not generate the model output. Receives it.
- Metrics requiring `ground_truth` raise a typed exception when it is missing rather than declaring the requirement statically.

### Score
- Always `[0, 1]`, higher is better. Pass/fail metrics encode as `1.0` / `0.0`. Normalization is the metric author's responsibility and is part of the metric's value judgment.

### Assessment
- Required, non-empty narrative summary of the metric's judgment for this case.
- Present at every score level, not only when there are issues. On a perfect score it describes what the metric saw and approved of.

### Signals
- Zero or more `IssueSignal`s per result. Empty list means no issues found.
- Each signal carries: suspected culprit prompt nodes (`list[str]`, possibly empty when unlocalizable), input snippets, output snippets, rationale, and an `ImprovementGuidance`.
- `ImprovementGuidance` requires `target_behavior` and `success_criterion`. `suggested_prompt_change` is optional — a metric may flag a problem without prescribing the fix.

### Preserve
- Top-level `MetricResult.preserve: list[str]`. Single source of truth for "what's working that an edit must not break."
- No per-issue preservation field exists; preservation is not duplicated inside `ImprovementGuidance`.

## Open Questions
None surfaced during the brainstorm.
