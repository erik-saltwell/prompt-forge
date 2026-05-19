from ..._protocols.action import Action, ApplyContext, SkipReason
from .add_annotation import AddExampleAction, AddGuidanceAction
from .add_node import AddNodeAction
from .anchor import LocationAnchor, NodeRef, NodeTarget, parse_anchor
from .registry import parse_action, register
from .remove_annotation import RemoveExampleAction, RemoveGuidanceAction
from .remove_node import RemoveNodeAction
from .rewrite_node import RewriteNodeAction
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
    "AddNodeAction",
    "UpdateExampleAction",
    "UpdateGuidanceAction",
    "RemoveExampleAction",
    "RemoveGuidanceAction",
    "RemoveNodeAction",
    "RewriteNodeAction",
]
