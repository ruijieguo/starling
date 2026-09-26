"""原生来源与观察者接口；Python只传递结构与JSON，不模拟检索。"""
import json
import sqlite3

import pytest

from starling import _core, runtime

TURNS = [{'speaker':'Ada','text':'Copper lantern in Kyoto.','turn_id':'s1_t2',
          'session_id':'s1','turn_index':2,'observed_at':'2025-01-01T10:00:00Z'}]

@pytest.fixture
def native(tmp_path):
    assert hasattr(_core, 'retain_source_turns'), 'native source retention missing'
    rt = runtime._build_local_store_sqlite_runtime(tmp_path/'memory.db'); rt.start()
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    semantic = _core.SemanticRetriever(rt.adapter, emb, idx)
    observer = _core.ObserverRetriever(rt.adapter, semantic)
    q = _core.ObserverQuery(); q.tenant_id='default'; q.allowed_holders=['Ada']
    q.question='copper lantern'; q.as_of_iso8601='2026-06-01T00:00:00Z';q.mode='sources'
    yield rt, observer, q


@pytest.mark.parametrize('strategy', ['evidence_profile_v8', 'evidence_profile_v9', 'evidence_profile_v10'])
def test_binding_forwards_independent_sidecar_profile_to_native(native, strategy):
    rt, observer, q = native
    q.mode = 'hybrid'
    q.k = 1
    q.source_strategy = strategy
    _core.retain_source_turns(rt.adapter, 'default', ['Ada'], json.dumps(TURNS),
                              '2026-01-01T00:00:00Z')
    result = json.loads(observer.run(q))
    assert result['source_count'] == 1
    assert result['source_diagnostics']['evidence_profile']['source_limit'] == 1
    assert result['statement_count'] == 0


def test_native_binding_roundtrip_preserves_source_identity(native):
    rt, observer, q = native
    saved = json.loads(_core.retain_source_turns(rt.adapter, 'default', ['Ada'], json.dumps(TURNS),
                                                '2026-01-01T00:00:00Z'))
    result=json.loads(observer.run(q))
    assert result['source_count']==1 and result['statement_ids']==[]
    assert result['source_refs'][0]['engram_ref']==saved['engram_refs'][0]
    assert result['source_refs'][0]['turn_id']=='s1_t2'
    assert result['source_refs'][0]['observed_at']==TURNS[0]['observed_at']
    assert result['context_bytes']==len(result['block'].encode())
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        assert conn.execute('SELECT COUNT(*) FROM statements').fetchone()[0]==0


@pytest.mark.parametrize('field,value', [('allowed_holders',[]), ('mode','typo'), ('k',0)])
def test_invalid_binding_query_is_rejected_by_native(native, field, value):
    _, observer, q = native
    setattr(q, field, value)
    with pytest.raises(ValueError):
        observer.run(q)


def test_binding_rejects_source_owner_outside_scope(native):
    rt, _, _ = native
    with pytest.raises(ValueError):
        _core.retain_source_turns(rt.adapter, 'default', ['Bob'], json.dumps(TURNS),
                                 '2026-01-01T00:00:00Z')


def test_native_multi_holder_statement_selection_matches_single_scope_planner(native):
    import importlib.util
    from pathlib import Path
    rt, _, _ = native
    path = Path(__file__).resolve().parents[2]/'scripts/eval_ladder_pipeline.py'
    spec = importlib.util.spec_from_file_location('fixture_pipe',path)
    pipe = importlib.util.module_from_spec(spec);spec.loader.exec_module(pipe)
    pipe.seed_gold_statements(str(rt.adapter.db_path), 'two-owners', [
        {'holder':'Ada','subject':'Museum','predicate':'said','object':'copper lantern',
         'observed_at':'2026-01-01T00:00:00Z'},
        {'holder':'Bob','subject':'Museum','predicate':'said','object':'copper lantern',
         'observed_at':'2026-01-01T00:00:00Z'}])
    emb=_core.StubEmbeddingAdapter(8);idx=_core.SqliteBlobVectorIndex()
    pipe.embed_seeded(_core,rt.adapter,emb,idx,'2026-06-01T00:00:00Z')
    semantic=_core.SemanticRetriever(rt.adapter,emb,idx)
    observer=_core.ObserverRetriever(rt.adapter,semantic)
    q=_core.ObserverQuery();q.tenant_id='default';q.allowed_holders=['Ada'];q.mode='statements'
    q.question='Museum said copper lantern';q.as_of_iso8601='2026-06-01T00:00:00Z'
    pq=_core.PlannerQuery();pq.tenant_id='default';pq.querier='Ada';pq.text=q.question
    pq.as_of_iso8601=q.as_of_iso8601;pq.query_id='single-parity';pq.k=10
    old=_core.RetrievalPlanner(rt.adapter,semantic).run(pq)
    assert not old.abstained
    single=json.loads(observer.run(q))
    assert single['statement_ids']==[e.row.id for e in old.entries]
    assert single['block']=='\n'.join(_core.render_context_line(e.row,e.label) for e in old.entries)
    assert single['receipts'][0]['holder']=='Ada'
    assert single['receipts'][0]['fetched']>=1
    assert single['receipts'][0]['abstained'] is False
    q.allowed_holders=['Bob','Ada','Bob']
    combined=json.loads(observer.run(q))
    assert set(combined['statement_ids'])=={'two-owners-gold0','two-owners-gold1'}
    assert len(combined['receipts'])==2
    q.allowed_holders=['Bob']
    assert json.loads(observer.run(q))['statement_ids']==['two-owners-gold1']


def test_invalid_time_retention_is_explicit_and_queryable_without_fabricated_time(native):
    rt, observer, q = native
    bad = [dict(TURNS[0], observed_at='2026-01-13T18:60:00')]
    with pytest.raises(RuntimeError, match='observation timestamp'):
        _core.retain_source_turns(rt.adapter, 'default', ['Ada'], json.dumps(bad), '2026-06-01T00:00:00Z')
    stored = json.loads(_core.retain_source_turns(rt.adapter, 'default', ['Ada'], json.dumps(bad),
                        '2026-06-01T00:00:00Z', preserve_invalid_time=True))
    assert stored['turns'] == 1
    q = _core.ObserverQuery()
    q.tenant_id = 'default'; q.allowed_holders = ['Ada']; q.question = 'Copper lantern'
    q.mode = 'sources'; q.as_of_iso8601 = '2026-12-08T00:00:00Z'
    assert json.loads(observer.run(q))['source_count'] == 0
    q.include_unknown_time = True
    result = json.loads(observer.run(q))
    assert result['source_count'] == 1
    assert result['source_refs'][0]['observed_at'] is None
    assert result['source_refs'][0]['raw_observed_at'] == '2026-01-13T18:60:00'
    assert result['source_diagnostics']['unknown_time_included'] == 1
    assert '"time_status":"invalid"' in result['block']
    q.as_of_iso8601 = '2026-05-31T00:00:00Z'
    assert json.loads(observer.run(q))['source_count'] == 0


def test_focused_binding_and_pipeline_delegate_to_native(native):
    import importlib.util
    from pathlib import Path
    rt, observer, q = native
    assert q.source_strategy == 'bm25'
    data = [dict(TURNS[0], text='I enjoy pottery.'),
            dict(TURNS[0], speaker='Bob', turn_id='b1', text='Ada Ada preferences')]
    _core.retain_source_turns(rt.adapter, 'default', ['Ada', 'Bob'], json.dumps(data), '2026-01-01T00:00:00Z')
    spec = importlib.util.spec_from_file_location('focus_pipe', Path(__file__).resolve().parents[2]/'scripts/eval_ladder_pipeline.py')
    pipe = importlib.util.module_from_spec(spec); spec.loader.exec_module(pipe)
    found = pipe.recall_observer_block(_core, adapter=rt.adapter, embedder=_core.StubEmbeddingAdapter(8),
        index=_core.SqliteBlobVectorIndex(), question="Ada's preferences", allowed_holders=['Ada','Bob'],
        mode='sources', now_iso=q.as_of_iso8601, k=1, source_strategy='focused')
    assert found['source_refs'][0]['speaker'] == 'Ada'
    q.source_strategy = 'typo'
    with pytest.raises(ValueError): observer.run(q)


def test_minimum_source_quota_is_only_a_native_query_field(native):
    _, _, q = native
    q.min_source_items = 3
    assert q.min_source_items == 3
