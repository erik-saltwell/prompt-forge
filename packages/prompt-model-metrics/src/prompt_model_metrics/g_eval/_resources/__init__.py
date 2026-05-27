from __future__ import annotations

from functools import cache
from importlib.resources import files

from jinja2 import Template


@cache
def _load_template_source(name: str) -> str:
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid template name: {name!r}")
    return files(__package__).joinpath(f"{name}.j2").read_text(encoding="utf-8")


def render_template(name: str, **context: object) -> str:
    return Template(_load_template_source(name)).render(**context)
