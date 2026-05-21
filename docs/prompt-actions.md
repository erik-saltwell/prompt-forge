# Prompt Optimization Actions

## Overview

The optimization actions are a closed vocabulary of structured operations that mutate a parsed prompt tree (see `prompt-model.md`). An actor LLM, given critique feedback aggregated across sample runs, emits a batch of actions as JSON. Deterministic code applies them to produce a new prompt for the next optimization iteration.

---

## Key Concepts

**Action** — A single structured operation targeting one node or annotation by ID. Fully self-contained: any content the action introduces is written inline in the JSON. No second LLM call is needed to apply it.

**Batch** — The set of actions the actor LLM emits in one iteration. All IDs in a batch resolve against a frozen snapshot of the tree the actor was given.

**Frozen batch IDs** — IDs do not shift mid-batch. The executor resolves each action's IDs against the snapshot, not against the partially mutated tree. Across iterations, IDs are recomputed from scratch — they are not durable identifiers, only addressable handles within one batch.

**Location anchor** — How an action specifies where to place a node. Two flat fields on the action, with three position values:
- `"target": <id>, "position": "before"` — insert immediately before `<id>` (a sibling).
- `"target": <id>, "position": "after"` — insert immediately after `<id>` (a sibling).
- `"target": <id>, "position": "inside"` — insert as the only child of `<id>`. **Valid only when the target has no existing children** (empty `Section`, empty `ListItem`, or an annotation host with no group of the relevant kind). For containers that already have children, use `before`/`after` against an existing child instead.

The Document root is never a `target` — it cannot be empty, and you can always anchor `before`/`after` one of its root sections.

---

## The Action Vocabulary

Ten actions across two groups.

### Node actions

| Action | Purpose |
|---|---|
| `rewrite_node` | Replace the text of a node. Text-only; does not change node type or structural properties. |
| `delete_node` | Remove a node and its subtree. Operates on node IDs only — annotation IDs must be removed via `remove_example` / `remove_guidance` (polymorphic dispatch is a v2 feature). |
| `insert_node` | Add one or more nodes at a location anchor. The subtree payload is most naturally a markdown string (parsed via the standard pipeline); a Pydantic dict form is also accepted as an escape hatch. |
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
  {"action": "add_example", "host_id": "1.1", "text": "...", "target": "1.1.e2", "position": "after"}
  ```
  `host_id` (required) — the Paragraph or ListItem to add to. `text` (required) — the annotation text. `target` + `position` (optional, but both required if either is given) — placement within the group; omit both to append at the end. When provided, `target` must be either an existing annotation ID in the host's group of the matching kind (for `before`/`after`), or the host ID itself (for `position: "inside"`, valid only when the host has no group of that kind yet).

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

**Cross-batch IDs are not durable.** After each batch the ID assigner re-runs and overwrites everything. Within a single batch, the per-batch counter (`ApplyContext.mint_annotation_id`) hands out fresh annotation IDs for `add_*` actions; this is the only ID minting outside of the global assigner. An `ApplyContext` is threaded through `apply(tree, ctx)`; the parameter is optional and an ad-hoc context is built per call when omitted.

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
   - Otherwise apply the action.
3. Recompute node and annotation IDs on the resulting tree.
4. Return the new tree plus a structured report of applied vs. skipped actions (with reasons) for the actor's next iteration.

---

## Behaviors & Rules

- **Skip-and-continue is the universal error policy.** The action stream is LLM-generated and inherently noisy. The executor is permissive: do an action if it has enough information; skip it otherwise; never abort the batch.
- **Lenient parameter handling.** Extra fields are ignored. Missing optional fields take defaults. Missing required fields cause the single action to skip, not the batch.
- **`delete_node` is node-only (v1).** Targeting an annotation ID with `delete_node` skips. Annotations must be removed via `remove_example` / `remove_guidance`. Polymorphic dispatch is deferred to v2.
- **`insert_node` subtree forms.** The `subtree` field accepts either:
  - **Markdown string (preferred).** Parsed via the same `parse_from_string` pipeline used for initial prompt parsing. Whatever the markdown produces at the `Document` root becomes the inserted roots — including `::: examples` / `::: guidance` directive blocks attached to new hosts. This is the natural form for the actor LLM because it requires no schema knowledge beyond plain markdown.
  - **Pydantic dict (escape hatch).** A `node_type`-discriminated dict matching the Pydantic schema. Yields a single root. Useful when surgical control over a structural flag (`List.ordered`, `CodeBlock.info`, `Section.level`) matters more than ergonomic input.
- **`insert_node` splat and auto-wrap.** A markdown payload may parse to multiple top-level blocks; all of them are inserted at adjacent indices starting at the resolved anchor. Type/parent compatibility is repaired with the same rules `move_node` uses:
  - A `ListItem` root landing in a non-`List` parent is wrapped in a fresh `List(ordered=False)`. (There is no source list to inherit `ordered` from, so the wrap defaults to unordered.) Adjacent `ListItem` roots are wrapped together into one fresh `List`.
  - A `List` root landing inside another `List` is unwrapped — its `ListItem` children splat into the destination list. This makes `"- one\n- two"` Just Work when targeted as a sibling of an existing list item.
  - A non-`ListItem` root targeted at a `List` parent skips with `InvalidStructure`.
- **`insert_node` empty containers.** Containers (Section, List) must be inserted with their contents — an `insert_node` whose markdown is just `## heading` (no body) parses to an empty Section and is skipped with `InvalidSubtree`. Same rule applies to the dict form. ListItem-with-no-body-children is fine because the item carries its own `text`.
- **`move_node` moves the whole subtree.** Children come along (including any `examples` / `guidance` groups on host nodes); the action's location anchor describes where the subtree root lands.
- **`move_node` is node-only (v1).** Targeting an annotation ID with `move_node` skips, same as `delete_node`. Polymorphic dispatch is deferred to v2.
- **`move_node` JSON shape.** `{"action": "move_node", "id": "<node_id>", "target": "<anchor_id>", "position": "<before|after|inside>"}`. All four fields required.
- **`move_node` skip conditions.**
  - Target ID does not resolve to a node, or resolves to an annotation, the Document root, or an annotation group.
  - Anchor does not resolve.
  - Anchor target is the moved node itself or a descendant of it (cycle).
  - The resolved destination would equal the node's current slot (no-op).
  - Type/host rules below are violated.
- **`move_node` type/host rules.**
  - `ListItem` may land only as a child of a `List`. If the resolved destination is a non-`List` parent (e.g., a `Section`), the executor **auto-wraps** the moved `ListItem` in a fresh `List` whose `ordered` flag is **inherited from the source list**.
  - Non-`ListItem` nodes may not land directly under a `List`.
  - `Section` and annotation groups are never the moved node themselves under v1 type rules — `Section` *can* be moved structurally, but its `level` is **auto-adjusted to fit the new parent's section depth** (rather than left literal and risking a level-skip validation error). Annotation groups have no ID and cannot be addressed.
- **`move_node` source cleanup.** If removing the node leaves its source `List` empty, the now-empty `List` is also removed (an empty `List` cannot be reserialised to conforming markdown).
- **`rewrite_node` does not change node type or structural flags.** Changing `List.ordered`, `CodeBlock.info`, or section heading level is out of scope; express such intent via `delete_node` + `insert_node`.
- **No promote/demote action.** Restructuring section hierarchy is expressed as `move_node`.
- **No split/merge action.** Reshaping is expressed via `delete_node` + `insert_node`.

---

## Open Questions

None — all design decisions were resolved during the brainstorm.
