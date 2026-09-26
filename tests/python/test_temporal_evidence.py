"""时间证据选择由 C++ 完成，使用真实原生入库和 Planner 验证边界。"""
import importlib
import json
from pathlib import Path
import sqlite3
import sys

import pytest
from starling import _core, runtime

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))


@pytest.fixture
def temporal_rig(tmp_path):
    evaluation = importlib.import_module('eval_socialmem_claim_contract')
    path = tmp_path / 'temporal.db'
    rt = runtime._build_local_store_sqlite_runtime(path)
    rt.start()
    ids = {}
    for session, emotion, salience in [('s1', 'nervous', 0), ('s2', 'hopeful', 1),
                                       ('s3', 'relaxed', 0.8), ('s4', 'excited', 0.9)]:
        passage = _core.claim_source_turn_payload(json.dumps([{'speaker': 'Mina', 'session_id': session,
            'turn_id': session + '-t0', 'turn_index': 0, 'observed_at': '2026-09-01T10:00:00Z',
            'text': f'I feel {emotion} about canoeing.'}]))
        claim = {'holder': 'Mina', 'holder_perspective': 'FIRST_PERSON', 'subject': 'Mina',
            'subject_kind': 'cognizer', 'predicate': 'feels', 'object': f'{emotion} about canoeing',
            'modality': 'BELIEVES', 'polarity': 'POS', 'nesting_depth': 0,
            'evidence': {'clause_id': 'c0', 'actor': 'Mina', 'assertion_scope': 'ASSERTED',
                'scope_markers': ['ASSERTED'], 'topic': 'canoeing', 'time_text': '', 'event_time': None}}
        case = {'id': session, 'track': 'fixed_controls', 'holder': 'Mina', 'passage': passage, 'candidate': claim}
        llm = _core.FakeLLMAdapter()
        llm.set_default_response('{"schema_version":1,"decisions":[{"index":0,"retain":true,"reason":"supported"}]}')
        committed, _ = evaluation.native_persist(_core, rt.adapter, case, llm)
        assert len(committed['statement_ids']) == 1
        ids[session] = committed['statement_ids'][0]
        with sqlite3.connect(path) as db:
            # Planner 输入契约要求稳定可见候选；显式固化 fixture，避免后台巩固调度决定测试窗口。
            db.execute("UPDATE statements SET salience=?,consolidation_state='consolidated' WHERE id=? AND tenant_id=?",
                       (salience, ids[session], 'default'))
    try:
        yield rt, path, ids
    finally:
        del rt


def query():
    q = _core.PlannerQuery()
    q.tenant_id = 'default'
    q.querier = q.subject_id = 'Mina'
    q.predicate = 'feels'
    q.as_of_iso8601 = '2026-09-13T00:00:00Z'
    q.query_id = 'temporal-fixture'
    q.k = 2
    return q


def temporal_request():
    assert hasattr(_core, 'TemporalEvidenceRequest'), 'native temporal evidence request is missing'
    request = _core.TemporalEvidenceRequest()
    request.tenant_id = 'default'
    request.actor_id = 'Mina'
    request.topic = 'canoeing'
    request.ordered_session_ids = ['s1', 's2', 's3', 's4']
    request.through_session_id = 's3'
    request.limit = 2
    return request


def run(rt, q):
    embedder = _core.StubEmbeddingAdapter(8)
    index = _core.SqliteBlobVectorIndex()
    semantic = _core.SemanticRetriever(rt.adapter, embedder, index)
    return _core.RetrievalPlanner(rt.adapter, semantic).run(q)


def test_planner_selects_early_and_late_before_top_k_and_keeps_event_time_unknown(temporal_rig):
    rt, path, ids = temporal_rig
    q = query()
    before = run(rt, q)
    assert ids['s1'] not in [e.row.id for e in before.entries]
    q.temporal_evidence = temporal_request()
    result = run(rt, q)
    view = json.loads(result.receipt.temporal_evidence_json)
    assert view['sufficient'] and view['early']['statement_id'] == ids['s1']
    assert view['late']['statement_id'] == ids['s3']
    assert {e.row.id for e in result.entries} == {ids['s1'], ids['s3']}
    assert view['excluded_after_cutoff'] == 1
    assert '[EVIDENCE_ORDER]' in result.context_pack and '事件时间' in result.context_pack
    for entry in result.entries:
        assert json.loads(entry.row.semantic_claim_json)['event_time'] is None
    assert {v.statement_id for v in result.receipt.score_breakdown} == {e.row.id for e in result.entries}
    q.temporal_evidence = None
    assert run(rt, q).context_pack == before.context_pack


def test_planner_rejects_tampered_source_before_temporal_selection(temporal_rig):
    rt, path, ids = temporal_rig
    q = query()
    q.temporal_evidence = temporal_request()
    with sqlite3.connect(path) as db:
        claim = json.loads(db.execute('SELECT semantic_claim_json FROM statements WHERE id=? AND tenant_id=?',
                                     (ids['s1'], 'default')).fetchone()[0])
        db.execute('UPDATE engrams SET payload_inline=? WHERE id=? AND tenant_id=?',
                   (b'tampered source', claim['source_span']['engram_ref'], 'default'))
    result = run(rt, q)
    assert ids['s1'] not in [e.row.id for e in result.entries]
    assert result.receipt.candidate_counts.dropped_by_claim_evidence >= 1
    view = json.loads(result.receipt.temporal_evidence_json)
    assert view['early']['statement_id'] == ids['s2']
    q.temporal_evidence = temporal_request()
    request = q.temporal_evidence
    request.tenant_id = 'other-tenant'
    q.temporal_evidence = request
    with pytest.raises(ValueError, match='tenant'):
        run(rt, q)


@pytest.mark.parametrize('k', [-1, 2147483647])
def test_temporal_query_rejects_invalid_candidate_budget_before_fetch(temporal_rig, k):
    rt, _, _ = temporal_rig
    q = query()
    q.temporal_evidence = temporal_request()
    q.k = k
    with pytest.raises(ValueError, match='candidate budget'):
        run(rt, q)
