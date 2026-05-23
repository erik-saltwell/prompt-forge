# Batch Testing — Implementation Plan

This is a step-by-step guide for implementing the design in `batch-testing.md`. It assumes
the surrounding scaffolding already exists: `Metric`, `MetricResult`, `Document`,
`LiteLLMConfig`, `acomplete`, and the parser. We are building the *harness* that orchestrates
candidates × eval cases × metrics under UCB1.

All code lives under `packages/prompt-model/src/prompt_model/_batch_testing/`. The package is
private (leading underscore); we will re-export the public surface from its `__init__.py` at
the very end.

> **Convention reminders for this repo.** Python 3.12. PEP 695 `type` statements. Library
> code uses relative imports; tests use absolute imports. Type hints on every parameter,
> return type, and non-primitive local. Line length 140.

---

## Step 1 — `case.py`: the `EvalCase` model

**Why:** Every other module in this package consumes `EvalCase`. Build it first so later
modules can import it without circular dependencies.

**What to write:**

```python
# case.py
from pydantic import BaseModel, ConfigDict, Field


class EvalCase(BaseModel):
    """One evaluation input. See docs/batch-testing.md."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input: str = Field(...)
    ground_truth: str | None = Field(default=None)
    retrieval_context: list[str] | None = Field(default=None)
```

**Notes:**
- `frozen=True` so cases can be used as dict keys or in sets if needed downstream.
- No methods. This is pure data.

---

## Step 2 — `result.py`: the `CandidateResult` return shape

**Why:** The public return type of `run_batch` is `list[CandidateResult]`. Defining the shape
early makes the harness signature obvious from the first line of code.

**What to write:**

```python
# result.py
from typing import NamedTuple

from .._metrics import MetricResult
from .._prompt import Document


class CandidateResult(NamedTuple):
    """One returned candidate from run_batch: the prompt and the flat list of
    every MetricResult produced for it across all successful pulls."""

    prompt: Document
    results: list[MetricResult]
```

**Notes:**
- `NamedTuple` (not `BaseModel`) — this is a return-value tuple, not validated input.
- The `results` list is the **flat concatenation** of every metric's result across every
  successful pull (per the doc, "Return shape is flat"). The harness builds it; no
  per-input or per-metric grouping happens here.

---

## Step 3 — `reward.py`: the `RewardStrategy` protocol and built-ins

**Why:** UCB1 needs a scalar reward per pull. The strategy is how the caller tells the
harness *which* scalar to use given the per-metric scores. Implementing this before the
runner avoids passing partially-typed strategies into half-built code.

**What to write — the protocol:**

```python
# reward.py
from typing import Protocol, runtime_checkable

from .._metrics import MetricResult


@runtime_checkable
class RewardStrategy(Protocol):
    def compute(self, results: list[MetricResult]) -> float: ...
```

**Built-in strategies (each a plain class with a `compute` method):**

```python
class MeanReward:
    def compute(self, results: list[MetricResult]) -> float:
        # arithmetic mean of result.score across all results
        ...

class WorstReward:
    def compute(self, results: list[MetricResult]) -> float:
        # min of result.score; floor at 0.0 if results is empty
        ...

class WeightedMeanReward:
    def __init__(self, weights: dict[str, float]) -> None:
        # store weights keyed by metric_name; values need not sum to 1 (we will normalize)
        ...
    def compute(self, results: list[MetricResult]) -> float:
        # weighted mean over results whose metric_name appears in self.weights;
        # missing names contribute 0 weight; result is clamped to [0, 1]
        ...

class SingleMetricReward:
    def __init__(self, metric_name: str) -> None:
        ...
    def compute(self, results: list[MetricResult]) -> float:
        # find the first result whose metric_name matches; return its score
        # if no match: return 0.0 (defensive; should not happen under normal config)
        ...

class GeometricMeanReward:
    def compute(self, results: list[MetricResult]) -> float:
        # geometric mean of scores; if any score is 0.0, result is 0.0
        # otherwise: exp(mean(log(scores)))
        ...
```

**Notes:**
- Every strategy returns a float in `[0, 1]`. Vetoes are not allowed.
- These are dependency-free except for `MetricResult`; trivial to unit test with hand-built
  fixtures.

---

## Step 4 — `_input_pool.py`: per-candidate sampling without replacement

**Why:** The doc requires inputs to be sampled **without replacement per candidate**, and
candidates whose inputs are exhausted to be removed from the bandit. This bookkeeping is
self-contained and worth isolating so the runner does not have to deal with it inline.

**What to write:**

```python
# _input_pool.py
import random

from .case import EvalCase


class InputPool:
    """Tracks which inputs each candidate has already seen.

    Identity of a candidate is its index into the candidate list (passed in by the runner).
    Identity of an input is its index into the cases list.
    """

    def __init__(self, num_candidates: int, num_cases: int, seed: int | None) -> None:
        # _unseen[c] is a list of input indices the candidate has not yet been pulled on
        # shuffle each list with a seeded random.Random for determinism
        ...

    def has_unseen(self, candidate_index: int) -> bool:
        # True if there are still inputs this candidate has not yet seen
        ...

    def take(self, candidate_index: int) -> int:
        # pop one input index off the candidate's unseen list (deterministic order from seed)
        # caller is responsible for not calling this when has_unseen is False
        ...

    def exhausted_indices(self) -> set[int]:
        # candidates with no remaining inputs; runner uses this to remove arms
        ...

    def total_remaining(self) -> int:
        # sum of unseen across all candidates; used to short-circuit when budget exceeds coverage
        ...
```

**Notes:**
- Use `random.Random(seed)` instances rather than the module-level `random` so multiple
  pools in one process do not interfere.
- This is **pure bookkeeping** — no I/O, no async. Easy to test with synthetic inputs.

---

## Step 5 — `_ucb.py`: the UCB1 arm-selection math

**Why:** UCB1's selection rule is a small piece of math that benefits from being isolated
and tested with fixed reward sequences. The runner orchestrates pulls and concurrency; this
module just answers "given what we know so far, which arm should we pull next?"

**What to write:**

```python
# _ucb.py
import math
from dataclasses import dataclass, field


@dataclass
class ArmStats:
    """Mutable per-arm running stats."""
    pulls: int = 0
    sum_reward: float = 0.0
    in_flight: int = 0  # virtual visits — see "Concurrency tolerates stale UCB stats"

    @property
    def mean_reward(self) -> float:
        # sum_reward / max(pulls, 1)
        ...

    @property
    def effective_pulls(self) -> int:
        # pulls + in_flight — used in the UCB denominator and ln(N) so an in-flight arm
        # is not picked again on the very next decision
        ...


def ucb_score(arm: ArmStats, total_effective_pulls: int, exploration_bonus: float) -> float:
    # mean_reward + exploration_bonus * sqrt(2 * ln(total_effective_pulls) / arm.effective_pulls)
    # if arm.effective_pulls == 0: return +inf so untouched arms always win first
    ...


def select_arm(
    eligible_indices: list[int],
    stats: list[ArmStats],
    exploration_bonus: float,
) -> int:
    # compute total_effective_pulls = sum of effective_pulls over ALL stats
    # return the index in eligible_indices with the highest ucb_score
    # break ties by lowest index (deterministic)
    ...
```

**Notes:**
- `eligible_indices` is "arms that still have unseen inputs". The runner passes this in
  fresh on every call (cheap — `num_candidates` is small).
- The `in_flight` mechanism is the "virtual visits" trick from the doc — when a pull is
  launched we bump `in_flight`, and when it lands we decrement `in_flight` and bump
  `pulls`. This stops the same arm from being chosen twice in a row before any reward has
  come back.
- Deterministic tie-break (lowest index wins) is what allows `seed`-based reproducibility
  when `max_concurrency=1`.

---

## Step 6 — `_runner.py`: the pull loop

**Why:** This is the heart of the harness — what schedules pulls, what calls the target
LLM, what runs metrics, what updates UCB stats, what handles errors and the error budget.
Everything else in this package is a small dependency of this one file.

This step is large. Implement and test the helpers below in order before wiring them
together in `run_batch`.

### 6a. The `BatchTestingErrorBudgetExceeded` exception

```python
# _runner.py
class BatchTestingErrorBudgetExceeded(Exception):
    """Raised when accumulated metric/target failures exceed error_budget.
    The run aborts; no partial results are returned."""
```

### 6b. Target LLM call — render the Document to markdown, prepend as user message

```python
async def _call_target(
    target_config: LiteLLMConfig,
    prompt_md: str,
    input_text: str,
) -> str:
    # build messages: [{"role": "user", "content": f"{prompt_md}\n\n{input_text}"}]
    # await acomplete(target_config, messages)
    # return the string
```

**Notes:**
- The prompt itself goes in as a user message, with the case input appended. We do not use
  a system role; the prompt under optimization is the prompt under optimization.
- Render `Document` to markdown via `document.to_markdown()` (or whatever the public
  serializer is — check `_prompt/__init__.py`).

### 6c. Run all metrics against one (prompt, input, output, ground_truth)

```python
async def _run_metrics(
    metrics: list[Metric],
    prompt_md: str,
    case: EvalCase,
    output: str,
) -> list[MetricResult]:
    # asyncio.gather over [m.evaluate(prompt_md, case.input, output, case.ground_truth) for m in metrics]
    # if any metric raises (including MissingGroundTruthError): re-raise so the caller
    #   can discard the pull and schedule a retry
    # stamp result.metric_name = m.name on each returned result if the metric did not set it
    #   (BaseLLMJudgeMetric already does this; defense-in-depth here)
    # return the list in metric-input order
```

**Notes:**
- Any single metric failure poisons the pull (doc: "On any metric failure: discard the
  pull's reward, do not update UCB stats…").
- The harness *stamps* `metric_name` if the metric forgot to; `BaseLLMJudgeMetric` already
  does it but we cannot assume custom metrics will.

### 6d. One full pull — orchestration

```python
async def _execute_pull(
    candidate_index: int,
    input_index: int,
    candidates: list[Document],
    cases: list[EvalCase],
    metrics: list[Metric],
    target_config: LiteLLMConfig,
    sem: asyncio.Semaphore,
) -> tuple[int, int, list[MetricResult] | None]:
    # async with sem:
    #   try:
    #     output = await _call_target(...)
    #     results = await _run_metrics(...)
    #     return candidate_index, input_index, results
    #   except Exception:
    #     return candidate_index, input_index, None    # signals failure to caller
```

**Notes:**
- Returns the indices alongside the result so the caller can update the right arm and
  pool slot without sharing closure state.
- `None` for the result list means "this pull failed; discard + retry".

### 6e. The orchestration loop — `run_batch`

This is the public function from `harness.py` that callers actually invoke. Pseudo-code:

```python
async def run_batch(
    candidates: list[Document],
    cases: list[EvalCase],
    metrics: list[Metric],
    target_config: LiteLLMConfig,
    reward_strategy: RewardStrategy,
    *,
    floor: int,
    ucb_budget: int,
    top_k: int | None,
    max_concurrency: int,
    exploration_bonus: float,
    error_budget: int,
    seed: int | None,
) -> list[CandidateResult]:
    # 1. Initialize:
    #      stats = [ArmStats() for _ in candidates]
    #      pool = InputPool(len(candidates), len(cases), seed)
    #      sem = asyncio.Semaphore(max_concurrency)
    #      results_per_candidate: list[list[MetricResult]] = [[] for _ in candidates]
    #      errors = 0
    #      remaining_budget = ucb_budget
    #      cap pulls at min(floor*N + ucb_budget, total_cells)
    #
    # 2. Floor phase:
    #    - Build the list of (candidate, input) pairs to satisfy floor for everyone.
    #    - For each candidate: take `floor` indices from the pool (or fewer if exhausted).
    #    - Launch all pulls as asyncio.create_task(_execute_pull(...)).
    #    - Track them in a set called in_flight; bump stats[c].in_flight on launch.
    #
    # 3. Main loop (combined floor + UCB completion + UCB scheduling):
    #    while in_flight or (remaining_budget > 0 and pool.total_remaining() > 0):
    #
    #      # Drain at least one completion if we're at capacity or out of new work to launch
    #      done, in_flight = await asyncio.wait(in_flight, return_when=FIRST_COMPLETED)
    #      for task in done:
    #          c_idx, i_idx, results = task.result()
    #          stats[c_idx].in_flight -= 1
    #          if results is None:
    #              errors += 1
    #              if errors > error_budget: raise BatchTestingErrorBudgetExceeded(...)
    #              # discard: return the input to the pool? NO — the doc says re-sample.
    #              # Simplest path: schedule a replacement pull on the same arm with a NEW input.
    #              # If pool.has_unseen(c_idx): launch another pull, bump in_flight
    #          else:
    #              stats[c_idx].pulls += 1
    #              stats[c_idx].sum_reward += reward_strategy.compute(results)
    #              results_per_candidate[c_idx].extend(results)
    #
    #      # Schedule new UCB pulls if budget allows and capacity is free
    #      while remaining_budget > 0 and len(in_flight) < max_concurrency:
    #          eligible = [c for c in range(len(candidates))
    #                      if pool.has_unseen(c) and stats[c].pulls >= floor]
    #          if not eligible: break
    #          c = select_arm(eligible, stats, exploration_bonus)
    #          i = pool.take(c)
    #          stats[c].in_flight += 1
    #          in_flight.add(asyncio.create_task(_execute_pull(c, i, ...)))
    #          remaining_budget -= 1
    #
    # 4. Selection:
    #    - eligible_for_top_k = candidates whose stats[c].pulls >= floor
    #    - rank descending by mean_reward
    #    - take top_k (or all eligible if top_k is None)
    #    - return [CandidateResult(candidates[c], results_per_candidate[c]) for c in ranked]
```

**Notes — this is the trickiest file in the package:**

- **Floor first, UCB after** (doc rule): the eligibility predicate for UCB arms requires
  `stats[c].pulls >= floor`. Until then, the only pulls landing on that arm are the floor
  pulls already scheduled in step 2.
- **Replacement pulls on failure** do not count against `ucb_budget`. They DO need an
  unseen input — if the failing arm has none left, just record the error and move on; no
  replacement.
- **The cap at coverage** (doc rule): `total_cells = num_candidates * num_cases`. If
  `floor * num_candidates + ucb_budget > total_cells`, silently use `total_cells` instead.
  This is "full evaluation, not failure".
- **Deterministic execution** is best-effort. With `max_concurrency=1` the run is
  bit-reproducible if the LLM is also deterministic; with higher concurrency, completions
  arrive in nondeterministic order and that is fine.

---

## Step 7 — `harness.py`: the public-facing wrapper

**Why:** `run_batch` in `_runner.py` carries every internal type. We give the world a
slightly thinner surface with `reward_strategy` made optional (defaults to `MeanReward`),
plus a synchronous convenience wrapper for non-async callers.

**What to write:**

```python
# harness.py
import asyncio
import math
# ... imports

DEFAULT_EXPLORATION_BONUS: float = math.sqrt(2)


async def run_batch(
    candidates: list[Document],
    cases: list[EvalCase],
    metrics: list[Metric],
    target_config: LiteLLMConfig,
    reward_strategy: RewardStrategy | None = None,
    *,
    floor: int,
    ucb_budget: int,
    top_k: int | None = None,
    max_concurrency: int = 4,
    exploration_bonus: float = DEFAULT_EXPLORATION_BONUS,
    error_budget: int = 0,
    seed: int | None = None,
) -> list[CandidateResult]:
    # default reward_strategy = MeanReward() if None
    # delegate to _runner.run_batch with everything passed through
    ...


def run_batch_sync(*args, **kwargs) -> list[CandidateResult]:
    # asyncio.run(run_batch(*args, **kwargs))
    ...
```

**Notes:**
- The public-facing default for `reward_strategy` is `MeanReward()`. The private runner
  requires it explicitly so the runner contract is unambiguous.
- `run_batch_sync` exists for CLI / script callers who do not want to manage an event
  loop themselves.

---

## Step 8 — `__init__.py`: the package's public surface

**Why:** Everything inside `_batch_testing/` is implementation detail. The package
re-exports a curated list of names that the rest of `prompt_model` and downstream
callers actually use.

**What to write:**

```python
# __init__.py
from ._runner import BatchTestingErrorBudgetExceeded
from .case import EvalCase
from .harness import DEFAULT_EXPLORATION_BONUS, run_batch, run_batch_sync
from .result import CandidateResult
from .reward import (
    GeometricMeanReward,
    MeanReward,
    RewardStrategy,
    SingleMetricReward,
    WeightedMeanReward,
    WorstReward,
)

__all__ = [
    "DEFAULT_EXPLORATION_BONUS",
    "BatchTestingErrorBudgetExceeded",
    "CandidateResult",
    "EvalCase",
    "GeometricMeanReward",
    "MeanReward",
    "RewardStrategy",
    "SingleMetricReward",
    "WeightedMeanReward",
    "WorstReward",
    "run_batch",
    "run_batch_sync",
]
```

---

## Step 9 — Tests

**Why:** The repo convention is **fixture-driven** tests (see `docs/test-infra.md`). For
batch testing, most tests are *behavioral*, not fixture-comparison, so they live as plain
pytest functions under `packages/prompt-model/tests/batch_testing/`. Use absolute imports
in tests.

Implement these in order:

1. **`test_input_pool.py`** — pure unit tests. Hand-built pool; assert `take` is
   without-replacement, `exhausted_indices` flips when emptied, `seed` produces
   deterministic order.
2. **`test_ucb.py`** — feed `ArmStats` with hand-crafted pull histories; assert
   `select_arm` picks the higher-mean arm at low exploration, the lower-pulled arm at
   high exploration, and the lowest-index arm on ties.
3. **`test_reward.py`** — synthetic `MetricResult`s; assert each strategy's math.
4. **`test_runner_smoke.py`** — fake `Metric` and fake LiteLLM call (monkeypatch
   `acomplete`) to drive a tiny end-to-end: 2 candidates, 3 cases, 1 metric, floor=1,
   ucb_budget=2. Assert: every candidate gets `>= floor` pulls; the higher-scoring
   candidate gets more total pulls; return list is ranked descending.
5. **`test_runner_errors.py`** — fake metric that raises on certain inputs. Assert
   pulls are discarded, replacements scheduled, and `BatchTestingErrorBudgetExceeded`
   raises once `error_budget` is exceeded.

**Notes:**
- Mock LiteLLM with `pytest`'s `monkeypatch` on `acomplete` — do NOT make real network
  calls in tests.
- Keep each test under 1 second. The full suite is ~600 tests in <1s; do not be the one
  who breaks that.

---

## Step 10 — Wire-up checklist

After all of the above:

- [ ] `uv run ruff format` (apply formatting)
- [ ] `uv run ruff check --fix` (lint)
- [ ] `uv run ty check packages apps` (type check — uses `ty`, not mypy)
- [ ] `uv run pytest` (full suite still passes)
- [ ] Manually confirm `from prompt_model._batch_testing import run_batch, EvalCase,
      MeanReward, CandidateResult` works from a Python REPL.

If `_optimize_prompt.py` (the outer optimizer) is the next step after this, none of its
imports need to change — they already reference these names.

---

## Open Questions

None — every decision is in the design doc.
