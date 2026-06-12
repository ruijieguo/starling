"""P3.a1 检索规划 e2e:facade 全链(remember→tick→query)+ 意图分支 + 拒答。

stub LLM + 默认 stub embedder,零网络。巩固依赖 P2.o 闭环(tick 内 idle 回放)。
"""
import starling

CANNED = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def _mem(tmp_path):
    llm = starling.make_stub_llm(default_response=CANNED)
    return starling.Memory.open(str(tmp_path / "plan.db"), agent="alice", llm=llm)


def test_query_fact_lookup_end_to_end(tmp_path):
    mem = _mem(tmp_path)
    try:
        assert mem.remember("Bob owns the auth module").outcome == "accepted"
        mem.tick()   # 巩固 + 嵌入(P2.o)
        r = mem.query("who owns auth", intent="FACT_LOOKUP",
                      subject="Bob", predicate="responsible_for")
        assert not r["abstained"]
        assert len(r["entries"]) >= 1
        assert r["entries"][0]["label"] in ("FACT", "BELIEF")
        assert "[" in r["context_pack"]            # 带标签行
        rc = r["receipt"]
        assert [s.step for s in rc.plan_steps] == [
            "parse", "mask", "plan", "fetch", "fuse", "ground", "abstain"]
        assert rc.intent_name == "FACT_LOOKUP"
        assert rc.scope_plan.plan_id == rc.query_id
        assert len(rc.score_breakdown) >= 1
    finally:
        mem.close()


def test_query_abstains_structured(tmp_path):
    mem = _mem(tmp_path)
    try:
        r = mem.query("anything about quantum", intent="FACT_LOOKUP",
                      subject="Nobody", predicate="responsible_for")
        assert r["abstained"] is True
        assert r["abstention_reason"] == "low_score"
        assert "[ABSTAIN]" in r["context_pack"]
        assert r["receipt"].sufficiency_status == starling._core.Sufficiency.ABSTAINED
    finally:
        mem.close()


def test_query_intent_enum_exposed(tmp_path):
    from starling import _core
    names = {"FACT_LOOKUP", "BELIEF_OF_OTHER", "META_BELIEF", "HISTORY",
             "COMMITMENT_DUE", "PREFERENCE", "NORM_LOOKUP", "COMMON_GROUND",
             "ABSTAIN_CHECK"}
    assert names.issubset(set(dir(_core.QueryIntent)))
