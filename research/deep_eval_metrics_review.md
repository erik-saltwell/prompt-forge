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

### Measure Test Case with Metric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

This is a basic example of how to measure a test case using a metric in DeepEval. Ensure the metric and test_case objects are properly initialized before use.

```python
metric.measure(test_case)
```

--------------------------------

### Define Deepeval Evaluation Dataset and Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/integrations/frameworks/huggingface.mdx

Create a Deepeval `EvaluationDataset` with `Golden` objects and define evaluation metrics like `GEval` for coherence. This setup is used for real-time evaluation during fine-tuning.

```python
from deepeval.test_case import SingleTurnParams
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.metrics import GEval

first_golden = Golden(input="...")
second_golden = Golden(input="...")

dataset = EvaluationDataset(goldens=[first_golden, second_golden])
coherence_metric = GEval(
    name="Coherence",
    criteria="Coherence - determine if the actual output is coherent with the input.",
    evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
)
```

--------------------------------

### Using Custom LLM with DeepEval Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-using-custom-llms.mdx

Instantiate your custom LLM and use it with DeepEval metrics like AnswerRelevancyMetric for evaluations.

```python
from deepeval.metrics import AnswerRelevancyMetric
...

custom_llm = CustomLlama3_8B()
metric = AnswerRelevancyMetric(model=custom_llm)
metric.measure(...)
```

--------------------------------

### Use Custom LLM with DeepEval Metric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-using-custom-llms.mdx

Supply your instantiated custom LLM object to a deepeval metric, such as AnswerRelevancyMetric, to perform evaluations using your chosen model.

```python
from deepeval.metrics import AnswerRelevancyMetric
...

metric = AnswerRelevancyMetric(model=custom_llm)
metric.measure(...)
```

--------------------------------

### Use Custom Mistral 7B Model in DeepEval Metric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-using-custom-llms.mdx

Integrate the custom Mistral 7B LLM with a DeepEval metric by passing an instance of the custom model wrapper to the metric's constructor. This allows DeepEval to use your custom model for evaluations.

```python
from deepeval.metrics import AnswerRelevancyMetric
...

metric = AnswerRelevancyMetric(model=mistral_7b)
```

--------------------------------

### Use Custom Vertex AI Model in DeepEval Metric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-using-custom-llms.mdx

Integrate the custom Google Vertex AI LLM with a DeepEval metric by passing an instance of the custom model wrapper to the metric's constructor. This enables DeepEval to utilize your Vertex AI model for evaluations.

```python
from deepeval.metrics import AnswerRelevancyMetric
...

metric = AnswerRelevancyMetric(model=vertexai_gemini)
```

--------------------------------

### LangGraph Integration with DeepEval

Source: https://github.com/confident-ai/deepeval/blob/main/README.md

Integrate DeepEval metrics with LangGraph for end-to-end trace evaluation. The CallbackHandler is used to capture metrics during agent invocation.

```python
from deepeval.integrations.langchain import CallbackHandler
from deepeval.metrics import TaskCompletionMetric

# This metric will be run on your trace end to end.
for golden in dataset.evals_iterator():
    agent.invoke(
        {"messages": [{"role": "user", "content": golden.input}]},
        config={"callbacks": [CallbackHandler(metrics=[TaskCompletionMetric()])]}
    )
```

--------------------------------

### Integrate Custom LLM with DeepEval Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-using-custom-llms.mdx

Supply your custom-wrapped LLM to DeepEval metrics by passing the instance to the metric's model parameter. This allows DeepEval to use your custom model for evaluation tasks.

```python
from deepeval.metrics import AnswerRelevancyMetric
...

metric = AnswerRelevancyMetric(model=aws_bedrock)
```

--------------------------------

### Evaluate Retriever with DeepEval Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/blog/rag-contract-assistant-deepeval-guide.mdx

Evaluate a retriever's performance using DeepEval's Contextual Relevancy, Contextual Recall, and Contextual Precision metrics. This involves creating LLMTestCase objects with retrieved contexts and measuring them against generated goldens.

```python
from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    ContextualRelevancyMetric,
    ContextualRecallMetric,
    ContextualPrecisionMetric,
)

# Initialize metrics
relevancy = ContextualRelevancyMetric()
recall = ContextualRecallMetric()
precision = ContextualPrecisionMetric()

# Evaluate for each golden
for golden in goldens:
    retrieved_docs = retriever.retrieve(golden.input)
    context_list = [doc.page_content for doc in retrieved_docs]
    test_case = LLMTestCase(
        input=golden.input,
        actual_output=golden.expected_output,
        expected_output=golden.expected_output,
        retrieval_context=context_list
    )
    relevancy.measure(test_case)
    recall.measure(test_case)
    precision.measure(test_case)

    print(f"Q: {golden.input}\nA: {golden.expected_output}")
    print(f"Relevancy: {relevancy.score}, Recall: {recall.score}, Precision: {precision.score}")
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

### Run Local Evaluations with DeepEval

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Run evaluations locally using DeepEval with a dataset and a list of metrics. This allows for greater flexibility in metric customization.

```python
from deepeval import evaluate
from deepeval.metrics import AnswerRelevancyMetric
...

evaluate(dataset, metrics=[AnswerRelevancyMetric()])
```

--------------------------------

### Pydantic AI Integration with DeepEval

Source: https://github.com/confident-ai/deepeval/blob/main/README.md

Evaluate Pydantic AI applications using DeepEval metrics. Metrics can be passed directly to the evals_iterator.

```python
from deepeval.metrics import TaskCompletionMetric

# This metric will be run on your trace end to end.
for golden in dataset.evals_iterator(metrics=[TaskCompletionMetric()]):
    agent.run_sync(golden.input)
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

### Iterate Retriever Configurations with DeepEval

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/blog/rag-contract-assistant-deepeval-guide.mdx

Iterate through various chunk sizes, embedding models, and retriever types to evaluate their impact on retrieval metrics. This setup is useful for systematic hyperparameter tuning.

```python
for chunk_size in chunking_strategies:
    for embedding_name, embedding_model in embedding_models:
        for retriever_name, retriever_type in retriever_models:
            print(f"Evaluating with Chunk Size: {chunk_size}, Embedding: {embedding_name}, Retriever: {retriever_name}")

            persist_dir = tempfile.mkdtemp() if retriever_type == Chroma else None

            retriever = SimpleRetriever(
                document_path="document.txt",
                chunk_size=chunk_size,
                chunk_overlap=50,
                embedding_model=embedding_model,
                vector_store_class=retriever_type,
                persist_directory=persist_dir,  # Pass only if using Chroma
            )

            for golden in goldens:
                retrieved_docs = retriever.retrieve(golden.input)
                context_list = [doc.page_content for doc in retrieved_docs]

                test_case = LLMTestCase(
                    input=golden.input,
                    actual_output=golden.expected_output,
                    expected_output=golden.expected_output,
                    retrieval_context=context_list
                )

                relevancy.measure(test_case)
                recall.measure(test_case)
                precision.measure(test_case)

                print(f"Q: {golden.input[:70]}...")
                print(f"Relevancy: {relevancy.score}, Recall: {recall.score}, Precision: {precision.score}")
```

--------------------------------

### Comprehensive AI Agent Evaluation Example

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-ai-agent-evaluation-metrics.mdx

This example demonstrates using multiple Deepeval metrics for end-to-end and component-level evaluation of an AI agent. It includes setting up various metrics, defining tools, and running evaluations on a dataset.

```python
from deepeval.tracing import observe, update_current_span
from deepeval.dataset import Golden, EvaluationDataset, get_current_golden
from deepeval.test_case import LLMTestCase, ToolCall
from deepeval.metrics import (
    TaskCompletionMetric,
    StepEfficiencyMetric,
    PlanQualityMetric,
    PlanAdherenceMetric,
    ToolCorrectnessMetric,
    ArgumentCorrectnessMetric
)

# End-to-end metrics (analyze full agent trace)
task_completion = TaskCompletionMetric()
step_efficiency = StepEfficiencyMetric()
plan_quality = PlanQualityMetric()
plan_adherence = PlanAdherenceMetric()

# Component-level metrics (analyze specific components)
tool_correctness = ToolCorrectnessMetric()
argument_correctness = ArgumentCorrectnessMetric()

# Define tools
@observe(type="tool")
def search_flights(origin, destination, date):
    return [{"id": "FL123", "price": 450}, {"id": "FL456", "price": 380}]

@observe(type="tool")
def book_flight(flight_id):
    return {"confirmation": "CONF-789", "flight_id": flight_id}

# Attach component-level metrics to the LLM component
@observe(type="llm", metrics=[tool_correctness, argument_correctness])
def call_llm(user_input):
    # LLM decides to search flights then book
    origin, destination, date = "NYC", "Paris", "2025-03-18"
    flights = search_flights(origin, destination, date)
    cheapest = min(flights, key=lambda x: x["price"])
    booking = book_flight(cheapest["id"])

    # Update span with tool info for component-level evaluation
    update_current_span(
        input=user_input,
        output=f"Booked {cheapest['id']}",
        expected_tools=get_current_golden().expected_tools
    )
    return booking

@observe(type="agent")
def travel_agent(user_input):
    booking = call_llm(user_input)
    return f"Flight booked! Confirmation: {booking['confirmation']}"

# Create evaluation dataset
dataset = EvaluationDataset(goldens=[
    Golden(input="Book a flight from NYC to Paris for next Tuesday", expected_tools=[ToolCall(name="search_flights"), ToolCall(name="book_flight")])
])

# Run evaluation with end-to-end metrics
for golden in dataset.evals_iterator(
    metrics=[task_completion, step_efficiency, plan_quality, plan_adherence]
):
    travel_agent(golden.input)
```

--------------------------------

### Evaluate Agent with Reasoning Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-ai-agent-evaluation.mdx

Prepare an EvaluationDataset and iterate through it using evals_iterator, passing the initialized PlanQualityMetric and PlanAdherenceMetric. This setup allows DeepEval to automatically collect traces and run the specified metrics on your agent's execution.

```python
from deepeval.dataset import EvaluationDataset, Golden

# Create dataset
dataset = EvaluationDataset(goldens=[
    Golden(input="Book a flight from NYC to London for next Monday")
])

# Loop through dataset with metrics
for golden in dataset.evals_iterator(metrics=[plan_quality, plan_adherence]):
    travel_agent(golden.input)
```

--------------------------------

### Run CrewAI Evaluations with AnswerRelevancyMetric using Python

Source: https://github.com/confident-ai/deepeval/blob/main/examples/notebooks/crewai.ipynb

This snippet shows how to initialize and use the AnswerRelevancyMetric from Deepeval to evaluate a CrewAI crew. It iterates through a dataset's golden examples and uses Deepeval's tracing to capture metric results during the crew's kickoff process. Ensure you have `deepeval` and `crewai` installed.

```python
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.tracing import trace

answer_relavancy_metric = AnswerRelevancyMetric()

for golden in dataset.evals_iterator():
    with trace(trace_metrics=[answer_relavancy_metric]):
        result = crew.kickoff(
            inputs={"topic": golden.input},
            metrics=[AnswerRelevancyMetric()]
        )
```

--------------------------------

### Run LLM Evaluations with DeepEval

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Use the `evaluate` function from DeepEval to run evaluations on a dataset with specified metrics and hyperparameters. This is useful for benchmarking different model configurations.

```python
from deepeval import evaluate


evaluate(
  dataset,
  metrics=[answer_relevancy_metric, faithfulness_metric],
  hyperparameters={"model": model, "prompt template": prompt_template, "top-k": top_k}
)

```

--------------------------------

### Defining Evaluation Datasets and Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/examples/notebooks/openai.ipynb

Create an evaluation dataset using Golden objects and select appropriate metrics such as AnswerRelevancyMetric and BiasMetric for performance assessment.

```python
from deepeval.dataset import Golden, EvaluationDataset
from deepeval.metrics import AnswerRelevancyMetric, BiasMetric

goldens = [
    Golden(input="What are the top 5 most popular palces to eat in New York City?"),
    Golden(input="What is the weather in Paris, France?"),
]

dataset = EvaluationDataset(goldens=goldens)
metrics = [AnswerRelevancyMetric(), BiasMetric()]
```

--------------------------------

### Evaluate RAG Pipeline with DeepEval Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Run the evaluation for a RAG pipeline using DeepEval's metrics and LLMTestCase. Ensure 'actual_output' and 'retrieval_context' are correctly generated.

```python
from deepeval.metrics import (
    ContextualRecallMetric,
    ContextualPrecisionMetric,
    ContextualRelevancyMetric,
)
from deepeval.test_case import LLMTestCase
from deepeval import evaluate

...
test_case = LLMTestCase(
    input=input,
    actual_output=actual_output,
    retrieval_context=retrieval_context,
    expected_output="Cognee is the Graph RAG Framework.",
)
evaluate(
    [test_case],
    metrics=(
        ContextualRecallMetric(),
        ContextualPrecisionMetric(),
        ContextualRelevancyMetric(),
    ),
)
```

--------------------------------

### Run Built-in Multi-Turn Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-multi-turn-evaluation.mdx

Use the `evaluate` function with a list of deepeval's built-in multi-turn metrics to assess conversational quality. Ensure `test_cases` are prepared beforehand.

```python
from deepeval import evaluate
from deepeval.metrics import (
    ConversationCompletenessMetric,
    TurnRelevancyMetric,
    KnowledgeRetentionMetric,
    RoleAdherenceMetric,
)

evaluate(
    test_cases=test_cases,
    metrics=[
        ConversationCompletenessMetric(),
        TurnRelevancyMetric(),
        KnowledgeRetentionMetric(),
        RoleAdherenceMetric(),
    ]
)
```

--------------------------------

### Define a Custom G-Eval Metric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Use the GEval class to define a custom metric by providing a name, criteria, and evaluation parameters. DeepEval automatically generates evaluation steps from the criteria if none are explicitly provided.

```python
custom_metric = GEval(
    name="Relevancy",
    criteria="Check if the actual output directly addresses the input.",
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.INPUT]
)
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

### Configure DeepEval CallbackHandler

Source: https://github.com/confident-ai/deepeval/blob/main/examples/notebooks/langgraph.ipynb

Integrates DeepEval metrics into the LangGraph execution flow using the CallbackHandler to perform automated evaluation during inference.

```python
from deepeval.integrations.langchain import CallbackHandler
from deepeval.metrics import TaskCompletionMetric

def run_rag_query(query: str):
    initial_state["messages"] = [HumanMessage(content=query)]
    result = app.invoke(
        initial_state,
        config={
            "callbacks": [
                CallbackHandler(
                    metrics=[
                        TaskCompletionMetric(strict_mode=True, async_mode=False)
                    ]
                )
            ]
        },
    )
    final_message = result["messages"][-1]
    return final_message.content
```

--------------------------------

### Evaluate Simulated Turns with DeepEval Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/conversation-simulator/index.mdx

Use the `ConversationalTestCase` objects generated by the simulator to evaluate your LLM chatbot with `deepeval`'s conversational metrics. This enables end-to-end evaluation of your chatbot's performance.

```python
from deepeval import evaluate
from deepeval.metrics import TurnRelevancyMetric
...

evaluate(test_cases=conversational_test_cases, metrics=[TurnRelevancyMetric()])
```

--------------------------------

### Define a Custom GEval Metric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/blog/top-5-geval-use-cases.mdx

Use the GEval class to define a custom metric by providing a name, criteria, and evaluation parameters. DeepEval automatically generates evaluation steps from the criteria, or you can supply your own for more control.

```python
from deepeval.metrics import GEval
from deepeval.test_case import SingleTurnParams

# Define a custom G-Eval metric
custom_metric = GEval(
    name="Relevancy",
    criteria="Check if the actual output directly addresses the input.",
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.INPUT]
)
```

--------------------------------

### Evaluate Generator Performance with DeepEval Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/blog/rag-contract-assistant-deepeval-guide.mdx

Set up a DeepEval evaluation pipeline by defining an LLMTestCase with query, expected answer, and retrieval context. Initialize and run FaithfulnessMetric, AnswerRelevancyMetric, and custom GEval metrics for Tone and Citations.

```python
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric, GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

# Hardcoded query and expected answer
query = "What benefits do part-time employees get?"
expected_answer = "Part-time employees receive prorated healthcare coverage, flexible PTO, and are eligible for wellness reimbursements."

# Run RAG pipeline
retrieved_docs = retriever.retrieve(query)
context = [doc.page_content for doc in retrieved_docs]
generated_answer = generator.generate(query)

# Create test case
test_case = LLMTestCase(
    input=query,
    actual_output=generated_answer,
    expected_output=expected_answer,
    retrieval_context=context,
)

# Initialize metrics
metrics = [
    FaithfulnessMetric(),
    AnswerRelevancyMetric(),
    GEval(
        name="Tone",
        criteria="Is the answer professional?",
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
        strict_mode=True,
    ),
    GEval(
        name="Citations",
        criteria="Does the answer cite or refer to the source documents?",
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.CONTEXT],
        strict_mode=True,
    ),
]


# Evaluate
for metric in metrics:
    metric.measure(test_case)
    print(f"{metric.name}: {metric.score} | {metric.reason}")
```

--------------------------------

### Evaluate LLMTestCase with Contextual Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/integrations/vector-databases/pgvector.mdx

Evaluates an LLMTestCase using DeepEval's contextual metrics (Recall, Precision, Relevancy) to assess the effectiveness of the PGVector retriever. Ensure necessary metrics and test cases are imported and instantiated.

```python
from deepeval import evaluate
from deepeval.metrics import (
    ContextualRecallMetric,
    ContextualPrecisionMetric,
    ContextualRelevancyMetric,
)

# Assume 'test_case' is an instantiated LLMTestCase
contextual_recall = ContextualRecallMetric()
contextual_precision = ContextualPrecisionMetric()
contextual_relevancy = ContextualRelevancyMetric()

evaluate(
    [test_case],
    metrics=[contextual_recall, contextual_precision, contextual_relevancy]
)
```

--------------------------------

### Evaluate Agent with Action Layer Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-ai-agent-evaluation.mdx

Prepare an EvaluationDataset and iterate through it using evals_iterator. This setup, combined with the decorated LLM component, allows DeepEval to collect traces and run the specified action layer metrics on your agent's tool calling behavior.

```python
from deepeval.dataset import EvaluationDataset, Golden

# Create dataset
dataset = EvaluationDataset(goldens=[
    Golden(input="What's the weather like in San Francisco and should I bring an umbrella?")
])

# Evaluate with action layer metrics
for golden in dataset.evals_iterator():
    weather_agent(golden.input)
```

--------------------------------

### Inherit BaseConversationalMetric for Multi-Turn Custom Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/(custom)/metrics-custom.mdx

Create a class that inherits from deepeval's BaseConversationalMetric to define a custom multi-turn metric. This ensures deepeval recognizes it correctly.

```python
from deepeval.metrics import BaseConversationalMetric

class CustomConversationalMetric(BaseConversationalMetric):
    ...
```

--------------------------------

### Run Multi-Turn Evaluation

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/(use-cases)/getting-started-chatbots.mdx

Execute an evaluation using Deepeval's multi-turn metrics like TurnRelevancyMetric and KnowledgeRetentionMetric. The evaluate function takes a list of test cases and metrics.

```python
from deepeval.metrics import TurnRelevancyMetric, KnowledgeRetentionMetric
from deepeval import evaluate

evaluate(test_cases=[test_case], metrics=[TurnRelevancyMetric(), KnowledgeRetentionMetric()])
```

--------------------------------

### Initialize Metric with Ollama Model from ENV

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/integrations/models/ollama.mdx

Use any Ollama model directly in DeepEval by setting `LOCAL_MODEL_API_KEY` in your environment and passing the model name during metric initialization.

```python
from deepeval.metrics import AnswerRelevancyMetric

answer_relevancy = AnswerRelevancyMetric(
    model="deepseek-r1:1.5b",
)
```

--------------------------------

### Google ADK Integration with DeepEval

Source: https://github.com/confident-ai/deepeval/blob/main/README.md

Integrate DeepEval with Google ADK for asynchronous evaluations. Use instrument_google_adk() and AsyncConfig for parallel metric runs.

```python
import asyncio
from deepeval.evaluate.configs import AsyncConfig
from deepeval.integrations.google_adk import instrument_google_adk
from deepeval.metrics import TaskCompletionMetric

instrument_google_adk()

# This metric will be run on your trace end to end.
for golden in dataset.evals_iterator(
    async_config=AsyncConfig(run_async=True),
    metrics=[TaskCompletionMetric()]
):
    task = asyncio.create_task(run_agent(golden.input))
    dataset.evaluate(task)
```

--------------------------------

### Debug DeepEval Metric Scores

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-llm-as-a-judge.mdx

Measure and inspect the score and reason for a DeepEval metric. This is crucial for understanding why a metric produced a certain result. Ensure the `test_case` object is correctly populated.

```python
metric.measure(test_case)
print(metric.score)
print(metric.reason)
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

### Assert LLMTestCase with Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Assert a test case by calling the `assert_test` function and running `deepeval test run`. A test case passes if all metrics pass, using various components like input, actual_output, and context.

```python
# A hypothetical LLM application example
import chatbot
import deepeval
from deepeval import assert_test
from deepeval.metrics import HallucinationMetric
from deepeval.test_case import LLMTestCase

def test_assert_example():
    input = "Why did the chicken cross the road?"
    test_case = LLMTestCase(
        input=input,
        actual_output=chatbot.run(input),
        context=["The chicken wanted to cross the road."],
    )
    metric = HallucinationMetric(threshold=0.7)
    assert_test(test_case, metrics=[metric])

# Optionally log hyperparameters to pick the best hyperparameter for your LLM application

```

--------------------------------

### Evaluate with TurnRelevancyMetric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Use the evaluate function with a list of metrics to run end-to-end evaluations on simulated conversations. Ensure deepeval and the desired metrics are imported.

```python
from deepeval import evaluate
from deepeval.metrics import TurnRelevancyMetric
...

evaluate(test_cases=convo_test_cases, metrics=[TurnRelevancyMetric()])
```

--------------------------------

### Implement RougeMetric using DeepEval Scorer

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Create a custom non-LLM evaluation metric using the ROUGE score. This metric is not scored by an LLM and requires the `rouge-score` package. Ensure `rouge-score` is installed via `pip install rouge-score`.

```python
from deepeval.scorer import Scorer
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

class RougeMetric(BaseMetric):
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
        self.scorer = Scorer()

    def measure(self, test_case: LLMTestCase):
        self.score = self.scorer.rouge_score(
            prediction=test_case.actual_output,
            target=test_case.expected_output,
            score_type="rouge1"
        )
        self.success = self.score >= self.threshold
        return self.score

    # Async implementation of measure(). If async version for
    # scoring method does not exist, just reuse the measure method.
    async def a_measure(self, test_case: LLMTestCase):
        return self.measure(test_case)

    def is_successful(self):
        return self.success

    @property
    def __name__(self):
        return "Rouge Metric"

```

--------------------------------

### CrewAI Integration with DeepEval

Source: https://github.com/confident-ai/deepeval/blob/main/README.md

Instrument CrewAI applications with DeepEval for metric evaluation. Use instrument_crewai() to enable DeepEval's integration.

```python
from deepeval.integrations.crewai import instrument_crewai
from deepeval.metrics import TaskCompletionMetric

instrument_crewai()

# This metric will be run on your trace end to end.
for golden in dataset.evals_iterator(metrics=[TaskCompletionMetric()]):
    crew.kickoff({"input": golden.input})
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

### Initialize and Use JsonCorrectnessMetric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Initialize the JsonCorrectnessMetric with the expected schema and use it within the DeepEval evaluation framework. This snippet shows how to set up the metric, create a test case, and run the evaluation.

```python
from deepeval import evaluate
from deepeval.metrics import JsonCorrectnessMetric
from deepeval.test_case import LLMTestCase

metric = JsonCorrectnessMetric(
    expected_schema=ExampleSchema,
    model="gpt-4",
    include_reason=True
)
test_case = LLMTestCase(
    input="Output me a random Json with the 'name' key",
    # Replace this with the actual output from your LLM application
    actual_output="{'name': null}"
)

# To run metric as a standalone
# metric.measure(test_case)
# print(metric.score, metric.reason)

evaluate(test_cases=[test_case], metrics=[metric])

```

--------------------------------

### Set Ollama Model for DeepEval

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/metrics-introduction.mdx

Configure DeepEval to use a specific Ollama model for metrics. The base URL can be specified if using a custom port.

```bash
deepeval set-ollama --model=deepseek-r1:1.5b
```

```bash
deepeval set-ollama --model=deepseek-r1:1.5b \
    --base-url="http://localhost:11434"
```

--------------------------------

### Run Component Metrics in CI/CD with LangChain

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/integrations/frameworks/langchain.mdx

Use this Python code within your CI/CD pipeline to test LangChain components with DeepEval metrics. Ensure `deepeval test run` is configured to execute these tests.

```python
import pytest
from deepeval import assert_test
...

@pytest.mark.parametrize("golden", dataset.goldens)
def test_component_metrics(golden: Golden):
    llm_with_component_metric.invoke(golden.input, config={"callbacks": [CallbackHandler()]})
    assert_test(golden=golden)
```

--------------------------------

### Run Evaluation with deepeval

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/integrations/vector-databases/elasticsearch.mdx

Use the deepeval 'evaluate' function, passing in a list of test cases and a list of defined metrics. This initiates the evaluation process for your RAG pipeline and retriever.

```python
from deepeval import evaluate

evaluate(
    [test_case],
    metrics=[contextual_recall, contextual_precision, contextual_relevancy]
)
```

--------------------------------

### Create LLM Regression Test File

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-regression-testing-in-cicd.mdx

Define LLM test cases and metrics in a Python file for regression testing. Use deepeval's `LLMTestCase` and metrics like `AnswerRelevancyMetric`. Load datasets using deepeval's dataset utilities for scalability.

```python
import pytest

from deepeval import assert_test
from deepeval.metrics import HallucinationMetric, AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase
from deepeval.dataset import EvaluationDataset

first_test_case = LLMTestCase(input="...", actual_output="...")
second_test_case = LLMTestCase(input="...", actual_output="...")
dataset = EvaluationDataset(
    test_cases=[first_test_case, second_test_case]
)

@pytest.mark.parametrize(
    "test_case",
    dataset.test_cases,
)
def test_example(test_case: LLMTestCase):
    metric = AnswerRelevancyMetric(threshold=0.5)
    assert_test(test_case, [metric])
```

--------------------------------

### Recommend Metrics using DeepEval CLI

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Run this command in your terminal to get suggestions for metrics based on your LLM application.

```bash
deepeval recommend metrics

```

--------------------------------

### Set Ollama Model for DeepEval

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Configure DeepEval to use a specific Ollama model for metrics by running 'deepeval set-ollama' with the model name.

```bash
deepeval set-ollama deepseek-r1:1.5b
```

--------------------------------

### LlamaIndex Integration with DeepEval

Source: https://github.com/confident-ai/deepeval/blob/main/README.md

Evaluate LlamaIndex applications asynchronously using DeepEval. Configure AsyncConfig for running metrics in parallel.

```python
import asyncio
from deepeval.evaluate.configs import AsyncConfig
from deepeval.metrics import TaskCompletionMetric

# This metric will be run on your trace end to end.
for golden in dataset.evals_iterator(
    async_config=AsyncConfig(run_async=True),
    metrics=[TaskCompletionMetric()]
):
    task = asyncio.create_task(agent.run(golden.input))
    dataset.evaluate(task)
```

--------------------------------

### Instrument OpenAI Agent with deepeval Tracing

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/integrations/frameworks/openai-agents.mdx

Register the DeepEvalTracingProcessor and use deepeval's Agent and function_tool wrappers. Attach metrics to your agent and tools for evaluation.

```python
from agents import Runner, add_trace_processor
from deepeval.openai_agents import Agent, DeepEvalTracingProcessor, function_tool
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.metrics import TaskCompletionMetric

add_trace_processor(DeepEvalTracingProcessor())

@function_tool
def get_weather(city: str) -> str:
    """Return the weather in a city."""
    return f"It's always sunny in {city}!"

agent = Agent(
    name="weather_agent",
    instructions="Answer weather questions concisely.",
    tools=[get_weather],
    agent_metrics=[TaskCompletionMetric()],
)

# Goldens are the inputs you want to evaluate.
dataset = EvaluationDataset(goldens=[Golden(input="What's the weather in Paris?")])

for golden in dataset.evals_iterator():
    Runner.run_sync(agent, golden.input)
```

--------------------------------

### Component-Level Evaluation with DeepEval

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/evaluation-unit-testing-in-ci-cd.mdx

Attach metrics directly to individual `@observe`'d spans for grading internal components like retrievers or tool calls, alongside end-to-end traces.

```python
from deepeval.metrics import AnswerRelevancyMetric

# Example of attaching metrics to spans (specific syntax depends on integration)
# observe(metric=AnswerRelevancyMetric())
# ... your component code ...

```

--------------------------------

### LangChain Integration with DeepEval

Source: https://github.com/confident-ai/deepeval/blob/main/README.md

Integrate DeepEval metrics with LangChain for end-to-end trace evaluation. Ensure the CallbackHandler is configured with the desired metrics.

```python
from deepeval.integrations.langchain import CallbackHandler
from deepeval.metrics import TaskCompletionMetric

# This metric will be run on your trace end to end.
for golden in dataset.evals_iterator():
    llm.invoke(
        golden.input,
        config={"callbacks": [CallbackHandler(metrics=[TaskCompletionMetric()])]}
    )
```

--------------------------------

### Running Metrics Asynchronously

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-building-custom-metrics.mdx

When `assert_test` is called with `run_async=True`, deepeval invokes the `a_measure` method, enabling concurrent execution of metrics.

```python
from deepeval import assert_test

def test_multiple_metrics():
    ...
    assert_test(test_case, [metric1, metric2], run_async=True)
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

### Use Moonshot Model via Environment Variables

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/integrations/models/moonshot.mdx

Configure DeepEval to use Moonshot models by setting the `USE_MOONSHOT_MODEL` environment variable to 1. The model name is then passed directly during metric initialization.

```python
from deepeval.metrics import AnswerRelevancyMetric

answer_relevancy = AnswerRelevancyMetric(
    model="kimi-k2-0711-preview",
)
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

### Run LLM Evaluation with DeepEval

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Use the `evaluate` function to run a list of metrics against test cases. Ensure you are logged into Confident AI before running.

```python
from deepeval.metrics import AnswerRelevancyMetric
from deepeval import evaluate

evaluate(test_cases=[...], metrics=[AnswerRelevancyMetric()])
```

--------------------------------

### Running Metrics Asynchronously with assert_test

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

When `run_async=True` is set in `assert_test`, DeepEval invokes the `a_measure()` method of metrics, allowing for concurrent execution.

```python
from deepeval import assert_test

def test_multiple_metrics():
    ...
    assert_test(test_case, [metric1, metric2], run_async=True)

```

--------------------------------

### Evaluate Exact Match Metric

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/(non-llm)/metrics-exact-match.mdx

Use this snippet to evaluate the ExactMatchMetric within the DeepEval framework. It requires importing necessary classes and defining test cases with input, actual, and expected outputs.

```python
from deepeval import evaluate
from deepeval.metrics import ExactMatchMetric
from deepeval.test_case import LLMTestCase

metric = ExactMatchMetric(
    threshold=1.0,
    verbose_mode=True,
)

test_case = LLMTestCase(
    input="Translate 'Hello, how are you?' in french",
    actual_output="Bonjour, comment ça va ?",
    expected_output="Bonjour, comment allez-vous ?"
)

# To run metric as a standalone
# metric.measure(test_case)
# print(metric.score, metric.reason)

evaluate(test_cases=[test_case], metrics=[metric])
```

--------------------------------

### Enable Verbose Mode for Metrics

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/docs/evaluation-flags-and-configs.mdx

Use the `-v` flag to enable verbose mode for all metrics during a `deepeval test run`. When enabled, intermediate steps for metric calculations are printed to the console.

```bash
deepeval test run test_example.py -v
```

--------------------------------

### Define and Run DeepEval Metrics for Chatbot Evaluation

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/blog/medical-chatbot-deepeval-guide.mdx

Set up evaluation metrics including `RoleAdherenceMetric`, `KnowledgeRetentionMetric`, and `ConversationalGEval` for a chatbot. Assign chatbot roles to test cases and configure custom criteria for the `ConversationalGEval`.

```python
from deepeval.metrics import (
    RoleAdherenceMetric,
    KnowledgeRetentionMetric,
    ConversationalGEval,
)
from deepeval import evaluate

# Assign role to each test case for Role Adherence evaluation
for test_case in convo_test_cases:
    test_case.chatbot_role = "a professional, empathetic medical assistant"

# Define evaluation metrics
metrics = [
    KnowledgeRetentionMetric(),
    RoleAdherenceMetric(),
    ConversationalGEval(
        name="MedicalAssistantQuality",
        criteria="Evaluate the assistant's response in a medical context, considering medical accuracy, completeness, empathy, and avoidance of risky or overly confident advice.",
    ),
]

```

--------------------------------

### Instrument and Evaluate Google ADK Agent

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/integrations/frameworks/google-adk.mdx

Instrument your Google ADK agent using `instrument_google_adk()` to enable DeepEval tracing. Then, define an evaluation dataset and run evaluations using DeepEval metrics.

```python
import asyncio
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types
from deepeval.integrations.google_adk import instrument_google_adk
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.evaluate.configs import AsyncConfig
from deepeval.metrics import TaskCompletionMetric

instrument_google_adk()

agent = LlmAgent(model="gemini-2.0-flash", name="assistant", instruction="Be concise.")
runner = InMemoryRunner(agent=agent, app_name="deepeval-google-adk")

async def run_agent(prompt: str) -> str:
    session = await runner.session_service.create_session(app_name="deepeval-google-adk", user_id="demo-user")
    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    async for event in runner.run_async(user_id="demo-user", session_id=session.id, new_message=message):
        if event.is_final_response() and event.content:
            return "".join(part.text for part in event.content.parts if getattr(part, "text", None))
    return ""

# Goldens are the inputs you want to evaluate.
dataset = EvaluationDataset(goldens=[Golden(input="What is 7 multiplied by 8?")])

# `evals_iterator` loops through goldens and applies metrics.
for golden in dataset.evals_iterator(async_config=AsyncConfig(run_async=True), metrics=[TaskCompletionMetric()]):
    task = asyncio.create_task(run_agent(golden.input)) # Produces trace for evaluation
    dataset.evaluate(task)
```

--------------------------------

### Use Amazon Bedrock via Environment Variables

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/integrations/models/amazon-bedrock.mdx

Configure deepeval to use Amazon Bedrock models by setting USE_AWS_BEDROCK_MODEL to 1 and specifying the model name directly in metric initialization.

```python
from deepeval.metrics import AnswerRelevancyMetric

answer_relevancy = AnswerRelevancyMetric(
    model="anthropic.claude-3-opus-20240229-v1:0",
)
```

--------------------------------

### Configure Gemini via Command Line

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Set Gemini as the default provider for all DeepEval metrics using the command line. This command configures your deepeval environment to use Gemini models.

```APIDOC
## Configure Gemini via Command Line

### Description
Run the following command in your terminal to configure your deepeval environment to use Gemini models for all metrics.

### Command
```bash
deepEval set-gemini \
    --model-name=<model_name> \
    --google-api-key=<api_key>
```

### Parameters
#### Command Line Parameters
- **model-name** (string) - Required - The name of the Gemini model to use (e.g., "gemini-2.0-flash-001").
- **google-api-key** (string) - Required - Your Google API key for authentication.

### Notes
The CLI command above sets Gemini as the default provider for all metrics, unless overridden in Python code. To use a different default model provider, you must first unset Gemini:

```bash
deepEval unset-gemini
```
```

--------------------------------

### Python Unit Test for RAG System

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-rag-evaluation.mdx

Define RAG test cases and metrics using DeepEval for unit testing. This setup converts golden datasets into test cases and asserts them against defined metrics.

```python
from deepeval import assert_test
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.test_case import LLMTestCase
from deepeval.metrics import AnswerRelevancyMetric
...

dataset = EvaluationDataset(goldens=[...])
for goldens in dataset.goldens:
  dataset.add_test_case(...) # convert golden to test case

@pytest.mark.parametrize(
    "test_case",
    dataset.test_cases,
)
def test_rag(test_case: LLMTestCase):
    # metrics is the list of RAG metrics as shown in previous sections
    assert_test(test_case, metrics)
```

--------------------------------

### G-Eval Metric within DAG

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/blog/top-5-geval-use-cases.mdx

This example demonstrates how to integrate a G-Eval metric as a node within a DeepEval DAG. It first defines a G-Eval metric for persuasiveness and then uses it as a child node in a BinaryJudgementNode, which is part of a larger DeepAcyclicGraph. This approach allows for deterministic evaluation logic while leveraging G-Eval's flexibility for subjective criteria.

```python
from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics.dag import (
    DeepAcyclicGraph,
    TaskNode,
    BinaryJudgementNode,
    NonBinaryJudgementNode,
    VerdictNode,
)
from deepeval.metrics import DAGMetric, GEval

geval_metric = GEval(
    name="Persuasiveness",
    criteria="Determine how persuasive the `actual output` is to getting a user booking in a call.",
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
)

conciseness_node = BinaryJudgementNode(
    criteria="Does the actual output contain less than or equal to 4 sentences?",
    children=[
        VerdictNode(verdict=False, score=0),
        VerdictNode(verdict=True, child=geval_metric),
    ],
)

# create the DAG
dag = DeepAcyclicGraph(root_nodes=[conciseness_node])
metric = DagMetric(dag=dag)

# create test case
test_case = LLMTestCase(input="...", actual_output="...")

# measure
metric.measure(test_case)
```

--------------------------------

### Write First DeepEval Test Case

Source: https://github.com/confident-ai/deepeval/blob/main/README.md

This Python code demonstrates how to set up and run an end-to-end evaluation for an LLM application using DeepEval's GEval metric and LLMTestCase.

```python
import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

def test_case():
    correctness_metric = GEval(
        name="Correctness",
        criteria="Determine if the 'actual output' is correct based on the 'expected output'.",
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.EXPECTED_OUTPUT],
        threshold=0.5
    )
    test_case = LLMTestCase(
        input="What if these shoes don't fit?",
        # Replace this with the actual output from your LLM application
        actual_output="You have 30 days to get a full refund at no extra cost.",
        expected_output="We offer a 30-day full refund at no extra costs.",
        retrieval_context=["All customers are eligible for a 30 day full refund at no extra costs."]
    )
    assert_test(test_case, [correctness_metric])
```

--------------------------------

### Inherit BaseMetric Class

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-building-custom-metrics.mdx

Start by creating a class that inherits from deepeval's BaseMetric. This allows deepeval to recognize your custom metric.

```python
from deepeval.metrics import BaseMetric

class CustomMetric(BaseMetric):
    ...

```

--------------------------------

### Assert Test Case with `deepeval test run`

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Use `assert_test` within a test function to assert a test case against a list of metrics. This is typically used with Deepeval's Pytest integration for running evaluations.

```python
from deepeval import assert_test
...

def test_answer_relevancy():
    assert_test(test_case, [metric])

```

--------------------------------

### Configure Azure OpenAI for DeepEval

Source: https://github.com/confident-ai/deepeval/blob/main/docs/public/llms-full.txt

Configure DeepEval to use Azure OpenAI for all LLM-based metrics by running this command in the CLI. The model-version is optional.

```bash
deepeval set-azure-openai --openai-endpoint=<endpoint> \
    --openai-api-key=<api_key> \
    --deployment-name=<deployment_name> \
    --openai-api-version=<api_version> \
    --model-version=<model_version>
```

--------------------------------

### Evaluate Cognee RAG Pipeline with DeepEval

Source: https://github.com/confident-ai/deepeval/blob/main/docs/content/integrations/vector-databases/cognee.mdx

Run the evaluation of your RAG pipeline using DeepEval. Define an LLMTestCase with inputs, outputs, and retrieval contexts, then specify the metrics for evaluation.

```python
from deepeval.metrics import (
    ContextualRecallMetric,
    ContextualPrecisionMetric,
    ContextualRelevancyMetric,
)
from deepeval.test_case import LLMTestCase
from deepeval import evaluate

...
test_case = LLMTestCase(
    input=input,
    actual_output=actual_output,
    retrieval_context=retrieval_context,
    expected_output="Cognee is the Graph RAG Framework.",
)
evaluate(
    [test_case],
    metrics=[
        ContextualRecallMetric(),
        ContextualPrecisionMetric(),
        ContextualRelevancyMetric(),
    ],
)
```
