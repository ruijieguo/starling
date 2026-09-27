"""人物会话覆盖的绑定、实验集合、冻结与配对统计契约。"""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest
from socialmem_fixtures import source_config

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))

def load(name):
    path=ROOT/'scripts'/f'{name}.py'
    assert path.exists(),f'missing coverage implementation: {name}'
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def fixture():
    records=[{'item_id':str(i),'source':{'network_id':str(i//2)}} for i in range(4)]
    before=[True,False,True,False];after=[True,True,False,True]
    rows=[{'item_id':str(i),'arm':arm,'correct':values[i],'status':'ok','terminal':True}
          for arm,values in [('dialogue',before),('coverage',after)] for i in range(4)]
    return records,rows

def test_paired_statistics_hand_calculation():
    stats=load('analyze_socialmem_source_coverage');records,rows=fixture();r=stats.analyze_rows(records,rows)
    assert r['arms']['dialogue']['correct']==2 and r['arms']['coverage']['correct']==3
    assert r['paired']['net_correct']==1 and r['paired']['delta']==.25
    assert r['paired']['new_correct']==2 and r['paired']['regressed']==1
    assert r['paired']['network_bootstrap_95ci']==[0, .5]
    assert r['direction_for_full_validation'] is False and r['promoted'] is False

@pytest.mark.parametrize('change',['missing','duplicate','extra','nonterminal','failed_true','bad_correct','duplicate_record'])
def test_invalid_analysis_sets_rejected(change):
    stats=load('analyze_socialmem_source_coverage');records,rows=fixture()
    if change=='missing':rows.pop()
    if change=='duplicate':rows.append(rows[0])
    if change=='extra':rows[0]['arm']='other'
    if change=='nonterminal':rows[0]['terminal']=False
    if change=='failed_true':rows[0]['status']='answer_failure'
    if change=='bad_correct':rows[0]['correct']='false'
    if change=='duplicate_record':records.append(records[0])
    with pytest.raises(ValueError):stats.analyze_rows(records,rows)

def test_no_common_success_keeps_main_denominator():
    stats=load('analyze_socialmem_source_coverage');records,rows=fixture()
    for r in rows:r.update(status='judge_failure',correct=False)
    report=stats.analyze_rows(records,rows)
    assert report['arms']['coverage']['n']==4
    assert report['both_ok']['n']==0 and report['both_ok']['paired']['delta'] is None

def test_config_rejects_model_budget_prompt_and_retry_changes():
    driver=load('run_socialmem_source_coverage')
    old=source_config('dialogue')
    good={**old,'core_sha256':'a'*64,'http_budget':396,'answer_policy':'grounded_v1'}
    driver.validate_config(old,good)
    for key,value in [('answer_model','different'),('max_retries',1),('answer_max_tokens',512),
                      ('http_budget',397),('answer_policy','synthesis_v1'),('k',61)]:
        bad=copy.deepcopy(good);bad[key]=value
        with pytest.raises(ValueError):driver.validate_config(old,bad)

def test_task_order_rotates_and_contains_only_registered_arms():
    driver=load('run_socialmem_source_coverage');records,_=fixture();tasks=driver.task_order(records)
    assert len(tasks)==8
    for i,r in enumerate(records):
        group=[t for t in tasks if t['item_id']==r['item_id']]
        assert [t['arm'] for t in group]==(['dialogue','coverage'] if i%2==0 else ['coverage','dialogue'])

def test_executing_dependencies_are_bound_to_manifest(tmp_path):
    driver=load('run_socialmem_source_coverage')
    (tmp_path/'execution-plan.json').write_text(json.dumps({'files':{}}))
    with pytest.raises(ValueError,match='executing dependency'):driver.verify_executor(tmp_path)

def test_context_guard_binds_every_selected_line_to_its_source():
    driver=load('run_socialmem_source_coverage')
    first={'speaker':'Alice','turn_id':'a'};second={'speaker':'Bob','turn_id':'b'}
    seeds={'block':'original A','source_refs':[first]}
    eligible={'block':'original A\noriginal B','source_refs':[first,second]}
    candidate={**eligible,'source_count':2,'context_bytes':len(eligible['block'].encode()),
               'source_diagnostics':{'focused_holders':['Bob'],'dialogue_seed_count':1,'coverage_added_sources':1,'dialogue_added_sources':0,
                 'selection_trace':[{'ref':r,'selected_by':'seed' if i==0 else 'coverage','bm25_rank':i+1,
                     'coverage_eligible':i==1,'coverage_considered':i==1,'coverage_budget_rejected':False,
                     'dialogue_considered':False,'dialogue_budget_rejected':False} for i,r in enumerate([first,second])]}}
    driver.verify_context(seeds,candidate,seeds,eligible)
    for change in ('text','swapped_text','trace','duplicate','missing_seed','stage','rank','person','count'):
        bad=copy.deepcopy(candidate)
        if change=='text':bad['block']='original A\nforged B';bad['context_bytes']=len(bad['block'].encode())
        if change=='swapped_text':bad['block']='original B\noriginal A';bad['context_bytes']=len(bad['block'].encode())
        if change=='trace':bad['source_diagnostics']['selection_trace'].pop()
        if change=='duplicate':bad['source_refs']=[first,first]
        if change=='missing_seed':bad['source_refs']=[second]
        if change=='stage':bad['source_diagnostics']['selection_trace'][1]['selected_by']='invented'
        if change=='rank':bad['source_diagnostics']['selection_trace'][1]['bm25_rank']=1
        if change=='person':bad['source_diagnostics']['focused_holders']=[]
        if change=='count':bad['source_count']=1
        with pytest.raises(ValueError):driver.verify_context(seeds,bad,seeds,eligible)

def test_freeze_requires_prompts_and_every_identity_file(tmp_path):
    driver=load('run_socialmem_source_coverage')
    required={'config.json','identity.json','sample.json','corpus.jsonl','scope-manifest.json',
              'network-split.json','tasks.json','inputs.json','prompts.json','native-preflight.json',*driver.SCRIPTS}
    (tmp_path/'identity.json').write_text(json.dumps({'frozen_files':{'python/frozen.py':'abc'}}))
    (tmp_path/'native-preflight.json').write_text(json.dumps({'rows':[{'group_id':'g'}]}))
    plan={'files':{**{n:'x' for n in required},'frozen/python/frozen.py':'abc','source-databases/g.db':'db'}}
    driver.verify_required_files(tmp_path,plan)
    for name in ('prompts.json','inputs.json','frozen/python/frozen.py','source-databases/g.db'):
        bad=copy.deepcopy(plan);del bad['files'][name]
        with pytest.raises(ValueError):driver.verify_required_files(tmp_path,bad)
    bad=copy.deepcopy(plan);bad['files']['frozen/python/frozen.py']='changed'
    with pytest.raises(ValueError):driver.verify_required_files(tmp_path,bad)

def test_actual_helper_paths_and_standard_hash_are_verified(tmp_path,monkeypatch):
    driver=load('run_socialmem_source_coverage')
    import hashlib
    files=[]
    for name in ('run_socialmem_source_coverage.py','run_socialmem_answer_ablation.py','run_socialmem_k30_controlled.py'):
        p=tmp_path/name;p.write_text(name);files.append(p)
    plan={'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (tmp_path/'execution-plan.json').write_text(json.dumps(plan))
    for module,path in zip((driver,driver.previous,driver.base),files):monkeypatch.setattr(module,'__file__',str(path))
    driver.verify_executor(tmp_path)
    files[2].write_text('drift')
    monkeypatch.setattr(driver,'sha',lambda p:plan['files'][Path(p).name])
    with pytest.raises(ValueError):driver.verify_executor(tmp_path)

def test_complete_budget_and_terminal_audit_rejects_mutation(tmp_path):
    driver=load('run_socialmem_source_coverage')
    import shutil
    import sqlite3
    import run_socialmem_baseline as runner
    from test_answer_ablation import Receipt,Boundary
    audit=load('eval_judge_audit')
    records=[{'item_id':str(i),'question':'When?','answer':'A','source':{'network_id':str(i//3)}} for i in range(99)]
    tasks=driver.task_order(records);driver.write(tmp_path/'execution-plan.json',{'fixture':True})
    fingerprint={'execution_plan_sha256':driver.sha(tmp_path/'execution-plan.json')}
    for name,value in [('run-started.json',fingerprint),('sample.json',records),('tasks.json',tasks),
                       ('prompts.json',{r['item_id']:{a:'fixed' for a in driver.ARMS} for r in records})]:driver.write(tmp_path/name,value)
    folder=tmp_path/'frozen/scripts';folder.mkdir(parents=True);shutil.copyfile(ROOT/'scripts/eval_judge_audit.py',folder/'eval_judge_audit.py')
    ledger=runner.BudgetLedger(tmp_path/'request-ledger.sqlite',396);by_id={r['item_id']:r for r in records}
    for t in tasks:driver.previous.execute_task(tmp_path,t,by_id[t['item_id']],'fixed',runner,audit,Boundary(Receipt('A')),Boundary(Receipt('YES')),ledger,fingerprint)
    assert driver.verify_terminal(tmp_path)['actual_requests']==396
    path=next((tmp_path/'receipts').glob('*.json'));original=driver.read(path)
    for change in ('prompt','score','attempts','missing'):
        row=copy.deepcopy(original)
        if change=='prompt':row['prompt']='wrong'
        if change=='score':row['correct']=False
        if change=='attempts':row['native_attempt_count']=0
        if change=='missing':path.unlink()
        else:driver.write(path,row)
        with pytest.raises(ValueError):driver.verify_terminal(tmp_path)
        driver.write(path,original)
    with sqlite3.connect(tmp_path/'request-ledger.sqlite') as conn:conn.execute('UPDATE reservations SET actual=0 WHERE id=1')
    with pytest.raises(ValueError):driver.verify_terminal(tmp_path)

def test_real_native_binding_routes_coverage_without_python_selection():
    program=r'''
import importlib.util,json,sys,tempfile
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'scripts'))
p=root/'build/python/starling/_core.cpython-314-darwin.so'
s=importlib.util.spec_from_file_location('starling._core',p);core=importlib.util.module_from_spec(s);sys.modules['starling._core']=core;s.loader.exec_module(core)
from starling import runtime
import run_socialmem_baseline as runner
import eval_ladder_pipeline as pipe
history=[{'speaker':'Alice','text':text,'session_id':session,'turn_index':idx,'turn_id':str(idx),'observed_at':'2025-01-01T00:00:00Z'}
 for text,session,idx in [('I prefer tea','early',1),('My ankle is recovering','later',80)]]
with tempfile.TemporaryDirectory() as tmp:
 rt=runtime._build_local_store_sqlite_runtime(Path(tmp)/'test.db');rt.start()
 runner.retain_history_sources(core,rt.adapter,history,'2026-06-01T00:00:00Z')
 r=pipe.recall_observer_block(core,adapter=rt.adapter,embedder=core.StubEmbeddingAdapter(8),index=core.SqliteBlobVectorIndex(),
 question='What does Alice prefer?',allowed_holders=['Alice'],mode='sources',now_iso='2026-12-08T00:00:00Z',
 source_strategy='focused_coverage',source_seed_k=1,source_seed_max_context_bytes=1000,source_dialogue_radius=2,k=5,max_context_bytes=4000)
 assert [x['turn_index'] for x in r['source_refs']]==[1,80]
 assert r['source_diagnostics']['coverage_added_sources']==1
'''
    p=subprocess.run([sys.executable,'-c',program,str(ROOT)],capture_output=True,text=True)
    assert p.returncode==0,p.stdout+p.stderr
