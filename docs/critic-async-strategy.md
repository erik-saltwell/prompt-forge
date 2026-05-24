# Critic Async Strategy

## Overview

The critic should get useful fan-out without making UCB scheduling hard to reason about. The chosen strategy is:

- fan out the floor phase in simple rounds;
- fan out metric evaluation inside each pull;
- keep the UCB phase sequential so each UCB decision sees the freshest completed scores.

This keeps the candidate picker and `_SelectionData` state model simple while still using concurrency where it is most valuable.

## Key Ideas

**Pull** — One candidate evaluated against one case. The target output is generated once, then all metrics run against that output.

**Floor round** — One pass over eligible candidates during the floor phase. Each candidate appears at most once in a round.

**Inner fan-out** — Metrics for a single pull run concurrently with `asyncio.gather`.

**Sequential UCB** — After the floor phase completes, UCB schedules one pull, waits for it to finish, updates scores, then picks the next pull.

## Flow

### Floor phase

Run up to `floor_size` rounds. In each round:

1. Select candidates that still have cases and still need floor coverage.
2. Start at most one `evaluate_candidate(...)` task per selected `_SelectionData`.
3. Await the whole round.
4. Apply successful results and error handling before starting the next round.

This allows broad floor coverage without repeatedly picking from stale in-flight state.

### Pull execution

For one selected candidate:

1. Enter `_SelectionData.processing_case()`.
2. Generate the candidate output for the selected eval case.
3. Run all metrics concurrently.
4. Compute the scalar score.
5. Complete the case manager so `_SelectionData` records results and score.

Metric fan-out is the main source of async throughput.

### UCB phase

After floor rounds complete:

1. Pick the next candidate with `pick_next_ucb(...)`.
2. Await `evaluate_candidate(...)` for that candidate.
3. Repeat until the UCB budget is exhausted or no eligible candidates remain.

UCB does not fan out candidate pulls. Each decision sees the latest completed scores, avoiding virtual visits, sleep handshakes, and stale-score surprises.

## Invariants

- A single `_SelectionData` is never evaluated more than once at the same time.
- The floor phase may run many candidates concurrently, but only one pull per candidate per round.
- UCB starts only after the floor phase has completed, so UCB candidates have real completed scores.
- UCB decisions are sequential and score-fresh.
- The scheduler does not rely on `await asyncio.sleep(0)` to make in-flight state visible.
- Missing ground truth for a metric that requires it is a configuration/coding error and should fail loudly.

## Rationale

Candidate-level UCB is naturally sequential: pick, observe, update, pick again. Fully parallel UCB requires virtual visits or reserved in-flight state, which makes the scheduler and picker more subtle.

The critic already has meaningful fan-out at the metric layer. By keeping UCB sequential and using round-based floor fan-out, the implementation stays easier to test and reason about while still avoiding unnecessary serial metric calls.
