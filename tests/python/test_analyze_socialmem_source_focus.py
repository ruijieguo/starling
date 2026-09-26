"""核验真实复评使用冻结上下文，并保留完整配对分母。"""
import hashlib
import importlib.util
from pathlib import Path
import pytest

def module():
    p=Path(__file__).resolve().parents[2]/'scripts/analyze_socialmem_source_focus.py'
    assert p.is_file(),'source focus analyzer missing'
    spec=importlib.util.spec_from_file_location('analyze_focus',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def fixture():
    refs=[{'turn_id':'t1'}]
    rows=[{'item_id':'a','recall':{'block':'evidence','source_refs':refs}}]
    expected={'a':{'block_sha256':hashlib.sha256(b'evidence').hexdigest(),'source_refs':refs}}
    return rows,expected

def test_exact_context_and_references_required():
    assert module().verify_contexts(*fixture())==1

@pytest.mark.parametrize('change',['text','refs','missing','duplicate','unexpected'])
def test_context_or_selection_drift_is_rejected(change):
    rows,expected=fixture()
    if change=='text':rows[0]['recall']['block']='changed'
    if change=='refs':rows[0]['recall']['source_refs']=[]
    if change=='missing':rows=[]
    if change=='duplicate':rows+=rows[:]
    if change=='unexpected':rows[0]['item_id']='other'
    with pytest.raises(ValueError):module().verify_contexts(rows,expected)


def test_query_failure_is_kept_but_has_no_context_to_verify():
    _, expected = fixture()
    failed = [{'item_id':'a','status':'query_failure','correct':False,'stages':{}}]
    assert module().verify_contexts(failed, expected) == 0
    resources = module().focus_resources(failed)
    assert resources['unavailable_contexts'] == 1
    assert resources['contexts'] is None
    failed[0]['status']='ok'
    with pytest.raises(ValueError): module().verify_contexts(failed, expected)
