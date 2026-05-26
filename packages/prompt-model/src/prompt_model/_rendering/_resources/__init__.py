from __future__ import annotations

from functools import cache
from importlib.resources import files


@cache
def load_rendering_resource(kind: str, name: str) -> str:
    """Load a packaged rendering snippet by kind and name.

    `kind` is one of `"prompt_format"` or `"signal_format"`. `name` is the
    bundled `.md` filename without extension (e.g. `"xml"`, `"default"`).
    """
    return (files(__package__) / kind / f"{name}.md").read_text(encoding="utf-8")
