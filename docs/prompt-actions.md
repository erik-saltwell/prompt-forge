# Prompt Optimization Actions

## Overview

The optimization actions are a closed vocabulary of structured operations that mutate a parsed prompt tree (see `prompt-model.md`). An actor LLM, given critique feedback aggregated across sample runs, emits a batch of actions as JSON. Deterministic code applies them to produce a new prompt for the next optimization iteration. Every applied action is reversible, supporting an undo stack used for testing and round-trip validation.

---

## Key Concepts

**Action** — A single structured operation targeting one node or annotation by ID. Fully self-contained: any content the action introduces is written inline in the JSON. No second LLM call is needed to apply it.

**Batch** — The set of actions the actor LLM emits in one iteration. All IDs in a batch resolve against a frozen snapshot of the tree the actor was given.

**Frozen batch IDs** — IDs do not shift mid-batch. The executor resolves each action's IDs against the snapshot, not against the partially mutated tree. Across iterations, IDs are recomputed from scratch — they are not durable identifiers, only addressable handles within one batch.

**Location anchor** — How an action specifies where to place a node. Four forms, all relative:
- `{"after": <sibling_id>}`
- `{"before": <sibling_id>}`
- `{"first_child": <parent_id>}`
- `{"last_child": <parent_id>}`

**Undo entry** — A captured inverse of a successfully applied action, sufficient to restore the prior tree state. Entries are recorded per-action, not per-batch.

---

## The Action Vocabulary

Ten actions across two groups.

### Node actions

| Action | Purpose |
|---|---|
| `rewrite_node` | Replace the text of a node. Text-only; does not change node type or structural properties. |
| `delete_node` | Remove a node and its subtree. Accepts annotation IDs too — if the target is an example or guidance annotation, it is removed. |
| `insert_node` | Add a new node at a location anchor. The action carries a full subtree, optionally including inline annotations. |
| `move_node` | Relocate an existing node (with its entire subtree) to a new location anchor. |

### Annotation actions

Annotations live inside annotation groups (`ExamplesGroup` or `GuidanceGroup`) attached to a `Paragraph` or `ListItem` host. See `prompt-model.md` for the model. Annotation actions operate on **individual** annotations within a group — groups themselves are never targeted directly.

| Action | Purpose |
|---|---|
| `add_example` / `add_guidance` | Add a new `Annotation` to a host's group. Creates the group if the host doesn't have one yet. |
| `update_example` / `update_guidance` | Replace the text of an existing annotation, identified by its ID. |
| `remove_example` / `remove_guidance` | Remove an annotation from its group. If it was the last annotation, the group is removed too. |

Examples and guidance are first-class actions — distinct from generic node operations — because they are the most common levers for improving a prompt and the actor LLM should be biased toward reaching for them.

**JSON shapes:**

- `add_example` / `add_guidance`:
  ```json
  {"action": "add_example", "host_id": "1.1", "text": "...", "anchor": {"after": "1.1.e2"}}
  ```
  `host_id` (required) — the Paragraph or ListItem to add to. `text` (required) — the annotation text. `anchor` (optional) — placement within the group; defaults to appending at the end. When provided, `anchor.target` must be an existing annotation ID in the host's group of the matching kind, or the host ID itself for `first_child`/`last_child`.

- `update_example` / `update_guidance`:
  ```json
  {"action": "update_example", "id": "1.1.e2", "text": "..."}
  ```
  `id` (required) — the annotation to update. `text` (required) — the replacement text.

- `remove_example` / `remove_guidance`:
  ```json
  {"action": "remove_example", "id": "1.1.e2"}
  ```
  `id` (required) — the annotation to remove. If this was the only annotation in its group, the group is removed; the host's `examples` (or `guidance`) attribute becomes `None`.

**Group lifecycle.** Add auto-creates a group when the host has none. Remove auto-deletes the group when the last annotation goes. Groups themselves cannot be added, removed, or updated by any action — they have no ID and no JSON-addressable identity.

**Undo IDs are fresh.** When a `remove_*` action's undo re-inserts the annotation, the restored annotation receives a **fresh** ID from a per-batch counter — not the original ID it had before removal. The per-batch counter skips any IDs already present in the frozen snapshot, so collisions are impossible. The text and position are preserved; only the addressable handle differs. This matches the broader "IDs are not durable" rule.

---

## Flows

### Optimization loop (single iteration)
1. The prompt is sent to a target LLM with sample inputs; results are collected.
2. A critique LLM analyzes the results and emits issues tagged by node ID.
3. Issues are aggregated across samples and sent to the actor LLM.
4. The actor LLM emits a batch of actions as structured JSON.
5. The executor applies the batch (see below) and produces the next prompt.

### Batch execution
1. Snapshot the current tree and freeze its IDs.
2. For each action in batch order:
   - If the action type is unknown → skip.
   - If required parameters are missing or unresolvable (e.g., target ID not in snapshot) → skip.
   - If extra/unexpected parameters are present → ignore them and proceed.
   - Otherwise apply the action and push its inverse onto the undo stack.
3. Recompute node and annotation IDs on the resulting tree.
4. Return the new tree plus a structured report of applied vs. skipped actions (with reasons) for the actor's next iteration.

### Undo
- Pop entries from the undo stack and apply them in reverse order.
- The resulting tree is structurally identical to a prior state (same node types, same text, same annotations, same shape) but IDs may differ — IDs are not durable.

---

## Behaviors & Rules

- **Skip-and-continue is the universal error policy.** The action stream is LLM-generated and inherently noisy. The executor is permissive: do an action if it has enough information; skip it otherwise; never abort the batch.
- **Lenient parameter handling.** Extra fields are ignored. Missing optional fields take defaults. Missing required fields cause the single action to skip, not the batch.
- **`delete_node` is polymorphic.** If the actor targets an annotation ID with `delete_node`, the executor honors it as an annotation removal.
- **`insert_node` carries full subtrees.** Containers (Section, List, ListItem) must be inserted with their contents — empty containers do not improve a prompt and are not a supported insertion target. Subtrees may include inline `examples` and `guidance` groups on Paragraph and ListItem nodes; each group's `children` is the list of `Annotation` nodes.
- **`move_node` moves the whole subtree.** Children come along; the action's location anchor describes where the subtree root lands.
- **`rewrite_node` does not change node type or structural flags.** Changing `List.ordered`, `CodeBlock.info`, or section heading level is out of scope; express such intent via `delete_node` + `insert_node`.
- **No promote/demote action.** Restructuring section hierarchy is expressed as `move_node`.
- **No split/merge action.** Reshaping is expressed via `delete_node` + `insert_node`.
- **Undo equivalence is by tree, not by ID.** The reversibility invariant is "same structure and text," which round-trips through `generate-conforming-prompt` to identical markdown. ID values are not part of the invariant.
- **Undo entries are per-action.** A partially applied batch (some actions applied, others skipped) produces one undo entry per applied action. Undoing rolls back only what was actually applied.

---

## Open Questions

None — all design decisions were resolved during the brainstorm.
