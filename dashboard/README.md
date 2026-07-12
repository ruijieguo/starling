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

## 会话摄入通道(dogfood 子项 A,spool 架构)

Claude Code 会话结束时自动把清洁对话喂进 starling 记忆(纯 host、复用 remember)。

**架构**:SessionEnd hook 只写一个 job 文件到 `~/.starling/ingest-spool/` 立即退出 → dashboard 进程内后台 worker 扫 spool、读 transcript、过滤(剥 thinking/工具/tool_result/代码围栏/超长行)、分块、逐块 `remember`(持 engine 锁=尊重单写者;重限流)→ statements 落库可 `/statements` 检视。

**装 hook**(`~/.claude/settings.json`,全局):
```json
{ "hooks": { "SessionEnd": [ { "hooks": [
  { "type": "command",
    "command": ".venv/bin/python <repo>/scripts/ingest_session.py",
    "timeout": 30 } ] } ] } }
```
hook 近零工作(只写 job 文件),永不阻塞会话退出;dashboard 不在跑也不丢(job 文件持久,下次跑 worker 补消化)。

**历史 bootstrap 起量**:`.venv/bin/python scripts/ingest_session.py --bootstrap ~/.claude/projects/**/*.jsonl`

**运维**:
- 状态:`GET /api/ingest_status` → `{pending, processing, done, failed, ingest_remember_ms_total}`。
- spool:`~/.starling/ingest-spool/`(pending `*.json`)、`done/`、`failed/`(死信 + `.error`);崩溃残留 `*.processing` 由 worker 启动时 reaper 收回。
- 失败:瞬态(LLM 黑洞)留 spool 有界重试(attempts<5),超限进 `failed/`;空抽取(无可记事实)= 正常成功进 `done/`。
- 卸载 hook:从 `~/.claude/settings.json` 删 `hooks.SessionEnd`(备份在 `settings.json.bak-*`)。
- `ingest_remember_ms_total` 是 worker 持锁跑 extraction 的累计墙钟——摄入期间 dashboard 会等这把锁(实测一块 ~54s),此值是「extraction 出锁」优化(方案 2)是否该做的证据。
