"""Tenant-safe filesystem layout for dashboard transcript ingestion jobs."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote


def tenant_spool_dir(root: Path, tenant: str) -> Path:
    """Return a non-traversable spool partition for one tenant."""
    if not tenant:
        raise ValueError("ingest spool tenant must not be empty")
    return root / f"tenant-{quote(tenant, safe='')}"
