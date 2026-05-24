# Actor Module

## Overview

The Actor Module turns a tested candidate into a list of revised candidate prompts. Given one `Candidate` (a prompt plus its accumulated per-case `MetricResult`s), the Actor aggregates the results into per-node buckets of feedback, fans out one revision pipeline per bucket, and returns the resulting `Document`s. Each returned document is a sibling branch of the parent — never a serial chain. The optimizer wraps each into a new `Candidate` and merges them with the surviving parents to form the next iteration's pool.

## Key Concepts

**Bucket.** Every `IssueSignal` accusing the same `culprit_node_id` (or the `"document"` sentinel), grouped together. One bucket → one revision pipeline → at most one new `Document`. Buckets are produced by aggregating `candidate.results` inside the Actor; the aggregator's output type does not leave the module.

**Per-bucket pipeline.** The unit of work for one bucket: select a focus region of the tree, render it, call the per-node actor LLM, apply the returned `ActionBatch`, optionally run a structural-cleanup LLM on the result, apply that batch too. Pipelines run as independent coroutines under a bounded-concurrency semaphore.

**Per-node pass (feedback).** The first LLM call in a bucket's pipeline. Sees a redacted view of the tree focused on the bucket's culprit, the bucket's rendered signals, and the `preserve` list. Emits an `ActionBatch` that mutates content/structure to address the bucket's complaints.

**Structural cleanup pass.** An optional second LLM call applied to the per-node pass's output. Cleans up structural clarity issues introduced by the per-node revision. Whether it runs at all is decided by an injected predicate over the per-node `ActionBatch`. There is no separate structural critic — the cleanup LLM reads the post-revision document and emits its own actions directly.

**RedactionStrategy.** Selects the set of node ids whose content the renderer should keep verbatim. Returns `None` to mean "keep everything." Decoupled from rendering: this strategy picks *what* to show; the render strategy decides *how* to show it.

**RenderPromptStrategy.** Renders a tree as the string the actor LLM reads, honoring the focus set from the `RedactionStrategy`. Three variants ship: XML (default, actor form per `prompt-serialization.md`), JSON (Pydantic `model_dump`), and Markdown (critic form — conforming markdown with `<!-- id -->` comments).

**SignalRenderingStrategy.** Renders one bucket's signals for the user prompt. Three variants ship: humanized markdown (default), JSON, and XML. The default emits one `## Issue N` subsection per signal with labeled fields (rationale, target behavior, success criterion, suggested change, input/output evidence, sightings count).

**`StructuralCleanupPredicate`.** Type alias for `Callable[[ActionBatch], bool]`. Invoked after the per-node pass to decide whether the structural cleanup pass runs. Named built-ins: `always_cleanup_structure`, `never_cleanup_structure`, `cleanup_structure_on_structural_actions` (true iff the batch contains `insert_node`/`delete_node`/`move_node`), and `cleanup_structure_on_move_actions` (move only).

**Preserve list.** Top-level field on the internal aggregation — a deduped union of guardrails from every metric. Injected into the user prompt of every per-node and structural LLM call in one `revise()`.

**PromptAndActions.** Internal `NamedTuple` of `(actions: ActionBatch, prompt: Document)` returned by the per-node pass. The pipeline needs both: `actions` to feed the cleanup predicate, `prompt` as the structural pass's input or the final result.

## Flows

### `revise(candidate, feedback_llm_config, structural_llm_config=None, max_concurrent=8) -> list[Document]`

1. If `candidate.results` is empty, return `[]`.
2. Aggregate `candidate.results` into per-node buckets and a `preserve` list. If there are no buckets, return `[]`.
3. Construct the internal strategy instances (redactor, prompt renderer, signal renderer, structural predicate) from module defaults. They are not part of the public signature.
4. Create one `asyncio.Semaphore` bounded at `max_concurrent`.
5. For each bucket, launch one pipeline coroutine. `asyncio.gather` them.
6. Return the list of `Document`s produced by surviving pipelines, dropping any `None`s. Order is arbitrary.

### Per-bucket pipeline

1. **Per-node pass (under the semaphore).**
   a. Compute focus ids: `redaction.focus_ids(tree, bucket.culprit_node_id)`.
   b. Render the tree: `prompt_renderer.render(tree, focus_ids)`.
   c. Render the bucket's signals: `signal_renderer.render(bucket)`.
   d. Build the user prompt: rendered tree + rendered signals + `preserve`. Load the per-node system prompt from package-data markdown (`_resources/feedback_actor.md`).
   e. Call the actor LLM with `feedback_llm_config` and `response_format=ActionBatch`. Malformed action elements are dropped by `ActionBatch`'s pre-validator; an unparseable envelope raises `ValidationError`, caught here → drop the bucket (return `None`).
   f. Call `apply_batch(tree, batch)`. `apply_batch` clones the tree, applies actions skip-and-continue under frozen-batch-IDs, reassigns IDs, and returns the new document. If zero actions applied, drop the bucket.
   g. Return `PromptAndActions(actions=batch, prompt=new_doc)`.
2. **Gating.** Call the structural-cleanup predicate on `batch`. If `False`, return the per-node document and finish.
3. **Structural cleanup pass (under the semaphore).**
   a. Render the per-node-pass document with `focus_ids=None` (full content visible).
   b. Build the structural user prompt: rendered tree + `preserve`. Load the structural system prompt from package-data markdown (`_resources/structural_actor.md`).
   c. Call the LLM with `structural_llm_config` (falling back to `feedback_llm_config` if `None`).
   d. On `ValidationError`, no emitted actions, or all-skipped: return the per-node-pass document unchanged.
   e. Otherwise call `apply_batch` again and return its document.

## Behaviors & Rules

- **One per-node call per bucket; at most one structural call per bucket.** No bucket merging, no whole-prompt single-call mode.
- **Branches are siblings, not a chain.** Each bucket's actions apply to a fresh clone of the parent. Buckets do not see each other's outputs. `apply_batch` owns the clone — the Actor never copies trees itself.
- **Variable-length return.** Pipelines that produce nothing (no signals on the parent, schema-unparseable per-node envelope, empty per-node actions, all per-node actions skipped at apply time) drop out of the returned list silently. The structural pass's empty/skip outcome is *not* a drop — it falls back to the per-node document.
- **Fail-fast on transport errors.** Any LLM transport failure (LiteLLM raising after exhausted retries) propagates through `asyncio.gather` out of `revise()` and kills the call. Schema/parse failures on the response do not — they drop only the affected bucket.
- **No actor-level retry.** Transport retries are LiteLLM's job.
- **Semaphore released between the two LLM calls.** The bucket pipeline acquires the cap for the per-node call, releases, then re-acquires for the structural call. Lets other buckets' pipelines interleave.
- **Frozen batch IDs hold per `apply_batch` call.** IDs in an emitted action resolve against the snapshot the LLM saw, never the partially mutated tree. IDs are reassigned once at the end of each batch. With per-node + structural, that is two regen points per bucket.
- **`preserve` appears in every LLM user prompt.** Per-node and structural, every bucket, every `revise()` call.
- **Aggregation is private to the Actor.** The aggregator's output type does not appear in the public function signature and is not re-exported.
- **Four strategies are swappable for code evolution, not runtime configuration.** `RedactionStrategy`, `RenderPromptStrategy`, `SignalRenderingStrategy`, and the structural-cleanup predicate are wired from module-level defaults inside `revise()`. Experimentation is a one-line edit of the default; the public function signature stays clean.
- **The Actor does not own the candidate pool, the bandit, or eval-case sampling.** It consumes a `Candidate` for its prompt and results; the optimizer wraps each returned `Document` into a fresh `Candidate` with its own case sampling and bandit accounting.
- **Nothing in `_actor` is exported by the public facade.** The module is consumed only by the orchestration layer and its tests.

## Open Questions

None — all design decisions were resolved during the brainstorm.
