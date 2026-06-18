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
import os

import pytest

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


# ----- Task 5.2(a): gated real-LLM end-to-end (the perception payoff) -----
#
# Mirrors A's gate in tests/python/test_episodic_e2e.py. Skipped unless
# STARLING_RUN_LLM_E2E is set AND a key is present, so the default offline suite
# stays green regardless of inherited keys (the real test hits a hardcoded
# DeepSeek endpoint, so an unrelated inherited OPENAI_API_KEY would otherwise run
# it with the wrong key and fail). Run it explicitly:
#
#   STARLING_RUN_LLM_E2E=1 OPENAI_API_KEY=$DEEPSEEK_API_KEY \
#   OPENAI_BASE_URL=https://api.deepseek.com/v1 \
#   .venv/bin/python -m pytest \
#       tests/python/test_perception_e2e.py::test_real_llm_sally_anne_perception -v
#
# It drives the FULL remember → A (episodic events) → B (PerceptionReconstructor)
# pipeline on a REAL model and asserts the first-order false-belief readout:
# what_does_X_think(Sally, ball) = basket (stale) and (Anne, ball) = box.

_HAS_LLM_KEY = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"))
_RUN_LLM_E2E = bool(os.environ.get("STARLING_RUN_LLM_E2E")) and _HAS_LLM_KEY


@pytest.mark.skipif(
    not _RUN_LLM_E2E,
    reason="real-LLM e2e: set STARLING_RUN_LLM_E2E=1 (+ OPENAI_API_KEY/"
           "DEEPSEEK_API_KEY for the DeepSeek endpoint) to run")
def test_real_llm_sally_anne_perception(tmp_path):
    """Perception end-to-end on a REAL model: the Sally/Anne narrative must yield
    Sally's stale basket belief and Anne's fresh box belief through the wired
    remember() → reconstruct() path."""
    # make_openai_llm sources the key from OPENAI_API_KEY only; mirror the eval
    # harness when only DEEPSEEK_API_KEY is set.
    if not os.environ.get("OPENAI_API_KEY") and os.environ.get("DEEPSEEK_API_KEY"):
        os.environ["OPENAI_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]

    mem = starling.Memory.open(
        str(tmp_path / "real.db"), agent="narrator",
        llm=starling.make_openai_llm(
            model="deepseek-v4-pro", base_url="https://api.deepseek.com/v1"))
    try:
        mem.remember(
            "Sally puts her ball in the basket and leaves the room. "
            "Anne moves the ball to the box.",
            now="2026-06-16T10:00:00Z")

        adapter = mem._rt.adapter
        tenant = mem._core.tenant
        frontier = _core.KnowledgeFrontier(adapter)

        sally = what_does_X_think(adapter, frontier, x="Sally", theme="ball",
                                  tenant_id=tenant)
        assert sally.has_belief, "Sally should have a belief about the ball"
        assert sally.state_value == "basket", f"Sally should think basket: {sally.state_value!r}"
        assert sally.is_stale, "Sally's basket belief is stale (ball really in box)"

        anne = what_does_X_think(adapter, frontier, x="Anne", theme="ball",
                                 tenant_id=tenant)
        assert anne.has_belief, "Anne should have a belief about the ball"
        assert anne.state_value == "box", f"Anne should think box: {anne.state_value!r}"
        assert not anne.is_stale, "Anne's box belief matches ground truth"
    finally:
        mem.close()
