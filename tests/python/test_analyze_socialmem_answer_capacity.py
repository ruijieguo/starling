"""回答容量实验必须同时保留质量收益和有限观测成本。"""
import importlib.util
from pathlib import Path
import pytest


def module():
    p = Path(__file__).resolve().parents[2] / 'scripts/analyze_socialmem_answer_capacity.py'
    assert p.is_file(), 'answer capacity analyzer missing'
    spec = importlib.util.spec_from_file_location('capacity_analysis', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize('delta,lower,gain,truncated,tokens,expected', [
    (8/733, .001, 8, 15, 3803932, True), (7/733, .001, 7, 15, 3803932, False),
    (.02, 0, 10, 0, 3043146, False), (.02, .001, 0, 0, 3043146, False),
    (.02, .001, 10, 16, 3043146, False), (.02, .001, 10, 0, 3803933, False),
])
def test_capacity_promotion_gate(delta, lower, gain, truncated, tokens, expected):
    assert module().promotion(delta, lower, gain, truncated, tokens) is expected
