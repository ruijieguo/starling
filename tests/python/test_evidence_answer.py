"""Python只负责调用原生证据回答及结算，不能读取gold参与生成。"""
import importlib.util
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import run_socialmem_baseline as runner

def test_evidence_policy_routes_only_question_and_authorized_source():
    class Native:
        @staticmethod
        def source_evidence_prompt(question,block):
            assert (question,block)==('Who?','[SOURCE] authorized')
            return 'native evidence request'
    record={'question':'Who?','answer_format':'long_form','answer':'POISON GOLD',
            'history':['POISON HISTORY'],'source':{'evidence_anchors':['POISON ANCHOR']}}
    assert runner.answer_prompt(Native,None,record,{'block':'[SOURCE] authorized'},
        {'answer_policy':'evidence_v1','recall_mode':'sources'})=='native evidence request'

@pytest.mark.parametrize('fmt,want',[('long_form',3),('short_answer',3),('multiple_choice',1)])
def test_request_reservation_covers_evidence_final_answer_and_judge(fmt,want):
    assert runner.question_request_bound({'answer_format':fmt},
        {'answer_policy':'evidence_v1','recall_mode':'sources'},None)==want

def test_choice_prompt_remains_legacy_under_evidence_policy():
    import eval_ladder as ladder
    record={'question':'Which?','answer_format':'multiple_choice','options':['tea','coffee']}
    actual=runner.answer_prompt(None,ladder,record,{'block':'[SOURCE] tea'},
        {'answer_policy':'evidence_v1','recall_mode':'sources'})
    assert actual==ladder._ladder_prompt(record,['[SOURCE] tea'])

def test_evidence_policy_rejects_non_source_recall():
    with pytest.raises(ValueError):runner.validate_answer_policy({'answer_policy':'evidence_v1','recall_mode':'hybrid'})
