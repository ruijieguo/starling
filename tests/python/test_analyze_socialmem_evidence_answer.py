"""两阶段回答须达到显著收益，所有阶段用量必须进入门槛。"""
import importlib.util
from pathlib import Path
import pytest
def module():
    p=Path(__file__).resolve().parents[2]/'scripts/analyze_socialmem_evidence_answer.py'
    assert p.is_file(),'evidence analyzer missing'
    s=importlib.util.spec_from_file_location('evidence_analysis',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
@pytest.mark.parametrize('delta,lower,gain,truncated,tokens,expected',[
 (37/733,.001,37,15,6370710,True),(36/733,.001,36,15,6370710,False),
 (.1,0,50,0,4000000,False),(.1,.01,0,0,4000000,False),(.1,.01,50,16,4000000,False),
 (.1,.01,50,0,6370711,False)])
def test_promotion_gate(delta,lower,gain,truncated,tokens,expected):
    assert module().promotion(delta,lower,gain,truncated,tokens) is expected
def test_evidence_tokens_and_failures_are_not_hidden():
    rows=[{'evidence':{'response':{'ok':False,'total_tokens':17,'prompt_tokens':10,'completion_tokens':7,
        'finish_reason':'length','attempt_count':1}},'evidence_fallback':True,
        'evidence_fallback_reason':'evidence_response_unusable','evidence_validation':{'accepted':[],'rejected':[]}}]
    result=module().evidence_resources(rows)
    assert result['total_tokens']==17 and result['attempt_count']==1
    assert result['fallback_count']==1 and result['unusable_response_count']==1
def test_failed_final_replay_does_not_publish_old_gate_report(tmp_path):
    import json,hashlib
    work=tmp_path/'candidate';parent=tmp_path/'parent';work.mkdir();parent.mkdir()
    record={'item_id':'a','answer_format':'short_answer','query_type':'Q1','question':'Who?',
        'answer':'A','source':{'network_id':'n','evidence_anchors':[]}}
    (work/'corpus.jsonl').write_text(json.dumps(record)+'\n')
    (work/'execution-plan.json').write_text(json.dumps({'parent_work':str(parent),'question_ids':['a']}))
    row={'item_id':'a','status':'ok','correct':True,'native_attempt_count':2,'embedding_request_delta':0,
        'recall':{'block':'','source_refs':[],'context_bytes':0,'source_count':0},'prompt':'fixture',
        'stages':{'answer':{'seconds':0},'judge':{'seconds':0}}}
    for stage in ['answer','judge']:
        row[stage]={'raw_xml':'A','response':{'ok':True,'finish_reason':'stop','completion_tokens':1,'prompt_tokens':1,'total_tokens':2}}
    for folder in (work,parent):
        dest=folder/'runs/g/questions';dest.mkdir(parents=True)
        (dest/'a.json').write_text(json.dumps(row))
    (work/'native-preflight.json').write_text(json.dumps({'rows':[{'item_id':'a','block_sha256':hashlib.sha256(b'').hexdigest(),
        'source_refs':[],'prompt_sha256':hashlib.sha256(b'fixture').hexdigest()}]}))
    with pytest.raises((FileNotFoundError,RuntimeError,ValueError)):
        module().analyze(work)
    assert not (work/'paired-analysis.json').exists(),'failed analysis published intermediate old-gate report'
    assert not (work/'paired-details.json').exists()
def test_sealed_analysis_refuses_to_rewrite_report(tmp_path):
    (tmp_path/'completion-seal.json').write_text('{}')
    report=tmp_path/'paired-analysis.json';report.write_text('sealed bytes')
    with pytest.raises(ValueError,match='sealed experiment cannot analyze'):
        module().analyze(tmp_path)
    assert report.read_text()=='sealed bytes'
