"""回答消融：抽样独立性、完整集合、配对统计和请求边界。"""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))

def load(name):
    path=ROOT/'scripts'/f'{name}.py'
    assert path.is_file(),f'missing ablation implementation: {name}'
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def corpus():
    return [{'item_id':f'n{n}-q{i}','source':{'network_id':str(n)},'answer_format':'long_form',
             'question':'Who?','answer':'SECRET_GOLD','correct':False} for n in range(33) for i in range(5)]

def test_sampling_is_balanced_and_independent_of_labels_and_order():
    driver=load('run_socialmem_answer_ablation');records=corpus()
    chosen=driver.select_sample(records)
    from collections import Counter
    assert len(chosen)==99
    assert set(Counter(r['source']['network_id'] for r in chosen).values())=={3}
    changed=copy.deepcopy(records[::-1])
    for row in changed:row.update(answer='DIFFERENT GOLD',correct=True)
    assert [r['item_id'] for r in chosen]==[r['item_id'] for r in driver.select_sample(changed)]

def test_sample_rejects_missing_network_duplicate_and_insufficient_free_questions():
    driver=load('run_socialmem_answer_ablation')
    for records in [corpus()[5:],corpus()+[corpus()[0]],corpus()[3:]]:
        with pytest.raises(ValueError):driver.select_sample(records)

def test_four_arms_rotate_with_complete_question_coverage():
    driver=load('run_socialmem_answer_ablation');sample=driver.select_sample(corpus())
    tasks=driver.task_order(sample)
    assert len(tasks)==396
    from collections import Counter
    assert set(Counter(t['item_id'] for t in tasks).values())=={4}
    for pos in range(4):
        counts=Counter(t['arm'] for t in tasks if t['position']==pos)
        assert sorted(counts.values())==[24,25,25,25]
    for item in sample:
        assert {t['arm'] for t in tasks if t['item_id']==item['item_id']}==set(driver.ARMS)

def fixture_rows():
    arms=('source_grounded','json_grounded','source_synthesis','json_synthesis')
    records=[{'item_id':str(i),'source':{'network_id':str(i)}} for i in range(3)]
    rows=[{'item_id':r['item_id'],'arm':arm,'terminal':True,'status':'ok','correct':arm!='source_grounded'}
          for r in records for arm in arms]
    return records,rows

def test_factor_effects_match_hand_calculation_and_network_resampling():
    stats=load('analyze_socialmem_answer_ablation');records,rows=fixture_rows()
    result=stats.analyze_rows(records,rows)
    assert result['arms']['source_grounded']['correct']==0
    assert result['arms']['json_grounded']['correct']==3
    for key,value in [('representation_grounded',1),('representation_synthesis',0),
                      ('guidance_source',1),('guidance_json',0),('interaction',-1)]:
        assert result['effects'][key]['delta']==value
        assert result['effects'][key]['network_bootstrap_95ci']==[value,value]
    assert result['effects']['representation_grounded']['new_correct']==3
    assert result['effects']['representation_grounded']['regressed']==0
    assert result['both_ok']['n']==3

@pytest.mark.parametrize('change',['missing','duplicate','extra','nonterminal','failed_true','bad_correct'])
def test_analysis_refuses_invalid_receipt_sets(change):
    stats=load('analyze_socialmem_answer_ablation');records,rows=fixture_rows()
    if change=='missing':rows.pop()
    if change=='duplicate':rows.append(rows[0])
    if change=='extra':rows[0]['arm']='unregistered'
    if change=='nonterminal':rows[0]['terminal']=False
    if change=='failed_true':rows[1]['status']='judge_failure'
    if change=='bad_correct':rows[0]['correct']='false'
    with pytest.raises(ValueError):stats.analyze_rows(records,rows)

def test_zero_technical_subset_is_null_and_failures_stay_in_denominator():
    stats=load('analyze_socialmem_answer_ablation');records,rows=fixture_rows()
    for row in rows:row.update(status='answer_failure',correct=False)
    report=stats.analyze_rows(records,rows)
    assert report['arms']['source_grounded']['n']==3
    assert report['arms']['source_grounded']['accuracy']==0
    assert report['both_ok']['n']==0
    assert report['both_ok']['effects']['interaction']['delta'] is None
    assert report['both_ok']['effects']['interaction']['network_bootstrap_95ci'] is None

def test_resource_report_separates_timeout_truncation_and_empty_output():
    stats=load('analyze_socialmem_answer_ablation');records,rows=fixture_rows()
    a,b,c=[r for r in rows if r['arm']=='source_grounded']
    a.update(status='judge_failure',correct=False,judge={'response':{'error':'Timeout was reached','ok':False}})
    b.update(status='judge_failure',correct=False,judge={'response':{'finish_reason':'length','ok':False}})
    c.update(status='judge_failure',correct=False,judge={'raw_xml':'','response':{'ok':True,'error':''}})
    report=stats.analyze_rows(records,rows)['arms']['source_grounded']
    assert report['stage_outcomes']['judge']=={'timeout':1,'truncated':1,'empty':1}
    assert report['judge_truncated']==1

def test_native_binding_keeps_both_historical_prompts():
    program=r'''
import importlib.util,sys
from pathlib import Path
root=Path(sys.argv[1]);p=root/'build/python/starling/_core.cpython-314-darwin.so'
spec=importlib.util.spec_from_file_location('starling._core',p)
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
assert hasattr(core,'source_answer_ablation_prompt'),'missing native ablation binding'
block='[SOURCE] {"speaker":"A","observed_at":null} text="6:30, not 7:30.\\n∆"'
assert core.source_answer_ablation_prompt('When?',block,'source','grounded')==core.grounded_source_answer_prompt('When?',block)
assert core.source_answer_ablation_prompt('When?',block,'json','synthesis')==core.synthesis_source_answer_prompt('When?',block)
try:core.source_answer_ablation_prompt('When?',block,'wrong','grounded')
except ValueError:pass
else:raise AssertionError('invalid factor reached provider boundary')
'''
    result=subprocess.run([sys.executable,'-c',program,str(ROOT)],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr

class Receipt:
    def __init__(self,text,ok=True):
        self.raw_xml=self.raw_completion=text;self.ok=ok;self.error='' if ok else 'timeout'
    def to_json(self):
        return json.dumps({'attempt_count':1,'http_attempts':[{'ok':self.ok}],
                          'ok':self.ok,'error':self.error,'total_tokens':11,
                          'raw_response':self.raw_xml,'raw_completion':self.raw_completion})

class Boundary:
    def __init__(self,response):self.response=response;self.prompts=[]
    def extract(self,prompt,system):
        self.prompts.append(prompt)
        if isinstance(self.response,Exception):raise self.response
        return self.response

@pytest.mark.parametrize('failure',[None,'answer','judge','exception'])
def test_one_answer_one_judge_no_retry_and_gold_only_in_judge(failure):
    driver=load('run_socialmem_answer_ablation')
    import run_socialmem_baseline as runner
    audit=load('eval_judge_audit')
    answer=Boundary(RuntimeError('network unknown') if failure=='exception' else Receipt('A preferred 6:30',failure!='answer'))
    judge=Boundary(Receipt('YES',failure!='judge'))
    row=driver.perform_answer({'item_id':'x','question':'When?','answer':'PRIVATE_GOLD'},'QUESTION_AND_SOURCES',runner,audit,answer,judge)
    assert row['terminal'] is True
    assert row['correct']==(failure is None)
    assert len(answer.prompts)==1
    assert len(judge.prompts)==(0 if failure in ('answer','exception') else 1)
    assert 'PRIVATE_GOLD' not in answer.prompts[0]
    if judge.prompts:assert 'PRIVATE_GOLD' in judge.prompts[0]
    if failure=='exception':assert row['budget_unknown'] is True

def test_task_started_or_sealed_cannot_send_again(tmp_path):
    driver=load('run_socialmem_answer_ablation')
    import run_socialmem_baseline as runner
    audit=load('eval_judge_audit')
    task={'item_id':'x','arm':'source_grounded','position':0,'question_order':0}
    record={'item_id':'x','question':'When?','answer':'6:30'}
    ledger=runner.BudgetLedger(tmp_path/'request-ledger.sqlite',2)
    answer,judge=Boundary(Receipt('6:30')),Boundary(Receipt('YES'))
    driver.execute_task(tmp_path,task,record,'fixed prompt',runner,audit,answer,judge,ledger,{'test':'frozen'})
    assert ledger.snapshot()['committed']==2
    with pytest.raises(ValueError):driver.execute_task(tmp_path,task,record,'fixed prompt',runner,audit,answer,judge,ledger,{'test':'frozen'})
    assert len(answer.prompts)==len(judge.prompts)==1
    (tmp_path/'completion-seal.json').write_text('{}')
    with pytest.raises(ValueError):driver.execute_task(tmp_path,{**task,'arm':'json_grounded'},record,'fixed prompt',runner,audit,answer,judge,ledger,{'test':'frozen'})
    assert len(answer.prompts)==1

def test_budget_blocks_before_provider_call(tmp_path):
    driver=load('run_socialmem_answer_ablation')
    import run_socialmem_baseline as runner
    audit=load('eval_judge_audit')
    answer,judge=Boundary(Receipt('x')),Boundary(Receipt('YES'))
    ledger=runner.BudgetLedger(tmp_path/'request-ledger.sqlite',1)
    with pytest.raises(ValueError):driver.execute_task(tmp_path,{'item_id':'x','arm':'json_grounded'},
        {'item_id':'x','question':'Who?','answer':'x'},'prompt',runner,audit,answer,judge,ledger,{})
    assert not answer.prompts and not judge.prompts

def test_statistics_executor_must_match_frozen_analyzer(tmp_path,monkeypatch):
    stats=load('analyze_socialmem_answer_ablation')
    import hashlib
    script=tmp_path/'analyze_socialmem_answer_ablation.py';script.write_text('original statistics')
    (tmp_path/'execution-plan.json').write_text(json.dumps({'files':{script.name:hashlib.sha256(script.read_bytes()).hexdigest()}}))
    monkeypatch.setattr(stats,'__file__',str(script))
    stats.verify_analyzer(tmp_path)
    script.write_text('modified statistics')
    with pytest.raises(ValueError):stats.verify_analyzer(tmp_path)

def test_terminal_score_is_replayed_from_original_judge_protocol():
    driver=load('run_socialmem_answer_ablation')
    import run_socialmem_baseline as runner
    audit=load('eval_judge_audit')
    record={'item_id':'x','question':'When?','answer':'6:30'}
    row=driver.perform_answer(record,'fixed prompt',runner,audit,Boundary(Receipt('6:30')),Boundary(Receipt('NO')))
    driver.verify_score(record,row,audit)
    for change in ('label','judge_prompt','raw_answer','joint_label','fake_failure','missing_prompt','zero_request'):
        forged=copy.deepcopy(row)
        if change=='label':forged['correct']=True
        if change=='judge_prompt':forged['judge_prompt']='Changed rubric or reference'
        if change=='raw_answer':forged['answer']['raw_xml']='Different answer'
        if change=='joint_label':forged['judge']['raw_xml']='YES';forged['correct']=True
        if change=='fake_failure':forged['status']='answer_failure'
        if change=='missing_prompt':forged.pop('judge_prompt')
        if change=='zero_request':forged['judge']['response']['attempt_count']=0;forged['judge']['response']['http_attempts']=[]
        with pytest.raises(ValueError):driver.verify_score(record,forged,audit)

def test_zero_http_initialization_failure_is_a_terminal_zero():
    driver=load('run_socialmem_answer_ablation');audit=load('eval_judge_audit')
    record={'item_id':'x','question':'When?','answer':'6:30'}
    row={'item_id':'x','terminal':True,'status':'answer_failure','correct':False,
         'answer':{'raw_xml':'','raw_completion':'','response':{
          'raw_response':'','raw_completion':'','ok':False,'error':'curl_init_failed',
          'attempt_count':0,'http_attempts':[]}}}
    driver.verify_score(record,row,audit)

def test_loaded_base_module_is_frozen_not_just_its_copy(tmp_path,monkeypatch):
    driver=load('run_socialmem_answer_ablation')
    import hashlib
    main=tmp_path/'run_socialmem_answer_ablation.py';main.write_text('driver')
    helper=tmp_path/'run_socialmem_k30_controlled.py';helper.write_text('helper')
    (tmp_path/'execution-plan.json').write_text(json.dumps({'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (main,helper)}}))
    monkeypatch.setattr(driver,'__file__',str(main));monkeypatch.setattr(driver.base,'__file__',str(helper))
    driver.verify_executor(tmp_path)
    live=tmp_path/'changed_helper.py';live.write_text('different helper')
    monkeypatch.setattr(driver.base,'__file__',str(live))
    with pytest.raises(ValueError):driver.verify_executor(tmp_path)

def test_complete_ledger_audit_rejects_tampering_and_missing_receipts(tmp_path):
    driver=load('run_socialmem_answer_ablation')
    import hashlib
    import shutil
    import sqlite3
    import run_socialmem_baseline as runner
    audit=load('eval_judge_audit')
    records=driver.select_sample(corpus());tasks=driver.task_order(records)
    driver.write(tmp_path/'execution-plan.json',{'test':'fixed'})
    fingerprint={'execution_plan_sha256':hashlib.sha256((tmp_path/'execution-plan.json').read_bytes()).hexdigest()}
    driver.write(tmp_path/'run-started.json',fingerprint);driver.write(tmp_path/'sample.json',records)
    driver.write(tmp_path/'tasks.json',tasks)
    prompts={r['item_id']:{arm:'fixed prompt' for arm in driver.ARMS} for r in records};driver.write(tmp_path/'prompts.json',prompts)
    folder=tmp_path/'frozen/scripts';folder.mkdir(parents=True);shutil.copyfile(ROOT/'scripts/eval_judge_audit.py',folder/'eval_judge_audit.py')
    ledger=runner.BudgetLedger(tmp_path/'request-ledger.sqlite',792)
    by_id={r['item_id']:r for r in records}
    for task in tasks:
        driver.execute_task(tmp_path,task,by_id[task['item_id']],'fixed prompt',runner,audit,Boundary(Receipt('A')),Boundary(Receipt('YES')),ledger,fingerprint)
    assert driver.verify_terminal(tmp_path)['actual_requests']==792
    path=next((tmp_path/'receipts').glob('*.json'));original=driver.read(path)
    for change in ('prompt','attempts','score','fingerprint','missing'):
        row=copy.deepcopy(original)
        if change=='prompt':row['prompt']='drift'
        if change=='attempts':row['answer']['response']['attempt_count']=2
        if change=='score':row['correct']=False
        if change=='fingerprint':row['fingerprint']={}
        if change=='missing':path.unlink()
        else:driver.write(path,row)
        with pytest.raises(ValueError):driver.verify_terminal(tmp_path)
        driver.write(path,original)
    with sqlite3.connect(tmp_path/'request-ledger.sqlite') as conn:conn.execute("UPDATE reservations SET actual=0 WHERE id=1")
    with pytest.raises(ValueError):driver.verify_terminal(tmp_path)
