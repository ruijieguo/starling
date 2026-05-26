"""
starling.cognizer — public API for 08_cognizer subsystem.

Wraps pybind11 bindings from starling._core and provides
higher-level builders and convenience helpers.
"""
from starling._core import (
    CognizerKind,
    FiskeMode,
    Cognizer,
    RelationEdge,
    CognizerHub,
    KnowledgeFrontier,
    AliasCollision,
    FiskeWeightsInvalid,
    GroupTenantImplicit,
    CognizerNotFound,
)
from starling.cognizer.builders import (
    for_human,
    for_agent,
    for_group,
    for_role,
    for_external,
    for_self,
)

__all__ = [
    "CognizerKind",
    "FiskeMode",
    "Cognizer",
    "RelationEdge",
    "CognizerHub",
    "KnowledgeFrontier",
    "AliasCollision",
    "FiskeWeightsInvalid",
    "GroupTenantImplicit",
    "CognizerNotFound",
    "for_human",
    "for_agent",
    "for_group",
    "for_role",
    "for_external",
    "for_self",
]
