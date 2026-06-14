"""Dashboard runtime configuration.

Single source of truth is `~/.starling/starling.json` (0600, gitignored): it
holds the dashboard fields plus the dashboard bearer `token` and the `llm` /
`embedder` provider configs (incl. their api_key). The file is the persistent
secret store — it is NEVER committed to git, written to the SQLite memory DB,
or logged. `GET /api/config` never returns the token or full keys.
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

_SERIALIZABLE = (
    "db_path", "agent", "tenant", "token", "host", "port",
    "cors_origins", "llm", "embedder", "tick_interval_s",
    "vector_backend", "vector_store_path",
)


def _default_llm() -> dict:
    return {"provider": "openai", "model": "", "base_url": "", "api_key": ""}


def _default_embedder() -> dict:
    return {"provider": "openai", "model": "", "base_url": "", "api_key": "", "dim": 1024}


@dataclass
class DashboardConfig:
    db_path: str = ""
    agent: str = "self"
    tenant: str = "default"
    token: str = ""
    host: str = "127.0.0.1"
    port: int = 8787
    cors_origins: list[str] = field(default_factory=list)
    llm: dict = field(default_factory=_default_llm)
    embedder: dict = field(default_factory=_default_embedder)
    # P2.o 运行时闭环:后台维护 tick 间隔秒数(嵌入/巩固/投影/出箱收敛)。
    # 0 = 禁用(回到纯手动 tick)。
    tick_interval_s: float = 30.0
    # P3.b1 phase 5: 向量后端选型。sqlite(默认)=暴力 cosine + SQL scope,任意维、零额外
    # 依赖;zvec=HNSW(需 STARLING_VECTOR_ZVEC 构建的 _core,否则 MemoryCore 报错)。
    # vector_store_path 空 → 工厂用 ~/.starling/vectors。
    vector_backend: str = "sqlite"
    vector_store_path: str = ""
    config_path: str = ""  # not serialized; where load()/save() persist

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
        """Load defaults -> file -> env, then auto-generate+persist a token."""
        cfg = cls(db_path=str(_DEFAULT_DB))
        p = Path(path or os.environ.get("STARLING_CONFIG") or _DEFAULT_CONFIG).expanduser()
        cfg.config_path = str(p)
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            for k in _SERIALIZABLE:
                if k in data and data[k] is not None:
                    setattr(cfg, k, data[k])
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


def _env_overlay(cfg: DashboardConfig) -> None:
    """env > file for dashboard fields; seed llm from OPENAI_* when file empty."""
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
    if not cfg.llm.get("api_key") and e("OPENAI_API_KEY"):
        cfg.llm = {"provider": cfg.llm.get("provider", "openai"),
                   "model": e("OPENAI_MODEL", cfg.llm.get("model", "")),
                   "base_url": e("OPENAI_BASE_URL", cfg.llm.get("base_url", "")),
                   "api_key": e("OPENAI_API_KEY")}
