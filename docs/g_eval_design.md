# G-Eval Metric

## Overview

A configurable, single-criterion LLM-judge metric inspired by the G-Eval paper. Given one criterion expressed in natural language, the metric scores a `(prompt, input, output, ground_truth?)` evaluation case on a 1–5 scale and, when the judge's provider exposes them, weights that score by the model's top-token log-probabilities to produce a real-valued expected score. The metric is paired with an LLM-driven factory that turns a bare criterion string into a fully realised judging context (evaluation steps, scoring rubric, reference-required flag), cached so repeat use of the same criterion is free.

## Key Concepts

**Criterion** — A natural-language string describing one judgment dimension (e.g. *"The output must be under 50 words."*, *"The output must be factually consistent with the reference answer."*). One criterion → one `GEvalMetric` instance.

**PromptContext** — The cached, per-criterion runtime object the judge prompt is rendered from. Fields:
- `criterion: str`
- `evaluation_steps: list[str]` — the judge's reasoning scaffold, always populated.
- `scoring_rubric: list[ScoringRubric]` — banded rubric (1–5 entries) describing what each score band means; always populated, banding may be coarse.
- `requires_ground_truth: bool` — set by the factory based on the criterion.

The score range is fixed at 1–5 globally and is not stored on `PromptContext`.

**ScoringRubric** — One band of the rubric: a `ScoreRange` (sub-band within 1–5) and the prose `expected_outcome` describing that band. Bands need not cover all five integer scores individually — coarse banding is allowed.

**PromptContextDraft** — The factory's structured output. Distinct from `PromptContext` so the factory's response surface can be evolved independently. Shape: `{reasoning, evaluation_steps, scoring_rubric, requires_ground_truth}`, with `reasoning` declared first.

**Factory** — Module-level function that turns a criterion + factory `LiteLLMConfig` into a `PromptContext`. Uses a stronger model than the rest of the optimizer.

**PromptContext cache** — Module-level `LRUCache(maxsize=256)`. Key: `(criterion, factory_model_id)`. Per-key locking via a `defaultdict(threading.Lock)` so two threads requesting the same criterion serialise on the LLM call, while threads requesting different criteria run in parallel.

**Judge response** — The structured object the judge LLM returns. Shape, in declared order:
```
{score: int(1..5), assessment: str, signal: IssueSignal | None, preserve: list[str]}
```
`score` must be declared first so its single-digit token is the one whose logprobs are read.

**Logprob-aware score extraction** — On providers that expose `top_logprobs`, the final score is `Σ_i P(token_i) * int(token_i)` over the score-token position, renormalised across `{"1","2","3","4","5"}`. On providers that do not, the bare integer is used.

## Flows

### 1. Constructing a metric

1. Caller provides a criterion string, the judge `LiteLLMConfig`, and the factory `LiteLLMConfig`.
2. `GEvalMetric.__init__` derives its `name` from a SHA-256 digest of the criterion (so multiple instances stay distinct).
3. `PromptContext` is *not* built eagerly — the factory call is deferred to the first `evaluate` call.

### 2. PromptContext production (factory call)

1. Caller asks the factory module for a `PromptContext` for `(criterion, factory_llm_config)`.
2. Cache lookup on `(criterion, factory_model_id)`. Hit → return.
3. Miss → acquire the per-key lock.
4. Inside the lock, re-check the cache (another thread may have populated it while we waited).
5. Render the factory jinja template (`_resources/context_factory_prompt.j2`) with the criterion.
6. Call the factory LLM with `response_format=PromptContextDraft`. The model emits `reasoning` first, then the three substantive fields.
7. Promote the draft to a `PromptContext` (drop `reasoning`).
8. Store in the cache, release the lock, return.

### 3. Evaluating a case

1. Harness calls `await metric.evaluate(prompt, input, output, ground_truth)`.
2. Metric obtains the `PromptContext` (cached, see flow 2).
3. If `context.requires_ground_truth and ground_truth is None`: raise a typed exception (harness treats this as a config error).
4. Render the judge jinja template (`_resources/user_prompt.j2`) with the `PromptContext` and the case content. The prompt's tree is rendered in **critic form** (conforming markdown with `<!-- id -->` HTML-comment overlay) so the judge can cite `culprit_node_id`s.
5. Call the judge LLM with `response_format={score, assessment, signal, preserve}`, `temperature=1`, `logprobs=True`, `top_logprobs=5`.
6. Extract the final score:
   - If logprobs are present at the score-token position: compute the weighted expected value across `{"1".."5"}`, renormalising. Log a warning if <90% of probability mass falls on numeric tokens.
   - Else: use the bare integer.
7. Normalise the score to `[0, 1]` (constant 1–5 range → `(score - 1) / 4`).
8. Assemble a `MetricResult`:
   - `metric_name` = this instance's name
   - `score` = normalised float
   - `assessment` = the judge's assessment field
   - `signals` = `[signal]` if non-null, else `[]`
   - `preserve` = the judge's preserve list

## Behaviors & Rules

- **Fixed score range, 1–5.** The single-token logprob trick requires a single-digit score; 1–5 is the global, non-configurable range. `PromptContext` does not carry a `score_range` field. `ScoringRubric.score_range` retains its sub-band role.
- **Score field is emitted first.** This is the load-bearing structural constraint of the judge schema. Field reordering breaks logprob extraction.
- **No pre-score chain-of-thought.** Because the score token must come first in the JSON, the judge cannot reason before committing the score. The `assessment` field is post-score rationalisation. The factory call still uses CoT (via its leading `reasoning` field) because the factory is unconstrained by logprob extraction.
- **One signal at most per evaluation.** The schema's `signal` is singular (or `None`). A monolithic criterion does not naturally factor into multiple sub-issues. The adapter wraps the singleton into `MetricResult.signals` as a list of zero or one.
- **Critic-form rendering for the prompt.** `IssueSignal.culprit_node_id` must reference a real node ID; the judge cannot cite IDs it cannot see. The prompt is rendered with `<!-- id -->` comments accordingly.
- **Logprob fallback is provider-driven, not configured.** The metric inspects the LLM response. If `logprobs` is populated, the weighted extraction runs; otherwise the bare integer is used. No user-visible knob.
- **`top_logprobs=5`, `temperature=1`, renormalise across `{"1".."5"}`.** Mass falling outside the numeric set is dropped (with a warning if it exceeds 10%). Lower temperatures would collapse the distribution onto the argmax and defeat the weighting.
- **Factory always emits both lists and the flag.** `evaluation_steps` and `scoring_rubric` are both required outputs; `requires_ground_truth` is a required boolean. The rubric may be coarsely banded.
- **Cache key includes the factory model id.** Swapping factory models invalidates entries automatically. To force broader invalidation (e.g., factory template change), bump a module-level cache-version constant into the key tuple.
- **Per-key locking on the cache.** Same-criterion requests from concurrent threads serialise on one LLM call; different-criterion requests run in parallel.
- **No TTL on the cache.** The factory output is a pure function of `(criterion, model_id)`; the LRU bound is sufficient.
- **`GEvalMetric` is standalone.** It does not extend `BaseLLMJudgeMetric`. The module owns its own LLM call, response schema, and extraction logic.

## Open Questions

None — all design decisions were resolved during the brainstorm.
