# Prompt Validation

## Overview

`validate-prompt` checks that a markdown-formatted prompt can be parsed into a well-formed tree per `prompt-model.md` before parsing is attempted. The contract is one-way and absolute: **if validation passes, parsing produces a well-formed tree** (every invariant in the prompt model holds). The validator does not attempt to second-guess author intent or catch stylistic issues — it enforces the structural and content rules required by the parser, no more.

---

## Key Concepts

**Well-formed tree** — A parsed tree in which every node and annotation obeys the invariants defined in `prompt-model.md`: heading hierarchy is stack-consistent, annotations attach only to legal hosts, no node has degenerate empty content where the spec requires non-empty content, and so on.

**Validation contract** — The promise that `validate-prompt → pass` implies `parse-prompt` produces a well-formed tree. This requires the validator and parser to use the same recognition rules wherever the parser interprets ambiguous input (most notably annotation prefixes).

**Heading stack** — The sequence of currently open Section levels during a top-to-bottom walk of heading tokens. Used by both the parser (Phase 2 — Section hierarchy) and the validator to determine legal next-heading levels.

**Annotation prefix** — A line matching `^\s*(example|guidance)\s*:\s*(.+)$` (case-insensitive). Recognition is lenient on case and whitespace before the colon; the parser and validator must use identical recognition.

**Degenerate node** — A node whose required text content is empty after parsing. Examples: a Section with an empty heading, a Paragraph whose entire body is annotation lines, a ListItem with no body text. The validator rejects these.

---

## Validation Rules

### Heading rules
- **No level skips.** At each heading, its level must be ≤ (current open section's level + 1). Going shallower is unrestricted (it closes sections off the stack); going deeper may open at most one new level.
- The first heading establishes the root level — starting at h2 (or any level) is allowed, but headings inside the document may not skip from there.
- **No empty headings.** A heading token with no text content is rejected.
- **No headings inside list items.** Any heading encountered while traversing a `ListItem`'s block children is a validation error.
- **No rule on heading depth > 6.** Markdown parses `####### foo` as a paragraph; the resulting tree is well-formed. The author's intent is not checked.

### Annotation rules
- **Lenient prefix recognition.** A line matches if it starts (after optional leading whitespace) with `example` or `guidance`, then optional whitespace, then `:`, then content. Case-insensitive.
- **No empty annotation text.** The portion after the colon must be non-empty after stripping surrounding whitespace.
- **Trailing rule.** Within a `Paragraph` or `ListItem` body, once an annotation line appears, every subsequent line must also be an annotation. A regular text line following an annotation line is a validation error.
- **No annotation-only Paragraph.** A Paragraph whose entire body is annotation lines (leaving no body text) is rejected.
- **No annotation-only ListItem.** Symmetric with the Paragraph rule: a ListItem whose entire body is annotation lines is rejected.
- **Annotations in other blocks are just text.** An `Example:` line inside a `CodeBlock`, `Blockquote`, `Table`, or heading text is not an annotation and not subject to annotation rules. No validation is performed.

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

- **Parser/validator symmetry.** Any rule the validator relaxes (e.g., lenient annotation prefix matching) must be matched by the parser. Otherwise a prompt could pass validation but parse to a tree that drops or misinterprets content, violating the contract.
- **Validation mirrors parsing.** Most validation logic walks the same structure the parser walks. Heading-skip detection uses the same heading stack as Phase 2; annotation rule checks scan the same text the parser scans in Phase 4.
- **No intent checks.** The validator does not catch author mistakes that produce a well-formed tree with surprising semantics — `####### foo` becoming a paragraph, a malformed table falling back to a paragraph, an `Example` typo inside a Blockquote being treated as text. These all pass.
- **Clear failure messages.** Each validation rule, when violated, must produce a message that identifies the offending location and explains what to fix. (The contract demands authors can act on validation failures.)

---

## Open Questions

None — all design decisions were resolved during the brainstorm.
