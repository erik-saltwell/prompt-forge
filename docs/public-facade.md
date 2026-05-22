# Public Facade — `prompt_model`

## Overview

The public facade of `prompt_model` is the import surface that callers (the apps layer, downstream tooling, custom metric authors) commit to. It exposes one entry point, `optimize_prompt`, a fluent configuration object, the metric and scoring protocols, two libraries of built-in implementations, and a progress reporting contract. Everything else — the parser, the action executor, the actor, the UCB harness internals — stays private.

## Key Concepts

**Entry point.** `optimize_prompt(config, metrics, scorer, progress_reporter) -> OptimizeResult` is the single async function the package exists to expose.

**OptimizerConfig.** A pydantic model with an immutable fluent API. Carries only primitives and collections of primitives (so it can be loaded from YAML at the apps layer): the seed prompt, the eval cases, three LLM configs (target / actor / judge), and tuning knobs (iterations, floor, UCB budget, top-K, concurrency). `.with_*` methods return new instances via `model_copy`. Helper variants (`with_seed_prompt_from_path`, `with_eval_cases_from_jsonl`) accept `Path` for caller convenience but the model itself stores strings.

**Three LLM roles.** Target (runs the prompt under optimization), actor (emits structural mutations), judge (default LLM for metrics). Each is a `LiteLLMConfig`. There is no separate critic LLM — each metric is its own critic and uses the judge by default. Metrics may override with their own `LiteLLMConfig` at construction.

**EvalCase.** The `(input, ground_truth, retrieval_context)` triple that drives evaluation. Lives on `OptimizerConfig.eval_cases`.

**Metric.** The protocol for "judge a single `(prompt, input, output, ground_truth)` case." Returns a `MetricResult` containing score, narrative assessment, structured `IssueSignal`s, and a `preserve` list.

**RewardStrategy.** The `scorer` argument. Collapses one pull's `list[MetricResult]` into a single scalar in `[0, 1]` for UCB to consume.

**Progress event.** A single in-flight event shape the caller's reporter receives.
- `ProgressEvent` — contains `run_progress`, `step_progress`, and `task_progress` nested models, plus optional `best_score`, `best_score_delta`, and `errors_so_far` snapshots.
- `RunProgress` — `current_run` / `total_runs`, using one-based counters for the optimizer's outer run loop.
- `StepProgress` — `current_step_name`, `current_step_id`, and `total_steps`, using one-based counters for the coarse phase within the current run.
- `TaskProgress` — `current_task_name`, `current_task_id`, and `total_tasks`, using one-based counters for fine-grained work inside the current step.

**ProgressReporter.** Type alias for `Callable[[ProgressEvent], Awaitable[None]]`. A single async callback. `None` means no reporting.

**OptimizeResult.** What `optimize_prompt` returns. Contains `best_prompt` (markdown string), `best_score`, `best_metrics` (per-metric mean scores), `top_k` (ranked `CandidateSummary` list, `top_k[0]` is the best), `iterations_run`, `total_errors`.

**CandidateSummary.** Per-candidate entry in `OptimizeResult.top_k`: `prompt` (markdown string), `score` (aggregated reward), `metrics` (per-metric mean scores).

## Flows

### Calling `optimize_prompt`

1. Caller constructs an `OptimizerConfig` — either directly, by chaining `.with_*` methods, or by loading YAML and applying overrides (`OptimizerConfig.model_validate(yaml_dict).with_target_llm(override)`).
2. Caller instantiates metrics from `prompt_model.metrics` (or custom ones implementing the `Metric` protocol).
3. Caller picks a `RewardStrategy` — typically one from `prompt_model.rewards`.
4. Caller defines a progress reporter (or passes `None`).
5. Caller awaits `optimize_prompt(config, metrics, scorer, progress_reporter)`.
6. Function returns `OptimizeResult`.

### Progress emission

- The reporter receives `ProgressEvent` values as the optimizer moves through each iteration's steps.
- Long-running steps (batch testing, actor fan-out) advance the nested `task_progress` fields so consumers can render fine-grained progress through pulls or actor calls.
- Iteration boundaries may carry `best_score` / `best_score_delta`.
- Non-fatal failures increment `errors_so_far`; fatal failures raise exceptions instead of emitting an event.

## Module Layout

**Root — `from prompt_model import ...`:**

- `optimize_prompt`, `OptimizeResult`, `CandidateSummary`
- `Metric`, `MetricResult`, `IssueSignal`, `BaseLLMJudgeMetric`, `MissingGroundTruthError`
- `RewardStrategy`
- `ProgressEvent`, `RunProgress`, `StepProgress`, `TaskProgress`, `ProgressReporter`

**`prompt_model.config`** — configuration types:

- `OptimizerConfig`
- `LiteLLMConfig`
- `EffortLevel`
- `EvalCase`

**`prompt_model.metrics`** — built-in metric implementations. Day-one inventory:

- `AnswerRelevancy` (LLM-judged)
- `Faithfulness` (LLM-judged, uses `retrieval_context`)
- `Correctness` (LLM-judged, uses `ground_truth`)
- `CustomCriterion` (GEval analog — caller supplies natural-language criterion)
- `JsonSchema` (non-LLM, validates output against a pydantic schema)

**`prompt_model.rewards`** — built-in reward strategies:

- `MeanReward`, `WorstReward`, `WeightedMeanReward`, `SingleMetricReward`, `GeometricMeanReward`

**Private (underscore-prefixed):** `_actions/`, `_actor/`, `_batch_testing/` (UCB harness internals), `_critic/`, `_prompt/` (Document tree), `_utils/`, `_llm/` (LiteLLM call helper).

## Behaviors & Rules

- **Three LLM configs are first-class on `OptimizerConfig`:** target, actor, judge. `BaseLLMJudgeMetric` accepts `LiteLLMConfig | None`; `None` means "use the default judge."
- **YAML-loadable config holds primitives only.** `OptimizerConfig` does not carry code objects. Metrics, reward strategy, and progress reporter are passed as separate arguments to `optimize_prompt` because they are code, not data.
- **Fluent methods return new instances.** `OptimizerConfig` is effectively immutable from the caller's perspective; `.with_*` uses `model_copy(update=...)` under the hood.
- **From-path helpers are convenience only.** They load file contents into the same string fields the model stores. The model itself never references a `Path`.
- **`Document` is not in the public API.** Result objects expose conforming markdown strings. Callers who want the parsed tree call the parser themselves on the returned string.
- **Metric library implementations are native, not DeepEval wrappers.** Built on `BaseLLMJudgeMetric` so each metric can emit rich `IssueSignal`s rather than a flattened `(score, reason)` pair.
- **The judge is shared by default, overridable per metric.** A metric constructor accepts its own `LiteLLMConfig` for cases where one metric needs a different model than the rest.
- **`acomplete` (LiteLLM call helper) is private.** Custom metric authors extend `BaseLLMJudgeMetric` rather than calling LiteLLM directly through our facade.
- **Progress reporting is push-only via a single async callback.** No Protocol with named methods, no async iterator. `None` is a valid value and means "no reporting."
- **`ProgressEvent` is a single stable shape with nested progress scopes.** Run, step, and task progress are always reported through their own nested models; optional score and error snapshots are included when available.
- **Top-level imports cover the 80% case.** Subpackage paths (`prompt_model.config`, `prompt_model.metrics`, `prompt_model.rewards`) cover discovery for the long tail.

## Open Questions

None — all design decisions were resolved during the brainstorm.
