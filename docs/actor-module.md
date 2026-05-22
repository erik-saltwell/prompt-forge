# Actor Module

## Overview

The Actor Module turns a candidate prompt and a bucket of critic feedback into a list of new candidate prompts. Each iteration of the optimizer hands the Actor one parent prompt plus an `AggregationResult` from the metric aggregator; the Actor returns up to one revised prompt per culprit node in that result. The module owns the full render → LLM call → action-apply → ID-regen sequence per bucket; the optimizer just consumes the returned candidates.

## Key Concepts

**Bucket.** One `AggregatedNodeBucket` from the aggregator — every `IssueSignal` accusing the same `culprit_node_id` (or the `"document"` sentinel). The unit of work for one actor call.

**Per-bucket fan-out.** One LLM call per bucket. For a parent prompt with g problematic nodes, the Actor produces up to g new candidates. Each is a sibling branch of the parent, not a serial chain — the bucket's actions are applied to a fresh copy of the parent, not to the previous bucket's output.

**RedactionStrategy.** The single injectable seam on the Actor. Given a tree and a culprit node ID, returns the XML the actor LLM will see. Swappable; only one is exposed at construction.

**ActorResult.** The structured output of one bucket's processing: the new `Document`, the `ActionBatch` the actor proposed, the indices of actions applied, and the indices of actions skipped (with reasons).

**Structural pass.** The same `revise()` call applied to a one-bucket `AggregationResult` whose sole bucket has `culprit_node_id == "document"`. Not a separate module or class. Orchestrated by the optimizer, not the Actor.

**Preserve list.** The `preserve` field on `AggregationResult` — a deduped union of guardrails from every metric. Shared across all g calls in one `revise()` and injected into every actor prompt template as instructions about what must not change.

## Flows

### `revise(tree, aggregation) → list[ActorResult]`

1. Acquire a slot on the internal concurrency semaphore.
2. For each bucket in `aggregation.buckets`, in bounded parallel:
   a. Render the tree via the `RedactionStrategy`, focused on the bucket's culprit node.
   b. Build the actor prompt: rendered tree + bucket signals + `aggregation.preserve`.
   c. Call the actor LLM; structured-output schema is the `ActionBatch` discriminated union.
   d. Parse leniently — malformed action entries are dropped, the rest of the batch proceeds.
   e. Apply the batch to a fresh copy of the tree via `apply_batch` (skip-and-continue, frozen-batch-IDs invariant).
   f. Re-assign IDs on the resulting tree (end of batch).
   g. Wrap in an `ActorResult`.
3. Return the list of successful `ActorResult`s. Length 0..g.

### Default RedactionStrategy

Given a tree and a culprit node ID:

- If `culprit_node_id == "document"`: return the full XML rendering with all content visible.
- Otherwise: return a skeleton XML where every node carries its ID and structural attributes, but content is preserved only for:
  - Section headings throughout the tree (the table of contents stays legible).
  - The ancestor chain of the target node.
  - The immediate siblings of the target node.
  - The target node's own `examples` and `guidance` groups, if any.
  - If the target is itself an annotation: its sibling annotations in the same group.

All other text is replaced with an elision marker. IDs remain on every node so any node remains addressable by an action.

### Structural pass (orchestrator-level)

Per parent candidate, the optimizer:

1. Calls `revise(parent_tree, per_node_aggregation)` and receives up to g new candidates.
2. For each new candidate, runs the structural critic to produce a one-bucket `AggregationResult` whose sole bucket has `culprit_node_id == "document"`.
3. Calls `revise(new_candidate.document, structural_aggregation)` and takes the single result if present.
4. The final candidate is either the structural-pass output (if it ran successfully) or the per-node-pass output otherwise.

The Actor itself is unaware of whether it's running a per-node or a structural pass. It receives an `AggregationResult` and processes its buckets uniformly.

## Behaviors & Rules

- **One actor call per bucket.** Always. No bucket merging, no whole-prompt single-call mode.
- **Branches are siblings, not a chain.** Each bucket's actions apply to a fresh copy of the input tree. Buckets do not see each other's outputs.
- **Variable-length return.** A failed actor call (transport error, schema parse failure, every action skipped at apply time) drops out of the returned list silently — no placeholder, no degenerate ActorResult. Failures are reported via the progress reporter, not the return value.
- **Bounded concurrency.** The Actor enforces its own ceiling on in-flight LLM calls within one `revise()` via an internal semaphore. The cap defaults to 8 and is not exposed in the public facade.
- **No actor-level retry.** Transport retries are LiteLLM's responsibility. Schema failures, lenient-validator drops, and skip-everything outcomes are treated as data — surfaced in `ActorResult.skipped` and visible to the actor next iteration as natural learning signal, not retried.
- **Frozen-batch-IDs holds within one bucket's action list.** IDs in the actor's emitted actions resolve against the snapshot the actor saw, not against the partially mutated tree. IDs are regenerated once, at end of batch, before the `ActorResult` is yielded.
- **`preserve` is injected into every per-bucket prompt.** Not just the bucket-specific call. The actor sees the guardrail list on every invocation within a single `revise()`.
- **`RedactionStrategy` is the only injectable collaborator.** Renderer, action executor, LLM helper, and ID assigner are module-level functions invoked directly. The strategy is what callers swap when they want to experiment with how much of the tree the actor sees.
- **The Actor does not own aggregation.** It receives a finished `AggregationResult` from the optimizer. Critic invocation, signal aggregation, and bucket construction happen upstream.
- **The Actor does not own the bandit or candidate pool.** It returns candidates; the optimizer adds them to the pool and scores them under UCB.

## Open Questions

None — all design decisions were resolved during the brainstorm.
