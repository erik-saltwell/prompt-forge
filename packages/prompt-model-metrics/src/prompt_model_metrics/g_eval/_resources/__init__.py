from __future__ import annotations

from functools import cache
from importlib.resources import files

from jinja2 import Template


@cache
def _load_template_source(name: str) -> str:
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid template name: {name!r}")
    resource_files = files(__package__)
    for extension in ("j2", "md"):
        resource = resource_files.joinpath(f"{name}.{extension}")
        if resource.is_file():
            return resource.read_text(encoding="utf-8")
    raise FileNotFoundError(f"No g_eval template found for {name!r}")


def render_template(name: str, **context: object) -> str:
    return Template(_load_template_source(name)).render(**context)


@cache
def load_resource(name: str) -> str:
    """Load a packaged g_eval resource by name (without `.md` extension)."""
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid resource name: {name!r}")
    return files(__package__).joinpath(f"{name}.md").read_text(encoding="utf-8")
