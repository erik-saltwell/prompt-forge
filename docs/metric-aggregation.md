# Aggregated Metric Results for the Actor

## Overview

After a candidate prompt has been evaluated against many inputs by many metrics, the resulting `MetricResult`s must be consolidated into focused, per-node payloads that drive the actor LLM's edits. The aggregator groups every issue signal by the prompt node it accuses, deduplicates near-identical complaints across cases, caps the per-node signal count, and emits one independent actor call per node that has findings. Score and assessment are not forwarded — the actor acts on signals only.

---

## Key Concepts

**Aggregated Node Bucket** — All issue signals raised against one prompt node id during one (candidate, iteration) pass, after dedupe and top-K capping. The unit of input to a single actor call.

**Document sentinel** — The literal string `"document"` used as the `culprit_node_id` for signals that aren't localizable to a specific tree node. Real node ids start at `"1"` per the prompt-model id scheme, so `"document"` cannot collide. The Document root itself still has no id on the tree — `"document"` is a routing label for the actor pipeline, not a node id.

**IssueSignal (unified)** — One signal, produced by the critic and carried unchanged through aggregation. Fields:

| Field | Type | Notes |
|---|---|---|
| `culprit_node_id` | `str` | Real node id (`"1.2.3"`, `"1.1.e2"`) or the `"document"` sentinel. Always exactly one. |
| `rationale` | `str` | Why the node is at fault. |
| `target_behavior` | `str` | What good looks like. |
| `success_criterion` | `str` | The bar that, if met, represents a successful change. |
| `suggested_prompt_change` | `str \| None` | Optional concrete suggestion. |
| `input_snippet` | `str` | Verbatim quote from the case's input that evidences the issue. Required. |
| `output_snippet` | `str` | Verbatim quote from the case's output that evidences the issue. Required. |
| `seen_in_n_cases` | `int = 1` | Defaults to 1 on critic emission; incremented during dedupe. |

`ImprovementGuidance` is flattened into `IssueSignal` — no nested object.

**Critic single-culprit rule** — A single signal accuses exactly one node. Cross-node issues (e.g., examples in 1.1 contradict the rule in 2.3) are expressed as **two independent peer signals**, each fully self-contained in its own node's bucket, with the cross-reference written as prose in each rationale. There is no primary/secondary relationship and no list of suspects.

**Dedupe key** — Normalized `(metric_name, culprit_node_id, success_criterion)`. Normalization is lowercase + whitespace collapse + trailing-punctuation strip on each component. `metric_name` is read from `MetricResult.metric_name`; it participates in the dedupe key and is stripped before the signal is sent to the actor.

**Top-K cap** — Each per-node bucket is capped at K=10 signals after dedupe, ordered by `seen_in_n_cases` descending, with tiebreak by `metric_name` lexically for determinism.

**Per-node actor payload** — The wire-format JSON sent to one actor call:

```
{
  focused_node_id: "1.2.3" | "document",
  prompt_xml: "<document>...</document>",   // full prompt, not a subtree
  preserve: [string, ...],                  // global, shared across all per-node calls
  signals: [IssueSignal, ...]               // for this node only, deduped + capped
}
```

---

## Flows

### Per-iteration aggregation and refinement (one candidate)

1. **Collect.** Gather every `MetricResult` produced for this candidate this iteration — one per (metric, input) pair. Flatten to a single list of `IssueSignal`s.
2. **Group.** Partition by `culprit_node_id`. Signals with the `"document"` sentinel form their own bucket alongside real-node buckets.
3. **Dedupe within each bucket.** Collapse signals with matching normalized `(metric_name, culprit_node_id, success_criterion)`. On collapse:
   - **Pick one signal in the group as the base.** Preference order: (i) signals whose `suggested_prompt_change` is not `None`; (ii) among those (or among all, if none qualify), the first encountered. Tiebreak is deterministic on encounter order.
   - The merged signal **is the base, verbatim** — `rationale`, `target_behavior`, `success_criterion`, `suggested_prompt_change`, `input_snippet`, and `output_snippet` all come from the base. No per-field cherry-picking.
   - `seen_in_n_cases` is set to the size of the group (sum across all merged-in signals' counts).
4. **Cap.** Keep the top 10 entries per bucket by `seen_in_n_cases` desc.
5. **Strip.** Remove `metric_name` from each signal (it was used only for dedupe).
6. **Skip empty.** Buckets with zero signals do not trigger an actor call; if the entire candidate has zero signals, no actor calls are made and the candidate carries forward unchanged.
7. **Fan out to actor calls.** For each non-empty bucket, make one independent actor call with `{focused_node_id, prompt_xml, preserve, signals}`. Calls are parallel siblings against the same parent candidate — never chained.
8. **Apply.** Each actor call returns an action list; apply against the parent candidate to produce one new sibling candidate. N buckets → N new candidates added to the pool.

### Position in the wider optimization loop

1. Seed the pool with one candidate.
2. Evaluate each candidate (SCULPT-style explore/exploit) → many `MetricResult`s per candidate.
3. Select top candidates. For each, run **Per-iteration aggregation and refinement** above to produce sibling candidates.
4. Repeat for a fixed number of iterations.

---

## Behaviors & Rules

- **Single culprit per signal.** The critic schema does not allow a list of suspects. Cross-node concerns are expressed as multiple signals with prose cross-references.
- **`"document"` is a first-class bucket.** Unlocalizable signals route to a `"document"` bucket that is treated identically to a real-node bucket — same dedupe, same cap, same actor-call payload.
- **Aggregation is per (candidate, iteration).** Buckets do not persist across iterations and do not merge across candidates (different candidates have different node ids).
- **No summary object.** The per-node payload is a flat list of `IssueSignal`s. No higher-level reduction or merge into a single composite signal happens after dedupe.
- **Snippets are verbatim quotes, not summaries.** `input_snippet` and `output_snippet` are excerpts taken directly from the case's input and output text — never paraphrased.
- **Dedupe preserves coherence via a base signal.** The merged entry is one source signal taken verbatim, not a per-field mash-up. This guarantees the rationale, snippets, target behavior, and suggestion all describe the same real case the critic saw.
- **Base-signal preference favors actionable suggestions.** Among signals sharing the dedupe key, one with a non-`None` `suggested_prompt_change` is picked over one without — the concrete suggestion is the more valuable artifact to forward to the actor.
- **Snippets are kept as a single coherent pair.** Even after merging N cases, only one `(input_snippet, output_snippet)` pair is kept — sourced from the base signal so the input quote and output quote belong to the same case. `seen_in_n_cases` carries the volume signal, so retaining multiple pairs is unnecessary.
- **`seen_in_n_cases` defaults to 1.** The critic emits with the default; aggregation increments. Same `IssueSignal` shape end-to-end.
- **Score and assessment never reach the actor.** They are critic/human telemetry only.
- **Preserve is global, not per-node.** The same `preserve` list rides along with every per-node call in the iteration.
- **Actor sees the entire prompt.** Each per-node call includes the full prompt XML, not just the focused node's subtree. Focus comes from *which signals* are sent, not from clipping the tree — the full tree is required so the actor can emit actions whose `target` references nodes outside the focused subtree.
- **Sibling fan-out, no chaining.** N per-node actor calls for one parent candidate produce N independent sibling candidates. Calls do not see each other's mutations; conflicts (e.g., two calls both deleting an ancestor) are absorbed by the action executor's skip-and-continue policy.
- **Empty candidates skip the actor.** A candidate with zero signals across all metrics is not edited; it carries forward into the next iteration's evaluation untouched.
- **Metric identity is internal.** `metric_name` is used for dedupe key construction and then dropped before the actor sees the payload — the actor does not weight signals by their source metric.
- **Aggregator input is `list[MetricResult]`.** Each `MetricResult` carries its own `metric_name`; no parallel name list is passed alongside.

---

## Open Questions

None — all decisions were resolved during the brainstorm.
