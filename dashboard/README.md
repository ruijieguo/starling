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

## 离线样例与回归验证

先停止使用目标数据库的 dashboard，再执行样例脚本；推荐始终指定独立样例库：

```bash
mkdir -p build/dashboard-demo
.venv/bin/python scripts/seed_demo.py --db build/dashboard-demo/dashboard.db
```

脚本通过确定性 FakeLLM 和真实 C++ 写入、巩固、承诺及关系接口生成样例，不请求外部模型。人物样例显式提供 `subject_kind=cognizer`，发布计划与服务标注为 `entity`；缺失类型仍由核心安全默认为实体。验收包含八名具名人物、六条关系、五个承诺和两个 gist，契约回归位于 `tests/python/test_seed_demo.py`。

样例 dashboard 应使用独立配置、端口和 `ingest_spool_path`，不绑定真实模型；设置 `tick_interval_s=0` 可保留固定样例时刻的承诺状态。正常主服务继续使用原数据库。`--reset` 会删除指定的**整个数据库及 WAL/SHM 文件**，并非只清空某个租户。

设计与验收边界见 [样例契约修复设计](../docs/superpowers/specs/2026-09-27-dashboard-demo-contract-design.md)。浏览器验收必须确认样例内容和 API 返回，导航壳 smoke 不能替代数据检查。

日常回归和历史评测回放的执行方式见[测试说明](../tests/README.md)，本次完整验收及后续修复见[回归报告](../docs/eval/2026-09-27-python-regression-boundary.md)。

## 安全姿态
- **令牌配置**：由权限为 `0600` 的统一配置保存，也可用 `STARLING_DASH_TOKEN` 覆盖；不写入记忆数据库或提交到代码库。启动器会输出带令牌的本地登录链接，启动日志须按敏感文件保管，不直接分享；服务端用恒定时间比较。
- **绑定校验**：非 loopback host 且无 token 时拒绝启动（validate_bind）。
- **WebSocket Origin 校验（防 CSWSH）**：跨源浏览器连接被拒；非浏览器客户端（无 Origin）放行；配置 CORS_ORIGINS 后按白名单；dev 默认仅允 loopback 浏览器。
- **REST CORS**：配置 STARLING_DASH_CORS_ORIGINS 后启用白名单。
- 检视面板走只读 SQL（mode=ro），命令经引擎门面（单写者）。

## 会话摄入通道(dogfood 子项 A,spool 架构)

Claude Code 会话结束时自动把清洁对话喂进 starling 记忆(纯 host、复用 remember)。

**架构**:SessionEnd hook 只写一个 job 文件到 `~/.starling/ingest-spool/tenant-<url-encoded-tenant>/` 立即退出 → 对应租户的 dashboard worker 只扫描自己的分区、读 transcript、过滤(剥 thinking/工具/tool_result/代码围栏/超长行)、分块、逐块 `remember`(持 engine 锁串行化 facade 状态；LLM 网络阶段不持 SQLite 事务)→ statements 落库可 `/statements` 检视。

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
- spool 根：`~/.starling/ingest-spool/`；每租户分区 `tenant-<url-encoded-tenant>/` 内含 pending `*.json`、`done/`、`failed/`(死信 + `.error`)。worker 只 claim 当前配置租户的分区；崩溃残留 `*.processing` 由该分区 worker 启动时 reaper 收回。
- 失败:瞬态(LLM 黑洞)留 spool 有界重试(attempts<5),超限进 `failed/`;空抽取(无可记事实)= 正常成功进 `done/`。
- 卸载 hook:从 `~/.claude/settings.json` 删 `hooks.SessionEnd`(备份在 `settings.json.bak-*`)。
- `ingest_remember_ms_total` 是 worker 持 engine 锁执行完整 remember 的累计墙钟（含锁外数据库事务的 LLM 网络阶段）；SQLite 写事务只覆盖 prepare/commit，但其他 dashboard facade 调用仍会等待 engine 锁。
