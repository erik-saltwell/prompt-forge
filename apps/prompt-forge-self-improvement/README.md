# prompt-forge-self-improvement

Uses prompt-forge to optimize prompt-forge's own internal LLM prompts.

## Usage

```bash
# Optimize the feedback actor prompt
uv run prompt-forge-self-improvement \
  --target feedback-actor \
  --output optimized_feedback_actor.md

# With custom model and iteration count
uv run prompt-forge-self-improvement \
  --target feedback-actor \
  --output optimized_feedback_actor.md \
  --model anthropic/claude-opus-4-7 \
  --iterations 12 \
  --concurrency 4
```

## Available Targets

| Target | Description |
|--------|-------------|
| `feedback-actor` | The per-node feedback actor prompt (`_actor/_resources/feedback_actor.md`) |
| `hybrid-judge` | The hybrid metric judge prompt (`_metrics/_resources/hybrid_judge.md`) |

## Adding a New Target

1. Create `src/prompt_forge_self_improvement/targets/<target_name>/` with:
   - `__init__.py`
   - `_scenario_loader.py` — loads YAML scenarios into `EvalCase` objects
   - `metrics.py` — the evaluation metrics for this target
   - `scenarios/` — YAML files, one per test scenario
2. Register it in `_registry.py` by adding an entry to `REGISTRY`.

## Scenario File Format

Each YAML file under `scenarios/` describes one evaluation scenario (one actor call):

```yaml
name: my_scenario
description: "What failure mode this tests."
prompt_markdown: |
  # Section
  Paragraph text.
signals:
  - culprit_node_id: "1.1"
    rationale: "What's wrong"
    target_behavior: "What should happen"
    success_criterion: "Observable predicate for fix"
    input_snippet: "verbatim input evidence"
    output_snippet: "verbatim output evidence"
    seen_in_n_cases: 5
preserve:
  - "Keep the output format instruction"
golden_actions:
  reasoning: "Short rationale."
  actions:
    - action: add_example
      host_id: "1.1"
      text: "Example text"
criteria:
  id_validity:
    - "All IDs in the batch exist in the prompt tree"
  host_type_correctness:
    - "host_id refers to a Paragraph or ListItem"
  issue_traceability:
    - "The action addresses the feedback signal"
  action_type_fitness:
    - "add_example is appropriate for teaching by demonstration"
  coverage:
    - "The high-sightings issue produced at least one action"
  preserve_compliance:
    - "The output format instruction is not removed"
  speculative_edit_absence:
    - "No actions target nodes not in the feedback"
```

All signals in one scenario share the same `culprit_node_id` (matching the production
one-bucket-per-actor-call design). IDs in `golden_actions` and `criteria` must match the
IDs that `parse_from_string(prompt_markdown)` will assign.
