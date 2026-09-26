"""R6.7：来源选择的冻结、完整性、单次调用与费用审计。"""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts/run_socialmem_r67_selection.py'


def driver():
    assert SCRIPT.is_file(), '缺少R6.7来源选择入口'
    spec=importlib.util.spec_from_file_location('r67_selection_test', SCRIPT)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


@pytest.mark.parametrize('stage',['prepare','select'])
def test_no_overwrite_before_loading_input(tmp_path,stage):
    m=driver();out=tmp_path/'exists';out.mkdir()
    with pytest.raises(ValueError,match='already exists'):getattr(m,stage)(tmp_path/'missing',out)


def test_wrong_origin_refused_before_output(tmp_path):
    m=driver();origin=tmp_path/'bad';origin.mkdir();(origin/'seal.json').write_text('{}')
    with pytest.raises(ValueError):m.prepare(origin,tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_historical_dependency_discovery_is_scoped_and_restored():
    m=driver();owner=m.e.builder.old;before=owner.source_paths
    archived=m.read(m.DEFAULT_ORIGIN/'program.json')['files']
    added=m.ROOT/'src/retrieval/source_selection.cpp'
    assert added in before() and 'src/retrieval/source_selection.cpp' not in archived
    with m.historical_dependencies(m.DEFAULT_ORIGIN):
        assert added not in owner.source_paths()
        assert m.ROOT/'src/retrieval/source_retriever.cpp' in owner.source_paths()
    assert owner.source_paths is before and added in owner.source_paths()


def test_reading_new_contexts_does_not_mutate_historical_strategy_table(tmp_path):
    m=driver();before=m.e.ablation.ARMS;item='fixture';gid='scope'
    row=dict(item_id=item,group_id=gid,arm='v9',strategy='evidence_profile_v9',mode='sources',k=20,
        database_sha256='db',core_sha256=m.CORE_SHA256,terminal=True,status='ok',embedding_requests=0,
        holders=['Alice'],recall=dict(source_count=0,statement_count=0,source_refs=[],statement_ids=[],receipts=[],
            block='',context_bytes=0,source_context_bytes=0,statement_context_bytes=0,source_diagnostics={}))
    m.write(tmp_path/'v9/recalls'/(m.e.text_sha(item)+'.json'),row)
    m.read_rows(tmp_path,[dict(item_id=item)],{gid:'db'},arms=('v9',))
    assert m.e.ablation.ARMS is before


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    m=driver();cache={};original=m.load_inputs
    def inputs(origin):
        m.previous.parent.verify_pinned(origin,m.ORIGIN_SEAL)
        if not cache:cache.update(original(origin))
        return cache
    m.load_inputs=inputs
    out=tmp_path_factory.mktemp('r67-prepare')/'prepare'
    result=m.prepare(m.DEFAULT_ORIGIN,out)
    assert result['external_requests']==0
    return m,out,m.check(out)


def test_full_native_pools_and_historical_controls(prepared):
    m,out,data=prepared;p=m.read(out/'plan.json');s=data['summary']
    assert p['questions']==133 and p['selection_http_budget']==133 and p['max_retries']==0
    assert s['control_mismatches']==0 and s['new_embedding_requests']==0
    assert s['pool_count']==133 and s['complete_pools']==133
    assert p['core_sha256']!=m.e.CORE_SHA256
    assert len(p['database_sha256'])==8
    assert all(x['pool']['source_count']==x['pool']['source_diagnostics']['eligible_sources'] for x in m.pool_rows(out).values())
    for row in m.pool_rows(out).values():
        assert row['prompt_sha256']==m.e.text_sha(row['prompt'])
        assert 'evidence_anchors' not in row['prompt'] and 'engram_ref' not in row['prompt']


def reseal(m,out):
    seal=m.read(out/'seal.json');files=m.inventory(out);files.pop('seal.json');seal['files']=files;m.write(out/'seal.json',seal)


@pytest.mark.parametrize('fault',['pool','missing','prompt','control','summary','core'])
def test_resealed_preparation_drift_rejected(prepared,tmp_path,fault):
    m,source,_=prepared;out=tmp_path/'copy';shutil.copytree(source,out)
    if fault in ('pool','missing','prompt'):
        p=next((out/'pools').glob('*.json'));r=m.read(p)
        if fault=='missing':p.unlink()
        else:
            if fault=='pool':r['pool']['source_diagnostics']['eligible_sources']+=1
            else:r['prompt']+=' forged';r['prompt_sha256']=m.e.text_sha(r['prompt'])
            m.write(p,r)
    elif fault=='control':
        p=next((out/'v9/recalls').glob('*.json'));r=m.read(p);r['recall']['block']+=' forged';m.write(p,r)
    elif fault=='summary':
        p=out/'summary.json';r=m.read(p);r['complete_pools']=0;m.write(p,r)
    else:
        p=next((out/'native-runtime/frozen/python/starling').glob('_core*.so'));p.write_bytes(p.read_bytes()+b'changed')
    reseal(m,out)
    with pytest.raises(ValueError):m.check(out)


def test_native_http_selection_failure_and_accounting(prepared,tmp_path):
    m,source,_=prepared
    # 独立进程载新核心，真实localhost HTTP验证，不在Python实现选择规则。
    code=r'''
import importlib.util,json,sys,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
spec=importlib.util.spec_from_file_location('selection',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=Path(sys.argv[2]);out=Path(sys.argv[3]);out.mkdir();core,*_=m.native_modules(p)
rows=m.pool_rows(p);task=next(iter(rows.values()));calls=[];mode=['ok']
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_POST(self):
        request=json.loads(self.rfile.read(int(self.headers['Content-Length'])));calls.append(request)
        raw=dict(choices=[dict(message=dict(content='{"source_ids":[1,2]}' if mode[0]!='bad_ids' else '{"source_ids":[9999]}'),finish_reason='length' if mode[0]=='truncated' else 'stop')])
        if mode[0]!='missing_usage':raw['usage']=dict(prompt_tokens=20,completion_tokens=5,total_tokens=25)
        body=json.dumps(raw).encode();self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
s=ThreadingHTTPServer(('127.0.0.1',0),Handler);t=threading.Thread(target=s.serve_forever,daemon=True);t.start()
config=m.read(p/'config.json');config['answer_endpoint']=f'http://127.0.0.1:{s.server_port}/v1'
import os
os.environ[config['answer_key_env']]='localhost-fixture'
try:
    for kind in ('ok','bad_ids','truncated','missing_usage'):
        mode[0]=kind;dest=out/kind;dest.mkdir();ledger=m.e.make_ledger(dest/'request-ledger.sqlite',1)
        adapter=m.make_adapter(core,config)
        row=m.execute_selection(task,dest,core,ledger,adapter)
        assert row['native_invoked'] and row['accounting']['observed_http_attempts']==1
        checked=m.audit_selection(task,row,dest,core)
        assert checked['state']=='settled' and checked['actual']==1
        assert row['status']==('ok' if kind=='ok' else 'error')
        if kind=='missing_usage':assert row['accounting']['total_tokens'] is None
        if kind=='ok':assert row['recall']['source_count']==2
        else:assert row['recall']['source_count']==0
        assert (dest/'started'/(m.e.text_sha('selector/'+task['item_id'])+'.json')).is_file()
    assert len(calls)==4 and all(c['model']=='qwen3.8-27b' and c['max_tokens']==512 and c['enable_thinking'] is False for c in calls)
    # 耗尽账本必须在调用前拒绝。
    dest=out/'exhausted';dest.mkdir();ledger=m.e.make_ledger(dest/'request-ledger.sqlite',0)
    try:m.execute_selection(task,dest,core,ledger,m.make_adapter(core,config))
    except ValueError:pass
    else:raise AssertionError('exhausted ledger allowed request')
    assert len(calls)==4
finally:s.shutdown();s.server_close();t.join()
'''
    result=subprocess.run([sys.executable,'-B','-c',code,str(SCRIPT),str(source),str(tmp_path/'http')],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_interruption_before_worker_is_sealed_and_independently_auditable(prepared,tmp_path,monkeypatch):
    m,source,_=prepared;out=tmp_path/'interrupted';original=m.invoke_worker
    def interrupt(stage,*args,**kwargs):
        if stage=='_select_worker':raise KeyboardInterrupt('fixture before worker')
        return original(stage,*args,**kwargs)
    monkeypatch.setattr(m,'invoke_worker',interrupt)
    with pytest.raises(KeyboardInterrupt):m.select(source,out)
    assert m.read(out/'seal.json')['state']=='incomplete'
    result=m.check(out)['summary']
    assert result['state']=='incomplete' and result['terminal_count']==0
    assert result['observed_http_attempts']==0 and result['ledger']['committed']==0
    assert result['unresolved_reservations']==[]
