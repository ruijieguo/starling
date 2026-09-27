"""R5.9 evaluation contracts; synthetic and localhost fixtures only."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import os
import shutil
import sqlite3
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/run_socialmem_r59_evaluate.py'


def driver():
    assert SCRIPT.is_file(), 'R5.9 independent retrieve/QA entry is required'
    spec = importlib.util.spec_from_file_location('r59_evaluation_test', SCRIPT)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def response(text='yes'):
    usage = dict(prompt_tokens=10, completion_tokens=2, total_tokens=12)
    raw = json.dumps(dict(choices=[dict(finish_reason='stop', message=dict(content=text, refusal=None))], usage=usage))
    return dict(raw_xml=text, raw_completion=text, response=dict(ok=True, error='', refusal=False,
        finish_reason='stop', attempt_count=1, raw_response=text, raw_completion=text, raw_http_response=raw,
        **usage, http_attempts=[dict(attempt=1, curl_code=0, http_status=200,
            execution_certainty='response_received', response_body=raw)]))


@pytest.mark.parametrize('stage', ['retrieve', 'qa'])
def test_existing_output_refused_before_input_inspection(tmp_path, stage):
    m = driver(); out = tmp_path / 'exists'; out.mkdir()
    with pytest.raises(ValueError, match='already exists'): getattr(m, stage)(tmp_path / 'missing', out)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_canonical_cohort_arms_and_fixed_task_budgets():
    m = driver(); inputs = m.builder.historical_inputs(m.builder.DEFAULT_PARENT)
    assert m.validate_cohort(inputs['records'], inputs['groups']) == dict(
        questions=133, scopes=8, holders=65, retrieval_budget=1336, qa_budget=956)
    assert {arm: m.ablation.ARMS[arm] for arm in m.ARMS} == {
        'baseline': ('evidence_profile_v6', 'hybrid', 10), 'source10': ('evidence_profile_v9', 'sources', 10)}
    for records in (inputs['records'][:-1], inputs['records'] + [inputs['records'][0]]):
        with pytest.raises(ValueError): m.validate_cohort(records, inputs['groups'])


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('problem', ['old_core', 'seven', 'true_string', 'profile', 'missing_database',
                                     'database_hash', 'sidecar', 'duplicate_question'])
def test_invalid_build_identity_is_rejected_before_provider(tmp_path, monkeypatch, problem):
    m = driver(); checked = m.builder.historical_inputs(m.builder.DEFAULT_PARENT)
    built = tmp_path / 'build'; databases = {}
    for group in checked['groups']:
        path = built / 'runs' / group['group_id'] / 'frozen.db'; path.parent.mkdir(parents=True)
        with sqlite3.connect(path) as db: db.execute('CREATE TABLE fixture_only(value INTEGER)')
        databases[group['group_id']] = m.sha(path)
    gids = list(databases)
    checked.update(stage='build', identity=dict(core_sha256=m.CORE_SHA256), seal_sha256='fixture',
        plans=dict(scopes={gid: dict(holders={'A': dict(claim_batch_prompt_profile='target_units_v1')}) for gid in gids}),
        summary=dict(state='complete', healthy_scopes=8, retrieval_ready=True, qa_ready=False,
            database_sha256=databases, health={gid: {} for gid in gids}))
    m.write(built / 'stage.json', dict(stage='build', input=str(tmp_path / 'prepare')))
    if problem == 'old_core': checked['config']['core_sha256'] = 'old'
    elif problem == 'seven': checked['summary']['healthy_scopes'] = 7
    elif problem == 'true_string': checked['config']['claim_batch_target_units'] = 'true'
    elif problem == 'profile': checked['plans']['scopes'][gids[0]]['holders']['A']['claim_batch_prompt_profile'] = 'legacy'
    elif problem == 'missing_database': (built / 'runs' / gids[0] / 'frozen.db').unlink()
    elif problem == 'database_hash': databases[gids[0]] = 'changed'
    elif problem == 'sidecar': (built / 'runs' / gids[0] / 'frozen.db-wal').write_bytes(b'live')
    else: checked['records'][-1] = checked['records'][0]
    monkeypatch.setattr(m.builder, 'check', lambda *args, **kwargs: checked)
    monkeypatch.setattr(m, 'runtime_modules', lambda *_: pytest.fail('provider boundary reached'))
    with pytest.raises(ValueError): m.retrieve(built, tmp_path / 'forbidden')
    assert not (tmp_path / 'forbidden').exists()


@pytest.mark.parametrize('fault', ['empty_choices', 'null_choice', 'null_message', 'refusal', 'length', 'usage_copy'])
def test_raw_usage_survives_malformed_or_unhealthy_envelope(fault):
    m = driver(); value = response(); native = value['response']; body = json.loads(native['raw_http_response'])
    if fault == 'empty_choices': body['choices'] = []
    elif fault == 'null_choice': body['choices'] = [None]
    elif fault == 'null_message': body['choices'][0]['message'] = None
    elif fault == 'refusal': body['choices'][0]['message']['refusal'] = 'refused'
    elif fault == 'length': body['choices'][0]['finish_reason'] = 'length'
    else: native['total_tokens'] = 999
    native['raw_http_response'] = native['http_attempts'][0]['response_body'] = json.dumps(body)
    cost = m.raw_accounting([value])
    assert cost['known_tokens'] == 12 and cost['observed_http_attempts'] == 1
    assert not cost['healthy_http']
    assert not cost['local_attempt_count_unknown']


@pytest.mark.parametrize('fault', ['missing_usage', 'malformed_json', 'certainty', 'missing_response', 'bool_count'])
def test_raw_unknown_cost_is_not_filled_with_zero(fault):
    m = driver(); value = response(); native = value['response']
    if fault == 'missing_response': cost = m.raw_accounting([], missing_response=True)
    else:
        if fault == 'missing_usage':
            body = json.loads(native['raw_http_response']); body.pop('usage')
            native['raw_http_response'] = native['http_attempts'][0]['response_body'] = json.dumps(body)
        elif fault == 'malformed_json': native['raw_http_response'] = native['http_attempts'][0]['response_body'] = '{'
        elif fault == 'certainty': native['http_attempts'][0]['execution_certainty'] = 'unregistered'
        else: native['attempt_count'] = True
        cost = m.raw_accounting([value])
    assert not cost['healthy_http']
    if fault != 'certainty': assert cost['total_tokens'] is None
    if fault in ('certainty', 'missing_response', 'bool_count'): assert cost['remote_execution_unknown']


@pytest.mark.parametrize('field', ['id', 'upper_bound', 'charged_requests', 'actual'])
@pytest.mark.parametrize('bad', [True, 1.0, '1'])
def test_reservation_counts_require_strict_integer_types(field, bad):
    m = driver(); row = dict(reservation=dict(id=1, state='reserved', upper_bound=1), charged_requests=1); actual = 1
    if field == 'actual': actual = bad
    elif field == 'charged_requests': row[field] = bad
    else: row['reservation'][field] = bad
    with pytest.raises(ValueError): m.reservation_evidence(row, 'scope', 'answer_judge', 1, actual, False)


def test_legacy_reasoning_raw_representations_remain_distinct():
    m = driver(); value = response('<think>reasoning</think>yes')
    value['raw_xml'] = value['response']['raw_response'] = 'yes'
    assert m.raw_accounting([value])['healthy_http']


def test_native_reasoning_binding_controls_cleaned_raw_xml():
    m = driver(); value = response('<think>reasoning</think>yes')
    value['raw_xml'] = value['response']['raw_response'] = 'yes'
    class Native:
        @staticmethod
        def strip_reasoning_trace(text): return text.replace('<think>reasoning</think>', '')
    cost = m.raw_accounting([value], native=(Native(),))
    assert cost['healthy_http']
    value['raw_xml'] = value['response']['raw_response'] = 'forged'
    assert not m.raw_accounting([value], native=(Native(),))['healthy_http']


@pytest.mark.parametrize('workers', [True, 1.0, '1', 0, 5])
def test_worker_count_is_strict_and_bounded(workers):
    with pytest.raises(ValueError): driver().validate_workers(workers)


FIXTURE_BUILD = ROOT / 'build/socialmem_20260926_r59_work/evaluator-native-fixture/build'


@pytest.fixture(scope='module')
def native():
    m = driver(); checked = m.validated_build(FIXTURE_BUILD)
    runner, modules = m.runtime_modules(checked)
    return m, checked, runner, modules


def empty_recall():
    return dict(block='', labels=[], source_refs=[], statement_ids=[], source_count=0, statement_count=0,
        context_bytes=0, source_context_bytes=0, statement_context_bytes=0, receipts=[], source_diagnostics={})


def synthetic_rows(m, checked):
    rows = {arm: [] for arm in m.ARMS}
    for group in checked['groups']:
        for record in group['records']:
            for arm in m.ARMS:
                holders = m.baseline.history_holders(record['history']); strategy, mode, k = m.ablation.ARMS[arm]
                recall = empty_recall()
                if arm == 'baseline': recall['receipts'] = [dict(holder=h, degraded_paths=[]) for h in holders]
                rows[arm].append(dict(item_id=record['item_id'], group_id=group['group_id'], arm=arm,
                    strategy=strategy, mode=mode, k=k, holders=holders, core_sha256=m.CORE_SHA256,
                    database_sha256=checked['databases'][group['group_id']], terminal=True, status='ok',
                    recall=recall, native_invoked=True, embedding_requests=len(holders) if arm == 'baseline' else 0))
    return rows


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_native_build_single_runtime_and_fixed_qa_task_inventory(native):
    m, checked, runner, modules = native
    assert checked['summary']['healthy_scopes'] == 8
    assert Path(modules[0].__file__).resolve().is_relative_to(checked['prepared'] / 'frozen')
    rows = synthetic_rows(m, checked); m.retrieval_inventory(checked, rows, require_healthy=True)
    tasks = m.make_tasks(checked, rows, runner, modules)
    assert len(tasks) == 532 and len({(t['item_id'], t['arm'], t['policy']) for t in tasks}) == 532
    assert sum(1 + int(t['record'].get('answer_format') != 'multiple_choice') for t in tasks) == 956


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('fault', ['265', 'duplicate', 'degraded', 'bool_count', 'strategy', 'core', 'database'])
def test_qa_gate_rejects_incomplete_or_forged_retrieval_inventory(native, fault):
    m, checked, _, _ = native; rows = synthetic_rows(m, checked); row = rows['baseline'][0]
    if fault == '265': rows['baseline'].pop()
    elif fault == 'duplicate': rows['baseline'][-1] = deepcopy(row)
    elif fault == 'degraded': row['recall']['receipts'][0]['degraded_paths'] = [dict(stage='embedding', reason='failed')]
    elif fault == 'bool_count': row['embedding_requests'] = True
    elif fault == 'strategy': row['strategy'] = 'evidence_profile_v9'
    elif fault == 'core': row['core_sha256'] = 'old'
    else: row['database_sha256'] = 'forged'
    with pytest.raises(ValueError): m.retrieval_inventory(checked, rows, require_healthy=True)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_low_anchor_diagnostics_do_not_block_healthy_retrieval(native):
    m, checked, _, _ = native; rows = synthetic_rows(m, checked)
    m.retrieval_inventory(checked, rows, require_healthy=True)
    assert m.previous.retrieval_comparison(checked['records'], rows)['gate_uses_anchor_scores'] is False


@pytest.mark.parametrize('field', ['id', 'upper_bound', 'actual'])
def test_sqlite_reservation_rows_bind_strict_integer_values(tmp_path, field):
    m = driver(); path = tmp_path / 'ledger.sqlite'; ledger = m.baseline.BudgetLedger(path, 10)
    reservation = ledger.reserve('a', 'answer_judge', 2); ledger.settle(reservation['id'], 1)
    expected = m.ledger_rows(path, 10)
    forged = deepcopy(expected); forged[0][field] = True
    with pytest.raises(ValueError): m.reconcile_ledger(path, 10, forged)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('fault', ['choices', 'message', 'usage_copy'])
def test_qa_verdict_chain_uses_local_raw_accounting(native, monkeypatch, fault):
    m, checked, runner, modules = native
    task = m.make_tasks(checked, synthetic_rows(m, checked), runner, modules)[0]
    value = response('0'); body = json.loads(value['response']['raw_http_response'])
    if fault == 'choices': body['choices'] = []
    elif fault == 'message': body['choices'][0]['message'] = None
    else: value['response']['total_tokens'] = 999
    value['response']['raw_http_response'] = value['response']['http_attempts'][0]['response_body'] = json.dumps(body)
    monkeypatch.setattr(m.old, 'raw_accounting', lambda *_args, **_kwargs: pytest.fail('old accounting closure used'))
    monkeypatch.setattr(m.old, 'qa_accounting', lambda *_args, **_kwargs: pytest.fail('old accounting wrapper used'))
    row = dict(native_invoked=True, answer=value, reservation=dict(id=1, state='reserved', upper_bound=2))
    status, correct, _, accounting = m.qa_verdict(task, row, modules)
    assert status == 'technical_failure' and correct is False and accounting['known_tokens'] == 12


class SyntheticResponse:
    def __init__(self, text):
        self.payload = response(text); self.raw_xml = text; self.raw_completion = text; self.ok = True; self.error = ''
    def to_json(self): return json.dumps(self.payload['response'])


class SyntheticAdapter:
    def __init__(self, text): self.text = text
    def extract(self, *_): return SyntheticResponse(self.text)


@pytest.fixture(scope='module')
def synthetic_contexts(native, tmp_path_factory):
    m, checked, _, _ = native; out = tmp_path_factory.mktemp('r59-evaluation') / 'retrieve'
    original_build, original_embedder, original_query = m.validated_build, m.make_embedder, m.query_one
    rows = synthetic_rows(m, checked); indexed = {(row['group_id'], row['item_id'], row['arm']): row for arm in m.ARMS for row in rows[arm]}
    class Embedder:
        request_count = 0
    def query(task, built, directory, *args):
        gid, record, arm, embedder = task; scope = arm + '/' + record['item_id']
        started = m.read(directory / 'started' / (m.text_sha(scope) + '.json'))
        assert started['native_invoked'] is True and started['reservation']['state'] == 'reserved'
        row = deepcopy(indexed[(gid, record['item_id'], arm)]); embedder.request_count = row['embedding_requests']
        row.pop('native_invoked'); m.write(directory / arm / 'recalls' / (m.text_sha(record['item_id']) + '.json'), row)
        return row
    m.validated_build = lambda *args, **kwargs: checked
    m.make_embedder = lambda *args: Embedder()
    m.query_one = query
    try: summary = m.retrieve(checked['built'], out, workers=4)
    finally: m.validated_build, m.make_embedder, m.query_one = original_build, original_embedder, original_query
    assert summary['healthy_terminals'] == 266 and summary['embedding_requests'] == 1336
    return out


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_retrieval_full_stage_is_immutable_and_low_anchor_gate_passes(native, synthetic_contexts, monkeypatch):
    m, checked, _, _ = native
    monkeypatch.setattr(m, 'validated_build', lambda *args, **kwargs: checked)
    before = m.inventory(synthetic_contexts); result = m.check(synthetic_contexts, 'retrieve')
    assert result['summary']['gate_uses_anchor_scores'] is False and result['summary']['source10_embedding_requests'] == 0
    assert before == m.inventory(synthetic_contexts) and result['audit_program_files']


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('fault', ['missing_terminal', 'context', 'ledger', 'started', 'summary'])
def test_qa_provider_gate_rechecks_resealed_retrieval_evidence(native, synthetic_contexts, tmp_path, monkeypatch, fault):
    m, checked, _, _ = native
    monkeypatch.setattr(m, 'validated_build', lambda *args, **kwargs: checked)
    monkeypatch.setattr(m, 'make_adapters', lambda *_: pytest.fail('QA provider was constructed before the gate'))
    out = synthetic_contexts; path = next((out / 'baseline/recalls').glob('*.json'))
    originals = {p: p.read_bytes() for p in (path, out / 'seal.json', out / 'summary.json', out / 'request-ledger.sqlite')}
    journal = out / 'started' / (m.text_sha('baseline/' + m.read(path)['item_id']) + '.json')
    originals[journal] = journal.read_bytes()
    try:
        if fault == 'missing_terminal': path.unlink()
        elif fault == 'context':
            row = m.read(path); row['recall']['block'] = '[SOURCE] forged'; row['recall']['context_bytes'] = len(row['recall']['block'])
            m.write(path, row)
        elif fault == 'ledger':
            with sqlite3.connect(out / 'request-ledger.sqlite') as db:
                db.execute('UPDATE reservations SET actual=0 WHERE id=(SELECT id FROM reservations WHERE actual>0 ORDER BY id LIMIT 1)')
            db.close()
        elif fault == 'started':
            row = m.read(journal); row['reservation']['id'] = True; m.write(journal, row)
        else:
            value = m.read(out / 'summary.json'); value['embedding_requests'] = 0; m.write(out / 'summary.json', value)
        (out / 'seal.json').unlink(); m.seal_output(out, 'retrieve')
        with pytest.raises((ValueError, RuntimeError)): m.qa(out, tmp_path / 'forbidden')
        assert not (tmp_path / 'forbidden').exists()
    finally:
        for path, data in originals.items(): path.write_bytes(data)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_full_fresh_qa_rechecks_native_prompts_statistics_and_raw_cost(native, synthetic_contexts, tmp_path, monkeypatch):
    m, checked, _, _ = native
    monkeypatch.setattr(m, 'validated_build', lambda *args, **kwargs: checked)
    monkeypatch.setattr(m, 'make_adapters', lambda *_: (None, None, SyntheticAdapter('0'), SyntheticAdapter('yes')))
    out = tmp_path / 'qa'; summary = m.qa(synthetic_contexts, out, workers=4)
    assert summary['state'] == 'complete' and summary['terminal_count'] == 532
    assert summary['ledger']['committed'] == 956 and summary['known_tokens'] == summary['total_tokens'] == 11472
    before = m.inventory(out); verified = m.check(out); assert verified['summary'] == summary and before == m.inventory(out)
    rows = verified['rows']
    for policy in m.POLICIES:
        left = [r for r in rows if r['policy'] == policy and r['arm'] == 'baseline']
        right = [r for r in rows if r['policy'] == policy and r['arm'] == 'source10']
        expected = m.previous.compare_scores(checked['records'], left, right, repetitions=100000)
        for key, value in expected.items(): assert summary['policies'][policy][key] == value
    path = next((out / 'answers/grounded_memory_v1/source10').glob('*.json'))
    row = m.read(path); row['prompt'] += ' forged'; row['prompt_sha256'] = m.text_sha(row['prompt']); m.write(path, row)
    plan = m.read(out / 'execution-plan.json')
    for task in plan['tasks_binding']:
        if (task['item_id'], task['arm'], task['policy']) == (row['item_id'], row['arm'], row['policy']): task['prompt_sha256'] = row['prompt_sha256']
    m.write(out / 'execution-plan.json', plan); (out / 'seal.json').unlink(); m.seal_output(out, 'qa')
    with pytest.raises(ValueError, match='prompt|binding'): m.check(out)


def install_synthetic_providers(m, checked, monkeypatch):
    monkeypatch.setattr(m, 'validated_build', lambda *args, **kwargs: checked)
    rows = synthetic_rows(m, checked)
    indexed = {(row['group_id'], row['item_id'], row['arm']): row for arm in m.ARMS for row in rows[arm]}
    class Embedder:
        request_count = 0
    def query(task, built, out, *args):
        gid, record, arm, embedder = task; row = deepcopy(indexed[(gid, record['item_id'], arm)])
        embedder.request_count = row['embedding_requests']; row.pop('native_invoked')
        m.qa_helpers.write(out / arm / 'recalls' / (m.text_sha(record['item_id']) + '.json'), row)
        return row
    monkeypatch.setattr(m, 'make_embedder', lambda *args: Embedder())
    monkeypatch.setattr(m, 'query_one', query)
    monkeypatch.setattr(m, 'make_adapters', lambda *args: (None, None, SyntheticAdapter('0'), SyntheticAdapter('yes')))


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('stage', ['retrieve', 'qa'])
@pytest.mark.parametrize('fault', ['initialize', 'native', 'helper_write', 'settlement', 'summary', 'summary_write'])
def test_stage_interruptions_are_sealed_and_raw_partial_cost_is_read_only_auditable(
        native, synthetic_contexts, tmp_path, monkeypatch, stage, fault):
    m, checked, runner, _ = native; install_synthetic_providers(m, checked, monkeypatch)
    def broken(*args, **kwargs): raise RuntimeError('injected ' + fault)
    if fault == 'initialize': monkeypatch.setattr(m, 'freeze_stage', broken)
    elif fault == 'native': monkeypatch.setattr(m, 'query_one' if stage == 'retrieve' else 'run_task', broken)
    elif fault == 'settlement':
        def ledger_factory(path, budget):
            ledger = runner.BudgetLedger(path, budget); ledger.settle = broken; return ledger
        monkeypatch.setattr(m, 'make_ledger', ledger_factory, raising=False)
    elif fault == 'summary': monkeypatch.setattr(m, 'retrieval_summary' if stage == 'retrieve' else 'qa_summary', broken)
    else:
        original_write = m.write
        def fail_write(path, value):
            if ((fault == 'summary_write' and Path(path).name == 'summary.json')
                or (fault == 'helper_write' and isinstance(value, dict) and 'accounting' in value)): broken()
            return original_write(path, value)
        monkeypatch.setattr(m, 'write', fail_write)
    out = tmp_path / stage
    summary = getattr(m, stage)(checked['built'] if stage == 'retrieve' else synthetic_contexts, out, workers=1)
    assert summary['state'] == 'incomplete' and 'policies' not in summary
    if fault == 'initialize': assert summary['known_tokens'] == 0 and not summary['local_attempt_count_unknown']
    if fault == 'native': assert summary['local_attempt_count_unknown']
    if fault == 'settlement': assert summary['unresolved_reservations']
    if stage == 'qa' and fault in ('helper_write', 'settlement', 'summary', 'summary_write'): assert summary['known_tokens'] > 0
    before = m.inventory(out); assert m.check(out)['summary'] == summary and before == m.inventory(out)
    assert {gid: m.sha(checked['built'] / 'runs' / gid / 'frozen.db') for gid in checked['databases']} == checked['databases']


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('stage', ['retrieve', 'qa'])
def test_provider_construction_failure_is_known_zero_without_native_invocation(
        native, synthetic_contexts, tmp_path, monkeypatch, stage):
    m, checked, _, _ = native; install_synthetic_providers(m, checked, monkeypatch)
    def unavailable(*args): raise RuntimeError('provider unavailable before native invocation')
    monkeypatch.setattr(m, 'make_embedder' if stage == 'retrieve' else 'make_adapters', unavailable)
    out = tmp_path / stage
    summary = getattr(m, stage)(checked['built'] if stage == 'retrieve' else synthetic_contexts, out, workers=1)
    assert summary['terminal_count'] == (266 if stage == 'retrieve' else 532) and summary['healthy_terminals'] == 0
    assert summary['total_tokens'] == 0 and not summary['local_attempt_count_unknown']
    assert m.check(out)['summary'] == summary


@pytest.mark.parametrize('field', ['prompt_tokens', 'completion_tokens', 'total_tokens'])
@pytest.mark.parametrize('bad', [True, 1.0, '1'])
def test_raw_usage_integer_types_are_never_coerced(field, bad):
    m = driver(); value = response(); body = json.loads(value['response']['raw_http_response'])
    body['usage'][field] = bad
    value['response']['raw_http_response'] = value['response']['http_attempts'][0]['response_body'] = json.dumps(body)
    cost = m.raw_accounting([value])
    assert cost['known_tokens'] == 0 and cost['total_tokens'] is None and not cost['healthy_http']


def test_source_only_native_failure_stays_known_zero():
    cost = driver().retrieval_accounting(dict(arm='source10', native_invoked=True, embedding_requests=0, status='error'))
    assert cost['total_tokens'] == 0 and not cost['local_attempt_count_unknown'] and not cost['remote_execution_unknown']


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('fault', ['seal', 'missing_ledger', 'corrupt_ledger', 'missing_ledger_after_plan', 'started_write'])
def test_additional_stage_failures_keep_costs_and_uncertainty(native, synthetic_contexts, tmp_path, monkeypatch, fault):
    m, checked, _, _ = native; install_synthetic_providers(m, checked, monkeypatch)
    def fail(): raise RuntimeError('injected ' + fault)
    if fault == 'seal': monkeypatch.setattr(m, 'seal_output', lambda *_: fail())
    elif fault in ('missing_ledger', 'corrupt_ledger'):
        def lost(out, *_args, **_kwargs):
            path = out / 'request-ledger.sqlite'
            if fault == 'missing_ledger': path.unlink()
            else: path.write_bytes(b'corrupt')
            fail()
        monkeypatch.setattr(m, 'qa_summary', lost)
    elif fault == 'missing_ledger_after_plan': monkeypatch.setattr(m, 'make_ledger', lambda *_: fail())
    else: monkeypatch.setattr(m, 'write_started', lambda *_: fail())
    out = tmp_path / 'qa'; result = m.qa(synthetic_contexts, out, workers=1)
    assert result['state'] == 'incomplete' and 'policies' not in result
    if fault in ('seal', 'missing_ledger', 'corrupt_ledger'): assert result['known_tokens'] == 11472
    if fault != 'seal': assert result['local_attempt_count_unknown'] and result['total_tokens'] is None
    if 'ledger' in fault: assert result['ledger_identity_unknown'] and result['unstarted_tasks'] == []
    before = m.inventory(out); assert m.check(out)['summary'] == result and m.inventory(out) == before


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_current_source_drift_blocks_run_but_historical_check_stays_read_only(native, synthetic_contexts, tmp_path, monkeypatch):
    m, checked, _, _ = native
    monkeypatch.setattr(m, 'validated_build', lambda *args, **kwargs: checked)
    original = m.source_files; values = original()
    monkeypatch.setattr(m, 'source_files', lambda: dict(values, changed='current-auditor-only'))
    assert m.check(synthetic_contexts)['audit_program_files']['changed'] == 'current-auditor-only'
    calls = 0
    def drift(*args, **kwargs):
        nonlocal calls
        calls += 1
        return values if calls <= 2 else dict(values, changed='during-initialization')
    monkeypatch.setattr(m, 'source_files', drift)
    monkeypatch.setattr(m, 'make_embedder', lambda *_: pytest.fail('provider called after source drift'))
    out = tmp_path / 'retrieval'; result = m.retrieve(checked['built'], out, workers=1)
    assert result['state'] == 'incomplete' and result['known_tokens'] == 0
    assert 'current evaluation source' in m.read(out / 'failure.json')['exception']
    assert m.check(out)['summary'] == result


@pytest.fixture(scope='module')
def localhost_stages(native, tmp_path_factory):
    """Real C++ and HTTP; only the provider factories and historical-run preflight are fixture overrides."""
    m, checked, runner, modules = native; core = modules[0]
    root = tmp_path_factory.mktemp('r59-localhost'); calls = []; lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            with lock: calls.append((self.path, request))
            if self.path.endswith('/embeddings'):
                count = len(request['input']) if isinstance(request['input'], list) else 1
                body = dict(data=[dict(index=i, embedding=[0.0] * 1024) for i in range(count)],
                            usage=dict(prompt_tokens=10, total_tokens=10))
            else:
                content = 'yes' if request['max_tokens'] == 64 else '0'
                body = dict(choices=[dict(message=dict(content=content, refusal=None), finish_reason='stop')],
                            usage=dict(prompt_tokens=10, completion_tokens=2, total_tokens=12))
            raw = json.dumps(body).encode(); self.send_response(200)
            self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(raw)))
            self.end_headers(); self.wfile.write(raw)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    endpoint = f'http://127.0.0.1:{server.server_port}/v1'
    environment = pytest.MonkeyPatch(); environment.setenv('OPENAI_API_KEY', 'offline-fixture')
    def embedder(_checked, _core, arm):
        if arm == 'source10': return core.StubEmbeddingAdapter(1024)
        cfg = core.OpenAIEmbeddingConfig.from_env(); cfg.base_url = endpoint
        cfg.model = checked['config']['embedding_model']; cfg.dim = 1024; cfg.timeout_ms = 120000; cfg.max_retries = 0
        return core.OpenAIEmbeddingAdapter(cfg)
    def adapters(*_):
        result = []
        for tokens in (512, 64):
            cfg = core.OpenAIAdapterConfig.from_env(); cfg.base_url = endpoint
            cfg.model = 'qwen3.8-27b'; cfg.timeout_ms = 120000; cfg.max_retries = 0; cfg.max_tokens = tokens
            if tokens == 512: cfg.enable_thinking = False
            result.append(core.OpenAIAdapter(cfg))
        return None, None, *result
    originals = m.validated_build, m.make_embedder, m.make_adapters
    try:
        m.validated_build = lambda *args, **kwargs: checked
        m.make_embedder, m.make_adapters = embedder, adapters
        retrieval = m.retrieve(checked['built'], root / 'retrieve', workers=4)
        assert retrieval['state'] == 'complete', retrieval
        answers = m.qa(root / 'retrieve', root / 'qa', workers=4)
        assert answers['state'] == 'complete', answers
    finally:
        m.validated_build, m.make_embedder, m.make_adapters = originals
        environment.undo()
        server.shutdown(); server.server_close(); thread.join()
    return root, calls


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_native_localhost_full_stages_and_independent_check(native, localhost_stages):
    m, checked, _, _ = native; root, calls = localhost_stages
    embeddings = [request for path, request in calls if path.endswith('/embeddings')]
    completions = [request for path, request in calls if not path.endswith('/embeddings')]
    assert len(embeddings) == 1336 and len(completions) == 956
    assert sum(request['max_tokens'] == 512 for request in completions) == 532
    assert sum(request['max_tokens'] == 64 for request in completions) == 424
    assert all(request['model'] == 'qwen3.8-27b' for request in completions)
    assert all(request.get('enable_thinking') is False for request in completions if request['max_tokens'] == 512)
    assert all('enable_thinking' not in request for request in completions if request['max_tokens'] == 64)
    rows = m.read_retrieval_rows(root / 'retrieve')
    assert all(r['embedding_requests'] == 0 and r['recall']['source_count'] > 0 for r in rows['source10'])
    assert all(m.ablation.healthy_embedding(r) for arm in m.ARMS for r in rows[arm])
    answers = [m.read(path) for path in (root / 'qa/answers').glob('*/*/*.json')]
    assert len(answers) == 532 and all(row['status'] == 'ok' for row in answers)
    for row in answers:
        assert row['answer']['raw_xml'].strip() == '0'
        assert row['answer']['response']['raw_response'] == row['answer']['raw_xml']
        assert row['answer']['raw_completion'] == row['answer']['raw_xml']
        assert row['accounting']['healthy_http'] and row['fresh'] is True
    before = m.inventory(root)
    process = subprocess.run([str(ROOT / '.venv/bin/python'), '-B', str(SCRIPT), 'check', '--input', str(root / 'qa')],
        cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), capture_output=True, text=True)
    assert process.returncode == 0, process.stdout + process.stderr
    audited = json.loads(process.stdout)
    assert audited['total_tokens'] == 11472 and audited['healthy_terminals'] == 532
    assert before == m.inventory(root)
    assert {gid: m.sha(checked['built'] / 'runs' / gid / 'frozen.db') for gid in checked['databases']} == checked['databases']


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('fault', ['source_text', 'source_ref', 'statement', 'prompt', 'judge_prompt', 'fresh', 'raw_binding'])
def test_native_context_and_qa_tampering_is_rejected(native, localhost_stages, fault):
    m, checked, runner, modules = native; root, _ = localhost_stages
    rows = m.read_retrieval_rows(root / 'retrieve')
    if fault in ('source_text', 'source_ref', 'statement'):
        row = rows['source10'][0]
        if fault == 'source_text':
            row['recall']['block'] += '\nforged source content'
            row['recall']['context_bytes'] = len(row['recall']['block'].encode())
        elif fault == 'source_ref': row['recall']['source_refs'][0]['engram_ref'] = 'forged'
        else: row['recall']['statement_ids'] = [999999999]
        with pytest.raises(ValueError): m.verify_contexts(checked, {'baseline': [], 'source10': [row]}, modules)
    else:
        task = next(task for task in m.make_tasks(checked, rows, runner, modules)
                    if task['record'].get('answer_format') != 'multiple_choice')
        row = m.read(root / 'qa/answers' / task['policy'] / task['arm'] / (m.text_sha(task['item_id']) + '.json'))
        if fault == 'prompt': row['prompt'] += ' forged'; row['prompt_sha256'] = m.text_sha(row['prompt'])
        elif fault == 'judge_prompt': row['judge_prompt'] += ' forged'; row['judge_prompt_sha256'] = m.text_sha(row['judge_prompt'])
        elif fault == 'fresh': row['fresh'] = False
        else: row['answer']['raw_xml'] = 'forged'
        with pytest.raises(ValueError): m.validate_qa_terminal(task, row, modules)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('fault', ['null_native', 'null_xml', 'null_completion'])
def test_malformed_native_metadata_is_technical_and_keeps_raw_cost(native, fault):
    m, checked, runner, modules = native
    task = m.make_tasks(checked, synthetic_rows(m, checked), runner, modules)[0]
    payload = response('0')
    if fault == 'null_native': payload['response'] = None
    elif fault == 'null_xml': payload['raw_xml'] = payload['response']['raw_response'] = None
    else:
        payload['raw_completion'] = payload['response']['raw_completion'] = None
        body = json.loads(payload['response']['raw_http_response']); body['choices'][0]['message']['content'] = None
        payload['response']['raw_http_response'] = payload['response']['http_attempts'][0]['response_body'] = json.dumps(body)
    status, correct, _, accounting = m.qa_verdict(task, dict(native_invoked=True, answer=payload), modules)
    assert status == 'technical_failure' and correct is False
    assert accounting['known_tokens'] == (0 if fault == 'null_native' else 12)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_joint_normalized_answer_tamper_is_rejected(native):
    m, checked, runner, modules = native
    rows = synthetic_rows(m, checked)
    task = next(task for task in m.make_tasks(checked, rows, runner, modules)
                if task['item_id'] == 'Q6_fm7s4c1' and task['arm'] == 'source10'
                and task['policy'] == 'grounded_memory_v1')
    answer = response('<think>trace</think>0')
    # This is the contract probe's joint normalized tamper: the HTTP body and
    # raw_completion remain untouched while normalized raw_xml/raw_response are
    # changed to the gold option.
    answer['raw_xml'] = answer['response']['raw_response'] = '2'
    row = dict((key, task[key]) for key in ('item_id', 'arm', 'policy', 'prompt', 'prompt_sha256', 'context_sha256'))
    row.update(terminal=True, fresh=True, native_invoked=True, answer=answer)
    accounting = m.raw_accounting([answer])
    row.update(status='ok', correct=True, prediction=2, accounting=accounting,
               reservation=dict(id=1, state='reserved', upper_bound=1), charged_requests=accounting['observed_http_attempts'])
    with pytest.raises(ValueError, match='raw response|raw_xml|raw_response|native binding|reasoning'):
        m.validate_qa_terminal(task, row, modules)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_http_message_content_tamper_is_rejected(native):
    m, checked, runner, modules = native
    task = m.make_tasks(checked, synthetic_rows(m, checked), runner, modules)[0]
    answer = response('0')
    body = json.loads(answer['response']['raw_http_response'])
    body['choices'][0]['message']['content'] = 'forged'
    answer['response']['raw_http_response'] = answer['response']['http_attempts'][0]['response_body'] = json.dumps(body)
    row = dict((key, task[key]) for key in ('item_id', 'arm', 'policy', 'prompt', 'prompt_sha256', 'context_sha256'))
    row.update(terminal=True, fresh=True, native_invoked=True, answer=answer,
               reservation=dict(id=1, state='reserved', upper_bound=1))
    accounting = m.raw_accounting([answer])
    row.update(status='ok', correct=True, prediction=0, accounting=accounting, charged_requests=accounting['observed_http_attempts'])
    with pytest.raises(ValueError, match='raw response|raw_xml|raw_response|native binding|reasoning'):
        m.validate_qa_terminal(task, row, modules)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_archived_source_manifest_cannot_drop_an_implementation_dependency(native, synthetic_contexts, monkeypatch):
    m, checked, _, _ = native; monkeypatch.setattr(m, 'validated_build', lambda *args, **kwargs: checked)
    dependency = synthetic_contexts / 'source/scripts/run_socialmem_r54_qa.py'
    identity_path = synthetic_contexts / 'identity.json'
    originals = {path: path.read_bytes() for path in (dependency, identity_path, synthetic_contexts / 'seal.json')}
    try:
        dependency.unlink(); identity = m.read(identity_path)
        identity['source_files'].pop('scripts/run_socialmem_r54_qa.py'); m.write(identity_path, identity)
        (synthetic_contexts / 'seal.json').unlink(); m.seal_output(synthetic_contexts, 'retrieve')
        with pytest.raises(ValueError, match='source|archive|dependency'): m.check(synthetic_contexts)
    finally:
        for path, value in originals.items(): path.write_bytes(value)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_second_runtime_root_is_rejected_before_embedding_construction(native, tmp_path, monkeypatch):
    m, checked, _, _ = native; other = dict(checked, prepared=tmp_path / 'other-prepare')
    shutil.copytree(checked['prepared'] / 'frozen', other['prepared'] / 'frozen')
    monkeypatch.setattr(m, 'validated_build', lambda *_args, **_kwargs: other)
    monkeypatch.setattr(m, 'make_embedder', lambda *_: pytest.fail('provider reached with wrong runtime'))
    with pytest.raises((ValueError, RuntimeError), match='frozen|runtime|identity'): m.runtime_modules(other)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_parallel_embedding_factories_serialize_process_environment_changes(native, monkeypatch):
    m, checked, _, modules = native; counts = dict(active=0, maximum=0); lock = threading.Lock()
    def factory(*_):
        with lock:
            counts['active'] += 1; counts['maximum'] = max(counts['maximum'], counts['active'])
        threading.Event().wait(0.02)
        with lock: counts['active'] -= 1
        return object()
    monkeypatch.setattr(m.previous.previous, '_build_embedder', factory)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: m.make_embedder(checked, modules[0], 'baseline'), range(8)))
    assert len({id(result) for result in results}) == 8 and counts['maximum'] == 1


def test_request_ledger_closes_connections_without_waiting_for_garbage_collection(tmp_path, monkeypatch):
    m = driver(); connect = sqlite3.connect; connections = []
    class Connection(sqlite3.Connection):
        closed = False
        def close(self):
            self.closed = True
            return super().close()
    def tracked(*args, **kwargs):
        kwargs['factory'] = Connection
        connection = connect(*args, **kwargs); connections.append(connection); return connection
    monkeypatch.setattr(sqlite3, 'connect', tracked)
    try:
        ledger = m.make_ledger(tmp_path / 'ledger.sqlite', 50)
        for index in range(20):
            reservation = ledger.reserve(str(index), 'answer_judge', 2)
            if index % 2: ledger.charge_upper(reservation['id'])
            else: ledger.settle(reservation['id'], 1)
        assert ledger.snapshot() == dict(budget=50, committed=30, reserved=0, charged_upper=20, remaining=20)
        assert ledger.reserve('blocked', 'answer_judge', 21) == dict(state='blocked', remaining=20)
        assert connections and all(connection.closed for connection in connections), 'SQLite context managers must not leave ledger file descriptors to GC'
        with pytest.raises(RuntimeError): ledger.settle(reservation['id'], 1)
        assert all(connection.closed for connection in connections)
    finally:
        for connection in connections: connection.close()


@pytest.mark.parametrize('operation', ['construct', 'reserve', 'settle', 'charge_upper', 'snapshot'])
def test_request_ledger_closes_every_connection_on_sql_exception(tmp_path, monkeypatch, operation):
    m = driver(); connect = sqlite3.connect; connections = []; armed = False
    class Connection(sqlite3.Connection):
        closed = False
        def execute(self, *args, **kwargs):
            if armed: raise sqlite3.OperationalError('injected SQL failure')
            return super().execute(*args, **kwargs)
        def close(self):
            self.closed = True
            return super().close()
    def tracked(*args, **kwargs):
        kwargs['factory'] = Connection
        connection = connect(*args, **kwargs); connections.append(connection); return connection
    monkeypatch.setattr(sqlite3, 'connect', tracked)
    try:
        path = tmp_path / 'ledger.sqlite'
        if operation != 'construct':
            ledger = m.make_ledger(path, 10); reservation = ledger.reserve('task', 'answer_judge', 2)
        for connection in connections: connection.close()
        connections.clear(); armed = True
        with pytest.raises(sqlite3.OperationalError, match='injected SQL failure'):
            if operation == 'construct': m.make_ledger(path, 10)
            elif operation == 'reserve': ledger.reserve('another', 'answer_judge', 2)
            elif operation == 'settle': ledger.settle(reservation['id'], 1)
            elif operation == 'charge_upper': ledger.charge_upper(reservation['id'])
            else: ledger.snapshot()
        assert connections and all(connection.closed for connection in connections)
    finally:
        for connection in connections: connection.close()
