"""原生向量健康的只读文件边界；不执行真实请求。"""
import hashlib
import json
import sqlite3
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from starling import _core, runtime


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[2] / 'scripts' / (name+'.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_scope_builder_accepts_recovered_vectors_and_preserves_failures(tmp_path):
    runner, pipe = load_script('run_socialmem_baseline'), load_script('eval_ladder_pipeline')
    embedder = _core.StubEmbeddingAdapter(8)
    def extract(adapter, record, model):
        pipe.seed_history_statements(str(adapter.db_path), 'recovered', record['history'])
        with sqlite3.connect(str(adapter.db_path)) as conn:
            row = conn.execute('SELECT subject_id,predicate,object_value FROM statements LIMIT 1').fetchone()
        embedder.fail_next(' '.join(row))
        return [{'holder': 'Ada', 'extraction_failed': False,
                 'receipt': {'channels': {'belief': {}, 'general_fact': {}, 'episodic': {}}}}]
    ladder = SimpleNamespace(_build_extract_llm=None, make_real_extract_fn=lambda *a, **k: extract)
    counter = SimpleNamespace(request_count=0)
    def drain(core, adapter, ignored, index, now, **kwargs):
        result = pipe.embed_seeded(core, adapter, embedder, index, now, **kwargs)
        counter.request_count = 3
        return result
    ledger = runner.BudgetLedger(tmp_path / 'ledger.sqlite', 1000)
    reservation = ledger.reserve('scope', 'scope_extraction', 10)
    scope = tmp_path / 'scope'; scope.mkdir()
    database, metadata = runner._build_scope_database(
        {'group_id': 'scope', 'history': [{'speaker': 'Ada', 'text': 'fact '+str(i)} for i in range(40)]},
        scope, (_core, runtime, None, ladder, SimpleNamespace(embed_seeded=drain), None),
        {'query_time': '2026-09-26T00:00:00Z', 'extract_model': 'fixture'},
        (None, counter, None, None), ledger, reservation)
    assert database.is_file()
    assert metadata['embedding']['failed'] == 32
    assert metadata['embedding']['final_health']['complete'] is True
    assert metadata['embedding_request_count'] == 3
    assert ledger.snapshot()['reserved'] == 0


def test_frozen_health_is_readonly_and_rejects_missing_file(tmp_path):
    assert hasattr(_core, 'embedding_health_json'), 'native frozen health API is required'
    rt = runtime._build_local_store_sqlite_runtime(tmp_path / 'live.db')
    rt.start()
    frozen = tmp_path / 'frozen.db'
    with sqlite3.connect(str(rt.adapter.db_path)) as src, sqlite3.connect(frozen) as dst:
        src.backup(dst)
    digest = hashlib.sha256(frozen.read_bytes()).hexdigest()
    result = json.loads(_core.embedding_health_json(str(frozen), 8, 'stub', 3))
    assert result['complete'] is True and result['total'] == 0
    assert hashlib.sha256(frozen.read_bytes()).hexdigest() == digest
    assert not list(tmp_path.glob('frozen.db-*'))
    with pytest.raises((ValueError, RuntimeError), match='frozen'):
        _core.embedding_health_json(str(tmp_path / 'missing.db'), 8, 'stub', 3)
    assert not (tmp_path / 'missing.db').exists()
    (tmp_path / 'frozen.db-wal').write_bytes(b'pending')
    with pytest.raises((ValueError, RuntimeError), match='frozen'):
        _core.embedding_health_json(str(frozen), 8, 'stub', 3)
