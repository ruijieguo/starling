# Starling Dashboard (P2.g)

可视化观测面：FastAPI engine-API（引擎唯一属主）+ SvelteKit 前端。

## 本地跑

```bash
# 后端（终端 1）
source .venv/bin/activate
pip install -e ".[dashboard]"
export STARLING_DASH_DB=path/to/your.db
export STARLING_DASH_TOKEN=$(python -c "import secrets;print(secrets.token_urlsafe(24))")
export OPENAI_API_KEY=...    # 命令路由真引擎；离线演示可注入 stub Memory
python scripts/run_dashboard.py

# 前端（终端 2）
cd dashboard/web && npm install && npm run dev
# 打开 http://localhost:5173，在左下 Token 框填入 STARLING_DASH_TOKEN
```

## 远端访问

```bash
export STARLING_DASH_HOST=0.0.0.0       # 非 loopback 必须设 token，否则拒启
export STARLING_DASH_TOKEN=...          # 共享 bearer token（env-only）
export STARLING_DASH_CORS_ORIGINS=https://your-frontend.example
```
建议置于 TLS 反代之后。

## 安全姿态
- **令牌仅经环境变量注入**（STARLING_DASH_TOKEN），绝不入库/log/前端硬编码/提交；服务端用恒定时间比较。
- **绑定校验**：非 loopback host 且无 token 时拒绝启动（validate_bind）。
- **WebSocket Origin 校验（防 CSWSH）**：跨源浏览器连接被拒；非浏览器客户端（无 Origin）放行；配置 CORS_ORIGINS 后按白名单；dev 默认仅允 loopback 浏览器。
- **REST CORS**：配置 STARLING_DASH_CORS_ORIGINS 后启用白名单。
- 检视面板走只读 SQL（mode=ro），命令经引擎门面（单写者）。
