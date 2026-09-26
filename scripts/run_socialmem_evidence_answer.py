#!/usr/bin/env python3
"""冻结的原生两阶段证据回答实验；Python只负责校验和编排。"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_socialmem_k30_controlled as base

ROOT = Path(__file__).resolve().parents[1]
PARENT_SEAL = '75f49fd3fa3ae3d78faa8e36d5c75987b933e85ccf44c39b4542a98b720cea06'
PARENT_CORE = 'fa538db8dd1afcea01817e590ae893c59e0ff85f19e90e263dbe24c3dcc226de'
CORE_NAME = 'python/starling/_core.cpython-314-darwin.so'
CHANGED = {CORE_NAME, 'include/starling/retrieval/source_retriever.hpp',
           'src/retrieval/source_retriever.cpp', 'bindings/python/bind_05_retrieval.cpp',
           'scripts/run_socialmem_baseline.py', 'tests/cpp/test_source_retriever.cpp', 'CMakeLists.txt'}
ADDED = {'include/starling/retrieval/evidence_answer.hpp', 'src/retrieval/evidence_answer.cpp',
         'tests/cpp/test_evidence_answer.cpp', 'tests/cpp/CMakeLists.txt'}
ANALYSIS_FILES = ('analyze_socialmem_evidence_answer.py', 'analyze_socialmem_grounded_answer.py',
                  'analyze_socialmem_source_focus.py', 'analyze_socialmem_k30.py',
                  'run_socialmem_evidence_answer.py', 'run_socialmem_k30_controlled.py')
read, write, sha = base.read, base.write, base.sha

def freeze_analysis(work):
    folder=Path(work)/'analysis-frozen';folder.mkdir()
    for name in ANALYSIS_FILES:shutil.copyfile(ROOT/'scripts'/name,folder/name)
    write(folder/'manifest.json',{name:sha(folder/name) for name in ANALYSIS_FILES})

def verify_analysis(work):
    folder=Path(work)/'analysis-frozen';manifest=read(folder/'manifest.json')
    if set(manifest)!=set(ANALYSIS_FILES):raise ValueError('analysis dependency set changed')
    base.verify_files(folder,manifest)

def validate_config(parent, candidate):
    digest = candidate.get('core_sha256', '')
    expected = {**parent, 'core_sha256': digest, 'answer_policy': 'evidence_v1', 'http_budget':1895}
    if (parent.get('core_sha256') != PARENT_CORE or parent.get('source_strategy') != 'focused_window'
        or parent.get('k') != 30 or parent.get('http_budget') != 1314
        or parent.get('answer_max_tokens') != 1024 or parent.get('recall_mode') != 'sources' or parent.get('answer_policy') != 'grounded_v1'
        or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)
        or digest == PARENT_CORE
        or json.dumps(candidate, sort_keys=True) != json.dumps(expected, sort_keys=True)):
        raise ValueError('only reviewed native core and evidence_v1 answer policy may change')


def validate_code_delta(parent, candidate):
    old, new = parent['frozen_files'], candidate['frozen_files']
    if set(new) != set(old) | ADDED or any(old[n] != new[n] for n in old if n not in CHANGED):
        raise ValueError('unreviewed code or scoring change')


def verify_preflight_rows(records, parent, rows):
    expected = {r['item_id']: r for r in records}
    ids = [r['item_id'] for r in rows]
    if len(records) != len(expected) or len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError('preflight question set changed')
    for row in rows:
        key = row['item_id']; old = parent[key]
        if row['block'] != old['recall']['block'] or row['source_refs'] != old['recall']['source_refs']:
            raise ValueError('retrieved evidence changed: ' + key)
        if expected[key]['answer_format'] == 'multiple_choice' and row['prompt'] != old['prompt']:
            raise ValueError('multiple choice prompt changed: ' + key)


def verify_parent(parent):
    if sha(parent / 'completion-seal.json') != PARENT_SEAL:
        raise ValueError('focus parent seal changed')
    seal = read(parent / 'completion-seal.json'); base.verify_files(parent, seal['files'])
    if (seal['questions'], seal['correct']) != (733, 345):
        raise ValueError('parent incomplete')


def selected_groups(runner, work):
    records = base.select_records(runner._read_jsonl(work / 'corpus.jsonl'), read(work / 'network-split.json'))
    return records, runner.prepare_groups(records)


def native_preflight(work, parent, runner, records, groups, config):
    modules = runner._frozen_imports(work, config, read(work / 'identity.json'))
    core, runtime, _, ladder, pipe, _ = modules
    old = {r['item_id']: r for r in (read(p) for p in parent.glob('runs/*/questions/*.json'))}
    rows = []
    with tempfile.TemporaryDirectory(prefix='starling-grounded-') as scratch:
        for group in groups:
            database = Path(scratch) / (group['group_id'] + '.db')
            shutil.copyfile(work / 'runs' / group['group_id'] / 'frozen.db', database)
            rt = runtime._build_local_store_sqlite_runtime(database); rt.start()
            embedding, index = core.StubEmbeddingAdapter(8), core.SqliteBlobVectorIndex()
            for record in group['records']:
                recall = pipe.recall_observer_block(core, adapter=rt.adapter, embedder=embedding, index=index,
                    question=record['question'], allowed_holders=runner.history_holders(group['history']),
                    mode='sources', k=config['k'], now_iso=config['query_time'],
                    max_context_bytes=config['max_context_bytes'], include_unknown_time=config['include_unknown_time'],
                    source_strategy=config['source_strategy'])
                legacy_prompt = runner.answer_prompt(core, ladder, record, recall, {**config, 'answer_policy':'grounded_v1'})
                if legacy_prompt != old[record['item_id']]['prompt']:
                    raise ValueError('parent grounded_v1 prompt changed: ' + record['item_id'])
                prompt = runner.answer_prompt(core, ladder, record, recall, config)
                rows.append({'item_id':record['item_id'], 'block':recall['block'],
                             'source_refs':recall['source_refs'], 'prompt':prompt})
    verify_preflight_rows(records, old, rows)
    digest = lambda text: hashlib.sha256(text.encode()).hexdigest()
    return {'verified':True, 'requests':0, 'questions':len(records), 'unchanged_contexts':len(rows),
            'unchanged_parent_prompts':len(rows),
            'unchanged_mc_prompts':sum(r['answer_format']=='multiple_choice' for r in records),
            'core_sha256':sha(core.__file__), 'rows':[{'item_id':r['item_id'],
                'block_sha256':digest(r['block']), 'source_refs':r['source_refs'],
                'prompt_sha256':digest(r['prompt'])} for r in rows]}


def prepare(work, parent):
    work, parent = Path(work).resolve(), Path(parent).resolve(); verify_parent(parent)
    if work.exists(): raise ValueError('prepare requires a new directory')
    original = read(parent / 'identity.json'); work.mkdir(parents=True)
    base.verify_files(parent / 'frozen', original['frozen_files'])
    for name in sorted(set(original['frozen_files']) | ADDED):
        expected = original['frozen_files'].get(name)
        source = ROOT / 'build' / name if name == CORE_NAME else ROOT / name
        if name != CORE_NAME and source.is_file() and sha(source) != expected and name not in CHANGED | ADDED:
            raise ValueError('unreviewed workspace drift: ' + name)
        if name not in CHANGED | ADDED: source = parent / 'frozen' / name
        target = work / 'frozen' / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for name in ('corpus.jsonl', 'scope-manifest.json', 'network-split.json'):
        shutil.copyfile(parent / name, work / name)
    config = {**read(parent / 'config.json'), 'core_sha256':sha(work / 'frozen' / CORE_NAME),
              'answer_policy':'evidence_v1', 'http_budget':1895}
    validate_config(read(parent / 'config.json'), config); write(work / 'config.json', config)
    identity = {**original, 'core_path':str(work / 'frozen' / CORE_NAME), 'core_sha256':config['core_sha256'],
        'config_sha256':sha(work / 'config.json'), 'parent_grounded_seal_sha256':PARENT_SEAL,
        'candidate_change':'C++两阶段自由回答及引用核验；每自由题增加至多一次请求，来源/选择题/模型/评分不变',
        'frozen_files':{n:sha(work / 'frozen' / n) for n in sorted(set(original['frozen_files']) | ADDED)}}
    validate_code_delta(original, identity); write(work / 'identity.json', identity)
    runner = base.load_runner(work); fingerprint = runner._verify_identity(work, config)
    records, groups = selected_groups(runner, work)
    for group in groups:
        folder = work / 'runs' / group['group_id']; folder.mkdir(parents=True)
        old = parent / 'runs' / group['group_id']; shutil.copyfile(old / 'frozen.db', folder / 'frozen.db')
        metadata = read(old / 'scope.json'); metadata['fingerprint'] = fingerprint; write(folder / 'scope.json', metadata)
    shutil.copyfile(Path(__file__), work / 'run.py')
    shutil.copyfile(Path(base.__file__), work / 'run_socialmem_k30_controlled.py')
    sources = [ROOT / n for n in ('scripts/run_socialmem_evidence_answer.py',
               'scripts/analyze_socialmem_evidence_answer.py', 'tests/python/test_evidence_answer.py',
               'tests/python/test_evidence_answer_native.py', 'tests/python/test_evidence_answer_guard.py',
               'tests/python/test_analyze_socialmem_evidence_answer.py')]
    sources += list((ROOT / 'docs').rglob('*.md'))
    for source in sources:
        target = work / 'execution-sources' / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
    preflight = native_preflight(work, parent, runner, records, groups, config)
    write(work / 'native-preflight.json', preflight)
    freeze_analysis(work)
    plan = {'parent_work':str(parent), 'parent_seal_sha256':PARENT_SEAL, 'driver_sha256':sha(work / 'run.py'),
        'core_sha256':config['core_sha256'], 'answer_policy':'evidence_v1', 'questions':733, 'groups':39,
        'http_budget':1895, 'scope_ids':[g['group_id'] for g in groups], 'question_ids':[r['item_id'] for r in records]}
    plan['files'] = {str(p.relative_to(work)):sha(p) for p in sorted(work.rglob('*'))
                     if p.is_file() and '__pycache__' not in p.parts}
    write(work / 'execution-plan.json', plan)


def check(work):
    work = Path(work).resolve(); plan = read(work / 'execution-plan.json')
    if sha(Path(__file__)) != plan['driver_sha256'] or plan['parent_seal_sha256'] != PARENT_SEAL:
        raise ValueError('driver or parent identity changed')
    base.verify_manifest(work, plan)
    verify_analysis(work)
    parent = Path(plan['parent_work']); verify_parent(parent)
    config, identity = read(work / 'config.json'), read(work / 'identity.json')
    validate_config(read(parent / 'config.json'), config); validate_code_delta(read(parent / 'identity.json'), identity)
    for name in ('corpus.jsonl', 'scope-manifest.json', 'network-split.json'):
        if sha(work / name) != sha(parent / name): raise ValueError('input or split changed')
    runner = base.load_runner(work); fingerprint = runner._verify_identity(work, config)
    records, groups = selected_groups(runner, work)
    if ([g['group_id'] for g in groups] != plan['scope_ids'] or [r['item_id'] for r in records] != plan['question_ids']
        or (plan['questions'], plan['groups'], plan['http_budget'], plan['answer_policy']) != (733,39,1895,'evidence_v1')
        or plan['core_sha256'] != config['core_sha256']):
        raise ValueError('selected set or plan changed')
    for group in groups:
        folder = work / 'runs' / group['group_id']
        if runner.scope_state(folder, fingerprint) != 'terminal' or (folder / 'scope.failure.json').exists():
            raise ValueError('source unavailable; extraction prohibited')
        if sha(folder / 'frozen.db') != sha(parent / 'runs' / group['group_id'] / 'frozen.db'):
            raise ValueError('source database changed')
    preflight = read(work / 'native-preflight.json')
    if (preflight['verified'] is not True or preflight['core_sha256'] != config['core_sha256']
        or (preflight['questions'],preflight['unchanged_contexts'],preflight['unchanged_mc_prompts'],preflight['requests']) != (733,733,152,0)
        or preflight.get('unchanged_parent_prompts') != 733
        or sorted(r['item_id'] for r in preflight['rows']) != sorted(plan['question_ids'])):
        raise ValueError('native preflight changed')
    bound = sum(runner.question_request_bound(r, config, work/'runs'/g['group_id']/'frozen.db')
                for g in groups for r in g['records'])
    if bound != 1895: raise ValueError('native request bound changed')
    return runner, groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare','check','run']); parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--parent',type=Path,default=ROOT/'build/socialmem_20260918_answer_capacity_v2')
    args = parser.parse_args()
    if args.mode == 'run' and (args.work/'completion-seal.json').exists():
        raise ValueError('sealed experiment cannot run')
    if args.mode == 'prepare': prepare(args.work, args.parent)
    runner, groups = check(args.work)
    if args.mode != 'run':
        print(json.dumps({'verified':True,'questions':733,'groups':39,'http_limit':1895,'requests':0})); return
    report = runner.run(args.work, groups=groups, workers=4)
    records = [r for g in groups for r in g['records']]; results = [r for g in report['groups'] for r in g['results']]
    summary = runner.summarize(records, results)
    result = {'state':'complete' if summary['executed']==733 else 'partial', 'summary':summary,
              'ledger':report['ledger'], 'scope_ids':[g['group_id'] for g in groups]}
    write(args.work/'selected-summary.json',result); print(json.dumps(result,ensure_ascii=False))

if __name__ == '__main__': main()
