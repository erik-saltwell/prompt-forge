# DeepEval Built-in Metrics — Catalog

Source: https://github.com/confident-ai/deepeval

Metrics relevant to prompt-forge's critic subsystem. All return `[0,1]` score + `reason`; all accept `threshold`, `model`, `include_reason`, `async_mode`, `strict_mode`.

## Single-turn, output-quality

| Metric | Needed test_case fields | What it judges |
|---|---|---|
| `AnswerRelevancyMetric` | input, actual_output | Output addresses the input |
| `FaithfulnessMetric` | input, actual_output, retrieval_context | Output is grounded in context (no hallucination) |
| `HallucinationMetric` | input, actual_output, context | Output contradicts provided context |
| `BiasMetric` | input, actual_output | Bias in output |
| `ToxicityMetric` | input, actual_output | Toxic content |
| `SummarizationMetric` | input, actual_output | Faithful, complete summary |
| `JsonCorrectnessMetric` | input, actual_output | Output matches expected pydantic schema (takes `expected_schema=`) |
| `PromptAlignmentMetric` | input, actual_output | Output follows prompt instructions |

## Retrieval / RAG (need `retrieval_context` and usually `expected_output`)

| Metric | What it judges |
|---|---|
| `ContextualRelevancyMetric` | Retrieved chunks relevant to input |
| `ContextualRecallMetric` | Retrieval covers info needed for expected_output |
| `ContextualPrecisionMetric` | Relevant chunks ranked above irrelevant ones |

Aggregate: `RagasMetric` plus individual `RAGASAnswerRelevancyMetric`, `RAGASFaithfulnessMetric`, `RAGASContextualRecallMetric`, `RAGASContextualPrecisionMetric`.

## Agent / tool-use

| Metric | What it judges |
|---|---|
| `TaskCompletionMetric` | End-to-end task accomplished (full trace) |
| `StepEfficiencyMetric` | Minimal steps used |
| `PlanQualityMetric` | Plan logic & completeness |
| `PlanAdherenceMetric` | Execution matched the plan |
| `ToolCorrectnessMetric` | Right tools selected (needs `expected_tools`) |
| `ArgumentCorrectnessMetric` | Tool arguments correct |

## Multi-turn (take `ConversationalTestCase`)

| Metric | What it judges |
|---|---|
| `TurnRelevancyMetric` | Each assistant turn relevant to user |
| `ConversationCompletenessMetric` | User goals satisfied across turns |
| `KnowledgeRetentionMetric` | Earlier facts not contradicted/forgotten |
| `RoleAdherenceMetric` | Assistant stays in declared `chatbot_role` |
| `ConversationalGEval` | Custom natural-language criteria multi-turn |
| `ConversationalDAGMetric` | DAG-driven multi-turn |

## Custom / generic

- `GEval` — natural-language single-turn judge (criteria or evaluation_steps + evaluation_params).
- `DAGMetric` — deterministic decision tree of nodes; leaves can be other metrics.
- `ExactMatchMetric` — non-LLM string equality (takes `actual_output`, `expected_output`).
- Custom `BaseMetric` subclass — e.g. wrap `deepeval.scorer.Scorer.rouge_score` for non-LLM ROUGE.

## Standalone vs `evaluate()`

Standalone: `metric.measure(test_case); print(metric.score, metric.reason)` — fine for one-offs.
`evaluate(test_cases, metrics=[...])` — batches, parallelism, hyperparameter logging, Confident AI reporting.

## Notes for prompt-forge

- The critic subsystem builds metrics on top of this surface; expect each prompt-forge `Metric` to wrap one or more of the above (often a `GEval` configured for the judgment we need) and adapt its output to the `MetricResult` schema.
- `GEval` + `DAGMetric` are the most natural extension points — built-in domain metrics (Faithfulness, AnswerRelevancy, RAG triad) are useful as embedded judges inside composite/DAG metrics.
- `evaluation_params` controls which `LLMTestCase` fields the judge LLM is shown.
- Use `a_measure` everywhere; the optimizer fans out many cases × many metrics per iteration.
