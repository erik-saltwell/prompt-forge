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

**Annotation** — Not a node. A typed attachment on a `Paragraph` or `ListItem` that enhances it without being part of the main content. Two kinds: `ExampleAnnotation` and `GuidanceAnnotation`. Annotations have their own IDs.

**Conforming prompt** — The canonical markdown representation generated from a parsed tree. Round-tripping a conforming prompt produces an identical tree.

---

## Flows

### 1. validate-prompt
Checks that the markdown can be cleanly parsed before attempting it. Primary rules:
- No heading level skips (e.g. h1 → h3 without h2)
- Annotation lines are trailing within their block (no regular text line follows an annotation line)
- Annotation text is not empty

### 2. parse-prompt (5 phases)

**Phase 1 — Mistune parse.** Run mistune with the table plugin and `AstRenderer`. Produces a flat list of block tokens.

**Phase 2 — Section hierarchy.** Walk the flat block list with a heading stack. On each heading token, pop the stack until the top is a container with a lower heading level (or Document), then push a new `SectionNode`. All other block tokens attach to the current stack top.

**Phase 3 — List hierarchy.** Mistune's list AST is already recursive. Walk it to produce `ListNode` and `ListItemNode` trees. For each `ListItem`, the first child (`block_text` for tight items, `paragraph` for loose) becomes the item's `text`. Remaining children (nested lists, paragraphs, code blocks) become `children`.

**Phase 4 — Annotation extraction.** For every `Paragraph` and `ListItem` text, flatten inline tokens to a string (rendering `softbreak` as `\n` to preserve line structure). Split on `\n`. Lines matching the pattern `^\s*(example|guidance)\s*:\s*(.+)$` (case-insensitive) become annotations — `example` → `ExampleAnnotation`, `guidance` → `GuidanceAnnotation`. The prefix word is case-insensitive and may have optional whitespace before the colon. All annotation lines must be trailing — regular text lines may not follow them.

**Phase 5 — ID assignment.** Depth-first traversal. Each node's `id` is its 1-based sibling position appended to its parent's id (e.g. `2.1.3`). Document has no id. Annotations receive a suffix: first example on node `2.3` is `2.3.e1`; first guidance item is `2.3.g1`.

### 3. generate-conforming-prompt
Reconstructs markdown from the tree:
- `Section` → `{"#" * level} {text}`, followed by children separated by blank lines
- `List` → each `ListItem` as `- ` or `1. ` prefix, text, then annotation lines indented with single `\n`, then block children indented
- `Paragraph` → text, then annotation lines separated by single `\n` (not a blank line)
- `CodeBlock` → fenced with info string
- `Blockquote` → `> ` prefixed lines
- `Table` → reproduced as-is from collapsed text
- Blocks separated by a blank line (`\n\n`); annotation lines separated by single `\n`

---

## Behaviors & Rules

- `blank_line` and `thematic_break` tokens are ignored during parsing — they act as separators with no node representation.
- Inline elements (bold, italic, links, code spans) are collapsed to plain text within any block node. No inline structure is preserved in the model.
- Annotations attach **only** to `Paragraph` and `ListItem`. `Document`, `List`, `Section`, `CodeBlock`, `Blockquote`, and `Table` cannot have annotations.
- Headings cannot appear inside list items. A heading token encountered while building a list subtree is a validation error.
- Blockquote contents are always collapsed to a single plain-text body, regardless of internal structure. Any block content inside a blockquote (paragraphs, headings, lists, code) is flattened to text and joined by newlines. No validation rule restricts what may appear inside a blockquote.
- `List` always gets its own ID segment — it is never transparent in the ID hierarchy. This prevents ID collisions when a section contains multiple sibling lists.
- `CodeBlock.info` (the fenced block language hint) is preserved and round-tripped.
- `ListNode.ordered` is preserved and round-tripped (bullet vs numbered).
- Annotation text is everything after the `example:` or `guidance:` prefix (case-insensitive, with optional whitespace before the colon), stripped of leading/trailing whitespace.

---

## Open Questions

None — all design decisions were resolved during the brainstorm.
