The prompt is rendered as conforming markdown — the same form the target LLM will see — interleaved with HTML comments that carry each addressable node's ID. Every addressable node is preceded by a single-line comment `<!-- id -->` on its own line, immediately above the block (or, for list items, immediately after the bullet marker). Annotation directives appear as `::: examples` / `::: guidance` blocks; each annotation inside carries its own `<!-- id -->` comment.

A small fragment:

```markdown
<!-- 1 -->
# Task

<!-- 1.1 -->
Read the story carefully.

::: examples
- <!-- 1.1.e1 -->
  Did X cause Y? -> Yes
:::
```

The HTML comments are invisible when the markdown is rendered but visible to you. When you reference a node in your JSON output, use the id string from the comment verbatim — for example `"1.1"` or `"1.1.e1"`. Annotation directives themselves carry no id and cannot be cited; only individual annotations can. The document root is not addressable.
