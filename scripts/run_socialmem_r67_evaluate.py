#!/usr/bin/env python3
"""R6.7：同库v9/selector同期QA；统一1024预算，原生回答与原始HTTP审计。"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import importlib.util
import json
from pathlib import Path
import queue
import shutil

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('r67_offline_qa', ROOT/'scripts/run_socialmem_r67_selection.py')
offline = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(offline)
previous = offline.previous
parent = previous.parent
e = offline.e
read, write, sha, inventory = e.read, e.write, e.sha, e.inventory
DEFAULT_SELECTION = ROOT/'build/socialmem_20260926_r67_expanded/selection'
ARMS = ('v9', 'selector')
POLICY = 'grounded_memory_v1'
BUDGET = 478
OWN_FILES = ('scripts/run_socialmem_r67_evaluate.py', 'tests/python/test_socialmem_r67_evaluate.py')


def answer_config(checked):
    return dict(checked['config'], answer_max_tokens=1024)


def config_sha(checked):
    return e.text_sha(json.dumps(answer_config(checked), ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def make_tasks(checked, contexts, runner, modules):
    tasks = []
    records = sorted(checked['records'], key=lambda r: e.text_sha('20260926/'+r['item_id']))
    for index, record in enumerate(records):
        for arm in (ARMS if index % 2 == 0 else tuple(reversed(ARMS))):
            task = e.qa_helpers.build_task('source10', POLICY, record, contexts[arm][record['item_id']]['recall'],
                runner, answer_config(checked), modules)
            task.update(arm=arm, execution_config_sha256=config_sha(checked),
                source_selection_status=contexts[arm][record['item_id']].get('selection_status','ok')); tasks.append(task)
    if (len(tasks) != 266 or len({(t['item_id'], t['arm']) for t in tasks}) != 266
        or sum(1 + int(t['record']['answer_format'] != 'multiple_choice') for t in tasks) != BUDGET):
        raise ValueError('paired task inventory/budget mismatch')
    return tasks


def load_inputs(origin):
    origin = Path(origin).resolve(); data = offline.check(origin)
    summary = data['summary']
    if (summary['state'] != 'complete' or summary['qa_gate'] != 'passed'
        or summary['terminal_count'] != 133 or summary['healthy_selections'] < 127 or summary['new_embedding_requests'] != 0
        or summary['control_mismatches'] != 0 or summary['arms']['v9']['anchor_hit'] != 194
        or summary['arms']['v9']['anchors'] != 263): raise ValueError('selection QA gate not satisfied')
    contexts = offline.read_rows(origin, data['checked']['records'], data['checked']['databases'])
    return dict(data, origin=origin, contexts=contexts, selection_summary=summary, selection_seal_sha256=data['seal_sha256'],
        tasks=make_tasks(data['checked'], contexts, data['runner'], data['modules']))


def source_files():
    return dict(offline.source_files(), **{name: sha(ROOT/name) for name in OWN_FILES})


def freeze_program(out):
    files = source_files()
    for name in files: e.builder.copy_file(ROOT/name, out/'source'/name)
    write(out/'program.json', dict(files=files, retrieval_core_sha256=offline.CORE_SHA256, answer_core_sha256=e.CORE_SHA256))


def verify_program(out, current=False):
    program = read(out/'program.json'); files = program.get('files', {})
    if (program.get('retrieval_core_sha256') != offline.CORE_SHA256 or program.get('answer_core_sha256') != e.CORE_SHA256
        or files != inventory(out/'source') or not set(OWN_FILES).issubset(files)):
        raise ValueError('archived program/core identity mismatch')
    if current and files != source_files(): raise ValueError('current execution program drift')
    for name, digest in files.items():
        if name.endswith('.py') and sha(ROOT/name) != digest: raise ValueError('executed program drift: '+name)


def seal_output(out, stage, state='complete'):
    if (out/'seal.json').exists(): raise ValueError('already sealed')
    write(out/'seal.json', dict(schema='r67-temporal-qa-v1', stage=stage, state=state, files=inventory(out)))


def verify_seal(out):
    seal = read(out/'seal.json'); actual = inventory(out); actual.pop('seal.json', None)
    if (seal.get('schema') != 'r67-temporal-qa-v1' or actual != seal.get('files')
        or seal.get('state') not in ('complete', 'incomplete')): raise ValueError('R6.7 QA seal inventory mismatch')
    return seal


def execution_plan(data, stage, workers=0):
    return dict(stage=stage, workers=workers, questions=133, tasks=266, http_budget=BUDGET, http_budget_per_arm=239,
        control_fresh=True, candidate_fresh=True, policy=POLICY, selection_seal_sha256=data['selection_seal_sha256'],
        arms=offline.ARMS, answer_config_sha256=config_sha(data['checked']),
        retrieval_core_sha256=offline.CORE_SHA256, answer_core_sha256=e.CORE_SHA256,
        database_sha256=data['checked']['databases'], answer_model='qwen3.8-27b', answer_max_tokens=1024,
        selection_http_budget=133, combined_http_budget=611, answer_enable_thinking=False, judge_max_tokens=64, judge_enable_thinking='provider_default_unset',
        max_retries=0, timeout_ms=120000, new_embedding_requests=0,
        scheduling='item SHA seed 20260926; adjacent pairs; alternating first arm; submission order only',
        bootstrap_seed=20260925, bootstrap_repetitions=100000,
        tasks_binding=[dict(e.qa_task_binding(t), execution_config_sha256=t['execution_config_sha256'], source_selection_status=t['source_selection_status']) for t in data['tasks']])


def prepare_summary(data):
    return dict(stage='prepare', state='complete', questions=133, contexts=266, tasks=266,
        control_fresh=True, candidate_fresh=True, inherited_answers=0, new_external_requests=0,
        http_budget=BUDGET, selection_seal_sha256=data['selection_seal_sha256'])


def prepare(origin, out):
    out = e.builder.new_output(out); data = load_inputs(origin); out.mkdir(parents=True); freeze_program(out)
    write(out/'stage.json', dict(stage='prepare', origin=str(data['origin'])))
    for name, value in [('answer-config.json', answer_config(data['checked'])), ('sample.json', data['checked']['records']),
                        ('provenance.json', e.provenance(data['checked']))]: write(out/name, value)
    for arm in ARMS: shutil.copytree(data['origin']/arm/'recalls', out/'contexts'/arm)
    shutil.copyfile(data['origin']/'seal.json', out/'selection-seal.json')
    write(out/'execution-plan.json', execution_plan(data, 'prepare'))
    summary = prepare_summary(data); write(out/'summary.json', summary); seal_output(out, 'prepare')
    return summary


def check_prepared(out):
    seal = verify_seal(out); stage = read(out/'stage.json')
    if seal['stage'] != 'prepare' or seal['state'] != 'complete' or stage.get('stage') != 'prepare':
        raise ValueError('incomplete/incorrect prepare input')
    verify_program(out); data = load_inputs(stage['origin'])
    for name, value in [('answer-config.json', answer_config(data['checked'])), ('sample.json', data['checked']['records']),
                        ('provenance.json', e.provenance(data['checked']))]:
        if not e.builder.identical(read(out/name), value): raise ValueError('prepare frozen input drift')
    if (any(inventory(out/'contexts'/arm) != inventory(data['origin']/arm/'recalls') for arm in ARMS)
        or sha(out/'selection-seal.json') != data['selection_seal_sha256']
        or read(out/'execution-plan.json') != execution_plan(data, 'prepare')
        or read(out/'summary.json') != prepare_summary(data)): raise ValueError('prepare context/plan/summary binding mismatch')
    return dict(data, summary=prepare_summary(data), seal_sha256=sha(out/'seal.json'))


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
            if (row.get('source_selection_status') != task['source_selection_status'] or
                (task['source_selection_status'] != 'ok' and row['native_invoked'] is not False)):
                raise ValueError('failed selection must not invoke answer')
            if row.get('execution_config_sha256') != task['execution_config_sha256']:
                raise ValueError('terminal answer configuration mismatch')
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
        retrieval_core_sha256=offline.CORE_SHA256, answer_core_sha256=e.CORE_SHA256,
        selection_seal_sha256=data['selection_seal_sha256'],
        selection_cost={key:data['selection_summary'][key] for key in ('observed_http_attempts','known_tokens','total_tokens','missing_token_usage')},
        interpretation='133题开发集，同期v9/selector新答案配对，选择失败计错；选择使用新核心，回答与HTTP审计沿用旧核心。选择阶段另有最多133次HTTP，不代表全量、保留集或生产结果。')
    if not partial:
        left = [r for r in rows if r['arm'] == 'v9']; right = [r for r in rows if r['arm'] == 'selector']
        comparison = parent.renamed(e.previous.compare_scores(data['checked']['records'], left, right, repetitions=100000))
        comparison['breakdowns'] = parent.breakdowns(data['checked']['records'], left, right)
        arms = {a: arm_summary([r for r in rows if r['arm'] == a]) for a in ARMS}
        comparison['eligible_for_expanded_development'] &= arms['selector']['ok'] >= arms['v9']['ok']
        summary.update(comparison=comparison, arms=arms, primary_endpoint='all_question_accuracy_selector_minus_v9',
            eligible_for_expanded_development=comparison['eligible_for_expanded_development'],
            judge_flip_audit=e.previous.judge_flip_audit(rows))
    return summary


def make_adapters(data, arm):
    return e.make_adapters(dict(data['checked'], config=answer_config(data['checked'])), data['runner'], data['modules'])


def execute_task(task,out,data,ledger,pair,error):
    if task['source_selection_status'] != 'ok':
        pair=None;error='source selection failed; retained in fixed denominator without retry'
    row=e.execute_qa(task,out/'answers',data['runner'],data['modules'],ledger,pair,error)
    row.update(execution_config_sha256=task['execution_config_sha256'],source_selection_status=task['source_selection_status'])
    write(out/'answers'/row['policy']/row['arm']/(e.text_sha(row['item_id'])+'.json'),row)
    return row


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
                return execute_task(task,out,data,ledger,pair,error)
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
        offline.verify_seal(data['origin'])
        if sha(data['origin']/'seal.json') != data['selection_seal_sha256']: raise ValueError('offline input changed during QA')
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
    return dict(summary=summary, seal_sha256=sha(out/'seal.json'), audit_program_files=read(out/'program.json')['files'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'qa', 'check'])
    parser.add_argument('--input', type=Path, default=DEFAULT_SELECTION)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if args.stage == 'check': result = check(args.input)['summary']
    elif args.out is None: parser.error('--out required')
    elif args.stage == 'prepare': result = prepare(args.input, args.out)
    else: result = qa(args.input, args.out, args.workers)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return int(result['state'] != 'complete')


if __name__ == '__main__': raise SystemExit(main())
