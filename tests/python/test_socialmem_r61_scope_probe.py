"""R6.1 独立候选探测的真实边界测试；不调用外部 provider。"""
import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/run_socialmem_r61_scope_probe.py'


def driver():
    assert SCRIPT.is_file(), 'R6.1 scope probe entry is required'
    spec = importlib.util.spec_from_file_location('r61_scope_probe_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_sources_are_bound_to_failed_r60_holder_and_full_payload():
    m = driver()
    inputs = m.fixed_inputs()
    assert set(inputs) == {'Lionel', 'Miriam'}
    for holder, source in inputs.items():
        assert source['receipt']['claim_batches_complete'] is False
        assert source['receipt']['failure_category'] == 'batch_scope_failure'
        assert source['original_plan']['source_payload_hash'] == m.text_sha(source['payload'])
        assert source['binding']['payload_sha256'] == m.text_sha(source['payload'])
        assert len(source['original_plan']['batches']) == (3 if holder == 'Lionel' else 2)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_tasks_interleave_complete_holders_with_exact_native_bounds():
    m = driver()
    inputs = m.fixed_inputs()
    tasks = m.fixed_tasks(inputs)
    assert [(t['holder'], t['revision']) for t in tasks] == [
        ('Lionel', 'old'), ('Lionel', 'candidate'), ('Miriam', 'candidate'), ('Miriam', 'old')]
    assert [t['request_upper_bound'] for t in tasks] == [9, 9, 6, 6]
    wrong = deepcopy(inputs)
    wrong['Miriam']['original_plan']['belief_request_upper_bound'] += 1
    with pytest.raises(ValueError, match='bound'):
        m.fixed_tasks(wrong)


@pytest.mark.parametrize('stage', ['prepare', 'run'])
def test_existing_output_is_rejected_before_input_loading(tmp_path, stage):
    m = driver()
    out = tmp_path / 'exists'
    out.mkdir()
    with pytest.raises(ValueError, match='already exists'):
        if stage == 'prepare':
            m.prepare(out, tmp_path / 'missing.so', '0' * 64)
        else:
            m.run(tmp_path / 'missing', out)


def test_prepare_rejects_core_mismatch_and_old_core_as_candidate(tmp_path):
    m = driver()
    candidate = tmp_path / '_core.so'
    candidate.write_bytes(b'not a native core')
    with pytest.raises(ValueError, match='candidate core'):
        m.prepare(tmp_path / 'bad', candidate, '0' * 64)
    assert not (tmp_path / 'bad').exists()
    with pytest.raises(ValueError, match='candidate core'):
        m.prepare(tmp_path / 'same', m.OLD_CORE, m.OLD_SHA)
    assert not (tmp_path / 'same').exists()


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_candidate_gate_requires_complete_nonempty_native_terminals():
    m = driver()
    tasks = m.fixed_tasks(m.fixed_inputs())
    good = [dict(t, status='passed', statement_count=1, native_replay={'verified': True},
                 accounting={'healthy_http': True, 'usage_complete': True,
                             'local_attempt_count_unknown': False, 'remote_execution_unknown': False}) for t in tasks]
    assert m.candidate_passed(good, tasks)
    assert not m.candidate_passed(good[:3], tasks)
    for field, value in [('status', 'protocol_failure'), ('statement_count', 0),
                         ('native_replay', {'verified': False})]:
        bad = deepcopy(good)
        bad[1][field] = value
        assert not m.candidate_passed(bad, tasks)
    bad = deepcopy(good)
    bad[1]['accounting']['remote_execution_unknown'] = True
    assert not m.candidate_passed(bad, tasks)
    bad = deepcopy(good)
    bad[1]['revision'] = 'old'
    assert not m.candidate_passed(bad, tasks)


def test_raw_http_integrity_required_for_admissible_terminal():
    m = driver()
    assert m.can_continue({'status': 'protocol_failure', 'accounting': {
        'healthy_http': True, 'usage_complete': True, 'local_attempt_count_unknown': False,
        'remote_execution_unknown': False}, 'native_replay': {'verified': True}})
    assert not m.can_continue({'status': 'technical_failure', 'accounting': {
        'healthy_http': False, 'usage_complete': False, 'local_attempt_count_unknown': True,
        'remote_execution_unknown': True}, 'native_replay': {'verified': False}})

NATIVE_CASE = r'''
import importlib.util,json,subprocess,sys,tempfile,threading,os
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
spec=importlib.util.spec_from_file_location('r61',Path('scripts/run_socialmem_r61_scope_probe.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
root=Path(tempfile.mkdtemp(prefix='r61-integration-'))
candidate=next(Path('build/socialmem_20260926_r61_work/cmake/python/starling').glob('_core*.so'))
prepared=root/'prepare';m.prepare(prepared,candidate,m.sha(candidate))
calls=[];behavior='normal'
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  calls.append(request)
  prompt=request['messages'][-1]['content']
  if 'Check every unchanged candidate' in prompt:
   content='{"schema_version":1,"decisions":[{"index":0,"retain":true,"reason":"supported"}]}'
  else:
   data=json.loads(prompt.split('SOURCE_DATA_JSON:\n')[1].split('\n')[0]);holder=data['source_holder']
   if data['batch_index']!=0:rows=[]
   else:
    corrected='PROTOCOL_CORRECTION_ERRORS_JSON:' in prompt
    clause=('c0' if holder=='Lionel' else 'c6') if corrected else ('c8' if holder=='Lionel' else 'c12')
    obj='the canal route is solid' if holder=='Lionel' else 'Solo running has its place'
    rows=[dict(holder=holder,holder_perspective='FIRST_PERSON',subject=holder,subject_kind='cognizer',
       predicate='believes',object=obj,modality='BELIEVES',polarity='POS',nesting_depth=0,confidence=None,
       evidence=dict(clause_id=clause,actor=holder,attributed_to=None,assertion_scope='ASSERTED',
                     scope_markers=['ASSERTED'],time_text='',topic=None,event_time=None))]
   content=json.dumps(dict(schema_version=2,statements=rows))
  body=dict(choices=[dict(message=dict(content=content,refusal=None),finish_reason='stop')],
            usage=dict(prompt_tokens=10,completion_tokens=2,total_tokens=12))
  if behavior=='missing_usage':body.pop('usage')
  raw=json.dumps(body).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)))
  self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
original=m.worker_call
def fixture_worker(prepared,revision,action,task=None,out=None):
 if action!='execute':return original(prepared,revision,action,task,out)
 code="""
import importlib.util,json,os,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('r61',Path('scripts/run_socialmem_r61_scope_probe.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def adapter(core,config):
 os.environ['R61_FIXTURE_KEY']='offline-fixture'
 with m.paired.helpers.baseline._provider_environment('R61_FIXTURE_KEY',sys.argv[5]):
  native=core.OpenAIAdapterConfig.from_env()
 native.model=config['extract_model'];native.max_tokens=8192;native.timeout_ms=120000;native.max_retries=0;native.enable_thinking=False
 return core.OpenAIAdapter(native)
m.paired.make_adapter=adapter
result=m.worker(Path(sys.argv[1]),sys.argv[2],'execute',sys.argv[3],Path(sys.argv[4]))
print(json.dumps(result))
"""
 p=subprocess.run([sys.executable,'-c',code,str(prepared),revision,task['task_id'],str(out),
      f'http://127.0.0.1:{server.server_port}/v1'],text=True,capture_output=True)
 if p.returncode:raise ValueError(p.stderr)
 return json.loads(p.stdout)
m.worker_call=fixture_worker
'''


def native_case(code):
    import subprocess
    import sys
    result = subprocess.run([sys.executable, '-c', NATIVE_CASE + '\n' + code], cwd=ROOT,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_two_isolated_native_cores_replay_scope_correction_and_reject_resealed_tampering():
    native_case(r'''
out=root/'run';summary=m.run(prepared,out)
assert summary['candidate_passed'],summary
assert [t['status'] for t in summary['tasks']]==['protocol_failure','passed','passed','protocol_failure'],summary
assert [t['protocol_correction_requests'] for t in summary['tasks']]==[0,1,1,0]
assert summary['observed_requests']==len(calls)==11
assert summary['ledger']['committed']==11 and summary['ledger']['reserved']==0
assert summary['total_tokens']==132
before=m.inventory(out);before_calls=len(calls)
assert m.check(out)==summary and m.inventory(out)==before and len(calls)==before_calls
m.write(out/'summary.json',{**summary,'observed_requests':0})
(out/'seal.json').unlink();m.seal(out,'run','complete')
try:m.check(out)
except ValueError:pass
else:raise AssertionError('resealed false summary accepted')
m.write(out/'summary.json',summary)
path=out/'tasks/Lionel-candidate/native-receipt.json';receipt=m.read(path)
receipt['attempts'][0]['extraction']['http_attempts'][0]['response_body']='{}'
m.write(path,receipt)
(out/'seal.json').unlink();m.seal(out,'run','complete')
try:m.check(out)
except ValueError:pass
else:raise AssertionError('resealed false HTTP evidence accepted')
''')


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_missing_http_usage_stops_after_one_task_without_candidate_promotion():
    native_case(r'''
behavior='missing_usage';out=root/'run';summary=m.run(prepared,out)
assert summary['state']=='incomplete' and not summary['candidate_passed']
assert len(calls)==len(summary['tasks'])==1
assert summary['tasks'][0]['status']=='technical_failure'
assert summary['total_tokens'] is None and summary['ledger']['reserved']==0
assert m.check(out)==summary
''')


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_worker_failure_is_sealed_and_never_becomes_candidate_success():
    native_case(r'''
def broken(*args,**kwargs):raise RuntimeError('injected worker failure before request')
m.worker_call=broken
out=root/'run'
# 准入仍调用无请求原生 plan；仅注入 execute 故障。
def execute_failure(prepared,revision,action,task=None,out=None):
 if action=='execute':return broken()
 return original(prepared,revision,action,task,out)
m.worker_call=execute_failure
summary=m.run(prepared,out)
assert summary['state']=='incomplete' and not summary['candidate_passed'] and calls==[]
assert summary['stage_failures'] and summary['ledger']['reserved']==0
assert m.check(out)==summary
''')
