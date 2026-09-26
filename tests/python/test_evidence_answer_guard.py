"""固定证据政策候选，禁止检索/裁判/预算漂移。"""
import importlib.util
import json
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
def module():
    path=ROOT/'scripts/run_socialmem_evidence_answer.py'
    assert path.is_file(),'evidence driver missing'
    spec=importlib.util.spec_from_file_location('evidence_driver',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def configs():
    parent=json.loads((ROOT/'build/socialmem_20260918_answer_capacity_v2/config.json').read_text())
    return parent,{**parent,'core_sha256':'a'*64,'answer_policy':'evidence_v1','http_budget':1895}
def test_valid_candidate():module().validate_config(*configs())
@pytest.mark.parametrize('key,value',[('judge_max_tokens',1024),('answer_model','other'),('answer_max_tokens',2048),
    ('k',60),('max_context_bytes',16000),('source_strategy','bm25'),('http_budget',1896),('max_retries',1),
    ('answer_enable_thinking',True),('answer_policy','grounded_v1'),('extra',True),('core_sha256','short'),
    ('include_unknown_time',1)])
def test_config_drift_rejected(key,value):
    old,new=configs();new[key]=value
    with pytest.raises(ValueError):module().validate_config(old,new)
def test_only_explicit_new_files_and_reviewed_changes_allowed():
    m=module();old={'frozen_files':{'scripts/eval_ladder.py':'locked','scripts/run_socialmem_baseline.py':'old'}}
    good={**old['frozen_files'],**{s:'new' for s in m.ADDED},'scripts/run_socialmem_baseline.py':'new'}
    m.validate_code_delta(old,{'frozen_files':good})
    for bad in [{**good,'scripts/eval_ladder.py':'changed'},{**good,'extra.py':'new'},
                {k:v for k,v in good.items() if k!='scripts/eval_ladder.py'}]:
        with pytest.raises(ValueError):m.validate_code_delta(old,{'frozen_files':bad})
def test_preflight_requires_all_source_and_choice_prompt_matches():
    m=module();records=[{'item_id':'a','answer_format':'multiple_choice'}]
    parent={'a':{'recall':{'block':'source','source_refs':[]},'prompt':'choice'}}
    row={'item_id':'a','block':'source','source_refs':[],'prompt':'choice'}
    m.verify_preflight_rows(records,parent,[row])
    for rows in [[],[row,row],[{**row,'block':'different'}],[{**row,'prompt':'different'}]]:
        with pytest.raises(ValueError):m.verify_preflight_rows(records,parent,rows)
def test_analysis_snapshot_is_self_contained_and_detects_dependency_drift(tmp_path):
    m=module();m.freeze_analysis(tmp_path)
    m.verify_analysis(tmp_path)
    import subprocess,sys
    script=tmp_path/'analysis-frozen/analyze_socialmem_evidence_answer.py'
    result=subprocess.run([sys.executable,str(script),'--help'],cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    dependency=tmp_path/'analysis-frozen/analyze_socialmem_k30.py'
    dependency.write_text(dependency.read_text()+'\n# drift\n')
    with pytest.raises((RuntimeError,ValueError)):m.verify_analysis(tmp_path)
def test_sealed_run_rejected_before_validation_or_mutation(tmp_path):
    import subprocess,sys
    (tmp_path/'completion-seal.json').write_text('{}')
    summary=tmp_path/'selected-summary.json';summary.write_text('sealed bytes')
    result=subprocess.run([sys.executable,str(ROOT/'scripts/run_socialmem_evidence_answer.py'),
        'run','--work',str(tmp_path)],capture_output=True,text=True)
    assert result.returncode!=0 and 'sealed experiment cannot run' in result.stderr
    assert summary.read_text()=='sealed bytes'
