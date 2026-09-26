"""R5.3 检索评测的证据完整性与统计合同。"""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def driver():
    path = Path(__file__).resolve().parents[2] / "scripts/run_socialmem_r53_offline.py"
    spec = importlib.util.spec_from_file_location("r53_offline_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(arm="v8"):
    return {
        "item_id": "q1", "group_id": "g1", "arm": arm,
        "strategy": "evidence_profile_" + arm, "core_sha256": "core",
        "database_sha256": "db", "terminal": True, "status": "ok",
        "recall": {"source_refs": [{"engram_ref": "e", "clause_id": "c0", "turn_id": "t1"}],
                   "statement_ids": [], "source_count": 1, "statement_count": 0,
                   "block": "[SOURCE] 中文", "context_bytes": 15,
                   "source_context_bytes": 15, "statement_context_bytes": 0,
                   "receipts": [], "source_diagnostics": {"evidence_profile": {
                       "sidecar_selection_order": []}}},
    }


def test_validate_counts_bytes_provenance_and_terminal():
    d = driver()
    d.validate_row(row(), "v8", "db", "core", k=1, max_bytes=20)
    for path, value in [(('terminal',), False), (('core_sha256',), 'old'),
                        (('database_sha256',), 'wrong'), (('strategy',), 'evidence_profile_v7'),
                        (('recall', 'source_count'), 0), (('recall', 'context_bytes'), 14),
                        (('recall', 'statement_context_bytes'), 1)]:
        bad = copy.deepcopy(row())
        target = bad
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        with pytest.raises(ValueError):
            d.validate_row(bad, "v8", "db", "core", k=1, max_bytes=20)


def test_reject_duplicate_sources_and_unlinked_sidecar():
    d = driver()
    bad = row()
    bad['recall']['source_refs'] *= 2
    bad['recall']['source_count'] = 2
    with pytest.raises(ValueError, match='duplicate'):
        d.validate_row(bad, 'v8', 'db', 'core', k=2, max_bytes=20)
    bad = row()
    bad['recall']['statement_ids'] = ['s1']
    bad['recall']['statement_count'] = 1
    with pytest.raises(ValueError, match='sidecar'):
        d.validate_row(bad, 'v8', 'db', 'core', k=1, max_bytes=20)


def test_compare_uses_turn_identity_and_detects_source_displacement():
    d = driver()
    records = [{'item_id': 'q1', 'source': {'evidence_anchors': [{'turn_id': 't1'}, {'turn_id': 't2'}]}}]
    result = d.compare_rows(records, [row('v6')], [row()], [row()])
    assert result['anchors']['v8'] == {'hit': 1, 'total': 2}
    assert result['source_control_mismatches'] == 0
    assert result['anchor_gate'] is True
    assert result['sidecar_precision'] is None
    bad = row()
    bad['recall']['source_refs'][0]['turn_id'] = 't3'
    result = d.compare_rows(records, [row('v6')], [bad], [row()])
    assert result['anchor_gate'] is False
    assert result['source_control_mismatches'] == 1
    assert result['qa_gate'] == 'blocked_source_control'
    with pytest.raises(ValueError, match='item'):
        d.compare_rows(records, [row('v6')], [row(), row()], [row()])


def test_degraded_embedding_is_not_healthy_semantic_evaluation():
    d = driver()
    bad = row()
    bad['recall']['receipts'] = [{'degraded_paths': [{'reason': 'embedder_unavailable'}]}]
    assert d.degraded_reasons(bad) == {'embedder_unavailable': 1}
    with pytest.raises(ValueError, match='status'):
        d.validate_row(bad, 'v8', 'db', 'core', k=1, max_bytes=20)


def test_error_row_cannot_pass_anchor_gate_or_create_quality_change():
    d = driver()
    records = [{'item_id': 'q1', 'source': {'evidence_anchors': [{'turn_id': 't1'}]}}]
    bad = row('v6')
    bad.update(status='error', error='transport failure')
    del bad['recall']
    result = d.compare_rows(records, [bad], [row()], [row()])
    assert result['anchor_gate'] is False
    assert result['qa_gate'] == 'blocked_technical'
    assert result['source_changed_questions'] == 0


def test_refuses_existing_output_before_loading_or_network(tmp_path):
    d = driver()
    with pytest.raises(ValueError, match='exists'):
        d.run(tmp_path / 'missing-parent', tmp_path, workers=1)


def test_seal_detects_changed_or_missing_receipt(tmp_path):
    d = driver()
    (tmp_path / 'receipt.json').write_text('{}')
    d.seal_output(tmp_path)
    d.verify_seal(tmp_path)
    (tmp_path / 'receipt.json').write_text('{"changed":true}')
    with pytest.raises(ValueError, match='hash'):
        d.verify_seal(tmp_path)


def test_seal_rejects_extra_receipt_and_incomplete_state(tmp_path):
    d = driver()
    (tmp_path / 'receipt.json').write_text('{}')
    d.seal_output(tmp_path)
    (tmp_path / 'extra.json').write_text('{}')
    with pytest.raises(ValueError, match='set'):
        d.verify_seal(tmp_path)
    d.seal_output(tmp_path, state='incomplete')
    with pytest.raises(ValueError, match='incomplete'):
        d.verify_seal(tmp_path)


@pytest.mark.parametrize('failure', ['', 'cleanup', 'validation'])
def test_frozen_runtime_without_stop_and_errors_keep_request_receipt(tmp_path, failure):
    d = driver()
    parent, out = tmp_path / 'parent', tmp_path / 'out'
    db = parent / 'runs/g1/frozen.db'
    db.parent.mkdir(parents=True)
    db.write_bytes(b'original')
    runtime_object = SimpleNamespace(start=lambda: None)
    if failure == 'cleanup':
        def fail():
            raise RuntimeError('cleanup failed')
        runtime_object.stop = fail
    runtime = SimpleNamespace(_build_local_store_sqlite_runtime=lambda path: runtime_object)
    runtime_object.adapter = object()
    core = SimpleNamespace(SqliteBlobVectorIndex=lambda: object())
    recall = row()['recall']
    if failure == 'validation':
        recall['context_bytes'] = 999
    pipeline = SimpleNamespace(recall_observer_block=lambda *a, **kw: recall)
    config = dict(core_sha256='core', k=1, max_context_bytes=20, recall_mode='hybrid',
                  query_time='2026-12-08T00:00:00Z', include_unknown_time=True,
                  min_source_items=1, source_seed_k=1, source_seed_max_context_bytes=20,
                  source_dialogue_radius=1)
    record = dict(item_id='q1', question='test', history=[{'speaker': 'Alice'}])
    result = d.query_one(('g1', record, 'v8', SimpleNamespace(request_count=1)),
                         parent, out, {'database_sha256': {'g1': 'db'}}, config, core, runtime, pipeline)
    assert result['status'] == ('error' if failure else 'ok')
    assert ('error' in result) is bool(failure)
    assert result['embedding_requests'] == 1
    assert len(list((out / 'v8/recalls').glob('*.json'))) == 1
    assert db.read_bytes() == b'original'
