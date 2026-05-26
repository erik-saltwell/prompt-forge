The feedback block lists issues as humanized markdown. It starts with a top-level heading naming the affected node, then one `## Issue N` subsection per signal. Each issue has labeled fields:

```
# Issues affecting node `1.1`

## Issue 1
**What's wrong:** the paragraph is vague about which causal convention to apply
**Target behavior:** be explicit about majority-human-judgment as the rubric
**Success criterion:** the prompt names the rubric and applies it consistently
**Suggested change:** (optional) add a one-sentence rule
**Evidence — input:** "Did Billy cause the car to start?"
**Evidence — output:** "Yes" (ground truth: No)
```

A `(seen in N cases)` suffix on the heading marks recurring issues — weight your effort by prevalence. Multiple `## Issue N` subsections may all cite the same node; treat them as independent complaints.
