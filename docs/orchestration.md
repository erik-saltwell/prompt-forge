# Orchestration Layer

## Overview

The orchestration layer is the public entry point to the optimizer. It accepts a seed prompt, a set of evaluation cases, a list of metrics, and a reward scorer; runs an iterative critic-actor-improve loop; and returns the highest-scoring prompt found. The loop is a generational search: each iteration revises a top-k slice of the current candidate pool to produce children, then evaluates the merged pool (survivors plus children) to score them for the next round.

## Key Concepts

**Candidate** — A prompt under consideration, paired with its accumulated evaluation results, sum-of-scores, tested count, and remaining `case_ids` to test. Defined in `_candidate`. Carries forward across iterations once it has survived a round.

**Pool** — The set of `Candidate`s under active consideration at a given moment. Grows when revise adds children, shrinks when top-k truncates survivors.

**Survivor** — A pool member that made the top-k cut after evaluation in some iteration and is therefore eligible to be revised.

**Child** — A new `Candidate` wrapping a `Document` returned by `Actor.revise()` of a survivor. Always starts unscored.

**Generation** — The pool snapshot at the start of an iteration's evaluation phase: `survivors ∪ children`.

**Bootstrap** — The pre-loop phase that evaluates the seed prompt before the first revise. Sized by `seed_warmup_pulls`.

**Bucket** — Internal to the Actor. One bucket per accused `culprit_node_id` aggregated from a candidate's results. One bucket produces at most one child. The orchestration layer never sees buckets directly — it just sees the list of children returned by `revise()`.

**Scorer / `CompositeScorer`** — A code object that combines a `MetricResult` set into a single reward in `[0, 1]`. Supplied as an argument to `optimize_prompt`. Default is `MeanScorer()`.

**Reward** — `Candidate.mean_score`: the candidate's sum-of-scores divided by tested count, where each per-case score is the scorer applied to that case's `MetricResult` list.

**Floor-cleared** — A candidate is floor-cleared once `tested_count >= floor`. Final-result selection and ranking are restricted to floor-cleared candidates.

**Early-stop** — A loop-termination signal raised before `config.iterations` exhausts. Two triggers: no-improvement-over-patience, and empty-revise (no actor produced any child).

## Flows

### `optimize_prompt(config, metrics, scorer=MeanScorer(), progress_reporter=None) -> OptimizationResult`

1. **Bootstrap.**
   - Construct the initial `Candidate` from `parse_from_string(config.seed_prompt)` with a fresh shuffled copy of `config.eval_cases`.
   - Pool = `[seed_candidate]`.
   - Evaluate the seed for `config.seed_warmup_pulls` pulls. No UCB selection needed — single candidate.

2. **Iteration loop, up to `config.iterations` times.** For each iteration:
   - **Step `revise`:** Rank the pool by `mean_score` (floor-cleared candidates only); take the top `top_k_per_iteration` as survivors. For each survivor, call `Actor.revise(...)`, capping the number of children per parent at `max_children_per_parent`. Wrap each returned `Document` into a fresh `Candidate` with a fresh shuffled copy of `config.eval_cases`, zero results, zero tested count.
   - **Step `evaluate`:** Pool = survivors ∪ children. Run `select_top_candidates` over the pool: floor pulls first, then UCB pulls up to `ucb_budget`. Survivors' prior results carry forward — UCB naturally allocates more pulls to the (low-n) children.
   - **Early-stop check:**
     - If every survivor's revise returned `[]` (no buckets across the pool): terminate.
     - If the pool's best `mean_score` has not improved by at least `min_improvement_delta` over the last `early_stop_patience` iterations: terminate.

3. **Final selection.** From the final pool, restrict to floor-cleared candidates. Pick `best_prompt` as the candidate with the highest `mean_score`. `top_k` is the same pool sorted by `mean_score`, truncated to `top_k_per_iteration`. `top_k[0] == best_prompt` is invariant.

4. **Return** an `OptimizationResult` populated with best prompt (as conforming markdown), best score, per-metric means for the best candidate, top-k summaries, completed iteration count, and total eval errors observed.

### Per-iteration shape (for progress events)

Per iteration, two `StepProgress` steps fire in order: `"revise"`, then `"evaluate"`.

- `"revise"` tasks: one per bucket pipeline. `total_tasks` = sum of buckets across survivors, after the per-parent cap.
- `"evaluate"` tasks: one per pull. `total_tasks` = `pool_size * floor + ucb_budget`.

The bootstrap fires one `"evaluate"` step with `total_tasks = seed_warmup_pulls`.

## Behaviors & Rules

### Pool dynamics
- The initial pool contains the seed only. Iterations 2+ have a pool size between `1 + 1` (one survivor, one child) and `top_k_per_iteration + top_k_per_iteration * max_children_per_parent` (worst case).
- `top_k_per_iteration` bounds **survivors**, not the full pool. Children join unranked and are ranked at the next iteration's evaluation phase.
- Children get a **fresh shuffled copy of all eval cases**; they do not inherit parent results or case ids. Their scores are independently sampled.
- Survivors **carry their results, sum-of-scores, tested count, and remaining `case_ids` forward** across iterations. UCB across the merged pool naturally favors testing fresh children over re-testing well-tested survivors.

### Revise behavior
- Each surviving parent is revised once per iteration. The actor's per-bucket fan-out produces zero or more sibling-branch `Document`s.
- Per-parent child production is capped at `max_children_per_parent`. When the actor's bucket count exceeds the cap, buckets are ranked by signal count or aggregated severity and the top buckets are revised.
- Children are siblings of the parent, never a serial chain — each child applies to a fresh clone of the parent prompt.
- If `revise()` returns `[]` for every survivor in an iteration, the loop early-stops. Re-evaluating an unchanged pool can't produce new buckets.

### Evaluation behavior
- `select_top_candidates` runs every iteration: floor pulls every below-floor candidate up to `floor`, then UCB allocates `ucb_budget` additional pulls weighted by uncertainty.
- `error_budget` is **per iteration**. Each iteration's evaluation phase tolerates up to `error_budget` failed pulls before raising. The budget resets at the start of each iteration.
- Actor transport errors propagate and kill the run (per the Actor module's contract); they are not covered by `error_budget`.

### Final selection
- `best_prompt` is the highest `mean_score` among floor-cleared candidates in the final pool. Unfloored candidates (e.g., last-iteration children that didn't reach floor) are excluded.
- `top_k` is drawn from the final pool only, ranked by the same criterion.
- `best_metrics` is per-metric mean across the best candidate's accumulated `MetricResult`s, keyed by `metric_name`.

### Reproducibility
- `config.seed`, when set, seeds the case-shuffle in `Candidate.__post_init__` and any UCB tiebreaks. With deterministic LLMs (temperature 0) the loop becomes reproducible up to LLM-provider noise.
- Without a seed, two identical configs can take different paths because case-sampling order shuffles independently per candidate.

### Concurrency
- A single `max_llm_concurrency` value caps both the evaluation phase (target-LLM calls) and the revise phase (actor / structural-LLM calls). The two phases run sequentially per iteration and never compete for the cap.

### Iteration accounting
- `OptimizationResult.iterations_run` counts **completed** iterations only. An iteration cut short by transport failure or early-stop mid-step is not counted.
- `OptimizationResult.total_errors` counts **evaluation errors only** — the same failures `error_budget` tracks. Actor schema/parse drops are not surfaced here (they're a normal skip-and-continue outcome inside the actor).

## Config Surface

`OptimizerConfig` additions on top of what already exists:

- `seed_warmup_pulls: int` — bootstrap eval pulls on the seed before iteration 1.
- `max_children_per_parent: int` — cap on revise children per survivor per iteration.
- `min_improvement_delta: float = 0.005` — early-stop threshold on best-score improvement.
- `early_stop_patience: int = 3` — iterations of no-improvement before early-stop fires.
- `structural_llm: LiteLLMConfig | None = None` — if set, used for the actor's structural pass; otherwise falls back to `actor_llm`.
- `seed: int | None = None` — optional RNG seed for case shuffling and UCB tiebreaks.
- `max_concurrency` renamed to `max_llm_concurrency` and now governs both evaluation and revise phases.

`optimize_prompt` signature:

```python
async def optimize_prompt(
    config: OptimizerConfig,
    metrics: list[Metric],
    scorer: CompositeScorer = MeanScorer(),
    progress_reporter: ProgressReporter = None,
) -> OptimizationResult:
    ...
```

## Open Questions

None — all design decisions were resolved during the brainstorm.
