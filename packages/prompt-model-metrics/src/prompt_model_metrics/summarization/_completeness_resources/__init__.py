from __future__ import annotations

from functools import cache
from importlib.resources import files


@cache
def load_completeness_resource(name: str) -> str:
    """Load a packaged completeness-metric resource by name (without `.md` extension).

    Raises FileNotFoundError if the resource does not exist.
    """
    return (files(__package__) / f"{name}.md").read_text(encoding="utf-8")
