"""R6.6同期QA：原生HTTP配置、逐臂上下文、费用与失败终态合同。"""
from collections import Counter
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import threading

import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts/run_socialmem_r66_evaluate.py'


def driver():
    assert SCRIPT.is_file(),'缺少R6.6同期QA入口'
    spec=importlib.util.spec_from_file_location('r66_qa_test',SCRIPT)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


@pytest.mark.parametrize('stage',['prepare','qa'])
def test_cannot_overwrite_before_loading_inputs(tmp_path,stage):
    m=driver();out=tmp_path/'exists';out.mkdir()
    with pytest.raises(ValueError,match='already exists'):getattr(m,stage)(tmp_path/'missing',out)


def test_unqualified_offline_refused_before_creating_output(tmp_path):
    m=driver();origin=tmp_path/'bad';origin.mkdir();(origin/'seal.json').write_text('{}')
    with pytest.raises(ValueError):m.prepare(origin,tmp_path/'out')
    assert not (tmp_path/'out').exists()


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    m=driver();original=m.load_inputs;cache={}
    def inputs(origin):
        assert Path(origin).resolve()==m.DEFAULT_OFFLINE
        m.offline.verify_seal(Path(origin))
        if not cache:cache.update(original(origin))
        return cache
    m.load_inputs=inputs
    with pytest.MonkeyPatch.context() as patch:
        def forbidden(*a,**k):pytest.fail('准备阶段构造provider')
        patch.setattr(m,'make_adapters',forbidden)
        out=tmp_path_factory.mktemp('r66-qa-prepare')/'prepare'
        result=m.prepare(m.DEFAULT_OFFLINE,out);data=m.check(out)
    assert result['new_external_requests']==0
    return m,out,data


def test_same_1024_factory_paired_contexts_and_two_core_identities(prepared):
    m,out,data=prepared;tasks=data['tasks'];plan=m.read(out/'execution-plan.json')
    assert len(tasks)==len({(t['item_id'],t['arm']) for t in tasks})==266
    assert Counter(t['arm'] for t in tasks)=={'v9':133,'v10':133}
    assert Counter(t['arm'] for t in tasks[::2])=={'v9':67,'v10':66}
    assert plan['retrieval_core_sha256']==m.offline.CORE_SHA256!=plan['answer_core_sha256']==m.e.CORE_SHA256
    assert plan['http_budget']==478 and plan['answer_max_tokens']==1024
    assert plan['control_fresh'] is True and plan['candidate_fresh'] is True
    assert sum(l['prompt']!=r['prompt'] for l,r in zip(tasks[::2],tasks[1::2]))==38
    for task in tasks:
        row=data['contexts'][task['arm']][task['item_id']]
        assert task['recall']==row['recall']
        assert task['policy']=='grounded_memory_v1'
    assert data['checked']['config']['answer_max_tokens']==512
    assert m.answer_config(data['checked'])['answer_max_tokens']==1024


def test_gold_does_not_enter_answer_prompt(prepared):
    m,_,data=prepared;checked=dict(data['checked']);records=deepcopy(checked['records'])
    for r in records:r['answer']='GOLD_CANARY';r['source']['evidence_anchors']=[]
    checked['records']=records
    tasks=m.make_tasks(checked,data['contexts'],data['runner'],data['modules'])
    assert [t['prompt'] for t in tasks]==[t['prompt'] for t in data['tasks']]


@pytest.fixture(scope='module')
def localhost_qa(prepared,tmp_path_factory):
    m,source,data=prepared;calls=[];lock=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_POST(self):
            request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            with lock:calls.append(request)
            raw=json.dumps(dict(choices=[dict(message=dict(content='yes' if request['max_tokens']==64 else '0'),finish_reason='stop')],
                usage=dict(prompt_tokens=10,completion_tokens=2,total_tokens=12))).encode()
            self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    factory=data['runner']._make_native_adapters
    def local_factory(core,config):
        config=dict(config)
        for role in ('extract','answer','embedding'):config[role+'_endpoint']=f'http://127.0.0.1:{server.server_port}/v1'
        return factory(core,config)
    out=tmp_path_factory.mktemp('r66-qa')/'qa'
    try:
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv('DASHSCOPE_API_KEY','localhost-fixture');patch.setattr(data['runner'],'_make_native_adapters',local_factory)
            result=m.qa(source,out,workers=4)
    finally:server.shutdown();server.server_close();thread.join()
    return m,out,result,calls


def test_real_native_factory_and_independent_accounting(localhost_qa):
    m,out,result,calls=localhost_qa
    assert result['state']=='complete' and result['terminal_count']==result['healthy_terminals']==266
    assert Counter(r['max_tokens'] for r in calls)=={1024:266,64:212}
    assert all(r['model']=='qwen3.8-27b' for r in calls)
    assert all(r.get('enable_thinking') is False for r in calls if r['max_tokens']==1024)
    assert all('enable_thinking' not in r for r in calls if r['max_tokens']==64)
    assert result['observed_http_attempts']==result['ledger']['committed']==478
    assert result['known_tokens']==result['total_tokens']==5736
    assert result['comparison']['denominator']==133 and result['automatic_promotion'] is False
    assert set(result['arms'])=={'v9','v10'}
    before=m.inventory(out);assert m.check(out)['summary']==result;assert m.inventory(out)==before


def reseal(m,out):
    s=m.read(out/'seal.json');files=m.inventory(out);files.pop('seal.json');s['files']=files;m.write(out/'seal.json',s)


@pytest.mark.parametrize('fault',['answer','prompt','context','started','ledger','summary','core'])
def test_resealed_qa_drift_rejected(localhost_qa,tmp_path,fault):
    m,source,_,_=localhost_qa;out=tmp_path/'copy';shutil.copytree(source,out)
    if fault in ('answer','prompt','context'):
        p=next((out/'answers').glob('*/*/*.json'));r=m.read(p)
        if fault=='answer':r['correct']=not r['correct']
        elif fault=='prompt':r['prompt']+=' forged'
        else:r['context_sha256']='forged'
        m.write(p,r)
    elif fault=='started':
        p=next((out/'started').glob('*.json'));r=m.read(p);r['native_invoked']=False;m.write(p,r)
    elif fault=='ledger':
        with sqlite3.connect(out/'request-ledger.sqlite') as db:db.execute('UPDATE reservations SET actual=0')
    elif fault=='core':
        p=out/'execution-plan.json';r=m.read(p);r['retrieval_core_sha256']=m.e.CORE_SHA256;m.write(p,r)
    else:
        p=out/'summary.json';r=m.read(p);r['known_tokens']=0;m.write(p,r)
    reseal(m,out)
    with pytest.raises(ValueError):m.check(out)


def test_missing_usage_retains_fixed_denominator(prepared,tmp_path,monkeypatch):
    m,source,data=prepared
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            raw=b'{"choices":[{"message":{"content":"0"},"finish_reason":"length"}]}'
            self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    factory=data['runner']._make_native_adapters
    def local_factory(core,config):
        config=dict(config)
        for role in ('extract','answer','embedding'):config[role+'_endpoint']=f'http://127.0.0.1:{server.server_port}/v1'
        return factory(core,config)
    monkeypatch.setenv('DASHSCOPE_API_KEY','localhost-fixture');monkeypatch.setattr(data['runner'],'_make_native_adapters',local_factory)
    try:result=m.qa(source,tmp_path/'missing-usage')
    finally:server.shutdown();server.server_close();thread.join()
    assert result['state']=='complete' and result['questions']==133 and result['terminal_count']==266
    assert result['healthy_terminals']==0 and result['total_tokens'] is None
    assert result['missing_token_usage']==266 and result['known_tokens']==0
    assert result['observed_http_attempts']==266
    assert all(a['correct']==0 and a['questions']==133 for a in result['arms'].values())


def test_interruption_is_sealed_without_retries(prepared,tmp_path,monkeypatch):
    m,source,_=prepared;out=tmp_path/'interrupted'
    def stop(*a,**k):raise KeyboardInterrupt('fixture interruption before HTTP')
    monkeypatch.setattr(m,'make_adapters',stop)
    result=m.qa(source,out)
    assert result['state']=='incomplete' and result['questions']==133 and result['terminal_count']==0
    assert m.read(out/'seal.json')['state']=='incomplete'
    assert m.check(out)['summary']==result
