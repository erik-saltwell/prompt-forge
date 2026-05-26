The prompt is rendered as a JSON tree. Each object has a `node_type` field (`"section"`, `"paragraph"`, `"list"`, `"item"`, `"code"`, `"blockquote"`, `"table"`) and a `children` array for container nodes. Structural properties appear as sibling fields (`level`, `ordered`, `info`). A node's prose lives in the `text` field as raw markdown. Annotation groups appear as `examples` and `guidance` objects on their host, each holding an `annotations` array of annotation objects.

Every addressable node has an `id` field. A small fragment:

```json
{
  "node_type": "document",
  "children": [
    {
      "node_type": "section", "id": "1", "level": 1, "text": "Task",
      "children": [
        {
          "node_type": "paragraph", "id": "1.1", "text": "Read the story carefully.",
          "examples": {"annotations": [{"id": "1.1.e1", "text": "Did X cause Y? -> Yes"}]}
        }
      ]
    }
  ]
}
```

When you reference a node in your JSON output, use the value of its `id` field verbatim — for example `"1.1"` or `"1.1.e1"`. Annotation groups (`examples`, `guidance`) themselves carry no `id` and cannot be cited; only their annotation children can. The document root is not addressable.
