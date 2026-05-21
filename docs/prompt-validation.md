# Prompt Validation

## Overview

`validate-prompt` checks that a markdown-formatted prompt can be parsed into a well-formed tree per `prompt-model.md` before parsing is attempted. The contract is one-way and absolute: **if validation passes, parsing produces a well-formed tree** (every invariant in the prompt model holds). The validator does not attempt to second-guess author intent or catch stylistic issues — it enforces the structural and content rules required by the parser, no more.

The same validator is the final gate for structural action mutations (`insert_node`, `delete_node`, `move_node`): the executor renders the post-mutation tree to markdown, runs it through `validate-prompt`, and skips the action if any rule fires. This means new content inserted via `insert_node` — including markdown-string subtrees parsed via the standard pipeline — must satisfy the same rules as content authored directly in a prompt file.

---

## Key Concepts

**Well-formed tree** — A parsed tree in which every node and annotation obeys the invariants defined in `prompt-model.md`: heading hierarchy is stack-consistent, annotations attach only to legal hosts, no node has degenerate empty content where the spec requires non-empty content, and so on.

**Validation contract** — The promise that `validate-prompt → pass` implies `parse-prompt` produces a well-formed tree.

**Heading stack** — The sequence of currently open Section levels during a top-to-bottom walk of heading tokens. Used by both the parser (Phase 2 — Section hierarchy) and the validator to determine legal next-heading levels.

**Annotation container** — A markdown directive container of the form `::: <kind>` … `:::`, where `<kind>` is one of the recognized annotation names (`examples`, `example`, `guidance`). Tokenized by `markdown-it-container` as a matched pair of `container_<kind>_open` / `container_<kind>_close` tokens with full block content between them. Recognition is **structural, not textual** — there are no line-by-line prefix regexes to maintain on the validator side.

**Annotation host** — The block an annotation container attaches to: its immediately preceding **non-annotation** sibling block at the same nesting level. Legal host types are `Paragraph` and `ListItem`.

**Degenerate node** — A node whose required text content is empty after parsing. Examples: a Section with an empty heading, a ListItem with no body text, an annotation container with no body content. The validator rejects these.

---

## Validation Rules

### Heading rules
- **No level skips.** At each heading, its level must be ≤ (current open section's level + 1). Going shallower is unrestricted (it closes sections off the stack); going deeper may open at most one new level.
- The first heading establishes the root level — starting at h2 (or any level) is allowed, but headings inside the document may not skip from there.
- **No empty headings.** A heading token with no text content is rejected.
- **No headings inside list items.** Any heading encountered while traversing a `ListItem`'s block children is a validation error.
- **No headings inside annotation containers.** Any heading encountered inside an `::: examples` / `::: example` / `::: guidance` container is a validation error.
- **No rule on heading depth > 6.** Markdown parses `####### foo` as a paragraph; the resulting tree is well-formed. The author's intent is not checked.

### List rules
- **No empty list items.** A `list_item` with no inline text content is rejected.
- **No mixed list-type siblings.** Adjacent sibling lists may not mix `bullet_list` and `ordered_list`.

### Annotation rules
- **Empty annotation rejected.** An `::: examples` / `::: example` / `::: guidance` container with no body content (no child blocks, or only empty child blocks) is rejected.
- **Orphan annotation rejected.** An annotation container with no preceding non-annotation sibling block at its nesting level is rejected. There is no host to attach to.
- **Illegal host rejected.** The host found by the attachment rule must be a `Paragraph` or `ListItem`. If the preceding non-annotation sibling is a `CodeBlock`, `Blockquote`, `Table`, `List`, or `Section` (impossible by structure but listed for completeness), the annotation is rejected.
- **No nested annotations.** An annotation container may not contain another annotation container in its body.
- **At most one annotation block of each kind per host.** A host (`Paragraph` or `ListItem`) may carry at most one `ExamplesGroup` block and at most one `GuidanceGroup` block. Multiple examples or multiple guidance items live *inside* the single group as separate `Annotation` children. `example` and `examples` are the same kind for purposes of this rule (the alias does not let you bypass it).
- **Annotation content must be paragraphs-or-UL** (rule: `AnnotationContentIsParagraphsOrUL`). The body of an annotation directive must be **exactly one** of:
  - One or more paragraphs (collapsed into a single `Annotation` on parse), **or**
  - A single flat unordered list (one `Annotation` per item on parse).
  Any other body shape — mixed paragraph + list, code block, blockquote, table, ordered list — is rejected. The error message identifies which disallowed block kind was seen.
- **No nested list inside an annotation UL** (rule: `NoNestedListInAnnotation`). When an annotation directive uses the list form, each list item's content must be a single paragraph (possibly multi-line). Nested lists inside an item are rejected.
- **No annotation fence inside a paragraph** (rule: `NoAnnotationFenceInParagraph`). A line of the form `::: examples` / `::: example` / `::: guidance` that ends up inside a paragraph's inline content (because it is indented four or more spaces, and so is treated as a lazy continuation rather than a container open) is rejected. This is the one author-intent check the validator makes: the line *looks* like a container open but silently parses as prose, so the resulting tree contradicts what the author plainly wrote. Inserting a blank line before the fence and removing leading indentation is the fix.
- **No `:::` text outside containers is validated.** A line like `::: foo` where `foo` is not a recognized kind parses as a regular paragraph; it is not subject to annotation rules.

### Document-level rules
- **No empty document.** A document with zero blocks is rejected.

### Out-of-scope (no rules)
- **Blockquote contents** — the parser collapses any internal structure (paragraphs, headings, lists, code) into a single plain-text body. No validation rule restricts what may appear inside.
- **Unclosed code fences** — the parser auto-closes at EOF; the resulting `CodeBlock` is well-formed.
- **Malformed tables** — the parser falls back to a `Paragraph` representation; the resulting tree is well-formed.
- **Empty sections** — a Section with no body children is a valid structural element (e.g., a placeholder heading); the heading itself has text.
- **Empty paragraphs** — markdown cannot express these (blank lines separate, not create), so no rule is needed.
- **Empty lists** — markdown cannot express these, so no rule is needed.

---

## Behaviors & Rules

- **Structural recognition.** Annotation recognition is delegated to `markdown-it-container`. The validator inspects token types (`container_<kind>_open` / `container_<kind>_close`) — it does not parse annotation syntax itself. The parser/validator symmetry tax of the previous prefix-based design is eliminated.
- **Parse-loosely, write-strictly.** `example` and `examples` are both accepted as kind names on input. The canonical generator always emits `examples`.
- **No intent checks.** The validator does not catch author mistakes that produce a well-formed tree with surprising semantics — `####### foo` becoming a paragraph, a malformed table falling back to a paragraph, an `Example` typo inside a Blockquote being treated as text. These all pass.
- **Clear failure messages.** Each validation rule, when violated, must produce a message that identifies the offending location and explains what to fix.

---

## Open Questions

None — all design decisions were resolved during the brainstorm.
