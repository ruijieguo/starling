#!/usr/bin/env python3
"""R6.4：固定k10控制与k20候选。只编排既有C++，不实现检索或回答语义。"""
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import importlib.util
import json
from pathlib import Path
import queue
import shutil

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('r64_parent', ROOT/'scripts/run_socialmem_r63_evaluate.py')
parent = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(parent)
e = parent.engine
read, write, sha, inventory = e.read, e.write, e.sha, e.inventory
DEFAULT_CONTROL = ROOT/'build/socialmem_20260926_r63_expanded/qa'
DEFAULT_CONTEXTS = ROOT/'build/socialmem_20260926_r63_work/offline-selection'
CONTROL_SEAL = '68c521e4384ba87aae306c63948fcf4ed00b77216dbdab819aef7d3e3493591b'
CONTEXT_SEAL = '0b034b0d829ff2abaa743d1117dba751485bccabfb080d5f2e5b25161ea77749'
BUILD_SEAL = '02922356edb7b78761b3ab97d97e1989bc287baea023bdaff57b519d2d98a2a2'
POLICIES = ('legacy', 'grounded_memory_v1')
BUDGET = 478
OWN_FILES = ('scripts/run_socialmem_r64_evaluate.py', 'tests/python/test_socialmem_r64_evaluate.py',
    'docs/superpowers/specs/2026-09-26-socialmem-r64-source-capacity-design.md',
    'docs/superpowers/plans/2026-09-26-socialmem-r64-source-capacity.md')


def verify_pinned(path, digest):
    path = Path(path).resolve()
    if sha(path/'seal.json') != digest: raise ValueError('fixed origin seal mismatch')
    seal = read(path/'seal.json'); actual = inventory(path); actual.pop('seal.json', None)
    if actual != seal.get('files'): raise ValueError('origin seal inventory mismatch')
    return seal


def validate_candidate_rows(checked, rows, modules):
    records = {r['item_id']: r for r in checked['records']}
    gids = {r['item_id']: g['group_id'] for g in checked['groups'] for r in g['records']}
    if len(rows) != 133 or {r.get('item_id') for r in rows} != set(records):
        raise ValueError('candidate context inventory duplicate/missing')
    # 增加一个编排标签，仍调用既有来源验证和C++渲染；不改变旧臂。
    validator = e.ablation.load(ROOT/'scripts/run_socialmem_r54_ablation.py', 'r64_context_validator')
    validator.ARMS = {'v9_20': ('evidence_profile_v9', 'sources', 20)}
    for row in rows:
        item = row['item_id']; gid = gids[item]; record = records[item]
        if (row.get('group_id') != gid or row.get('holders') != e.baseline.history_holders(record['history'])
            or row.get('status') != 'ok' or type(row.get('embedding_requests')) is not int
            or row['embedding_requests'] != 0 or type(row.get('k')) is not int):
            raise ValueError('candidate context identity/health mismatch')
        validator.validate_row(row, 'v9_20', checked['databases'][gid], e.CORE_SHA256, 8000)
        e.validate_context(modules[0], record, row, checked['plans']['scopes'][gid],
            checked['summary']['health'][gid]['source_engrams'], lambda _: None)


def make_tasks(checked, rows, runner, modules):
    indexed = {r['item_id']: r['recall'] for r in rows}; tasks = []
    for record in checked['records']:
        for policy in POLICIES:
            task = e.qa_helpers.build_task('source10', policy, record, indexed[record['item_id']],
                                           runner, checked['config'], modules)
            task['arm'] = 'source20'; tasks.append(task)
    if len(tasks) != 266 or sum(1 + int(t['record'].get('answer_format') != 'multiple_choice') for t in tasks) != BUDGET:
        raise ValueError('candidate task inventory/budget mismatch')
    return tasks


def load_inputs(control, contexts):
    control, contexts = Path(control).resolve(), Path(contexts).resolve()
    verify_pinned(control, CONTROL_SEAL); verify_pinned(contexts, CONTEXT_SEAL)
    historical = parent.check(control, 'qa'); checked = historical['build']
    if checked['seal_sha256'] != BUILD_SEAL: raise ValueError('fixed eight-database build mismatch')
    plan = read(contexts/'plan.json')
    expected = dict(build_seal_sha256=BUILD_SEAL, core_sha256=e.CORE_SHA256,
        config_sha256=sha(checked['built']/'config.json'), database_sha256=checked['databases'],
        reference_retrieve_seal_sha256=read(control/'stage.json')['input_seal_sha256'],
        embedding_adapter='StubEmbeddingAdapter', expected_external_requests=0, questions=133)
    if any(plan.get(k) != v for k, v in expected.items()) or plan['arms'].get('v9_20') != ['evidence_profile_v9', 'sources', 20]:
        raise ValueError('offline context plan identity mismatch')
    runner, modules = e.runtime_modules(checked)
    rows = [read(p) for p in sorted((contexts/'v9_20/recalls').glob('*.json'))]
    validate_candidate_rows(checked, rows, modules)
    controls = sorted((r for r in historical['rows'] if r['arm'] == 'source10'), key=lambda r:(r['item_id'], r['policy']))
    if len(controls) != 266: raise ValueError('control answer inventory mismatch')
    return dict(checked=checked, runner=runner, modules=modules, candidate_rows=rows, controls=controls,
        tasks=make_tasks(checked, rows, runner, modules), control=control, contexts=contexts)


def source_files():
    return dict(e.source_files(), **{name: sha(ROOT/name) for name in OWN_FILES})


def freeze_program(out):
    files = source_files()
    for name in files: e.builder.copy_file(ROOT/name, out/'source'/name)
    write(out/'program.json', dict(files=files, core_sha256=e.CORE_SHA256))


def verify_program(out, current=False):
    program = read(out/'program.json'); files = program.get('files', {})
    if (program.get('core_sha256') != e.CORE_SHA256 or files != inventory(out/'source')
        or not set(source_files()).issubset(files)):
        raise ValueError('archived program dependency/hash mismatch')
    if current and files != source_files(): raise ValueError('current execution program drift')


def seal_output(out, stage, state='complete'):
    if (out/'seal.json').exists(): raise ValueError('already sealed')
    write(out/'seal.json', dict(schema='r64-capacity-seal-v1', stage=stage, state=state, files=inventory(out)))


def verify_seal(out):
    seal = read(out/'seal.json'); actual = inventory(out); actual.pop('seal.json', None)
    if (seal.get('schema') != 'r64-capacity-seal-v1' or seal.get('state') not in ('complete', 'incomplete')
        or not actual or actual != seal.get('files')): raise ValueError('R6.4 seal inventory mismatch')
    return seal


def execution_plan(data, stage, workers=0):
    return dict(stage=stage, workers=workers, questions=133, candidate_tasks=266, http_budget=BUDGET,
        control_fresh=False, candidate_fresh=True, control_seal_sha256=CONTROL_SEAL, contexts_seal_sha256=CONTEXT_SEAL,
        control=dict(strategy='evidence_profile_v9', mode='sources', k=10),
        candidate=dict(strategy='evidence_profile_v9', mode='sources', k=20),
        core_sha256=e.CORE_SHA256, build_seal_sha256=BUILD_SEAL, database_sha256=data['checked']['databases'],
        answer_model='qwen3.8-27b', answer_max_tokens=512, answer_enable_thinking=False,
        judge_max_tokens=64, judge_enable_thinking='provider_default_unset', max_retries=0, timeout_ms=120000,
        max_context_bytes=8000, source_dialogue_radius=1, new_embedding_requests=0,
        bootstrap_seed=20260925, bootstrap_repetitions=100000,
        tasks_binding=[e.qa_task_binding(t) for t in data['tasks']])


def prepare_summary(data):
    return dict(stage='prepare', state='complete', questions=133, contexts=133, candidate_tasks=266,
        inherited_control_answers=266, control_fresh=False, new_external_requests=0, http_budget=BUDGET,
        control_seal_sha256=CONTROL_SEAL, contexts_seal_sha256=CONTEXT_SEAL)


def prepare(control, contexts, out):
    out = e.builder.new_output(out); data = load_inputs(control, contexts); out.mkdir(parents=True)
    write(out/'stage.json', dict(stage='prepare', control=str(data['control']), contexts=str(data['contexts'])))
    freeze_program(out)
    for name, value in [('config.json', data['checked']['config']), ('sample.json', data['checked']['records']),
                        ('provenance.json', e.provenance(data['checked']))]: write(out/name, value)
    shutil.copytree(data['contexts']/'v9_20/recalls', out/'candidate-contexts')
    for policy in POLICIES: shutil.copytree(data['control']/'answers'/policy/'source10', out/'control-answers'/policy/'source10')
    for name, origin in [('control-seal.json', data['control']), ('contexts-seal.json', data['contexts'])]:
        shutil.copyfile(origin/'seal.json', out/name)
    write(out/'execution-plan.json', execution_plan(data, 'prepare'))
    summary = prepare_summary(data); write(out/'summary.json', summary); seal_output(out, 'prepare')
    return summary


def check_prepared(out):
    seal = verify_seal(out); stage = read(out/'stage.json')
    if seal['stage'] != 'prepare' or seal['state'] != 'complete' or stage.get('stage') != 'prepare':
        raise ValueError('incomplete/incorrect prepare input')
    verify_program(out); data = load_inputs(stage['control'], stage['contexts'])
    for name, value in [('config.json', data['checked']['config']), ('sample.json', data['checked']['records']),
                        ('provenance.json', e.provenance(data['checked']))]:
        if not e.builder.identical(read(out/name), value): raise ValueError('prepare frozen input drift')
    if inventory(out/'candidate-contexts') != inventory(data['contexts']/'v9_20/recalls'):
        raise ValueError('candidate context copy drift')
    for policy in POLICIES:
        if inventory(out/'control-answers'/policy/'source10') != inventory(data['control']/'answers'/policy/'source10'):
            raise ValueError('control answer copy drift')
    if (sha(out/'control-seal.json') != CONTROL_SEAL or sha(out/'contexts-seal.json') != CONTEXT_SEAL
        or read(out/'execution-plan.json') != execution_plan(data, 'prepare')
        or read(out/'summary.json') != prepare_summary(data)):
        raise ValueError('prepare plan/summary/origin binding mismatch')
    return dict(data, summary=prepare_summary(data), seal_sha256=sha(out/'seal.json'))


def renamed(value):
    if isinstance(value, dict):
        return {k.replace('baseline', 'control').replace('source10', 'candidate'): renamed(v) for k, v in value.items()}
    if isinstance(value, list): return [renamed(v) for v in value]
    return value


def breakdowns(records, controls, candidates):
    left = {r['item_id']: r for r in controls}; right = {r['item_id']: r for r in candidates}; result = {}
    for dimension in ('network', 'question_type', 'answer_format'):
        buckets = defaultdict(list)
        for r in records:
            label = r['source']['network_id'] if dimension == 'network' else r['query_type'] if dimension == 'question_type' else r['answer_format']
            buckets[label].append(r['item_id'])
        result[dimension] = {label: dict(questions=len(ids), **{name: dict(correct=sum(index[i]['correct'] for i in ids),
            ok=sum(index[i]['status'] == 'ok' for i in ids)) for name, index in [('control', left), ('candidate', right)]})
            for label, ids in sorted(buckets.items())}
    return result


def summarize(out, data, partial=False):
    tasks = {(t['item_id'], t['arm'], t['policy']): t for t in data['tasks']}
    rows = [read(p) for p in sorted((out/'answers').glob('*/*/*.json'))]
    observed = [(r.get('item_id'), r.get('arm'), r.get('policy')) for r in rows]
    errors = []; reservations = []; costs = []; valid = []
    if len(set(observed)) != len(rows) or not set(observed).issubset(tasks): errors.append('candidate task duplicate/unknown')
    for row in rows:
        key = (row.get('item_id'), row.get('arm'), row.get('policy')); task = tasks.get(key)
        if task is None: continue
        costs.append(e.qa_accounting(task, row, data['modules']))
        try:
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
    inventory_complete = len(valid) == len(tasks) == len(rows) and set(observed) == set(tasks)
    if not partial and (errors or not inventory_complete or observed_starts != expected_starts):
        raise ValueError('candidate terminal/raw/started/ledger audit failed: '+str(errors[:2]))
    unresolved = [r['scope'] for r in ledger_rows if r['state'] == 'reserved']
    unknown = ledger_unknown or bool(errors or unresolved or observed_starts - expected_starts) or any(c['local_attempt_count_unknown'] for c in costs)
    usage_complete = not unknown and all(c['usage_complete'] for c in costs)
    summary = dict(stage='qa', state='incomplete' if partial else 'complete', questions=133,
        expected_candidate_tasks=266, terminal_count=len(rows), terminal_inventory_complete=inventory_complete,
        healthy_terminals=sum(r['status'] == 'ok' for r in valid), status_counts=dict(Counter(r['status'] for r in valid)),
        observed_http_attempts=sum(c['observed_http_attempts'] for c in costs),
        known_tokens=sum(c['known_tokens'] for c in costs), total_tokens=sum(c['known_tokens'] for c in costs) if usage_complete else None,
        missing_token_usage=sum(c['missing_token_usage'] for c in costs), usage_complete=usage_complete,
        local_attempt_count_unknown=unknown, remote_execution_unknown=unknown or any(c['remote_execution_unknown'] for c in costs),
        ledger=ledger, ledger_identity_unknown=ledger_unknown, unresolved_reservations=unresolved, audit_errors=errors,
        automatic_promotion=False, control_fresh=False, inherited_control_answers=266, new_embedding_requests=0,
        control_seal_sha256=CONTROL_SEAL, contexts_seal_sha256=CONTEXT_SEAL,
        interpretation='133题开发集；k10为固定历史控制，k20为新答案；跨轮差值不排除生成和裁判波动。')
    if not partial:
        policies = {}
        for policy in POLICIES:
            left = [r for r in data['controls'] if r['policy'] == policy]; right = [r for r in rows if r['policy'] == policy]
            comparison = renamed(e.previous.compare_scores(data['checked']['records'], left, right, repetitions=100000))
            comparison['breakdowns'] = breakdowns(data['checked']['records'], left, right)
            comparison['arms'] = {name: dict(questions=133, correct=sum(r['correct'] for r in arm),
                ok=sum(r['status'] == 'ok' for r in arm), status_counts=dict(Counter(r['status'] for r in arm)))
                for name, arm in [('control', left), ('candidate', right)]}
            policies[policy] = comparison
        summary.update(policies=policies, primary_endpoint='grounded_memory_v1_all_question_accuracy_gain',
            eligible_for_expanded_development=policies['grounded_memory_v1']['eligible_for_expanded_development'],
            judge_flip_audit=e.previous.judge_flip_audit(data['controls']+rows))
    return summary


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
            try: adapters.put((e.make_adapters(data['checked'], data['runner'], data['modules']), None))
            except Exception as exc: adapters.put((None, f'{type(exc).__name__}: {exc}'))
        def execute(task):
            pair, error = adapters.get()
            try: return e.execute_qa(task, out/'answers', data['runner'], data['modules'], ledger, pair, error)
            finally: adapters.put((pair, error))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(execute, t) for t in data['tasks']]
            try:
                for count, future in enumerate(as_completed(futures), 1):
                    future.result()
                    if count % 20 == 0: print(f'候选QA完成 {count}/266', flush=True)
            except BaseException:
                for future in futures: future.cancel()
                raise
        summary = summarize(out, data)
        verify_program(out, current=True); verify_seal(prepared)
        if sha(prepared/'seal.json') != data['seal_sha256']: raise ValueError('prepare changed during QA')
        verify_pinned(data['control'], CONTROL_SEAL); verify_pinned(data['contexts'], CONTEXT_SEAL)
        e.builder.old.validate_loaded(data['checked']['prepared'], data['checked']['identity'])
        if any(sha(data['checked']['built']/'runs'/gid/'frozen.db') != digest for gid, digest in data['checked']['databases'].items()):
            raise ValueError('database changed during QA')
        write(out/'summary.json', summary); seal_output(out, 'qa')
    except BaseException as exc:
        write(out/'failure.json', dict(exception=f'{type(exc).__name__}: {exc}'))
        summary = summarize(out, data, partial=True)
        write(out/'summary.json', summary); seal_output(out, 'qa', 'incomplete')
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
    p = sub.add_parser('prepare'); p.add_argument('--control', type=Path, default=DEFAULT_CONTROL)
    p.add_argument('--contexts', type=Path, default=DEFAULT_CONTEXTS); p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('qa'); p.add_argument('--input', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--workers', type=int, default=4)
    p = sub.add_parser('check'); p.add_argument('--input', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.stage == 'prepare': result = prepare(args.control, args.contexts, args.out)
    elif args.stage == 'qa': result = qa(args.input, args.out, args.workers)
    else:
        checked = check(args.input); result = dict(checked['summary'], seal_sha256=checked['seal_sha256'], audit_program_files=source_files())
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)); return int(result['state'] != 'complete')


if __name__ == '__main__': raise SystemExit(main())
