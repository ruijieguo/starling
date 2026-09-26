"""结构化 SocialMemBench 运行器必须只透传原生抽取策略。"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from starling import _core


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "run_socialmem_baseline_wiring", ROOT / "scripts/run_socialmem_baseline.py"
)
runner = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(runner)


def test_default_runner_policy_keeps_legacy_contract_off():
    policy = runner._build_extraction_config({}).to_native_policy()
    assert policy.semantic_claim_contract is False
    assert policy.preserve_text_objects is False


def test_structured_runner_policy_is_native_and_explicit():
    config = {
        "semantic_claim_contract": True,
        "preserve_text_objects": True,
    }
    extraction = runner._build_extraction_config(config)
    policy = extraction.to_native_policy()
    assert extraction.semantic_claim_contract is True
    assert extraction.preserve_text_objects is True
    assert policy.semantic_claim_contract is True
    assert policy.preserve_text_objects is True
    assert hasattr(_core, "ValidationPolicy")
