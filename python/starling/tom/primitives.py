"""
starling.tom.primitives — Pythonic wrappers around the bound C++ ToM free functions.

These wrappers normalise call signatures for Python callers:
  - as_of defaults to now (UTC)
  - as_of accepts any timezone-aware datetime; naive datetimes raise ValueError
  - modality accepts None (maps to empty string = no filter)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from starling import _core


def _iso_now_or_convert(as_of: Optional[datetime]) -> str:
    """Return ISO-8601 UTC string from as_of, defaulting to now."""
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        raise ValueError("as_of must be a timezone-aware datetime (naive datetimes are not allowed)")
    return as_of.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def what_does_X_believe(
    adapter,
    *,
    x: str,
    about_y: str,
    tenant_id: str = "default",
    as_of: Optional[datetime] = None,
    modality: Optional[str] = None,
):
    """
    Return all statements held by cognizer X about subject Y.

    Parameters
    ----------
    adapter     : SqliteAdapter
    x           : cognizer id of the querying perspective holder
    about_y     : subject id to filter on (subject_kind = 'cognizer')
    tenant_id   : tenant scope (default: 'default')
    as_of       : time anchor; defaults to now (UTC).  Must be tz-aware.
    modality    : optional modality string filter (e.g. 'BELIEVES', 'KNOWS');
                  None means no modality filter.

    Returns
    -------
    list[StatementRow]
    """
    as_of_iso = _iso_now_or_convert(as_of)
    return _core.what_does_X_believe(
        adapter, x, about_y, tenant_id, as_of_iso, modality or ""
    )


def does_X_know(
    adapter,
    frontier,
    *,
    x: str,
    fact: "_core.FactKey",
    tenant_id: str = "default",
    as_of: Optional[datetime] = None,
):
    """
    Tri-valued knowledge query for cognizer X about a specific fact.

    Parameters
    ----------
    adapter     : SqliteAdapter
    frontier    : KnowledgeFrontier
    x           : cognizer id
    fact        : FactKey describing the fact to check
    tenant_id   : tenant scope
    as_of       : time anchor; defaults to now (UTC).  Must be tz-aware.

    Returns
    -------
    KnowsResult  (FullKnowledge | NotKnown | Unknowable)
    """
    as_of_iso = _iso_now_or_convert(as_of)
    return _core.does_X_know(adapter, frontier, x, fact, tenant_id, as_of_iso)


def find_misalignment(
    adapter,
    *,
    x: str,
    y: str,
    subject_kind: str,
    subject_id: str,
    tenant_id: str = "default",
    as_of: Optional[datetime] = None,
):
    """
    Find belief misalignments between cognizers X and Y about a given subject.

    Parameters
    ----------
    adapter      : SqliteAdapter
    x            : cognizer id for the first perspective
    y            : cognizer id for the second perspective
    subject_kind : e.g. 'cognizer', 'entity'
    subject_id   : subject being compared
    tenant_id    : tenant scope
    as_of        : time anchor; defaults to now (UTC).  Must be tz-aware.

    Returns
    -------
    Misalignment  with fields: only_x_believes, only_y_believes, confidence_diverges
    """
    as_of_iso = _iso_now_or_convert(as_of)
    return _core.find_misalignment(
        adapter, x, y, subject_kind, subject_id, tenant_id, as_of_iso
    )


def shared_with(
    adapter,
    *,
    members: list[str],
    tenant_id: str = "default",
    as_of: Optional[datetime] = None,
):
    """
    Return facts believed by ALL members in the given list.

    Parameters
    ----------
    adapter   : SqliteAdapter
    members   : list of cognizer ids
    tenant_id : tenant scope
    as_of     : time anchor; defaults to now (UTC).  Must be tz-aware.

    Returns
    -------
    list[SharedFact]
    """
    as_of_iso = _iso_now_or_convert(as_of)
    return _core.shared_with(adapter, members, tenant_id, as_of_iso)
