"""连续对话实验的冻结边界、种子保真和有限预算。"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
def module():
    p=ROOT/'scripts/run_socialmem_dialogue_expansion.py'
    assert p.is_file(),'dialogue driver missing'
    spec=importlib.util.spec_from_file_location('dialogue_driver',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def configs():
    parent=json.loads((ROOT/'build/socialmem_20260918_answer_capacity_v2/config.json').read_text())
    return parent,{**parent,'core_sha256':'a'*64,'source_strategy':'focused_dialogue','k':60,'max_context_bytes':16000,
       'source_seed_k':30,'source_seed_max_context_bytes':8000,'source_dialogue_radius':2}
def test_fixed_config():module().validate_config(*configs())
@pytest.mark.parametrize('key,value',[('answer_policy','evidence_v1'),('judge_max_tokens',1024),('answer_model','other'),
 ('answer_max_tokens',512),('k',90),('max_context_bytes',24000),('source_dialogue_radius',3),('source_seed_k',20),
 ('source_seed_max_context_bytes',4000),('max_retries',1),('http_budget',1500),('extra',True),('core_sha256','short')])
def test_drift_rejected(key,value):
    old,new=configs();new[key]=value
    with pytest.raises(ValueError):module().validate_config(old,new)
def test_only_reviewed_code_changes_allowed():
    m=module();old={'frozen_files':{'scripts/eval_ladder.py':'locked','src/retrieval/source_retriever.cpp':'old'}}
    new={'frozen_files':{**old['frozen_files'],'src/retrieval/source_retriever.cpp':'new'}}
    m.validate_code_delta(old,new)
    for files in [{**new['frozen_files'],'extra':'x'},{**new['frozen_files'],'scripts/eval_ladder.py':'changed'},{}]:
        with pytest.raises(ValueError):m.validate_code_delta(old,{'frozen_files':files})
def fixture():
    ref={'turn_id':'t1','engram_ref':'e','clause_id':'c','speaker':'A'}
    old={'a':{'recall':{'block':'old','source_refs':[ref]},'prompt':'same'}}
    row={'item_id':'a','baseline_block':'old','baseline_source_refs':[ref],'baseline_prompt':'same',
         'block':'old\nnew','source_refs':[ref,{'turn_id':'t2'}],'prompt':'new prompt'}
    return [{'item_id':'a','answer_format':'short_answer'}],old,row

def test_preflight_rejects_lost_or_mutated_seed_and_mismatched_baseline():
    m=module();records,old,row=fixture();m.verify_preflight_rows(records,old,[row])
    for bad in [[],[row,row],[{**row,'baseline_prompt':'drift'}],[{**row,'baseline_block':'drift'}],
                [{**row,'block':'new'}],[{**row,'source_refs':[{'turn_id':'t1','speaker':'wrong'}]}],
                [{**row,'block':'old\n'+'x'*16000}],[{**row,'source_refs':row['source_refs']*31}]]:
        with pytest.raises(ValueError):m.verify_preflight_rows(records,old,bad)
def test_analysis_dependencies_are_frozen_and_importable(tmp_path):
    m=module();m.freeze_analysis(tmp_path);m.verify_analysis(tmp_path)
    p=tmp_path/'analysis-frozen/analyze_socialmem_dialogue_expansion.py'
    result=subprocess.run([sys.executable,str(p),'--help'],cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    dep=tmp_path/'analysis-frozen/analyze_socialmem_k30.py';dep.write_text(dep.read_text()+'\n# changed\n')
    with pytest.raises(ValueError):m.verify_analysis(tmp_path)
def test_sealed_run_is_read_only(tmp_path):
    (tmp_path/'completion-seal.json').write_text('{}')
    output=tmp_path/'selected-summary.json';output.write_text('original')
    result=subprocess.run([sys.executable,str(ROOT/'scripts/run_socialmem_dialogue_expansion.py'),'run','--work',str(tmp_path)],capture_output=True,text=True)
    assert result.returncode!=0 and 'sealed experiment cannot run' in result.stderr
    assert output.read_text()=='original'
