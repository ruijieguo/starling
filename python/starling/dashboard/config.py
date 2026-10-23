"""Dashboard runtime configuration.

Single source of truth is `~/.starling/starling.json` (0600, gitignored): it
holds the dashboard fields plus the dashboard bearer `token` and a multi-model
provider registry. The file is the persistent secret store — it is NEVER
committed to git, written to the SQLite memory DB, or logged. `GET /api/config`
never returns the token or full keys.

Model config (Phase 2a) is a named-provider registry + per-job role bindings:

    providers: { "<name>": {provider, model, base_url, api_key, dim?, max_tokens?, timeout_ms?, max_retries?, enable_thinking?} }
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
_DEFAULT_INGEST_SPOOL = _DEFAULT_DIR / "ingest-spool"

# Role keys. extraction/embedding are wired today; chat is consumed by
# converse() (2c); consolidation is reserved (replay uses no LLM yet).
ROLES = ("extraction", "embedding", "chat", "consolidation")

_SERIALIZABLE = (
    "db_path", "agent", "tenant", "token", "host", "port",
    "cors_origins", "providers", "roles", "tick_interval_s",
    "vector_backend", "vector_store_path", "gist_thresholds", "ingest_spool_path",
    "source_lane_enabled", "source_lane_render_time", "source_lane_tau_source",
    "support_check_enabled",
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
    # Root directory only. DashboardEngine adds a tenant-specific partition.
    ingest_spool_path: str = ""
    # #38-C v2 threshold surface: NORM-gist tuning knobs. Empty keys → C++ defaults
    # (min_holders=3, min_replay_count=1, min_confidence=0.6). Threaded into
    # run_idle/run_sleep via MemoryCore.gist_thresholds.
    gist_thresholds: dict = field(default_factory=dict)
    # 形态 S 左脑来源 lane 的三个开关。**默认全关**：tau_source 未经标定前
    # 不得开启（spec §4.4 硬约束）。render_time 从属于 enabled——单独打开它
    # 没有意义（没有原文可渲染）。
    source_lane_enabled: bool = False
    source_lane_render_time: bool = False
    source_lane_tau_source: float = 0.0
    # 前提核验（support check）。默认关闭：关闭时不额外调用任何 LLM，对话提示
    # 逐字节不变。开启后每轮多一次 LLM 调用（判定「所问细节是否被直接陈述过」），
    # 判为未陈述时把本轮指令从「作答」改成「说明记忆里有什么、缺什么」。
    # 与 source_lane 独立：它作用于**作答层**，不改变检索。
    support_check_enabled: bool = False
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

    def resolve_provider(self, name: str | None) -> dict | None:
        """The provider config dict for a registry name, or None when the name is
        empty/absent. Distinct from resolve_role (which goes through a role binding):
        this powers per-turn model selection on the converse / interact pages, where
        the operator picks a registry provider directly for one request."""
        return self.providers.get(name) if name else None

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
            ingest_spool_path=os.environ.get(
                "STARLING_DASH_INGEST_SPOOL", str(_DEFAULT_INGEST_SPOOL)),
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
        if cfg.ingest_spool_path:
            cfg.ingest_spool_path = str(Path(cfg.ingest_spool_path).expanduser())
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

    def validate_source_lane(self) -> None:
        """左脑 lane 的开关一致性。

        ``tau_source`` 未经标定不得开启（spec §4.4 硬约束）——用一个拍脑袋的
        阈值上线，等于用一个没有依据的分界线决定"记不记得"。
        ``render_time`` 从属于 ``enabled``：没有原文可渲染时单独打开它没有意义。
        """
        if self.source_lane_enabled:
            if not (self.source_lane_tau_source > 0):
                raise RuntimeError(
                    "source_lane_enabled requires a calibrated "
                    "source_lane_tau_source (> 0)")
        elif self.source_lane_render_time:
            raise RuntimeError(
                "source_lane_render_time requires source_lane_enabled")

    def validate_bind(self) -> None:
        """Refuse to expose a tokenless service on a non-loopback interface."""
        if self.host not in ("127.0.0.1", "localhost", "::1") and not self.token:
            raise RuntimeError(
                "refusing to bind dashboard to non-loopback host without a token"
            )

    def ingest_spool_root(self) -> Path:
        configured = self.ingest_spool_path or os.environ.get(
            "STARLING_DASH_INGEST_SPOOL", str(_DEFAULT_INGEST_SPOOL))
        return Path(configured).expanduser()


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
    if e("STARLING_DASH_INGEST_SPOOL"): cfg.ingest_spool_path = e("STARLING_DASH_INGEST_SPOOL")
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
