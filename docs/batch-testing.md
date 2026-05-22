# Batch Testing

## Overview

Batch Testing evaluates a set of candidate prompts against a set of evaluation cases using one or more metrics, and returns the top-K prompts ranked by aggregated metric scores. Evaluation is allocated via UCB1 — every prompt receives a floor of evaluations, after which a bounded budget of additional evaluations is spent on the prompts that look most promising. The harness produces target outputs itself (via LiteLLM) and feeds them to caller-supplied metrics; it does not mutate prompts.

---

## Key Concepts

**Candidate** — A prompt `Document` under evaluation. Identity is the `Document` instance itself; no separate ID is assigned.

**EvalCase** — One evaluation input. Shape: `EvalCase(input: str, ground_truth: str | None = None, retrieval_context: list[str] | None = None)`. Metrics that need `ground_truth` or `retrieval_context` read it from here.

**Pull** — One unit of work: pick a candidate, pick an input it has not yet been evaluated on, call the target LLM to produce an output, then run every metric against `(prompt, input, output, ground_truth)`. Produces one `MetricResult` per metric.

**Arm** — A candidate. UCB1 treats each candidate as an arm; each pull samples one input for that candidate **without replacement**. A candidate whose inputs are exhausted is removed from the bandit.

**Floor** — The minimum number of pulls every candidate receives before UCB starts allocating extras. Guarantees a baseline signal-to-noise per candidate and protects against premature elimination from one unlucky input. Caller-supplied.

**UCB Budget** — The number of pulls allocated *after* the floor is satisfied, distributed by UCB1. Total pulls in a run = `floor × num_candidates + ucb_budget`, capped at the total `(candidate, input)` cell count.

**Exploration Bonus** — The `c` constant in UCB1's `score + c × sqrt(2 ln N / n_arm)`. Caller-tunable; default `sqrt(2)`.

**RewardStrategy** — A protocol that collapses one pull's `list[MetricResult]` into a single float in `[0, 1]` for UCB to consume. Built-in strategies: `MeanReward`, `WorstReward`, `WeightedMeanReward(weights: dict[str, float])`, `SingleMetricReward(metric_name: str)`, `GeometricMeanReward`. Strategies always return a float — vetoes are not allowed.

**LiteLLMConfig** — Shared LLM-call configuration used by both the target call and any LLM-judge metric. Typed common fields: `model`, `temperature`, `max_tokens`, `timeout`, `effort` (maps to LiteLLM's `reasoning_effort`), `api_base`, `api_key`. An `extra: dict` bag carries less common kwargs through to LiteLLM. Typical callers construct two — one cheap+fast for the target, one stronger for the judge.

**Error Budget** — Caller-supplied cap on metric failures (absolute count or fraction). When a metric raises (e.g., `ground_truth` missing), the pull is **discarded**, does not count against UCB, and a replacement pull is scheduled. If errors exceed the budget, the whole run aborts with an exception.

---

## Flows

### Single run
1. Caller invokes the harness with: candidates, eval cases, metrics, `LiteLLMConfig` for the target, `RewardStrategy`, `floor`, `ucb_budget`, `top_k`, `max_concurrency`, `exploration_bonus`, `error_budget`, optional `seed`.
2. The harness initialises UCB state: every candidate starts with zero pulls and an empty set of "inputs already seen."
3. **Floor phase.** Schedule `floor × num_candidates` pulls — every candidate gets `floor` distinct inputs (sampled without replacement per candidate). Pulls run concurrently, bounded by `max_concurrency`.
4. **UCB phase.** While `ucb_budget` remains and at least one candidate still has unused inputs:
   - Compute the UCB score for every eligible (non-exhausted) candidate using current observed rewards.
   - Pick the highest-scoring candidate; when an arm has a pull in flight, count it via a virtual visit so the same arm is not picked twice immediately.
   - Sample a fresh input for that candidate, launch the pull, decrement `ucb_budget`.
5. **Pull execution.** For one pull:
   - Call the target LLM with `(prompt_markdown, input)` to obtain `output`.
   - Run every metric concurrently against `(prompt, input, output, ground_truth)`.
   - On any metric failure: discard the pull's reward, do not update UCB stats, increment the error counter, schedule a replacement pull at the same arm.
   - On success: apply `RewardStrategy.compute(results)` to get the scalar reward; update the candidate's mean and visit count.
6. **Selection.** Once all pulls complete (or the budget is exhausted, or all cells covered), rank candidates that met the floor by mean reward. Return the top `top_k` as `list[(Document, list[MetricResult])]`, where the inner list is the **flat concatenation of every `MetricResult` produced for that candidate** across every pull. Downstream aggregation (see `metric-aggregation.md`) handles the rest.

### Failure handling
- Single metric failure → discard pull, retry same arm, log to error counter.
- Total errors exceed `error_budget` → raise, do not return partial results.
- Target LLM failure → treated identically to a metric failure (discard + retry + count).

---

## Behaviors & Rules

- **No mutation.** The harness evaluates and selects only. Prompts are not edited mid-run; the actor/aggregator pipeline (see `metric-aggregation.md`) is a separate concern that consumes this module's output.
- **Inputs sampled without replacement per candidate.** A `(candidate, input)` cell is never evaluated twice. Re-sampling for judge-noise reduction is out of scope — input variance dominates.
- **Floor first, UCB after.** UCB never runs before every candidate has met the floor. A candidate that hit the floor but did not earn UCB extras is still eligible for top-K — UCB elected to confirm leaders, not eliminate that candidate.
- **Top-K eligibility = met floor.** Candidates with fewer than `floor` successful pulls are excluded from top-K but may still appear ranked below it.
- **`top_k` drops non-selected candidates from the return.** When the caller passes `top_k=None`, the return contains every floor-eligible candidate ranked.
- **Budget is capped at coverage.** If `floor × num_candidates + ucb_budget` exceeds the total available cells, the harness silently caps at full coverage and records actual pulls used. Hitting the cap is full evaluation, not failure.
- **Concurrency tolerates stale UCB stats.** Decisions made while pulls are in flight use current observed rewards plus a virtual-visit bump on in-flight arms. Determinism under concurrency is best-effort; bit-identical reproducibility requires `max_concurrency=1`.
- **Reward strategies see partial result lists.** When metrics fail, the strategy never runs — the pull is discarded entirely. When all metrics succeed, the strategy receives the full `list[MetricResult]` and must return a float.
- **Metric identity travels on `MetricResult`.** `MetricResult` carries a `metric_name` field stamped by the harness so strategies like `WeightedMeanReward` and `SingleMetricReward` can route by name without parallel metadata.
- **LiteLLM is the LLM-call surface for both target and metrics.** Both accept `LiteLLMConfig`; the typed fields surface common knobs (notably `effort`), and the `extra: dict` bag passes anything else through to LiteLLM verbatim.
- **Return shape is flat.** `list[(Document, list[MetricResult])]`. The inner list contains every `MetricResult` from every successful pull on that candidate; no per-input or per-metric aggregation is performed by this module.

---

## Open Questions

None — all decisions were resolved during the brainstorm.
