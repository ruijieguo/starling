#!/usr/bin/env python3
"""R6.2 最终向量健康修复；显式继承费用并原生重验证两个历史库。"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


engine = load(ROOT / 'scripts/run_socialmem_r60_expanded.py', 'r62_engine')
audit = load(ROOT / 'scripts/socialmem_frozen_audit.py', 'r62_frozen_audit')
engine.CORE_SHA256 = '949484630a9c83d93fb0582c9b37ff6a228e3f39bc80fe020b1384441e0c9bfb'
engine.IDENTITY_SCHEMA = 'r62-expanded-identity-v1'
engine.SEAL_SCHEMA = 'r62-expanded-seal-v1'
engine.ARM = 'r62_embedding_health_revalidated_development'
engine.DEFAULT_PROBE = ROOT / 'build/socialmem_20260926_r61_work/run-real-retry'
engine.PROBE_SEAL = '1a2a9f20a82e87880272a9058f8599fa8117ff8a92662833b35f560e49f2e60c'
engine.PROBE_PREPARE_SEAL = '285cbea5751c37b6c43809f8e7c3cbafc62ff0159a2dd1dc09cba460d46feedb'
engine.OWN_FILES = (*engine.OWN_FILES, 'scripts/run_socialmem_r62_expanded.py',
    'scripts/socialmem_frozen_audit.py', 'tests/python/test_socialmem_r62_expanded.py',
    'tests/python/test_socialmem_frozen_audit.py', 'tests/python/test_embedding_health.py',
    'tests/python/test_eval_ladder_pipeline.py', 'tests/cpp/test_embedding_worker.cpp')
CANDIDATE_CORE = ROOT / 'build/socialmem_20260926_r62_work/cmake/python/starling/_core.cpython-314-darwin.so'
HISTORY = ROOT / 'build/socialmem_20260926_r61_expanded/build'
HISTORY_PREPARED = ROOT / 'build/socialmem_20260926_r61_expanded/prepare'
HISTORY_SEAL = '0cbe5bedc8ec203b74780824de6a17d2cee8c7368b46c6753050841902aecb04'
HISTORY_CORE = 'd2f60d1836336f9114efd437fec428050ac77e6bbec6abeea02a0e219b9df793'
RECOVERED = ('ae45ef45d7ff23aade9a9a29', '1c2838ef51b9983207436fc9')
engine.embedding_model = 'qwen3.7-text-embedding'


def current_core():
    if not CANDIDATE_CORE.is_file() or engine.sha(CANDIDATE_CORE) != engine.CORE_SHA256:
        raise ValueError('fixed isolated candidate core mismatch')
    return CANDIDATE_CORE


def historical_scope(gid):
    if gid not in RECOVERED: raise ValueError('scope is not eligible for recovery')
    scope = HISTORY / 'runs' / gid
    database = scope / ('frozen.db' if gid == RECOVERED[0] else 'diagnostic.db')
    rows = engine.old.raw_scope_extraction(scope)
    return scope, database, rows


def compatibility_bridge():
    """独立进程装载候选核心，复用全部真实响应作零请求重放。"""
    core = current_core()
    inputs = engine.historical_inputs(engine.DEFAULT_PARENT)
    with tempfile.TemporaryDirectory(prefix='r62-bridge-') as temp:
        work = Path(temp)
        shutil.copytree(HISTORY_PREPARED / 'frozen', work / 'frozen')
        for path in (work / 'frozen/python/starling').glob('_core*.so'): path.unlink()
        engine.copy_file(core, work / 'frozen/python/starling' / core.name)
        identity = dict(core_sha256=engine.CORE_SHA256, frozen_files=engine.inventory(work / 'frozen'))
        runner, modules = engine.frozen_modules(work, inputs['config'], identity)
        checked = dict(runner=runner, modules=modules, config=inputs['config'])
        plans = engine.native_plans(runner, modules, inputs['groups'], inputs['config'])
        scopes = {}
        for group in inputs['groups'][:2]:
            gid = group['group_id']; original, database, rows = historical_scope(gid)
            start, end = engine.read(original / 'scope.started.json'), engine.read(original / 'native.finished.json')
            replay = engine.native_replay(checked, database, rows, plans['scopes'][gid], group,
                dict(start=start['native_started_at'], end=end['native_ended_at']))
            health = json.loads(modules[0].embedding_health_json(str(database), 1024, engine.embedding_model, 3))
            if not replay['verified'] or not health['complete'] or health['total'] <= 0:
                raise ValueError('inherited scope incompatible with candidate core')
            scopes[gid] = dict(database_sha256=engine.sha(database), native_replay=replay, final_health=health)
    return dict(core_sha256=engine.CORE_SHA256, original_core_sha256=HISTORY_CORE,
                historical_seal_sha256=HISTORY_SEAL, external_requests=0, scopes=scopes)


def qualify_probe(probe):
    probe = Path(probe).resolve()
    if engine.sha(probe / 'seal.json') != engine.PROBE_SEAL: raise ValueError('historical probe seal mismatch')
    prepared = Path(engine.read(probe / 'stage.json')['input'])
    if engine.sha(prepared / 'seal.json') != engine.PROBE_PREPARE_SEAL: raise ValueError('probe prepare seal mismatch')
    previous = audit.run_frozen_check(probe, prepared, 'scripts/run_socialmem_r61_scope_probe.py', engine.PROBE_SEAL)
    inherited = audit.run_frozen_check(HISTORY, HISTORY_PREPARED, 'scripts/run_socialmem_r61_expanded.py', HISTORY_SEAL)
    if (previous['summary'].get('candidate_passed') is not True or
        previous['summary'].get('core_sha256', {}).get('candidate') != HISTORY_CORE or
        inherited['summary']['healthy_scopes'] != 1 or inherited['summary']['extraction_known_tokens'] != 1291057):
        raise ValueError('historical qualification mismatch')
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/run_socialmem_r62_expanded.py'), 'bridge'],
        cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}, capture_output=True, text=True)
    if result.returncode: raise ValueError('candidate compatibility bridge failed: '+result.stderr[-2000:])
    compatibility = json.loads(result.stdout)
    if compatibility['core_sha256'] != engine.CORE_SHA256 or set(compatibility['scopes']) != set(RECOVERED):
        raise ValueError('candidate compatibility identity mismatch')
    summary = dict(candidate_core_sha256=engine.CORE_SHA256, original_probe=previous['summary'],
                   inherited_build=inherited['summary'], compatibility=compatibility, external_requests=0)
    stdout = json.dumps(summary, ensure_ascii=False, sort_keys=True)
    return dict(returncode=0, summary=summary, stdout=stdout, stdout_sha256=engine.paired.text_sha(stdout),
                stderr='', mode='frozen historical check plus candidate native replay')


_legacy_health = engine.previous.validate_scope_health


def validate_scope_health(group, database, metadata):
    from starling import _core
    if engine.sha(_core.__file__) != engine.CORE_SHA256: raise ValueError('native health core mismatch')
    return _legacy_health(group, database, metadata, native_embedding_health=lambda path:
        json.loads(_core.embedding_health_json(str(path), 1024, engine.embedding_model, 3)))


def recovered_metadata(checked, group):
    gid = group['group_id']; original, database, rows = historical_scope(gid)
    proof = engine.old.database_proof(database, checked['plans']['scopes'][gid], rows)
    health = json.loads(checked['modules'][0].embedding_health_json(str(database), 1024, engine.embedding_model, 3))
    if not health['complete'] or not health['total']: raise ValueError('inherited final embedding health incomplete')
    if (original / 'scope.json').exists():
        metadata = engine.read(original / 'scope.json')
        metadata['embedding']['final_health'] = health
    else:
        failure = engine.read(original / 'failure.json')
        if failure != dict(error='RuntimeError: embedding technical failures: 32', embedding_request_count=24):
            raise ValueError('recovery only permits the fixed cumulative-failure misclassification')
        holders = checked['runner'].history_holders(group['history'])
        metadata = dict(group=gid, extraction=rows, scope_state='complete', holder_complete=holders,
            holder_failures=[], replay=dict(mode=checked['config']['lifecycle'], stats=None, inherited=True),
            embedding=dict(embedded=None, failed=32, ticks=None, final_health=health,
                missing_execution_counters=['embedded', 'ticks']), embedding_request_count=24,
            sources=dict(documents=len(holders), turns=len(group['history']), engram_refs=list(proof['source_engrams'].values())),
            database=dict(statements=proof['statements'], statement_vectors=proof['vectors']))
    return metadata


def recovery_record(gid):
    original, database, _ = historical_scope(gid)
    return dict(mode='revalidated_recovery', historical_build=str(HISTORY), historical_seal_sha256=HISTORY_SEAL,
        original_core_sha256=HISTORY_CORE, validation_core_sha256=engine.CORE_SHA256,
        original_database=str(database), database_sha256=engine.sha(database), new_external_requests=0,
        original_failure=engine.read(original / 'failure.json') if (original / 'failure.json').exists() else None,
        original_status=engine.read(HISTORY / 'summary.json')['scopes'][gid]['status'])


_scope_audit = engine.scope_audit


def scope_audit(scope, checked, group):
    gid = group['group_id']
    if gid not in RECOVERED:
        if (scope / 'recovery.json').exists(): raise ValueError('unexpected recovery marker')
        return _scope_audit(scope, checked, group)
    original, database, _ = historical_scope(gid)
    record = recovery_record(gid)
    if (engine.read(scope / 'recovery.json') != record or engine.sha(scope / 'frozen.db') != record['database_sha256']
        or engine.read(scope / 'scope.json') != recovered_metadata(checked, group)):
        raise ValueError('inherited recovery database/metadata/provenance mismatch')
    for name in ('extraction.completed.json', 'extraction.receipts.json', 'native.finished.json'):
        if engine.sha(scope / name) != engine.sha(original / name): raise ValueError('inherited raw evidence mismatch')
    started = engine.read(scope / 'scope.started.json'); expected = engine.read(original / 'scope.started.json')
    expected['reservation'] = started['reservation']
    if started != expected: raise ValueError('inherited invocation/clock mismatch')
    result = _scope_audit(scope, checked, group)
    return dict(result, recovery=record)


_run_scope = engine.run_scope


def run_scope(checked, group, scope, ledger):
    gid = group['group_id']
    if gid not in RECOVERED: return _run_scope(checked, group, scope, ledger)
    # 已封存的账本消耗作为继承行纳入总预算；不伪称本阶段发生新调用。
    original, database, _ = historical_scope(gid)
    metadata = recovered_metadata(checked, group)
    scope.mkdir(parents=True)
    reservation = ledger.reserve(gid, 'scope_extraction', checked['plans']['scopes'][gid]['extraction_request_upper_bound'])
    if reservation['state'] != 'reserved': raise ValueError('inherited extraction budget blocked')
    started = engine.read(original / 'scope.started.json'); started['reservation'] = reservation
    engine.write(scope / 'scope.started.json', started)
    for name in ('extraction.completed.json', 'extraction.receipts.json', 'native.finished.json'):
        engine.copy_file(original / name, scope / name)
    engine.copy_file(database, scope / 'frozen.db')
    engine.write(scope / 'scope.json', metadata); engine.write(scope / 'recovery.json', recovery_record(gid))
    ledger.charge_upper(reservation['id'])
    embedding = ledger.reserve(gid, 'scope_embedding', engine.baseline._embedding_reservation(metadata['database']['statements']))
    if embedding['state'] != 'reserved': raise ValueError('inherited embedding budget blocked')
    ledger.settle(embedding['id'], metadata['embedding_request_count'])
    result = scope_audit(scope, checked, group)
    engine.write(scope / 'terminal.json', result)
    return result


_build_summary = engine.build_summary


def build_summary(out, checked):
    summary = _build_summary(out, checked)
    inherited = [v for gid, v in summary['scopes'].items() if gid in RECOVERED]
    count = sum(v['accounting']['observed_native_requests'] for v in inherited)
    tokens = sum(v['accounting']['known_tokens'] for v in inherited)
    embeddings = sum(v['embedding_request_count'] for v in inherited)
    return dict(summary, mode='revalidated_recovery', historical_build_seal_sha256=HISTORY_SEAL,
        inherited_cost=dict(chat_requests=count, known_chat_tokens=tokens, embedding_requests=embeddings),
        new_cost=dict(chat_requests=summary['extraction_observed_requests']-count,
            known_chat_tokens=summary['extraction_known_tokens']-tokens,
            embedding_requests=summary['embedding_requests']-embeddings),
        invocation_scope='Recovered scopes retain historical invocation records; no new provider calls for them.')


engine.current_core = current_core
engine.qualify_probe = qualify_probe
engine.previous.validate_scope_health = validate_scope_health
engine.scope_audit = scope_audit
engine.run_scope = run_scope
engine.build_summary = build_summary
_prepare = engine.prepare
engine.prepare = lambda parent, out, probe=None, evidence=(): _prepare(
    parent, out, engine.DEFAULT_PROBE if probe is None else probe, evidence)


if __name__ == '__main__':
    if sys.argv[1:] == ['bridge']:
        print(json.dumps(compatibility_bridge(), ensure_ascii=False)); raise SystemExit(0)
    raise SystemExit(engine.main())
