# Starling Memory

**English** | [中文](README.zh-CN.md)

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

A web observability + interaction surface: a **FastAPI** engine-API fronted by a **SvelteKit + Tailwind** UI. Four panel bundles — **interaction** (remember / recall / working-set render / commitment reminders), **cognitive inspection** (statement explorer, cognizer social graph, commitment state machine), **dynamics & ops** (replay / reconsolidation, conflict probe, outbox & embedding queues), and an **overview + eval-report** landing page. Live updates stream over WebSocket; inspection panels read SQLite read-only, while commands run through the engine (with a UI-configurable LLM + embedder).

**Prerequisites:** the Python package installed (see [Build & test](#build--test)) plus Node ≥20 and npm (for the one-time frontend build).

**One-click run:**

```bash
source .venv/bin/activate
pip install -e ".[dashboard]"
python scripts/run_dashboard.py
```

That single command loads the unified config (`~/.starling/starling.json`, created on first run), generates a bearer token, builds the SvelteKit frontend if missing (needs Node; `--no-build` skips it), and serves the API + the static frontend on **one port**. It prints a login URL with the token in the URL **fragment**:

```
Dashboard ready → http://127.0.0.1:8787/#token=…
```

Open it — the frontend reads the token from the fragment (which browsers never send to the server, so it stays out of access logs) and stores it. **No second terminal, no env vars to memorize.**

**Configure the LLM in the UI:** the dashboard starts with no LLM configured; inspection panels, `recall`, `tick`, and working-set work immediately (offline embedder), while `remember` (statement extraction) returns 409 until you set one. Open **Settings** (`/settings`) and fill in the chat **LLM** and the **embedder** (model / base URL / API key). Changes are hot-swapped — no restart. Changing the embedder re-embeds existing memories (the vector dimension changes).

**Unified config — `~/.starling/starling.json` (0600):** one file holds everything — `db_path` (defaults to `~/.starling/dashboard.db`, auto-created), `agent`, `tenant`, `token` (auto-generated), `host`, `port`, `cors_origins`, and the `llm` / `embedder` provider configs (including their API keys). The file is gitignored and chmod-0600. Override its path with `STARLING_CONFIG` or `--config`; environment variables (`STARLING_DASH_*`, `OPENAI_*`) still override the file for CI / ephemeral use.

**Remote access:** bind a public interface (a token is always present, hence required), then share the printed `#token=` URL:

```bash
export STARLING_DASH_HOST=0.0.0.0
python scripts/run_dashboard.py
```

Put it behind a TLS reverse proxy. **Security:** all secrets live only in `starling.json` (0600, gitignored) plus process memory (a transient env-swap at adapter-build time) — they never enter git, the SQLite memory DB, or logs. `GET /api/config` returns only `key_set` booleans, never the token or full keys. The token travels in the URL fragment (never in access logs) and is compared in constant time. The SPA fallback has a path-traversal guard, the WebSocket endpoint enforces an Origin check (anti-CSWSH), and the static shell is public while every `/api` + `/ws` route is token-gated.

**Tests:** `pytest tests/python/test_dashboard_*.py` (config / engine / auth / inspection / commands / WebSocket, offline-deterministic); in `dashboard/web/`, `npx vitest run` (unit) and `npx playwright test` (e2e smoke).

> **Dev hot-reload:** for frontend iteration, run the backend (`python scripts/run_dashboard.py`) and, in a second terminal, `cd dashboard/web && npm run dev` (Vite on :5173, proxying `/api` + `/ws` to :8787).

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
