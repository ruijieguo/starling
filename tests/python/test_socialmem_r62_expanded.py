"""R6.2 原生回放后恢复；本模块不调用外部模型。"""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/run_socialmem_r62_expanded.py'


def run_code(code, *args):
    assert SCRIPT.is_file(), 'R6.2 recovery runner required'
    setup = """
import importlib.util,json,sys,sqlite3
from pathlib import Path
s=importlib.util.spec_from_file_location('r62','scripts/run_socialmem_r62_expanded.py')
entry=importlib.util.module_from_spec(s);s.loader.exec_module(entry);m=entry.engine
"""
    result = subprocess.run([sys.executable, '-c', setup+code, *map(str,args)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout+result.stderr


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    out = tmp_path_factory.mktemp('r62')/'prepare'
    run_code("assert m.prepare(m.DEFAULT_PARENT,Path(sys.argv[1]))['state']=='complete'", out)
    return out


def test_new_core_replays_both_historical_scopes_without_provider(prepared):
    run_code("""
checked=m.check(Path(sys.argv[1]));q=checked['qualification_audit']['summary']
assert q['candidate_core_sha256']==m.CORE_SHA256
assert len(q['compatibility']['scopes'])==2
assert [v['final_health']['embedded'] for v in q['compatibility']['scopes'].values()]==[35,189]
assert all(v['native_replay']['verified'] for v in q['compatibility']['scopes'].values())
assert q['external_requests']==0
""", prepared)


def test_recovery_preserves_original_failure_and_rejects_metadata_forgery(prepared,tmp_path):
    run_code("""
checked=m.check(Path(sys.argv[1]));out=Path(sys.argv[2]);out.mkdir()
ledger=m.make_ledger(out/'ledger.sqlite')
m.make_adapters=lambda *_: (_ for _ in ()).throw(AssertionError('provider construction during recovery'))
for group in checked['groups'][:2]:
 scope=out/group['group_id'];result=m.run_scope(checked,group,scope,ledger)
 assert result['status']=='passed',result
 assert result['recovery']['new_external_requests']==0
 assert m.scope_audit(scope,checked,group)==result
metadata=m.read(scope/'scope.json')
assert metadata['embedding']['failed']==32
assert metadata['embedding']['final_health']['embedded']==189
assert m.read(scope/'recovery.json')['original_failure']['error']=='RuntimeError: embedding technical failures: 32'
metadata['embedding']['failed']=0;m.write(scope/'scope.json',metadata)
try:m.scope_audit(scope,checked,group)
except ValueError:pass
else:raise AssertionError('erased inherited failure accepted')
""",prepared,tmp_path/'recovered')


def test_recovery_rejects_wrong_database_and_never_mutates_history(prepared,tmp_path):
    run_code("""
checked=m.check(Path(sys.argv[1]));out=Path(sys.argv[2]);out.mkdir()
before=m.inventory(entry.HISTORY);group=checked['groups'][0]
scope=out/'scope';ledger=m.make_ledger(out/'ledger.sqlite')
result=m.run_scope(checked,group,scope,ledger);assert result['status']=='passed',result
with sqlite3.connect(scope/'frozen.db') as db:db.execute("UPDATE statement_vectors SET model='wrong'")
db.close()
try:m.scope_audit(scope,checked,group)
except ValueError:pass
else:raise AssertionError('changed inherited database accepted')
assert before==m.inventory(entry.HISTORY)
""",prepared,tmp_path/'bad')


_spec = importlib.util.spec_from_file_location('r62_fixture_helpers', ROOT/'tests/python/test_socialmem_r59_expanded.py')
_shared = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_shared)
FULL_SETUP = _shared.FULL_NATIVE_SETUP + r'''
original_post=Handler.do_POST
embedding_calls=[]
def with_embeddings(self):
 if not self.path.endswith('/embeddings'):return original_post(self)
 request=json.loads(self.rfile.read(int(self.headers['Content-Length'])));embedding_calls.append(request)
 if len(embedding_calls)==1:
  raw=b'{"error":{"message":"fixture transient"}}';self.send_response(503)
 else:
  raw=json.dumps(dict(data=[dict(index=i,embedding=[float(j==i) for j in range(1024)]) for i,_ in enumerate(request['input'])])).encode()
  self.send_response(200)
 self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
Handler.do_POST=with_embeddings
old_adapters=m.make_adapters
def native_adapters(value):
 llm,_,answer,judge=old_adapters(value)
 with m.baseline._provider_environment('R59_FIXTURE_KEY',f'http://127.0.0.1:{server.server_port}/v1'):
  cfg=core.OpenAIEmbeddingConfig.from_env()
 cfg.model='qwen3.7-text-embedding';cfg.dim=1024;cfg.max_retries=0;cfg.timeout_ms=2000
 return llm,core.OpenAIEmbeddingAdapter(cfg),answer,judge
m.make_adapters=native_adapters
'''


@pytest.fixture(scope='module')
def built(prepared,tmp_path_factory):
    root=tmp_path_factory.mktemp('r62-build')/'fixture'
    run_code(FULL_SETUP+r'''
summary=m.build(Path(sys.argv[1]),root/'build')
assert summary['state']=='complete' and summary['healthy_scopes']==8,summary
assert summary['inherited_cost']==dict(chat_requests=108,known_chat_tokens=1291057,embedding_requests=29)
assert summary['new_cost']['chat_requests']==len(calls)
assert summary['new_cost']['known_chat_tokens']==12*len(calls)
assert summary['new_cost']['embedding_requests']==len(embedding_calls)
assert summary['ledger']['reserved']==0
assert summary['extraction_conservative_charge']==851
gid=checked['groups'][2]['group_id'];metadata=m.read(root/'build/runs'/gid/'scope.json')
assert metadata['embedding']['failed']>0 and metadata['embedding']['final_health']['complete']
assert m.check(root/'build')['summary']==summary
''',prepared,root)
    return root/'build'


def test_full_recovered_build_and_independent_check(built):
    run_code("""
path=Path(sys.argv[1]);before=m.inventory(path);result=m.check(path)
assert result['summary']['healthy_scopes']==8
assert result['summary']['mode']=='revalidated_recovery'
assert before==m.inventory(path)
""",built)
