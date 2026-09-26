"""开发对照的配置与题集必须在请求前固定。"""
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
def module():
    path=ROOT/'scripts/run_socialmem_source_speaker.py'
    assert path.exists(), 'speaker comparison entry missing'
    spec=importlib.util.spec_from_file_location('speaker_entry',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def configs():
    parent=json.loads((ROOT/'build/socialmem_20260917_source_full/config.json').read_text())
    candidate={**parent,'core_sha256':'candidate','http_budget':101}
    return parent,candidate

def groups():
    from run_socialmem_baseline import prepare_groups
    records=[json.loads(x) for x in (ROOT/'build/socialmem_20260917_source_full/corpus.jsonl').read_text().splitlines()]
    return prepare_groups(records)

def test_candidate_changes_only_native_core_and_subset_budget():
    m=module();m.validate_config(*configs(),'candidate')
    selected=m.select_groups(groups())
    assert sum(len(g['records']) for g in selected)==57

@pytest.mark.parametrize('field,value',[('answer_model','other'),('answer_enable_thinking',None),('k',20),('http_budget',102),('core_sha256','other')])
def test_config_drift_is_rejected(field,value):
    parent,candidate=configs();candidate[field]=value
    with pytest.raises(ValueError):module().validate_config(parent,candidate,'candidate')

def test_missing_selected_scope_is_rejected():
    m=module();all_groups=groups()
    removed=next(g for g in all_groups if g['network_id']=='grp_0d1e2f3a')
    with pytest.raises(ValueError):m.select_groups([g for g in all_groups if g is not removed])

def test_archive_cannot_omit_frozen_sources(tmp_path):
    with pytest.raises(ValueError):module().verify_manifest(tmp_path,{'files':{},'scope_ids':['scope']})

def test_copied_entry_loads_before_frozen_dependency_import(tmp_path):
    import shutil,subprocess,sys
    driver=tmp_path/'run.py';shutil.copyfile(ROOT/'scripts/run_socialmem_source_speaker.py',driver)
    result=subprocess.run([sys.executable,str(driver),'--help'],capture_output=True,text=True)
    assert result.returncode==0,result.stderr

def test_full_selected_run_uses_57_question_denominator():
    import run_socialmem_baseline as runner
    m=module();selected=m.select_groups(groups())
    outcomes=[{'results':[{'item_id':r['item_id'],'status':'ok','correct':True} for r in g['records']]} for g in selected]
    summary=m.summarize_selected(runner,selected,{'groups':outcomes,'ledger':{}})
    assert summary['state']=='complete' and summary['summary']['total']==57
    assert summary['summary']['correct']==57 and summary['summary']['accuracy']==1.0
    outcomes[0]['results'].pop()
    assert m.summarize_selected(runner,selected,{'groups':outcomes,'ledger':{}})['state']=='partial'

def test_answer_prompt_change_is_rejected_even_with_new_hash_manifest():
    m=module()
    parent=json.loads((ROOT/'build/socialmem_20260917_source_full/identity.json').read_text())
    candidate=json.loads((ROOT/'build/socialmem_20260917_source_speaker/identity.json').read_text())
    m.validate_code_delta(parent,candidate)
    candidate['frozen_files']['scripts/eval_ladder.py']='changed-valid-hash'
    with pytest.raises(ValueError):m.validate_code_delta(parent,candidate)

def test_context_density_profile_only_adds_k_change():
    parent,candidate=configs();candidate['k']=30
    module().validate_config(parent,candidate,'candidate',variant='context_density')
    candidate['max_context_bytes']=16000
    with pytest.raises(ValueError):module().validate_config(parent,candidate,'candidate',variant='context_density')

def test_unknown_candidate_profile_is_rejected():
    with pytest.raises(ValueError):module().validate_config(*configs(),'candidate',variant='unregistered')
