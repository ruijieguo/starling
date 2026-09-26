#!/usr/bin/env python3
"""冻结的回答容量开发实验；原生核心和提示完全复用父版本。"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_socialmem_k30_controlled as base

ROOT = Path(__file__).resolve().parents[1]
PARENT_SEAL = '5ad3963de6b9e4ce17e5cfa92113edf508724cd0dcbd464a8a9b2aebfc48c01d'
PARENT_CORE = 'fa538db8dd1afcea01817e590ae893c59e0ff85f19e90e263dbe24c3dcc226de'
CORE_NAME = 'python/starling/_core.cpython-314-darwin.so'
read, write, sha = base.read, base.write, base.sha


def validate_config(parent, candidate):
    required = {'core_sha256': PARENT_CORE, 'source_strategy': 'focused_window',
                'k': 30, 'http_budget': 1314, 'recall_mode': 'sources',
                'answer_policy': 'grounded_v1', 'answer_max_tokens': 512}
    expected = {**parent, 'answer_max_tokens': 1024}
    if (any(parent.get(k) != v for k, v in required.items())
        or json.dumps(candidate, sort_keys=True) != json.dumps(expected, sort_keys=True)):
        raise ValueError('only answer_max_tokens 512 to 1024 may change')


def validate_code_delta(parent, candidate):
    if parent['frozen_files'] != candidate['frozen_files']:
        raise ValueError('capacity requires identical frozen implementation and prompts')


def copy_frozen_code(parent, work, identity):
    parent, work = Path(parent), Path(work)
    base.verify_files(parent / 'frozen', identity['frozen_files'])
    for name in identity['frozen_files']:
        target = work / 'frozen' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(parent / 'frozen' / name, target)


def verify_preflight_rows(records, parent, rows):
    expected = {r['item_id']: r for r in records}
    ids = [r['item_id'] for r in rows]
    if len(expected) != len(records) or len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError('preflight question set changed')
    for row in rows:
        key = row['item_id']; old = parent[key]
        if row['block'] != old['recall']['block'] or row['source_refs'] != old['recall']['source_refs']:
            raise ValueError('retrieved evidence changed: ' + key)
        if row['prompt'] != old['prompt']:
            raise ValueError('answer prompt changed: ' + key)


def verify_parent(parent):
    if sha(parent / 'completion-seal.json') != PARENT_SEAL:
        raise ValueError('grounded parent seal changed')
    seal = read(parent / 'completion-seal.json'); base.verify_files(parent, seal['files'])
    if (seal['questions'], seal['correct']) != (733, 332):
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
                prompt = runner.answer_prompt(core, ladder, record, recall, config)
                rows.append({'item_id':record['item_id'], 'block':recall['block'],
                             'source_refs':recall['source_refs'], 'prompt':prompt})
    verify_preflight_rows(records, old, rows)
    digest = lambda text: hashlib.sha256(text.encode()).hexdigest()
    return {'verified':True, 'requests':0, 'questions':len(records), 'unchanged_contexts':len(rows), 'unchanged_parent_prompts':len(rows),
            'unchanged_mc_prompts':sum(r['answer_format']=='multiple_choice' for r in records),
            'core_sha256':sha(core.__file__), 'rows':[{'item_id':r['item_id'],
                'block_sha256':digest(r['block']), 'source_refs':r['source_refs'],
                'prompt_sha256':digest(r['prompt'])} for r in rows]}


def prepare(work, parent):
    work, parent = Path(work).resolve(), Path(parent).resolve(); verify_parent(parent)
    if work.exists(): raise ValueError('prepare requires a new directory')
    original = read(parent / 'identity.json'); work.mkdir(parents=True)
    copy_frozen_code(parent, work, original)
    for name in ('corpus.jsonl', 'scope-manifest.json', 'network-split.json'):
        shutil.copyfile(parent / name, work / name)
    config = {**read(parent / 'config.json'), 'answer_max_tokens':1024}
    validate_config(read(parent / 'config.json'), config); write(work / 'config.json', config)
    identity = {**original, 'core_path':str(work / 'frozen' / CORE_NAME), 'core_sha256':config['core_sha256'],
        'config_sha256':sha(work / 'config.json'), 'parent_grounded_seal_sha256':PARENT_SEAL,
        'candidate_change':'仅回答max_tokens从512到1024；核心/提示/来源/模型/评分完全复用父版本',
        'frozen_files':{n:sha(work / 'frozen' / n) for n in original['frozen_files']}}
    validate_code_delta(original, identity); write(work / 'identity.json', identity)
    runner = base.load_runner(work); fingerprint = runner._verify_identity(work, config)
    records, groups = selected_groups(runner, work)
    for group in groups:
        folder = work / 'runs' / group['group_id']; folder.mkdir(parents=True)
        old = parent / 'runs' / group['group_id']; shutil.copyfile(old / 'frozen.db', folder / 'frozen.db')
        metadata = read(old / 'scope.json'); metadata['fingerprint'] = fingerprint; write(folder / 'scope.json', metadata)
    shutil.copyfile(Path(__file__), work / 'run.py')
    shutil.copyfile(Path(base.__file__), work / 'run_socialmem_k30_controlled.py')
    sources = [ROOT / n for n in ('scripts/run_socialmem_answer_capacity.py', 'scripts/analyze_socialmem_answer_capacity.py',
               'tests/python/test_answer_capacity_guard.py', 'tests/python/test_answer_capacity_native.py',
               'tests/python/test_analyze_socialmem_answer_capacity.py')]
    sources += list((ROOT / 'docs').rglob('*.md'))
    for source in sources:
        target = work / 'execution-sources' / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
    preflight = native_preflight(work, parent, runner, records, groups, config)
    write(work / 'native-preflight.json', preflight)
    plan = {'parent_work':str(parent), 'parent_seal_sha256':PARENT_SEAL, 'driver_sha256':sha(work / 'run.py'),
        'core_sha256':config['core_sha256'], 'answer_policy':'grounded_v1', 'answer_max_tokens':1024, 'questions':733, 'groups':39,
        'http_budget':1314, 'scope_ids':[g['group_id'] for g in groups], 'question_ids':[r['item_id'] for r in records]}
    plan['files'] = {str(p.relative_to(work)):sha(p) for p in sorted(work.rglob('*'))
                     if p.is_file() and '__pycache__' not in p.parts}
    write(work / 'execution-plan.json', plan)


def check(work):
    work = Path(work).resolve(); plan = read(work / 'execution-plan.json')
    if sha(Path(__file__)) != plan['driver_sha256'] or plan['parent_seal_sha256'] != PARENT_SEAL:
        raise ValueError('driver or parent identity changed')
    base.verify_manifest(work, plan)
    parent = Path(plan['parent_work']); verify_parent(parent)
    config, identity = read(work / 'config.json'), read(work / 'identity.json')
    validate_config(read(parent / 'config.json'), config); validate_code_delta(read(parent / 'identity.json'), identity)
    for name in ('corpus.jsonl', 'scope-manifest.json', 'network-split.json'):
        if sha(work / name) != sha(parent / name): raise ValueError('input or split changed')
    runner = base.load_runner(work); fingerprint = runner._verify_identity(work, config)
    records, groups = selected_groups(runner, work)
    if ([g['group_id'] for g in groups] != plan['scope_ids'] or [r['item_id'] for r in records] != plan['question_ids']
        or (plan['questions'], plan['groups'], plan['http_budget'], plan['answer_policy']) != (733,39,1314,'grounded_v1')
        or plan['core_sha256'] != config['core_sha256'] or plan['answer_max_tokens'] != 1024):
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
    if bound != 1314: raise ValueError('native request bound changed')
    return runner, groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare','check','run']); parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--parent',type=Path,default=ROOT/'build/socialmem_20260917_grounded_answer_v2')
    args = parser.parse_args()
    if args.mode == 'run' and (args.work/'completion-seal.json').exists():
        raise ValueError('sealed experiment cannot run again')
    if args.mode == 'prepare': prepare(args.work, args.parent)
    runner, groups = check(args.work)
    if args.mode != 'run':
        print(json.dumps({'verified':True,'questions':733,'groups':39,'http_limit':1314,'requests':0})); return
    report = runner.run(args.work, groups=groups, workers=4)
    records = [r for g in groups for r in g['records']]; results = [r for g in report['groups'] for r in g['results']]
    summary = runner.summarize(records, results)
    result = {'state':'complete' if summary['executed']==733 else 'partial', 'summary':summary,
              'ledger':report['ledger'], 'scope_ids':[g['group_id'] for g in groups]}
    write(args.work/'selected-summary.json',result); print(json.dumps(result,ensure_ascii=False))

if __name__ == '__main__': main()
