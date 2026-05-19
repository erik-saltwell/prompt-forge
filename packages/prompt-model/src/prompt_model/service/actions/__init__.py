from ..._protocols.action import Action, ApplyContext, SkipReason
from .add_annotation import AddExampleAction, AddGuidanceAction
from .anchor import LocationAnchor, NodeRef, NodeTarget, parse_anchor
from .registry import parse_action, register
from .remove_annotation import RemoveExampleAction, RemoveGuidanceAction
from .update_annotation import UpdateExampleAction, UpdateGuidanceAction

__all__ = [
    "Action",
    "ApplyContext",
    "SkipReason",
    "LocationAnchor",
    "NodeRef",
    "NodeTarget",
    "parse_anchor",
    "parse_action",
    "register",
    "AddExampleAction",
    "AddGuidanceAction",
    "UpdateExampleAction",
    "UpdateGuidanceAction",
    "RemoveExampleAction",
    "RemoveGuidanceAction",
]
