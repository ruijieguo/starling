#!/usr/bin/env python3
"""R5.9 paired retrieval and fresh QA using the single qualified prepare runtime."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import queue
import shutil
import sqlite3
import sys
import tempfile
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


builder = load(ROOT / 'scripts/run_socialmem_r59_expanded.py', 'r59_evaluation_builder')
old = load(ROOT / 'scripts/run_socialmem_r56_evaluate.py', 'r59_evaluation_helpers')
previous, baseline = builder.previous, builder.baseline
qa_helpers, ablation = previous.qa_helpers, previous.ablation
read, write, sha, inventory = builder.read, builder.write, builder.sha, builder.inventory
text_sha = qa_helpers.text_sha
CORE_SHA256 = builder.CORE_SHA256
SEAL_SCHEMA = 'r59-evaluation-seal-v1'
IDENTITY_SCHEMA = 'r59-evaluation-identity-v1'
FAILURE_SCHEMA = 'r59-evaluation-failure-v1'
ARMS = ('baseline', 'source10')
POLICIES = ('legacy', 'grounded_memory_v1')
RETRIEVAL_BUDGET, QA_BUDGET = 1336, 956
OWN_FILES = ('scripts/run_socialmem_r59_evaluate.py', 'tests/python/test_socialmem_r59_evaluate.py')
PROVIDER_ENVIRONMENT_LOCK = threading.Lock()
validate_context = old.validate_context
validate_qa_binding = old.validate_qa_binding
make_tasks = old.make_tasks
read_retrieval_rows = old.read_retrieval_rows
failure_task_specs = old.failure_task_specs
query_one = ablation.query_one
run_task = qa_helpers.run_task


def require_count(value, *, positive=False):
    if type(value) is not int or value < int(positive): raise ValueError('strict integer count required')
    return value


def validate_workers(workers):
    if type(workers) is not int or not 1 <= workers <= 4: raise ValueError('workers must be integer 1..4')


def validate_cohort(records, groups):
    counts = old.validate_cohort(records, groups)
    canonical = builder.historical_inputs(builder.DEFAULT_PARENT)
    if not builder.identical(records, canonical['records']) or not builder.identical(groups, canonical['groups']):
        raise ValueError('canonical cohort content mismatch')
    return counts


def validated_build(built, require_current=False):
    built = Path(built).resolve(); checked = builder.check(built, 'build', require_current=require_current)
    validate_cohort(checked['records'], checked['groups'])
    summary = checked['summary']; gids = {g['group_id'] for g in checked['groups']}
    databases = summary.get('database_sha256', {})
    if (checked['stage'] != 'build' or summary.get('state') != 'complete' or summary.get('healthy_scopes') != 8
        or summary.get('retrieval_ready') is not True or checked['config'].get('core_sha256') != CORE_SHA256
        or checked['identity'].get('core_sha256') != CORE_SHA256
        or checked['config'].get('claim_batch_target_units') is not True
        or set(databases) != gids or set(summary.get('health', {})) != gids):
        raise ValueError('eight healthy fixed-core databases required before provider construction')
    if any(plan.get('claim_batch_prompt_profile') != builder.PROFILE for scope in checked['plans']['scopes'].values()
           for plan in scope['holders'].values()): raise ValueError('target-unit native profile mismatch')
    for gid, digest in databases.items():
        path = built / 'runs' / gid / 'frozen.db'
        if not path.is_file() or any(Path(str(path) + suffix).exists() for suffix in ('-wal', '-shm')) or sha(path) != digest:
            raise ValueError('missing/live/changed build database')
    prepared = Path(read(built / 'stage.json')['input']).resolve()
    return dict(checked, built=built, prepared=prepared, databases=databases)


def runtime_modules(checked):
    return builder.frozen_modules(checked['prepared'], checked['config'], checked['identity'])


def raw_accounting(payloads, *, missing_response=False, native=None):
    if type(missing_response) is not bool: raise ValueError('missing-response state must be boolean')
    result = dict(observed_http_attempts=0, local_attempt_count_unknown=missing_response,
        remote_execution_unknown=missing_response, remote_execution_unknown_attempts=0,
        usage_complete=not missing_response, total_tokens=None, known_tokens=0, missing_token_usage=0,
        healthy_http=not missing_response)
    for payload in payloads:
        if not isinstance(payload, dict): payload = {}
        response = payload.get('response')
        if not isinstance(response, dict): response = {}
        http, count = response.get('http_attempts'), response.get('attempt_count')
        if not isinstance(http, list): http = []; result['local_attempt_count_unknown'] = True
        if type(count) is not int or count != len(http) or not http: result['local_attempt_count_unknown'] = True
        result['observed_http_attempts'] += len(http)
        healthy = (response.get('ok') is True and response.get('error') == '' and response.get('refusal') is False
            and response.get('finish_reason') == 'stop' and count == 1 and len(http) == 1
            and isinstance(payload.get('raw_xml'), str) and isinstance(payload.get('raw_completion'), str)
            and response.get('raw_response') == payload.get('raw_xml')
            and response.get('raw_completion') == payload.get('raw_completion'))
        # raw_xml is the legacy native-cleaned representation.  When the
        # native completion differs, bind it back through the C++ helper;
        # never trust a normalized copy supplied by the receipt itself.
        if healthy and native is not None and payload.get('raw_xml') != payload.get('raw_completion'):
            cleaner = getattr(native[0], 'strip_reasoning_trace', None) if native is not None else None
            if not callable(cleaner):
                healthy = False
                result['remote_execution_unknown'] = True
            else:
                try: healthy &= cleaner(payload['raw_completion']) == payload['raw_xml']
                except (TypeError, ValueError): healthy = False
        if not http: result['missing_token_usage'] += 1; result['usage_complete'] = False
        for attempt in http:
            if not isinstance(attempt, dict): attempt = {}
            unknown = attempt.get('execution_certainty') not in ('not_connected', 'response_received')
            result['remote_execution_unknown_attempts'] += int(unknown)
            healthy &= (type(attempt.get('curl_code')) is int and attempt['curl_code'] == 0
                and type(attempt.get('http_status')) is int and 200 <= attempt['http_status'] < 300
                and attempt.get('execution_certainty') == 'response_received')
            try: body = json.loads(attempt['response_body'])
            except (KeyError, ValueError, TypeError): body = {}
            if not isinstance(body, dict): body = {}
            # Raw usage is independent of output-envelope health and duplicate metadata.
            try:
                usage = body['usage']; values = [usage[k] for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')]
                if not all(type(v) is int and v >= 0 for v in values) or values[0] + values[1] != values[2] or values[2] <= 0:
                    raise ValueError('invalid raw usage')
                result['known_tokens'] += values[2]
                if any(type(response.get(key)) is not int or response[key] != usage[key]
                       for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')):
                    raise ValueError('raw/native usage mismatch')
            except (KeyError, ValueError, TypeError):
                result['missing_token_usage'] += 1; result['usage_complete'] = False; healthy = False
            try:
                choice = body['choices'][0]; message = choice['message']
                if not isinstance(choice, dict) or not isinstance(message, dict): raise ValueError('malformed choice/message')
                healthy &= (choice.get('finish_reason') == 'stop' and not message.get('refusal')
                    and message.get('content') == payload.get('raw_completion')
                    and response.get('raw_http_response') == attempt['response_body'])
            except (KeyError, ValueError, TypeError, IndexError): healthy = False
        result['healthy_http'] &= bool(healthy)
    result['usage_complete'] &= not result['local_attempt_count_unknown']
    result['healthy_http'] &= not result['local_attempt_count_unknown']
    result['remote_execution_unknown'] |= bool(result['remote_execution_unknown_attempts'] or result['local_attempt_count_unknown'])
    if result['usage_complete']: result['total_tokens'] = result['known_tokens']
    return result


def reservation_evidence(row, scope, stage, upper, actual, unknown):
    require_count(upper)
    if type(unknown) is not bool: raise ValueError('unknown consumption state must be boolean')
    if actual is not None: require_count(actual)
    elif not unknown: raise ValueError('known consumption requires an integer count')
    reservation = row.get('reservation', {})
    require_count(reservation.get('id'), positive=True); require_count(reservation.get('upper_bound'))
    require_count(row.get('charged_requests'))
    if reservation != dict(id=reservation['id'], state='reserved', upper_bound=upper):
        raise ValueError('terminal reservation identity mismatch')
    charged_upper = unknown or actual > upper
    charged = upper if charged_upper else actual
    if row['charged_requests'] != charged: raise ValueError('terminal raw charge mismatch')
    return dict(id=reservation['id'], scope=scope, stage=stage, upper_bound=upper,
        actual=None if charged_upper else actual, state='charged_upper' if charged_upper else 'settled')


def validate_ledger_row(row):
    require_count(row.get('id'), positive=True); upper = require_count(row.get('upper_bound'))
    if not isinstance(row.get('scope'), str) or not isinstance(row.get('stage'), str): raise ValueError('ledger task identity missing')
    if row.get('state') == 'settled':
        if require_count(row.get('actual')) > upper: raise ValueError('ledger settlement exceeds reservation')
    elif row.get('state') not in ('reserved', 'charged_upper') or row.get('actual') is not None:
        raise ValueError('ledger state/actual mismatch')


def ledger_rows(path, budget):
    previous.read_ledger(path, require_count(budget))
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
        rows = [dict(zip(('id', 'scope', 'stage', 'upper_bound', 'actual', 'state'), row))
                for row in db.execute('SELECT id,scope,stage,upper_bound,actual,state FROM reservations ORDER BY id')]
    for row in rows: validate_ledger_row(row)
    return rows


def reconcile_ledger(path, budget, expected):
    for row in expected: validate_ledger_row(row)
    actual = ledger_rows(path, budget)
    if not builder.identical(sorted(actual, key=lambda r: r['id']), sorted(expected, key=lambda r: r['id'])):
        raise ValueError('per-terminal reservation/settlement mismatch')
    snapshot = previous.read_ledger(path, budget)
    if snapshot['reserved'] or snapshot['remaining'] < 0: raise ValueError('unfinished/over-budget ledger')
    return snapshot


def retrieval_accounting(row):
    invoked, count = row.get('native_invoked'), row.get('embedding_requests')
    if type(invoked) is not bool: raise ValueError('retrieval native invocation evidence missing')
    if count is not None: require_count(count)
    elif not invoked or row.get('status') != 'error': raise ValueError('native embedding count missing')
    if not invoked and (count != 0 or row.get('status') != 'error' or 'recall' in row):
        raise ValueError('retrieval response/count without native invocation')
    source = row['arm'] == 'source10'
    if source and count != 0: raise ValueError('source10 must use Stub with zero embedding')
    unknown = invoked and not source and (count is None or row['status'] == 'error')
    return dict(observed_native_requests=count, raw_http_available=False,
        raw_http_detail='frozen embedding binding exposes counters and holder health only',
        token_usage_unknown=bool(count or unknown), total_tokens=None if count or unknown else 0,
        local_attempt_count_unknown=unknown, remote_execution_unknown=unknown)


def validate_retrieval_row(checked, record, gid, arm, row):
    if row.get('group_id') != gid or row.get('holders') != baseline.history_holders(record['history']):
        raise ValueError('retrieval group/holder mismatch')
    require_count(row.get('k')); retrieval_accounting(row)
    if 'recall' in row:
        for key in ('source_count', 'statement_count', 'context_bytes'): require_count(row['recall'].get(key))
        for key in ('source_context_bytes', 'statement_context_bytes'):
            if arm == 'source10' or key in row['recall']: require_count(row['recall'].get(key))
    validation_row = dict(row, embedding_requests=0) if row.get('embedding_requests') is None else row
    ablation.validate_row(validation_row, arm, checked['databases'][gid], CORE_SHA256, checked['config']['max_context_bytes'])


def retrieval_inventory(checked, rows, *, require_healthy=False):
    indexed = {r['item_id']: r for r in checked['records']}
    by_item = {r['item_id']: g['group_id'] for g in checked['groups'] for r in g['records']}
    if set(rows) != set(ARMS): raise ValueError('retrieval arms mismatch')
    for arm, receipts in rows.items():
        ids = [r.get('item_id') for r in receipts]
        if len(ids) != len(indexed) or set(ids) != set(indexed): raise ValueError('retrieval duplicate/missing items')
        for row in receipts:
            validate_retrieval_row(checked, indexed[row['item_id']], by_item[row['item_id']], arm, row)
            if require_healthy and not ablation.healthy_embedding(row): raise ValueError('retrieval is not healthy enough for QA')
    return indexed, by_item


def verify_contexts(checked, rows, modules, errors=None):
    core, runtime = modules[:2]; records = {r['item_id']: r for r in checked['records']}
    with tempfile.TemporaryDirectory(prefix='r59-context-proof-') as temp:
        for group in checked['groups']:
            gid = group['group_id']; target = Path(temp) / (gid + '.db')
            shutil.copyfile(checked['built'] / 'runs' / gid / 'frozen.db', target)
            rt = runtime._build_local_store_sqlite_runtime(target); rt.start()
            try:
                for row in [r for arm in ARMS for r in rows[arm] if r['group_id'] == gid and r['status'] != 'error' and 'recall' in r]:
                    try:
                        validate_context(core, records[row['item_id']], row, checked['plans']['scopes'][gid],
                            checked['summary']['health'][gid]['source_engrams'],
                            lambda sid: core.get_statement_row(rt.adapter, 'default', sid))
                    except Exception as exc:
                        if errors is None: raise
                        errors.append(dict(task=row['arm'] + '/' + row['item_id'], error=f'{type(exc).__name__}: {exc}'))
            finally:
                stop = getattr(rt, 'stop', None)
                if callable(stop): stop()


def qa_accounting(task, row, modules=None):
    invoked = row.get('native_invoked')
    if type(invoked) is not bool: raise ValueError('QA native invocation evidence missing')
    payloads = [row[name] for name in ('answer', 'judge') if isinstance(row.get(name), dict)]
    if not invoked:
        if payloads: raise ValueError('QA response without native invocation')
        return raw_accounting([])
    missing = not isinstance(row.get('answer'), dict) or any(
        not isinstance(p.get('response'), dict) or not p['response'].get('http_attempts') for p in payloads)
    answer = row.get('answer') if isinstance(row.get('answer'), dict) else {}
    response = answer.get('response') if isinstance(answer.get('response'), dict) else {}
    expected_judge = (task['record'].get('answer_format', 'multiple_choice') != 'multiple_choice'
        and response.get('ok') is True and not response.get('error')
        and isinstance(answer.get('raw_xml'), str) and bool(answer['raw_xml'].strip())
        and type(response.get('attempt_count')) is int and response['attempt_count'] == 1)
    missing |= bool(expected_judge and not isinstance(row.get('judge'), dict))
    return raw_accounting(payloads, missing_response=missing, native=modules)


def qa_verdict(task, row, modules):
    accounting = qa_accounting(task, row, modules)
    if not row['native_invoked'] or not accounting['healthy_http']: return 'technical_failure', False, None, accounting
    text = row.get('answer', {}).get('raw_xml', '').strip(); record = task['record']
    if not text: return 'answer_failure', False, None, accounting
    if record.get('answer_format', 'multiple_choice') == 'multiple_choice':
        try: prediction = modules[5]._parse_option_index(text, len(record['options']))
        except (ValueError, TypeError): prediction = None
        if prediction is None: return 'invalid_answer', False, None, accounting
        return 'ok', prediction == int(record['answer']), prediction, accounting
    if not row.get('judge', {}).get('raw_xml', '').strip(): return 'judge_failure', False, None, accounting
    return 'ok', bool(modules[2]._parse_judge_verdict(row['judge']['raw_xml'].strip())), None, accounting


def validate_qa_terminal(task, row, modules):
    validate_qa_binding(task, row, modules)
    status, correct, prediction, accounting = qa_verdict(task, row, modules)
    if (row.get('status') != status or type(row.get('correct')) is not bool or row['correct'] != correct
        or not builder.identical(row.get('prediction'), prediction) or not builder.identical(row.get('accounting'), accounting)):
        raise ValueError('QA raw response status/score/usage mismatch')
    upper = 1 + int(task['record'].get('answer_format', 'multiple_choice') != 'multiple_choice')
    return reservation_evidence(row, f"{task['arm']}/{task['policy']}/{task['item_id']}", 'answer_judge', upper,
        accounting['observed_http_attempts'], accounting['local_attempt_count_unknown'])


def source_files():
    paths = {ROOT / name for name in builder.current_source_files()}
    paths.update(ROOT / name for name in (*OWN_FILES, 'scripts/run_socialmem_r56_evaluate.py'))
    return {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(paths)}


def seal_output(out, stage, state='complete'):
    if (out / 'seal.json').exists(): raise ValueError('output already sealed')
    write(out / 'seal.json', dict(schema=SEAL_SCHEMA, stage=stage, state=state, files=inventory(out)))


def verify_seal(out):
    seal = read(out / 'seal.json'); actual = inventory(out); actual.pop('seal.json', None)
    if (seal.get('schema') != SEAL_SCHEMA or seal.get('state') not in ('complete', 'incomplete')
        or not actual or seal.get('files') != actual): raise ValueError('evaluation seal identity/inventory mismatch')
    return seal


def provenance(checked):
    return dict(build=str(checked['built']), build_seal_sha256=checked['seal_sha256'],
        prepare=str(checked['prepared']), prepare_seal_sha256=sha(checked['prepared'] / 'seal.json'),
        core_sha256=CORE_SHA256, database_sha256=checked['databases'])


def freeze_stage(checked, out, stage, source, source_seal, workers, evidence=()):
    out.mkdir(parents=True)
    write(out / 'stage.json', dict(stage=stage, input=str(source), input_seal_sha256=source_seal, workers=workers))
    for name, value in [('config.json', checked['config']), ('sample.json', checked['records']),
                        ('groups.json', checked['groups']), ('provenance.json', provenance(checked))]: write(out / name, value)
    builder.copy_file(source / 'seal.json', out / 'input-seal.json')
    builder.copy_file(checked['built'] / 'seal.json', out / 'build-seal.json')
    builder.copy_file(checked['prepared'] / 'seal.json', out / 'prepare-seal.json')
    files = source_files()
    for name in files: builder.copy_file(ROOT / name, out / 'source' / name)
    evidence_sources = {str(Path(path).resolve()): sha(path) for path in evidence}
    for index, path in enumerate(evidence_sources): builder.copy_file(path, out / 'evidence' / f'{index}-{Path(path).name}')
    identity = dict(schema=IDENTITY_SCHEMA, core_sha256=CORE_SHA256,
        inputs={name: sha(out / name) for name in ('config.json', 'sample.json', 'groups.json', 'provenance.json',
                                                'build-seal.json', 'prepare-seal.json')},
        source_files=files, evidence_files=inventory(out / 'evidence'), evidence_sources=evidence_sources)
    write(out / 'identity.json', identity)
    return identity


def validate_identity(out, require_current=False):
    identity = read(out / 'identity.json'); origin = read(out / 'provenance.json')
    checked = validated_build(origin['build'], require_current=require_current)
    if origin != provenance(checked) or sha(out / 'build-seal.json') != checked['seal_sha256']:
        raise ValueError('build/prepare provenance drift')
    if sha(out / 'prepare-seal.json') != origin['prepare_seal_sha256']: raise ValueError('prepare seal copy drift')
    if identity.get('schema') != IDENTITY_SCHEMA or identity.get('core_sha256') != CORE_SHA256:
        raise ValueError('evaluation identity mismatch')
    for name, value in [('config.json', checked['config']), ('sample.json', checked['records']), ('groups.json', checked['groups'])]:
        if not builder.identical(read(out / name), value): raise ValueError('fixed evaluation input drift')
    inputs = {name: sha(out / name) for name in ('config.json', 'sample.json', 'groups.json', 'provenance.json',
                                               'build-seal.json', 'prepare-seal.json')}
    if (identity.get('inputs') != inputs or identity.get('source_files') != inventory(out / 'source')
        or inventory(out / 'evidence') != identity.get('evidence_files')):
        raise ValueError('evaluation frozen input/source/evidence drift')
    required = set(builder.current_source_files()) | set(OWN_FILES) | {'scripts/run_socialmem_r56_evaluate.py'}
    if not required.issubset(identity['source_files']): raise ValueError('archived implementation dependency missing')
    if require_current and (identity['source_files'] != source_files()
        or any(sha(path) != digest for path, digest in identity['evidence_sources'].items())):
        raise ValueError('current evaluation source/evidence drift')
    return checked


def execution_plan(stage, workers, checked, tasks=()):
    common = dict(stage=stage, workers=workers, core_sha256=CORE_SHA256,
        runtime_prepare=str(checked['prepared']), database_sha256=checked['databases'])
    if stage == 'retrieve':
        return dict(common, arms={arm: list(ablation.ARMS[arm]) for arm in ARMS}, questions=133, tasks=266,
            http_budget=RETRIEVAL_BUDGET, source10_embedding_requests=0, answer_requests=0, judge_requests=0,
            per_query_copy=True, max_context_bytes=8000, min_source_items=7, source_dialogue_radius=1)
    return dict(common, arms=list(ARMS), policies=list(POLICIES), questions=133, tasks=532, http_budget=QA_BUDGET,
        fresh=True, answer_model='qwen3.8-27b', answer_max_tokens=512, answer_enable_thinking=False,
        judge_max_tokens=64, judge_enable_thinking='provider_default_unset', max_retries=0, timeout_ms=120000,
        embedding_requests=0, bootstrap_seed=20260925, bootstrap_repetitions=100000,
        tasks_binding=[qa_task_binding(task) for task in tasks])


def qa_task_binding(task):
    return {key: task[key] for key in ('item_id', 'arm', 'policy', 'prompt_sha256', 'context_sha256')}


def retrieval_binding(checked, gid, record, arm):
    strategy, mode, k = ablation.ARMS[arm]
    return dict(item_id=record['item_id'], group_id=gid, arm=arm, strategy=strategy, mode=mode, k=k,
        holders=baseline.history_holders(record['history']), database_sha256=checked['databases'][gid], core_sha256=CORE_SHA256)


def write_started(out, scope, stage, reservation, binding, invoked):
    value = dict(scope=scope, stage=stage, reservation=reservation, task=binding, native_invoked=invoked)
    write(out / 'started' / (text_sha(scope) + '.json'), value)


def validate_started(out, scope, stage, reservation, binding, invoked):
    require_count(reservation.get('id'), positive=True); require_count(reservation.get('upper_bound'))
    actual = read(out / 'started' / (text_sha(scope) + '.json'))
    expected = dict(scope=scope, stage=stage, reservation=reservation, task=binding, native_invoked=invoked)
    if type(invoked) is not bool or not builder.identical(actual, expected): raise ValueError('started task/reservation/invocation mismatch')


def retrieval_summary(out, checked, rows):
    records, by_item = retrieval_inventory(checked, rows); reservations = []; costs = []; health = 0
    for arm in ARMS:
        for row in rows[arm]:
            record = records[row['item_id']]; scope = arm + '/' + row['item_id']; accounting = retrieval_accounting(row)
            if not builder.identical(row.get('accounting'), accounting): raise ValueError('retrieval accounting drift')
            upper = len(baseline.history_holders(record['history'])) if arm == 'baseline' else 0
            reservations.append(reservation_evidence(row, scope, 'query_embedding', upper,
                accounting['observed_native_requests'], accounting['local_attempt_count_unknown']))
            validate_started(out, scope, 'query_embedding', row['reservation'],
                retrieval_binding(checked, by_item[row['item_id']], record, arm), row['native_invoked'])
            costs.append(accounting); health += int(ablation.healthy_embedding(row))
    ledger = reconcile_ledger(out / 'request-ledger.sqlite', RETRIEVAL_BUDGET, reservations)
    requests = sum(cost['observed_native_requests'] or 0 for cost in costs)
    unknown = any(cost['local_attempt_count_unknown'] for cost in costs)
    if health == 266 and requests != 1336: raise ValueError('healthy retrieval must contain 1336 native embedding requests')
    return dict(stage='retrieve', state='complete' if health == 266 else 'incomplete', questions=133, terminal_count=266,
        healthy_terminals=health, qa_gate='passed_technical_health' if health == 266 else 'blocked_technical_health',
        gate_uses_anchor_scores=False, ledger=ledger, embedding_requests=requests, source10_embedding_requests=0,
        embedding_raw_http_available=False, embedding_token_usage_unknown=bool(requests or unknown),
        total_tokens=None if requests or unknown else 0, local_attempt_count_unknown=unknown,
        database_sha256=checked['databases'], unexecuted_stages=['qa'])


def qa_summary(out, records, rows, tasks, modules, *, repetitions=100000):
    previous.validate_terminal_inventory(records, rows)
    taskmap = {(t['item_id'], t['arm'], t['policy']): t for t in tasks}; reservations = []
    for row in rows:
        task = taskmap[(row['item_id'], row['arm'], row['policy'])]
        expected = validate_qa_terminal(task, row, modules); reservations.append(expected)
        validate_started(out, expected['scope'], 'answer_judge', row['reservation'], qa_task_binding(task), row['native_invoked'])
    ledger = reconcile_ledger(out / 'request-ledger.sqlite', QA_BUDGET, reservations)
    rows = sorted(rows, key=lambda r: (r['item_id'], r['arm'], r['policy'])); policies = {}
    for policy in POLICIES:
        selected = [row for row in rows if row['policy'] == policy]
        pairs = {arm: [row for row in selected if row['arm'] == arm] for arm in ARMS}
        comparison = previous.compare_scores(records, pairs['baseline'], pairs['source10'], repetitions=repetitions)
        comparison['breakdowns'] = previous._breakdowns(records, selected)
        comparison['arms'] = {arm: dict(questions=133, correct=sum(row['correct'] for row in pairs[arm]),
            ok=sum(row['status'] == 'ok' for row in pairs[arm]), status_counts=dict(Counter(row['status'] for row in pairs[arm]))) for arm in ARMS}
        policies[policy] = comparison
    accounting = [row['accounting'] for row in rows]; complete = all(cost['usage_complete'] for cost in accounting)
    return dict(stage='qa', state='complete', questions=133, terminal_count=532, terminal_inventory_complete=True,
        healthy_terminals=sum(row['status'] == 'ok' for row in rows), status_counts=dict(Counter(row['status'] for row in rows)),
        policies=policies, primary_endpoint='grounded_memory_v1_all_question_accuracy_gain',
        eligible_for_expanded_development=policies['grounded_memory_v1']['eligible_for_expanded_development'], automatic_promotion=False,
        ledger=ledger, observed_http_attempts=sum(cost['observed_http_attempts'] for cost in accounting),
        total_tokens=sum(cost['known_tokens'] for cost in accounting) if complete else None,
        known_tokens=sum(cost['known_tokens'] for cost in accounting), usage_complete=complete,
        missing_token_usage=sum(cost['missing_token_usage'] for cost in accounting),
        local_attempt_count_unknown=any(cost['local_attempt_count_unknown'] for cost in accounting),
        remote_execution_unknown=any(cost['remote_execution_unknown'] for cost in accounting),
        judge_flip_audit=previous.judge_flip_audit(rows),
        interpretation='133 additional historically used development questions; historical 57 excluded; no automatic promotion')


class DeferredLedger:
    """Reuse the durable reservation; helper settlement waits for local raw audit."""
    def __init__(self, ledger, scope, reservation): self.ledger, self.scope, self.reservation = ledger, scope, reservation
    def reserve(self, scope, stage, upper):
        if scope != self.scope or stage != 'answer_judge' or upper != self.reservation['upper_bound']:
            raise ValueError('helper reservation identity mismatch')
        return self.reservation
    def settle(self, *_): pass
    def charge_upper(self, *_): pass


class RequestLedger:
    """Durable reservations with explicit connection ownership on every exit path."""
    def __init__(self, path, budget):
        self.path, self.budget = Path(path), require_count(budget)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS reservations ('
                'id INTEGER PRIMARY KEY, scope TEXT, stage TEXT, upper_bound INTEGER, actual INTEGER, state TEXT NOT NULL)')

    def reserve(self, scope, stage, upper_bound):
        require_count(upper_bound)
        if not isinstance(scope, str) or not isinstance(stage, str): raise ValueError('reservation scope/stage must be strings')
        with closing(sqlite3.connect(self.path, isolation_level=None)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            used = db.execute("SELECT COALESCE(SUM(CASE WHEN state='settled' THEN actual ELSE upper_bound END),0) "
                "FROM reservations WHERE state IN ('reserved','settled','charged_upper')").fetchone()[0]
            require_count(used)
            if used + upper_bound > self.budget: return dict(state='blocked', remaining=self.budget - used)
            cursor = db.execute('INSERT INTO reservations(scope,stage,upper_bound,actual,state) VALUES(?,?,?,?,?)',
                                (scope, stage, upper_bound, None, 'reserved'))
            return dict(id=cursor.lastrowid, state='reserved', upper_bound=upper_bound)

    def settle(self, reservation_id, actual):
        require_count(reservation_id, positive=True); require_count(actual)
        with closing(sqlite3.connect(self.path, isolation_level=None)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT upper_bound,state FROM reservations WHERE id=?', (reservation_id,)).fetchone()
            if row is None: raise RuntimeError('unknown reservation')
            if row[1] != 'reserved': raise RuntimeError('reservation is not active')
            if actual > require_count(row[0]): raise RuntimeError('actual request count exceeds reservation')
            db.execute("UPDATE reservations SET actual=?,state='settled' WHERE id=?", (actual, reservation_id))

    def charge_upper(self, reservation_id):
        require_count(reservation_id, positive=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE reservations SET state='charged_upper' WHERE id=? AND state='reserved'", (reservation_id,))

    def snapshot(self):
        return previous.read_ledger(self.path, self.budget)


def make_ledger(path, budget):
    return RequestLedger(path, budget)


def charge_for(upper, actual, unknown):
    require_count(upper)
    if actual is not None: require_count(actual)
    if type(unknown) is not bool or actual is None and not unknown: raise ValueError('unknown count state mismatch')
    return upper if unknown or actual > upper else actual


def settle(ledger, reservation, actual, unknown):
    if unknown or actual > reservation['upper_bound']: ledger.charge_upper(reservation['id'])
    else: ledger.settle(reservation['id'], actual)


def make_embedder(checked, core, arm):
    if arm == 'source10': return core.StubEmbeddingAdapter(checked['config']['embedding_dim'])
    # The existing factory temporarily sets process environment while constructing a fresh native adapter.
    with PROVIDER_ENVIRONMENT_LOCK:
        return previous.previous._build_embedder(core, checked['config'], 'dashscope')


def make_adapters(checked, runner, modules):
    return runner._make_native_adapters(modules[0], checked['config'])


def execute_retrieval(task, out, checked, modules, ledger):
    gid, record, arm = task; core, runtime, _, _, pipeline, _ = modules
    scope = arm + '/' + record['item_id']; binding = retrieval_binding(checked, gid, record, arm)
    upper = len(binding['holders']) if arm == 'baseline' else 0
    reservation = ledger.reserve(scope, 'query_embedding', upper)
    if reservation.get('state') != 'reserved': raise ValueError('fixed retrieval budget unexpectedly blocked')
    write_started(out, scope, 'query_embedding', reservation, binding, False)
    row = dict(binding, terminal=True, status='error', embedding_requests=0); invoked = False; embedder = None
    try:
        embedder = make_embedder(checked, core, arm)
        if arm == 'baseline' and require_count(getattr(embedder, 'request_count', None)) != 0:
            raise ValueError('each query requires a fresh native embedder counter')
        write_started(out, scope, 'query_embedding', reservation, binding, True); invoked = True
        row = query_one((gid, record, arm, embedder), checked['built'], out,
            dict(database_sha256=checked['databases']), checked['config'], core, runtime, pipeline)
        actual = getattr(embedder, 'request_count', 0 if arm == 'source10' else None)
        if type(actual) is not int or actual != row.get('embedding_requests'):
            raise ValueError('native embedding counter/receipt mismatch')
    except Exception as exc:
        count = getattr(embedder, 'request_count', None) if invoked and arm == 'baseline' else 0
        row.update(status='error', error=f'{type(exc).__name__}: {exc}', embedding_requests=count)
    row.update(reservation=reservation, native_invoked=invoked)
    accounting = retrieval_accounting(row); row['accounting'] = accounting
    row['charged_requests'] = charge_for(upper, accounting['observed_native_requests'], accounting['local_attempt_count_unknown'])
    write(out / arm / 'recalls' / (text_sha(record['item_id']) + '.json'), row)
    settle(ledger, reservation, accounting['observed_native_requests'], accounting['local_attempt_count_unknown'])
    return row


def execute_qa(task, out, runner, modules, ledger, adapters, creation_error=None):
    scope = f"{task['arm']}/{task['policy']}/{task['item_id']}"
    upper = 1 + int(task['record'].get('answer_format', 'multiple_choice') != 'multiple_choice')
    reservation = ledger.reserve(scope, 'answer_judge', upper)
    if reservation.get('state') != 'reserved': raise ValueError('fixed QA budget unexpectedly blocked')
    write_started(out.parent, scope, 'answer_judge', reservation, qa_task_binding(task), False)
    if adapters is None:
        row = {key: task[key] for key in ('item_id', 'arm', 'policy', 'prompt', 'prompt_sha256', 'context_sha256')}
        row.update(terminal=True, fresh=True, reservation=reservation, native_invoked=False,
                   error=creation_error or 'provider construction failed')
    else:
        write_started(out.parent, scope, 'answer_judge', reservation, qa_task_binding(task), True)
        row = run_task(task, out, runner, modules, DeferredLedger(ledger, scope, reservation), adapters)
        row['native_invoked'] = True
    status, correct, prediction, accounting = qa_verdict(task, row, modules)
    for key in ('tokens', 'native_attempt_count', 'budget_unknown'): row.pop(key, None)
    row.update(status=status, correct=correct, prediction=prediction, accounting=accounting,
        charged_requests=charge_for(upper, accounting['observed_http_attempts'], accounting['local_attempt_count_unknown']))
    write(out / row['policy'] / row['arm'] / (text_sha(row['item_id']) + '.json'), row)
    settle(ledger, reservation, accounting['observed_http_attempts'], accounting['local_attempt_count_unknown'])
    return row


def run_parallel(tasks, execute, workers):
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(execute, task) for task in tasks]
        try:
            for future in as_completed(futures): rows.append(future.result())
        except BaseException:
            for future in futures: future.cancel()
            raise
    return rows


def failure_audit(out, checked, runner=None, modules=None, parent_rows=None):
    """Audit durable partial evidence without invoking providers or inventing scores."""
    failure = read(out / 'failure.json'); stage_info = failure['stage_info']; stage = stage_info['stage']
    specs = failure_task_specs(checked, stage); budget = QA_BUDGET if stage == 'qa' else RETRIEVAL_BUDGET
    paths = {spec['path'].as_posix(): scope for scope, spec in specs.items()}
    invalid = []; receipts = {}; accountings = {}; valid = []; partial = []; reservations = []; ledger = None
    def reject(task, exc): invalid.append(dict(task=task, error=f'{type(exc).__name__}: {exc}'))
    if failure['provenance'] != provenance(checked): raise ValueError('failure provenance drift')
    # Initialization may have stopped between any two copies. Existing copies still bind.
    for name, expected in [('stage.json', stage_info), ('config.json', checked['config']),
                           ('sample.json', checked['records']), ('groups.json', checked['groups']),
                           ('provenance.json', provenance(checked))]:
        if (out / name).exists():
            try:
                if not builder.identical(read(out / name), expected): raise ValueError('partial fixed input drift')
            except Exception as exc: reject(name, exc)
    if (out / 'identity.json').exists():
        try: validate_identity(out)
        except Exception as exc: reject('identity', exc)
    for path in sorted((out / 'source').rglob('*')):
        if path.is_file() and failure['source_files'].get(path.relative_to(out / 'source').as_posix()) != sha(path):
            reject('source', ValueError('partial source archive drift'))
    saved = sorted((out / 'answers').glob('*/*/*')) if stage == 'qa' else sorted(out.glob('*/recalls/*'))
    saved = [p for p in saved if p.is_file()]; starts = sorted((out / 'started').glob('*.json'))
    by_scope = {}; ledger_unknown = False; ledger_path = out / 'request-ledger.sqlite'
    if ledger_path.exists():
        try:
            reservations = ledger_rows(ledger_path, budget); ledger = previous.read_ledger(ledger_path, budget)
            if ledger['remaining'] < 0: raise ValueError('over-budget partial ledger')
            for reservation in reservations:
                scope = reservation['scope']; spec = specs.get(scope)
                if (spec is None or scope in by_scope or reservation['stage'] != spec['stage']
                    or reservation['upper_bound'] != spec['upper_bound']): raise ValueError('partial ledger task binding drift')
                by_scope[scope] = reservation
        except Exception as exc: ledger_unknown = True; reject('ledger', exc)
    elif saved or starts or (out / 'execution-plan.json').exists():
        ledger_unknown = True; reject('ledger', ValueError('started work without request ledger'))
    tasks = {}
    if stage == 'qa' and (saved or starts or (out / 'execution-plan.json').exists()):
        if modules is None: runner, modules = runtime_modules(checked)
        if parent_rows is None: parent_rows = read_retrieval_rows(Path(stage_info['input']))
        tasks = {f"{t['arm']}/{t['policy']}/{t['item_id']}": t for t in make_tasks(checked, parent_rows, runner, modules)}
    if (out / 'execution-plan.json').exists():
        try:
            plan = execution_plan(stage, stage_info['workers'], checked, list(tasks.values()))
            if not builder.identical(read(out / 'execution-plan.json'), plan): raise ValueError('partial execution plan drift')
        except Exception as exc: reject('execution-plan', exc)
    elif reservations or saved or starts: reject('execution-plan', ValueError('missing execution plan for started work'))
    journals = {}
    for path in starts:
        try:
            journal = read(path); scope = journal['scope']; spec = specs[scope]; reservation = by_scope[scope]
            if path.name != text_sha(scope) + '.json' or scope in journals: raise ValueError('unexpected/duplicate started journal')
            journals[scope] = journal
            binding = qa_task_binding(tasks[scope]) if stage == 'qa' else retrieval_binding(
                checked, spec['group_id'], spec['record'], spec['arm'])
            validate_started(out, scope, spec['stage'], dict(id=reservation['id'], state='reserved',
                upper_bound=spec['upper_bound']), binding, journal.get('native_invoked'))
        except Exception as exc: reject(path.relative_to(out).as_posix(), exc)
    context_rows = {arm: [] for arm in ARMS}
    for path in saved:
        relative = path.relative_to(out).as_posix(); scope = paths.get(relative); spec = specs.get(scope)
        try:
            row = read(path)
            if not isinstance(row, dict): raise ValueError('receipt must be an object')
        except Exception as exc: reject(scope or relative, exc); continue
        # Account every visible raw response before trusting identity, invocation or verdict copies.
        if stage == 'qa':
            payloads = [row[name] for name in ('answer', 'judge') if isinstance(row.get(name), dict)]
            if payloads:
                accountings[scope or relative] = raw_accounting(payloads, native=modules)
            try:
                if spec is not None:
                    invoked = row.get('native_invoked', journals.get(scope, {}).get('native_invoked', True))
                    accountings[scope] = qa_accounting(tasks[scope], dict(row, native_invoked=invoked), modules)
            except Exception: pass
        elif spec is not None:
            try: accountings[scope] = retrieval_accounting(dict(row,
                native_invoked=row.get('native_invoked', journals.get(scope, {}).get('native_invoked', True))))
            except Exception: pass
        if spec is None: reject(relative, ValueError('unexpected receipt path')); continue
        receipts[scope] = row
        try:
            reservation = by_scope[scope]; journal = journals[scope]
            expected_reservation = dict(id=reservation['id'], state='reserved', upper_bound=spec['upper_bound'])
            helper = 'native_invoked' not in row and 'accounting' not in row
            if not helper and not builder.identical(row.get('reservation'), expected_reservation):
                raise ValueError('partial receipt reservation binding drift')
            if not helper and row.get('native_invoked') is not journal['native_invoked']:
                raise ValueError('receipt and started invocation mismatch')
            if helper and journal['native_invoked'] is not True: raise ValueError('helper receipt without native start')
            normalized = dict(row, native_invoked=journal['native_invoked']) if helper else row
            if stage == 'qa':
                if helper:
                    validate_qa_binding(tasks[scope], row, modules)
                    if not builder.identical(row.get('reservation'), expected_reservation):
                        raise ValueError('helper reservation binding drift')
                    cost = qa_accounting(tasks[scope], normalized, modules)
                    expected = dict(reservation, actual=cost['observed_http_attempts'], state='settled')
                else:
                    expected = validate_qa_terminal(tasks[scope], row, modules); cost = qa_accounting(tasks[scope], row, modules)
            else:
                validate_retrieval_row(checked, spec['record'], spec['group_id'], spec['arm'], normalized)
                cost = retrieval_accounting(normalized); actual = cost['observed_native_requests']
                unknown = cost['local_attempt_count_unknown']
                if helper:
                    expected = dict(reservation, actual=None if unknown else actual,
                                    state='charged_upper' if unknown else 'settled')
                else:
                    if not builder.identical(row.get('accounting'), cost): raise ValueError('retrieval accounting drift')
                    expected = reservation_evidence(row, scope, spec['stage'], spec['upper_bound'], actual, unknown)
                context_rows[spec['arm']].append(normalized)
            if reservation['state'] != 'reserved' and not builder.identical(reservation, expected):
                raise ValueError('raw response/ledger settlement mismatch')
            accountings[scope] = cost
            (partial if helper or reservation['state'] == 'reserved' else valid).append(scope)
        except Exception as exc: reject(scope, exc)
    if stage == 'retrieve' and any(context_rows.values()):
        if modules is None: runner, modules = runtime_modules(checked)
        verify_contexts(checked, context_rows, modules, invalid)
    bad = {entry['task'] for entry in invalid}; valid = sorted(set(valid) - bad); partial = sorted(set(partial) - bad)
    unknown = set()
    for scope, spec in specs.items():
        if not spec['upper_bound']: continue
        journal = journals.get(scope); cost = accountings.get(scope)
        if journal and journal.get('native_invoked') is False and scope not in receipts and scope not in bad: continue
        if scope in by_scope or scope in journals or scope in receipts:
            if cost is None or cost['local_attempt_count_unknown'] or scope in bad: unknown.add(scope)
    costs = list(accountings.values()); known = sum(cost.get('known_tokens', 0) for cost in costs)
    complete = not ledger_unknown and not unknown and not invalid and all(
        cost.get('usage_complete', not cost.get('token_usage_unknown', False)) for cost in costs)
    return dict(stage=stage, state='incomplete', artifact_state='incomplete', evidence_valid=not invalid,
        failure_sha256=sha(out / 'failure.json'), expected_task_count=len(specs), validated_terminal_count=len(valid),
        validated_terminal_tasks=valid, partial_receipt_tasks=partial,
        missing_receipt_tasks=sorted(set(specs) - set(receipts)),
        unstarted_tasks=[] if ledger_unknown else sorted(set(specs) - set(by_scope) - set(receipts) - set(journals)),
        ledger_identity_unknown=ledger_unknown, invalid_evidence=invalid,
        unverified_settlement_tasks=sorted(set(by_scope) - set(valid) - set(partial)),
        unresolved_reservations=[r for r in reservations if r['state'] == 'reserved'],
        unknown_request_tasks=sorted(unknown), ledger=ledger, ledger_reservations=reservations,
        observed_http_attempts=sum(cost.get('observed_http_attempts', 0) for cost in costs),
        observed_native_requests=sum(cost.get('observed_native_requests') or 0 for cost in costs),
        raw_http_available=stage == 'qa', known_tokens=known, total_tokens=known if complete else None,
        usage_complete=complete, missing_token_usage=sum(cost.get('missing_token_usage', 0) for cost in costs),
        local_attempt_count_unknown=ledger_unknown or bool(unknown),
        remote_execution_unknown=ledger_unknown or bool(unknown) or any(cost.get('remote_execution_unknown', False) for cost in costs),
        automatic_promotion=False, retry='refuse overwrite; no automatic replay')


def fail_stage(out, checked, stage_info, sources, exc, runner=None, modules=None, parent_rows=None):
    out.mkdir(parents=True, exist_ok=True)
    # The emergency path uses the underlying atomic writer, independently of normal-stage writes.
    builder.write(out / 'failure.json', dict(schema=FAILURE_SCHEMA, stage_info=stage_info,
        provenance=provenance(checked), source_files=sources,
        exception=f'{type(exc).__name__}: {exc}', traceback=traceback.format_exc()))
    summary = failure_audit(out, checked, runner, modules, parent_rows)
    builder.write(out / 'failure-summary.json', summary)
    builder.write(out / 'seal.json', dict(schema=SEAL_SCHEMA, stage=stage_info['stage'],
        state='incomplete', files={k: v for k, v in inventory(out).items() if k != 'seal.json'}))
    return summary


def retrieve(built, out, workers=4, evidence=()):
    out = builder.new_output(out); validate_workers(workers); checked = validated_build(built, require_current=True)
    stage_info = dict(stage='retrieve', input=str(checked['built']), input_seal_sha256=checked['seal_sha256'], workers=workers)
    sources = source_files(); runner = modules = None
    try:
        freeze_stage(checked, out, 'retrieve', checked['built'], checked['seal_sha256'], workers, evidence)
        runner, modules = runtime_modules(checked); validate_identity(out, require_current=True)
        ledger = make_ledger(out / 'request-ledger.sqlite', RETRIEVAL_BUDGET)
        write(out / 'execution-plan.json', execution_plan('retrieve', workers, checked))
        tasks = [(group['group_id'], record, arm) for group in checked['groups'] for record in group['records'] for arm in ARMS]
        completed = run_parallel(tasks, lambda task: execute_retrieval(task, out, checked, modules, ledger), workers)
        rows = {arm: [row for row in completed if row['arm'] == arm] for arm in ARMS}
        retrieval_inventory(checked, rows); verify_contexts(checked, rows, modules)
        summary = retrieval_summary(out, checked, rows)
        if summary['state'] == 'complete': write(out / 'comparison.json', previous.retrieval_comparison(checked['records'], rows))
        validate_identity(out, require_current=True); builder.old.validate_loaded(checked['prepared'], checked['identity'])
        write(out / 'summary.json', summary); seal_output(out, 'retrieve', summary['state'])
        return summary
    except BaseException as exc:
        return fail_stage(out, checked, stage_info, sources, exc, runner, modules)


def qa(contexts, out, workers=4, evidence=()):
    out = builder.new_output(out); validate_workers(workers); contexts = Path(contexts).resolve()
    parent = check(contexts, 'retrieve'); checked = parent['build']
    validated_build(checked['built'], require_current=True)
    stage_info = dict(stage='qa', input=str(contexts), input_seal_sha256=parent['seal_sha256'], workers=workers)
    sources = source_files(); runner = modules = None
    try:
        freeze_stage(checked, out, 'qa', contexts, parent['seal_sha256'], workers, evidence)
        for arm in ARMS: shutil.copytree(contexts / arm / 'recalls', out / 'input-recalls' / arm)
        runner, modules = runtime_modules(checked); tasks = make_tasks(checked, parent['rows'], runner, modules)
        write(out / 'execution-plan.json', execution_plan('qa', workers, checked, tasks))
        validate_identity(out, require_current=True)
        ledger = make_ledger(out / 'request-ledger.sqlite', QA_BUDGET); adapters = queue.Queue()
        for _ in range(workers):
            try: adapters.put((make_adapters(checked, runner, modules), None))
            except Exception as exc: adapters.put((None, f'{type(exc).__name__}: {exc}'))
        def execute(task):
            pair, error = adapters.get()
            try: return execute_qa(task, out / 'answers', runner, modules, ledger, pair, error)
            finally: adapters.put((pair, error))
        rows = run_parallel(tasks, execute, workers)
        summary = qa_summary(out, checked['records'], rows, tasks, modules)
        validate_identity(out, require_current=True); builder.old.validate_loaded(checked['prepared'], checked['identity'])
        verify_seal(contexts)
        if sha(contexts / 'seal.json') != parent['seal_sha256']: raise ValueError('retrieval input changed during QA')
        write(out / 'summary.json', summary); seal_output(out, 'qa')
        return summary
    except BaseException as exc:
        return fail_stage(out, checked, stage_info, sources, exc, runner, modules, parent['rows'])


def check_failure(out, seal, expected_stage=None):
    failure = read(out / 'failure.json'); stage = failure['stage_info']
    if (failure.get('schema') != FAILURE_SCHEMA or seal['state'] != 'incomplete'
        or stage.get('stage') not in ('retrieve', 'qa') or seal['stage'] != stage['stage']):
        raise ValueError('invalid partial evaluation identity')
    if expected_stage: raise ValueError('incomplete evaluation cannot be an input')
    validate_workers(stage.get('workers'))
    checked = validated_build(failure['provenance']['build']); source = Path(stage['input']).resolve()
    if source == out: raise ValueError('cyclic evaluation input')
    parent_rows = None
    if stage['stage'] == 'qa':
        parent = check(source, 'retrieve'); parent_rows = parent['rows']; digest = parent['seal_sha256']
        if parent['build']['seal_sha256'] != checked['seal_sha256']: raise ValueError('partial QA build drift')
        for arm in ARMS:
            for path in sorted((out / 'input-recalls' / arm).glob('*')):
                if path.is_file() and sha(path) != sha(source / arm / 'recalls' / path.name):
                    raise ValueError('partial QA recall copy drift')
    else:
        if source != checked['built']: raise ValueError('partial retrieval requires bound build')
        digest = checked['seal_sha256']
    if stage['input_seal_sha256'] != digest: raise ValueError('partial stage input drift')
    for name, expected in [('input-seal.json', digest), ('build-seal.json', checked['seal_sha256']),
                           ('prepare-seal.json', failure['provenance']['prepare_seal_sha256'])]:
        if (out / name).exists() and sha(out / name) != expected: raise ValueError('partial seal copy drift')
    summary = failure_audit(out, checked, parent_rows=parent_rows)
    if not builder.identical(read(out / 'failure-summary.json'), summary): raise ValueError('partial audit summary drift')
    verify_seal(out)
    return dict(stage=stage['stage'], build=checked, summary=summary,
        seal_sha256=sha(out / 'seal.json'), audit_program_files=source_files())


def check(out, expected_stage=None):
    out = Path(out).resolve(); seal = verify_seal(out)
    if (out / 'failure.json').exists(): return check_failure(out, seal, expected_stage)
    stage = read(out / 'stage.json')
    if stage.get('stage') != seal['stage'] or stage['stage'] not in ('retrieve', 'qa'): raise ValueError('evaluation stage mismatch')
    validate_workers(stage.get('workers'))
    if expected_stage and (stage['stage'] != expected_stage or seal['state'] != 'complete'):
        raise ValueError('incomplete or incorrect evaluation input')
    checked = validate_identity(out); source = Path(stage['input']).resolve()
    if source == out: raise ValueError('cyclic evaluation input')
    runner, modules = runtime_modules(checked)
    if stage['stage'] == 'retrieve':
        if source != checked['built']: raise ValueError('retrieval requires bound build input')
        digest = checked['seal_sha256']; rows = read_retrieval_rows(out)
        retrieval_inventory(checked, rows); verify_contexts(checked, rows, modules)
        summary = retrieval_summary(out, checked, rows); plan = execution_plan('retrieve', stage['workers'], checked)
        if summary['state'] == 'complete' and read(out / 'comparison.json') != previous.retrieval_comparison(checked['records'], rows):
            raise ValueError('anchor diagnostic drift')
    else:
        parent = check(source, 'retrieve'); digest = parent['seal_sha256']
        if parent['build']['seal_sha256'] != checked['seal_sha256']: raise ValueError('QA build input mismatch')
        for arm in ARMS:
            if inventory(out / 'input-recalls' / arm) != inventory(source / arm / 'recalls'): raise ValueError('QA recall copy drift')
        tasks = make_tasks(checked, parent['rows'], runner, modules)
        rows = [read(path) for path in sorted((out / 'answers').glob('*/*/*.json'))]
        summary = qa_summary(out, checked['records'], rows, tasks, modules)
        plan = execution_plan('qa', stage['workers'], checked, tasks)
    if stage.get('input_seal_sha256') != digest or sha(out / 'input-seal.json') != digest: raise ValueError('stage input seal mismatch')
    if (read(out / 'execution-plan.json') != plan or not builder.identical(read(out / 'summary.json'), summary)
        or seal['state'] != summary['state']): raise ValueError('recomputed evaluation plan/summary mismatch')
    builder.old.validate_loaded(checked['prepared'], checked['identity']); verify_seal(out)
    return dict(stage=stage['stage'], build=checked, rows=rows, summary=summary,
        seal_sha256=sha(out / 'seal.json'), audit_program_files=source_files())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); stages = parser.add_subparsers(dest='stage', required=True)
    for name in ('retrieve', 'qa'):
        command = stages.add_parser(name); command.add_argument('--input', type=Path, required=True)
        command.add_argument('--out', type=Path, required=True); command.add_argument('--workers', type=int, default=4)
        command.add_argument('--evidence', type=Path, action='append', default=[])
    command = stages.add_parser('check'); command.add_argument('--input', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.stage == 'check':
        audited = check(args.input); result = dict(audited['summary'], audit_program_files=audited['audit_program_files'])
    else: result = globals()[args.stage](args.input, args.out, args.workers, args.evidence)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False)); return int(result['state'] != 'complete')


if __name__ == '__main__': raise SystemExit(main())
