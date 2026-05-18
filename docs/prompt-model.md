# Prompt Model — Markdown-to-Tree Parser

## Overview

The Prompt Model parses a markdown-formatted LLM prompt into a typed, hierarchical tree of nodes. Each node in the tree has a stable, addressable ID. The tree can be serialized back to conforming markdown, and any node or annotation can be targeted by a SCULPT-style optimization action. Three operations form the core contract: `validate-prompt`, `parse-prompt`, and `generate-conforming-prompt`.

---

## Key Concepts

**Node** — A single element in the tree. Every node has a `type`, an `id`, and (where applicable) `text` and `children`.

**Container node** — A node that holds other nodes as children. The four container types are:
- `Document` — root of the tree; no id, no text
- `Section` — introduced by a heading; has `level` (1–6) and heading `text`
- `List` — ordered or unordered; has `ordered` flag; children are `ListItem` only
- `ListItem` — has `text` (first inline run) and optional block children

**Leaf node** — A node with no structural children. Content is collapsed to plain text. The four leaf types are: `Paragraph`, `CodeBlock` (with `info` for language hint), `Blockquote`, `Table`.

**Annotation** — Not a node. A typed attachment on a `Paragraph` or `ListItem` that enhances it without being part of the main content. Two kinds: `ExampleAnnotation` and `GuidanceAnnotation`. Each kind is its own delimited block; a host may carry at most one block of each kind (at most one `::: examples` and at most one `::: guidance`). Multiple concrete examples or pieces of guidance go inside the single block as list items or paragraphs. Annotations have their own IDs.

**Annotation block (directive container)** — Annotations are written as markdown directive containers:

```
::: examples
Body text of the annotation.
:::

::: guidance
- be concise
- be creative
:::
```

The opening line is `:::` followed by a kind name (`examples` or `guidance`); the closing line is `:::`. Recognized names:
- `examples` — canonical (plural) → `ExampleAnnotation`
- `example` — accepted (singular alias) → `ExampleAnnotation`
- `guidance` — canonical → `GuidanceAnnotation`

The parser follows **parse-loosely, write-strictly**: both `example` and `examples` are accepted on input; the canonical generator always emits `examples`.

The content between the open and close lines is the annotation's body. It is full markdown (paragraphs, lists, inline formatting, code blocks). Inline formatting is collapsed to plain text per the standard node rules; structural content (lists, code blocks) is preserved as the annotation's body markdown.

**Annotation attachment rule** — An annotation container attaches to its **immediately preceding non-annotation sibling block at the same nesting level**. Multiple annotation containers may follow a single host; each attaches to the same host (the nearest preceding non-annotation sibling). An annotation container with no preceding non-annotation sibling at its nesting level is **orphan** and rejected by the validator.

A single host (Paragraph or ListItem) may carry at most one `ExampleAnnotation` block and at most one `GuidanceAnnotation` block. Order between the two kinds is unconstrained.

**Conforming prompt** — The canonical markdown representation generated from a parsed tree. Round-tripping a conforming prompt produces an identical tree. Annotations are always emitted as `::: examples` / `::: guidance` directive blocks (plural, lower-case).

---

## Flows

### 1. validate-prompt
Checks that the markdown can be cleanly parsed before attempting it. See `prompt-validation.md` for the full rule list. Key checks:
- No heading level skips
- No headings inside list items
- No empty annotations (`::: examples` / `:::` with no body content)
- No orphan annotations (annotation containers with no host to attach to)

### 2. parse-prompt (5 phases)

**Phase 1 — markdown-it parse.** Run markdown-it (commonmark preset) with the `table` rule enabled and the `markdown-it-container` plugin registered for the names `example`, `examples`, and `guidance`. Produces a flat token stream where each directive becomes `container_<name>_open` / `container_<name>_close` token pairs.

**Phase 2 — Section hierarchy.** Walk the flat block list with a heading stack. On each heading token, pop the stack until the top is a container with a lower heading level (or Document), then push a new `SectionNode`. All other block tokens attach to the current stack top.

**Phase 3 — List hierarchy.** Walk markdown-it's recursive list tokens to produce `ListNode` and `ListItemNode` trees. For each `ListItem`, the first inline run becomes the item's `text`; remaining block children (nested lists, paragraphs, code blocks, annotation containers) become `children`.

**Phase 4 — Annotation attachment.** For every `container_<kind>_open` token (where `<kind>` is `example`, `examples`, or `guidance`):
- Determine the kind: `example`/`examples` → `ExampleAnnotation`; `guidance` → `GuidanceAnnotation`.
- Locate the nearest preceding **non-annotation** sibling block at the same nesting level. That block is the host. The host must be a `Paragraph` or `ListItem`; attaching to other host types is a validation error (and prevented earlier, because annotations are only legal where their preceding sibling is one of those types).
- Extract the body content between the container's open and close tokens. The body's textual representation becomes the annotation's `text`. If the body contains structural content (e.g. an inner bullet list), each top-level child of the body produces a separate annotation entry of the same kind (mirroring the prior list-form behavior): one paragraph child → one annotation with that paragraph's text; one bullet list child → one annotation per list item.

For ListItems, the same extraction applies to annotation containers appearing as block children of the item.

**Phase 5 — ID assignment.** Depth-first traversal. Each node's `id` is its 1-based sibling position appended to its parent's id (e.g. `2.1.3`). Document has no id. Annotations receive a suffix counted **per kind across all annotations on the same host, in document order** — e.g. a host `2.3` with two examples, then one guidance, then one more example receives `2.3.e1`, `2.3.e2`, `2.3.g1`, `2.3.e3`.

### 3. generate-conforming-prompt
Reconstructs markdown from the tree:
- `Section` → `{"#" * level} {text}`, followed by children separated by blank lines
- `List` → each `ListItem` as `- ` or `1. ` prefix, text, then annotation containers indented under the item, then block children indented
- `Paragraph` → text, followed by annotation containers as sibling blocks (separated by blank lines)
- `CodeBlock` → fenced with info string
- `Blockquote` → `> ` prefixed lines
- `Table` → reproduced as-is from collapsed text
- Annotations → `::: examples` / `:::` or `::: guidance` / `:::` (canonical plural for examples), separated from siblings by blank lines

---

## Behaviors & Rules

- `blank_line` and `thematic_break` tokens are ignored during parsing — they act as separators with no node representation.
- Inline elements (bold, italic, links, code spans) are collapsed to plain text within any block node. No inline structure is preserved in the model.
- Annotations attach **only** to `Paragraph` and `ListItem`. `Document`, `List`, `Section`, `CodeBlock`, `Blockquote`, and `Table` cannot host annotations. An annotation container whose immediately preceding non-annotation sibling is not a Paragraph or ListItem is a validation error.
- Headings cannot appear inside list items. A heading token encountered while building a list subtree is a validation error.
- Headings cannot appear inside annotation containers. An annotation's body is restricted to flow content (paragraphs, lists, code blocks, blockquotes, tables).
- Annotation containers cannot nest. An `::: examples` or `::: guidance` block inside another annotation container is a validation error.
- Blockquote contents are always collapsed to a single plain-text body, regardless of internal structure. Any block content inside a blockquote (paragraphs, headings, lists, code) is flattened to text and joined by newlines. No validation rule restricts what may appear inside a blockquote.
- `List` always gets its own ID segment — it is never transparent in the ID hierarchy. This prevents ID collisions when a section contains multiple sibling lists.
- `CodeBlock.info` (the fenced block language hint) is preserved and round-tripped.
- `ListNode.ordered` is preserved and round-tripped (bullet vs numbered).
- The recognized annotation kind names are `examples`, `example` (alias of `examples`), and `guidance`. Names outside this set are not annotations — they parse as ordinary paragraphs whose first line happens to start with `:::`.

---

## Open Questions

None — all design decisions were resolved during the brainstorm.
