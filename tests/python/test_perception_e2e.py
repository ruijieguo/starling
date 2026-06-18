"""sub-project B phase 1 Task 1.4: Sally-Anne 错误信念确定性 e2e。

stub LLM 对每次调用都返回固定的 3 事件 JSON 数组,驱动 remember → A(EpisodicExtractor
写 3 条 OCCURRED + episodic_events)→ B(PerceptionReconstructor 重建 perception_state)。
belief/会话抽取那条管线拿到同一段事件 JSON 抽不出信念语句(graceful 空集),
episodic 那条抽出 3 个事件。断言:Sally 在离场前只见 basket(stale),Anne 全程在场见 box。

注:Memory facade 暴露 `mem._rt.adapter`(非 plan 草案里的 `mem.rt.adapter`),tenant
默认 "default"(facade 无 `mem.tenant` 属性,取 `mem._core.tenant`)。what_does_X_think 的
frontier 参数要 C++ 引擎类 `_core.KnowledgeFrontier`(schema.container.KnowledgeFrontier 是
另一个 dataclass)。
"""
import json

import starling
from starling import _core
from starling.tom import what_does_X_think

_CANNED = json.dumps([
    {"actor": "Sally", "action": "put", "theme": "ball", "location": "basket",
     "participants": ["Sally"], "time": None},
    {"actor": "Sally", "action": "leave", "theme": "room", "location": None,
     "participants": ["Sally"], "time": None},
    {"actor": "Anne", "action": "move", "theme": "ball", "location": "box",
     "participants": ["Anne"], "time": None},
])


def test_sally_anne_false_belief_deterministic(tmp_path):
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="narrator",
                               llm=starling.make_stub_llm(default_response=_CANNED))
    mem.remember("Sally puts her ball in the basket and leaves. Anne moves it to the box.")

    adapter = mem._rt.adapter
    tenant = mem._core.tenant
    frontier = _core.KnowledgeFrontier(adapter)

    sally = what_does_X_think(adapter, frontier, x="Sally", theme="ball", tenant_id=tenant)
    assert sally.has_belief and sally.state_value == "basket" and sally.is_stale

    anne = what_does_X_think(adapter, frontier, x="Anne", theme="ball", tenant_id=tenant)
    assert anne.has_belief and anne.state_value == "box" and not anne.is_stale

    # An outsider who never perceived the ball has no belief about it.
    outsider = what_does_X_think(adapter, frontier, x="Charlie", theme="ball", tenant_id=tenant)
    assert not outsider.has_belief

    mem.close()
