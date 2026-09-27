"""全量来源评测必须先验证完整题集和不可变范围。"""
import importlib.util
from pathlib import Path
import pytest
SCRIPT=Path(__file__).resolve().parents[2]/'scripts/run_socialmem_source_full.py'
def module():
    assert SCRIPT.exists(), 'full source entry missing'
    spec=importlib.util.spec_from_file_location('full_source',SCRIPT)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def prepared():
    groups=[{'group_id':str(i),'records':[]} for i in range(49)]
    for i in range(1031):groups[i%49]['records'].append({'item_id':str(i),'answer_format':'multiple_choice' if i<214 else 'long_form'})
    cfg={'recall_mode':'sources','answer_enable_thinking':False,'retain_sources':True,'http_budget':1848,
         'k':10,'max_context_bytes':8000,'max_retries':0,'timeout_ms':120000,
         'query_time':'2026-12-08T00:00:00Z','answer_max_tokens':512,'judge_max_tokens':64,
         'extract_model':'qwen3.8-27b','answer_model':'qwen3.8-27b',
         'extract_endpoint':'https://dashscope.aliyuncs.com/compatible-mode/v1',
         'answer_endpoint':'https://dashscope.aliyuncs.com/compatible-mode/v1'}
    plan={'questions':1031,'groups':49,'http_budget':1848,'scope_ids':[g['group_id'] for g in groups]}
    return plan,cfg,groups

def test_complete_fixed_protocol_is_accepted():
    module().validate_protocol(*prepared())

@pytest.mark.parametrize('field,value',[('answer_enable_thinking',None),('http_budget',2000),('recall_mode','hybrid'),('answer_model','another-model')])
def test_changed_model_role_or_budget_is_rejected(field,value):
    plan,cfg,groups=prepared();cfg[field]=value
    with pytest.raises(ValueError):module().validate_protocol(plan,cfg,groups)

def test_missing_or_duplicate_questions_are_rejected():
    plan,cfg,groups=prepared();groups[0]['records'][0]['item_id']=groups[1]['records'][0]['item_id']
    with pytest.raises(ValueError):module().validate_protocol(plan,cfg,groups)

def test_empty_archive_manifest_cannot_skip_snapshot_verification(tmp_path):
    with pytest.raises(ValueError):module().verify_manifest(tmp_path,{'scope_ids':[str(i) for i in range(49)],'files':{}})


def test_failed_source_scope_requires_all_affected_questions_to_be_terminal(tmp_path):
    import json
    from types import SimpleNamespace
    m=module()
    assert hasattr(m,'verify_scope_states'), 'source failure terminal validation missing'
    group={'group_id':'bad','records':[{'item_id':'q1'}]}
    folder=tmp_path/'runs/bad';folder.mkdir(parents=True)
    fingerprint={'core':'frozen'}
    (folder/'scope.failure.json').write_text(json.dumps({'fingerprint':fingerprint,'error':'invalid source observation timestamp'}))
    runner=SimpleNamespace(scope_state=lambda *a:'pending',question_states=lambda *a:{'q1':'pending'},_stable_id=lambda *a:'fixed')
    with pytest.raises(ValueError):m.verify_scope_states(tmp_path,[group],runner,fingerprint,{'failed_scopes':['bad']})
    runner.question_states=lambda *a:{'q1':'terminal'}
    with pytest.raises(ValueError):m.verify_scope_states(tmp_path,[group],runner,fingerprint,{'failed_scopes':['bad']})
    (folder/'questions').mkdir()
    (folder/'questions/fixed.json').write_text(json.dumps({'status':'ingestion_failure','correct':False,'terminal':True}))
    m.verify_scope_states(tmp_path,[group],runner,fingerprint,{'failed_scopes':['bad'],'files':{'runs/bad/questions/fixed.json':'hash'}})


def test_frozen_runner_can_be_dispatched_to_spawn_workers(tmp_path):
    import subprocess,sys
    root=Path(__file__).resolve().parents[2]
    code=r'''
from concurrent.futures import ProcessPoolExecutor
import importlib.util,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('entry',Path(sys.argv[1])/'scripts/run_socialmem_source_full.py')
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
assert hasattr(d,'load_frozen_runner'),'spawn-safe frozen runner loader missing'
r=d.load_frozen_runner(Path(sys.argv[2]))
with ProcessPoolExecutor(max_workers=2) as pool:
 assert pool.submit(r._stable_id,'source-full').result(timeout=20)==r._stable_id('source-full')
'''
    import shutil
    scripts = tmp_path/'frozen/scripts'; scripts.mkdir(parents=True)
    shutil.copyfile(root/'scripts/run_socialmem_baseline.py', scripts/'run_socialmem_baseline.py')
    result=subprocess.run([sys.executable,'-c',code,str(root),str(tmp_path)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
