# DeepEval Metrics API — Condensed Reference

Source: https://github.com/confident-ai/deepeval

## Standalone usage

```python
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase

metric = AnswerRelevancyMetric(threshold=0.5)
test_case = LLMTestCase(input="...", actual_output="...", retrieval_context=["..."])
metric.measure(test_case)
print(metric.score, metric.reason)   # also: metric.success, metric.is_successful()
```

Every metric exposes: `score` (float), `reason` (str), `success` (bool), `threshold`, `error`.
Optional ctor flags on most metrics: `threshold`, `model`, `include_reason`, `async_mode`, `strict_mode`, `verbose_mode`.

## Async

`measure()` runs internal calls concurrently but blocks; use `a_measure()` for non-blocking:

```python
await asyncio.gather(m1.a_measure(tc), m2.a_measure(tc))
```

## Custom LLM judge

Pass any custom LLM via `model=`:

```python
metric = AnswerRelevancyMetric(model=azure_openai)   # or string name like "deepseek-r1:1.5b"
```

## Subclassing `BaseMetric` (single-turn)

```python
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

class CustomMetric(BaseMetric):
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
        self.include_reason = True

    def measure(self, test_case: LLMTestCase) -> float:
        try:
            self.score = compute_score(test_case)
            if self.include_reason:
                self.reason = compute_reason(test_case)
            self.success = self.score >= self.threshold
            return self.score
        except Exception as e:
            self.error = str(e); raise

    async def a_measure(self, test_case: LLMTestCase) -> float:
        ...   # same pattern with awaits

    def is_successful(self) -> bool:
        return False if self.error else self.success

    @property
    def __name__(self): return "Custom Metric"
```

Multi-turn variant: inherit `BaseConversationalMetric`, take `ConversationalTestCase`.

## GEval — natural-language custom judge

```python
from deepeval.metrics import GEval
from deepeval.test_case import SingleTurnParams

correctness = GEval(
    name="Correctness",
    criteria="Determine if the actual output is correct vs the expected output.",
    # OR (mutually exclusive with criteria):
    evaluation_steps=["Check facts...", "Penalize omissions...", "Vague language OK"],
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.EXPECTED_OUTPUT],
    strict_mode=True, threshold=0.5,
)
correctness.measure(test_case)
```

`SingleTurnParams`: `INPUT`, `ACTUAL_OUTPUT`, `EXPECTED_OUTPUT`, `RETRIEVAL_CONTEXT`, `CONTEXT`.
Multi-turn equivalent: `ConversationalGEval` (criteria-only).

## DAGMetric — deterministic decision tree

`TaskNode` / `BinaryJudgementNode` / `NonBinaryJudgementNode` / `VerdictNode` compose a `DeepAcyclicGraph`; leaves can embed other metrics (incl. GEval). Use when you need branching deterministic logic atop LLM judgments.

## Composite metric pattern

Subclass `BaseMetric`; in `measure` instantiate sub-metrics, call their `measure`/`a_measure`, then combine scores/reasons (e.g. `min(scores)`, concatenated reasons).

## Test case fields used by metrics

`LLMTestCase(input, actual_output, expected_output?, retrieval_context?, context?, tools_called?, expected_tools?, completion_time?, token_cost?)`.

## Evaluate API

```python
from deepeval import evaluate
evaluate(test_cases=[...], metrics=[...], hyperparameters={...})
# or pytest-style
from deepeval import assert_test
assert_test(test_case, [metric], run_async=True)
```

`run_async=True` makes `assert_test` invoke `a_measure()` concurrently.

## Customizing prompt templates

Override a metric's template class (e.g. `AnswerRelevancyTemplate`) and pass via `evaluation_template=` to inject custom prompt text into the judge.
