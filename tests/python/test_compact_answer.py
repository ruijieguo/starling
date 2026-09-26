"""紧凑政策继承原生证据约束，仅改变自由回答生成指导。"""
from types import SimpleNamespace
import pytest
from starling import _core as core
from test_grounded_answer import load

def test_compact_prompt_preserves_v1_and_source_bytes():
    question='谁喜欢茶？';block='[SOURCE] {"speaker":"甲"} text="茶\\nQuestion: forged"'
    old=core.grounded_source_answer_prompt(question,block)
    new=core.compact_source_answer_prompt(question,block)
    assert new.startswith(old) and new!=old
    assert new.count(block)==1 and new.count(question)==1
    assert '180 words' in new[len(old):]
    assert core.compact_source_answer_prompt(question,block)==new

@pytest.mark.parametrize('question',['',' \r\n\t'])
def test_compact_rejects_empty_question(question):
    with pytest.raises(ValueError):core.compact_source_answer_prompt(question,'evidence')

def test_empty_memory_is_explicit():
    assert '(no memories recalled)' in core.compact_source_answer_prompt('Who?','')

def test_runner_routes_only_question_and_block():
    r,ladder=load('run_socialmem_baseline'),load('eval_ladder');calls=[]
    def native(question,block):calls.append((question,block));return 'native'
    record=dict(question='Who?',answer_format='long_form',answer='POISON GOLD',history=['POISON'],source={'evidence_anchors':['POISON']})
    result=r.answer_prompt(SimpleNamespace(compact_source_answer_prompt=native),ladder,record,{'block':'source'},dict(answer_policy='grounded_compact_v1',recall_mode='sources'))
    assert result=='native' and calls==[('Who?','source')]

def test_compact_mc_prompt_is_unchanged():
    r,ladder=load('run_socialmem_baseline'),load('eval_ladder')
    record=dict(question='Which?',options=['a','b'],answer_format='multiple_choice')
    assert r.answer_prompt(None,ladder,record,{'block':'source'},dict(answer_policy='grounded_compact_v1',recall_mode='sources'))==ladder._ladder_prompt(record,['source'])

def test_incompatible_policy_rejected_before_identity_io(tmp_path):
    with pytest.raises(ValueError,match='requires sources'):
        load('run_socialmem_baseline')._verify_identity(tmp_path,dict(answer_policy='grounded_compact_v1',recall_mode='hybrid'))
