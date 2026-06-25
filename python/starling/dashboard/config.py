"""Dashboard runtime configuration.

Single source of truth is `~/.starling/starling.json` (0600, gitignored): it
holds the dashboard fields plus the dashboard bearer `token` and a multi-model
provider registry. The file is the persistent secret store — it is NEVER
committed to git, written to the SQLite memory DB, or logged. `GET /api/config`
never returns the token or full keys.

Model config (Phase 2a) is a named-provider registry + per-job role bindings:

    providers: { "<name>": {provider, model, base_url, api_key, dim?} }
    roles:     { extraction|embedding|chat|consolidation: "<provider name>" }

`extraction` and `embedding` have live consumers today; `chat` gains one with
converse() (Phase 2c); `consolidation` is reserved (no LLM consumer yet). The
old single `{llm, embedder}` shape is auto-migrated on load (llm → provider
"default" bound to extraction; embedder → provider "embedder" bound to
embedding), so existing configs keep working with no manual edit.
"""
from __future__ import annotations

import json
import os
import secrets
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

_DEFAULT_DIR = Path.home() / ".starling"
_DEFAULT_CONFIG = _DEFAULT_DIR / "starling.json"
_DEFAULT_DB = _DEFAULT_DIR / "dashboard.db"

# Role keys. extraction/embedding are wired today; chat is consumed by
# converse() (2c); consolidation is reserved (replay uses no LLM yet).
ROLES = ("extraction", "embedding", "chat", "consolidation")

_SERIALIZABLE = (
    "db_path", "agent", "tenant", "token", "host", "port",
    "cors_origins", "providers", "roles", "tick_interval_s",
    "vector_backend", "vector_store_path",
)


@dataclass
class DashboardConfig:
    db_path: str = ""
    agent: str = "self"
    tenant: str = "default"
    token: str = ""
    host: str = "127.0.0.1"
    port: int = 8787
    cors_origins: list[str] = field(default_factory=list)
    # Named provider registry + role bindings (see module docstring).
    providers: dict = field(default_factory=dict)
    roles: dict = field(default_factory=dict)
    # P2.o 运行时闭环:后台维护 tick 间隔秒数(嵌入/巩固/投影/出箱收敛)。
    # 0 = 禁用(回到纯手动 tick)。
    tick_interval_s: float = 30.0
    # P3.b1 phase 5: 向量后端选型。sqlite(默认)=暴力 cosine + SQL scope。
    vector_backend: str = "sqlite"
    vector_store_path: str = ""
    config_path: str = ""  # not serialized; where load()/save() persist

    # ----- role → provider resolution -----
    def resolve_role(self, role: str) -> dict | None:
        """The provider config dict bound to `role`, or None when unbound /
        unconfigured. Callers treat None as 'no adapter for this job'."""
        name = self.roles.get(role)
        if not name:
            return None
        return self.providers.get(name)

    def extraction(self) -> dict | None:
        return self.resolve_role("extraction")

    def embedding(self) -> dict | None:
        return self.resolve_role("embedding")

    def chat(self) -> dict | None:
        # converse falls back to the extraction provider when chat is unbound.
        return self.resolve_role("chat") or self.resolve_role("extraction")

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
            tick_interval_s=float(os.environ.get("STARLING_DASH_TICK_INTERVAL", "30")),
        )

    @classmethod
    def load(cls, path: str | None = None) -> "DashboardConfig":
        """Load defaults -> file (+ legacy migration) -> env, then ensure token."""
        cfg = cls(db_path=str(_DEFAULT_DB))
        p = Path(path or os.environ.get("STARLING_CONFIG") or _DEFAULT_CONFIG).expanduser()
        cfg.config_path = str(p)
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            for k in _SERIALIZABLE:
                if k in data and data[k] is not None:
                    setattr(cfg, k, data[k])
            _migrate_legacy_model_config(cfg, data)
        _env_overlay(cfg)
        cfg.db_path = str(Path(cfg.db_path).expanduser())
        if not cfg.token:
            cfg.token = secrets.token_urlsafe(24)
            cfg.save()
        return cfg

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in _SERIALIZABLE}

    def save(self, path: str | None = None) -> None:
        p = Path(path or self.config_path or _DEFAULT_CONFIG).expanduser()
        p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".starling-", suffix=".tmp")
        try:
            os.chmod(fd, 0o600)  # set perms before any secret bytes are written
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
            os.replace(tmp, p)   # atomic replace; never leaves a partial file
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        self.config_path = str(p)

    def validate_bind(self) -> None:
        """Refuse to expose a tokenless service on a non-loopback interface."""
        if self.host not in ("127.0.0.1", "localhost", "::1") and not self.token:
            raise RuntimeError(
                "refusing to bind dashboard to non-loopback host without a token"
            )


def _migrate_legacy_model_config(cfg: DashboardConfig, data: dict) -> None:
    """Old `{llm, embedder}` files → providers/roles (one-way, on load).

    Only fires when the file predates the registry (no `providers`/`roles`
    keys). llm → provider "default" bound to extraction; embedder → provider
    "embedder" bound to embedding. Idempotent: re-saving persists the new shape,
    so this runs at most once per file.
    """
    if "providers" in data or "roles" in data:
        return
    legacy_llm = data.get("llm")
    legacy_emb = data.get("embedder")
    if legacy_llm and legacy_llm.get("api_key"):
        cfg.providers["default"] = dict(legacy_llm)
        cfg.roles["extraction"] = "default"
    if legacy_emb and legacy_emb.get("api_key"):
        cfg.providers["embedder"] = dict(legacy_emb)
        cfg.roles["embedding"] = "embedder"


def _env_overlay(cfg: DashboardConfig) -> None:
    """env > file for dashboard fields; seed an extraction provider from OPENAI_*
    when no extraction provider is configured (preserves the zero-config-file,
    OPENAI_API_KEY-only quickstart)."""
    e = os.environ.get
    if e("STARLING_DASH_DB"): cfg.db_path = e("STARLING_DASH_DB")
    if e("STARLING_DASH_AGENT"): cfg.agent = e("STARLING_DASH_AGENT")
    if e("STARLING_DASH_TENANT"): cfg.tenant = e("STARLING_DASH_TENANT")
    if e("STARLING_DASH_TOKEN"): cfg.token = e("STARLING_DASH_TOKEN")
    if e("STARLING_DASH_HOST"): cfg.host = e("STARLING_DASH_HOST")
    if e("STARLING_DASH_PORT"): cfg.port = int(e("STARLING_DASH_PORT"))
    if e("STARLING_DASH_TICK_INTERVAL"): cfg.tick_interval_s = float(e("STARLING_DASH_TICK_INTERVAL"))
    if e("STARLING_DASH_VECTOR_BACKEND"): cfg.vector_backend = e("STARLING_DASH_VECTOR_BACKEND")
    if e("STARLING_DASH_VECTOR_STORE_PATH"): cfg.vector_store_path = e("STARLING_DASH_VECTOR_STORE_PATH")
    if e("STARLING_DASH_CORS_ORIGINS"):
        cfg.cors_origins = [o.strip() for o in e("STARLING_DASH_CORS_ORIGINS").split(",") if o.strip()]
    if cfg.resolve_role("extraction") is None and e("OPENAI_API_KEY"):
        cfg.providers["default"] = {
            "provider": "openai",
            "model": e("OPENAI_MODEL", ""),
            "base_url": e("OPENAI_BASE_URL", ""),
            "api_key": e("OPENAI_API_KEY"),
        }
        cfg.roles["extraction"] = "default"
