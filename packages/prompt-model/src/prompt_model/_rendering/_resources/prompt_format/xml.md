The prompt is rendered as an XML tree. Each element's tag name gives the node type (`<section>`, `<paragraph>`, `<list>`, `<item>`, `<code>`, `<blockquote>`, `<table>`); structural properties appear as attributes (`level`, `ordered`, `info`). A node's text content is the raw markdown prose. Annotation groups appear as `<examples>` and `<guidance>` children of their host, with individual `<annotation>` children inside.

Every addressable node carries an `id` attribute. A small fragment:

```xml
<document>
  <section id="1" level="1" heading="Task">
    <paragraph id="1.1">Read the story carefully.
      <examples>
        <annotation id="1.1.e1">Did X cause Y? -&gt; Yes</annotation>
      </examples>
    </paragraph>
  </section>
</document>
```

When you reference a node in your JSON output, use the value of its `id` attribute verbatim — for example `"1.1"` or `"1.1.e1"`. Annotation groups (`<examples>`, `<guidance>`) themselves carry no `id` and cannot be cited; only their `<annotation>` children can. The `<document>` root is not addressable.
