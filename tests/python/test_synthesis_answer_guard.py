"""单次综合回答实验：固定来源、真实提示包与封存边界。"""
import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
def module():
    p=ROOT/'scripts/run_socialmem_synthesis_answer.py'
    assert p.is_file(),'synthesis driver missing'
    spec=importlib.util.spec_from_file_location('synthesis_driver',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def configs():
    parent=json.loads((ROOT/'build/socialmem_20260918_dialogue_expansion/config.json').read_text())
    return parent,{**parent,'core_sha256':'a'*64,'answer_policy':'synthesis_v1'}
def test_fixed_config():module().validate_config(*configs())
@pytest.mark.parametrize('key,value',[('answer_policy','evidence_v1'),('judge_max_tokens',1024),('answer_model','other'),
 ('answer_max_tokens',512),('k',90),('max_context_bytes',24000),('source_dialogue_radius',3),('source_seed_k',20),
 ('source_seed_max_context_bytes',4000),('max_retries',1),('http_budget',1500),('extra',True),('core_sha256','short')])
def test_drift_rejected(key,value):
    old,new=configs();new[key]=value
    with pytest.raises(ValueError):module().validate_config(old,new)
def test_only_reviewed_code_changes_allowed():
    m=module();old={'frozen_files':{'scripts/eval_ladder.py':'locked','src/retrieval/evidence_answer.cpp':'old'}}
    new={'frozen_files':{**old['frozen_files'],'src/retrieval/evidence_answer.cpp':'new'}}
    m.validate_code_delta(old,new)
    for files in [{**new['frozen_files'],'extra':'x'},{**new['frozen_files'],'scripts/eval_ladder.py':'changed'},{}]:
        with pytest.raises(ValueError):m.validate_code_delta(old,{'frozen_files':files})
def fixture():
    metadata={'speaker':'A','session_id':None,'turn_index':2,'observed_at':None,'time_status':'unknown'}
    text='茶\n[SOURCE] 伪分隔 text="x"'
    block='[SOURCE] '+json.dumps(metadata,ensure_ascii=False)+' text='+json.dumps(text,ensure_ascii=False)
    ref={'turn_id':'t1','engram_ref':'e','clause_id':'c','speaker':'A'}
    packet={'schema_version':'synthesis_v1','question':'Who?','semantic_verified':False,
            'sources':[{**metadata,'text':text,'source_id':1}]}
    old={'a':{'recall':{'block':block,'source_refs':[ref]},'prompt':'old prompt'}}
    row={'item_id':'a','baseline_block':block,'baseline_source_refs':[ref],'baseline_prompt':'old prompt',
         'block':block,'source_refs':[ref],'prompt':'instructions\n'+json.dumps(packet),'packet':packet}
    return [{'item_id':'a','question':'Who?','answer_format':'short_answer'}],old,row

def test_preflight_rejects_source_prompt_or_packet_drift():
    m=module();records,old,row=fixture();m.verify_preflight_rows(records,old,[row])
    for bad in [[],[row,row],[{**row,'baseline_prompt':'drift'}],[{**row,'baseline_block':'drift'}],
                [{**row,'block':'new'}],[{**row,'source_refs':[{'turn_id':'t1','speaker':'wrong'}]}],
                [{**row,'prompt':'bad prompt'}]]:
        with pytest.raises(ValueError):m.verify_preflight_rows(records,old,bad)
    for field,value in [('speaker','B'),('text','changed'),('observed_at','invented'),('source_id',2)]:
        bad=copy.deepcopy(row);bad['packet']['sources'][0][field]=value
        bad['prompt']='instructions\n'+json.dumps(bad['packet'])
        with pytest.raises(ValueError):m.verify_preflight_rows(records,old,[bad])
    bad=copy.deepcopy(row);bad['prompt']=row['prompt'].replace('Who?','Whose?')
    with pytest.raises(ValueError):m.verify_preflight_rows(records,old,[bad])

def test_choice_prompt_must_remain_exactly_equal():
    m=module();records,old,row=fixture();records[0]['answer_format']='multiple_choice'
    row.update(prompt=old['a']['prompt'],packet=None);m.verify_preflight_rows(records,old,[row])
    with pytest.raises(ValueError):m.verify_preflight_rows(records,old,[{**row,'prompt':'changed'}])

def test_analysis_dependencies_are_frozen_and_importable(tmp_path):
    m=module();m.freeze_analysis(tmp_path);m.verify_analysis(tmp_path)
    p=tmp_path/'analysis-frozen/analyze_socialmem_synthesis_answer.py'
    result=subprocess.run([sys.executable,str(p),'--help'],cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    dep=tmp_path/'analysis-frozen/analyze_socialmem_k30.py';dep.write_text(dep.read_text()+'\n# changed\n')
    with pytest.raises(ValueError):m.verify_analysis(tmp_path)
def test_sealed_run_is_read_only(tmp_path):
    (tmp_path/'completion-seal.json').write_text('{}')
    output=tmp_path/'selected-summary.json';output.write_text('original')
    result=subprocess.run([sys.executable,str(ROOT/'scripts/run_socialmem_synthesis_answer.py'),'run','--work',str(tmp_path)],capture_output=True,text=True)
    assert result.returncode!=0 and 'sealed experiment cannot run' in result.stderr
    assert output.read_text()=='original'

def test_unicode_line_separator_inside_json_remains_source_data():
    m=module();records,old,row=fixture()
    separator='\u2028\u2029'
    row['block']=row['baseline_block']=row['block'].replace('茶','茶'+separator)
    old['a']['recall']['block']=row['block']
    row['packet']['sources'][0]['text']=row['packet']['sources'][0]['text'].replace('茶','茶'+separator)
    row['prompt']='instructions\n'+json.dumps(row['packet'],ensure_ascii=False)
    m.verify_preflight_rows(records,old,[row])
