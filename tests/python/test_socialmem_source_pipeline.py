"""来源数据适配不得引入评分答案；原生选择与请求预算的装配边界。"""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

runner = load('run_socialmem_baseline')
pipe = load('eval_ladder_pipeline')
HISTORY = [{'speaker':'Ada', 'text':'I prefer blue murals.',
            'observed_at':'2026-03-01T10:00:00', 'turn_id':'s1_t1',
            'session_index':1, 'message_index':1, 'answer':'DO_NOT_SEND',
            'evidence_anchor':'DO_NOT_SEND'}]


def test_retention_maps_only_public_source_fields():
    assert hasattr(runner, 'retain_history_sources'), 'source ingestion adapter missing'
    captured = []
    def retain(*args):
        captured.append(args)
        return '{"documents":1,"turns":1,"engram_refs":["e1"]}'
    result = runner.retain_history_sources(SimpleNamespace(retain_source_turns=retain),
                                          'adapter', HISTORY, '2026-06-01T00:00:00Z')
    args = captured[0]
    assert args[:3] == ('adapter', 'default', ['Ada'])
    assert 'DO_NOT_SEND' not in args[3]
    source = json.loads(args[3])[0]
    assert source == {'speaker':'Ada','text':'I prefer blue murals.',
                      'observed_at':'2026-03-01T10:00:00','turn_id':'s1_t1',
                      'session_id':'1','turn_index':1}
    assert result['turns'] == 1


def test_observer_passes_explicit_scope_and_preserves_native_selection():
    assert hasattr(pipe, 'recall_observer_block'), 'native observer adapter missing'
    calls = []
    native_result = {'block':'[SOURCE] native ordered result', 'source_refs':[{'engram_ref':'e2'}],
                     'statement_ids':['s3'], 'abstained':False}
    class Observer:
        def __init__(self, adapter, semantic):
            assert adapter == 'adapter'
        def run(self, query):
            calls.append(vars(query))
            return json.dumps(native_result)
    core = SimpleNamespace(ObserverQuery=SimpleNamespace, ObserverRetriever=Observer,
                           SemanticRetriever=lambda *args: 'semantic')
    result = pipe.recall_observer_block(core, adapter='adapter', embedder='embedder', index='index',
        question='What does Ada prefer?', allowed_holders=['Ada'], mode='hybrid',
        now_iso='2026-06-01T00:00:00Z', k=3, max_context_bytes=500)
    assert result == native_result
    assert calls[0] == {'tenant_id':'default','allowed_holders':['Ada'],
                       'question':'What does Ada prefer?','mode':'hybrid',
                       'as_of_iso8601':'2026-06-01T00:00:00Z','k':3,'max_context_bytes':500}


@pytest.mark.parametrize('mode, expected', [('sources',2),('full',2),('statements',3),('hybrid',3)])
def test_new_mode_budget_matches_explicit_source_holders(mode, expected):
    assert hasattr(runner, 'question_request_bound'), 'observer reservation mapping missing'
    record = {'history': HISTORY, 'answer_format':'long_form'}
    assert runner.question_request_bound(record, {'recall_mode':mode}, None) == expected


def test_unknown_mode_fails_before_any_query_or_request():
    assert hasattr(runner, 'question_request_bound'), 'observer reservation mapping missing'
    with pytest.raises(ValueError, match='recall_mode'):
        runner.question_request_bound({'history':HISTORY}, {'recall_mode':'typo'}, None)


def test_real_native_source_roundtrip_through_dataset_adapter(tmp_path):
    import subprocess
    import sys
    program = r'''
import importlib.util,json,sqlite3,sys
from starling import _core, runtime
root=sys.argv[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,root+'/scripts/'+name+'.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
runner=load('run_socialmem_baseline');pipe=load('eval_ladder_pipeline')
rt=runtime._build_local_store_sqlite_runtime(sys.argv[2]);rt.start()
history=json.loads(sys.argv[3])
assert hasattr(_core,'retain_source_turns'), 'native source retention missing'
result=runner.retain_history_sources(_core,rt.adapter,history,'2026-06-01T00:00:00Z')
assert result['turns']==1 and result['documents']==1
r=pipe.recall_observer_block(_core,adapter=rt.adapter,embedder=_core.StubEmbeddingAdapter(8),
    index=_core.SqliteBlobVectorIndex(),question='blue murals',allowed_holders=['Ada'],
    mode='sources',now_iso='2026-12-08T00:00:00Z',k=10,max_context_bytes=8000)
assert 'blue murals' in r['block'] and r['source_count']==1 and r['statement_count']==0
assert r['source_refs'][0]['turn_id']=='s1_t1'
assert 'DO_NOT_SEND' not in r['block']
with sqlite3.connect(sys.argv[2]) as conn:
    assert conn.execute('select count(*) from statements').fetchone()[0]==0
'''
    result = subprocess.run([sys.executable, '-c', program, str(ROOT), str(tmp_path/'native.db'),
                             json.dumps(HISTORY)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
