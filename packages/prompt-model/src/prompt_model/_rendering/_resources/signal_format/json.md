The feedback block is a JSON object with `culprit_node_id` (the affected node) and a `signals` array. Each signal has `rationale`, `target_behavior`, `success_criterion`, optional `suggested_prompt_change`, verbatim `input_snippet` / `output_snippet` evidence, and a `seen_in_n_cases` count.

```json
{
  "culprit_node_id": "1.1",
  "signals": [
    {
      "rationale": "the paragraph is vague about which causal convention to apply",
      "target_behavior": "be explicit about majority-human-judgment as the rubric",
      "success_criterion": "the prompt names the rubric and applies it consistently",
      "suggested_prompt_change": null,
      "input_snippet": "Did Billy cause the car to start?",
      "output_snippet": "Yes",
      "seen_in_n_cases": 7
    }
  ]
}
```

Multiple signals may cite the same node; treat them as independent complaints. Weight your effort by `seen_in_n_cases`.
