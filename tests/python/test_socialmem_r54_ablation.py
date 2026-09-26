"""R5.4 四组消融和门槛的编排合同；不重复C++检索逻辑。"""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def driver():
    path = Path(__file__).resolve().parents[2] / 'scripts/run_socialmem_r54_ablation.py'
    spec = importlib.util.spec_from_file_location('r54_test', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def row(arm):
    strategy, mode, k = {
        'baseline': ('evidence_profile_v6', 'hybrid', 10),
        'source7': ('evidence_profile_v6', 'sources', 7),
        'source10': ('evidence_profile_v9', 'sources', 10),
        'sidecar': ('evidence_profile_v9', 'hybrid', 10),
    }[arm]
    recall = {'source_refs': [{'engram_ref': 'e1', 'clause_id': 'c0', 'turn_id': 't1'}],
              'statement_ids': [], 'source_count': 1, 'statement_count': 0,
              'block': '[SOURCE] 中文', 'context_bytes': 15,
              'source_context_bytes': 15, 'statement_context_bytes': 0,
              'receipts': [{'holder': 'Alice', 'degraded_paths': []}] if mode == 'hybrid' else [],
              'source_diagnostics': {'evidence_profile': {'sidecar_selection_order': []}}}
    return dict(item_id='q1', group_id='g1', arm=arm, strategy=strategy, mode=mode, k=k,
                core_sha256='core', database_sha256='db', terminal=True, status='ok',
                holders=['Alice'], embedding_requests=1 if mode == 'hybrid' else 0, recall=recall)


def fixture_rows():
    return {a: [row(a)] for a in ('baseline', 'source7', 'source10', 'sidecar')}


RECORDS = [{'item_id': 'q1', 'source': {'evidence_anchors': [{'turn_id': 't1'}]}}]


def test_arms_are_preregistered_and_candidate_is_source_only():
    d = driver()
    assert d.ARMS == {
        'baseline': ('evidence_profile_v6', 'hybrid', 10),
        'source7': ('evidence_profile_v6', 'sources', 7),
        'source10': ('evidence_profile_v9', 'sources', 10),
        'sidecar': ('evidence_profile_v9', 'hybrid', 10)}
    assert d.QA_CANDIDATE == 'source10'


@pytest.mark.parametrize('path,value', [
    (('terminal',), False), (('core_sha256',), 'old'), (('database_sha256',), 'wrong'),
    (('strategy',), 'evidence_profile_v8'), (('mode',), 'hybrid'), (('k',), 7),
    (('embedding_requests',), 1), (('recall', 'context_bytes'), 14),
    (('recall', 'statement_context_bytes'), 1), (('recall', 'source_count'), 2),
    (('recall', 'receipts'), [{'degraded_paths': [{'reason': 'embedder_unavailable'}]}])])
def test_native_receipt_contract_rejects_drift(path, value):
    d = driver()
    good = row('source10')
    d.validate_row(good, 'source10', 'db', 'core', 8000)
    bad = copy.deepcopy(good)
    target = bad
    for key in path[:-1]: target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError): d.validate_row(bad, 'source10', 'db', 'core', 8000)


def test_sidecar_must_reference_selected_source():
    d = driver()
    bad = row('sidecar')
    bad['recall'].update(statement_ids=['s1'], statement_count=1)
    bad['recall']['block'] += '\n[OBS] claim'
    bad['recall']['context_bytes'] = len(bad['recall']['block'].encode())
    bad['recall']['statement_context_bytes'] = len('\n[OBS] claim'.encode())
    bad['recall']['source_diagnostics']['evidence_profile']['sidecar_selection_order'] = [
        {'statement_id': 's1', 'rendered': True, 'source_ref': {'engram_ref': 'wrong', 'clause_id': 'c0'}}]
    with pytest.raises(ValueError, match='sidecar'):
        d.validate_row(bad, 'sidecar', 'db', 'core', 8000)


def test_gate_requires_changed_healthy_context_not_empty_precision():
    d = driver()
    rows = fixture_rows()
    result = d.compare_rows(RECORDS, rows)
    assert result['qa_gate'] == 'blocked_unchanged_context'
    assert result['source_only_sidecar_relevance'] == 'not_applicable'
    rows['baseline'][0]['recall']['block'] += '\n[OBS] baseline statement'
    result = d.compare_rows(RECORDS, rows)
    assert result['qa_gate'] == 'passed'
    assert result['anchors']['source10'] == {'hit': 1, 'total': 1}
    rows['baseline'][0]['status'] = 'error'
    assert d.compare_rows(RECORDS, rows)['qa_gate'] == 'blocked_technical'


def test_pairing_and_source_controls_fail_closed():
    d = driver()
    rows = fixture_rows()
    rows['baseline'][0]['recall']['block'] += '\n[OBS] baseline statement'
    bad = copy.deepcopy(rows)
    bad['source10'][0]['recall']['source_refs'][0]['turn_id'] = 'wrong'
    assert d.compare_rows(RECORDS, bad)['qa_gate'] == 'blocked_source_controls'
    bad['sidecar'][0]['recall']['source_refs'][0]['turn_id'] = 'wrong'
    assert d.compare_rows(RECORDS, bad)['qa_gate'] == 'blocked_anchor_recall'
    with pytest.raises(ValueError, match='item'):
        d.compare_rows(RECORDS, {**rows, 'sidecar': rows['sidecar'] * 2})


def test_output_refused_before_parent_validation(tmp_path):
    with pytest.raises(ValueError, match='exists'):
        driver().run(tmp_path / 'missing', tmp_path)


def test_hybrid_zero_embedding_or_missing_holder_is_not_healthy():
    d = driver()
    bad = row('baseline')
    bad['recall']['receipts'] = []
    bad['embedding_requests'] = 0
    with pytest.raises(ValueError, match='embedding|holder'):
        d.validate_row(bad, 'baseline', 'db', 'core', 8000)
    rows = fixture_rows()
    rows['baseline'] = [bad]
    rows['baseline'][0]['recall']['block'] += '\n[OBS] baseline statement'
    assert d.compare_rows(RECORDS, rows)['qa_gate'] == 'blocked_technical'


def test_missing_degradation_evidence_is_not_empty_degradation():
    d = driver()
    bad = row('baseline')
    del bad['recall']['receipts'][0]['degraded_paths']
    with pytest.raises(ValueError):
        d.validate_row(bad, 'baseline', 'db', 'core', 8000)
    rows = fixture_rows(); rows['baseline'] = [bad]
    rows['baseline'][0]['recall']['block'] += '\n[OBS] baseline statement'
    assert d.compare_rows(RECORDS, rows)['qa_gate'] == 'blocked_technical'


def test_group_duplicates_rejected_before_adapters(tmp_path):
    d = driver()
    records = [dict(item_id=f'q{i}', history=[{'speaker': f'h{j}'} for j in range(9 if i == 0 else 6)]) for i in range(57)]
    groups = [{'group_id': 'g1', 'records': records}]
    assert d.validate_record_groups(records, groups) == 690
    groups[0]['records'] = records + [records[0]]
    with pytest.raises(ValueError, match='unique|duplicate'):
        d.validate_record_groups(records, groups)
    groups[0]['records'] = copy.deepcopy(records)
    groups[0]['records'][0]['history'].append({'speaker': 'extra'})
    with pytest.raises(ValueError, match='content|budget'):
        d.validate_record_groups(records, groups)


@pytest.mark.parametrize('bad_bytes', [False, True])
def test_query_lifecycle_retains_attempt_count_without_runtime_stop(tmp_path, bad_bytes):
    d = driver()
    source = tmp_path / 'parent/runs/g1/frozen.db'
    source.parent.mkdir(parents=True); source.write_bytes(b'unchanged')
    rt = SimpleNamespace(start=lambda: None, adapter=object())
    runtime = SimpleNamespace(_build_local_store_sqlite_runtime=lambda p: rt)
    recall = row('baseline')['recall']
    if bad_bytes: recall['context_bytes'] = 999
    pipeline = SimpleNamespace(recall_observer_block=lambda *a, **kw: recall)
    core = SimpleNamespace(SqliteBlobVectorIndex=lambda: object())
    cfg = dict(core_sha256='core', max_context_bytes=8000, query_time='2026-12-08T00:00:00Z',
               include_unknown_time=True, min_source_items=7, source_seed_k=5,
               source_seed_max_context_bytes=4000, source_dialogue_radius=1)
    record = dict(item_id='q1', question='test', history=[{'speaker': 'Alice'}])
    r = d.query_one(('g1', record, 'baseline', SimpleNamespace(request_count=1)),
                    tmp_path / 'parent', tmp_path / 'out', {'database_sha256': {'g1': 'db'}},
                    cfg, core, runtime, pipeline)
    assert r['status'] == ('error' if bad_bytes else 'ok')
    assert r['embedding_requests'] == 1
    assert source.read_bytes() == b'unchanged'
    assert len(list((tmp_path / 'out/baseline/recalls').glob('*.json'))) == 1
