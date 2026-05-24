# Actor Module

## Overview

The Actor Module turns a tested candidate into a list of revised candidate prompts. Given one `Candidate` (a prompt plus its accumulated per-case `MetricResult`s), the Actor aggregates the results into per-node buckets of feedback, fans out one revision pipeline per bucket, and returns the resulting `Document`s. Each returned document is a sibling branch of the parent — never a serial chain. The optimizer wraps each into a new `Candidate` and merges them with the surviving parents to form the next iteration's pool.

## Key Concepts

**Bucket.** Every `IssueSignal` accusing the same `culprit_node_id` (or the `"document"` sentinel), grouped together. One bucket → one revision pipeline → at most one new `Document`. Buckets are produced by aggregating `candidate.results` inside the Actor; the aggregator's output type does not leave the module.

**Per-bucket pipeline.** The unit of work for one bucket: render the tree, call the per-node actor LLM, apply the returned `ActionBatch`, optionally run a structural-pass LLM on the result, apply that batch too. Pipelines run as independent coroutines under a bounded-concurrency semaphore.

**Per-node pass.** The first LLM call in a bucket's pipeline. Sees a redacted view of the tree focused on the bucket's culprit, the bucket's rendered signals, and the `preserve` list. Emits an `ActionBatch` that mutates content/structure to address the bucket's complaints.

**Structural pass.** An optional second LLM call applied to the per-node pass's output. Cleans up structural clarity issues introduced by the per-node revision. Whether it runs at all is decided by an injected predicate over the per-node `ActionBatch`.

**RedactionStrategy.** Renders the tree as XML for the per-node LLM, given a culprit node ID. The default elides distant content but preserves every node's ID and structural attributes; the focus region keeps content for the culprit, its ancestors and siblings, its own annotations, and all section headings.

**SignalRenderingStrategy.** Renders one bucket's signals as humanized markdown for the user prompt — one numbered subsection per signal with labeled fields (rationale, target behavior, success criterion, suggested change, input/output evidence, sightings count).

**`should_run_structural` predicate.** A `Callable[[ActionBatch], bool]` invoked after the per-node pass to decide whether the structural pass runs. Named built-ins include `always`, `never`, and `on_structural_actions` (true iff the per-node batch contained at least one `insert_node`/`move_node`/`delete_node`).

**Preserve list.** Top-level field on the internal aggregation — a deduped union of guardrails from every metric. Injected into the user prompt of every per-node and structural LLM call in one `revise()`.

## Flows

### `revise(candidate, *, llm_config, structural_llm_config=None, redaction=..., signal_renderer=..., should_run_structural=always, max_concurrent=8) -> list[Document]`

1. Aggregate `candidate.results` into per-node buckets and a `preserve` list. If there are no buckets, return `[]`.
2. For each bucket, launch one pipeline coroutine. Gather them under a `max_concurrent`-bounded semaphore.
3. Return the list of `Document`s produced by successful pipelines, in arbitrary order.

### Per-bucket pipeline

1. **Per-node pass.**
   a. Render the tree via `RedactionStrategy.render(tree, bucket.culprit_node_id)`.
   b. Render the bucket's signals via `SignalRenderingStrategy.render(bucket)`.
   c. Build the user prompt: rendered tree + rendered signals + `preserve` list. Load the per-node system prompt from package-data markdown.
   d. Call the actor LLM with `llm_config` and the `ActionBatch` discriminated-union schema. Parse leniently — malformed action elements are dropped by `ActionBatch`'s pre-validator; an unparseable envelope drops the bucket.
   e. Call `apply_batch(tree, batch)`. `apply_batch` clones the tree, applies actions skip-and-continue under frozen-batch-IDs, reassigns IDs, and returns the new document. If zero actions applied, drop the bucket.
2. **Gating.** Call `should_run_structural(per_node_batch)`. If false, emit the per-node pass's document and finish.
3. **Structural pass.**
   a. Render the per-node-pass document with the document-sentinel redaction (full content visible).
   b. Build the structural user prompt: rendered tree + `preserve`. Load the structural system prompt from package-data markdown.
   c. Call the LLM with `structural_llm_config` (falling back to `llm_config` if `None`). Same lenient `ActionBatch` parsing.
   d. If no actions are emitted or all are skipped, emit the per-node-pass document unchanged.
   e. Otherwise call `apply_batch` again and emit its document.

## Behaviors & Rules

- **One per-node call per bucket; at most one structural call per bucket.** No bucket merging, no whole-prompt single-call mode.
- **Branches are siblings, not a chain.** Each bucket's actions apply to a fresh clone of the parent. Buckets do not see each other's outputs. `apply_batch` owns the clone — the Actor never copies trees itself.
- **Variable-length return.** Pipelines that produce nothing (no signals, all actions skipped, schema-unparseable envelope) drop out of the returned list silently. The structural pass's empty/skip outcome is *not* a drop — it falls back to the per-node document.
- **Fail-fast on transport errors.** Any LLM transport failure (LiteLLM raising after exhausted retries) propagates out of `revise()` and kills the call. Schema/parse failures on the response do not — they drop only the affected bucket.
- **No actor-level retry.** Transport retries are LiteLLM's job.
- **Frozen batch IDs hold per `apply_batch` call.** IDs in an emitted action resolve against the snapshot the LLM saw, never the partially mutated tree. IDs are reassigned once at the end of each batch. With per-node + structural, that is two regen points per bucket.
- **`preserve` appears in every LLM user prompt.** Per-node and structural, every bucket, every `revise()` call.
- **Aggregation is private to the Actor.** The aggregator's output type does not appear in the public function signature and is not re-exported.
- **Three strategies are swappable for code evolution, not runtime configuration.** `RedactionStrategy`, `SignalRenderingStrategy`, and the structural-pass predicate live behind `Protocol`s (or a `Callable` for the predicate) so experimentation is a one-line swap, but no public facade exposes them.
- **The Actor does not own the candidate pool, the bandit, or eval-case sampling.** It consumes a `Candidate` for its prompt and results; the optimizer wraps each returned `Document` into a fresh `Candidate` with its own case sampling and bandit accounting.
- **Nothing in `_actor` is exported by the public facade.** The module is consumed only by the orchestration layer and its tests.

## Open Questions

None — all design decisions were resolved during the brainstorm.
