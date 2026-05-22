from collections.abc import Awaitable, Callable

from pydantic import BaseModel, Field, PositiveInt

from ._utils import pydantic_aliases as alias


class RunProgress(BaseModel):
    """Progress through optimizer runs.

    A run is one full pass through the critic-actor-improve loop. The public
    optimizer normally reports one run per configured iteration, using
    one-based counters so callers can render the values directly.
    """

    total_runs: PositiveInt = Field(
        description="Total number of optimizer runs expected for this call.",
    )
    current_run: PositiveInt = Field(
        description="One-based index of the run currently being executed.",
    )


class StepProgress(BaseModel):
    """Progress through the named steps inside the current run.

    Steps are coarse-grained optimizer phases such as evaluating a candidate
    pool, aggregating metric results, or asking the actor to produce prompt
    edits. Step ids are one-based and scoped to the current run.
    """

    current_step_name: alias.StrippedNonBlankStr = Field(
        description="Human-readable name of the step currently running.",
    )
    current_step_id: PositiveInt = Field(
        description="One-based index of the current step within the run.",
    )
    total_steps: PositiveInt = Field(
        description="Total number of coarse-grained steps expected in each run.",
    )


class TaskProgress(BaseModel):
    """Progress through fine-grained work units inside the current step.

    Tasks make long-running steps streamable. For example, a batch-evaluation
    step can report each pull or case as a task while remaining under the same
    step. Task ids are one-based and scoped to the current step.
    """

    current_task_name: alias.StrippedNonBlankStr = Field(
        description="Human-readable name of the fine-grained task currently running.",
    )
    current_task_id: PositiveInt = Field(
        description="One-based index of the current task within the step.",
    )
    total_tasks: PositiveInt = Field(
        description="Total number of fine-grained tasks expected in the current step.",
    )


class ProgressEvent(BaseModel):
    """In-flight progress event emitted by the optimizer.

    Progress is reported as one stable event shape containing three nested
    scopes:

    - Run: one full critic-actor-improve pass.
    - Step: one coarse optimizer phase inside that run, such as batch testing,
      metric aggregation, or prompt improvement.
    - Task: one fine-grained unit inside a long-running step, allowing callers
      to render responsive progress without knowing optimizer internals.

    The optional score and error fields are snapshots of the optimizer's
    current aggregate state at the moment the event is emitted. They may be
    absent before the first candidate has been scored or before any comparable
    previous score exists.
    """

    run_progress: RunProgress = Field(
        description="Progress through the optimizer's outer run loop.",
    )
    step_progress: StepProgress = Field(
        description="Progress through the coarse phase currently running.",
    )
    task_progress: TaskProgress = Field(
        description="Progress through the fine-grained task currently running.",
    )

    best_score: float | None = Field(
        default=None,
        description="Current best aggregated reward across the candidate pool, if known.",
    )
    best_score_delta: float | None = Field(
        default=None,
        description="Change in best_score since the previous comparable emission, if known.",
    )
    errors_so_far: int | None = Field(
        default=None,
        description="Count of non-fatal failures observed so far, if tracked.",
    )


type ProgressReporter = Callable[[ProgressEvent], Awaitable[None]] | None
