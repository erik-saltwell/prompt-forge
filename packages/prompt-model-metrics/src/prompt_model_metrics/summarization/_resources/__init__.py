from __future__ import annotations

from functools import cache
from importlib.resources import files

from jinja2 import Template


@cache
def load_prompt_resource(name: str) -> str:
    """Load a summarization prompt resource by name, without the `.md` suffix."""
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid prompt resource name: {name!r}")
    return files(__package__).joinpath(f"{name}.md").read_text(encoding="utf-8")


load_rendering_resource = load_prompt_resource


def render_prompt_resource(name: str, **context: object) -> str:
    return Template(load_prompt_resource(name)).render(**context)
