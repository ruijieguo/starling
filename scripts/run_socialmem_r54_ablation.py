#!/usr/bin/env python3
"""R5.4 同库来源容量/声明消融。检索与渲染只调用 C++。"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARENT = ROOT / 'build/socialmem_20260925_r50_semantic_real_retry4'
DEFAULT_OUT = ROOT / 'build/socialmem_20260925_r54_budget_ablation'
ARMS = {'baseline': ('evidence_profile_v6', 'hybrid', 10),
        'source7': ('evidence_profile_v6', 'sources', 7),
        'source10': ('evidence_profile_v9', 'sources', 10),
        'sidecar': ('evidence_profile_v9', 'hybrid', 10)}
QA_CANDIDATE = 'source10'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


r53 = load(ROOT / 'scripts/run_socialmem_r53_offline.py', 'r53_for_r54')
read, write, sha = r53.read, r53.write, r53.sha


def source_block(recall):
    return '\n'.join(recall.get('block', '').splitlines()[:recall.get('source_count', 0)])


def healthy_embedding(row):
    if row.get('status') != 'ok' or 'error' in row:
        return False
    holders = row.get('holders', [])
    if not holders or len(set(holders)) != len(holders):
        return False
    receipts = row.get('recall', {}).get('receipts', [])
    if not isinstance(receipts, list) or any(not isinstance(r, dict) for r in receipts):
        return False
    if row.get('mode') == 'sources':
        return not receipts and row.get('embedding_requests') == 0
    return (all(isinstance(r.get('degraded_paths'), list) and not r['degraded_paths'] for r in receipts)
            and row.get('embedding_requests') == len(holders) and len(receipts) == len(holders)
            and sorted(r.get('holder', '') for r in receipts) == sorted(holders))


def validate_record_groups(records, groups):
    flat = [r for g in groups for r in g['records']]
    for rows in (records, flat):
        if len(rows) != 57 or len({r['item_id'] for r in rows}) != 57:
            raise ValueError('57 unique items required; duplicate/missing input')
    if {r['item_id']: r for r in records} != {r['item_id']: r for r in flat}:
        raise ValueError('sample/group full content mismatch')
    budget = 2 * sum(len({t['speaker'] for t in r['history']}) for r in records)
    if budget != 690:
        raise ValueError('cohort holder/embedding budget mismatch')
    return budget


def validate_row(row, arm, database_sha256, core_sha256, max_bytes):
    strategy, mode, k = ARMS[arm]
    if (row.get('arm'), row.get('strategy'), row.get('mode'), row.get('k')) != (arm, strategy, mode, k):
        raise ValueError('arm configuration drift')
    if row.get('database_sha256') != database_sha256 or row.get('core_sha256') != core_sha256:
        raise ValueError('core/database hash mismatch')
    if row.get('terminal') is not True or row.get('status') not in ('ok', 'error', 'degraded'):
        raise ValueError('invalid terminal state')
    if not isinstance(row.get('embedding_requests'), int) or row['embedding_requests'] < 0:
        raise ValueError('request count missing')
    if row['status'] == 'error':
        return
    if 'error' in row or (row['status'] == 'ok') != (not r53.degraded_reasons(row)):
        raise ValueError('status inconsistent with health')
    if row['status'] == 'ok' and not healthy_embedding(row):
        raise ValueError('embedding requests or holder receipts incomplete')
    r = row['recall']
    refs, ids = r['source_refs'], r['statement_ids']
    keys = [r53.source_key(ref) for ref in refs]
    if len(set(keys)) != len(keys) or len(set(ids)) != len(ids):
        raise ValueError('duplicate sources/statements')
    if (len(refs), len(ids)) != (r['source_count'], r['statement_count']) or len(refs) > k:
        raise ValueError('source/statement count mismatch')
    if len(r['block'].encode()) != r['context_bytes'] or not 0 <= r['context_bytes'] <= max_bytes:
        raise ValueError('UTF-8 budget mismatch')
    lines = r['block'].splitlines()
    if len(lines) != len(refs) + len(ids) or any(not s.startswith('[SOURCE]') for s in lines[:len(refs)]):
        raise ValueError('rendered lines mismatch')
    if mode == 'sources' and (ids or r['receipts'] or row['embedding_requests']):
        raise ValueError('source-only used planner or rendered statements')
    if strategy == 'evidence_profile_v9':
        if len(ids) > 3 or r['source_context_bytes'] + r['statement_context_bytes'] != r['context_bytes']:
            raise ValueError('sidecar byte/count mismatch')
        if len(source_block(r).encode()) != r['source_context_bytes']:
            raise ValueError('source byte mismatch')
        selected = [t for t in r53.profile(row).get('sidecar_selection_order', []) if t['rendered']]
        if [t['statement_id'] for t in selected] != ids:
            raise ValueError('sidecar trace mismatch')
        if any(not t.get('source_ref') or r53.source_key(t['source_ref']) not in keys for t in selected):
            raise ValueError('sidecar source not selected')


def compare_rows(records, rows):
    expected = {r['item_id'] for r in records}
    if len(expected) != len(records) or set(rows) != set(ARMS):
        raise ValueError('record/arm set mismatch')
    indexed = {}
    for arm, rs in rows.items():
        idx = {r['item_id']: r for r in rs}
        if len(idx) != len(rs) or set(idx) != expected:
            raise ValueError('item set mismatch')
        indexed[arm] = idx
    unhealthy = sum(not healthy_embedding(r) for rs in rows.values() for r in rs)
    anchors = {a: {'hit': 0, 'total': 0} for a in ARMS}
    details = []
    for record in records:
        item = record['item_id']
        recalls = {a: indexed[a][item].get('recall', {}) for a in ARMS}
        gold = {g['turn_id'] for g in record.get('source', {}).get('evidence_anchors', [])}
        selected = {a: {r.get('turn_id') for r in recalls[a].get('source_refs', [])} for a in ARMS}
        detail = {'item_id': item, 'anchor_total': len(gold)}
        for arm in ARMS:
            hits = len(gold & selected[arm])
            anchors[arm]['hit'] += hits
            anchors[arm]['total'] += len(gold)
            detail[arm + '_anchor_hit'] = hits
            detail[arm + '_source_count'] = recalls[arm].get('source_count', 0)
            detail[arm + '_statement_count'] = recalls[arm].get('statement_count', 0)
        def equal_sources(a, b):
            return recalls[a].get('source_refs') == recalls[b].get('source_refs') and source_block(recalls[a]) == source_block(recalls[b])
        detail['baseline_source7_equal'] = equal_sources('baseline', 'source7')
        detail['source10_sidecar_equal'] = (equal_sources('source10', 'sidecar') and
            recalls['source10'].get('source_context_bytes') == recalls['sidecar'].get('source_context_bytes'))
        detail['expanded_source_set_contains_source7'] = selected['source7'] <= selected['source10']
        detail['source7_to_source10_lost_anchors'] = sorted(gold & (selected['source7'] - selected['source10']))
        detail['source7_to_source10_gained_anchors'] = sorted(gold & (selected['source10'] - selected['source7']))
        detail['qa_context_changed'] = indexed['baseline'][item]['status'] == indexed['source10'][item]['status'] == 'ok' and recalls['baseline'].get('block') != recalls['source10'].get('block')
        details.append(detail)
    controls = sum(not d['baseline_source7_equal'] or not d['source10_sidecar_equal'] for d in details)
    changes = sum(d['qa_context_changed'] for d in details)
    candidate_statements = sum(d['source10_statement_count'] for d in details)
    gate = ('blocked_technical' if unhealthy else 'blocked_source_controls' if controls or candidate_statements
            else 'blocked_anchor_recall' if anchors['source10']['hit'] < anchors['baseline']['hit']
            else 'blocked_unchanged_context' if not changes else 'passed')
    return {'questions': len(records), 'anchors': anchors, 'qa_candidate': QA_CANDIDATE,
            'qa_gate': gate, 'technical_or_degraded_rows': unhealthy,
            'source_control_mismatches': controls, 'changed_qa_contexts': changes,
            'capacity_source_replacements': sum(not d['expanded_source_set_contains_source7'] for d in details),
            'source_only_sidecar_relevance': 'not_applicable',
            'sidecar_qa_eligible': False, 'rows': details}


def query_one(task, parent, out, provenance, config, core, runtime, pipeline):
    gid, record, arm, embedder = task
    strategy, mode, k = ARMS[arm]
    row = dict(item_id=record['item_id'], group_id=gid, arm=arm, strategy=strategy, mode=mode, k=k,
               holders=sorted({t['speaker'] for t in record['history']}),
               database_sha256=provenance['database_sha256'][gid], core_sha256=config['core_sha256'],
               status='error', terminal=False)
    try:
        with tempfile.TemporaryDirectory(prefix='socialmem-r54-') as tmp:
            db = Path(tmp) / 'query.db'
            shutil.copyfile(parent / 'runs' / gid / 'frozen.db', db)
            rt = runtime._build_local_store_sqlite_runtime(db)
            rt.start()
            try:
                row['recall'] = pipeline.recall_observer_block(
                    core, adapter=rt.adapter, embedder=embedder, index=core.SqliteBlobVectorIndex(),
                    question=record['question'], allowed_holders=sorted({t['speaker'] for t in record['history']}),
                    mode=mode, now_iso=config['query_time'], k=k, max_context_bytes=config['max_context_bytes'],
                    include_unknown_time=config['include_unknown_time'], source_strategy=strategy,
                    min_source_items=config['min_source_items'], source_seed_k=config['source_seed_k'],
                    source_seed_max_context_bytes=config['source_seed_max_context_bytes'],
                    source_dialogue_radius=config['source_dialogue_radius'])
                row['status'] = 'degraded' if r53.degraded_reasons(row) else 'ok'
            finally:
                stop = getattr(rt, 'stop', None)
                if callable(stop): stop()
    except Exception as exc:
        row.update(status='error', error=f'{type(exc).__name__}: {exc}')
    row.update(terminal=True, embedding_requests=int(getattr(embedder, 'request_count', 0)))
    try:
        validate_row(row, arm, row['database_sha256'], config['core_sha256'], config['max_context_bytes'])
    except Exception as exc:
        row.update(status='error', error_stage='validation', error=f'{type(exc).__name__}: {exc}')
    write(out / arm / 'recalls' / (hashlib.sha256(record['item_id'].encode()).hexdigest() + '.json'), row)
    return row


def _run(parent, out, workers):
    if not 1 <= workers <= 4: raise ValueError('workers must be 1..4')
    previous = load(ROOT / 'scripts/run_socialmem_r51_same_db.py', 'r51_for_r54')
    provenance = previous.validate_parent(parent)
    records = read(parent / 'sample.json')
    groups = read(parent / 'groups.json')
    budget = validate_record_groups(records, groups)
    if sha(parent / 'corpus.jsonl') != provenance['identity']['corpus_sha256']:
        raise ValueError('corpus hash mismatch')
    inputs = {n: sha(parent / n) for n in ('sample.json', 'groups.json', 'corpus.jsonl')}
    out.mkdir(parents=True)
    config, modules = r53.stage_modules(parent, out, provenance)
    core, runtime, _, _, pipeline, _ = modules
    for name in ['scripts/run_socialmem_r54_ablation.py', 'scripts/run_socialmem_r53_offline.py',
                 'scripts/run_socialmem_r51_same_db.py', 'src/retrieval/source_retriever.cpp',
                 'src/retrieval/retrieval_planner.cpp', 'tests/cpp/test_retrieval_planner.cpp',
                 'include/starling/retrieval/source_retriever.hpp', 'tests/cpp/test_source_retriever.cpp',
                 'tests/python/test_socialmem_r54_ablation.py', 'tests/python/test_source_retriever_binding.py',
                 'docs/superpowers/specs/2026-09-25-socialmem-r54-budget-ablation-design.md',
                 'docs/superpowers/plans/2026-09-25-socialmem-r54-budget-ablation.md']:
        target = out / 'implementation' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    write(out / 'execution-plan.json', dict(parent=str(parent), parent_provenance=provenance,
          parent_input_sha256=inputs, arms=ARMS, qa_candidate=QA_CANDIDATE,
          embedding_request_limit=budget, answer_requests=0, judge_requests=0,
          source_embedding='unused_stub_constructor_only', workers=workers, loaded_core=str(core.__file__),
          loaded_core_sha256=sha(core.__file__)))
    tasks = [(g['group_id'], r, arm,
              previous._build_embedder(core, config, 'dashscope') if mode == 'hybrid'
              else core.StubEmbeddingAdapter(config['embedding_dim']))
             for g in groups for r in g['records'] for arm, (_, mode, _) in ARMS.items()]
    if len(tasks) != 228 or len({(t[1]['item_id'], t[2]) for t in tasks}) != 228:
        raise RuntimeError('task inventory has duplicates')
    def query(task): return query_one(task, parent, out, provenance, config, core, runtime, pipeline)
    rows = {a: [] for a in ARMS}
    for task in tasks[:4]:
        row = query(task); rows[row['arm']].append(row)
        if row['status'] != 'ok': raise RuntimeError('preflight unhealthy; inspect saved receipt')
    print('preflight: 4/4 healthy', flush=True)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for future in as_completed([executor.submit(query, t) for t in tasks[4:]]):
            row = future.result(); rows[row['arm']].append(row)
            count = sum(len(rs) for rs in rows.values())
            if count % 20 == 0: print(f'recalls: {count}/228', flush=True)
    comparison = compare_rows(records, rows)
    for arm, rs in rows.items():
        write(out / arm / 'summary.json', dict(rows=len(rs), statuses=dict(Counter(r['status'] for r in rs)),
                                             embedding_requests=sum(r['embedding_requests'] for r in rs)))
    comparison['embedding_requests'] = sum(r['embedding_requests'] for rs in rows.values() for r in rs)
    if comparison['embedding_requests'] > budget: raise RuntimeError('embedding budget exceeded')
    if previous.validate_parent(parent)['database_sha256'] != provenance['database_sha256']:
        raise RuntimeError('parent database changed')
    if any(sha(parent / name) != digest for name, digest in inputs.items()):
        raise RuntimeError('parent input changed')
    write(out / 'comparison.json', comparison)
    r53.seal_output(out); r53.verify_seal(out)
    return {k: v for k, v in comparison.items() if k != 'rows'}


def run(parent, out, workers=4):
    parent, out = Path(parent).resolve(), Path(out).resolve()
    if out.exists(): raise ValueError('output already exists: ' + str(out))
    try:
        return _run(parent, out, workers)
    except Exception as exc:
        if out.exists():
            rs = [read(p) for p in out.glob('*/recalls/*.json')]
            write(out / 'failure-summary.json', dict(state='incomplete', error=f'{type(exc).__name__}: {exc}',
                  saved_receipts=len(rs), embedding_requests=sum(r.get('embedding_requests', 0) for r in rs)))
            r53.seal_output(out, 'incomplete')
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', type=Path, default=DEFAULT_PARENT)
    p.add_argument('--out', type=Path, default=DEFAULT_OUT)
    p.add_argument('--workers', type=int, default=4)
    args = p.parse_args()
    print(json.dumps(run(args.parent, args.out, args.workers), ensure_ascii=False, indent=2))
