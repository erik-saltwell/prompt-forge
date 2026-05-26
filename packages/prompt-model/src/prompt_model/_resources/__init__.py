from __future__ import annotations

from functools import cache
from importlib.resources import files


@cache
def load_prompt(name: str) -> str:
    """Load a packaged actor prompt by name (without `.md` extension).

    Raises FileNotFoundError if the resource does not exist.
    """
    return (files(__package__) / f"{name}.md").read_text(encoding="utf-8")
