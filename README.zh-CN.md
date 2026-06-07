# Starling Memory

[English](README.md) | **中文**

**多主体社会心智 + 类脑动力学的智能体记忆系统。**

Starling 给 LLM Agent 的是向量库给不了的东西:对它交谈的*每一个*对象,形成一份持续演化的模型——他者的画像、Agent 对他的信念、以及 Agent 以为*他*相信什么——并配以类脑的记忆动力学:快写 / 慢巩固、优先重放、再巩固(不覆盖)、自适应遗忘、显著性调制、前瞻触发。

它**不是** `user_id` 隔离 + 向量 RAG。它是三件套——数据模型、运行时调度器、检索规划器——可以**挂在** mem0 / Letta / cognee / Graphiti **之上**,而非取代它们。

C++20 核心、raw SQLite,配 Python(`pybind11`)绑定。

---

## 为何不同

主流智能体记忆栈集体缺失的七件事:

1. **Cognizer 是一等实体**,而非 `user_id` 列。记忆归属于认知主体。
2. **Statement 替代 Fact。** 每次写入都是*「谁、何时、基于何证据、对谁、以何样态与极性、持有何判断」*。
3. **数据模型内建二阶心智理论(ToM)**——嵌套 Statement + `nesting_depth` + 自适应 ToM 阶数(「我相信你相信……」)。
4. **类脑六态生命周期**——`consolidation_state ∈ {VOLATILE, REPLAYING_CONSOLIDATING, REPLAYING_RECONSOLIDATING, CONSOLIDATED, ARCHIVED, FORGOTTEN}`。
5. **Reconsolidation 绝不覆盖。** 召回一条记忆会打开一个可塑窗口;旧版本进入 `supersedes` 链,而非被删除。
6. **真正的前瞻**——类型化 Trigger(time / event / state / compound)+ Commitment 五态机,无需用户提问即可唤醒 Agent。
7. **视角化检索 + 心智摘要**——检索按 `(querier, perspective, intent, goal)` 重构,带显式弃答,而非一堆工具的扇出。

**非目标:** 它不重写向量库、不做训练、不追求形式化完备。

## 三条公理

- **I —— 没有孤立的事实,只有归属于主体的陈述。** 每条记忆都是 `Statement(holder, subject, predicate, object, modality, polarity, time, evidence, confidence)`。一种形状同时解决归属、冲突、撤销、视角与二阶 ToM。
- **II —— 两套时间尺度协同(互补学习系统 CLS)。** 写入先落入 Hippocampus(`VOLATILE`),再经 Replay、模式分离/补全、再巩固,才上升进 Neocortex 成为稳定的语义 / 规范 / 技能 / 人格。
- **III —— 记忆为当前目标重构,不是录像回放(Conway SMS)。** 检索返回一份视角塑形的心智摘要,并可显式弃答。

## 架构

Statement Bus 是脊柱——每次读写都经过它。其周围环绕十二个子系统(完整设计见 [`docs/design/`](docs/design/)):

| 子系统 | 职责 |
|---|---|
| **Substrate**(`04`) | SQLite 持久化、capability/preflight、Projection Index |
| **Statement Bus**(`05`) | Outbox 支撑的事件总线;所有读写都过它 |
| **Governance**(`05`) | RuntimeHealth(READY/DEGRADED/UNREADY)、preflight 门 |
| **EngramStore**(`06`) | 证据存储 + 摄取策略 |
| **Hippocampus**(`06`) | VOLATILE 缓冲、模式分离、Affect Buffer |
| **Neocortex**(`07`) | Persona / CommonGround 容器(物化、CAS 版本化) |
| **Cognizer Hub**(`08`) | 主体注册、别名归一、社会图边 |
| **Theory of Mind**(`09`) | 心智化原语、嵌套信念、共同基础 |
| **Replay Scheduler**(`10`) | 遗忘曲线、SWR 优先采样、5 个巩固算子 |
| **Reconsolidation**(`11`) | 可塑窗口、仲裁、supersedes 链 |
| **Prospective Loop**(`12`) | Commitment 状态机、类型化 Trigger、ActionGuard |
| **Retrieval**(`13`) | 视角过滤、语义召回、上下文包构建 |

## 技术栈

C++20 · raw SQLite(≥3.46)· libcurl · nlohmann/json · OpenSSL · pybind11 · Python ≥3.11 · CMake(≥3.27)+ Ninja · ctest + pytest。

**Dashboard(可选):** FastAPI · uvicorn · SvelteKit(Svelte 5)· Tailwind · TypeScript(Node ≥20)。见 [Dashboard](#dashboard)。

## 构建与测试

推荐从仓库根目录运行:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements-build.txt
python scripts/configure_build.py --build --test
```

`python scripts/configure_build.py --build --test` 会先 configure,再 build 并运行 C++ 测试。这个脚本优先复用本机依赖: `.venv`、当前 conda 环境、conda package cache、Homebrew、系统包、以及已有的 `build/_deps` 源码。只有本机找不到 nlohmann/json 或 GoogleTest 时,才交给 CMake `FetchContent` 尝试联网兜底。

直接使用 CMake:

```bash
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
```

Python editable 安装:

```bash
python scripts/configure_build.py --python-editable
```

改了 C++ 源码、`migrations/` 或绑定之后,重建 C++ 构建目录:

```bash
cmake --build build-linux   # Linux 默认目录
cmake --build build-macos   # macOS 默认目录
```

**前置**

- **Python ≥3.11** —— `python3 --version` 查看。
- **C++20 编译器 + git。** macOS:`xcode-select --install`(装上 Apple Clang + git)。Linux:`sudo apt install build-essential git`。
- C++ 核心链接 **SQLite、OpenSSL、libcurl、ICU**,并使用 **nlohmann/json** 与 **GoogleTest** 跑 C++ 测试。Linux 若偏好系统包,安装开发头文件:`sudo apt install libsqlite3-dev libssl-dev libcurl4-openssl-dev libicu-dev`。

到此即可。`from starling import _core`(已绑定的 C++ 核心)与 `starling.Memory` 门面都能用了;`python examples/quickstart.py` 跑一个离线端到端示例。

**排障**

- 旧 `build/` 污染: 换用 `build-linux`、`build-macos` 或另一个新目录。
- SQLite: 需要 SQLite >= 3.46。
- Linux ICU: 安装 `libicu-dev`,或手动传 ICU CMake 变量。
- 离线 FetchContent: 复用已有下载,或传 `-DFETCHCONTENT_SOURCE_DIR_JSON=...` 和 `-DFETCHCONTENT_SOURCE_DIR_GOOGLETEST=...`。
- conda linker wrapper: 避免复用带 `compiler_compat` 的 CMake cache。
- conda libstdc++ 冲突: 不要把整个 `~/miniconda3/lib` 加进 rpath。

**原理:** `scripts/configure_build.py` 使用明确的本机依赖 hints 驱动 CMake + Ninja 构建;Python editable 安装仍由 `pyproject.toml` 声明的 scikit-build-core 构建后端负责。`migrations/*.sql` 在编译期内嵌进二进制,故 schema 随核心走——运行时没有单独的 migration 步骤。

Python 面向的是被绑定的 C++ 核心:`from starling import _core`,其上是面向应用的 `starling.Memory` 门面(`open` / `remember` / `recall` / `tick` / `render_working_set` / `close`)。可运行示例(写入 Statement、检索、Replay、Reconsolidation、Commitment 生命周期)见 [`tests/python/`](tests/python/) 与 [`examples/`](examples/)。

## Dashboard

一个 Web 观测 + 交互面:**FastAPI** engine-API,前面是 **SvelteKit + Tailwind** UI。四个面板 bundle——**交互**(remember / recall / Working Set 渲染 / 承诺提醒)、**认知检视**(statement explorer、cognizer 社会图、commitment 状态机)、**动力学 · 运维**(replay / reconsolidation、conflict probe、outbox 与 embedding 队列),以及一个**总览 + Eval 报告**落地页。实时更新经 WebSocket 推送;检视面板只读 SQLite,命令则经引擎(LLM + embedder 可在 UI 配置)。

**前置:** 已安装 Python 包(见 [构建与测试](#构建与测试))+ Node ≥20 与 npm(用于一次性前端构建)。

**一键启动:**

```bash
source .venv/bin/activate
pip install -e ".[dashboard]"
python scripts/run_dashboard.py
```

这一条命令会载入统一配置(`~/.starling/starling.json`,首次运行自动创建)、生成一个 bearer token、若前端构建缺失则构建它(需要 Node;`--no-build` 跳过),并在**同一个端口**上 serve API + 静态前端。它会打印一个把 token 放在 URL **片段**里的登录链接:

```
Dashboard ready → http://127.0.0.1:8787/#token=…
```

打开它——前端从片段读取 token(浏览器**绝不**把片段发往服务器,故它不会进 access log)并存下来。**无需第二个终端、无需记一堆环境变量。**

**在 UI 里配置 LLM:** dashboard 启动时未配 LLM;检视面板、`recall`、`tick`、Working Set 立即可用(走离线 embedder),而 `remember`(抽取 Statement)在你配置之前返回 409。打开**设置页**(`/settings`)填入对话 **LLM** 与 **embedder**(model / base URL / API key)。改动会**热切换**——无需重启。改 embedder 会重嵌已有记忆(向量维度变化)。

**统一配置 —— `~/.starling/starling.json`(0600):** 一个文件收纳一切——`db_path`(默认 `~/.starling/dashboard.db`,自动建库)、`agent`、`tenant`、`token`(自动生成)、`host`、`port`、`cors_origins`,以及 `llm` / `embedder` 的 provider 配置(含其 API key)。该文件 gitignored 且 chmod 0600。用 `STARLING_CONFIG` 或 `--config` 覆盖其路径;环境变量(`STARLING_DASH_*`、`OPENAI_*`)仍会覆盖文件,供 CI / 临时使用。

**远端访问:** 绑定一个公网接口(token 始终存在,因此是必需的),再把打印出的 `#token=` URL 分享出去:

```bash
export STARLING_DASH_HOST=0.0.0.0
python scripts/run_dashboard.py
```

建议置于 TLS 反向代理之后。**安全:** 所有密钥只存在于 `starling.json`(0600,gitignored)+ 进程内存(建 adapter 时的瞬时 env-swap)——它们绝不进 git、不进 SQLite 记忆库、不进 log。`GET /api/config` 只返回 `key_set` 布尔,绝不返回 token 或完整 key。token 经 URL 片段传递(绝不进 access log)且用恒定时间比较。SPA 兜底带路径穿越守护,WebSocket 端点强制 Origin 校验(防 CSWSH),静态壳公开而每个 `/api` + `/ws` 路由都受 token 守护。

**测试:** `pytest tests/python/test_dashboard_*.py`(config / engine / auth / inspection / commands / WebSocket,离线确定性);在 `dashboard/web/` 下 `npx vitest run`(单测)与 `npx playwright test`(e2e smoke)。

> **开发热重载:** 前端迭代时,起后端(`python scripts/run_dashboard.py`),再在第二个终端 `cd dashboard/web && npm run dev`(Vite 在 :5173,把 `/api` + `/ws` 反代到 :8787)。

## 仓库布局

```
include/    C++ 公共头文件 (starling/...)
src/        C++ 实现 (bus, evidence, extractor, cognizer, tom,
            replay, reconsolidation, neocortex, projection, vector,
            embedding, retrieval, prospective, affect, persistence)
bindings/   pybind11 模块
python/     Python 包 (starling) —— 含 Memory 门面与
            dashboard FastAPI api (python/starling/dashboard)
migrations/ SQL schema 迁移 (编译期内嵌进核心)
scripts/    Python 工具 —— eval harness + run_dashboard.py 启动器
dashboard/  Dashboard 前端 (dashboard/web, SvelteKit) + 运行文档
tests/      ctest (tests/cpp) + pytest (tests/python)
docs/       系统设计 (docs/design) + specs 与 plans (docs/superpowers)
```

## 文档

权威设计在 [`docs/design/system_design.md`](docs/design/system_design.md)(主文档:公理、拓扑、数据本体、roadmap、权衡),外加 [`docs/design/subsystems_design/`](docs/design/subsystems_design/) 下十二个子系统文档。各里程碑的 spec 与实施计划在 [`docs/superpowers/`](docs/superpowers/)。

## 许可证

尚未选定许可证。在添加许可证之前,作者保留所有权利。
