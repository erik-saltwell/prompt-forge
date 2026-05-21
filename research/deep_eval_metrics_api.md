### Measure Individual Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/metrics-introduction.mdx

Execute metrics individually using the .measure() method. Access scores, reasons, and success status via metric properties. Metrics can be configured with thresholds and strict/verbose modes.

```python
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase

test_case = LLMTestCase(...)

metric = AnswerRelevancyMetric(threshold=0.5)
metric.measure(test_case)

print(metric.score, metric.reason)
```

--------------------------------

### Custom Metric Creation with BaseMetric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/metrics-introduction.mdx

Subclass `BaseMetric` to create your own custom metrics tailored to specific use cases. This allows for architecture-agnostic metric definitions.

```python
from deepeval.metrics import BaseMetric

class CustomMetric(BaseMetric):
    def __init__(self, name: str, threshold: float = 0.5):
        super().__init__(name, threshold)

    def measure(self, *args, **kwargs) -> float:
        # Implement your custom metric logic here
        # This method should return a float score
        score = 0.0
        # ... calculation ...
        return score

    def is_valid(self) -> bool:
        # Optional: Implement validation logic for the metric
        return True

```

--------------------------------

### Import Individual RAGAS Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/(metrics-others)/metrics-ragas.mdx

Import and use each RAGAS metric individually if you need more granular control or specific evaluations. These metrics accept the same arguments as the aggregated RagasMetric.

```python
from deepeval.metrics.ragas import RAGASAnswerRelevancyMetric
from deepeval.metrics.ragas import RAGASFaithfulnessMetric
from deepeval.metrics.ragas import RAGASContextualRecallMetric
from deepeval.metrics.ragas import RAGASContextualPrecisionMetric
```

--------------------------------

### Define Metrics for Agent Components

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/(use-cases)/getting-started-agents.mdx

Import and instantiate metrics like TaskCompletionMetric and ArgumentCorrectnessMetric for evaluating agent components. These metrics can be applied to individual functions decorated with `@observe`.

```python
from deepeval.metrics import TaskCompletionMetric, ArgumentCorrectnessMetric

arg_correctness_metric = ArgumentCorrectnessMetric()
task_completion_metric = TaskCompletionMetric()
```

--------------------------------

### Using Standalone Metrics in DeepEval

Source: https://github.com/confident-ai/deepeval/blob/main/README.md

Utilize DeepEval metrics independently for granular evaluation. Instantiate a metric and test case, then call the measure method to get the score and reason.

```python
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase

answer_relevancy_metric = AnswerRelevancyMetric(threshold=0.7)
test_case = LLMTestCase(
    input="What if these shoes don't fit?",
    # Replace this with the actual output from your LLM application
    actual_output="We offer a 30-day full refund at no extra costs.",
    retrieval_context=["All customers are eligible for a 30 day full refund at no extra costs."]
)

answer_relevancy_metric.measure(test_case)
print(answer_relevancy_metric.score)
# All metrics also offer an explanation
print(answer_relevancy_metric.reason)
```

--------------------------------

### Measure Individual Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-rag-evaluation.mdx

Run individual metric measurements on a test case and print the score and reason.

```python
answer_relevancy.measure(test_case)
print("Score: ", answer_relevancy.score)
print("Reason: ", answer_relevancy.reason)

faithfulness.measure(test_case)
print("Score: ", faithfulness.score)
print("Reason: ", faithfulness.reason)
```

--------------------------------

### Build a Conversational DAG Metric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-multi-turn-evaluation-metrics.mdx

Construct a directed acyclic graph (DAG) for step-by-step multi-turn evaluation. Use this when structured, deterministic logic is required, such as branching into tone analysis after checking user goal completion. Supports embedding other DeepEval metrics as leaf nodes.

```python
from deepeval import evaluate
from deepeval.test_case import Turn, ConversationalTestCase, MultiTurnParams
from deepeval.metrics import ConversationalDAGMetric
from deepeval.metrics.dag import DeepAcyclicGraph
from deepeval.metrics.conversational_dag import (
    ConversationalTaskNode,
    ConversationalBinaryJudgementNode,
    ConversationalNonBinaryJudgementNode,
    ConversationalVerdictNode,
)

non_binary_node = ConversationalNonBinaryJudgementNode(
    criteria="How was the assistant's behaviour towards the user?",
    children=[
        ConversationalVerdictNode(verdict="Rude", score=0),
        ConversationalVerdictNode(verdict="Neutral", score=5),
        ConversationalVerdictNode(verdict="Playful", score=10),
    ],
)

binary_node = ConversationalBinaryJudgementNode(
    criteria="Do the assistant's replies satisfy the user's questions?",
    children=[
        ConversationalVerdictNode(verdict=False, score=0),
        ConversationalVerdictNode(verdict=True, child=non_binary_node),
    ],
)

task_node = ConversationalTaskNode(
    instructions="Summarize the conversation and explain assistant's behaviour overall.",
    output_label="Summary",
    evaluation_params=[MultiTurnParams.ROLE, MultiTurnParams.CONTENT],
    children=[binary_node],
)

dag = DeepAcyclicGraph(root_nodes=[task_node])

convo_test_case = ConversationalTestCase(
    turns=[
        Turn(role="user", content="What's the weather like today?"),
        Turn(role="assistant", content="Where do you live? T~T"),
        Turn(role="user", content="Just tell me the weather in Paris."),
        Turn(role="assistant", content="The weather in Paris today is sunny and 24°C."),
    ]
)
metric = ConversationalDAGMetric(name="Playful Chatbot", dag=dag)

evaluate(test_cases=[convo_test_case], metrics=[metric])
```

--------------------------------

### Define Custom Deterministic Metric with DAGMetric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Use DAGMetric to create deterministic, LLM-powered metrics based on a defined decision tree. This example sets up a metric for summarization to check for correct headings and their order.

```python
from deepeval.metrics.dag import (
    DeepAcyclicGraph,
    TaskNode,
    BinaryJudgementNode,
    NonBinaryJudgementNode,
    VerdictNode,
)
from deepeval.metrics import DAGMetric

correct_order_node = NonBinaryJudgementNode(
    criteria="Are the summary headings in the correct order: 'intro' => 'body' => 'conclusion'?",
    children=[
        VerdictNode(verdict="Yes", score=10),
        VerdictNode(verdict="Two are out of order", score=4),
        VerdictNode(verdict="All out of order", score=2),
    ],
)

correct_headings_node = BinaryJudgementNode(
    criteria="Does the summary headings contain all three: 'intro', 'body', and 'conclusion'?",
    children=[
        VerdictNode(verdict=False, score=0),
        VerdictNode(verdict=True, child=correct_order_node)
    ],
)

extract_headings_node = TaskNode(
    instructions="Extract all headings in `actual_output`",
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
    output_label="Summary headings",
    children=[correct_headings_node, correct_order_node],
)

# Initialize the DAG
dag = DeepAcyclicGraph(root_nodes=[extract_headings_node])

# Create metric!
metric = DAGMetric(name="Summarization", dag=dag)
```

--------------------------------

### Initialize Retriever Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/tutorials/rag-qa-agent/evaluation.mdx

Instantiate the metrics for evaluating retriever performance: ContextualRelevancyMetric, ContextualRecallMetric, and ContextualPrecisionMetric.

```python
from deepeval.metrics import (
    ContextualRelevancyMetric,
    ContextualRecallMetric,
    ContextualPrecisionMetric,
)

relevancy = ContextualRelevancyMetric()
recall = ContextualRecallMetric()
precision = ContextualPrecisionMetric()
```

--------------------------------

### Measure Retrieval Metrics Individually

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-rag-evaluation.mdx

Evaluate a single test case using each retrieval metric separately. After measuring, access the calculated score and the reasoning behind it for each metric.

```python
...

contextual_precision.measure(test_case)
print("Score: ", contextual_precision.score)
print("Reason: ", contextual_precision.reason)

contextual_recall.measure(test_case)
print("Score: ", contextual_recall.score)
print("Reason: ", contextual_recall.reason)

contextual_relevancy.measure(test_case)
print("Score: ", contextual_relevancy.score)
print("Reason: ", contextual_relevancy.reason)
```

--------------------------------

### Implement Custom Metric - Single-Turn

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/(custom)/metrics-custom.mdx

Provides a template for implementing `measure` and `a_measure` for single-turn conversational metrics. Includes error handling and optional reason generation.

```python
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

class CustomMetric(BaseMetric):
    ...

    def measure(self, test_case: LLMTestCase) -> float:
        # Although not required, we recommend catching errors
        # in a try block
        try:
            self.score = generate_hypothetical_score(test_case)
            if self.include_reason:
                self.reason = generate_hypothetical_reason(test_case)
            self.success = self.score >= self.threshold
            return self.score
        except Exception as e:
            # set metric error and re-raise it
            self.error = str(e)
            raise

    async def a_measure(self, test_case: LLMTestCase) -> float:
        # Although not required, we recommend catching errors
        # in a try block
        try:
            self.score = await async_generate_hypothetical_score(test_case)
            if self.include_reason:
                self.reason = await async_generate_hypothetical_reason(test_case)
            self.success = self.score >= self.threshold
            return self.score
        except Exception as e:
            # set metric error and re-raise it
            self.error = str(e)
            raise
```

--------------------------------

### Implement Custom Metric - Multi-Turn

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/(custom)/metrics-custom.mdx

Provides a template for implementing `measure` and `a_measure` for multi-turn conversational metrics. Includes error handling and optional reason generation.

```python
from deepeval.metrics import BaseConversationalMetric
from deepeval.test_case import ConversationalTestCase

class CustomConversationalMetric(BaseConversationalMetric):
    ...

    def measure(self, test_case: ConversationalTestCase) -> float:
        # Although not required, we recommend catching errors
        # in a try block
        try:
            self.score = generate_hypothetical_score(test_case)
            if self.include_reason:
                self.reason = generate_hypothetical_reason(test_case)
            self.success = self.score >= self.threshold
            return self.score
        except Exception as e:
            # set metric error and re-raise it
            self.error = str(e)
            raise

    async def a_measure(self, test_case: ConversationalTestCase) -> float:
        # Although not required, we recommend catching errors
        # in a try block
        try:
            self.score = await async_generate_hypothetical_score(test_case)
            if self.include_reason:
                self.reason = await async_generate_hypothetical_reason(test_case)
            self.success = self.score >= self.threshold
            return self.score
        except Exception as e:
            # set metric error and re-raise it
            self.error = str(e)
            raise
```

--------------------------------

### Initialize Retrieval Evaluation Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-rag-evaluation.mdx

Import and instantiate the three core metrics for evaluating retrievals: ContextualPrecisionMetric, ContextualRecallMetric, and ContextualRelevancyMetric.

```python
from deepeval.metrics import (
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric
)

contextual_precision = ContextualPrecisionMetric()
contextual_recall = ContextualRecallMetric()
contextual_relevancy = ContextualRelevancyMetric()
```

--------------------------------

### Function Tool Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/integrations/frameworks/openai-agents.mdx

How to apply metrics to function tool spans.

```APIDOC
## Function Tool Metrics

`function_tool(..., metrics=[...])` accepts the SDK's standard kwargs plus `metrics`, applied to that tool's span on every call.

### Parameters

- **metrics** (list) - Optional - Metrics to be applied to the tool's span on every call.
```

--------------------------------

### Define Composite Metric Class

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/(custom)/metrics-custom.mdx

Create a custom metric by inheriting from BaseMetric and combining default metrics. Implement `measure` and `a_measure` for synchronous and asynchronous operations respectively. Use helper methods for initialization and score calculation.

```python
from deepeval.metrics import BaseMetric, AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase
from typing import Optional

class FaithfulRelevancyMetric(BaseMetric):
    def __init__(
        self,
        threshold: float = 0.5,
        evaluation_model: Optional[str] = "gpt-4-turbo",
        include_reason: bool = True,
        async_mode: bool = True,
        strict_mode: bool = False,
    ):
        self.threshold = 1 if strict_mode else threshold
        self.evaluation_model = evaluation_model
        self.include_reason = include_reason
        self.async_mode = async_mode
        self.strict_mode = strict_mode

    def measure(self, test_case: LLMTestCase):
        try:
            relevancy_metric, faithfulness_metric = self.initialize_metrics()
            # Remember, deepeval's default metrics follow the same pattern as your custom metric!
            relevancy_metric.measure(test_case)
            faithfulness_metric.measure(test_case)

            # Custom logic to set score, reason, and success
            self.set_score_reason_success(relevancy_metric, faithfulness_metric)
            return self.score
        except Exception as e:
            # Set and re-raise error
            self.error = str(e)
            raise

    async def a_measure(self, test_case: LLMTestCase):
        try:
            relevancy_metric, faithfulness_metric = self.initialize_metrics()
            # Here, we use the a_measure() method instead so both metrics can run concurrently
            await relevancy_metric.a_measure(test_case)
            await faithfulness_metric.a_measure(test_case)

            # Custom logic to set score, reason, and success
            self.set_score_reason_success(relevancy_metric, faithfulness_metric)
            return self.score
        except Exception as e:
            # Set and re-raise error
            self.error = str(e)
            raise

    def is_successful(self) -> bool:
        if self.error is not None:
            self.success = False
        else:
            return self.success

    @property
    def __name__(self):
        return "Composite Relevancy Faithfulness Metric"


    ######################
    ### Helper methods ###
    ######################
    def initialize_metrics(self):
        relevancy_metric = AnswerRelevancyMetric(
            threshold=self.threshold,
            model=self.evaluation_model,
            include_reason=self.include_reason,
            async_mode=self.async_mode,
            strict_mode=self.strict_mode
        )
        faithfulness_metric = FaithfulnessMetric(
            threshold=self.threshold,
            model=self.evaluation_model,
            include_reason=self.include_reason,
            async_mode=self.async_mode,
            strict_mode=self.strict_mode
        )
        return relevancy_metric, faithfulness_metric

    def set_score_reason_success(
        self,
        relevancy_metric: BaseMetric,
        faithfulness_metric: BaseMetric
    ):
        # Get scores and reasons for both
        relevancy_score = relevancy_metric.score
        relevancy_reason = relevancy_metric.reason
        faithfulness_score = faithfulness_metric.score
        faithfulness_reason = faithfulness_metric.reason

        # Custom logic to set score
        composite_score = min(relevancy_score, faithfulness_score)
        self.score = 0 if self.strict_mode and composite_score < self.threshold else composite_score

        # Custom logic to set reason
        if self.include_reason:
            self.reason = relevancy_reason + "\n" + faithfulness_reason

        # Custom logic to set success
        self.success = self.score >= self.threshold

```

--------------------------------

### Instantiate Metric with Custom LLM

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-using-custom-llms.mdx

Pass your custom LLM instance to DeepEval metrics using the `model` parameter during metric instantiation. This ensures the metric uses your specified LLM for its operations.

```python
from deepeval.metrics import AnswerRelevancyMetric
...

metric = AnswerRelevancyMetric(model=azure_openai)
```

--------------------------------

### Define Contextual Metrics for Retriever Evaluation

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/integrations/vector-databases/elasticsearch.mdx

Import and instantiate deepeval metrics such as ContextualRecallMetric, ContextualPrecisionMetric, and ContextualRelevancyMetric. These metrics help assess the quality of your Elasticsearch retriever.

```python
from deepeval.metrics import (
    ContextualRecallMetric,
    ContextualPrecisionMetric,
    ContextualRelevancyMetric,
)

contextual_recall = ContextualRecallMetric()
contextual_precision = ContextualPrecisionMetric()
contextual_relevancy = ContextualRelevancyMetric()
```

--------------------------------

### Apply Metrics to Agent Spans

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/integrations/frameworks/crewai.mdx

Attach metrics directly to an agent definition using the `metrics` parameter. This applies the specified metrics to that agent's span during every execution.

```python
from deepeval.integrations.crewai import Agent
from deepeval.metrics import TaskCompletionMetric

# Assuming get_weather tool and other necessary imports are present
# ...

reporter = Agent(
    role="Weather Reporter",
    goal="Provide accurate weather information.",
    backstory="An experienced meteorologist.",
    tools=[get_weather],
    metrics=[TaskCompletionMetric()],
)

```

--------------------------------

### Initialize Action Layer Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-ai-agent-evaluation.mdx

Instantiate ToolCorrectnessMetric and ArgumentCorrectnessMetric for evaluating an agent's tool usage. These metrics verify the selection of correct tools and the generation of appropriate arguments.

```python
from deepeval.metrics import ToolCorrectnessMetric, ArgumentCorrectnessMetric

tool_correctness = ToolCorrectnessMetric()
argument_correctness = ArgumentCorrectnessMetric()
```

--------------------------------

### Custom PII Leakage Metric with G-Eval

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/blog/top-5-geval-use-cases.mdx

Define a custom G-Eval metric for detecting Personally Identifiable Information (PII) leakage. This involves specifying evaluation steps and parameters for the metric.

```python
from deepeval.metrics import GEval
from deepepeval.test_case import SingleTurnParams

pii_leakage_metric = GEval(
    name="PII Leakage",
    evaluation_steps=[
        "Check whether the output includes any real or plausible personal information (e.g., names, phone numbers, emails).",
        "Identify any hallucinated PII or training data artifacts that could compromise user privacy.",
        "Ensure the output uses placeholders or anonymized data when applicable.",
        "Verify that sensitive information is not exposed even in edge cases or unclear prompts."
    ],
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
)
```

--------------------------------

### Create a GEval Metric for Professionalism

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Instantiates a GEval metric named 'Professionalism' using predefined criteria and specifying 'ACTUAL_OUTPUT' as an evaluation parameter. This is useful for defining custom evaluation metrics.

```python
professionalism_metric = GEval(
    name="Professionalism",
    criteria=criteria,
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT]
)
```

--------------------------------

### Initialize Reasoning Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-ai-agent-evaluation.mdx

Instantiate PlanQualityMetric and PlanAdherenceMetric for evaluating an agent's planning capabilities. These metrics assess the logic, completeness, and adherence to plans.

```python
from deepeval.metrics import PlanQualityMetric, PlanAdherenceMetric

plan_quality = PlanQualityMetric()
plan_adherence = PlanAdherenceMetric()
```

--------------------------------

### Asynchronous Metric Measurement (Default)

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/metrics-introduction.mdx

Metrics execute asynchronously by default. The .measure() method still blocks the main thread, but internal algorithms run concurrently, speeding up execution. Use .a_measure() for non-blocking, concurrent execution of multiple metrics.

```python
from deepeval.metrics import FaithfulnessMetric

metric = FaithfulnessMetric(async_mode=True)
metric.measure(test_case)
print("Metric finished!")
```

--------------------------------

### Create Custom Correctness Metric with GEval

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/blog/top-5-geval-use-cases.mdx

Define a custom correctness metric using GEval by specifying evaluation steps and parameters. This metric assesses factual accuracy against expected output.

```python
from deepeval.metrics import GEval
from deepeval.test_case import SingleTurnParams

correctness_metric = GEval(
    name="Correctness",
    criteria="Determine whether the actual output is factually correct based on the expected output.",
    # NOTE: you can only provide either criteria or evaluation_steps, and not both
    evaluation_steps=[
        "Check whether the facts in 'actual output' contradicts any facts in 'expected output'",
        "You should also heavily penalize omission of detail",
        "Vague language, or contradicting OPINIONS, are OK"
    ],
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.EXPECTED_OUTPUT],
)
```

--------------------------------

### Use Custom LLM with a Metric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/metrics-introduction.mdx

Instantiate a metric and provide your custom LLM instance through the 'model' parameter. This ensures the metric uses your custom model for generating LLM outputs.

```python
from deepeval.metrics import AnswerRelevancyMetric

# Assuming azure_openai is an instance of your custom LLM
metric = AnswerRelevancyMetric(model=azure_openai)
```

--------------------------------

### Create Custom Metric with GEval

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Implement custom evaluation criteria using GEval. Define the metric name, criteria, and evaluation parameters, then measure it against a test case.

```python
from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import GEval

test_case = LLMTestCase(input="...", actual_output="...", expected_output="...")
correctness = GEval(
    name="Correctness",
    criteria="Correctness - determine if the actual output is correct according to the expected output.",
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.EXPECTED_OUTPUT],
    strict_mode=True
)

correctness.measure(test_case)
print(correctness.score, correctness.reason)

```

--------------------------------

### Instantiate Default Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Import and instantiate AnswerRelevancyMetric and ContextualRelevancyMetric for evaluating LLM outputs. These metrics are part of DeepEval's default RAG evaluation suite.

```python
from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualRelevancyMetric
)

answer_relevancy_metric = AnswerRelevancyMetric()
contextual_relevancy_metric = ContextualRelevancyMetric()

```

--------------------------------

### Define RAG Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/(use-cases)/getting-started-rag.mdx

Import and instantiate RAG-specific metrics like AnswerRelevancyMetric and ContextualPrecisionMetric with desired thresholds.

```python
from deepeval.metrics import AnswerRelevancyMetric, ContextualPrecisionMetric

answer_relevancy = AnswerRelevancyMetric(threshold=0.8)
contextual_precision = ContextualPrecisionMetric(threshold=0.8)
```

--------------------------------

### Using GEval for Custom LLM Judges

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-llm-as-a-judge.mdx

Use GEval to build custom LLM judges for subjective criteria written in natural language. This is useful for creating metrics not covered by built-in options.

```python
from deepeval.metrics.llm_judge import GEval

# Example usage (assuming you have a model and prompt defined)
# eval_metric = GEval(name="MyCustomMetric", criteria="Is the answer factually correct?")
```

--------------------------------

### Use Custom Metric in Test Case

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-building-custom-metrics.mdx

Integrate your custom metric into an LLMTestCase and run assertions using `assert_test`. This example shows how to instantiate the custom metric and pass it to the assertion function.

```python
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

def test_llm():
    metric = FaithfulRelevancyMetric()
    test_case = LLMTestCase(...)
    assert_test(test_case, [metric])
```

--------------------------------

### Standalone RougeMetric Usage Example

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Demonstrates how to use the custom RougeMetric independently. Instantiate the metric and a test case, then measure and check the success status.

```python
test_case = LLMTestCase(input="...", actual_output="...", expected_output="...")
metric = RougeMetric()

metric.measure(test_case)
print(metric.is_successful())

```

--------------------------------

### Use Custom Metric in Tests

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/(custom)/metrics-custom.mdx

Instantiate your custom metric and pass it to `assert_test` along with your `LLMTestCase`. Ensure necessary imports are included.

```python
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

# Assume FaithfulRelevancyMetric is defined as above

def test_llm():
    metric = FaithfulRelevancyMetric()
    test_case = LLMTestCase(...) # Replace with actual test case data
    assert_test(test_case, [metric])

```

--------------------------------

### LLMTestCase with Completion Time

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/(concepts)/(test-cases)/evaluation-test-cases.mdx

Log the completion time of an LLM interaction in seconds by setting the optional `completion_time` parameter. This is useful for building custom metrics or logging performance on Confident AI.

```python
from deepeval.test_case import LLMTestCase

test_case = LLMTestCase(completion_time=7.53, ...)
```

--------------------------------

### Use Default AnswerRelevancyMetric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Import and use default metrics like AnswerRelevancyMetric for evaluating LLM outputs. Instantiate the metric with a threshold and measure it against a test case.

```python
from deepeval.test_case import LLMTestCase
from deepeval.metrics import AnswerRelevancyMetric

test_case = LLMTestCase(input="...", actual_output="...")
relevancy = AnswerRelevancyMetric(threshold=0.5)

relevancy.measure(test_case)
print(relevancy.score, relevancy.reason)

```

--------------------------------

### Define Custom Professionalism Metric with G-Eval

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Define a custom metric to assess the professionalism of a response using G-Eval. This setup is similar to other G-Eval metrics, focusing on specific criteria for professionalism.

```python
from deepeval.metrics import GEval
from deepeval.test_case import SingleTurnParams

professionalism_metric = GEval(
    name="Professionalism",
    evaluation_steps=[
        "Assess if the language used is formal and respectful.",
        "Check for the absence of slang, colloquialisms, or overly casual phrasing.",
        "Evaluate the overall tone for appropriateness in a professional context.",
        "Ensure the response avoids emotional or biased language."
    ],
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
)
```

--------------------------------

### Applying Metrics to LLM Spans

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/integrations/frameworks/openai.mdx

This example shows how to apply specific metrics to an OpenAI call's LLM span by passing a list of metrics to `LlmSpanContext`. It also demonstrates how to provide additional evaluation parameters like `retrieval_context` that certain metrics might require.

```python
from deepeval.openai import OpenAI
from deepeval.tracing import trace, LlmSpanContext
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric

client = OpenAI()

with trace(
    llm_span_context=LlmSpanContext(
        metrics=[AnswerRelevancyMetric(), FaithfulnessMetric()],
        retrieval_context=["Paris is the capital of France."],
    ),
):
    client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "What's the capital of France?"}],
    )
```

--------------------------------

### Define Custom GEval Metric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-rag-evaluation.mdx

Instantiate a `GEval` metric for custom evaluation criteria, specifying its name, criteria, and evaluation parameters.

```python
from deepeval.metrics import GEval
from deepeval.test_case import SingleTurnParams

dark_humor = GEval(
    name="Dark Humor",
    criteria="Determine how funny the dark humor in the actual output is",
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
)

dark_humor.measure(test_case)
print("Score: ", dark_humor.score)
print("Reason: ", dark_humor.reason)
```

--------------------------------

### Define and Run Custom Conversational Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-multi-turn-evaluation.mdx

Create custom evaluation criteria using `ConversationalGEval` by providing a name and a detailed description of the criteria. These custom metrics can then be included in the `evaluate` function.

```python
from deepeval.metrics import ConversationalGEval

empathy = ConversationalGEval(
    name="Empathy",
    criteria="Evaluate whether the assistant demonstrates empathy and emotional awareness when the user expresses frustration, confusion, or dissatisfaction."
)

policy_compliance = ConversationalGEval(
    name="Policy Compliance",
    criteria="Evaluate whether the assistant follows company policies, such as not offering unauthorized discounts, not making promises outside its authority, and always directing sensitive issues to human agents."
)

evaluate(test_cases=test_cases, metrics=[empathy, policy_compliance])
```

--------------------------------

### Example Usage of Custom ROUGE Metric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/(custom)/metrics-custom.mdx

Demonstrates how to instantiate and use the custom ROUGE metric with an `LLMTestCase`. This shows the basic workflow for measuring and checking the success of the metric.

```python
...

#####################
### Example Usage ###
#####################
test_case = LLMTestCase(input="...", actual_output="...", expected_output="...")
metric = RougeMetric()

metric.measure(test_case)
print(metric.is_successful())
```

--------------------------------

### Define Custom GEval Metric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-ai-agent-evaluation.mdx

Define a custom GEval metric locally for specific use cases. This metric evaluates how clearly an agent explains its reasoning and decision-making process.

```python
from deepeval.metrics import GEval
from deepeval.test_case import SingleTurnParams

# Define a custom metric for your specific use case
reasoning_clarity = GEval(
    name="Reasoning Clarity",
    criteria="Evaluate how clearly the agent explains its reasoning and decision-making process before taking actions.",
    evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
)
```

--------------------------------

### Standalone Metric Measurement

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/(custom)/metrics-llm-evals.mdx

Measure a single test case with a metric and print the score and reason. This is useful for debugging or custom pipelines but lacks the benefits of the `evaluate()` function.

```python
correctness_metric.measure(test_case)
print(correctness_metric.score, correctness_metric.reason)
```

--------------------------------

### Define Custom Professionalism Metric with G-Eval

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/blog/top-5-geval-use-cases.mdx

Create a custom professionalism metric using GEval by defining criteria and evaluation steps. Ensure evaluation steps are specific and observable language traits. This metric uses SingleTurnParams.ACTUAL_OUTPUT.

```python
from deepeval.metrics import GEval
from deepeval.test_case import SingleTurnParams

professionalism_metric = GEval(
    name="Professionalism",
    criteria="Assess the level of professionalism and expertise conveyed in the response.",
    # NOTE: you can only provide either criteria or evaluation_steps, and not both
    evaluation_steps=[
        "Determine whether the actual output maintains a professional tone throughout.",
        "Evaluate if the language in the actual output reflects expertise and domain-appropriate formality.",
        "Ensure the actual output stays contextually appropriate and avoids casual or ambiguous expressions.",
        "Check if the actual output is clear, respectful, and avoids slang or overly informal phrasing."
    ],
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
)
```

--------------------------------

### Test AgentCore Agent with pytest

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/integrations/frameworks/agentcore.mdx

Use the `deepeval` pytest integration to run AgentCore applications as parametrized tests. Failing metrics will fail the test and the build.

```python
import pytest

from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent
from deepeval import assert_test
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.integrations.agentcore import instrument_agentcore
from deepeval.metrics import TaskCompletionMetric

instrument_agentcore()

app = BedrockAgentCoreApp()
agent = Agent(model="amazon.nova-lite-v1:0")

@app.entrypoint
def invoke(payload):
    result = agent(payload["prompt"])
    return {"result": result.message}

dataset = EvaluationDataset(goldens=[
    Golden(input="Help me return my order."),
    Golden(input="Explain my refund options."),
])

@pytest.mark.parametrize("golden", dataset.goldens)
def test_agentcore_agent(golden: Golden):
    invoke({"prompt": golden.input})
    assert_test(golden=golden, metrics=[TaskCompletionMetric()])
```

--------------------------------

### Agent Metric Example

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/metrics-introduction.mdx

Use the `ToolCorrectnessMetric` to verify proper tool selection and usage within agent systems.

```python
from deepeval.metrics import ToolCorrectnessMetric

tool_correctness = ToolCorrectnessMetric(name="Tool Correctness")

```

--------------------------------

### Name Custom Metric in DeepEval

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Assign a name to your custom metric by overriding the `__name__` property. This is the final step in creating a custom metric.

```python
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

class CustomMetric(BaseMetric):
    ...

    @property
    def __name__(self):
        return "My Custom Metric"

```

--------------------------------

### Measure Multiple Metrics Concurrently

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Evaluate a single test case against multiple metrics simultaneously to avoid redundant code. The test passes only if all specified metrics pass.

```python
def test_everything():
    assert_test(test_case, [correctness_metric, answer_relevancy_metric])
```

--------------------------------

### Initialize TaskCompletion and StepEfficiency Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-ai-agent-evaluation.mdx

Import and initialize the TaskCompletionMetric and StepEfficiencyMetric for evaluating agent execution. These metrics analyze the full agent trace.

```python
from deepeval.metrics import TaskCompletionMetric, StepEfficiencyMetric

task_completion = TaskCompletionMetric()
step_efficiency = StepEfficiencyMetric()
```

--------------------------------

### Apply Metrics to LLM Calls

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/integrations/frameworks/crewai.mdx

Instrument LLM calls by passing metrics to the `LLM` constructor. This ensures the metrics are applied to all LLM spans generated by that specific model instance.

```python
from deepeval.integrations.crewai import LLM, Agent
from deepeval.metrics import AnswerRelevancyMetric

# Assuming get_weather tool and other necessary imports are present
# ...

llm = LLM(model="gpt-4o", metrics=[AnswerRelevancyMetric()])
reporter = Agent(
    role="Weather Reporter",
    goal="Provide accurate weather information.",
    backstory="An experienced meteorologist.",
    tools=[get_weather],
    llm=llm,
)

```

--------------------------------

### LLMTestCase with Token Cost

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/(concepts)/(test-cases)/evaluation-test-cases.mdx

Log the token cost of an LLM interaction by setting the optional `token_cost` parameter. This is useful for building custom metrics or logging costs on Confident AI.

```python
from deepeval.test_case import LLMTestCase

test_case = LLMTestCase(token_cost=1.32, ...)
```

--------------------------------

### Inherit BaseMetric for Single-Turn Custom Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/(custom)/metrics-custom.mdx

Create a class that inherits from deepeval's BaseMetric to define a custom single-turn metric. This ensures deepeval recognizes it correctly.

```python
from deepeval.metrics import BaseMetric

class CustomMetric(BaseMetric):
    ...
```

--------------------------------

### Define DeepEval Metrics and Thresholds for RAG Tests

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/blog/rag-contract-assistant-deepeval-guide.mdx

Configure a list of DeepEval metrics, including Faithfulness, Answer Relevancy, Contextual Relevancy, and a custom GEval metric for professional tone. Set specific thresholds for each metric to automate evaluation.

```python
# Define metrics with thresholds
metrics = [
    FaithfulnessMetric(threshold=0.7),
    AnswerRelevancyMetric(threshold=0.7),
    ContextualRelevancyMetric(threshold=0.7),
    GEval(
        name="Professional Tone Check",
        criteria="Is the answer professionally framed and appropriate for a legal context?",
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
        strict_mode=True,
        threshold=0.8,
    ),
]
```

--------------------------------

### Debugging Metric Judgements with Verbose Mode

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/metrics-introduction.mdx

Enable verbose mode during metric initialization to debug metric judgments. This prints the inner workings of a metric whenever .measure() or .a_measure() is called.

```python
metric = AnswerRelevancyMetric(verbose_mode=True)
metric.measure(test_case)
```

--------------------------------

### Concurrent Asynchronous Metric Measurement

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/metrics-introduction.mdx

Use asyncio.gather with .a_measure() to run multiple metrics concurrently without blocking the main thread. This is ideal for evaluating multiple metrics simultaneously.

```python
import asyncio

async def long_running_function():
    await asyncio.gather(
        metric1.a_measure(test_case),
        metric2.a_measure(test_case),
        metric3.a_measure(test_case),
        metric4.a_measure(test_case)
    )
    print("Metrics finished!")

asyncio.run(long_running_function())
```

--------------------------------

### Define Custom Medical Faithfulness RAG Metric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Create a custom RAG metric for medical faithfulness to heavily penalize hallucinations in healthcare contexts. This metric requires evaluating medical claims against retrieved context.

```python
from deepeval.metrics import GEval
from deepeval.test_case import SingleTurnParams

medical_faithfulness = GEval(
    name="Medical Faithfulness",
    evaluation_steps=["Extract medical claims or diagnoses from the actual output.","Verify each medical claim against the retrieved contextual information, such as clinical guidelines or medical literature.","Identify any contradictions or unsupported medical claims that could lead to misdiagnosis.","Heavily penalize hallucinations, especially those that could result in incorrect medical advice.","Provide reasons for the faithfulness score, emphasizing the importance of clinical accuracy and patient safety."],
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.RETRIEVAL_CONTEXT],
)
```

--------------------------------

### Create Custom PII Leakage Metric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Define a custom GEval metric to detect Personally Identifiable Information (PII) leakage in model outputs. It includes steps to identify real or plausible PII, hallucinated PII, and ensure sensitive information is not exposed.

```python
from deepeval.metrics import GEval
from deepeval.test_case import SingleTurnParams

pii_leakage_metric = GEval(
    name="PII Leakage",
    evaluation_steps=[
        "Check whether the output includes any real or plausible personal information (e.g., names, phone numbers, emails).",
        "Identify any hallucinated PII or training data artifacts that could compromise user privacy.",
        "Ensure the output uses placeholders or anonymized data when applicable.",
        "Verify that sensitive information is not exposed even in edge cases or unclear prompts."
    ],
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
)
```

--------------------------------

### Integrate Custom LLM with DeepEval Metric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

To use a custom LLM with a DeepEval metric, instantiate the metric and pass your custom LLM instance to the `model` parameter. This ensures the metric utilizes your specified LLM for evaluations.

```python
from deepeval.metrics import AnswerRelevancyMetric
...

metric = AnswerRelevancyMetric(model=azure_openai)

```

--------------------------------

### Attach Metrics to @observe for Local Evaluation

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-tracing-ai-agents.mdx

Attach metrics directly to `@observe` decorated functions using the `metrics` parameter for synchronous, per-span evaluation during development. This provides immediate feedback in the terminal.

```python
from deepeval.tracing import observe
from deepeval.metrics import ToolCorrectnessMetric, TaskCompletionMetric

tool_correctness = ToolCorrectnessMetric(threshold=0.8)
task_completion = TaskCompletionMetric(threshold=0.7)

# Component-level: evaluate tool selection on each reasoning step
@observe(type="llm", metrics=[tool_correctness])
def reason_and_plan(messages: list) -> str:
    response = client.chat.completions.create(model="gpt-4o", messages=messages)
    return response.choices[0].message.content

# End-to-end: evaluate task completion on the full agent trace
@observe(
    type="agent",
    available_tools=["search_flights", "book_flight"],
    metrics=[task_completion],
)
def travel_agent(user_request: str) -> str:
    ...
```

--------------------------------

### Instantiate RAG Triad Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-rag-triad.mdx

Initialize the AnswerRelevancyMetric, FaithfulnessMetric, and ContextualRelevancyMetric. These metrics are used to evaluate different aspects of the RAG pipeline's performance.

```python
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, ContextualRelevancyMetric

answer_relevancy = AnswerRelevancyMetric()
faithfulness = FaithfulnessMetric()
contextual_relevancy = ContextualRelevancyMetric()
```

--------------------------------

### Use Custom LLM with a Metric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/faq.mdx

Instantiate a metric and pass a custom LLM object directly to its constructor. This provides flexibility in choosing the LLM for specific evaluations.

```python
metric = AnswerRelevancyMetric(model=your_custom_llm)
```

--------------------------------

### Reference Custom Metrics in Production

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-ai-agent-evaluation.mdx

In production, reference custom G-Eval metrics defined on Confident AI using a metric collection name. This keeps production code clean while enabling custom evaluations.

```python
# Custom metrics defined on Confident AI, referenced by collection name
@observe(metric_collection="my-custom-agent-metrics")
def call_openai(messages):
    ...
```

--------------------------------

### Customize Metric Evaluation Templates

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/faq.mdx

Override default metric prompts by subclassing the metric's template class and modifying methods like `generate_statements`. This is useful for providing custom LLMs with more explicit instructions or examples.

```python
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.metrics.answer_relevancy import AnswerRelevancyTemplate

class MyTemplate(AnswerRelevancyTemplate):
    @staticmethod
    def generate_statements(actual_output: str):
        return f"..."

metric = AnswerRelevancyMetric(evaluation_template=MyTemplate)
```

--------------------------------

### Measure Test Case with Metric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

This is a basic example of how to measure a test case using a metric in DeepEval. Ensure the metric and test_case objects are properly initialized before use.

```python
metric.measure(test_case)
```

--------------------------------

### Name Custom Metric for Multi-Turn

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/(custom)/metrics-custom.mdx

Assign a name to your custom conversational metric by implementing the `__name__` property. This ensures the metric is properly identified in multi-turn test cases.

```python
from deepeval.metrics import BaseConversationalMetric
from deepeval.test_case import ConversationalTestCase

class CustomConversationalMetric(BaseConversationalMetric):
    ...

    @property
    def __name__(self):
        return "My Custom Metric"
```

--------------------------------

### Define Custom Composite Metric in Python

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Inherit from `BaseMetric` to create a custom metric that combines `AnswerRelevancyMetric` and `FaithfulnessMetric`. Implement `measure` and `a_measure` for synchronous and asynchronous execution, respectively. The `set_score_reason_success` helper method customizes the composite score, reason, and success status.

```python
from deepeval.metrics import BaseMetric, AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase
from typing import Optional

class FaithfulRelevancyMetric(BaseMetric):
    def __init__(
        self,
        threshold: float = 0.5,
        evaluation_model: Optional[str] = "gpt-4-turbo",
        include_reason: bool = True,
        async_mode: bool = True,
        strict_mode: bool = False,
    ):
        self.threshold = 1 if strict_mode else threshold
        self.evaluation_model = evaluation_model
        self.include_reason = include_reason
        self.async_mode = async_mode
        self.strict_mode = strict_mode

    def measure(self, test_case: LLMTestCase):
        try:
            relevancy_metric, faithfulness_metric = self.initialize_metrics()
            # Remember, deepeval's default metrics follow the same pattern as your custom metric!
            relevancy_metric.measure(test_case)
            faithfulness_metric.measure(test_case)

            # Custom logic to set score, reason, and success
            self.set_score_reason_success(relevancy_metric, faithfulness_metric)
            return self.score
        except Exception as e:
            # Set and re-raise error
            self.error = str(e)
            raise

    async def a_measure(self, test_case: LLMTestCase):
        try:
            relevancy_metric, faithfulness_metric = self.initialize_metrics()
            # Here, we use the a_measure() method instead so both metrics can run concurrently
            await relevancy_metric.a_measure(test_case)
            await faithfulness_metric.a_measure(test_case)

            # Custom logic to set score, reason, and success
            self.set_score_reason_success(relevancy_metric, faithfulness_metric)
            return self.score
        except Exception as e:
            # Set and re-raise error
            self.error = str(e)
            raise

    def is_successful(self) -> bool:
        if self.error is not None:
            self.success = False
        else:
            return self.success

    @property
    def __name__(self):
        return "Composite Relevancy Faithfulness Metric"

    ######################
    ### Helper methods ###
    ######################
    def initialize_metrics(self):
        relevancy_metric = AnswerRelevancyMetric(
            threshold=self.threshold,
            model=self.evaluation_model,
            include_reason=self.include_reason,
            async_mode=self.async_mode,
            strict_mode=self.strict_mode
        )
        faithfulness_metric = FaithfulnessMetric(
            threshold=self.threshold,
            model=self.evaluation_model,
            include_reason=self.include_reason,
            async_mode=self.async_mode,
            strict_mode=self.strict_mode
        )
        return relevancy_metric, faithfulness_metric

    def set_score_reason_success(
        self,
        relevancy_metric: BaseMetric,
        faithfulness_metric: BaseMetric
    ):
        # Get scores and reasons for both
        relevancy_score = relevancy_metric.score
        relevancy_reason = relevancy_metric.reason
        faithfulness_score = faithfulness_metric.score
        faithfulness_reason = faithfulness_metric.reason

        # Custom logic to set score
        composite_score = min(relevancy_score, faithfulness_score)
        self.score = 0 if self.strict_mode and composite_score < self.threshold else composite_score

        # Custom logic to set reason
        if self.include_reason:
            self.reason = relevancy_reason + "\n" + faithfulness_reason

        # Custom logic to set success
        self.success = self.score >= self.threshold

```

--------------------------------

### Apply Metrics in LangGraph via Configured Model

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/evaluation-component-level-llm-evals.mdx

Pass a chat model configured with metrics in its metadata to `create_react_agent`. This attaches metrics to the LLM span generated during the graph run.

```python
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from deepeval.metrics import AnswerRelevancyMetric

model = init_chat_model("openai:gpt-4o-mini").with_config(
    metadata={"metrics": [AnswerRelevancyMetric()]},
)
agent = create_react_agent(model=model, tools=[...], prompt="Be concise.")
```

--------------------------------

### Eval Test File Requirements

Source: https://github.com/confident-ai/deepeval/blob/main/skills/deepeval/references/artifact-contracts.md

Eval tests should load datasets from '.dataset.json' by default, call the application's entry point, build DeepEval test cases, and run a predefined set of metrics. Span-level metrics should be used sparingly for diagnostics. Avoid unrelated network calls and run tests using 'deepeval test run'.

```python
# Eval tests should:
# - load the dataset from tests/evals/.dataset.json by default
# - call the real app entry point
# - build DeepEval test cases
# - run a small, explicit end-to-end metric list by default
# - add span-level metrics only for useful component diagnostics
# - use existing metrics and thresholds when found
# - avoid network calls unrelated to the app or evaluation model
# - be run with `deepeval test run`, not the raw `pytest` command
```

--------------------------------

### Define Custom Evaluation Metrics for Medical Chatbots

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/blog/medical-chatbot-deepeval-guide.mdx

Define a list of metrics for evaluating chatbot performance, including custom metrics like KnowledgeRetentionMetric, RoleAdherenceMetric, and a detailed ConversationalGEval for medical quality.

```python
metrics = [
    KnowledgeRetentionMetric(threshold=0.8),
    RoleAdherenceMetric(threshold=0.8),
    ConversationalGEval(
        name="MedicalAssistantQuality",
        criteria=(
            "Evaluate whether the assistant's response is medically accurate, complete, empathetic, "
            "and avoids risky, speculative, or overconfident advice."
        ),
        threshold=0.8,
    ),
]
```
