from __future__ import annotations

from typing import Final

ANNOTATION_NAMES: Final[frozenset[str]] = frozenset({"example", "examples", "guidance"})


def annotation_name(token: object) -> str | None:
    type_ = getattr(token, "type", "")
    if not type_.startswith("container_"):
        return None
    if type_.endswith("_open"):
        name = type_[len("container_") : -len("_open")]
    elif type_.endswith("_close"):
        name = type_[len("container_") : -len("_close")]
    else:
        return None
    return name if name in ANNOTATION_NAMES else None


def annotation_kind(token: object) -> str | None:
    """Canonical kind — collapses example/examples to 'examples'."""
    name = annotation_name(token)
    if name in ("example", "examples"):
        return "examples"
    if name == "guidance":
        return "guidance"
    return None


def is_annotation_open(token: object) -> bool:
    return annotation_name(token) is not None and getattr(token, "nesting", 0) == 1


def is_annotation_close(token: object) -> bool:
    return annotation_name(token) is not None and getattr(token, "nesting", 0) == -1


def find_matching_close(tokens: list, open_index: int) -> int:
    level = tokens[open_index].level
    for i in range(open_index + 1, len(tokens)):
        if tokens[i].level == level and tokens[i].nesting == -1:
            return i
    return -1


def find_matching_open(tokens: list, close_index: int) -> int:
    level = tokens[close_index].level
    for i in range(close_index - 1, -1, -1):
        if tokens[i].level == level and tokens[i].nesting == 1:
            return i
    return -1


def find_preceding_sibling_end(tokens: list, start_index: int) -> int:
    """Index of the most recent sibling-block-ending token at the same level
    as tokens[start_index]. Sibling-ending = nesting -1 (matched close) or
    nesting 0 (singleton block like fence/hr/html_block). Returns -1 if none."""
    level = tokens[start_index].level
    for i in range(start_index - 1, -1, -1):
        t = tokens[i]
        if t.level < level:
            return -1
        if t.level == level:
            if t.nesting in (-1, 0):
                return i
            return -1
    return -1


def sibling_block_type(token: object) -> str:
    nesting = getattr(token, "nesting", 0)
    type_ = getattr(token, "type", "")
    if nesting == 0:
        return type_
    if type_.endswith("_close"):
        return type_[: -len("_close")]
    if type_.endswith("_open"):
        return type_[: -len("_open")]
    return type_


def find_preceding_non_annotation_sibling_end(tokens: list, open_index: int) -> int:
    """Walks back at the same nesting level, skipping past annotation-container
    siblings, to find the end of the nearest non-annotation preceding sibling.
    Returns its index, or -1 if no such sibling exists."""
    cursor = open_index
    while True:
        end_i = find_preceding_sibling_end(tokens, cursor)
        if end_i == -1:
            return -1
        end_token = tokens[end_i]
        if end_token.nesting == -1 and annotation_name(end_token) is not None:
            open_i = find_matching_open(tokens, end_i)
            if open_i == -1:
                return -1
            cursor = open_i
            continue
        return end_i


def open_line(token: object) -> int:
    map_ = getattr(token, "map", None)
    if not map_:
        return 0
    return map_[0] + 1
