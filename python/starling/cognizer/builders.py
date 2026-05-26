"""
Convenience builder functions for CognizerHub.register_cognizer.

Each builder maps to one CognizerKind and sets canonical defaults.
Call them to build keyword-argument dicts, then pass to hub.register_cognizer().

Usage:
    hub.register_cognizer(**for_human("alice", canonical_name="Alice Smith"))
    hub.register_cognizer(**for_group("team-a", tenant_id="acme", canonical_name="Team A"))
"""
from __future__ import annotations
from typing import Sequence


def for_human(
    external_id: str,
    *,
    canonical_name: str,
    tenant_id: str = "default",
    aliases: Sequence[str] = (),
) -> dict:
    """Build kwargs for a human cognizer. tenant_id defaults to 'default'."""
    return dict(
        kind="human",
        external_id=external_id,
        canonical_name=canonical_name,
        tenant_id=tenant_id,
        aliases=list(aliases),
        tenant_explicitly_set=False,
    )


def for_agent(
    external_id: str,
    *,
    canonical_name: str,
    tenant_id: str = "default",
    aliases: Sequence[str] = (),
) -> dict:
    """Build kwargs for an AI agent cognizer."""
    return dict(
        kind="agent",
        external_id=external_id,
        canonical_name=canonical_name,
        tenant_id=tenant_id,
        aliases=list(aliases),
        tenant_explicitly_set=False,
    )


def for_group(
    external_id: str,
    *,
    canonical_name: str,
    tenant_id: str,
    aliases: Sequence[str] = (),
) -> dict:
    """
    Build kwargs for a group cognizer.

    tenant_id is mandatory and keyword-only; omitting it is a TypeError at
    call time (Python layer) rather than GroupTenantImplicit (C++ layer).
    The dict sets tenant_explicitly_set=True so CognizerHub accepts it.
    """
    return dict(
        kind="group",
        external_id=external_id,
        canonical_name=canonical_name,
        tenant_id=tenant_id,
        aliases=list(aliases),
        tenant_explicitly_set=True,
    )


def for_role(
    external_id: str,
    *,
    canonical_name: str,
    tenant_id: str = "default",
    aliases: Sequence[str] = (),
) -> dict:
    """Build kwargs for a role cognizer (e.g. 'manager', 'moderator')."""
    return dict(
        kind="role",
        external_id=external_id,
        canonical_name=canonical_name,
        tenant_id=tenant_id,
        aliases=list(aliases),
        tenant_explicitly_set=False,
    )


def for_external(
    external_id: str,
    *,
    canonical_name: str,
    tenant_id: str = "default",
    aliases: Sequence[str] = (),
) -> dict:
    """Build kwargs for an external system or service cognizer."""
    return dict(
        kind="external",
        external_id=external_id,
        canonical_name=canonical_name,
        tenant_id=tenant_id,
        aliases=list(aliases),
        tenant_explicitly_set=False,
    )


def for_self(
    external_id: str = "starling_system",
    *,
    canonical_name: str = "Starling",
    tenant_id: str = "default",
) -> dict:
    """
    Build kwargs for the system-self cognizer (kind='self').

    There should be exactly one self-cognizer per tenant. external_id and
    canonical_name have sensible defaults matching RuntimeConfig.self_cognizer_id.
    """
    return dict(
        kind="self",
        external_id=external_id,
        canonical_name=canonical_name,
        tenant_id=tenant_id,
        aliases=[],
        tenant_explicitly_set=False,
    )
