from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from .protocol import Action, SkipReason


class _ActionFactory(Protocol):
    """Builds an Action from a raw JSON dict, or returns a SkipReason.

    Concrete action classes register a factory under their `type` string.
    The factory is responsible for the lenient-parameter rule: pull known
    fields, ignore extras, return SkipReason.MissingRequired when required
    fields are absent or malformed.
    """

    def __call__(self, raw: dict) -> Action | SkipReason: ...


_REGISTRY: dict[str, _ActionFactory] = {}


def register(type_name: str) -> Callable[[_ActionFactory], _ActionFactory]:
    """Decorator: register a factory for the given action `type` string."""

    def decorator(factory: _ActionFactory) -> _ActionFactory:
        if type_name in _REGISTRY:
            raise ValueError(f"action type already registered: {type_name}")
        _REGISTRY[type_name] = factory
        return factory

    return decorator


def parse_action(raw: dict) -> Action | SkipReason:
    """Resolve a raw JSON action dict to a concrete Action.

    Returns a SkipReason when the action cannot be constructed. The caller
    (the batch executor) records the reason and continues — actions are
    never raised as exceptions, per the skip-and-continue policy.
    """
    type_name = raw.get("type")
    if not isinstance(type_name, str):
        return SkipReason.MissingRequired
    factory = _REGISTRY.get(type_name)
    if factory is None:
        return SkipReason.UnknownType
    return factory(raw)
