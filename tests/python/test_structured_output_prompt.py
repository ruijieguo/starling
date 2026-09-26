"""结构化抽取提示的原生 C++ 格式边界。"""

from starling import _core


def test_native_prompt_places_top_level_reminder_after_source_data():
    prompt = _core.claim_extraction_prompt("Mina: I am sad about leaving the team.", "Mina")
    source = prompt.index("SOURCE_DATA_JSON:")
    reminder = prompt.index("FINAL FORMAT CHECK:", source)
    assert "TOP-LEVEL fields" in prompt[reminder:]
    assert "Never put statement fields inside evidence" in prompt[reminder:]
    assert "Never omit holder_perspective" in prompt[reminder:]


def test_native_prompt_requires_unique_keys_and_bad_good_layout_examples():
    prompt = _core.claim_extraction_prompt("Mina: I am sad about leaving the team.", "Mina")
    reminder = prompt.index("FINAL FORMAT CHECK:")
    suffix = prompt[reminder:]
    assert "Each JSON key must appear exactly once" in suffix
    assert "BAD:" in suffix
    assert "GOOD:" in suffix
    assert suffix.index("BAD:") < suffix.index("GOOD:")
    assert "statement={...}, evidence={...}" in suffix
    assert "statement={...}, evidence={clause_id,...}" in suffix
    assert "Mina" not in suffix[suffix.index("BAD:"):]
    assert "leaving the team" not in suffix[suffix.index("BAD:"):]


def test_python_surface_does_not_add_nested_field_repair_logic():
    import pathlib

    root = pathlib.Path(__file__).parents[2]
    source = (root / "scripts" / "run_socialmem_baseline.py").read_text(encoding="utf-8")
    assert "flatten_evidence" not in source
    assert "repair_nested" not in source


def test_native_prompt_exposes_r32_canonical_shapes():
    prompt = _core.claim_extraction_prompt(
        "Mina: I am sad about leaving the team.", "Mina")
    suffix = prompt[prompt.index("FINAL FORMAT CHECK:"):]
    assert "STATEMENT TOP-LEVEL SHAPE" in suffix
    assert "EVIDENCE NESTED SHAPE" in suffix
    assert "CANONICAL SKELETON" in suffix
    assert "Each object key appears exactly once" in suffix
    assert "event_time:null" in suffix
    assert "Mina" not in suffix
    assert "leaving the team" not in suffix
