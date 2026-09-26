"""真实回执的提示一致性与预注册晋升门槛。"""
import hashlib
import importlib.util
from pathlib import Path
import pytest

def module():
    path=Path(__file__).resolve().parents[2]/'scripts/analyze_socialmem_grounded_answer.py'
    assert path.is_file(), 'analysis missing'
    spec=importlib.util.spec_from_file_location('grounded_analysis',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def test_prompt_mismatch_cannot_be_scored_as_valid_experiment():
    expected={'a':{'prompt_sha256':hashlib.sha256(b'expected').hexdigest()}}
    assert module().verify_prompts([{'item_id':'a','status':'ok','prompt':'expected','correct':True}],expected)==1
    for rows in [[],[{'item_id':'a','status':'ok','prompt':'drift','correct':True}],
                 [{'item_id':'a','status':'ok','correct':False}]]:
        with pytest.raises(ValueError):module().verify_prompts(rows,expected)

def test_missing_prompt_is_permitted_only_for_failure_and_remains_unverified():
    assert module().verify_prompts([{'item_id':'a','status':'answer_failure','correct':False}], {'a':{}})==0

@pytest.mark.parametrize('delta,low,free_gain,expected',[(.04,.01,20,True),(.02,.01,20,False),
    (.04,0,20,False),(.04,.01,0,False)])
def test_preregistered_promotion(delta,low,free_gain,expected):
    assert module().promotion(delta,low,free_gain) is expected
