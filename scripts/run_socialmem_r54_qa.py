#!/usr/bin/env python3
"""R5.4：只消费封存上下文的 baseline/source10 fresh QA，不执行检索。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
from pathlib import Path
import queue
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTEXTS = ROOT / 'build/socialmem_20260925_r54_budget_ablation_retry1'
DEFAULT_OUT = ROOT / 'build/socialmem_20260925_r54_qa'
EXPECTED_CORE_SHA256 = '02a2a3d8c653d331c700cdf652c59fefe2b812ff99845271bd5137bebf81dd3d'
ARMS = ('baseline', 'source10')
POLICIES = ('legacy', 'grounded_memory_v1')
LEDGER_BUDGET = 500
BOOTSTRAP_SEED = 20260925
BOOTSTRAP_REPETITIONS = 100000


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ablation = load(ROOT / 'scripts/run_socialmem_r54_ablation.py', 'r54_qa_ablation')
statistics = load(ROOT / 'scripts/run_socialmem_r52_v6_v7_qa.py', 'r54_qa_statistics')
read, sha = ablation.read, ablation.sha


def text_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def write(path, value):
    """Replace one complete JSON receipt atomically; a crash cannot leave partial JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    temporary.replace(path)


def verify_seal(contexts):
    if not (contexts / 'seal.json').is_file():
        raise ValueError('seal missing')
    seal = ablation.r53.verify_seal(contexts)
    actual = {p.relative_to(contexts).as_posix() for p in contexts.rglob('*')
              if p.is_file() and p != contexts / 'seal.json' and '__pycache__' not in p.parts}
    if actual != set(seal['files']):
        raise ValueError('seal file set mismatch')
    for name in seal['files']:
        path = contexts / name
        if path.is_symlink() or not path.resolve().is_relative_to(contexts):
            raise ValueError('seal contains unsafe file path')
    return seal


def validate_inputs(contexts):
    """Validate the full four-arm input before imports, adapter creation, or output."""
    contexts = Path(contexts).resolve()
    seal = verify_seal(contexts)
    config, identity = read(contexts / 'config.json'), read(contexts / 'identity.json')
    fixed = {'answer_model': 'qwen3.8-27b', 'answer_max_tokens': 512, 'judge_max_tokens': 64,
             'answer_enable_thinking': False, 'max_retries': 0, 'timeout_ms': 120000,
             'answer_endpoint': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
             'answer_key_env': 'DASHSCOPE_API_KEY', 'core_sha256': EXPECTED_CORE_SHA256,
             'scoring': 'existing_ladder_mc_and_single_yes_no_local_protocol'}
    if any(config.get(k) != v or type(config.get(k)) is not type(v) for k, v in fixed.items()):
        raise ValueError('fixed QA config/protocol mismatch')
    if identity.get('core_sha256') != EXPECTED_CORE_SHA256:
        raise ValueError('identity core mismatch')
    for filename, key in [('config.json', 'config_sha256'), ('scope-manifest.json', 'scope_manifest_sha256')]:
        if sha(contexts / filename) != identity.get(key):
            raise ValueError('identity config/manifest hash mismatch: ' + filename)
    frozen = contexts / 'frozen'
    frozen_files = identity.get('frozen_files', {})
    actual_frozen = {p.relative_to(frozen).as_posix() for p in frozen.rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts}
    if not frozen_files or actual_frozen != set(frozen_files):
        raise ValueError('identity frozen file set mismatch')
    for relative, expected in frozen_files.items():
        if sha(frozen / relative) != expected:
            raise ValueError('identity frozen hash mismatch: ' + relative)
    current_core = list((ROOT / 'build/python/starling').glob('_core*.so'))
    archived_core = list((frozen / 'python/starling').glob('_core*.so'))
    if len(current_core) != 1 or len(archived_core) != 1 or any(
            sha(p) != EXPECTED_CORE_SHA256 for p in current_core + archived_core):
        raise ValueError('current/frozen core mismatch')
    # R5.4 saved updated C++ in implementation; frozen/src is the historical parent tree.
    implementation = contexts / 'implementation'
    production = [p for p in implementation.rglob('*') if p.is_file()
                  and p.relative_to(implementation).parts[0] in ('src', 'include', 'scripts')]
    if not production:
        raise ValueError('retrieval implementation code missing')
    for path in production:
        current = ROOT / path.relative_to(implementation)
        if not current.is_file() or sha(current) != sha(path):
            raise ValueError('current retrieval code drift: ' + str(current))
    for relative in ('scripts/run_socialmem_baseline.py', 'scripts/eval_judge_audit.py',
                     'scripts/eval_ladder.py', 'scripts/eval_ladder_pipeline.py',
                     'scripts/eval_longmemeval.py', 'python/starling/runtime.py'):
        if relative in frozen_files and (not (ROOT / relative).is_file()
                                        or sha(ROOT / relative) != frozen_files[relative]):
            raise ValueError('current QA code drift: ' + relative)
    plan = read(contexts / 'execution-plan.json')
    if plan.get('qa_candidate') != 'source10' or plan.get('arms') != {
            a: list(v) for a, v in ablation.ARMS.items()}:
        raise ValueError('retrieval arm/candidate identity mismatch')
    if plan.get('loaded_core_sha256') != EXPECTED_CORE_SHA256 or Path(plan.get('loaded_core', '')).resolve() != archived_core[0].resolve():
        raise ValueError('retrieval loaded core identity mismatch')
    if (plan.get('embedding_request_limit'), plan.get('answer_requests'), plan.get('judge_requests')) != (690, 0, 0):
        raise ValueError('retrieval request protocol mismatch')
    parent = Path(plan['parent']).resolve()
    parent_config = plan['parent_provenance']['config']
    if config != {**parent_config, 'core_sha256': EXPECTED_CORE_SHA256}:
        raise ValueError('retrieval config drift from parent protocol')
    if read(parent / 'config.json') != parent_config:
        raise ValueError('parent config drift')
    inputs = plan.get('parent_input_sha256', {})
    if set(inputs) != {'sample.json', 'groups.json', 'corpus.jsonl'}:
        raise ValueError('parent input manifest incomplete')
    for name, expected in inputs.items():
        if sha(parent / name) != expected or (name != 'corpus.jsonl' and sha(contexts / name) != expected):
            raise ValueError('parent input hash mismatch: ' + name)
    if inputs['corpus.jsonl'] != identity.get('corpus_sha256'):
        raise ValueError('corpus identity mismatch')
    records, groups = read(contexts / 'sample.json'), read(contexts / 'groups.json')
    ablation.validate_record_groups(records, groups)
    group_ids = [g['group_id'] for g in groups]
    if len(group_ids) != 7 or len(set(group_ids)) != 7:
        raise ValueError('seven unique groups required')
    networks = {str(r.get('source', {}).get('network_id') or r.get('network_id') or '') for r in records}
    if len(networks) != 6 or '' in networks:
        raise ValueError('six identified networks required')
    indexed = {r['item_id']: r for r in records}
    group_by_item = {r['item_id']: g['group_id'] for g in groups for r in g['records']}
    databases = plan['parent_provenance']['database_sha256']
    if set(databases) != set(group_ids):
        raise ValueError('database group identity mismatch')
    for gid, expected in databases.items():
        db = parent / 'runs' / gid / 'frozen.db'
        if not db.is_file() or sha(db) != expected or any(Path(str(db) + suffix).exists() for suffix in ('-wal', '-shm')):
            raise ValueError('parent database identity mismatch')
    rows = {}
    for arm in ablation.ARMS:
        paths = sorted((contexts / arm / 'recalls').glob('*.json'))
        arm_rows = [read(p) for p in paths]
        if len(arm_rows) != 57 or len({r.get('item_id') for r in arm_rows}) != 57 or {r.get('item_id') for r in arm_rows} != set(indexed):
            raise ValueError('duplicate/missing recall item')
        for row in arm_rows:
            item = row['item_id']
            gid = group_by_item[item]
            holders = sorted({t['speaker'] for t in indexed[item]['history']})
            if row.get('group_id') != gid or row.get('holders') != holders:
                raise ValueError('recall group/holder identity mismatch')
            ablation.validate_row(row, arm, databases[gid], EXPECTED_CORE_SHA256, config['max_context_bytes'])
            if row.get('status') != 'ok' or not ablation.healthy_embedding(row):
                raise ValueError('unhealthy recall input')
        summary = {'rows': 57, 'statuses': {'ok': 57}, 'embedding_requests': sum(r['embedding_requests'] for r in arm_rows)}
        if read(contexts / arm / 'summary.json') != summary:
            raise ValueError('recall summary request/terminal mismatch')
        rows[arm] = arm_rows
    comparison = ablation.compare_rows(records, rows)
    comparison['embedding_requests'] = sum(r['embedding_requests'] for rs in rows.values() for r in rs)
    if comparison != read(contexts / 'comparison.json') or comparison['qa_gate'] != 'passed':
        raise ValueError('recomputed retrieval QA gate mismatch')
    if comparison['anchors']['baseline'] != {'hit': 51, 'total': 104} or comparison['anchors']['source10'] != {'hit': 67, 'total': 104}:
        raise ValueError('verified frozen retrieval result mismatch')
    return dict(contexts=contexts, parent=parent, config=config, identity=identity, records=indexed,
                rows=rows, comparison=comparison, seal_sha256=sha(contexts / 'seal.json'), seal=seal)


def _frozen_modules(contexts, config, identity):
    runner = load(contexts / 'frozen/scripts/run_socialmem_baseline.py', 'r54_qa_frozen_runner')
    modules = runner._frozen_imports(contexts, config, identity)
    if sha(modules[0].__file__) != EXPECTED_CORE_SHA256:
        raise ValueError('loaded frozen QA core mismatch')
    return runner, modules


def build_task(arm, policy, record, recall, runner, config, modules):
    if arm not in ARMS or policy not in POLICIES:
        raise ValueError('unregistered QA arm/policy')
    core, _, _, ladder, _, _ = modules
    prompt = runner.answer_prompt(core, ladder, record, recall, {**config, 'answer_policy': policy})
    return dict(item_id=record['item_id'], arm=arm, policy=policy, record=record, recall=recall,
                prompt=prompt, prompt_sha256=text_sha(prompt), context_sha256=text_sha(recall['block']))


def run_task(task, out, runner, modules, ledger, adapters):
    if task['prompt_sha256'] != text_sha(task['prompt']) or task['context_sha256'] != text_sha(task['recall']['block']):
        raise ValueError('prompt/context binding mismatch')
    record = task['record']
    upper = 1 + int(record.get('answer_format', 'multiple_choice') != 'multiple_choice')
    row = {k: task[k] for k in ('item_id', 'arm', 'policy', 'prompt', 'prompt_sha256', 'context_sha256')}
    row.update(terminal=False, correct=False, status='budget_failure', native_attempt_count=0,
               tokens=0, charged_requests=0, fresh=True)
    reservation = ledger.reserve(f"{task['arm']}/{task['policy']}/{task['item_id']}", 'answer_judge', upper)
    row['reservation'] = reservation
    try:
        if reservation['state'] != 'reserved':
            row['error'] = 'request budget exhausted'
        else:
            _, _, answer_llm, judge_llm = adapters
            _, _, audit, _, _, longmem = modules
            def response(llm, prompt, stage):
                payload, text, error = runner.response_text(llm.extract(prompt, ''), stage)
                row[stage] = payload
                attempts = runner._response_attempts(payload)
                if attempts != 1:
                    raise ValueError('missing or non-unit native request evidence')
                row['native_attempt_count'] += attempts
                row['tokens'] += int(payload.get('response', {}).get('total_tokens', 0))
                return text, error
            answer, error = response(answer_llm, task['prompt'], 'answer')
            if error:
                row.update(status='answer_failure', error=error)
            elif record.get('answer_format', 'multiple_choice') == 'multiple_choice':
                prediction = longmem._parse_option_index(answer, len(record['options']))
                if prediction is None:
                    row.update(status='invalid_answer', error='invalid option')
                else:
                    row.update(status='ok', prediction=prediction, correct=prediction == int(record['answer']))
            else:
                prompt = audit._judge_prompt(str(record['question']), str(record['answer']), answer)
                row.update(judge_prompt=prompt, judge_prompt_sha256=text_sha(prompt))
                verdict, error = response(judge_llm, prompt, 'judge')
                if error:
                    row.update(status='judge_failure', error=error)
                else:
                    row.update(status='ok', correct=bool(audit._parse_judge_verdict(verdict)))
            ledger.settle(reservation['id'], row['native_attempt_count'])
            row['charged_requests'] = row['native_attempt_count']
    except Exception as exc:
        row.update(status='technical_failure', correct=False, error=f'{type(exc).__name__}: {exc}', budget_unknown=True)
        if reservation['state'] == 'reserved':
            ledger.charge_upper(reservation['id'])
            row['charged_requests'] = upper
    finally:
        row['terminal'] = True
        write(Path(out) / row['policy'] / row['arm'] / (text_sha(row['item_id']) + '.json'), row)
    return row


def _statistical_names(value):
    """R5.2 statistics are directional; publish actual R5.4 identities everywhere."""
    if isinstance(value, dict):
        return {k.replace('v6', 'baseline').replace('v7', 'source10'): _statistical_names(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_statistical_names(v) for v in value]
    return value


def compare_scores(records, baseline, source10, *, repetitions=None):
    repetitions = BOOTSTRAP_REPETITIONS if repetitions is None else repetitions
    for rows in (baseline, source10):
        if any(r.get('terminal') is not True or (r.get('status') != 'ok' and r.get('correct')) for r in rows):
            raise ValueError('QA terminal/failure score mismatch')
    result = _statistical_names(statistics.compare_scores(baseline, source10))
    ids = {r['item_id'] for r in records}
    if len(ids) != len(records) or ids != {r['item_id'] for r in baseline}:
        raise ValueError('bootstrap record set mismatch')
    left, right = ({r['item_id']: r for r in rows} for rows in (baseline, source10))
    cells = Counter('both_correct' if left[i]['correct'] and right[i]['correct'] else
                    'baseline_only' if left[i]['correct'] else 'source10_only' if right[i]['correct'] else
                    'both_wrong' for i in ids)
    result['four_cells'] = {k: cells[k] for k in ('both_correct', 'baseline_only', 'source10_only', 'both_wrong')}
    def bootstrap(sample):
        return _statistical_names(statistics._bootstrap(sample, [left[r['item_id']] for r in sample],
            [right[r['item_id']] for r in sample], seed=BOOTSTRAP_SEED, repetitions=repetitions))
    result['bootstrap'] = bootstrap(records)
    common = [r for r in records if left[r['item_id']]['status'] == right[r['item_id']]['status'] == 'ok']
    result['common_normal_bootstrap'] = bootstrap(common) if common else None
    result['common_normal_net_source10_minus_baseline'] = result['common_normal_source10_correct'] - result['common_normal_baseline_correct']
    result['eligible_for_expanded_development'] = bool(common and result['common_normal_net_source10_minus_baseline'] >= 5
        and result['common_normal_bootstrap']['ci95_percent'][0] > 0)
    return result


def judge_flip_audit(rows):
    groups = defaultdict(list)
    for row in rows:
        if row.get('status') == 'ok' and 'judge' in row:
            key = (row['item_id'], row['prompt_sha256'], row['answer']['raw_xml'], row['judge_prompt'])
            groups[key].append(row)
    repeated = [rs for rs in groups.values() if len(rs) > 1]
    flips = [rs for rs in repeated if len({r['correct'] for r in rs}) > 1]
    return {'identical_prompt_answer_groups': len(repeated), 'judge_flip_groups': len(flips),
            'flips': [[{k: r[k] for k in ('item_id', 'arm', 'policy', 'correct', 'prompt_sha256')} for r in rs] for rs in flips]}


def _freeze_implementation(out):
    paths = [Path(__file__), Path(statistics.__file__), Path(ablation.__file__), Path(ablation.r53.__file__),
             Path(__file__).resolve().parents[1] / 'scripts/run_socialmem_r51_same_db.py',
             Path(__file__).resolve().parents[1] / 'tests/python/test_socialmem_r54_qa.py']
    for path in paths:
        kind = 'tests/python' if path.name.startswith('test_') else 'scripts'
        target = out / 'implementation' / kind / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def run(contexts, out, workers=4):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('output already exists: ' + str(out))
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError('workers must be 1..4')
    validated = validate_inputs(contexts)
    contexts, config, identity = validated['contexts'], validated['config'], validated['identity']
    runner, modules = _frozen_modules(contexts, config, identity)
    recalls = {a: {r['item_id']: r['recall'] for r in validated['rows'][a]} for a in ARMS}
    tasks = [build_task(a, policy, validated['records'][item], recalls[a][item], runner, config, modules)
             for item in sorted(validated['records']) for policy in POLICIES for a in ARMS]
    if len(tasks) != 228 or len({(t['arm'], t['policy'], t['item_id']) for t in tasks}) != 228:
        raise ValueError('QA task inventory mismatch')
    bound = sum(1 + int(t['record'].get('answer_format', 'multiple_choice') != 'multiple_choice') for t in tasks)
    if bound > LEDGER_BUDGET:
        raise ValueError('QA cohort exceeds request budget')
    out.mkdir(parents=True)
    ledger = runner.BudgetLedger(out / 'request-ledger.sqlite', LEDGER_BUDGET)
    rows = []
    try:
        _freeze_implementation(out)
        # Keep the exact executable dependencies in this output seal, including
        # the native prompt builder and the frozen ledger/adapter/scoring code.
        shutil.copytree(contexts / 'frozen', out / 'frozen', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copyfile(contexts / 'seal.json', out / 'input-seal.json')
        for name in ('scope-manifest.json', 'groups.json'):
            shutil.copyfile(contexts / name, out / name)
        write(out / 'input-validation.json', {k: validated[k] for k in ('seal_sha256', 'comparison')})
        write(out / 'config.json', config)
        write(out / 'identity.json', identity)
        write(out / 'sample.json', list(validated['records'].values()))
        plan = {'contexts': str(contexts), 'contexts_seal_sha256': validated['seal_sha256'],
                'core_sha256': EXPECTED_CORE_SHA256, 'loaded_core': str(getattr(modules[0], '__file__', 'offline_fixture')),
                'arms': list(ARMS), 'policies': list(POLICIES), 'fresh': True, 'questions': 57, 'tasks': 228,
                'workers': workers, 'http_budget': LEDGER_BUDGET, 'cohort_request_upper_bound': bound,
                'retrieval_requests': 0, 'embedding_requests': 0, 'answer_model': config['answer_model'],
                'answer_max_tokens': 512, 'judge_max_tokens': 64, 'answer_enable_thinking': False,
                'judge_enable_thinking': 'provider_default_unset', 'max_retries': 0, 'timeout_ms': 120000,
                'bootstrap_seed': BOOTSTRAP_SEED, 'bootstrap_repetitions': BOOTSTRAP_REPETITIONS,
                'tasks_binding': [{k: t[k] for k in ('item_id', 'arm', 'policy', 'prompt_sha256', 'context_sha256')} for t in tasks]}
        write(out / 'execution-plan.json', plan)
        # Constructors use temporary process environment variables: build sequentially.
        # Extract/embedder are never called. One answer/judge pair serves one task at a time.
        adapters = queue.Queue()
        for _ in range(workers):
            adapters.put(runner._make_native_adapters(modules[0], config))
        def execute(task):
            pair = adapters.get()
            try:
                return run_task(task, out / 'answers', runner, modules, ledger, pair)
            finally:
                adapters.put(pair)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for future in as_completed([pool.submit(execute, task) for task in tasks]):
                rows.append(future.result())
                if len(rows) % 20 == 0:
                    print(f'QA terminal receipts: {len(rows)}/228', flush=True)
        if len(rows) != 228 or any(not r['terminal'] for r in rows):
            raise RuntimeError('QA terminal inventory incomplete')
        comparisons = {}
        for policy in POLICIES:
            pair = {a: sorted([r for r in rows if r['arm'] == a and r['policy'] == policy], key=lambda r: r['item_id']) for a in ARMS}
            comparison = compare_scores(list(validated['records'].values()), pair['baseline'], pair['source10'])
            for arm in ARMS:
                comparison[arm + '_summary'] = statistics._summary(pair[arm], policy, arm)
            comparisons[policy] = comparison
            write(out / 'answers' / policy / 'comparison.json', comparison)
        snapshot = ledger.snapshot()
        if snapshot['reserved'] or snapshot['remaining'] < 0 or snapshot['committed'] != sum(r['charged_requests'] for r in rows):
            raise RuntimeError('ledger does not reconcile with terminal receipts')
        # Verify immutable input again after QA to detect drift during provider calls.
        verify_seal(contexts)
        if sha(contexts / 'seal.json') != validated['seal_sha256']:
            raise RuntimeError('input seal changed during QA')
        summary = dict(state='complete', questions=57, terminal_count=len(rows), policies=comparisons,
                       ledger=snapshot, native_requests=sum(r['native_attempt_count'] for r in rows),
                       tokens=sum(r['tokens'] for r in rows), status_counts=dict(Counter(r['status'] for r in rows)),
                       judge_flip_audit=judge_flip_audit(rows), core_sha256=EXPECTED_CORE_SHA256,
                       eligible_for_expanded_development=any(c['eligible_for_expanded_development'] for c in comparisons.values()),
                       interpretation='source expansion plus statement removal; development cohort only; no automatic promotion')
        write(out / 'summary.json', summary)
        ablation.r53.seal_output(out)
        verify_seal(out)
        return summary
    except BaseException as exc:
        saved = [read(p) for p in out.glob('answers/*/*/*.json')]
        write(out / 'failure-summary.json', dict(state='incomplete', error=f'{type(exc).__name__}: {exc}',
                                               terminal_count=len(saved), ledger=ledger.snapshot()))
        ablation.r53.seal_output(out, 'incomplete')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contexts', type=Path, default=DEFAULT_CONTEXTS)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--validate-only', action='store_true', help='只校验封存输入，不创建输出或适配器')
    args = parser.parse_args()
    if args.validate_only:
        result = validate_inputs(args.contexts)
        print(json.dumps({'state': 'validated', 'questions': len(result['records']),
                          'qa_candidate': 'source10', 'qa_gate': result['comparison']['qa_gate'],
                          'seal_sha256': result['seal_sha256']}, ensure_ascii=False))
    else:
        result = run(args.contexts, args.out, args.workers)
        print(json.dumps({k: v for k, v in result.items() if k != 'policies'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
