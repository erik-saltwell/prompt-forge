# Prompt Serialization for Critic and Actor LLMs

## Overview

The optimization loop sends the parsed prompt tree to three different LLM roles. Each role consumes the prompt in a different form:

| Role | Form | Why |
|---|---|---|
| **Target** (exercising the prompt) | Conforming markdown via `generate-conforming-prompt` | This is what the prompt *is* — the artifact whose quality we are optimising. No IDs, no overlays. |
| **Critic** (judging output quality) | Conforming markdown + HTML-comment ID overlay | Critic must reason about the prompt in a form recognisable as a prompt; addressability is a side-channel. |
| **Actor** (emitting structural mutations) | XML representation with `id` attributes | Actor's job is structured output keyed on IDs; explicit element tags eliminate addressing ambiguity. |

The two non-target renderings derive from the same in-memory `Document` and assign **identical IDs** to the same nodes. The aggregator pipes critic-emitted IDs through to the actor unchanged.

---

## Key Concepts

**Exercise form** — The canonical conforming markdown produced by `generate-conforming-prompt`. No IDs. This is the artifact the optimizer is trying to improve.

**Critic form** — Exercise-form markdown interleaved with HTML-comment lines carrying each addressable node's ID. The comment appears immediately *before* the block it labels and is invisible when the markdown is rendered, but token-visible to the LLM. Critic instructions explain the convention and ask the critic to cite IDs in its findings.

**Actor form** — An XML tree whose elements correspond 1:1 to parsed nodes, with `id` and structural attributes as XML attributes. Inline content (paragraph text, list-item text, code body) is the raw markdown the target would see — XML wraps the structure, not the inline markup.

**ID stability across forms** — The same in-memory tree renders into both critic form and actor form with identical IDs on the same nodes. Critic outputs IDs; the aggregator forwards them to the actor; the actor's emitted JSON references the same IDs.

---

## Why hybrid

A single shared format would be simpler operationally, but the two roles have asymmetric needs:

- **Critic quality drives every downstream metric.** A bad critique poisons aggregation, which poisons the actor's input, which produces bad actions. Optimising for critique fidelity dominates.
- **Actor's failure modes are protocol-level.** Wrong IDs and malformed JSON skip individual actions but don't degrade the batch's other actions — the skip-and-continue policy contains the blast radius (see `prompt-actions.md`).

Published evidence supports putting the prompt in front of the critic in a form as close to the exercise form as possible. SCULPT (Singh et al., 2024) explicitly tested JSON-tree-form critic input and observed critique-quality degradation — the critic ends up assessing tree well-formedness rather than the prompt's clarity. The same evidence argues *for* JSON-or-XML on the actor side, where the work is structured output.

The hybrid pays a small implementation cost (two renderers) for a meaningful quality lift on the load-bearing role.

---

## Critic Form

### Layout

Every addressable node (every node with a string `id`) is preceded by a single-line HTML comment containing its ID. The comment lives on its own line, separated from the block by no blank line so the visual binding is unambiguous.

Annotations inside `::: examples` / `::: guidance` directive bodies are addressable too; their ID comments appear immediately before the annotation's list item (in list form) or before the directive open (in text form, where the directive *is* the annotation).

### Example

Source tree (parsed from `# foo\n\n## bar\n\n- one\n- two\n`):

```
<!-- 1 -->
# foo

<!-- 1.1 -->
## bar

<!-- 1.1.1 -->
- <!-- 1.1.1.1 -->
  one
- <!-- 1.1.1.2 -->
  two
```

For list items the comment may appear before the bullet marker as shown, or inline after the marker — implementation choice; whichever the LLM scans more reliably. Test both during the eval phase referenced at the bottom of this doc.

For annotations:

```
<!-- 1.1 -->
intro text

::: examples
- <!-- 1.1.e1 -->
  first example
- <!-- 1.1.e2 -->
  second example
:::
```

### Critic system prompt convention

The critic prompt explains the overlay in one sentence: *"Each block is preceded by an HTML comment containing its ID, e.g. `<!-- 1.2.3 -->`. When you cite a node in your findings, use that ID."* The critic is also told the markdown otherwise reads exactly as the target LLM will see it.

The critic LLM's structured output conforms to `MetricResult` — see `critic-metric-interface.md` for the schema (score, assessment, issue signals with cited IDs, preserve list).

### Why HTML comments specifically

- Markdown-it parses them as comments — they have zero rendered effect, so if a critic ever pipes the prompt back through markdown rendering nothing changes.
- They cannot collide with markdown reference-link syntax (`[label]: url`), with paragraph-leading sigils, or with inline code spans.
- The token sequence `<!--` is rare enough in natural prose that LLMs reliably treat it as a structural marker.
- They survive round-trips through diff tools and LLM context windows without re-escaping.

---

## Actor Form

### Layout

Each parsed node becomes an XML element. Element names mirror `node_type`. Structural fields become attributes. Node text (paragraph body, list-item text, heading text, code body) becomes the element's text content as **raw markdown** — inline markup like `**bold**` and `[link](url)` is preserved verbatim so the actor reads the same inline content the target LLM will.

Attribute conventions:

- `id="…"` on every addressable node.
- `level="N"` on `<section>`.
- `ordered="true|false"` on `<list>`.
- `info="…"` on `<code>` (empty attribute omitted).
- Annotation groups (`<examples>` / `<guidance>`) carry no `id` — groups are not addressable.

### Example

The same tree as above:

```xml
<document>
  <section id="1" level="1" heading="foo">
    <section id="1.1" level="2" heading="bar">
      <list id="1.1.1" ordered="false">
        <item id="1.1.1.1">one</item>
        <item id="1.1.1.2">two</item>
      </list>
    </section>
  </section>
</document>
```

With annotations:

```xml
<paragraph id="1.1">intro text
  <examples>
    <annotation id="1.1.e1">first example</annotation>
    <annotation id="1.1.e2">second example</annotation>
  </examples>
</paragraph>
```

### Actor system prompt convention

The actor prompt declares: *"The prompt is rendered as XML. The text inside each element is the prose the target LLM will see, rendered as markdown. Reference nodes by their `id` attribute. Emit actions as JSON per the action vocabulary in `prompt-actions.md`."*

### Why XML

- Anthropic's published prompt-engineering guidance recommends XML tags as the canonical structured-input pattern for Claude. The Claude model family is post-trained to attend to XML structure.
- ID-as-attribute removes any ambiguity between addressing and content.
- Structural attributes (`level`, `ordered`, `info`) surface the post-mutation rules from `prompt-actions.md` in a form the actor can reason about — e.g., wrap/unwrap behaviour on `insert_node` is legible when the destination's element type is visible.
- The actor's output is structured JSON; reading structured input puts it in the right mindset.

---

## ID Generation Symmetry

Both renderings traverse the tree post-`assign_ids` (see `prompt-model.md` — Phase 5). They read the existing `id` attribute on each node; they do not re-mint. This guarantees:

1. The IDs the critic emits are the same strings the actor sees on its input.
2. The aggregator pipes IDs through as opaque strings — no rewriting, no validation beyond presence.
3. The actor's emitted action JSON references IDs that resolve against the snapshot the actor saw, per the frozen-batch-IDs rule.

A test should assert that for every `Document` in the test corpus, the set of IDs in the critic rendering equals the set in the actor rendering.

---

## Behaviors & Rules

- **One source of truth.** Both renderers consume an in-memory `Document` whose IDs have been assigned. Neither renderer re-assigns or mutates IDs.
- **No ID changes between forms.** If a node has `id="1.2.3"` in the critic form, it has `id="1.2.3"` in the actor form.
- **Annotation groups have no ID in either form.** The group is structural sugar; only its `Annotation` children are addressable.
- **The Document root has no ID in either form.** `<document>` carries no `id` attribute; the critic form starts at the first root-level child.
- **Inline markup is preserved verbatim in both forms.** Bold, italic, links, inline code — all pass through as raw markdown inside the element's text or inside the comment-preceded block.
- **Empty containers are still illegal.** Both renderers refuse to serialise an empty `Section` or `List` — this is enforced upstream by `validate-prompt` and `has_empty_container`.

---

## Open Questions

- **ListItem ID-comment placement.** Putting the `<!-- 1.1.1.1 -->` comment before the `-` bullet vs. between the bullet and the item text: both work in CommonMark, neither has obvious comprehension advantages. Decide via the eval below.
- **Token-cost calibration.** XML is roughly 1.4–1.7× markdown by token count for typical prompts. For very large prompts this becomes load-bearing. If a corpus measurement shows the actor's context budget is the binding constraint, consider a tagless variant (single-letter element names, attributes only where required).
- **Multi-model actor portability.** Anthropic-trained Claude attends to XML especially well; GPT-family and Gemini handle it competently but JSON might be marginally stronger for them. If we ever multiplex actor models, add a JSON-tree renderer as a third form — same ID-stability guarantee.
- **Pre-rollout eval.** Before locking the formats in production, build a small benchmark: 5–10 representative prompts, render in (a) pristine markdown + sidecar legend, (b) markdown + `<!-- id -->` comments, (c) XML; have the critic model grade each form's critique against a hand-written reference. The half-day of work calibrates the assumption this design rests on.

---

## References

- SCULPT — *Singh et al., "SCULPT: Systematic Tuning of Long Prompts," 2024.* Source of the path-ID convention and the published evidence that critic input format matters.
- Anthropic — *Prompt Engineering Guide, "Use XML tags."* Source of the XML-for-Claude recommendation.
- `prompt-model.md` — Node types, ID assignment, parsing pipeline.
- `prompt-actions.md` — The action vocabulary the actor emits.
- `critic-metric-interface.md` — The `MetricResult` shape returned by critic LLM calls.
- `prompt-validation.md` — The validation rules every rendered form must respect on round-trip.
