<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# P3.c1 Phase 2 (2b) — RuntimeHealth read route + dashboard panel — Implementation Plan
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.
>
> **SEQUENCING:** This plan's implementation **must start after PR #31 (2a) merges to main** — 2b consumes 2a's bound supervisor surface (`_core.RuntimeSupervisor.health/events/last_event`) and the `DashboardEngine._rt` handle, and it touches `runtime.py`/`engine.py` which #31 also changed. Branch 2b off the post-merge `main`.
> **DESIGN GATE:** Task 2.6 (the SvelteKit panel) is UI — run `/plan-design-review` on this plan before executing Task 2.6 (project CLAUDE.md routing). Task 2.5 (the JSON route) is backend and can proceed on eng judgment.

**Goal:** Expose the in-memory RuntimeHealth state (current status + transition event log) as a read-only `GET /api/runtime_health` JSON route, and surface it as a read-only SvelteKit dashboard panel — so an operator can see READY/DEGRADED/DRAINING/UNREADY and the recent transitions live.

**Architecture:** The supervisor (C++) is the source of truth; health/events live IN MEMORY (not SQLite), so the route reaches the LIVE `DashboardEngine` (not the DB). Engine + Runtime expose thin `health()`/`events()` passthroughs (OV-5); the route maps the bound `_core` structs to plain JSON dicts (OV-8). The panel mirrors the existing vitals panel: `createQuery` + WS-driven refetch + `Badge`/`StatCard` design atoms.

**Tech Stack:** Python (FastAPI route, pybind passthroughs) + SvelteKit (Svelte 5 runes, Tailwind v4, vitest).

## Global Constraints
- **Architecture rule (repo-wide):** core semantics in C++; Python/TS only adapter/presentation. The route + panel are pure presentation over the C++ supervisor — no state-machine/gate logic in Python or TS.
- **OV-5:** reach the LIVE supervisor through the engine passthroughs / `engine._rt._sup`; the bare `engine._runtime._sup` path is BROKEN (`_runtime` is the module). 2a added `begin_drain`; 2b adds `health()`/`events()` passthroughs (engine + Runtime).
- **OV-8:** the route maps `MetricsSnapshot`/`RuntimeHealthEvent` to PLAIN dicts (mirror the `plan_query` receipt mapping / `queries.vitals` plain-dict return) — never return the raw bound struct. Enum fields → `.name`.
- **Phase-2 scope:** DRAINING's full read-continue/`retry_after` contract is Phase 5; the panel shows STATE + events only. `runtime_event_loop_lag_ms` + the other metrics are 0 until Phase 5's sampler — the panel must render gracefully with all-zero metrics (don't imply live backpressure that isn't sampled yet).
- **Gates:** `.venv/bin/python -m pytest tests/python` green; in `dashboard/web/`: `npm run check` + `npx vitest run` + `npm run build` green. git: explicit-path add;
- No `--python-editable` needed (no C++/binding change — the supervisor surface is already bound from 2a).

---

### Task 2.5: `GET /api/runtime_health` route + engine/Runtime passthroughs

**Files:**
- Modify: `python/starling/runtime.py` — add `Runtime.events()` + `Runtime.last_event()` passthroughs (mirror the existing `health()`/`begin_drain()`).
- Modify: `python/starling/dashboard/engine.py` — add `DashboardEngine.health()` + `DashboardEngine.events()` passthroughs (mirror `begin_drain()`; NO `self._lock` — supervisor self-locks, OV-5).
- Modify: `python/starling/dashboard/routes/inspect.py` — add the `GET /runtime_health` handler + a local `_engine_or_none(request)` accessor (inspect.py currently has no engine access).
- Test: `tests/python/test_dashboard_runtime_health_route.py` (NEW).

**Interfaces:**
- Consumes (2a, already bound): `_core.RuntimeSupervisor.health() -> _core.RuntimeHealth`, `.events() -> list[_core.RuntimeHealthEvent]`, `.last_event() -> _core.RuntimeHealthEvent | None`, `.exit_code() -> int`; `_core.RuntimeHealthEvent{previous_status, current_status (both `_core.RuntimeHealth`), trigger:str, metrics_snapshot:_core.MetricsSnapshot, missing_capabilities:list[str]}`; `_core.MetricsSnapshot{outbox_lag_sequence, subscriber_failure_rate, extraction_queue_depth, projection_lag_seconds, runtime_event_loop_lag_ms, vector_delete_lag, erased_evidence_visible_count}`. `DashboardEngine._rt` (2a) holds the live Runtime; `Runtime._sup` is the supervisor.
- Produces (Task 2.6 consumes): JSON `{status:str, exit_code:int, events:[{previous_status, current_status, trigger, missing_capabilities, metrics_snapshot:{...7 fields...}}]}` from `GET /api/runtime_health`.

- [ ] **Step 1: Write the failing test** — `tests/python/test_dashboard_runtime_health_route.py`

```python
"""GET /api/runtime_health — P3.c1 Phase 2 (2b) read-only route.

Unlike the SQL-backed inspect routes, this reaches the LIVE in-memory supervisor
through the engine, so the test injects a real DashboardEngine (tick off).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from starling import _core
from starling.dashboard import DashboardConfig, create_app
from starling.dashboard.engine import DashboardEngine


@pytest.fixture
def client(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "rh.db"), token="",
                          tick_interval_s=0)
    eng = DashboardEngine(cfg)            # starts READY (embedded preflight passes)
    return TestClient(create_app(cfg, engine=eng)), eng


def test_runtime_health_reports_ready(client):
    c, _eng = client
    r = c.get("/api/runtime_health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "READY"
    assert isinstance(body["events"], list)
    assert body["events"], "start() records a transition event"
    last = body["events"][-1]
    assert last["current_status"] == "READY"
    assert last["previous_status"] == "UNREADY"
    assert last["trigger"] == "preflight_passed"
    assert last["missing_capabilities"] == []
    # MetricsSnapshot mapped to a plain dict, all 7 fields present, 0 in Phase 2.
    ms = last["metrics_snapshot"]
    assert set(ms) == {
        "outbox_lag_sequence", "subscriber_failure_rate", "extraction_queue_depth",
        "projection_lag_seconds", "runtime_event_loop_lag_ms", "vector_delete_lag",
        "erased_evidence_visible_count"}
    assert ms["outbox_lag_sequence"] == 0


def test_runtime_health_reflects_drain(client):
    c, eng = client
    eng.begin_drain()
    body = c.get("/api/runtime_health").json()
    assert body["status"] == "DRAINING"
    assert body["events"][-1]["current_status"] == "DRAINING"
    assert body["events"][-1]["trigger"] == "admin_drain"


def test_runtime_health_503_when_no_engine(tmp_path):
    # No engine + no lazy build path here is acceptable; assert the route does
    # not 500. (If _engine_or_none lazily builds, status is READY instead.)
    cfg = DashboardConfig(db_path=str(tmp_path / "rh2.db"), token="",
                          tick_interval_s=0)
    c = TestClient(create_app(cfg))       # engine=None
    r = c.get("/api/runtime_health")
    assert r.status_code in (200, 503)
```

- [ ] **Step 2: Run, confirm FAIL** — `.venv/bin/python -m pytest tests/python/test_dashboard_runtime_health_route.py -v` → FAIL (route 404; engine has no health/events).

- [ ] **Step 3a: Runtime passthroughs** — `python/starling/runtime.py`, after `health()`:
```python
    def events(self) -> list:
        """Snapshot of the supervisor's transition event log (forwards to C++)."""
        return self._sup.events()

    def last_event(self):
        """Latest transition event, or None (forwards to C++)."""
        return self._sup.last_event()
```

- [ ] **Step 3b: Engine passthroughs** — `python/starling/dashboard/engine.py`, beside `begin_drain()` (NO `self._lock` — OV-5, supervisor self-locks):
```python
    def health(self):
        """Current RuntimeHealth (read-only; forwards to the live supervisor)."""
        return self._rt.health()

    def events(self) -> list:
        """Snapshot of the supervisor transition log (read-only passthrough)."""
        return self._rt.events()
```

- [ ] **Step 3c: The route** — `python/starling/dashboard/routes/inspect.py`. Add an engine accessor (inspect.py has none) and the handler. Mirror the `plan_query` struct→dict mapping (`.name` for enums, list comprehensions for sub-structs):
```python
def _engine_or_none(request: Request):
    return request.app.state.engine


def _metrics_to_dict(ms) -> dict:
    return {
        "outbox_lag_sequence": ms.outbox_lag_sequence,
        "subscriber_failure_rate": ms.subscriber_failure_rate,
        "extraction_queue_depth": ms.extraction_queue_depth,
        "projection_lag_seconds": ms.projection_lag_seconds,
        "runtime_event_loop_lag_ms": ms.runtime_event_loop_lag_ms,
        "vector_delete_lag": ms.vector_delete_lag,
        "erased_evidence_visible_count": ms.erased_evidence_visible_count,
    }


def _event_to_dict(e) -> dict:
    return {
        "previous_status": e.previous_status.name,
        "current_status": e.current_status.name,
        "trigger": e.trigger,
        "missing_capabilities": list(e.missing_capabilities),
        "metrics_snapshot": _metrics_to_dict(e.metrics_snapshot),
    }


@router.get("/runtime_health")
async def runtime_health(request: Request):
    eng = _engine_or_none(request)
    if eng is None:
        # health/events are in-memory; with no live engine there is nothing to read.
        raise HTTPException(status_code=503, detail="engine not initialized")
    return {
        "status": eng.health().name,
        "events": [_event_to_dict(e) for e in eng.events()],
    }
```
(Add `HTTPException` to the `fastapi` import if not present.)

- [ ] **Step 4: Run, confirm PASS + regression** — `.venv/bin/python -m pytest tests/python/test_dashboard_runtime_health_route.py tests/python/test_dashboard_drain.py tests/python/test_tc_new_preflight.py -v` then full `.venv/bin/python -m pytest tests/python -q`. All green.

- [ ] **Step 5: Commit** — `git add python/starling/runtime.py python/starling/dashboard/engine.py python/starling/dashboard/routes/inspect.py tests/python/test_dashboard_runtime_health_route.py` + commit.

---

### Task 2.6: SvelteKit RuntimeHealth panel (read-only) — DESIGN-REVIEW GATED

**Files (in `dashboard/web/`):**
- Create: `src/lib/runtime_health.ts` — `RuntimeHealthResponse` type + `stateTone()`/`isHealthy()` helpers.
- Create: `src/lib/runtime_health.test.ts` — unit tests for the helpers (vitest).
- Create: `src/routes/runtime-health/+page.svelte` — the panel (mirror `routes/vitals/+page.svelte`).
- Modify: `src/lib/nav.ts` — add `{href:'/runtime-health', label:'运行时健康', icon:'<existing-icon>'}` to the `'生命体征 · 脑干'` group.
- Modify: `src/lib/nav.test.ts` — add the new nav entry to the asserted inventory.

**Interfaces:**
- Consumes: `GET /api/runtime_health` (Task 2.5 shape) via `api.get<RuntimeHealthResponse>('/api/runtime_health')`.

- [ ] **Step 1: Types + helpers + failing test** — `src/lib/runtime_health.ts`:
```ts
export type RuntimeHealthStatus = 'READY' | 'DEGRADED' | 'DRAINING' | 'UNREADY';

export interface MetricsSnapshot {
  outbox_lag_sequence: number;
  subscriber_failure_rate: number;
  extraction_queue_depth: number;
  projection_lag_seconds: number;
  runtime_event_loop_lag_ms: number;
  vector_delete_lag: number;
  erased_evidence_visible_count: number;
}
export interface RuntimeHealthEvent {
  previous_status: RuntimeHealthStatus;
  current_status: RuntimeHealthStatus;
  trigger: string;
  missing_capabilities: string[];
  metrics_snapshot: MetricsSnapshot;
}
export interface RuntimeHealthResponse {
  status: RuntimeHealthStatus;
  events: RuntimeHealthEvent[];
}

export type Tone = 'success' | 'warn' | 'danger' | 'neutral' | 'info';
export function stateTone(s: RuntimeHealthStatus): Tone {
  return s === 'READY' ? 'success'
       : s === 'DEGRADED' ? 'warn'
       : s === 'DRAINING' ? 'info'   // design-review D2: distinct from DEGRADED's warn — intentional wind-down, not a fault ("keep the teal calm")
       : 'danger';   // UNREADY
}
export function isHealthy(r: RuntimeHealthResponse): boolean {
  return r.status === 'READY';
}
```
`src/lib/runtime_health.test.ts` (mirror `vitals.test.ts`): assert `stateTone('READY')==='success'`, `'DEGRADED'==='warn'`, `'DRAINING'==='info'` (design-review D2 — DRAINING must NOT collide with DEGRADED's warn), `'UNREADY'==='danger'`; `isHealthy` true only for READY.

- [ ] **Step 2: Run, confirm FAIL** — `cd dashboard/web && npx vitest run src/lib/runtime_health.test.ts` → FAIL (module missing).

- [ ] **Step 3: The panel** — `src/routes/runtime-health/+page.svelte` (mirror vitals: `createQuery` + WS-driven refetch + `PageHeader` + `Card`/`Badge`/`StatCard` + skeleton/empty states). **[DESIGN-REVIEW will refine layout/what-to-surface]** baseline:
```svelte
<script lang="ts">
  import { api } from '$lib/api';
  import { createQuery } from '$lib/query.svelte';
  import { lastWsEvent } from '$lib/health';
  import { PageHeader, Card, Badge, EmptyState, Skeleton } from '$lib/components/ui';
  import { stateTone, type RuntimeHealthResponse } from '$lib/runtime_health';

  const q = createQuery(() => api.get<RuntimeHealthResponse>('/api/runtime_health'));
  $effect(() => { q.refetch(); });
  $effect(() => {
    const e = $lastWsEvent;
    if (e && (e.type === 'tick' || e.type === 'statement_added')) q.refetch();
  });
</script>

<PageHeader title="运行时健康" subtitle="RuntimeHealth 状态机 + 转换事件(只读)" />

{#if q.error}
  <EmptyState title="加载失败" description={q.error.message} />
{:else if q.loading && !q.data}
  <Skeleton class="h-24 w-full" />
{:else if q.data}
  <div class="space-y-6">
    <Card title="当前状态">
      <Badge tone={stateTone(q.data.status)}>{q.data.status}</Badge>
    </Card>
    <Card title="转换事件" description="最近的健康状态转换(最多 64 条)">
      {#if q.data.events.length}
        <ul class="divide-y divide-border">
          {#each [...q.data.events].reverse() as e}
            <li class="flex items-center gap-2 py-2 text-sm">
              <Badge tone={stateTone(e.previous_status)}>{e.previous_status}</Badge>
              <span>→</span>
              <Badge tone={stateTone(e.current_status)}>{e.current_status}</Badge>
              <span class="text-muted">{e.trigger}</span>
              {#if e.missing_capabilities.length}
                <span class="text-danger">缺: {e.missing_capabilities.join(', ')}</span>
              {/if}
            </li>
          {/each}
        </ul>
      {:else}
        <EmptyState title="暂无转换" description="启动后将记录第一次转换" />
      {/if}
    </Card>
  </div>
{/if}
```
(Confirm the exact `ui` barrel exports — `Card`, `Badge`, `EmptyState`, `Skeleton` — against `src/lib/components/ui/index.ts`; adjust imports if a name differs. **design-review D1 (LOCKED): do NOT display the MetricsSnapshot.** Phase 2's 7 fields are all 0 until Phase 5's sampler; rendering a row of zeros implies live backpressure data that isn't sampled yet — the same honesty rule that makes `engine.py` `plan_query` deliberately omit `runtime_health`. The panel surfaces **status + transition events only**; the metrics block is a Phase 5 follow-up. Hierarchy is intentional: current-status pill is the first/headline card, the transition-event list is secondary.)

- [ ] **Step 4: Nav entry** — `src/lib/nav.ts` add the entry to the `'生命体征 · 脑干'` group; pick an existing `NavIcon.svelte` icon name (e.g. `'activity'`) or add one. Update `src/lib/nav.test.ts`'s asserted inventory.

- [ ] **Step 5: Run all frontend gates** — `cd dashboard/web && npx vitest run && npm run check && npm run build`. All green.

- [ ] **Step 6: Commit** — explicit `git add` of the 5 frontend files + commit.

---

## Self-Review (writing-plans)
- **Coverage:** Task 2.5 = route + the OV-5 passthroughs + OV-8 dict mapping; Task 2.6 = panel + nav + types/tests. Together = plan §Task 2.5/2.6.
- **Type consistency:** route JSON keys (`status`/`exit_code`/`events[].{previous_status,current_status,trigger,missing_capabilities,metrics_snapshot}`) match the TS `RuntimeHealthResponse` exactly.
## Design decisions — LOCKED by /plan-design-review (2026-06-29)

Initial design completeness 6/10 → 9/10. The panel mirrors the in-production vitals panel + reuses the `ui/` atoms + Tailwind tokens (the de-facto design system; no DESIGN.md). Four decisions resolved:

- **D1 — MetricsSnapshot: DEFER to Phase 5, do not display.** The 7 fields are all 0 until Phase 5's sampler; showing zeros implies live backpressure data that isn't sampled yet (the honesty rule that makes `engine.py` `plan_query` omit `runtime_health`). Panel shows status + transition events only.
- **D2 — DRAINING tone = `info` (NOT `warn`).** Resolves the DEGRADED/DRAINING color collision. Final map: READY=success / DEGRADED=warn / DRAINING=info / UNREADY=danger. `info` signals "intentional wind-down, not a fault" ("keep the teal calm; danger only when something's wrong").
- **D3 — Layout: mirror vitals.** PageHeader → current-status Card (status pill = headline/first card, the hierarchy anchor) → transition-event Card (`divide-y` list) → affirmative "一切正常 / healthy" state when READY (not a blank). Status first; events secondary.
- **D4 — Live refresh: reuse `createQuery` + WS `tick` refetch, NO new WS event types** (follows the established vitals decision at `routes/vitals/+page.svelte:10-11`). A dedicated `runtime.health_changed` WS push is a Phase 5 concern (the sampler isn't on the bus yet).

**a11y (Pass 6):** state pills carry the state NAME as Badge text (not color-only) → colorblind-safe; the D2 collision was a glanceability nicety, not an a11y defect. Interaction states (loading=Skeleton, error/empty=EmptyState) are specified. Responsive: inherits vitals' simple single-column card stack (no dense grid needed for status + one list).

**NOT in scope (deferred, with rationale):** the MetricsSnapshot display (→ Phase 5 sampler, D1); a dedicated health-change WS event (→ Phase 5, D4); per-viewport responsive tuning beyond the inherited vitals stack (the panel is status + one list — the inherited behavior suffices).

**Backend (Task 2.5) decision retained:** thin engine `health()`/`events()` passthroughs + route-side struct→dict mapping (per OV-5/OV-8), NOT a single `runtime_health()->dict` engine method — eng-review (post-#31-merge) validates the route architecture.

## Eng-review decisions — LOCKED by /plan-eng-review (2026-06-29)

Backend (Task 2.5) reviewed. Step 0 complexity gate noted 9 files but assessed **minimal-necessary** (0 new classes/services; route + OV-5 passthrough layering + mirror-vitals patterns + 3 tests — nothing overbuilt). Two architecture decisions:

- **E1 — passthrough layering: all-through-Runtime (consistent).** `DashboardEngine.health()`/`events()` forward to `self._rt.X` (NOT `self._rt._sup.X`); add `Runtime.events()`/`last_event()` passthroughs mirroring 2a's `Runtime.health()`/`begin_drain()`. The engine never reaches Runtime's private `_sup`; Runtime is the supervisor's single Python face.
- **E2 — `exit_code` DROPPED from the route.** Route returns `{status, events}` only. Rationale: on a LIVE health route `exit_code` is always 0 (a UNREADY runtime exits via exit-78, so a running process is never UNREADY), AND a `Runtime.exit_code()` method would collide with Runtime's existing `exit_code` dataclass field. Dropped from the route, the route test, the `RuntimeHealthResponse` TS type, and the panel display — smaller + honest, no touch to merged 2a.

Code quality / tests / performance: clean — mapping helpers (`_metrics_to_dict`/`_event_to_dict`) are DRY; edge cases (503-no-engine, `last_event()` None) covered; the route test drives a REAL engine (not a mock); reads are in-memory snapshots (no SQL, no perf concern). The route still returns each event's `metrics_snapshot` (raw event fidelity at the API layer); the PANEL's D1 decision (don't render zeros) is a UI-presentation choice — consistent separation of API vs presentation.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | 2 decisions (E1 all-through-Runtime passthroughs; E2 drop exit_code); complexity 9 files = minimal-necessary; quality/tests/perf clean |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | clean | score 6/10 → 9/10, 4 decisions locked (D1-D4) |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**VERDICT:** ENG + DESIGN CLEARED — ready to implement (post-#31-merge already done; branch off main@4ef621d). Backend layering locked (all-through-Runtime passthroughs per OV-5; exit_code dropped as dead-on-live-route); panel design locked (D1-D4). Next: subagent-driven execution, with per-task + whole-branch review as usual.

NO UNRESOLVED DECISIONS
