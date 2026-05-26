The feedback block is an XML `<bucket>` element with a `culprit_node_id` attribute naming the affected node, and one `<signal>` child per issue. Each signal carries `<rationale>`, `<target_behavior>`, `<success_criterion>`, optional `<suggested_prompt_change>`, and verbatim `<input_snippet>` / `<output_snippet>` evidence. A `seen_in_n_cases` attribute on `<signal>` marks recurrence.

```xml
<bucket culprit_node_id="1.1">
  <signal seen_in_n_cases="7">
    <rationale>the paragraph is vague about which causal convention to apply</rationale>
    <target_behavior>be explicit about majority-human-judgment as the rubric</target_behavior>
    <success_criterion>the prompt names the rubric and applies it consistently</success_criterion>
    <input_snippet>Did Billy cause the car to start?</input_snippet>
    <output_snippet>Yes</output_snippet>
  </signal>
</bucket>
```

Multiple signals may cite the same node; treat them as independent complaints. Weight your effort by `seen_in_n_cases`.
