"""紧凑候选的晋升必须同时通过质量、截断与观测成本门槛。"""
import importlib.util
from pathlib import Path
import pytest

def module():
    p=Path(__file__).resolve().parents[2]/'scripts/analyze_socialmem_compact_answer.py'
    assert p.is_file(),'compact analyzer missing'
    spec=importlib.util.spec_from_file_location('compact_analysis',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

@pytest.mark.parametrize('delta,lower,gain,truncated,tokens,expected',[
    (8/733,.001,8,15,3043146,True),(7/733,.001,7,15,3043146,False),
    (.02,0,10,0,2900000,False),(.02,.001,0,0,2900000,False),
    (.02,.001,10,16,2900000,False),(.02,.001,10,0,3043147,False)])
def test_preregistered_gate(delta,lower,gain,truncated,tokens,expected):
    assert module().promotion(delta,lower,gain,truncated,tokens) is expected
