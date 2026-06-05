# Starling Memory

**Agent memory with a multi-subject social mind and brain-inspired dynamics.**

Starling gives an LLM agent something a vector store can't: a persistent, evolving model of *each* person it talks to — a picture of the other, what the agent believes about them, and what the agent thinks *they* believe — together with brain-like memory dynamics: fast write / slow consolidation, priority replay, reconsolidation (without overwrite), adaptive forgetting, salience modulation, and prospective triggers.

It is **not** `user_id` isolation plus vector-RAG. It's a three-part system — a data model, a runtime scheduler, and a retrieval planner — that can sit on top of mem0 / Letta / cognee / Graphiti rather than replace them.

C++20 core, raw SQLite, with Python (`pybind11`) bindings.

---

## Why it's different

Seven things mainstream agent-memory stacks collectively lack:

1. **Cognizer is a first-class entity**, not a `user_id` column. Memory is attributed to cognitive subjects.
2. **Statement replaces Fact.** Every write is *"who, when, on what evidence, about whom, with what modality and polarity, holds what judgment."*
3. **Second-order Theory of Mind in the data model** — nested Statements + `nesting_depth` + adaptive ToM order ("I believe that you believe…").
4. **A brain-like six-state lifecycle** — `consolidation_state ∈ {VOLATILE, REPLAYING_CONSOLIDATING, REPLAYING_RECONSOLIDATING, CONSOLIDATED, ARCHIVED, FORGOTTEN}`.
5. **Reconsolidation never overwrites.** Recalling a memory opens a plastic window; the old version enters a `supersedes` chain instead of being deleted.
6. **Real prospection** — typed Triggers (time / event / state / compound) + a Commitment five-state machine that wakes the agent without a user query.
7. **Perspective-aware retrieval + mind summaries** — retrieval is reconstructed per `(querier, perspective, intent, goal)` with explicit abstention, not a fan-out of tools.

**Non-goals:** it does not rewrite the vector store, do training, or chase formal completeness.

## Three axioms

- **I — No isolated facts, only statements attributed to a subject.** Every memory is `Statement(holder, subject, predicate, object, modality, polarity, time, evidence, confidence)`. One shape solves attribution, conflict, retraction, perspective, and second-order ToM.
- **II — Two timescales cooperate (Complementary Learning Systems).** Writes land in the Hippocampus (`VOLATILE`), then pass through Replay, pattern separation/completion, and reconsolidation before rising into Neocortex as stable semantics / norms / skills / personas.
- **III — Memory is reconstructed for the current goal, not replayed like a tape (Conway SMS).** Retrieval returns a perspective-shaped mind summary, with the option to abstain.

## Architecture

A Statement Bus is the spine — every read and write goes through it. Around it sit twelve subsystems (full design in [`docs/design/`](docs/design/)):

| Subsystem | Responsibility |
|---|---|
| **Substrate** (`04`) | SQLite persistence, capability/preflight, Projection Index |
| **Statement Bus** (`05`) | Outbox-backed event bus; all reads/writes pass through it |
| **Governance** (`05`) | RuntimeHealth (READY/DEGRADED/UNREADY), preflight gate |
| **EngramStore** (`06`) | Evidence storage + ingest policy |
| **Hippocampus** (`06`) | VOLATILE buffer, pattern separation, Affect Buffer |
| **Neocortex** (`07`) | Persona / CommonGround containers (materialized, CAS-versioned) |
| **Cognizer Hub** (`08`) | Subject registry, alias normalization, social-graph edges |
| **Theory of Mind** (`09`) | Mentalizing primitives, nested beliefs, common ground |
| **Replay Scheduler** (`10`) | Forgetting curve, SWR priority sampling, 5 consolidation ops |
| **Reconsolidation** (`11`) | Plastic windows, arbitration, supersedes chains |
| **Prospective Loop** (`12`) | Commitment state machine, typed Triggers, ActionGuard |
| **Retrieval** (`13`) | Perspective filter, semantic recall, context-pack builder |

## Tech stack

C++20 · raw SQLite (≥3.46) · libcurl · nlohmann/json · OpenSSL · pybind11 · Python ≥3.11 · CMake (≥3.27) + Ninja · ctest + pytest.

**Dashboard (optional):** FastAPI · uvicorn · SvelteKit (Svelte 5) · Tailwind · TypeScript (Node ≥20). See [Dashboard](#dashboard).

## Build & test

**Prerequisites:** a C++20 compiler, CMake ≥3.27, Ninja, SQLite ≥3.46, OpenSSL, libcurl, and Python ≥3.11. (`nlohmann/json` is auto-fetched if not found.) On macOS/Homebrew: `brew install cmake ninja sqlite openssl@3 curl`.

**How the build system works:** [scikit-build-core](https://scikit-build-core.readthedocs.io/) is the Python build backend (declared in `pyproject.toml`). It drives a CMake + Ninja build that compiles the C++ core and the `pybind11` extension module `starling._core` (CMake flag `-DSTARLING_BUILD_PYTHON=ON`). The SQL files under `migrations/` are embedded into the core at build time, so the schema travels with the binary — there is no separate migration step at runtime. `pip install -e ".[dev]"` produces an *editable* install whose import hook can auto-rebuild the extension; the C++ targets can also be built directly with CMake (below) for `ctest`.

**C++ core + tests:**

```bash
cmake -S . -B build -G Ninja
cmake --build build
ctest --test-dir build
```

**Python bindings + tests:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # scikit-build compiles the _core extension
pytest tests/python
```

> Note: after changing C++ sources, migrations, or bindings, refresh the editable extension with `cmake --build build && cmake --install build --prefix .venv/lib/python<ver>/site-packages` before re-running pytest — `pip install -e .` alone can leave a stale `_core.so` due to scikit-build glob caching.

The Python surface is the bound C++ core: `from starling import _core`, with the application-facing `starling.Memory` facade on top (`open` / `remember` / `recall` / `tick` / `render_working_set` / `close`). See [`tests/python/`](tests/python/) and [`examples/`](examples/) for runnable examples of writing statements, retrieval, replay, reconsolidation, and the commitment lifecycle.

## Dashboard

A web observability + interaction surface (milestone P2.g): a **FastAPI** engine-API that owns a single `starling.Memory` instance (the sole writer), fronted by a **SvelteKit + Tailwind** UI. Four panel bundles — **interaction** (remember / recall / working-set render / commitment reminders), **cognitive inspection** (statement explorer, cognizer social graph, commitment state machine), **dynamics & ops** (replay / reconsolidation, conflict probe, outbox & embedding queues), and an **overview + eval-report** landing page. Live updates stream over WebSocket; commands run through the `starling.Memory` facade, while inspection panels read SQLite read-only.

**Prerequisites:** the Python package installed (see [Build & test](#build--test)) plus Node ≥20 and npm for the frontend.

**Run it locally** (two terminals):

```bash
# Terminal 1 — backend engine-API (FastAPI, defaults to 127.0.0.1:8787)
source .venv/bin/activate
pip install -e ".[dashboard]"                          # fastapi + uvicorn + httpx
export STARLING_DASH_DB=path/to/your.db                # the SQLite memory store to observe
export STARLING_DASH_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(24))")
export OPENAI_API_KEY=...                               # only needed for command routes (real engine)
python scripts/run_dashboard.py

# Terminal 2 — frontend dev server (Vite on :5173, proxies /api and /ws to :8787)
cd dashboard/web && npm install && npm run dev
# open http://localhost:5173 and paste STARLING_DASH_TOKEN into the Token box (bottom-left)
```

**Remote access:** to serve beyond loopback, bind a public interface — a token is then mandatory (the server refuses to start on a non-loopback host without `STARLING_DASH_TOKEN`):

```bash
export STARLING_DASH_HOST=0.0.0.0
export STARLING_DASH_TOKEN=...                                   # shared bearer token (env-only)
export STARLING_DASH_CORS_ORIGINS=https://your-frontend.example  # REST CORS allowlist
```

Put it behind a TLS reverse proxy. **All config is env-only:** `STARLING_DASH_DB`, `STARLING_DASH_AGENT` (default `self`), `STARLING_DASH_TENANT` (default `default`), `STARLING_DASH_TOKEN`, `STARLING_DASH_HOST` (default `127.0.0.1`), `STARLING_DASH_PORT` (default `8787`), `STARLING_DASH_CORS_ORIGINS`.

**Security:** the token is env-only (never persisted, logged, hardcoded in the frontend, or committed) and compared in constant time; non-loopback binds without a token are refused; the WebSocket endpoint enforces an Origin check (anti-CSWSH); inspection is read-only SQL and commands go only through the engine facade. Full notes: [`dashboard/README.md`](dashboard/README.md).

**Tests:** `pytest tests/python/test_dashboard_*.py` (API / auth / inspection / WebSocket, offline-deterministic); in `dashboard/web/`, `npx vitest run` (unit) and `npx playwright test` (e2e smoke).

## Repository layout

```
include/    C++ public headers (starling/...)
src/        C++ implementation (bus, evidence, extractor, cognizer, tom,
            replay, reconsolidation, neocortex, projection, vector,
            embedding, retrieval, prospective, affect, persistence)
bindings/   pybind11 module
python/     Python package (starling) — incl. the Memory facade and the
            dashboard FastAPI api (python/starling/dashboard)
migrations/ SQL schema migrations (embedded into the core at build time)
scripts/    Python tooling — eval harnesses + run_dashboard.py launcher
dashboard/  Dashboard frontend (dashboard/web, SvelteKit) + run docs
tests/      ctest (tests/cpp) + pytest (tests/python)
docs/       system design (docs/design) + specs & plans (docs/superpowers)
```

## Documentation

The authoritative design lives in [`docs/design/system_design.md`](docs/design/system_design.md) (main document: axioms, topology, data ontology, roadmap, trade-offs) plus twelve subsystem documents in [`docs/design/subsystems_design/`](docs/design/subsystems_design/). Per-milestone specs and implementation plans are under [`docs/superpowers/`](docs/superpowers/).

## License

A license has not yet been chosen. Until one is added, all rights are reserved by the authors.

---

## 中文简介

**Starling Memory —— 多主体社会心智 + 类脑动力学的智能体记忆系统。**

它给 LLM Agent 的不是向量库能给的东西:对每个交互对象形成一份「持续演化的他者画像 + 我对他的信念 + 我以为他相信什么」,并在系统层具备类脑的「快写慢洗、优先重放、再巩固(不覆盖)、自适应遗忘、显著性调制、前瞻触发」动力学。它不是 `user_id` 隔离 + 向量 RAG,而是**数据模型 + 运行时调度 + 检索规划器**三件套,可挂在 mem0 / Letta / cognee / Graphiti 之上。

**七大差异**:① Cognizer 一等公民(非 user_id);② Statement 替代 Fact(谁、何时、基于何证据、对谁、以何样态/极性、持有何判断);③ 二阶 ToM 数据模型(嵌套 Statement + nesting_depth);④ 类脑六态状态机(consolidation_state);⑤ Reconsolidation 不覆盖(supersedes 链);⑥ 真前瞻(类型化 Trigger + Commitment 五态机);⑦ 视角化检索 + 心智摘要。

**三条公理**:① 没有孤立的事实,只有归属于主体的陈述;② 两套时间尺度协同(CLS):写入先入 Hippocampus(VOLATILE),经 Replay / 模式分离补全 / 再巩固才上升到 Neocortex;③ 记忆为当前目标重构,不是录像回放,且可显式弃答。

完整设计见 [`docs/design/system_design.md`](docs/design/system_design.md) 与 [`docs/design/subsystems_design/`](docs/design/subsystems_design/)。构建与测试见上文 **Build & test**(scikit-build-core 驱动 CMake + Ninja 编译 `pybind11` 扩展 `starling._core`,`migrations/` 在编译期内嵌)。

**可视化 Dashboard(P2.g)**:FastAPI engine-API(持有唯一 `starling.Memory` 写者)+ SvelteKit 前端的 Web 观测/交互面——四面板(交互 / 认知检视 / 动力学·运维 / 总览·Eval)+ WebSocket 实时,支持远端访问与 token 鉴权。两个终端起:后端 `pip install -e ".[dashboard]"` 后 `python scripts/run_dashboard.py`,前端 `cd dashboard/web && npm install && npm run dev`(打开 http://localhost:5173 填 token)。详见上文 **[Dashboard](#dashboard)** 一节或 [`dashboard/README.md`](dashboard/README.md)。
