"""PR3 纯逻辑单测:plan_fix() —— 订正指向已归档认知体的悬挂 cognizer 语句。
零 DB、零网络(DB 读写 + 真库操作是手动运维,不测)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from fix_dangling_cognizer_statements import plan_fix  # noqa: E402


def test_fixes_cognizer_statement_pointing_at_archived():
    # subject_kind=cognizer 且 subject 指向已归档名 → 订正。
    rows = [
        {"id": "s1", "subject_kind": "cognizer", "subject_id": ".181 GPU"},
        {"id": "s2", "subject_kind": "cognizer", "subject_id": "/hdd free space"},
    ]
    archived = {".181 GPU", "/hdd free space"}
    assert plan_fix(rows, archived) == ["s1", "s2"]


def test_keeps_cognizer_statement_pointing_at_active():
    # subject 指向活跃认知体(不在 archived 集)→ 不动。
    rows = [
        {"id": "s1", "subject_kind": "cognizer", "subject_id": "Alice"},
        {"id": "s2", "subject_kind": "cognizer", "subject_id": ".181 GPU"},
    ]
    archived = {".181 GPU"}  # Alice 活跃
    assert plan_fix(rows, archived) == ["s2"]


def test_idempotent_skips_already_entity():
    # 已订正(subject_kind=entity)的行不再命中 —— 幂等重入。
    rows = [
        {"id": "s1", "subject_kind": "entity", "subject_id": ".181 GPU"},
        {"id": "s2", "subject_kind": "cognizer", "subject_id": ".181 GPU"},
    ]
    archived = {".181 GPU"}
    assert plan_fix(rows, archived) == ["s2"]  # s1 已是 entity,跳过


def test_empty_archived_fixes_nothing():
    rows = [{"id": "s1", "subject_kind": "cognizer", "subject_id": "Alice"}]
    assert plan_fix(rows, set()) == []


def test_no_cognizer_statements():
    rows = [{"id": "s1", "subject_kind": "entity", "subject_id": "Redis"}]
    assert plan_fix(rows, {"Redis"}) == []


def test_mixed_batch():
    rows = [
        {"id": "a", "subject_kind": "cognizer", "subject_id": "Alice"},        # 活跃→留
        {"id": "b", "subject_kind": "cognizer", "subject_id": ".181 GPU"},     # 归档→改
        {"id": "c", "subject_kind": "entity",   "subject_id": ".181 GPU"},     # 已entity→跳
        {"id": "d", "subject_kind": "cognizer", "subject_id": "/hdd size"},    # 归档→改
    ]
    archived = {".181 GPU", "/hdd size", "Postgres"}
    assert plan_fix(rows, archived) == ["b", "d"]
