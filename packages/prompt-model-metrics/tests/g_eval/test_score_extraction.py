from __future__ import annotations

import math

import pytest
from prompt_model_metrics.g_eval._metric import _extract_weighted_score


class _Entry:
    """Mimics LiteLLM's logprob-content entry shape."""

    def __init__(self, token: str, logprob: float, top: list[_TopEntry] | None = None) -> None:
        self.token: str = token
        self.logprob: float = logprob
        self.top_logprobs: list[_TopEntry] = top or []


class _TopEntry:
    def __init__(self, token: str, logprob: float) -> None:
        self.token: str = token
        self.logprob: float = logprob


class _Logprobs:
    def __init__(self, content: list[_Entry]) -> None:
        self.content: list[_Entry] = content


class _Choice:
    def __init__(self, logprobs: _Logprobs | None) -> None:
        self.logprobs: _Logprobs | None = logprobs


class _Response:
    def __init__(self, choices: list[_Choice]) -> None:
        self.choices: list[_Choice] = choices


def _build_response(score_top: list[tuple[str, float]]) -> _Response:
    """Build a fake response with `{"score": <digit>` token stream and given top-k at the score token."""
    top: list[_TopEntry] = [_TopEntry(t, math.log(p)) for t, p in score_top]
    score_entry: _Entry = _Entry("4", math.log(0.7), top=top)
    content: list[_Entry] = [
        _Entry('{"', 0.0),
        _Entry("score", 0.0),
        _Entry('":', 0.0),
        _Entry(" ", 0.0),
        score_entry,
    ]
    return _Response([_Choice(_Logprobs(content))])


def test_no_logprobs_returns_none() -> None:
    response = _Response([_Choice(logprobs=None)])
    assert _extract_weighted_score(response) is None


def test_pure_numeric_distribution_weighted_correctly() -> None:
    response: _Response = _build_response([("4", 0.7), ("5", 0.2), ("3", 0.1)])
    weighted: float | None = _extract_weighted_score(response)
    assert weighted is not None
    # All mass numeric → renormalized weighted sum
    assert weighted == pytest.approx(4 * 0.7 + 5 * 0.2 + 3 * 0.1, rel=1e-6)


def test_renormalizes_across_numeric_tokens() -> None:
    response: _Response = _build_response([("4", 0.5), ("5", 0.3), ("foo", 0.2)])
    weighted: float | None = _extract_weighted_score(response)
    assert weighted is not None
    numeric_mass: float = 0.8
    expected: float = (4 * 0.5 + 5 * 0.3) / numeric_mass
    assert weighted == pytest.approx(expected, rel=1e-6)


def test_low_numeric_mass_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    response: _Response = _build_response([("4", 0.2), ("foo", 0.7), ("bar", 0.1)])
    with caplog.at_level("WARNING"):
        _extract_weighted_score(response)
    assert any("numeric" in r.getMessage() for r in caplog.records)


def test_no_numeric_mass_returns_none() -> None:
    response: _Response = _build_response([("foo", 0.5), ("bar", 0.5)])
    assert _extract_weighted_score(response) is None


def test_score_token_with_whitespace_prefix() -> None:
    response: _Response = _build_response([(" 4", 0.6), (" 5", 0.4)])
    weighted: float | None = _extract_weighted_score(response)
    assert weighted is not None
    assert weighted == pytest.approx(4 * 0.6 + 5 * 0.4, rel=1e-6)
