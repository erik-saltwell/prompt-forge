"""Verify doc_from_shorthand: determinism + shorthand round-trip via tree_to_shorthand."""

from __future__ import annotations

import pytest

from .utils.parsing_utils import (
    assert_trees_structurally_equal,
    doc_from_shorthand,
    tree_to_shorthand,
)


@pytest.mark.parametrize(
    "shorthand",
    [
        "p",
        "p p",
        "h1",
        "h1 p",
        "h1 p h2 p h2 ul1 ul1 p",
        "h1 ul1 ul2 ul2 ul1",
        "h1 ul1 ol2 ol2 ul1",
        "h1 ul1 ol2 ul3 ol4 ul3",
        "h1 p e g",
        "h1 ul1 e ul1 g ul1",
        "cb bq t",
        "h1 p h2 p h3 p h2 p",
        "ul1 ul1 ul1",
    ],
)
def test_deterministic(shorthand: str) -> None:
    a = doc_from_shorthand(shorthand)
    b = doc_from_shorthand(shorthand)
    assert_trees_structurally_equal(a, b)


@pytest.mark.parametrize(
    "shorthand",
    [
        "p",
        "p p",
        "h1 p",
        "h1 p h2 p h2 ul1 ul1 p",
        "h1 ul1 ul2 ul2 ul1",
        "h1 ul1 ol2 ol2 ul1",
        "h1 ul1 ol2 ul3 ol4 ul3",
        "h1 p e g",
        "h1 ul1 e ul1 g ul1",
        "cb bq t",
        "h1 p h2 p h3 p h2 p",
        "ul1 ul1 ul1",
    ],
)
def test_round_trip_through_shorthand(shorthand: str) -> None:
    assert tree_to_shorthand(doc_from_shorthand(shorthand)) == shorthand


def test_rejects_unknown_token() -> None:
    with pytest.raises(ValueError, match="unknown shorthand token"):
        doc_from_shorthand("h1 xyz")


def test_rejects_depth_skip() -> None:
    with pytest.raises(ValueError, match="skipped a list-depth level"):
        doc_from_shorthand("h1 ul2")


def test_rejects_annotation_with_no_host() -> None:
    with pytest.raises(ValueError, match="no host"):
        doc_from_shorthand("h1 e")
