#!/usr/bin/env python3
"""R5.3 同库检索复评；只有 C++ 执行检索，Python 负责封存、调度和统计。

名称沿用计划的 offline，真实查询嵌入仍会请求 DashScope；不调用回答或裁判。
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARENT = ROOT / 'build/socialmem_20260925_r50_semantic_real_retry4'
DEFAULT_OUT = ROOT / 'build/socialmem_20260925_r53_source_sidecar_offline'
ARMS = ('v6', 'v8', 'v8_sources')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def profile(row):
    return row.get('recall', {}).get('source_diagnostics', {}).get('evidence_profile', {})


def degraded_reasons(row):
    return dict(Counter(d.get('reason', 'unknown') for r in row.get('recall', {}).get('receipts', [])
                        for d in r.get('degraded_paths', [])))


def source_key(ref):
    return ref['engram_ref'], ref['clause_id']


def validate_row(row, arm, database_sha256, core_sha256, *, k, max_bytes):
    strategy = 'evidence_profile_v6' if arm == 'v6' else 'evidence_profile_v8'
    if arm not in ARMS or row.get('arm') != arm or row.get('strategy') != strategy:
        raise ValueError('arm/strategy mismatch')
    if row.get('database_sha256') != database_sha256 or row.get('core_sha256') != core_sha256:
        raise ValueError('core/database hash mismatch')
    if row.get('terminal') is not True:
        raise ValueError('non-terminal receipt')
    if row.get('status') == 'error':
        return
    if row.get('status') not in ('ok', 'degraded'):
        raise ValueError('invalid terminal status')
    if 'error' in row or (row['status'] == 'ok') != (not degraded_reasons(row)):
        raise ValueError('status inconsistent with degradation/error')
    r = row['recall']
    refs, ids = r['source_refs'], r['statement_ids']
    keys = [source_key(ref) for ref in refs]
    if len(set(keys)) != len(keys) or len(set(ids)) != len(ids):
        raise ValueError('duplicate source or statement')
    if len(refs) != r['source_count'] or len(ids) != r['statement_count']:
        raise ValueError('count mismatch')
    if len(refs) > k or (arm != 'v6' and len(ids) > 3):
        raise ValueError('item limit exceeded')
    if len(r['block'].encode()) != r['context_bytes'] or not 0 <= r['context_bytes'] <= max_bytes:
        raise ValueError('UTF-8 byte budget mismatch')
    if arm != 'v6':
        if r['source_context_bytes'] + r['statement_context_bytes'] != r['context_bytes']:
            raise ValueError('byte parts mismatch')
        selected = [t for t in profile(row).get('sidecar_selection_order', []) if t['rendered']]
        if [t['statement_id'] for t in selected] != ids:
            raise ValueError('sidecar trace mismatch')
        if any(not t.get('source_ref') or source_key(t['source_ref']) not in keys for t in selected):
            raise ValueError('sidecar has no selected source')
        if arm == 'v8_sources' and ids:
            raise ValueError('source-only rendered sidecar')


def compare_rows(records, v6, v8, controls):
    expected = {r['item_id'] for r in records}
    if len(expected) != len(records):
        raise ValueError('duplicate record item')
    indexed = []
    for rows in (v6, v8, controls):
        idx = {r['item_id']: r for r in rows}
        if len(idx) != len(rows) or set(idx) != expected:
            raise ValueError('item sets do not align')
        indexed.append(idx)
    anchors = {a: {'hit': 0, 'total': 0} for a in ('v6', 'v8')}
    unhealthy = sum(r.get('status') != 'ok' or bool(degraded_reasons(r)) or 'error' in r
                    for rows in (v6, v8, controls) for r in rows)
    details, rejections, degraded = [], Counter(), Counter()
    for record in records:
        item = record['item_id']
        a, b, control = [idx[item] for idx in indexed]
        gold = {v['turn_id'] for v in record.get('source', {}).get('evidence_anchors', [])}
        detail = {'item_id': item, 'anchor_total': len(gold)}
        for arm, row in (('v6', a), ('v8', b)):
            r = row.get('recall', {})
            selected = {v.get('turn_id') for v in r.get('source_refs', [])}
            hit = len(gold & selected)
            anchors[arm]['hit'] += hit
            anchors[arm]['total'] += len(gold)
            detail[arm + '_anchor_hit'] = hit
            detail[arm + '_source_count'] = r.get('source_count', 0)
            detail[arm + '_statement_count'] = r.get('statement_count', 0)
            detail[arm + '_context_bytes'] = r.get('context_bytes', 0)
            degraded.update(degraded_reasons(row))
        ar, br, cr = [r.get('recall', {}) for r in (a, b, control)]
        detail['source_control_equal'] = (b.get('status') == control.get('status') == 'ok'
            and br.get('source_refs') == cr.get('source_refs')
            and br.get('source_context_bytes') == cr.get('source_context_bytes')
            and br.get('block', '').encode()[:br.get('source_context_bytes', 0)] == cr.get('block', '').encode())
        healthy_pair = a.get('status') == b.get('status') == 'ok' and not degraded_reasons(a) and not degraded_reasons(b)
        detail['source_changed'] = healthy_pair and ar.get('source_refs') != br.get('source_refs')
        detail['block_changed'] = healthy_pair and ar.get('block') != br.get('block')
        rejections.update(profile(b).get('sidecar_rejections', {}))
        details.append(detail)
    mismatches = sum(not d['source_control_equal'] for d in details)
    anchor_gate = unhealthy == 0 and anchors['v8']['hit'] >= anchors['v6']['hit']
    gate = ('blocked_technical' if unhealthy else 'blocked_source_control' if mismatches
            else 'blocked_anchor_recall' if not anchor_gate else 'pending_semantic_review')
    return {
        'questions': len(records), 'anchors': anchors,
        'anchor_gate': anchor_gate,
        'source_control_mismatches': mismatches,
        'source_changed_questions': sum(d['source_changed'] for d in details),
        'block_changed_questions': sum(d['block_changed'] for d in details),
        'technical_or_degraded_rows': unhealthy,
        'degraded_reasons_hybrid': dict(degraded), 'sidecar_rejections': dict(rejections),
        'sidecar_count': sum(d['v8_statement_count'] for d in details),
        'sidecar_precision': None, 'qa_gate': gate, 'rows': details,
    }


def seal_output(out, state='complete'):
    files = {p.relative_to(out).as_posix(): sha(p) for p in sorted(Path(out).rglob('*'))
             if p.is_file() and p.name != 'seal.json' and '__pycache__' not in p.parts}
    write(Path(out) / 'seal.json', {'state': state, 'files': files})


def verify_seal(out):
    seal = read(Path(out) / 'seal.json')
    if seal.get('state') != 'complete':
        raise ValueError('incomplete seal')
    if not seal.get('files'):
        raise ValueError('empty seal')
    actual = {p.relative_to(out).as_posix() for p in Path(out).rglob('*')
              if p.is_file() and p.name != 'seal.json' and '__pycache__' not in p.parts}
    if actual != set(seal['files']):
        raise ValueError('seal file set mismatch')
    for relative, digest in seal['files'].items():
        p = Path(out) / relative
        if not p.is_file() or sha(p) != digest:
            raise ValueError('seal hash mismatch: ' + relative)
    return seal


def stage_modules(parent, out, provenance):
    current = list((ROOT / 'build/python/starling').glob('_core*.so'))
    if len(current) != 1:
        raise ValueError('exactly one current core required')
    shutil.copytree(parent / 'frozen', out / 'frozen')
    archived = list((out / 'frozen/python/starling').glob('_core*.so'))
    if len(archived) != 1:
        raise ValueError('exactly one frozen core required')
    shutil.copyfile(current[0], archived[0])
    config = {**provenance['config'], 'core_sha256': sha(archived[0])}
    if config['max_retries'] != 0:
        raise ValueError('embedding accounting requires max_retries=0')
    write(out / 'config.json', config)
    for name in ('scope-manifest.json', 'sample.json', 'groups.json'):
        shutil.copyfile(parent / name, out / name)
    identity = {**provenance['identity'], 'core_sha256': config['core_sha256'],
                'config_sha256': sha(out / 'config.json'),
                'frozen_files': dict(provenance['identity']['frozen_files'])}
    identity['frozen_files'][archived[0].relative_to(out / 'frozen').as_posix()] = sha(archived[0])
    write(out / 'identity.json', identity)
    runner = load(out / 'frozen/scripts/run_socialmem_baseline.py', 'r53_frozen_baseline')
    modules = runner._frozen_imports(out, config, identity)
    return config, modules


def query_one(task, parent, out, provenance, config, core, runtime, pipeline):
    gid, record, arm, embedder = task
    strategy = 'evidence_profile_v6' if arm == 'v6' else 'evidence_profile_v8'
    row = {'item_id': record['item_id'], 'group_id': gid, 'arm': arm, 'strategy': strategy,
           'database_sha256': provenance['database_sha256'][gid], 'core_sha256': config['core_sha256'],
           'status': 'error', 'terminal': False}
    try:
        with tempfile.TemporaryDirectory(prefix='socialmem-r53-') as tmp:
            db = Path(tmp) / 'query.db'
            shutil.copyfile(parent / 'runs' / gid / 'frozen.db', db)
            rt = runtime._build_local_store_sqlite_runtime(db)
            rt.start()
            try:
                row['recall'] = pipeline.recall_observer_block(
                    core, adapter=rt.adapter, embedder=embedder, index=core.SqliteBlobVectorIndex(),
                    question=record['question'], allowed_holders=sorted({t['speaker'] for t in record['history']}),
                    mode='sources' if arm == 'v8_sources' else config['recall_mode'],
                    now_iso=config['query_time'], k=config['k'], max_context_bytes=config['max_context_bytes'],
                    include_unknown_time=config['include_unknown_time'], source_strategy=strategy,
                    min_source_items=config['min_source_items'], source_seed_k=config['source_seed_k'],
                    source_seed_max_context_bytes=config['source_seed_max_context_bytes'],
                    source_dialogue_radius=config['source_dialogue_radius'])
                row['status'] = 'degraded' if degraded_reasons(row) else 'ok'
            finally:
                stop = getattr(rt, 'stop', None)
                if callable(stop):
                    stop()
    except Exception as exc:
        row['status'] = 'error'
        row['error'] = f'{type(exc).__name__}: {exc}'
    row['terminal'] = True
    row['embedding_requests'] = int(embedder.request_count)
    try:
        validate_row(row, arm, row['database_sha256'], config['core_sha256'], k=config['k'], max_bytes=config['max_context_bytes'])
    except Exception as exc:
        row.update(status='error', error_stage='validation', error=f'{type(exc).__name__}: {exc}')
    write(out / arm / 'recalls' / (hashlib.sha256(record['item_id'].encode()).hexdigest() + '.json'), row)
    return row


def _run(parent, out, workers=4):
    parent, out = Path(parent).resolve(), Path(out).resolve()
    if out.exists():
        raise ValueError('output already exists: ' + str(out))
    if not 1 <= workers <= 4:
        raise ValueError('workers must be between 1 and 4')
    previous = load(ROOT / 'scripts/run_socialmem_r51_same_db.py', 'r53_parent_validation')
    provenance = previous.validate_parent(parent)
    groups = read(parent / 'groups.json')
    records = [r for group in groups for r in group['records']]
    if len(records) != 57 or len({r['item_id'] for r in records}) != 57:
        raise ValueError('57 unique items required')
    if {r['item_id']: r for r in records} != {r['item_id']: r for r in read(parent / 'sample.json')}:
        raise ValueError('sample/group full content mismatch')
    if sha(parent / 'corpus.jsonl') != provenance['identity']['corpus_sha256']:
        raise ValueError('parent corpus hash mismatch')
    parent_inputs = {name: sha(parent / name) for name in ('sample.json', 'groups.json', 'corpus.jsonl')}
    out.mkdir(parents=True)
    config, modules = stage_modules(parent, out, provenance)
    core, runtime, _, _, pipeline, _ = modules
    for path in [Path(__file__), ROOT / 'scripts/run_socialmem_r51_same_db.py',
                 ROOT / 'src/retrieval/source_retriever.cpp', ROOT / 'include/starling/retrieval/source_retriever.hpp',
                 ROOT / 'tests/cpp/test_source_retriever.cpp', ROOT / 'tests/python/test_socialmem_r53_offline.py',
                 ROOT / 'docs/superpowers/specs/2026-09-25-socialmem-r53-source-sidecar-design.md',
                 ROOT / 'docs/superpowers/plans/2026-09-25-socialmem-r53-source-sidecar.md']:
        dst = out / 'implementation' / path.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dst)
    budget = 3 * sum(len({t['speaker'] for t in r['history']}) for r in records)
    write(out / 'execution-plan.json', {'parent': str(parent), 'parent_provenance': provenance,
          'arms': ARMS, 'workers': workers, 'embedding_kind': 'dashscope', 'embedding_request_limit': budget,
          'answer_requests': 0, 'judge_requests': 0, 'loaded_core': str(core.__file__),
          'parent_input_sha256': parent_inputs,
          'loaded_core_sha256': sha(core.__file__), 'gold_usage': 'post-retrieval turn-id statistics only'})
    # 配置构造会暂时设置 provider 环境，因此在主线程预先完成，工作线程不改环境。
    tasks = [(group['group_id'], record, arm, previous._build_embedder(core, config, 'dashscope'))
             for group in groups for record in group['records'] for arm in ARMS]


    def query(task):
        return query_one(task, parent, out, provenance, config, core, runtime, pipeline)

    rows = {a: [] for a in ARMS}
    # 先完成一题三组，避免服务不可用时向全部题目重复发送失败请求。
    for task in tasks[:3]:
        r = query(task)
        rows[r['arm']].append(r)
        if r['status'] != 'ok':
            seal_output(out, 'incomplete')
            raise RuntimeError('embedding/recall preflight unhealthy; inspect saved receipt')
    print('preflight: 3/3 healthy', flush=True)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for future in as_completed([executor.submit(query, task) for task in tasks[3:]]):
            r = future.result()
            rows[r['arm']].append(r)
            count = sum(len(rs) for rs in rows.values())
            if count % 15 == 0:
                print(f'recalls: {count}/171', flush=True)
    for arm, rs in rows.items():
        write(out / arm / 'summary.json', {'rows': len(rs), 'statuses': dict(Counter(r['status'] for r in rs)),
              'embedding_requests': sum(r['embedding_requests'] for r in rs)})
    comparison = compare_rows(records, rows['v6'], rows['v8'], rows['v8_sources'])
    comparison['embedding_requests'] = sum(r['embedding_requests'] for rs in rows.values() for r in rs)
    if comparison['embedding_requests'] > budget:
        raise RuntimeError('embedding request limit exceeded')
    # 历史源库在查询前后都逐库验证，不允许打开原始快照进行写入。
    after = previous.validate_parent(parent)
    if after['database_sha256'] != provenance['database_sha256']:
        raise RuntimeError('parent database changed')
    if any(sha(parent / name) != digest for name, digest in parent_inputs.items()):
        raise RuntimeError('parent inputs changed')
    write(out / 'comparison.json', comparison)
    seal_output(out)
    verify_seal(out)
    return {k: v for k, v in comparison.items() if k != 'rows'}


def run(parent, out, workers=4):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('output already exists: ' + str(out))
    try:
        return _run(parent, out, workers)
    except Exception as exc:
        if out.exists():
            saved = [read(p) for p in out.glob('*/recalls/*.json')]
            write(out / 'failure-summary.json', {
                'state': 'incomplete', 'error': f'{type(exc).__name__}: {exc}',
                'saved_receipts': len(saved),
                'embedding_requests': sum(r.get('embedding_requests', 0) for r in saved),
                'answer_requests': 0, 'judge_requests': 0})
            seal_output(out, 'incomplete')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, default=DEFAULT_PARENT)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(run(args.parent, args.out, args.workers), ensure_ascii=False, indent=2))
