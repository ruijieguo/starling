"""Dashboard runtime configuration (env-only secrets)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class DashboardConfig:
    db_path: str
    agent: str = "self"
    tenant: str = "default"
    token: str = ""                      # STARLING_DASH_TOKEN — never logged/persisted
    host: str = "127.0.0.1"
    port: int = 8787
    cors_origins: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "DashboardConfig":
        origins = os.environ.get("STARLING_DASH_CORS_ORIGINS", "")
        return cls(
            db_path=os.environ.get("STARLING_DASH_DB", "starling_dashboard.db"),
            agent=os.environ.get("STARLING_DASH_AGENT", "self"),
            tenant=os.environ.get("STARLING_DASH_TENANT", "default"),
            token=os.environ.get("STARLING_DASH_TOKEN", ""),
            host=os.environ.get("STARLING_DASH_HOST", "127.0.0.1"),
            port=int(os.environ.get("STARLING_DASH_PORT", "8787")),
            cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
        )

    def validate_bind(self) -> None:
        """Refuse to expose a tokenless service on a non-loopback interface."""
        if self.host not in ("127.0.0.1", "localhost", "::1") and not self.token:
            raise RuntimeError(
                "refusing to bind dashboard to non-loopback host without "
                "STARLING_DASH_TOKEN set"
            )
