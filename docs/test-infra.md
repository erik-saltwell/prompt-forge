# Test Infrastructure

## Overview

The test infrastructure for the prompt-model package supports unit testing the three core components — `validate-prompt`, `parse-prompt`/`generate-conforming-prompt`, and the action executor — with a fixture-driven, auto-discovered pytest harness. Tests are expressed as files on disk wherever possible: dropping a markdown file into the right directory creates a new test case without writing Python. A small set of comparison primitives (structural tree equality, markdown round-trip, and a compact structure shorthand) covers every assertion mode used across the three components.

---

## Key Concepts

**Fixture** — A file (or small group of related files) on disk that defines one test case. Pytest auto-discovery walks the fixture directories and parametrizes test functions over what it finds.

**Structure shorthand** — A compact one-line text format describing a tree's *shape* without its content. Used in tests where the assertion is "the parser produced the right structure" rather than "the parser produced exact text X."

**Structural equality** — Tree equality that ignores `id` fields. Two trees are structurally equal if they have identical node types, identical structure, identical text, and identical attached annotations. This is the only equality mode used by the test harness.

**ID uniqueness invariant** — No tree may contain duplicate IDs across nodes and annotations. Enforced as a Pydantic model validator at construction time, so it is impossible to construct an invalid tree (in production or in tests) by accident.

**Sidecar file** — A companion file paired with a fixture by filename prefix, carrying assertion metadata. For example, `bad_heading_skip.md` is paired with `bad_heading_skip.expected.json` listing the expected validation error codes and line numbers.

**Test mode** — For tests with multiple natural assertion shapes (especially action tests), the mode is encoded by which subdirectory the fixture lives in (`exact/`, `shorthand/`). One parametrized test function per mode walks its directory.

---

## Structure Shorthand Grammar

The shorthand describes a tree as a flat sequence of tokens.

| Token | Meaning |
|---|---|
| `h1`–`h6` | Section at heading level N |
| `p` | Paragraph |
| `cb` | CodeBlock |
| `bq` | Blockquote |
| `t` | Table |
| `ul<N>` | Unordered list item at nesting depth N |
| `ol<N>` | Ordered list item at nesting depth N |
| `e` | Append one `Annotation` to the immediately preceding `p`/`ul<N>`/`ol<N>`'s `ExamplesGroup` (creating the group on first occurrence) |
| `g` | Append one `Annotation` to the immediately preceding `p`/`ul<N>`/`ol<N>`'s `GuidanceGroup` (creating the group on first occurrence) |

**Implicit rules:**
- Lists are inferred. Consecutive same-depth, same-orderedness items form one list. Any non-list-item token between them starts a new list.
- A `ul1 ol1` sequence at the same depth is two sibling lists (the parser does not merge them).
- Section nesting follows heading levels: a heading at level N closes any open sections at level ≥ N.
- Annotation tokens append, they don't overwrite. `p e e e` means one paragraph with an `ExamplesGroup` of three annotations. `p e e g g` means an `ExamplesGroup` of two and a `GuidanceGroup` of two.
- `e` and `g` may interleave freely — each appends to its kind's group on the current host. `p e g e` means an `ExamplesGroup` of two and a `GuidanceGroup` of one, regardless of source ordering.
- The document root is implicit; the token stream *is* the body.

**Out of scope for v1:** code block info strings, list-item block children, document root markers. Tests that need to assert these use exact-file comparison instead.

The harness implements only one direction: `tree_to_shorthand(tree) → str`. Tests assert string equality. There is no shorthand-to-tree parser.

---

## Test Patterns by Component

### Validator
- **Pass tests** — every `.md` file under `fixtures/validate/pass/` must validate successfully.
- **Fail tests** — every `.md` file under `fixtures/validate/fail/` must fail validation with the specific error codes and line numbers listed in its sidecar `.expected.json`.

### Parser
- **Shorthand mode** — input `.md` is paired with an expected shorthand string. The harness parses the input, generates shorthand from the result, and compares strings.
- **Exact mode** — input `.md` is paired with an expected `.md`. Both are parsed; the resulting trees are compared with structural equality.

### Generator
- **Round-trip** — parse a file, generate from the tree, assert the output equals the input file. Validates that conforming markdown round-trips identically.
- **Normalized** — parse a file, generate from the tree, assert the output equals a paired expected `.md`. Used for non-conforming inputs that get normalized.
- **Parse-generate-reparse** — parse, generate, parse again, assert the two trees are structurally equal. Validates that generation produces parseable markdown.

### Action executor
- **Exact mode** — `input.md` + `actions.json` + `expected.md`. Parse input, apply actions, generate, compare to expected markdown.
- **Shorthand mode** — `input.md` + `actions.json` + `expected.shorthand`. Parse input, apply actions, generate shorthand from result, compare to expected.

---

## Fixture Layout

```
tests/
  fixtures/
    validate/
      pass/                          # *.md
      fail/                          # *.md + *.expected.json
    parse/
      shorthand/                     # *.md + *.expected.shorthand
      exact/                         # *.md + *.expected.md
    generate/
      roundtrip/                     # *.md
      normalize/                     # *.md + *.expected.md
      reparse/                       # *.md
    actions/
      exact/                         # *.input.md + *.actions.json + *.expected.md
      shorthand/                     # *.input.md + *.actions.json + *.expected.shorthand
```

---

## Test Wiring

Auto-discovery is the default; manual functions are an escape hatch for fixtures that need custom setup or named-regression visibility.

A small number of parametrized test functions — roughly one per (component, mode) pair — walk the fixture directories and produce one parametrized test case per file. The pytest test ID surfaces the fixture path, so a failure points directly at the file.

```python
@pytest.mark.parametrize("md", discover("fixtures/validate/pass"))
def test_validate_pass(md): ...

@pytest.mark.parametrize("md,expected", discover_paired("fixtures/validate/fail", ".expected.json"))
def test_validate_fail(md, expected): ...
```

Manual tests live alongside the parametrized ones when a fixture's assertion is unusual or when naming a specific regression is helpful.

---

## Behaviors & Rules

- **Structural equality only.** The harness has one tree comparator, and it ignores IDs. ID assignment correctness is tested separately by tests that read `id` fields directly and assert specific values.
- **ID uniqueness is a Pydantic invariant.** No test (or production code) ever produces a tree with duplicate IDs — the model rejects it at construction. No separate `assert_unique_ids` helper exists; it doesn't need to.
- **Fail-case fixtures assert specific errors.** A fixture in `validate/fail/` cannot pass for the wrong reason. The sidecar `.expected.json` lists every expected error code and its line number; mismatches fail the test.
- **Auto-discovery scales the corpus.** Adding a test case is almost always "drop a file in the right directory." Editing Python is reserved for genuinely novel test shapes.
- **Mode-per-directory for multi-file fixtures.** Action tests live under `actions/exact/` or `actions/shorthand/`. The author chooses the assertion mode by choosing the directory; the harness has one test function per mode.
- **Shorthand is for shape, not content.** Tests that need to assert text, code block info strings, or list-item block children use exact-file comparison; the shorthand intentionally cannot express these.

---

## Open Questions

None — all design decisions were resolved during the brainstorm.
