"""Bounded strict probe scheduling and sealed evidence; loopback HTTP only."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT/'scripts/run_socialmem_r57_strict_probe.py'


def worker(code, *args):
    assert SCRIPT.is_file(), 'R57 independent strict probe entry is required'
    bootstrap = """
import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('r57', 'scripts/run_socialmem_r57_strict_probe.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
"""
    result = subprocess.run([sys.executable,'-B','-c',bootstrap+code,*map(str,args)],cwd=ROOT,
                            text=True,capture_output=True)
    assert result.returncode==0,result.stdout+result.stderr
    return result.stdout


@contextmanager
def server(mode='success'):
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(request)
            contract=request['response_format']['json_schema']['name']
            status=400 if mode in ('unsupported','keyword_error') else 200
            if status==400:
                body={'error':{'message':('response_format json_schema is not supported' if mode=='unsupported' else 'Unsupported parameter: uniqueItems')}}
            else:
                content={'schema_version':1,'decisions':[]} if contract=='claim_admission_v1' else {'schema_version':2,'statements':[]}
                if mode=='bad_admission': content={'wrong':True}
                body={'choices':[{'message':{'content':json.dumps(content)},'finish_reason':'stop'}]}
                if mode!='missing_usage':body['usage']={'prompt_tokens':10,'completion_tokens':2,'total_tokens':12}
                if mode=='length':body['choices'][0]['finish_reason']='length'
                if mode=='malformed_envelope':body=[]
                if mode=='malformed_choices':body['choices']='invalid'
                if mode=='malformed_choice_item':body['choices']=[None]
            raw=json.dumps(body).encode();self.send_response(status)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
            self.end_headers();self.wfile.write(raw)
        def log_message(self,*args):pass
    http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{http.server_port}/v1',requests
    finally:http.shutdown();http.server_close();thread.join()


RUN_CODE = """
import os
os.environ['DASHSCOPE_API_KEY']='local-fixture-only'
original=m.probe_config
m.probe_config=lambda c:dict(original(c),endpoint=sys.argv[2])
out=Path(sys.argv[1]);summary=m.run(out)
assert m.check(out)==summary
print(json.dumps(summary))
"""


def test_existing_output_rejected_before_fixed_input_or_provider(tmp_path):
    worker("""
m.load_fixed=lambda: (_ for _ in ()).throw(AssertionError('input read'))
out=Path(sys.argv[1]);out.mkdir()
try:m.run(out)
except ValueError as e:assert 'exists' in str(e)
else:raise AssertionError('overwrote output')
""",tmp_path/'exists')


def test_fixed_prepare_drift_rejected_before_provider(tmp_path):
    worker("""
m.PREPARE=Path(sys.argv[1]);m.PREPARE.mkdir()
(m.PREPARE/'seal.json').write_text('{}')
m.make_adapter=lambda *_: (_ for _ in ()).throw(AssertionError('provider constructed'))
try:m.run(Path(sys.argv[2]))
except ValueError:pass
else:raise AssertionError('accepted drift')
assert not Path(sys.argv[2]).exists()
""",tmp_path/'bad-prepare',tmp_path/'out')


@pytest.fixture(scope='module')
def success(tmp_path_factory):
    out=tmp_path_factory.mktemp('r57-success')/'run'
    with server() as (endpoint,requests):
        summary=json.loads(worker(RUN_CODE,out,endpoint))
    return out,endpoint,requests,summary


def test_four_native_http_fixtures_and_readonly_check(success):
    out,endpoint,requests,summary=success
    assert summary['state']=='complete' and summary['status']=='strict_fixture_passed'
    assert summary['observed_requests']==4 and summary['observed_tokens']==48
    assert summary['ledger']==dict(budget=4,committed=4,reserved=0,charged_upper=0,remaining=0)
    assert [r['response_format']['json_schema']['name'] for r in requests]==[
        'claim_admission_v1','claim_admission_v1','claim_extraction_v2','claim_extraction_v2']
    for index,r in enumerate(requests):
        assert r['model']=='qwen3.8-27b' and r['max_tokens']==8192 and r['enable_thinking'] is False
        assert r['response_format']['type']=='json_schema' and r['response_format']['json_schema']['strict'] is True
        assert ('Contrary-format fixture:' in r['messages'][-1]['content'])==(index%2==1)
    assert 'uniqueItems' not in json.dumps(requests[0]['response_format'])
    assert 'uniqueItems' in json.dumps(requests[2]['response_format'])
    worker("""
original=m.probe_config;m.probe_config=lambda c:dict(original(c),endpoint=sys.argv[2])
m.make_adapter=lambda *_: (_ for _ in ()).throw(AssertionError('check called provider'))
assert m.check(Path(sys.argv[1]))['observed_requests']==4
""",out,endpoint)


@pytest.mark.parametrize('mode,state,tokens',[
    ('bad_admission','nonconformant',24),('unsupported','unsupported',None),
    ('missing_usage','observed_conformant',None),('length','nonconformant',24),
    ('malformed_envelope','nonconformant',None),('malformed_choices','nonconformant',24),
    ('malformed_choice_item','nonconformant',24),('keyword_error','unknown',None)])
def test_admission_failure_stops_after_native_pair(tmp_path,mode,state,tokens):
    with server(mode) as (endpoint,requests):
        summary=json.loads(worker(RUN_CODE,tmp_path/'run',endpoint))
    assert len(requests)==2
    assert summary['state']=='incomplete' and summary['status']=='strict_fixture_stopped'
    assert summary['observed_requests']==2 and summary['observed_tokens']==tokens
    assert summary['contracts'][0]['native_state']==state
    assert not (tmp_path/'run/claim_extraction_v2.evidence.json').exists()
    if tokens is None:assert summary['usage_complete'] is False and summary['missing_token_usage']==2


def test_native_exception_charges_reserved_pair_and_keeps_unknown(tmp_path):
    worker("""
class Bomb:
 def probe_structured_output(self,*_):raise RuntimeError('native fixture failure')
m.make_adapter=lambda *_:Bomb()
out=Path(sys.argv[1]);s=m.run(out)
assert s['state']=='incomplete' and s['ledger']['committed']==2
assert s['ledger']['charged_upper']==2 and s['ledger']['reserved']==0
assert s['observed_tokens'] is None and s['local_attempt_count_unknown'] and s['remote_execution_unknown']
assert m.check(out)==s
""",tmp_path/'run')


def test_logical_success_without_http_cannot_advance(tmp_path):
    with server() as (endpoint,requests):
        worker("""
import os,hashlib
from types import SimpleNamespace
os.environ['DASHSCOPE_API_KEY']='local-fixture-only'
original=m.probe_config;m.probe_config=lambda c:dict(original(c),endpoint=sys.argv[2])
factory=m.make_adapter
class NoHttp:
 def __init__(self,adapter):self.adapter=adapter
 def probe_structured_output(self,request):
  value=json.loads(self.adapter.probe_structured_output(request).to_json())
  for p in value['probes']:p['response']['http_attempts']=[];p['response']['attempt_count']=0
  value['request_count']=0;value['evidence_id']=''
  value['evidence_id']=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
  return SimpleNamespace(to_json=lambda:json.dumps(value))
m.make_adapter=lambda core,c:NoHttp(factory(core,c))
out=Path(sys.argv[1]);s=m.run(out)
assert s['state']=='incomplete' and s['local_attempt_count_unknown']
assert s['ledger']['charged_upper']==2
assert m.check(out)==s
""",tmp_path/'run',endpoint)
    assert len(requests)==2


@pytest.mark.parametrize('change',['raw','summary','schema','config','ledger','fixture_prompt','source_copy'])
def test_resealed_forgery_is_rejected(success,tmp_path,change):
    original,endpoint,_,_=success;out=tmp_path/'changed';shutil.copytree(original,out)
    worker("""
import sqlite3,hashlib
original=m.probe_config;m.probe_config=lambda c:dict(original(c),endpoint=sys.argv[2])
out=Path(sys.argv[1]);change=sys.argv[3]
if change in ('raw','fixture_prompt'):
 p=out/'claim_admission_v1.evidence.json';v=m.read(p)
 if change=='raw':v['probes'][0]['response']['raw_completion']='{}'
 else:
  v['probes'][0]['prompt']='unrelated prompt';v['evidence_id']=''
  v['evidence_id']=hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
 m.write(p,v)
elif change=='summary':
 p=out/'summary.json';v=m.read(p);v['observed_tokens']=0;m.write(p,v)
elif change=='schema':
 p=out/'schemas.json';v=m.read(p);v['claim_admission_v1']['schema']='{}';m.write(p,v)
elif change=='config':
 p=out/'config.json';v=m.read(p);v['max_retries']=1;m.write(p,v)
elif change=='source_copy':(out/'source/scripts/run_socialmem_r57_strict_probe.py').write_text('# forged')
else:
 with sqlite3.connect(out/'request-ledger.sqlite') as db:db.execute('update reservations set actual=0')
(out/'seal.json').unlink();m.seal(out)
try:m.check(out)
except ValueError:pass
else:raise AssertionError('re-sealed forgery accepted: '+change)
""",out,endpoint,change)


def test_internal_native_catch_preserves_partial_usage_and_charges_upper(tmp_path):
    with server() as (endpoint,requests):
        worker("""
import os
from types import SimpleNamespace
os.environ['DASHSCOPE_API_KEY']='local-fixture-only'
original=m.probe_config;m.probe_config=lambda c:dict(original(c),endpoint=sys.argv[2])
factory=m.make_adapter
class Partial:
 def __init__(self,adapter):self.adapter=adapter
 def probe_structured_output(self,request):
  value=json.loads(self.adapter.probe_structured_output(request).to_json())
  value['probes']=value['probes'][:1];value['request_count']=1;value['evidence_id']=''
  value['state']='unknown';value['error']='internal native fixture exception'
  return SimpleNamespace(to_json=lambda:json.dumps(value))
m.make_adapter=lambda core,c:Partial(factory(core,c))
out=Path(sys.argv[1]);s=m.run(out)
assert s['state']=='incomplete' and s['observed_requests']==1 and s['known_tokens']==12
assert s['observed_tokens'] is None and s['missing_token_usage']==1
assert s['ledger']['committed']==2 and s['ledger']['charged_upper']==2
assert s['contracts'][0]['native_state']=='unknown' and s['contracts'][0]['native_validation_error']
assert m.check(out)==s
""",tmp_path/'run',endpoint)
    assert len(requests)==2


def test_source_change_during_run_cannot_seal_success(tmp_path):
    with server() as (endpoint,requests):
        worker("""
import os
os.environ['DASHSCOPE_API_KEY']='local-fixture-only'
original=m.probe_config;m.probe_config=lambda c:dict(original(c),endpoint=sys.argv[2])
factory=m.make_adapter;real_sha=m.sha
class Drift:
 def __init__(self,adapter):self.adapter=adapter
 def probe_structured_output(self,request):
  result=self.adapter.probe_structured_output(request)
  m.sha=lambda path: '0'*64 if Path(path)==m.ROOT/m.SOURCES[0] else real_sha(path)
  return result
m.make_adapter=lambda core,c:Drift(factory(core,c))
out=Path(sys.argv[1]);s=m.run(out)
assert s['state']=='incomplete' and s['execution_sources_unchanged'] is False
assert s['observed_requests']==4 and s['ledger']['committed']==4
assert m.check(out)==s
""",tmp_path/'run',endpoint)
    assert len(requests)==4
