#!/usr/bin/env python3
"""R6.5：固定k20与主策略，同期512/1024容量比较；复用C++语义和原生HTTP审计。"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import importlib.util
import json
from pathlib import Path
import queue
import shutil

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('r65_parent', ROOT/'scripts/run_socialmem_r64_evaluate.py')
parent = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(parent)
e = parent.e
read, write, sha, inventory = e.read, e.write, e.sha, e.inventory
DEFAULT_ORIGIN = ROOT/'build/socialmem_20260926_r64_expanded/prepare-v2'
ORIGIN_SEAL = '3390419111061398c14d31feaa4e3e5f096d218024bd883bbfbd4661c28ffb85'
ARMS = {'tokens512': 512, 'tokens1024': 1024}
POLICY = 'grounded_memory_v1'
BUDGET = 478
OWN_FILES = ('scripts/run_socialmem_r65_evaluate.py', 'tests/python/test_socialmem_r65_evaluate.py',
    'docs/superpowers/specs/2026-09-26-socialmem-r65-answer-capacity-design.md',
    'docs/superpowers/plans/2026-09-26-socialmem-r65-answer-capacity.md')


def arm_config(checked, arm):
    return dict(checked['config'], answer_max_tokens=ARMS[arm])


def config_sha(checked, arm):
    return e.text_sha(json.dumps(arm_config(checked, arm), ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def make_tasks(checked, rows, runner, modules):
    indexed = {r['item_id']: r['recall'] for r in rows}; tasks = []
    records = sorted(checked['records'], key=lambda r: e.text_sha('20260926/'+r['item_id']))
    for index, record in enumerate(records):
        arms = list(ARMS) if index % 2 == 0 else list(reversed(ARMS))
        for arm in arms:
            task = e.qa_helpers.build_task('source10', POLICY, record, indexed[record['item_id']],
                                          runner, arm_config(checked, arm), modules)
            task.update(arm=arm, execution_config_sha256=config_sha(checked, arm)); tasks.append(task)
    if (len(tasks) != 266 or len({(t['item_id'], t['arm']) for t in tasks}) != 266
        or sum(1 + int(t['record']['answer_format'] != 'multiple_choice') for t in tasks) != BUDGET):
        raise ValueError('paired task inventory/budget mismatch')
    for left, right in zip(tasks[::2], tasks[1::2]):
        if left['prompt'] != right['prompt'] or left['context_sha256'] != right['context_sha256']:
            raise ValueError('capacity arms changed prompt/context')
    return tasks


def load_inputs(origin):
    origin = Path(origin).resolve(); parent.verify_pinned(origin, ORIGIN_SEAL)
    data = parent.check_prepared(origin)
    return dict(origin=origin, checked=data['checked'], runner=data['runner'], modules=data['modules'],
        candidate_rows=data['candidate_rows'],
        tasks=make_tasks(data['checked'], data['candidate_rows'], data['runner'], data['modules']))


def source_files():
    return dict(parent.source_files(), **{name: sha(ROOT/name) for name in OWN_FILES})


def freeze_program(out):
    files = source_files()
    for name in files: e.builder.copy_file(ROOT/name, out/'source'/name)
    write(out/'program.json', dict(files=files, core_sha256=e.CORE_SHA256))


def verify_program(out, current=False):
    program = read(out/'program.json'); files = program.get('files', {})
    if (program.get('core_sha256') != e.CORE_SHA256 or files != inventory(out/'source')
        or not set(source_files()).issubset(files)): raise ValueError('archived program dependency/hash mismatch')
    if current and files != source_files(): raise ValueError('current execution program drift')


def seal_output(out, stage, state='complete'):
    if (out/'seal.json').exists(): raise ValueError('already sealed')
    write(out/'seal.json', dict(schema='r65-answer-capacity-seal-v1', stage=stage, state=state, files=inventory(out)))


def verify_seal(out):
    seal = read(out/'seal.json'); actual = inventory(out); actual.pop('seal.json', None)
    if (seal.get('schema') != 'r65-answer-capacity-seal-v1' or seal.get('state') not in ('complete', 'incomplete')
        or not actual or actual != seal.get('files')): raise ValueError('R6.5 seal inventory mismatch')
    return seal


def execution_plan(data, stage, workers=0):
    return dict(stage=stage, workers=workers, questions=133, tasks=266, http_budget=BUDGET, http_budget_per_arm=239,
        control_fresh=True, candidate_fresh=True, policy=POLICY, origin_seal_sha256=ORIGIN_SEAL,
        arms={a: dict(answer_max_tokens=n, config_sha256=config_sha(data['checked'], a)) for a, n in ARMS.items()},
        source=dict(strategy='evidence_profile_v9', mode='sources', k=20, max_context_bytes=8000, source_dialogue_radius=1),
        core_sha256=e.CORE_SHA256, build_seal_sha256=parent.BUILD_SEAL, database_sha256=data['checked']['databases'],
        answer_model='qwen3.8-27b', answer_enable_thinking=False, judge_max_tokens=64,
        judge_enable_thinking='provider_default_unset', max_retries=0, timeout_ms=120000, new_embedding_requests=0,
        scheduling='item SHA seed 20260926; adjacent pairs; alternating first arm; submission order only',
        bootstrap_seed=20260925, bootstrap_repetitions=100000,
        tasks_binding=[dict(e.qa_task_binding(t), execution_config_sha256=t['execution_config_sha256']) for t in data['tasks']])


def prepare_summary():
    return dict(stage='prepare', state='complete', questions=133, contexts=133, tasks=266,
        control_fresh=True, candidate_fresh=True, inherited_answers=0, new_external_requests=0,
        http_budget=BUDGET, origin_seal_sha256=ORIGIN_SEAL)


def prepare(origin, out):
    out = e.builder.new_output(out); data = load_inputs(origin); out.mkdir(parents=True)
    write(out/'stage.json', dict(stage='prepare', origin=str(data['origin']))); freeze_program(out)
    for name, value in [('arm-configs.json', {a: arm_config(data['checked'], a) for a in ARMS}),
                        ('sample.json', data['checked']['records']), ('provenance.json', e.provenance(data['checked']))]:
        write(out/name, value)
    shutil.copytree(data['origin']/'candidate-contexts', out/'contexts')
    shutil.copyfile(data['origin']/'seal.json', out/'origin-seal.json')
    write(out/'execution-plan.json', execution_plan(data, 'prepare'))
    summary = prepare_summary(); write(out/'summary.json', summary); seal_output(out, 'prepare')
    return summary


def check_prepared(out):
    seal = verify_seal(out); stage = read(out/'stage.json')
    if seal['stage'] != 'prepare' or seal['state'] != 'complete' or stage.get('stage') != 'prepare':
        raise ValueError('incomplete/incorrect prepare input')
    verify_program(out); data = load_inputs(stage['origin'])
    for name, value in [('arm-configs.json', {a: arm_config(data['checked'], a) for a in ARMS}),
                        ('sample.json', data['checked']['records']), ('provenance.json', e.provenance(data['checked']))]:
        if not e.builder.identical(read(out/name), value): raise ValueError('prepare frozen input drift')
    if (inventory(out/'contexts') != inventory(data['origin']/'candidate-contexts')
        or sha(out/'origin-seal.json') != ORIGIN_SEAL
        or read(out/'execution-plan.json') != execution_plan(data, 'prepare')
        or read(out/'summary.json') != prepare_summary()): raise ValueError('prepare context/plan/summary binding mismatch')
    return dict(data, summary=prepare_summary(), seal_sha256=sha(out/'seal.json'))


def arm_summary(rows):
    costs = [r['accounting'] for r in rows]; complete = all(c['usage_complete'] for c in costs)
    return dict(questions=133, terminals=len(rows), correct=sum(r['correct'] for r in rows),
        ok=sum(r['status'] == 'ok' for r in rows), status_counts=dict(Counter(r['status'] for r in rows)),
        answer_truncated=sum(r.get('answer', {}).get('response', {}).get('finish_reason') == 'length' for r in rows),
        observed_http_attempts=sum(c['observed_http_attempts'] for c in costs),
        known_tokens=sum(c['known_tokens'] for c in costs),
        total_tokens=sum(c['known_tokens'] for c in costs) if complete else None,
        missing_token_usage=sum(c['missing_token_usage'] for c in costs), usage_complete=complete)


def summarize(out, data, partial=False):
    tasks = {(t['item_id'], t['arm'], t['policy']): t for t in data['tasks']}
    rows = [read(p) for p in sorted((out/'answers').glob('*/*/*.json'))]
    observed = [(r.get('item_id'), r.get('arm'), r.get('policy')) for r in rows]
    errors = []; reservations = []; costs = []; valid = []
    if len(set(observed)) != len(rows) or not set(observed).issubset(tasks): errors.append('task duplicate/unknown')
    for row in rows:
        key = (row.get('item_id'), row.get('arm'), row.get('policy')); task = tasks.get(key)
        if task is None: continue
        try:
            costs.append(e.qa_accounting(task, row, data['modules']))
            if row.get('execution_config_sha256') != task['execution_config_sha256']:
                raise ValueError('terminal capacity configuration mismatch')
            reservation = e.validate_qa_terminal(task, row, data['modules'])
            e.validate_started(out, reservation['scope'], 'answer_judge', row['reservation'], e.qa_task_binding(task), row['native_invoked'])
            reservations.append(reservation); valid.append(row)
        except (ValueError, TypeError, KeyError, OSError) as exc: errors.append(f'{key}: {type(exc).__name__}: {exc}')
    expected_starts = {e.text_sha(r['scope'])+'.json' for r in reservations}
    observed_starts = {p.name for p in (out/'started').glob('*.json')}
    ledger = None; ledger_rows = []; ledger_unknown = False
    try:
        ledger_rows = e.ledger_rows(out/'request-ledger.sqlite', BUDGET)
        ledger = e.previous.read_ledger(out/'request-ledger.sqlite', BUDGET)
        if not partial: e.reconcile_ledger(out/'request-ledger.sqlite', BUDGET, reservations)
        else:
            actual = {r['id']: r for r in ledger_rows}
            for reservation in reservations:
                if actual.get(reservation['id']) != reservation: errors.append('partial terminal/ledger mismatch')
    except (ValueError, OSError, e.sqlite3.Error) as exc:
        ledger_unknown = True; errors.append(f'ledger: {type(exc).__name__}: {exc}')
    complete = len(valid) == len(tasks) == len(rows) and set(observed) == set(tasks)
    if not partial and (errors or not complete or observed_starts != expected_starts):
        raise ValueError('terminal/raw/started/ledger audit failed: '+str(errors[:2]))
    unresolved = [r['scope'] for r in ledger_rows if r['state'] == 'reserved']
    unknown = ledger_unknown or bool(errors or unresolved or observed_starts - expected_starts) or any(c['local_attempt_count_unknown'] for c in costs)
    usage_complete = not unknown and all(c['usage_complete'] for c in costs)
    summary = dict(stage='qa', state='incomplete' if partial else 'complete', questions=133, expected_tasks=266,
        terminal_count=len(rows), terminal_inventory_complete=complete, healthy_terminals=sum(r['status'] == 'ok' for r in valid),
        status_counts=dict(Counter(r['status'] for r in valid)), observed_http_attempts=sum(c['observed_http_attempts'] for c in costs),
        known_tokens=sum(c['known_tokens'] for c in costs), total_tokens=sum(c['known_tokens'] for c in costs) if usage_complete else None,
        missing_token_usage=sum(c['missing_token_usage'] for c in costs), usage_complete=usage_complete,
        local_attempt_count_unknown=unknown, remote_execution_unknown=unknown or any(c['remote_execution_unknown'] for c in costs),
        ledger=ledger, ledger_identity_unknown=ledger_unknown, unresolved_reservations=unresolved, audit_errors=errors,
        automatic_promotion=False, control_fresh=True, candidate_fresh=True, inherited_answers=0, new_embedding_requests=0,
        origin_seal_sha256=ORIGIN_SEAL,
        interpretation='133题开发集，同期512/1024新答案配对，固定k20及主策略；不代表全量、保留集或生产结果。')
    if not partial:
        left = [r for r in rows if r['arm'] == 'tokens512']; right = [r for r in rows if r['arm'] == 'tokens1024']
        comparison = parent.renamed(e.previous.compare_scores(data['checked']['records'], left, right, repetitions=100000))
        comparison['breakdowns'] = parent.breakdowns(data['checked']['records'], left, right)
        arms = {a: arm_summary([r for r in rows if r['arm'] == a]) for a in ARMS}
        comparison['eligible_for_expanded_development'] &= arms['tokens1024']['ok'] >= arms['tokens512']['ok']
        summary.update(comparison=comparison, arms=arms, primary_endpoint='all_question_accuracy_1024_minus_512',
            eligible_for_expanded_development=comparison['eligible_for_expanded_development'],
            judge_flip_audit=e.previous.judge_flip_audit(rows))
    return summary


def make_adapters(data, arm):
    return e.make_adapters(dict(data['checked'], config=arm_config(data['checked'], arm)), data['runner'], data['modules'])


def qa(prepared, out, workers=4):
    out = e.builder.new_output(out); e.validate_workers(workers); prepared = Path(prepared).resolve()
    data = check_prepared(prepared); verify_program(prepared, current=True)
    out.mkdir(parents=True); freeze_program(out)
    write(out/'stage.json', dict(stage='qa', prepared=str(prepared), prepare_seal_sha256=data['seal_sha256'], workers=workers))
    shutil.copyfile(prepared/'seal.json', out/'prepare-seal.json')
    write(out/'execution-plan.json', execution_plan(data, 'qa', workers))
    try:
        ledger = e.make_ledger(out/'request-ledger.sqlite', BUDGET); adapters = queue.Queue()
        for _ in range(workers):
            pairs = {}
            for arm in ARMS:
                try: pairs[arm] = (make_adapters(data, arm), None)
                except Exception as exc: pairs[arm] = (None, f'{type(exc).__name__}: {exc}')
            adapters.put(pairs)
        def execute(task):
            pairs = adapters.get(); pair, error = pairs[task['arm']]
            try:
                row = e.execute_qa(task, out/'answers', data['runner'], data['modules'], ledger, pair, error)
                row['execution_config_sha256'] = task['execution_config_sha256']
                write(out/'answers'/row['policy']/row['arm']/(e.text_sha(row['item_id'])+'.json'), row)
                return row
            finally: adapters.put(pairs)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(execute, t) for t in data['tasks']]
            try:
                for count, future in enumerate(as_completed(futures), 1):
                    future.result()
                    if count % 20 == 0: print(f'同期QA完成 {count}/266', flush=True)
            except BaseException:
                for future in futures: future.cancel()
                raise
        summary = summarize(out, data)
        verify_program(out, current=True); verify_seal(prepared)
        if sha(prepared/'seal.json') != data['seal_sha256']: raise ValueError('prepare changed during QA')
        parent.verify_pinned(data['origin'], ORIGIN_SEAL)
        e.builder.old.validate_loaded(data['checked']['prepared'], data['checked']['identity'])
        if any(sha(data['checked']['built']/'runs'/gid/'frozen.db') != digest for gid, digest in data['checked']['databases'].items()):
            raise ValueError('database changed during QA')
        write(out/'summary.json', summary); seal_output(out, 'qa')
    except BaseException as exc:
        write(out/'failure.json', dict(exception=f'{type(exc).__name__}: {exc}'))
        summary = summarize(out, data, partial=True); write(out/'summary.json', summary); seal_output(out, 'qa', 'incomplete')
    return summary


def check(out):
    out = Path(out).resolve(); seal = verify_seal(out)
    if seal['stage'] == 'prepare': return check_prepared(out)
    if seal['stage'] != 'qa': raise ValueError('unknown stage')
    verify_program(out); stage = read(out/'stage.json'); e.validate_workers(stage.get('workers'))
    source = Path(stage['prepared']).resolve()
    if source == out: raise ValueError('cyclic stage input')
    data = check_prepared(source)
    if (stage.get('stage') != 'qa' or stage['prepare_seal_sha256'] != data['seal_sha256']
        or sha(out/'prepare-seal.json') != data['seal_sha256']
        or read(out/'program.json') != read(source/'program.json')
        or read(out/'execution-plan.json') != execution_plan(data, 'qa', stage['workers'])):
        raise ValueError('QA stage/program/plan input drift')
    partial = seal['state'] == 'incomplete'
    if (out/'failure.json').exists() != partial: raise ValueError('failure seal mismatch')
    summary = summarize(out, data, partial=partial)
    if not e.builder.identical(read(out/'summary.json'), summary): raise ValueError('recomputed QA summary mismatch')
    return dict(summary=summary, seal_sha256=sha(out/'seal.json'), audit_program_files=source_files())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='stage', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--origin', type=Path, default=DEFAULT_ORIGIN); p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('qa'); p.add_argument('--input', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--workers', type=int, default=4)
    p = sub.add_parser('check'); p.add_argument('--input', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.stage == 'prepare': result = prepare(args.origin, args.out)
    elif args.stage == 'qa': result = qa(args.input, args.out, args.workers)
    else:
        checked = check(args.input); result = dict(checked['summary'], seal_sha256=checked['seal_sha256'], audit_program_files=source_files())
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)); return int(result['state'] != 'complete')


if __name__ == '__main__': raise SystemExit(main())
