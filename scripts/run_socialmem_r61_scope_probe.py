#!/usr/bin/env python3
"""R6.1 完整 holder 双核心探测；所有抽取、准入及回放均调用 C++。"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


paired = load(ROOT / 'scripts/run_socialmem_r58_paired_probe.py', 'r61_shared_probe')
read, write, sha, text_sha, inventory = paired.read, paired.write, paired.sha, paired.text_sha, paired.inventory
PROFILE = 'target_units_statement_first_v1'
# 两个独立核心均启用目标索引；历史 helper 的 B 只表示该原生策略。
paired.PROFILE = PROFILE
HISTORY = ROOT / 'build/socialmem_20260926_r60_work/build-real'
HISTORY_SEAL = '587d9181e477c2d235d87a3575caccc7e8b5b7cbeef508e2cdb01463ef200808'
SCOPE = '7313df353a6801409499b156'
OLD_PREPARED = ROOT / 'build/socialmem_20260926_r60_work/prepare-v2'
OLD_CORE = OLD_PREPARED / 'frozen/python/starling/_core.cpython-314-darwin.so'
OLD_SHA = '600a17182d920d4a7379892eec5440dec4409516352c3fee4750f70706ceaf27'
BUDGET = 30
paired.BUDGET = BUDGET
OWN_FILES = ('scripts/run_socialmem_r61_scope_probe.py', 'tests/python/test_socialmem_r61_scope_probe.py')
COPY_FILES = ('identity.json', 'config.json', 'tasks.json', 'plans.json')


def fixed_inputs():
    paired.historical_seal(HISTORY, dict(seal_sha256=HISTORY_SEAL,
        schema='r60-expanded-seal-v1', stage='build', state='incomplete'))
    scope = read(HISTORY / 'runs' / SCOPE / 'scope.json')
    if scope['group'] != SCOPE: raise ValueError('historical scope mismatch')
    config = read(HISTORY / 'config.json')
    if any(config.get(k) != v for k, v in paired.FIXED.items()):
        raise ValueError('historical policy mismatch')
    result = {}
    database = HISTORY / 'runs' / SCOPE / 'frozen.db'
    with paired.immutable(database) as db:
        for holder in ('Lionel', 'Miriam'):
            rows = [r for r in scope['extraction'] if r.get('holder') == holder]
            sources = db.execute('SELECT d.engram_ref,e.payload_inline FROM source_documents d JOIN engrams e '
                'ON e.id=d.engram_ref AND e.tenant_id=d.tenant_id WHERE d.tenant_id=? AND d.holder_id=?',
                ('default', holder)).fetchall()
            if len(rows) != 1 or len(sources) != 1 or sources[0][0] != rows[0]['engram_ref']:
                raise ValueError('historical source/holder identity mismatch')
            payload = sources[0][1].decode()
            receipt = rows[0]['receipt']['channels']['belief']
            if (receipt['holder'] != holder or receipt['source_payload_hash'] != text_sha(payload)
                    or receipt['claim_batches_complete'] is not False
                    or receipt['failure_category'] != 'batch_scope_failure'):
                raise ValueError('historical failed receipt mismatch')
            result[holder] = dict(payload=payload, receipt=receipt, original_plan=receipt['claim_batch_plan'],
                binding=dict(payload_sha256=text_sha(payload), database_sha256=sha(database),
                             historical_seal_sha256=HISTORY_SEAL), config=config)
    return result


def fixed_tasks(inputs):
    order = (('Lionel', 'old'), ('Lionel', 'candidate'), ('Miriam', 'candidate'), ('Miriam', 'old'))
    tasks = []
    for holder, revision in order:
        bound = inputs[holder]['original_plan']['belief_request_upper_bound']
        if bound != (9 if holder == 'Lionel' else 6): raise ValueError('fixed native bound mismatch')
        tasks.append(dict(task_id=holder + '-' + revision, holder=holder, revision=revision,
                          arm='B', request_upper_bound=bound))
    return tasks


def can_continue(result):
    cost = result.get('accounting', {})
    return (result.get('status') in ('passed', 'protocol_failure', 'empty_candidate')
        and result.get('native_replay', {}).get('verified') is True
        and cost.get('healthy_http') is True and cost.get('usage_complete') is True
        and cost.get('local_attempt_count_unknown') is False and cost.get('remote_execution_unknown') is False)


def candidate_passed(results, tasks):
    if len(results) != len(tasks): return False
    if any({k: r.get(k) for k in t} != t or not can_continue(r) for r, t in zip(results, tasks)): return False
    candidates = [r for r in results if r['revision'] == 'candidate']
    return len(candidates) == 2 and all(r['status'] == 'passed' and r['statement_count'] > 0 for r in candidates)


def source_files():
    paths = set(paired.source_paths()) | {ROOT / name for name in OWN_FILES}
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}


def seal(out, stage, state):
    if (out / 'seal.json').exists(): raise ValueError('output already sealed')
    write(out / 'seal.json', dict(schema='r61-scope-probe-v1', stage=stage, state=state, files=inventory(out)))


def verify_seal(out):
    value = read(out / 'seal.json'); actual = inventory(out); actual.pop('seal.json', None)
    if value.get('schema') != 'r61-scope-probe-v1' or value.get('files') != actual:
        raise ValueError('probe seal identity mismatch')
    return value


def prepare(out, candidate_core, candidate_sha):
    out = paired.new_output(out); candidate_core = Path(candidate_core).resolve()
    if (not candidate_core.is_file() or sha(candidate_core) != candidate_sha or candidate_sha == OLD_SHA
            or not OLD_CORE.is_file() or sha(OLD_CORE) != OLD_SHA):
        raise ValueError('candidate core must be distinct and match explicit SHA')
    inputs = fixed_inputs(); tasks = fixed_tasks(inputs)
    out.mkdir(parents=True)
    try:
        write(out / 'stage.json', dict(stage='prepare'))
        config = {**paired.FIXED, 'created_at': inputs['Lionel']['config']['created_at']}
        write(out / 'config.json', config); write(out / 'inputs.json', inputs); write(out / 'tasks.json', tasks)
        sources = source_files()
        for name in sources: paired.copy_file(ROOT / name, out / 'source' / name)
        revisions = {}
        for revision, core_path in [('old', OLD_CORE), ('candidate', candidate_core)]:
            runtime = out / 'runtimes' / revision
            shutil.copytree(OLD_PREPARED / 'frozen/python', runtime / 'frozen/python')
            for core in (runtime / 'frozen/python/starling').glob('_core*.so'): core.unlink()
            paired.copy_file(core_path, runtime / 'frozen/python/starling' / core_path.name)
            revisions[revision] = dict(core_sha256=sha(core_path), frozen_files=inventory(runtime / 'frozen'))
        identity = dict(revisions=revisions, source_files=sources, input_sha256=sha(out / 'inputs.json'),
                        config_sha256=sha(out / 'config.json'), historical_seal_sha256=HISTORY_SEAL)
        write(out / 'identity.json', identity)
        plans = {revision: worker_call(out, revision, 'plan') for revision in revisions}
        write(out / 'plans.json', plans)
        if plans['old'] != plans['candidate']: raise ValueError('initial prompt/plan/schema differs between cores')
        summary = prepare_summary(identity)
        write(out / 'summary.json', summary); seal(out, 'prepare', 'complete')
        check(out)
        return summary
    except BaseException as exc:
        if not (out / 'seal.json').exists():
            write(out / 'failure.json', dict(error=f'{type(exc).__name__}: {exc}'))
            write(out / 'summary.json', dict(stage='prepare', state='incomplete', external_requests=0))
            seal(out, 'prepare', 'incomplete')
        raise


def prepare_summary(identity):
    return dict(stage='prepare', state='complete', external_requests=0, tasks=4, request_upper_bound=BUDGET,
                core_sha256={k: v['core_sha256'] for k, v in identity['revisions'].items()},
                limitation='历史开发来源的有界故障探测；无QA分数。')


def validate_inputs(prepared, require_current=False):
    identity = read(prepared / 'identity.json'); inputs = fixed_inputs()
    if (read(prepared / 'inputs.json') != inputs or identity['input_sha256'] != sha(prepared / 'inputs.json')
        or identity['historical_seal_sha256'] != HISTORY_SEAL
        or read(prepared / 'tasks.json') != fixed_tasks(inputs)
        or read(prepared / 'config.json') != {**paired.FIXED, 'created_at': inputs['Lionel']['config']['created_at']}
        or identity['config_sha256'] != sha(prepared / 'config.json')
        or inventory(prepared / 'source') != identity['source_files']):
        raise ValueError('prepared source/input/config identity mismatch')
    if require_current and source_files() != identity['source_files']: raise ValueError('current source drift')
    # 检查程序也绑定封存的 Python 依赖，避免更换审计代码后静默放行。
    for name, digest in identity['source_files'].items():
        if name.endswith('.py') and sha(ROOT / name) != digest: raise ValueError('audit program drift')
    if set(identity['revisions']) != {'old', 'candidate'} or identity['revisions']['old']['core_sha256'] != OLD_SHA:
        raise ValueError('old core identity mismatch')
    if identity['revisions']['candidate']['core_sha256'] == OLD_SHA: raise ValueError('candidate core equals old core')
    for revision, value in identity['revisions'].items():
        frozen = prepared / 'runtimes' / revision / 'frozen'
        cores = list((frozen / 'python/starling').glob('_core*.so'))
        if inventory(frozen) != value['frozen_files'] or len(cores) != 1 or sha(cores[0]) != value['core_sha256']:
            raise ValueError('frozen runtime/core identity mismatch')
    return dict(identity=identity, inputs=inputs, tasks=fixed_tasks(inputs))


def worker_call(prepared, revision, action, task=None, out=None):
    with tempfile.TemporaryDirectory(prefix='r61-worker-result-') as temp:
        result_path = Path(temp) / 'result.json'
        command = [sys.executable, str(ROOT / OWN_FILES[0]), 'worker', '--input', str(prepared),
                   '--revision', revision, '--action', action, '--result', str(result_path)]
        if task is not None: command += ['--task-id', task['task_id']]
        if out is not None: command += ['--out', str(out)]
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        if result.returncode: raise ValueError('isolated worker failed: ' + result.stderr[-1600:])
        return read(result_path)


def worker(prepared, revision, action, task_id=None, out=None):
    validated = validate_inputs(prepared, require_current=action == 'execute')
    identity = validated['identity']['revisions'][revision]
    core, runtime = paired.helpers.load_frozen(prepared / 'runtimes' / revision, identity)
    config = read(prepared / 'config.json'); inputs = validated['inputs']
    policy = paired.make_policy(core, config, 'B')
    plans = {holder: {'B': json.loads(core.claim_extraction_batch_plan(source['payload'], policy))}
             for holder, source in inputs.items()}
    prompts = {}
    for holder, source in inputs.items():
        if plans[holder]['B'] != source['original_plan']: raise ValueError('full native plan changed')
        if action == 'plan':
            # 通过已有原生入口读取首次提示；Python 不构造批次提示。
            with tempfile.TemporaryDirectory(prefix='r61-plan-') as temp:
                rt = runtime._build_local_store_sqlite_runtime(Path(temp) / 'plan.db'); rt.start()
                try:
                    fake = core.FakeLLMAdapter()
                    fake.set_default_response('{"schema_version":2,"statements":[]}')
                    extracted = core.memory_extract_llm(rt.adapter, fake, '', holder, source['payload'].encode(), policy)
                    receipt = json.loads(core.claim_extraction_receipt(extracted))
                    if receipt['claim_batches_complete'] is not True: raise ValueError('native empty plan failed')
                    prompts[holder] = [a['extraction']['prompt_input_hash'] for a in receipt['attempts']]
                finally:
                    stop = getattr(rt, 'stop', None)
                    if callable(stop): stop()
    if action == 'plan': return dict(plans=plans, prompt_hashes=prompts, schemas=paired.schema_identity(core))
    tasks = validated['tasks']; task = next(t for t in tasks if t['task_id'] == task_id)
    if task['revision'] != revision: raise ValueError('worker revision/task mismatch')
    if out.name != task['task_id']: raise ValueError('worker output/task mismatch')
    checked = dict(core=core, runtime=runtime, inputs=inputs, config=config, plans=plans, tasks=tasks)
    if action == 'execute':
        if out.exists(): raise ValueError('task output already exists')
        ledger = paired.helpers.baseline.BudgetLedger(out.parent.parent / 'request-ledger.sqlite', BUDGET)
        return paired.execute_task(checked, task, out, ledger)
    if (out / 'analysis-failure.json').exists(): return paired.partial_analysis_audit(out, checked, task)
    return paired.analyze_task(out, checked, task)


def summarize(out, prepared, tasks):
    reservations, ledger = paired.read_ledger(out); results = []; failures = []
    if len(reservations) > len(tasks) or ledger['remaining'] < 0: raise ValueError('task budget overflow')
    for i, reservation in enumerate(reservations):
        task = tasks[i]; path = out / 'tasks' / task['task_id']
        if (reservation['id'] != i + 1 or reservation['scope'] != task['task_id']
            or reservation['stage'] != 'belief_batches' or reservation['upper_bound'] != task['request_upper_bound']):
            raise ValueError('task ledger identity mismatch')
        if i and not can_continue(results[-1]): raise ValueError('task executed after required stop')
        result = worker_call(prepared, task['revision'], 'analyze', task, path)
        journal = read(path / 'started.json')['reservation']
        if journal != dict(id=reservation['id'], state='reserved', upper_bound=reservation['upper_bound']):
            raise ValueError('journal/ledger reservation mismatch')
        cost = result['accounting']
        expected = ('charged_upper', None) if cost['local_attempt_count_unknown'] or cost['observed_requests'] > task['request_upper_bound'] else ('settled', cost['observed_requests'])
        if (reservation['state'], reservation['actual']) != expected: raise ValueError('raw cost/ledger mismatch')
        if not (path / 'terminal.json').exists(): failures.append(task['task_id'] + ': missing terminal')
        elif read(path / 'terminal.json') != result: raise ValueError('recomputed task terminal mismatch')
        results.append(result)
    actual_tasks = {p.name for p in (out / 'tasks').iterdir()} if (out / 'tasks').exists() else set()
    if actual_tasks != {t['task_id'] for t in tasks[:len(reservations)]}: raise ValueError('unreserved task artifacts')
    if (out / 'failure.json').exists(): failures.append(read(out / 'failure.json')['error'])
    if results and len(results) < len(tasks) and can_continue(results[-1]) and not failures:
        raise ValueError('unexplained incomplete execution')
    passed = candidate_passed(results, tasks) and not failures and ledger['reserved'] == 0
    costs = [r['accounting'] for r in results]
    known = sum(c['known_tokens'] for c in costs)
    return dict(stage='run', state='complete' if passed else 'incomplete', candidate_passed=passed,
        tasks=results, unexecuted_tasks=[t['task_id'] for t in tasks[len(results):]], stage_failures=failures,
        observed_requests=sum(c['observed_requests'] for c in costs), known_tokens=known,
        total_tokens=known if all(c['usage_complete'] for c in costs) else None,
        ledger=ledger, core_sha256=prepare_summary(read(prepared / 'identity.json'))['core_sha256'],
        limitation='四个完整holder开发探测；不是baseline或QA提升证据；无embedding请求。')


def check(out):
    out = Path(out).resolve(); sealed = verify_seal(out); stage = read(out / 'stage.json')
    if stage['stage'] != sealed['stage']: raise ValueError('stage/seal mismatch')
    if stage['stage'] == 'prepare':
        if sealed['state'] != 'complete': raise ValueError('incomplete prepare')
        checked = validate_inputs(out)
        plans = {revision: worker_call(out, revision, 'plan') for revision in ('old', 'candidate')}
        if plans != read(out / 'plans.json'): raise ValueError('native plan/prompt/schema mismatch')
        summary = prepare_summary(checked['identity'])
    elif stage['stage'] == 'run':
        prepared = Path(stage['input']).resolve()
        if prepared == out: raise ValueError('cyclic stage')
        if check(prepared)['stage'] != 'prepare': raise ValueError('wrong input stage')
        if stage['input_seal_sha256'] != sha(prepared / 'seal.json') or sha(out / 'prepare-seal.json') != sha(prepared / 'seal.json'):
            raise ValueError('prepare seal binding mismatch')
        for name in COPY_FILES:
            if sha(out / name) != sha(prepared / name): raise ValueError('run input identity mismatch')
        if sealed['state'] == 'incomplete' and (out / 'analysis-failure.json').exists():
            # 分析中断仅提供可核对的原始文件索引，永不授予候选资格。
            summary = partial_summary(out)
        else: summary = summarize(out, prepared, read(prepared / 'tasks.json'))
    else: raise ValueError('unknown stage')
    if read(out / 'summary.json') != summary or sealed['state'] != summary['state']:
        raise ValueError('recomputed summary mismatch')
    verify_seal(out)
    return summary


def partial_summary(out):
    files = inventory(out)
    for name in ('summary.json', 'seal.json'): files.pop(name, None)
    return dict(stage='run', state='incomplete', candidate_passed=False,
        failure=read(out / 'analysis-failure.json'), raw_files=files,
        limitation='分析中断，原始证据留存；消费和终态尚未完整核验。')


def run(prepared, out):
    out = paired.new_output(out); prepared = Path(prepared).resolve()
    if check(prepared)['stage'] != 'prepare': raise ValueError('complete prepare required')
    validated = validate_inputs(prepared, require_current=True); tasks = validated['tasks']
    out.mkdir(parents=True)
    try:
        write(out / 'stage.json', dict(stage='run', input=str(prepared), input_seal_sha256=sha(prepared / 'seal.json')))
        for name in COPY_FILES: paired.copy_file(prepared / name, out / name)
        paired.copy_file(prepared / 'seal.json', out / 'prepare-seal.json')
        ledger = paired.helpers.baseline.BudgetLedger(out / 'request-ledger.sqlite', BUDGET)
        for task in tasks:
            result = worker_call(prepared, task['revision'], 'execute', task, out / 'tasks' / task['task_id'])
            print(f'{task["task_id"]}: {result["status"]}; statements={result["statement_count"]}', flush=True)
            if not can_continue(result): break
        validate_inputs(prepared, require_current=True)
    except BaseException as exc:
        write(out / 'failure.json', dict(error=f'{type(exc).__name__}: {exc}'))
    try:
        if (out / 'request-ledger.sqlite').exists():
            ledger = paired.helpers.baseline.BudgetLedger(out / 'request-ledger.sqlite', BUDGET)
            for reservation in paired.read_ledger(out)[0]:
                if reservation['state'] == 'reserved': ledger.charge_upper(reservation['id'])
        summary = summarize(out, prepared, tasks)
    except BaseException as exc:
        write(out / 'analysis-failure.json', dict(error=f'{type(exc).__name__}: {exc}'))
        summary = partial_summary(out)
    write(out / 'summary.json', summary); seal(out, 'run', summary['state'])
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__); commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare'); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--candidate-core', type=Path, required=True); p.add_argument('--candidate-sha', required=True)
    for name in ('run', 'check'):
        p = commands.add_parser(name); p.add_argument('--input', type=Path, required=True)
        if name == 'run': p.add_argument('--out', type=Path, required=True)
    p = commands.add_parser('worker'); p.add_argument('--input', type=Path, required=True)
    p.add_argument('--revision', choices=('old', 'candidate'), required=True)
    p.add_argument('--action', choices=('plan', 'execute', 'analyze'), required=True)
    p.add_argument('--result', type=Path, required=True); p.add_argument('--task-id'); p.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.command == 'worker':
        result = worker(args.input, args.revision, args.action, args.task_id, args.out)
        write(args.result, result); return 0
    if args.command == 'prepare': result = prepare(args.out, args.candidate_core, args.candidate_sha)
    elif args.command == 'run': result = run(args.input, args.out)
    else: result = check(args.input)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result['state'] != 'complete')


if __name__ == '__main__':
    raise SystemExit(main())
