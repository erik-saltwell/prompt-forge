# Prompt Model — Markdown-to-Tree Parser

## Overview

The Prompt Model parses a markdown-formatted LLM prompt into a typed, hierarchical tree of nodes. Each node in the tree has a stable, addressable ID. The tree can be serialized back to conforming markdown, and any node or annotation can be targeted by a SCULPT-style optimization action. Three operations form the core contract: `validate-prompt`, `parse-prompt`, and `generate-conforming-prompt`.

The `parse-prompt` pipeline is also reused by the `insert_node` action (see `prompt-actions.md`) to materialise markdown-string subtrees into nodes — so any markdown the parser accepts as a top-level Document can be inserted as a subtree.

---

## Key Concepts

**Node** — A single element in the tree. Every node has a `type`, an `id`, and (where applicable) `text` and `children`.

**Container node** — A node that holds other nodes as children. The four container types are:
- `Document` — root of the tree; no id, no text
- `Section` — introduced by a heading; has `level` (1–6) and heading `text`
- `List` — ordered or unordered; has `ordered` flag; children are `ListItem` only
- `ListItem` — has `text` (first inline run) and optional block children

**Leaf node** — A node with no structural children. Content is collapsed to plain text. The four leaf types are: `Paragraph`, `CodeBlock` (with `info` for language hint), `Blockquote`, `Table`.

**Annotation** — A node type representing a single example or piece of guidance. An `Annotation` has only `text` and an `id`. It always lives as a child of an `ExamplesGroup` or `GuidanceGroup` — never directly on a host.

**Annotation group** — A node type that holds one or more `Annotation` children. Two kinds:
- `ExamplesGroup` — children render as the body of a `::: examples` directive.
- `GuidanceGroup` — children render as the body of a `::: guidance` directive.

Both groups have the same structure (`children: list[Annotation]`); they differ only in the directive label they emit. Groups have **no id** of their own — only their children do. A group can never be empty: when its last annotation is removed, the group itself is removed.

**Annotation host** — A `Paragraph` or `ListItem`. Each host has two optional attributes: `examples: ExamplesGroup | None` and `guidance: GuidanceGroup | None`. A host may carry at most one of each. No other node type can host annotations.

**Annotation block (directive container)** — Annotations are written as markdown directive containers:

```
::: examples
Body text of one example.
:::

::: guidance
- be concise
- be creative
:::
```

The opening line is `:::` followed by a kind name (`examples` or `guidance`); the closing line is `:::`. Recognized names:
- `examples` — canonical (plural) → `ExamplesGroup`
- `example` — accepted (singular alias) → `ExamplesGroup`
- `guidance` — canonical → `GuidanceGroup`

The parser follows **parse-loosely, write-strictly**: both `example` and `examples` are accepted on input; the canonical generator always emits `examples`.

**Directive body — two exclusive forms.** The content between the open and close lines must be **either**:

1. **Text form** — one or more paragraphs (possibly with inline markup). All paragraphs collapse into a **single** `Annotation` whose `text` is the paragraphs joined by `\n` with blank lines removed.
2. **List form** — a single flat unordered list. Each list item becomes one `Annotation`. The item's paragraph content (which may span multiple lines via softbreaks) becomes that annotation's `text`.

Anything else — mixed paragraphs and a list in the same directive, code blocks, blockquotes, tables, ordered lists, nested lists inside the list form — is a validation error.

**Annotation attachment rule** — A directive attaches to its **immediately preceding non-annotation sibling block at the same nesting level**. The host must be a `Paragraph` or `ListItem`. Multiple directives may follow one host; each attaches to the same host. A directive with no preceding non-annotation sibling at its nesting level is **orphan** and rejected by the validator.

A host may carry at most one `ExamplesGroup` and at most one `GuidanceGroup`. If the source has two directives of the same kind on the same host, the parser merges them defensively into one group and the validator emits an error.

Source order between the two kinds is unconstrained. The generator always emits examples before guidance on the same host.

**Conforming prompt** — The canonical markdown representation generated from a parsed tree. Round-tripping a conforming prompt produces an identical tree. Annotations are always emitted as `::: examples` / `::: guidance` directive blocks (plural, lower-case), examples before guidance on any given host.

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
- Determine the kind: `example`/`examples` → `ExamplesGroup`; `guidance` → `GuidanceGroup`.
- Locate the nearest preceding **non-annotation** sibling block at the same nesting level. That block is the host. The host must be a `Paragraph` or `ListItem`; attaching to other host types is a validation error.
- Inspect the body content between the open and close tokens:
  - If the body is one or more paragraphs (and nothing else): build **one** `Annotation` whose `text` is the paragraphs joined by `\n` with blank lines removed.
  - If the body is a single flat bullet list: build **one `Annotation` per list item**, with each item's paragraph content as the annotation's `text`.
  - Any other body shape is left to the validator to flag; the parser collects what `Annotation` nodes it can from any paragraph-or-UL children it finds.
- Attach to the host: if `host.examples` (or `host.guidance`) is `None`, create the group and set the attribute; otherwise append the new annotations to the existing group's `children` (defensive merge — the validator will flag the duplicate-directive case).

For `ListItem`s, the same extraction applies to annotation containers appearing as block children of the item.

**Phase 5 — ID assignment.** Depth-first traversal. Each node's `id` is its 1-based sibling position appended to its parent's id (e.g. `2.1.3`). Document and annotation groups have no id. Each `Annotation` receives a suffix `.e<n>` (in an `ExamplesGroup`) or `.g<n>` (in a `GuidanceGroup`), where `n` is its 1-based position in the group's `children` — e.g. a host `2.3` with three examples and two guidance items has annotations `2.3.e1`, `2.3.e2`, `2.3.e3`, `2.3.g1`, `2.3.g2`.

### 3. generate-conforming-prompt
Reconstructs markdown from the tree:
- `Section` → `{"#" * level} {text}`, followed by a blank line, followed by children separated by blank lines (MD022: headings are surrounded by blank lines)
- `List` → each `ListItem` as `- ` or `1. ` prefix, text, then annotation groups indented under the item, then block children indented. On a `ListItem` host the annotation groups **hug** the item — no blank line between the item text and its first `::: examples`/`::: guidance` block, and no blank line between adjacent annotation blocks. This keeps the annotation visually attached to the item it documents rather than appearing to belong to the next item.
- `Paragraph` → text, followed by `examples` group then `guidance` group as sibling blocks (separated by blank lines)
- `CodeBlock` → fenced with info string
- `Blockquote` → `> ` prefixed lines
- `Table` → reproduced as-is from collapsed text
- `ExamplesGroup` / `GuidanceGroup` — directive body chosen by child count:
  - **Single child** → text form: `::: examples` / annotation text / `:::`
  - **Multiple children** → list form: `::: examples` / `- <ann1>` / `- <ann2>` / … / `:::`. Multi-line annotation text in list form has continuation lines indented by 2 spaces.
  - On any host with both groups, `examples` is emitted before `guidance`.

---

## Behaviors & Rules

- `blank_line` and `thematic_break` tokens are ignored during parsing — they act as separators with no node representation.
- Inline elements (bold, italic, links, code spans) are **not separate nodes** in the model — they are part of the host block's text. Their raw source markup is preserved verbatim. Optimization actions operate on the block's text as a single string; they cannot target an inline span directly. Inline markup the author wrote (e.g. `**must follow**`) is preserved through parse/generate round-trips so semantic emphasis to the target LLM survives optimization.
- Annotations attach **only** to `Paragraph` and `ListItem`. `Document`, `List`, `Section`, `CodeBlock`, `Blockquote`, and `Table` cannot host annotations. An annotation container whose immediately preceding non-annotation sibling is not a Paragraph or ListItem is a validation error.
- Headings cannot appear inside list items. A heading token encountered while building a list subtree is a validation error.
- Headings cannot appear inside annotation containers. An annotation's body is restricted to paragraphs or a single flat unordered list (see "Directive body — two exclusive forms" above). Other block types — code blocks, blockquotes, tables, ordered lists, nested lists inside the UL form — are validation errors.
- Annotation containers cannot nest. An `::: examples` or `::: guidance` block inside another annotation container is a validation error.
- Blockquote contents are always collapsed to a single plain-text body, regardless of internal structure. Any block content inside a blockquote (paragraphs, headings, lists, code) is flattened to text and joined by newlines. No validation rule restricts what may appear inside a blockquote.
- `List` always gets its own ID segment — it is never transparent in the ID hierarchy. This prevents ID collisions when a section contains multiple sibling lists.
- `CodeBlock.info` (the fenced block language hint) is preserved and round-tripped.
- `ListNode.ordered` is preserved and round-tripped (bullet vs numbered).
- The recognized annotation kind names are `examples`, `example` (alias of `examples`), and `guidance`. Names outside this set are not annotations — they parse as ordinary paragraphs whose first line happens to start with `:::`.

---

## Open Questions

None — all design decisions were resolved during the brainstorm.
