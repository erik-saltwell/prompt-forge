from __future__ import annotations

from importlib.resources import files


def load_rendering_resource(name: str) -> str:
    """Load a prompt rendering format description from this package."""
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid prompt rendering resource name: {name!r}")
    return files(__package__).joinpath(f"{name}.md").read_text(encoding="utf-8")
