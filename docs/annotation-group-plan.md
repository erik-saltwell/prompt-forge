# Annotation Group Refactor — Implementation Plan

## Goal

Replace the current "one example string, one guidance string per host" model with **annotation groups**: a host (Paragraph or ListItem) may have at most one `ExamplesGroup` and at most one `GuidanceGroup`, each containing one or more `Annotation` children with stable, addressable IDs.

This is required so the actor LLM can add, remove, and update individual examples or guidance items independently rather than treating each kind as an atomic blob.

---

## Decisions (from grilling)

| Topic | Decision |
|---|---|
| Annotation type | Single `Annotation` node type — kind is carried by the parent group |
| Parent attributes | `Paragraph.examples` / `Paragraph.guidance` (and same on `ListItem`) — each is `ExamplesGroup \| None` / `GuidanceGroup \| None` |
| Group child list | `children: list[Annotation]` (matches existing container convention) |
| Group IDs | Groups have no ID (inherited field stays `None`) |
| Annotation IDs | `<host_id>.e<n>` and `<host_id>.g<n>` — e.g. `1.1.e1`, `1.1.e2`, `1.1.g1` |
| Mixed paragraphs + UL in a directive | Validation error |
| Non-paragraph / non-UL content in a directive | Validation error (no code blocks, blockquotes, tables, ordered lists, headings) |
| Nested list inside an annotation UL | Validation error |
| Multiple `::: examples` directives per host | Validator rejects; parser merges defensively into one group |
| Source order of `::: examples` vs `::: guidance` | Parser accepts any order; emitter is canonical (examples-then-guidance) |
| Action vocabulary | Six kind-specific actions: `add_example`, `add_guidance`, `remove_example`, `remove_guidance`, `update_example`, `update_guidance` |
| Add action shape | `host_id` (required) + optional `anchor`; group is auto-created if missing |
| Default add position | Append at end of group |
| Group auto-removal | When the last annotation is removed, the group is removed too |
| Undo for remove | An add action with a fresh annotation ID (not the original); per-batch ID counter skips frozen-snapshot IDs |
| Shorthand grammar | `e` / `g` tokens append to the host's group of that kind; any interleaving allowed |
| Multi-line annotation in list form | Continuation lines indented to align (reuse existing `_render_list_item` indent logic) |
| New validation rules | `AnnotationContentIsParagraphsOrUL` and `NoNestedListInAnnotation` |

---

## Generation rules (canonical form)

- **Examples group is always emitted before guidance group** on the same host.
- **Single-annotation group** is emitted as text form:

  ```
  ::: examples
  one example text
  :::
  ```

- **Multi-annotation group** is emitted as a flat unordered list:

  ```
  ::: examples
  - first example
  - second example
  - third example
  :::
  ```

- An empty group is never emitted (it cannot exist — removing the last annotation deletes the group).

---

## Parsing rules

A directive (`::: examples` / `::: guidance`) may contain **exactly one** of:

1. One or more paragraphs (with inline markup) → collapsed into a single `Annotation` whose `text` joins the paragraph contents with `\n`, with blank lines removed.
2. A single flat unordered list, where each list item becomes one `Annotation` (its `text` is the item's paragraph content, possibly multi-line via softbreaks).

Anything else (mixed content, code blocks, blockquotes, tables, ordered lists, headings, nested lists inside the UL) is a validation error.

Two consecutive `::: examples` directives on the same host: the parser merges them into one `ExamplesGroup` defensively, and the validator emits an error (this is already covered by the existing `NoDuplicateAnnotationKind` rule, which continues to apply).

Source ordering of `::: examples` vs `::: guidance` is irrelevant to parsing; emission always reorders to examples-first.

---

## Phases

### Phase 0 — Plan (this document)

Write this plan. *Current phase.*

### Phase 1 — Update authoritative documentation

Files in `docs/`:

- `prompt-model.md` — update annotation section: introduce `ExamplesGroup`, `GuidanceGroup`, `Annotation`; update parent attribute names; update ID scheme; update parsing rules (text vs list form, two-form rule, mixed-content error, no nested lists).
- `prompt-actions.md` — confirm the six annotation actions; specify add/remove JSON shape (`host_id`, optional `anchor`, `text` for add; `id` for remove/update); document group auto-create on add and auto-remove on last-removed; document the fresh-id rule for undo.
- `prompt-validation.md` — document two new rules: `AnnotationContentIsParagraphsOrUL` and `NoNestedListInAnnotation`. Confirm `NoDuplicateAnnotationKind` still applies.
- `test-infra.md` — update shorthand grammar section: `e` and `g` tokens now append to the host's group instead of overwriting; provide updated examples (`p e e e g g`).

### Phase 2 — Update memory

Files in `~/.claude/projects/-home-eriksalt-proj-prompt-forge/memory/`:

- `project_prompt_model.md` — replace `ExampleAnnotation`/`GuidanceAnnotation` bullets with the new group/annotation triple; update ID scheme line.
- `project_prompt_actions.md` — note the six annotation actions plus group auto-create/auto-remove invariant.
- `project_prompt_validation.md` — list the two new rules.
- `project_test_infra.md` — note shorthand `e`/`g` is now appending, not overwriting.

### Phase 3 — Model layer

Files:

- `src/prompt_model/model/_base.py` — `NodeType` enum: remove `ExampleAnnotation`, `GuidanceAnnotation`; add `Annotation`, `ExamplesGroup`, `GuidanceGroup`.
- `src/prompt_model/model/annotations.py` — replace `ExampleAnnotation` / `GuidanceAnnotation` with three classes: `Annotation` (text), `ExamplesGroup` (children: list[Annotation], to_markdown writes `::: examples` text/list form), `GuidanceGroup` (same shape, label "guidance").
- `src/prompt_model/model/nodes.py` — `Paragraph` and `ListItem`: replace `example: ExampleAnnotation \| None` / `guidance: GuidanceAnnotation \| None` with `examples: ExamplesGroup \| None` / `guidance: GuidanceGroup \| None`. Update `to_markdown` and `_render_list_item` to call the group's `to_markdown`.
- `src/prompt_model/model/__init__.py` — update exports: remove `ExampleAnnotation`/`GuidanceAnnotation`, add `Annotation`, `ExamplesGroup`, `GuidanceGroup`.

### Phase 4 — Parser + ID assigner

Files:

- `src/prompt_model/service/parsing/_tree_builder.py` — `_attach_annotation` becomes a per-host group-builder: for each directive, build a list of `Annotation` nodes (one if text-form; one per LI if list-form); attach to host's `examples` or `guidance` (create group if absent, append if exists — defensive merge for the duplicate-directive case).
- `src/prompt_model/service/parsing/_id_assigner.py` — when assigning IDs to a host, iterate `host.examples.children` and `host.guidance.children`, emitting `<host_id>.e<n>` / `<host_id>.g<n>`. Groups themselves get no ID.

### Phase 5 — Markdown generation

Files:

- `src/prompt_model/model/annotations.py` — `ExamplesGroup.to_markdown` and `GuidanceGroup.to_markdown` emit text form for single annotation, list form for multi-annotation. List form uses `-` markers and joins items with `\n`. Multi-line annotation text inside list form indents continuation lines by 2 spaces.

### Phase 6 — Shorthand + tree-equality

Files:

- `tests/utils/_short_hand.py` — `doc_from_shorthand`: `e` token appends a new `Annotation` to host's `examples` (create group if missing); same for `g`. `shorthand_to_markdown`: same logic in the parallel dict-based implementation. `tree_to_shorthand`: emit one `e` per annotation in `examples.children` and one `g` per annotation in `guidance.children`.
- `tests/utils/_tree_comparison.py` — `structural_equal` for `Paragraph`/`ListItem`: compare `examples` and `guidance` as groups (recurse into `children`).

### Phase 7 — Get existing tests green

Touch:

- `tests/parsing/test_parse_prompt.py` and `tests/parsing/test_markdown_generation.py` — update any fixtures or assertions that touch `.example` / `.guidance` to use the new shape. Most existing single-annotation cases should still pass with minimal changes once the new ID scheme keeps `.e1` / `.g1` for single annotations.
- Existing test fixtures under `tests/fixtures/` (if any) — audit for now-illegal directive contents (mixed, ordered list, code block); either fix fixture or move to a "should fail validation" set.

### Phase 8 — Update `update_annotation` action

Files:

- `src/prompt_model/service/actions/update_annotation.py` — `_find_host` walks `host.examples.children` / `host.guidance.children` instead of looking at `host.example` / `host.guidance` directly. Resolves annotation by ID match within the group.
- `tests/actions/test_update_annotation.py` — keep existing single-annotation tests; add multi-annotation tests that verify the update only touches the targeted annotation.
- `tests/utils/actions.py` — no changes expected (helpers are layer-agnostic).

### Phase 9 — New validation rules

Files:

- `src/prompt_model/service/validation/_rules/annotation_content_is_paragraphs_or_ul.py` — scan a directive's direct children; if not (all-paragraphs or single bullet_list), emit error.
- `src/prompt_model/service/validation/_rules/no_nested_list_in_annotation.py` — inside an annotation UL, reject nested lists.
- `src/prompt_model/model/prompt_validation_error.py` — add two new `PromptErrorType` enum members.
- `src/prompt_model/service/validation/__init__.py` — register the new rules.
- `tests/parsing/test_validate_prompt.py` and fixtures — add positive and negative cases for both rules.

### Phase 10 — New `add_*` / `remove_*` actions

Files:

- `src/prompt_model/service/actions/add_annotation.py` — `AddExampleAction` and `AddGuidanceAction`. JSON fields: `host_id` (required), `text` (required), `anchor` (optional). `validate`: host exists and is Paragraph/ListItem; anchor (if given) must reference an annotation in the matching group; text non-empty. `apply`: create group if missing; insert annotation at anchor position (default append); return a `RemoveExampleAction`/`RemoveGuidanceAction` keyed on the new annotation's ID.
- `src/prompt_model/service/actions/remove_annotation.py` — `RemoveExampleAction` and `RemoveGuidanceAction`. JSON fields: `id` (required, the annotation ID). `validate`: annotation exists. `apply`: remove annotation; if its group is now empty, remove the group too; return an `AddExampleAction`/`AddGuidanceAction` carrying the removed text and an anchor reconstructed from the removed annotation's position (`{"after": prev_sibling_id}` or `{"first_child": host_id}` if it was first; or no anchor if it was the only one and the group was deleted).
- `src/prompt_model/service/actions/__init__.py` — export new classes.
- `src/prompt_model/service/actions/registry.py` — no changes (decorators self-register).
- `tests/actions/test_add_annotation.py` — new tests covering: add to host without existing group; add to host with existing group (append default); add with explicit anchor (before/after/first_child/last_child); add then undo; group auto-create.
- `tests/actions/test_remove_annotation.py` — new tests covering: remove middle annotation; remove first/last; remove only annotation (group also deleted); remove then undo restores annotation at correct position; remove with non-existent ID returns `AnnotationNotFound` skip.

### Phase 11 — Per-batch ID counter

Files:

- The executor (location TBD — actions module or a new `executor.py`) — track a per-batch counter for fresh annotation IDs; when an undo path needs to insert a new annotation, draw from this counter. IDs must not collide with any frozen-snapshot ID. Format: `<host_id>.e<n>` where `n` is past the snapshot's max for that host.

This phase may be empty if the existing executor already centralizes ID generation — confirm during Phase 10 implementation.

---

## Out of scope

- Changing the SCULPT optimization loop or evaluator.
- Adding annotation kinds beyond `examples` / `guidance`.
- Allowing code blocks, tables, or other block content inside annotations.
- Supporting durable annotation IDs across batches (IDs remain per-batch handles).

---

## Risk register

- **Test fixture churn**: directive-content rules (Phase 9) may reject existing test fixtures that worked under the lenient parser. Audit during Phase 7.
- **Round-trip stability for multi-line annotations**: continuation indent (Phase 5) must match what markdown-it parses back as one LI. Add a round-trip test for `e e` with multi-line text.
- **Anchor reconstruction for remove undo**: if the removed annotation was the only child and the group was deleted, the undo's anchor cannot point at a sibling. Use no anchor in that case; the add will recreate the group.
- **Frozen-batch ID collision**: ensure the per-batch ID counter (Phase 11) genuinely avoids snapshot IDs, including for cross-host adds.
