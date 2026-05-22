import pytest
from prompt_model import IssueSignal
from pydantic import ValidationError


def _signal(**overrides: object) -> IssueSignal:
    defaults: dict[str, object] = {
        "culprit_node_id": "1.2",
        "rationale": "the example contradicts the rule",
        "target_behavior": "examples match the stated tone",
        "success_criterion": "no example uses a casual register",
        "suggested_prompt_change": None,
        "input_snippet": "Tell me a joke.",
        "output_snippet": "Sure, here's one: ...",
        "seen_in_n_cases": 1,
    }
    defaults.update(overrides)
    return IssueSignal(**defaults)  # type: ignore[arg-type]


def test_defaults_construct() -> None:
    signal: IssueSignal = _signal()
    assert signal.seen_in_n_cases == 1
    assert signal.suggested_prompt_change is None


def test_blank_culprit_rejected() -> None:
    with pytest.raises(ValidationError):
        _signal(culprit_node_id="   ")


def test_blank_rationale_rejected() -> None:
    with pytest.raises(ValidationError):
        _signal(rationale="")


def test_blank_input_snippet_rejected() -> None:
    with pytest.raises(ValidationError):
        _signal(input_snippet="\t\n")


def test_seen_in_n_cases_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        _signal(seen_in_n_cases=0)


def test_suggested_prompt_change_blank_rejected() -> None:
    with pytest.raises(ValidationError):
        _signal(suggested_prompt_change="   ")


def test_suggested_prompt_change_optional() -> None:
    signal: IssueSignal = _signal(suggested_prompt_change="rephrase as imperative")
    assert signal.suggested_prompt_change == "rephrase as imperative"
