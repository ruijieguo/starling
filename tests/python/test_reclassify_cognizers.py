"""reclassify_cognizers 纯逻辑单测(零真 LLM,零 DB)。

覆盖 plan_archive() 全分支:entity 归档、幂等跳过、分类缺失保守跳过、
kind 更新、无「有边保护」(那 6 个 seed 假人不特殊对待)。真 LLM 的
classify_names() 不在此测(Clash 黑洞换时刻手动跑)。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from reclassify_cognizers import plan_archive  # noqa: E402


def _row(cid, name, kind="human", archived_at=None):
    return {"id": cid, "canonical_name": name, "kind": kind, "archived_at": archived_at}


def test_entity_gets_archived():
    rows = [_row("c1", "H800 memory"), _row("c2", "Alice")]
    cls = {
        "H800 memory": {"is_cognizer": False, "cognizer_kind": None},
        "Alice": {"is_cognizer": True, "cognizer_kind": "human"},
    }
    archive_ids, kind_updates = plan_archive(rows, cls)
    assert archive_ids == ["c1"]        # entity 归档
    assert kind_updates == []           # Alice 已是 human,无更新


def test_idempotent_skips_already_archived():
    # 已归档(archived_at 非空)→ 跳过,不重复处理。
    rows = [_row("c1", "macro4 score", archived_at="2026-07-23T00:00:00Z")]
    cls = {"macro4 score": {"is_cognizer": False, "cognizer_kind": None}}
    archive_ids, kind_updates = plan_archive(rows, cls)
    assert archive_ids == []
    assert kind_updates == []


def test_missing_classification_is_conservatively_skipped():
    # LLM 没返回该 name(失败的批)→ 保守不动,留待重跑,绝不误杀。
    rows = [_row("c1", "some name")]
    archive_ids, kind_updates = plan_archive(rows, {})
    assert archive_ids == []
    assert kind_updates == []


def test_cognizer_kind_update():
    # 是认知体但 kind 更准(库中 human,LLM 判 agent)→ kind 更新,不归档。
    rows = [_row("c1", "Claude", kind="human")]
    cls = {"Claude": {"is_cognizer": True, "cognizer_kind": "agent"}}
    archive_ids, kind_updates = plan_archive(rows, cls)
    assert archive_ids == []
    assert kind_updates == [("c1", "agent")]


def test_cognizer_kind_unchanged_no_update():
    rows = [_row("c1", "the eng team", kind="group")]
    cls = {"the eng team": {"is_cognizer": True, "cognizer_kind": "group"}}
    archive_ids, kind_updates = plan_archive(rows, cls)
    assert archive_ids == []
    assert kind_updates == []          # kind 已对,不重复更新


def test_invalid_kind_ignored():
    # LLM 返回值域外 kind → 不更新(不写非法值)。
    rows = [_row("c1", "Bob", kind="human")]
    cls = {"Bob": {"is_cognizer": True, "cognizer_kind": "robot"}}
    archive_ids, kind_updates = plan_archive(rows, cls)
    assert archive_ids == []
    assert kind_updates == []


def test_no_edge_protection():
    # 决策锁定:不做「有边保护」。seed 假人 Alice 若被 LLM 判为 entity(假设),
    # 照常归档 —— plan_archive 不看关系边,纯 LLM 分类为准。
    # (现实中 Alice 会判 cognizer;这里构造反例证明逻辑不含边保护分支。)
    rows = [_row("c1", "Alice")]
    cls = {"Alice": {"is_cognizer": False, "cognizer_kind": None}}
    archive_ids, kind_updates = plan_archive(rows, cls)
    assert archive_ids == ["c1"]        # 无豁免,照归档


def test_mixed_batch():
    rows = [
        _row("c1", "iter1 Q1 improvement"),
        _row("c2", "c20 composite score"),
        _row("c3", "Alice", kind="human"),
        _row("c4", "Claude", kind="human"),
        _row("c5", "archived one", archived_at="2026-07-23T00:00:00Z"),
    ]
    cls = {
        "iter1 Q1 improvement": {"is_cognizer": False, "cognizer_kind": None},
        "c20 composite score": {"is_cognizer": False, "cognizer_kind": None},
        "Alice": {"is_cognizer": True, "cognizer_kind": "human"},
        "Claude": {"is_cognizer": True, "cognizer_kind": "agent"},
        "archived one": {"is_cognizer": False, "cognizer_kind": None},
    }
    archive_ids, kind_updates = plan_archive(rows, cls)
    assert set(archive_ids) == {"c1", "c2"}     # 两个 entity;c5 已归档跳过
    assert kind_updates == [("c4", "agent")]     # Claude human→agent
