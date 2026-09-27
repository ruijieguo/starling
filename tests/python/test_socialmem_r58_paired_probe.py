"""R5.8 fixed paired probe orchestration, offline fixtures only."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts/run_socialmem_r58_paired_probe.py'


def driver():
    assert SCRIPT.is_file(),'independent R5.8 paired probe entry is required'
    spec=importlib.util.spec_from_file_location('r58_probe_test',SCRIPT)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def plans():
    return {holder:{arm:dict(belief_request_upper_bound=bound) for arm in ('A','B')}
            for holder,bound in (('Mum',6),('Kwame',15))}


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_fixed_history_inputs_preserve_exact_mum_and_kwame_payloads():
    m=driver();inputs=m.fixed_inputs()
    assert inputs['Mum']['binding']['payload_bytes']==3807
    assert inputs['Mum']['binding']['payload_sha256']=='91c41782d532083501e8361d2cfbb978480abe9138c41ec7aa7587cf6cc57535'
    assert inputs['Kwame']['binding']['payload_bytes']==12133
    assert inputs['Kwame']['binding']['payload_sha256']=='739a240bde63ee1286da19474305fb620be683fd48f4bf29defd3144cac7fab9'
    assert inputs['Mum']['binding']['source_link']=='source_documents'
    assert inputs['Kwame']['binding']['source_link']=='remember_prepare_and_commit'


def test_paired_task_order_and_total_budget_are_fixed():
    m=driver();tasks=m.fixed_tasks(plans())
    assert [t['task_id'] for t in tasks]==['Mum1-A','Mum1-B','Mum2-B','Mum2-A','Kwame1-A','Kwame1-B']
    assert [t['request_upper_bound'] for t in tasks]==[6,6,6,6,15,15]
    assert sum(t['request_upper_bound'] for t in tasks)==54
    wrong=plans();wrong['Mum']['B']['belief_request_upper_bound']=7
    with pytest.raises(ValueError):m.fixed_tasks(wrong)


@pytest.mark.parametrize('stage',['prepare','run'])
def test_existing_output_refused_before_reading_or_loading_any_input(tmp_path,stage):
    m=driver();out=tmp_path/'exists';out.mkdir()
    with pytest.raises(ValueError,match='already exists'):
        m.prepare(out,core_sha256='0'*64) if stage=='prepare' else m.run(tmp_path/'missing',out)


def test_candidate_core_must_be_explicit_and_match_before_freezing(tmp_path):
    m=driver()
    with pytest.raises(ValueError,match='candidate core'):m.prepare(tmp_path/'missing-sha',core_sha256=None)
    with pytest.raises(ValueError,match='candidate core'):m.prepare(tmp_path/'wrong-sha',core_sha256='0'*64)
    assert not (tmp_path/'missing-sha').exists() and not (tmp_path/'wrong-sha').exists()


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_fixed_historical_seal_is_checked_before_payload_sql(monkeypatch):
    m=driver();wrong=deepcopy(m.HISTORY);wrong['Mum']['seal_sha256']='0'*64
    monkeypatch.setattr(m,'HISTORY',wrong)
    with pytest.raises(ValueError,match='historical seal'):m.fixed_inputs()


def raw_response(text='{"schema_version":2,"statements":[]}',contract='claim_extraction_v2'):
    usage=dict(prompt_tokens=10,completion_tokens=2,total_tokens=12)
    body=json.dumps(dict(choices=[dict(message=dict(content=text,refusal=None),finish_reason='stop')],usage=usage))
    return dict(prompt='native prompt',prompt_input_hash='hash',ok=True,error='',finish_reason='stop',refusal=False,
        raw_response=text,raw_completion=text,raw_http_response=body,output_mode='json_object',output_contract=contract,
        attempt_count=1,http_attempts=[dict(http_status=200,curl_code=0,execution_certainty='response_received',response_body=body)],**usage)


def receipt():
    return dict(attempts=[dict(extraction=raw_response(),admission=dict(called=False,attempt_count=0,http_attempts=[]))])


def test_raw_cost_uses_http_envelope_and_never_default_zero_usage():
    m=driver();good=receipt();report=m.raw_cost(good,True)
    assert report['observed_requests']==1 and report['total_tokens']==12 and report['healthy_http']
    missing=deepcopy(good);body=json.loads(missing['attempts'][0]['extraction']['http_attempts'][0]['response_body']);body.pop('usage')
    missing['attempts'][0]['extraction']['http_attempts'][0]['response_body']=json.dumps(body)
    report=m.raw_cost(missing,True)
    assert report['total_tokens'] is None and report['missing_token_usage']==1 and not report['healthy_http']
    assert m.raw_cost(None,False)['total_tokens']==0
    unknown=m.raw_cost(None,True)
    assert unknown['total_tokens'] is None and unknown['local_attempt_count_unknown'] and unknown['remote_execution_unknown']


@pytest.mark.parametrize('tamper',['native_usage','raw_content','count','finish'])
def test_raw_cost_detects_contradictory_native_and_http_metadata(tamper):
    m=driver();value=receipt();response=value['attempts'][0]['extraction']
    if tamper=='native_usage':response['total_tokens']=999
    elif tamper=='raw_content':response['raw_completion']='forged'
    elif tamper=='count':response['attempt_count']=2
    else:response['finish_reason']='length'
    assert not m.raw_cost(value,True)['healthy_http']


@pytest.mark.parametrize('choices',[[None],['bad'],[dict(message=None,finish_reason='stop')],None])
def test_malformed_http_choices_preserve_observed_cost_without_raising(choices):
    m=driver();value=receipt();response=value['attempts'][0]['extraction'];body=json.loads(response['raw_http_response'])
    if choices is None:body.pop('choices')
    else:body['choices']=choices
    raw=json.dumps(body);response['raw_http_response']=raw;response['http_attempts'][0]['response_body']=raw
    report=m.raw_cost(value,True)
    assert not report['healthy_http'] and report['observed_requests']==1 and report['known_tokens']==12


def test_structured_raw_response_and_current_schema_cannot_be_forged():
    m=driver();value=receipt();value['attempts'][0]['extraction']['raw_response']='forged semantic answer'
    assert not m.raw_cost(value,True)['healthy_http']
    value=receipt();value['attempts'][0]['extraction']['schema_sha256']='wrong'
    assert not m.raw_cost(value,True,{'claim_extraction_v2':'expected'})['healthy_http']


def test_malformed_admission_called_flag_cannot_erase_its_observed_cost():
    m=driver();value=receipt();value['attempts'][0]['admission']=raw_response(contract='claim_admission_v1')
    report=m.raw_cost(value,True)
    assert report['observed_requests']==2 and report['known_tokens']==24 and report['local_attempt_count_unknown']


@pytest.mark.parametrize('arm,status,expected',[
    ('A','passed',True),('A','protocol_failure',True),('A','technical_failure',False),
    ('B','passed',True),('B','protocol_failure',False),('B','empty_candidate',False)])
def test_continue_gate_only_accepts_control_protocol_failures(arm,status,expected):
    m=driver();assert m.allow_next(dict(arm=arm),dict(status=status)) is expected


NATIVE_SETUP=r'''
import importlib.util,json,tempfile,threading,sqlite3,os
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
spec=importlib.util.spec_from_file_location('r58',Path('scripts/run_socialmem_r58_paired_probe.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
scratch=tempfile.TemporaryDirectory(prefix='r58-native-test-');root=Path(scratch.name)
prepared=root/'prepare';core_path=next(Path('build/python/starling').glob('_core*.so'))
m.prepare(prepared,core_sha256=m.sha(core_path));checked=m.check(prepared)
core=checked['core'];calls=[];behavior='success';task_index=-1;task_calls=0
def claim(holder):
 return dict(holder=holder,holder_perspective='FIRST_PERSON',subject=holder,subject_kind='cognizer',
  predicate='feels',object='fine' if holder=='Mum' else 'proud of having my waterproofs',
  modality='BELIEVES',polarity='POS',nesting_depth=0,confidence=None,
  evidence=dict(clause_id='c3' if holder=='Mum' else 'c24',actor=holder,attributed_to=None,assertion_scope='ASSERTED',
   scope_markers=['ASSERTED'],time_text='',topic=None,event_time=None))
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  global task_calls
  request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  calls.append(request);task_calls+=1;task=checked['tasks'][task_index]
  if behavior=='control_protocol' and task_index==0:text='{}'
  elif behavior=='control_envelope' and task_index==0:text='not json'
  elif behavior=='control_scope' and task_index==0:
   row=claim(task['holder']);row['evidence']['clause_id']='c8';row['object']='slightly worried'
   text=json.dumps(dict(schema_version=2,statements=[row]))
  elif behavior=='admission_protocol' and task_index==0 and task_calls==2:text='{}'
  elif behavior=='candidate_empty' and task_index==1:text='{"schema_version":2,"statements":[]}'
  elif task['holder']=='Kwame' and task_calls<=3:text='{"schema_version":2,"statements":[]}'
  elif task['holder']=='Kwame' and task_calls==4:text=json.dumps(dict(schema_version=2,statements=[claim(task['holder'])]))
  elif task['holder']=='Kwame' and task_calls==5:text='{"schema_version":1,"decisions":[{"index":0,"retain":true,"reason":"supported"}]}'
  elif task_calls==1:text=json.dumps(dict(schema_version=2,statements=[claim(task['holder'])]))
  elif task_calls==2:text='{"schema_version":1,"decisions":[{"index":0,"retain":true,"reason":"supported"}]}'
  else:text='{"schema_version":2,"statements":[]}'
  finish='length' if behavior=='truncated' and task_index==0 else 'stop'
  body=dict(choices=[dict(message=dict(content=text,refusal=None),finish_reason=finish)],
   usage=dict(prompt_tokens=10,completion_tokens=2,total_tokens=12))
  if behavior=='missing_usage':body.pop('usage')
  raw=json.dumps(body).encode();self.send_response(200);self.send_header('Content-Type','application/json')
  self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
def adapter(core,config):
 global task_index,task_calls
 task_index+=1;task_calls=0
 os.environ['R58_FIXTURE_KEY']='offline-fixture'
 with m.helpers.baseline._provider_environment('R58_FIXTURE_KEY',f'http://127.0.0.1:{server.server_port}/v1'):
  native=core.OpenAIAdapterConfig.from_env()
 native.model=config['extract_model'];native.max_tokens=8192;native.timeout_ms=120000;native.max_retries=0
 native.enable_thinking=False
 return core.OpenAIAdapter(native)
m.make_adapter=adapter
'''


def native_case(code):
    driver()
    result=subprocess.run([sys.executable,'-c',NATIVE_SETUP+'\n'+code],cwd=ROOT,text=True,capture_output=True)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_native_prepare_binds_new_core_profiles_and_fixed_source_units():
    native_case(r'''
assert len(checked['tasks'])==6
for holder,arms in checked['plans'].items():
 assert 'claim_batch_prompt_profile' not in arms['A']
 assert arms['B']['claim_batch_prompt_profile']=='target_units_v1'
 assert arms['A']['source_units']==arms['B']['source_units']==checked['inputs'][holder]['original_plan']['source_units']
 assert arms['A']['batches']==arms['B']['batches']
assert calls==[]
before=m.inventory(prepared);m.check(prepared);assert m.inventory(prepared)==before
wrong=m.read(prepared/'tasks.json');wrong.reverse();m.write(prepared/'tasks.json',wrong)
(prepared/'seal.json').unlink();m.seal(prepared,'prepare')
try:m.check(prepared)
except ValueError:pass
else:raise AssertionError('resealed task order accepted')
''')


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('behavior,executed,status',[
    ('success',6,'paired_probe_passed'),('control_protocol',6,'paired_probe_passed'),
    ('control_envelope',6,'paired_probe_passed'),('control_scope',6,'paired_probe_passed'),
    ('admission_protocol',1,'paired_probe_stopped'),
    ('candidate_empty',2,'paired_probe_stopped'),('missing_usage',1,'paired_probe_stopped'),('truncated',1,'paired_probe_stopped')])
def test_native_paired_run_stop_rules_replay_and_read_only_check(behavior,executed,status):
    native_case(f'behavior={behavior!r}\n'+r'''
out=root/'run';summary=m.run(prepared,out)
before=m.inventory(out);audited=m.check(out)['summary'];assert audited==summary and m.inventory(out)==before
'''+f"assert len(summary['tasks'])=={executed},summary\nassert summary['status']=={status!r},summary\n"+r'''
assert len(summary['unexecuted_tasks'])==6-len(summary['tasks'])
assert summary['ledger']['reserved']==0 and summary['ledger']['committed']==len(calls)
assert all(t['native_replay']['verified'] for t in summary['tasks'])
if behavior in ('success','control_protocol','control_envelope','control_scope'):
 assert summary['candidate_passed'] and len([t for t in summary['tasks'] if t['arm']=='B' and t['statement_count']>0])==3
 assert summary['total_tokens']==12*len(calls)
else:assert not summary['candidate_passed']
if behavior.startswith('control_'):
 assert summary['tasks'][0]['status']=='protocol_failure' and summary['tasks'][0]['failure_stage']=='extraction'
 assert summary['tasks'][0]['protocol_correction_requests']==(0 if behavior=='control_scope' else 1)
if behavior=='admission_protocol':assert summary['tasks'][0]['failure_stage']=='admission'
if behavior=='success':assert all(t['candidate_count']==1 for t in summary['tasks'])
for request in calls:
 assert request['model']=='qwen3.8-27b' and request['max_tokens']==8192 and request['temperature']==0
 assert request['response_format']['type']=='json_object'
forged=m.read(out/'summary.json');forged['observed_requests']=0;m.write(out/'summary.json',forged)
(out/'seal.json').unlink();m.seal(out,'run',summary['state'])
try:m.check(out)
except ValueError:pass
else:raise AssertionError('resealed false summary accepted')
''')


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('fault',['native','settlement','terminal_write','commit_write','backup','analysis','setup'])
def test_stage_exceptions_preserve_partial_evidence_and_unknown_reservations(fault):
    native_case(f'fault={fault!r}\n'+r'''
original_write=m.write
original_analysis=m.analyze_task
if fault=='native':
 def broken(*args,**kwargs):raise RuntimeError('injected native entry exception')
 core.memory_extract_llm=broken
elif fault in ('backup','analysis','setup'):
 def broken(*args,**kwargs):raise RuntimeError('injected '+fault+' exception')
 setattr(m,{'backup':'backup','analysis':'analyze_task','setup':'remember_prepare'}[fault],broken)
elif fault=='settlement':
 def broken(*args,**kwargs):raise RuntimeError('injected ledger settlement exception')
 m.helpers.baseline.BudgetLedger.settle=broken
else:
 def broken(path,value):
  if Path(path).name==('terminal.json' if fault=='terminal_write' else 'commit.json'):
   raise RuntimeError('injected task write exception')
  return original_write(path,value)
 m.write=broken
out=root/'run';summary=m.run(prepared,out)
if fault=='analysis':m.analyze_task=original_analysis
assert summary['state']=='incomplete'
assert len(summary['tasks'])==(0 if fault=='setup' else 1)
assert len(summary['unexecuted_tasks'])==(6 if fault=='setup' else 5)
before=m.inventory(out);assert m.check(out)['summary']==summary and m.inventory(out)==before
assert summary['ledger']['reserved']==0
if fault=='native':
 assert summary['ledger']['charged_upper']==6 and summary['total_tokens'] is None and summary['local_attempt_count_unknown']
else:assert summary['observed_requests']==len(calls) and summary['known_tokens']==12*len(calls)
if fault=='setup':assert summary['total_tokens']==0 and not summary['local_attempt_count_unknown']
''')


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('tamper',['predicate','object','source_time','source_proof','raw_response','nested_usage','admission_nested_usage','ledger'])
def test_resealed_task_receipt_or_database_drift_cannot_pass_native_replay(tamper):
    native_case(f'tamper={tamper!r}\n'+r'''
behavior='candidate_empty';out=root/'run';original=m.run(prepared,out);task_dir=out/'tasks/Mum1-A'
assert original['tasks'][0]['status']=='passed',original
if tamper in ('predicate','object','source_time','source_proof'):
 with sqlite3.connect(task_dir/'frozen.db') as db:
  if tamper=='predicate':db.execute("UPDATE statements SET predicate='forged'")
  elif tamper=='object':db.execute("UPDATE statements SET object_value='forged'")
  elif tamper=='source_time':db.execute("UPDATE engrams SET created_at='1900-01-01T00:00:00Z'")
  else:db.execute("UPDATE statements SET source_spans_json='[]'")
 db.close()
elif tamper=='raw_response':
 receipt=m.read(task_dir/'native-receipt.json');receipt['attempts'][0]['extraction']['raw_response']='{}';m.write(task_dir/'native-receipt.json',receipt)
elif tamper in ('nested_usage','admission_nested_usage'):
 receipt=m.read(task_dir/'native-receipt.json');kind='admission' if tamper=='admission_nested_usage' else 'extraction'
 response=receipt['attempts'][0][kind]
 if kind=='admission':assert response['called'] is True
 assert response['total_tokens']==response['structured_output']['total_tokens']==12
 response['structured_output']['total_tokens']=999
 m.write(task_dir/'native-receipt.json',receipt)
else:
 with sqlite3.connect(out/'request-ledger.sqlite') as db:db.execute('UPDATE reservations SET actual=0 WHERE id=1')
 db.close()
# Rewriting both terminal and summary must not turn corrupted raw evidence into a healthy task.
if tamper!='ledger':
 audited=m.analyze_task(task_dir,checked,checked['tasks'][0]);assert audited['status']=='technical_failure',audited
 assert audited['evidence_errors'] or not audited['accounting']['healthy_http']
 if tamper=='admission_nested_usage':
  assert audited['accounting']['observed_requests']==3 and audited['accounting']['known_tokens']==36
  assert m.read(task_dir/'native-receipt.json')['attempts'][0]['admission']['structured_output']['total_tokens']==999
(out/'seal.json').unlink();m.seal(out,'run','incomplete')
try:m.check(out)
except ValueError:pass
else:raise AssertionError('resealed mutated evidence accepted')
''')


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('field,partial',[
    ('id',False),('id_type',False),('upper_bound',False),('state',False),('id',True)])
def test_resealed_start_reservation_must_match_exact_sqlite_ledger_row(field,partial):
    native_case(f'field={field!r};partial={partial!r}\n'+r'''
original_analyze=m.analyze_task
if partial:
 def broken(*args):raise RuntimeError('injected partial analysis for reservation binding')
 m.analyze_task=broken
out=root/'run';summary=m.run(prepared,out);m.analyze_task=original_analyze
assert summary['candidate_passed'] is (not partial)
path=out/'tasks/Mum1-A';started=m.read(path/'started.json')
key='id' if field=='id_type' else field
started['reservation'][key]={'id':999,'id_type':True,'upper_bound':5,'state':'settled'}[field]
m.write(path/'started.json',started)
try:
 audited=(m.partial_analysis_audit if partial else m.analyze_task)(path,checked,checked['tasks'][0])
 m.write(path/'terminal.json',audited);m.write(out/'summary.json',m.summarize(out,checked))
 (out/'seal.json').unlink();m.seal(out,'run',summary['state'])
 m.check(out)
except ValueError:pass
else:raise AssertionError('forged start reservation accepted independently of SQLite ledger')
''')
