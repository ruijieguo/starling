#!/usr/bin/env python3
"""Launch the Starling dashboard FastAPI engine-API.

Config from env (see DashboardConfig.from_env). Refuses to bind a non-loopback
host without STARLING_DASH_TOKEN. The SvelteKit frontend is built/served
separately (npm run dev / build); in dev it proxies /api and /ws here.
"""
from __future__ import annotations

import uvicorn

from starling.dashboard import DashboardConfig, create_app


def main() -> None:
    cfg = DashboardConfig.from_env()
    cfg.validate_bind()
    app = create_app(cfg)
    uvicorn.run(app, host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    main()
