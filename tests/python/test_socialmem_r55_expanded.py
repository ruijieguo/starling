"""R5.5 cohort, immutable stages and failure accounting; no provider requests."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/run_socialmem_r55_expanded.py'


def driver():
    assert SCRIPT.exists(), 'R5.5 staged runner must exist'
    spec = importlib.util.spec_from_file_location('r55_test_driver', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cohort(m):
    corpus = [json.loads(s) for s in m.DEFAULT_CORPUS.read_text().splitlines() if s.strip()]
    split = m.read(m.DEFAULT_SPLIT)
    old = m.read(m.DEFAULT_PARENT / 'sample.json')
    return corpus, split, old


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_fixed_selection_uses_only_new_development_networks():
    m = driver()
    records, groups, manifest = m.select_cohort(*cohort(m))
    assert manifest['networks'] == list(m.NETWORKS)
    assert manifest['questions'] == 133
    assert manifest['scopes'] == 8
    assert manifest['holder_scopes'] == 65
    assert manifest['history_turns'] == 1322
    assert manifest['free_response'] == 106
    assert manifest['query_embedding_bound'] == 1336
    assert manifest['qa_request_bound'] == 956
    assert len(records) == 133 and len(groups) == 8
    assert not set(manifest['networks']) & set(manifest['excluded_networks'])


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('change', ['reserved', 'duplicate', 'history', 'old_network'])
def test_selection_rejects_contamination_and_drift(change):
    m = driver()
    corpus, split, old = cohort(m)
    selected = next(r for r in corpus if m.baseline._network_id(r) == m.NETWORKS[0])
    if change == 'reserved':
        split['reserved_networks'].append(m.NETWORKS[0])
    elif change == 'duplicate':
        corpus.append(deepcopy(selected))
    elif change == 'history':
        selected['history'][0]['text'] += ' drift'
    else:
        old.append(deepcopy(selected))
    with pytest.raises(ValueError):
        m.select_cohort(corpus, split, old)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_full_record_group_identity_rejects_answer_drift():
    m = driver()
    records, groups, _ = m.select_cohort(*cohort(m))
    groups = deepcopy(groups)
    groups[0]['records'][0]['answer'] = 'changed'
    with pytest.raises(ValueError, match='group'):
        m.validate_record_groups(records, groups)


def health_fixture(tmp_path):
    group = {'group_id': 'g', 'history': [{'speaker': 'A', 'text': 'x'}, {'speaker': 'B', 'text': 'y'}]}
    db = tmp_path / 'frozen.db'
    with sqlite3.connect(db) as conn:
        conn.executescript('''
            CREATE TABLE statements (id TEXT, tenant_id TEXT, holder_id TEXT);
            CREATE TABLE statement_vectors (stmt_id TEXT, tenant_id TEXT, status TEXT, dim INTEGER, index_vector BLOB);
            CREATE TABLE source_documents (tenant_id TEXT, holder_id TEXT, engram_ref TEXT);
            CREATE TABLE engrams (id TEXT, tenant_id TEXT, payload_inline BLOB);
            INSERT INTO statements VALUES ('s1','default','A'),('s2','default','B');
            INSERT INTO statement_vectors VALUES ('s1','default','embedded',1024,x'01'),('s2','default','embedded',1024,x'01');
            INSERT INTO source_documents VALUES ('default','A','e1'),('default','B','e2');
        ''')
        conn.execute('UPDATE statement_vectors SET index_vector=zeroblob(4096)')
        for i, turn in enumerate(group['history'], 1):
            conn.execute('INSERT INTO engrams VALUES (?,?,?)', ('e' + str(i), 'default',
                ('@starling/source-turn-v1 ' + json.dumps(turn)).encode()))
    metadata = {'scope_state': 'complete', 'holder_complete': ['A', 'B'], 'holder_failures': [],
        'extraction': [{'holder': h, 'extraction_failed': False, 'receipt': {'channels': healthy_channels()}} for h in ['A', 'B']],
        'database': {'statements': 2, 'statement_vectors': 2},
        'embedding': {'embedded': 2, 'failed': 0, 'ticks': 2}, 'embedding_request_count': 1,
        'sources': {'documents': 2, 'turns': 2, 'engram_refs': ['e1', 'e2']}}
    return group, db, metadata


def healthy_channels():
    response = dict(ok=True, error='', finish_reason='stop', refusal=False, attempt_count=1,
                    total_tokens=3, http_attempts=[dict(http_status=200, curl_code=0,
                    execution_certainty='response_received', response_body='{"usage":{"total_tokens":3}}')])
    return dict(belief={'attempts': [{'extraction': deepcopy(response)}]},
                general_fact={'attempts': [{'extraction': deepcopy(response)}]},
                episodic={'ok': False, 'event_count': 0, 'response': deepcopy(response)})


def test_healthy_scope_has_observed_statement_and_source_counts(tmp_path):
    m = driver()
    report = m.validate_scope_health(*health_fixture(tmp_path))
    assert report['statements'] == 2
    assert report['pending_embeddings'] == 0
    assert report['source_documents'] == 2


@pytest.mark.parametrize('change', ['missing_holder', 'duplicate_holder', 'implicit_success', 'partial',
    'zero_statements', 'pending', 'embedding_failure', 'missing_source', 'false_source_count'])
def test_unhealthy_build_cannot_become_hybrid_control(tmp_path, change):
    m = driver()
    group, db, metadata = health_fixture(tmp_path)
    if change == 'missing_holder': metadata['extraction'].pop()
    elif change == 'duplicate_holder': metadata['extraction'].append(deepcopy(metadata['extraction'][0]))
    elif change == 'implicit_success': metadata['extraction'][0].pop('extraction_failed')
    elif change == 'partial': metadata['scope_state'] = 'partial'
    elif change == 'embedding_failure': metadata['embedding']['failed'] = 1
    elif change == 'false_source_count': metadata['sources']['turns'] = 1
    else:
        with sqlite3.connect(db) as conn:
            if change == 'zero_statements': conn.execute('DELETE FROM statements')
            elif change == 'pending': conn.execute("UPDATE statement_vectors SET status='pending' WHERE stmt_id='s1'")
            elif change == 'missing_source': conn.execute("DELETE FROM source_documents WHERE holder_id='B'")
    with pytest.raises(ValueError):
        m.validate_scope_health(group, db, metadata)


@pytest.mark.parametrize('stage', ['prepare', 'build', 'retrieve', 'qa'])
def test_existing_output_is_refused_before_reading_inputs(tmp_path, stage):
    m = driver()
    out = tmp_path / 'exists'; out.mkdir()
    with pytest.raises(ValueError, match='already exists'):
        if stage == 'prepare': m.prepare(tmp_path / 'absent', out)
        else: getattr(m, stage)(tmp_path / 'absent', out)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_prepare_is_offline_and_binds_all_inputs(tmp_path, monkeypatch):
    m = driver()
    monkeypatch.setattr(m, 'frozen_modules', lambda *_: pytest.fail('prepare imported native runtime'))
    out = tmp_path / 'prepared'
    result = m.prepare(m.DEFAULT_PARENT, out)
    assert result['questions'] == 133
    assert m.check(out)['stage'] == 'prepare'
    assert (out / 'implementation/scripts/run_socialmem_r55_expanded.py').exists()
    assert (out / 'current-source/src/retrieval/source_retriever.cpp').exists()
    assert m.read(out / 'provenance.json')['inherited_source_tree'] == 'historical_R5.0_not_current_core_source'
    assert m.sha(out / 'corpus.jsonl') == m.CORPUS_SHA256
    assert not (out / 'request-ledger.sqlite').exists()
    (out / 'sample.json').write_text('[]')
    with pytest.raises(ValueError, match='seal'):
        m.check(out)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('target', ['config', 'core', 'implementation', 'extra'])
def test_resealed_identity_drift_rejected(tmp_path, target):
    m = driver()
    out = tmp_path / 'prepared'
    m.prepare(m.DEFAULT_PARENT, out)
    if target == 'config':
        value = m.read(out / 'config.json'); value['max_retries'] = 1; m.write(out / 'config.json', value)
        ident = m.read(out / 'identity.json'); ident['config_sha256'] = m.sha(out / 'config.json'); m.write(out / 'identity.json', ident)
    elif target == 'core':
        next((out / 'frozen/python/starling').glob('_core*.so')).write_bytes(b'wrong-core')
    elif target == 'implementation':
        (out / 'implementation/scripts/run_socialmem_r54_qa.py').write_text('# drift\n')
    else:
        (out / 'surprise.json').write_text('{}')
    if target != 'extra':
        (out / 'seal.json').unlink(); m.seal_output(out, 'prepare')
    with pytest.raises(ValueError):
        m.check(out)


def test_terminal_inventory_rejects_duplicates_failure_credit_and_missing():
    m = driver()
    records = [{'item_id': 'x'}]
    rows = [{'item_id': 'x', 'arm': arm, 'policy': policy, 'terminal': True, 'status': 'ok', 'correct': False,
             'fresh': True} for arm in m.ARMS for policy in m.POLICIES]
    m.validate_terminal_inventory(records, rows)
    for bad in [rows[:-1], rows + [rows[0]], [{**r, 'correct': True, 'status': 'technical_failure'} for r in rows]]:
        with pytest.raises(ValueError): m.validate_terminal_inventory(records, bad)


def test_budget_unknown_exception_is_charged_and_terminal_saved(tmp_path):
    m = driver()
    ledger = m.baseline.BudgetLedger(tmp_path / 'ledger.sqlite', 2)
    class Broken:
        def extract(self, *_): raise RuntimeError('unknown request outcome')
    task = {'item_id': 'q', 'arm': 'baseline', 'policy': 'legacy', 'record': {'item_id': 'q', 'answer_format': 'free_response'},
            'recall': {'block': 'ctx'}, 'prompt': 'p', 'prompt_sha256': m.qa_helpers.text_sha('p'),
            'context_sha256': m.qa_helpers.text_sha('ctx')}
    modules = (None,) * 6
    row = m.qa_helpers.run_task(task, tmp_path / 'answers', m.baseline, modules, ledger, (None, None, Broken(), Broken()))
    assert row['terminal'] and row['status'] == 'technical_failure' and not row['correct']
    assert ledger.snapshot()['charged_upper'] == 2
    assert ledger.reserve('other', 'qa', 1)['state'] == 'blocked'


def test_primary_gate_uses_fixed_denominator_and_grounded_policy():
    m = driver()
    records = [{'item_id': str(i), 'network_id': 'g' + str(i % 6)} for i in range(133)]
    left = [{'item_id': r['item_id'], 'terminal': True, 'status': 'ok', 'correct': False} for r in records]
    right = [{**r, 'correct': i < 6} for i, r in enumerate(left)]
    result = m.compare_scores(records, left, right, repetitions=200)
    assert result['accuracy_gain'] == pytest.approx(6 / 133)
    assert result['eligible_for_expanded_development'] is False
    right = [{**r, 'correct': i < 12} for i, r in enumerate(left)]
    result = m.compare_scores(records, left, right, repetitions=200)
    assert result['eligible_for_expanded_development'] is True
    for r in right[:14]: r.update(status='technical_failure', correct=False)
    result = m.compare_scores(records, left, right, repetitions=200)
    assert result['denominator'] == 133
    assert result['eligible_for_expanded_development'] is False


@pytest.mark.parametrize('change', ['error', 'length', 'empty_finish', 'missing', 'http_missing', 'http_failure', 'raw_body_missing'])
def test_episodic_native_response_must_be_healthy(tmp_path, change):
    m = driver(); group, db, metadata = health_fixture(tmp_path)
    channel = metadata['extraction'][0]['receipt']['channels']['episodic']
    if change == 'missing': channel.pop('response')
    elif change == 'error': channel['response'].update(ok=False, error='provider failure')
    elif change == 'length': channel['response']['finish_reason'] = 'length'
    elif change == 'empty_finish': channel['response']['finish_reason'] = ''
    elif change == 'http_missing': channel['response']['http_attempts'] = []
    elif change == 'raw_body_missing': channel['response']['http_attempts'][0].pop('response_body')
    else: channel['response']['http_attempts'][0]['http_status'] = 500
    with pytest.raises(ValueError, match='native|response|HTTP'):
        m.validate_scope_health(group, db, metadata)


def test_episodic_empty_or_unparsed_is_separate_from_transport_health(tmp_path):
    m = driver(); group, db, metadata = health_fixture(tmp_path)
    report = m.validate_scope_health(group, db, metadata)
    assert report['episodic_empty_or_unparsed_count'] == 2
    usage = m.extraction_usage(metadata['extraction'])
    assert usage['observed_native_requests'] == 6
    assert usage['observed_tokens'] == 18


def test_source_payload_must_contain_exact_history_turns(tmp_path):
    m = driver(); group, db, metadata = health_fixture(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE engrams SET payload_inline=? WHERE id='e1'", (b'@starling/source-turn-v1 {"speaker":"A","text":"wrong"}',))
    with pytest.raises(ValueError, match='source'):
        m.validate_scope_health(group, db, metadata)


def test_judge_flip_audit_groups_exact_judge_input_even_if_answer_prompts_differ():
    m = driver()
    rows = [dict(item_id='q', status='ok', correct=correct, judge={}, judge_prompt='same actual input',
                 prompt_sha256=str(i), arm=arm, policy='legacy', answer={'raw_xml': 'same answer'})
            for i, (arm, correct) in enumerate([('baseline', False), ('source10', True)])]
    result = m.judge_flip_audit(rows)
    assert result['identical_judge_input_groups'] == 1
    assert result['judge_flip_groups'] == 1


def test_primary_gate_rejects_one_arm_below_95_percent_even_with_aggregate_above():
    m = driver()
    records = [{'item_id': str(i), 'network_id': 'g' + str(i % 6)} for i in range(133)]
    left = [dict(item_id=r['item_id'], terminal=True, status='ok', correct=False) for r in records]
    right = [{**r, 'correct': i < 30} for i, r in enumerate(left)]
    for r in left[:7]: r['status'] = 'technical_failure'
    assert (126 + 133) / 266 >= .95
    result = m.compare_scores(records, left, right, repetitions=200)
    assert result['accuracy_gain'] > .05 and result['bootstrap']['ci95_percent'][0] > 0
    assert result['eligible_for_expanded_development'] is False


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_question_type_breakdown_uses_corpus_query_type():
    m = driver(); records, _, _ = m.select_cohort(*cohort(m))
    rows = [dict(item_id=r['item_id'], arm=a, status='ok', correct=False) for r in records for a in m.ARMS]
    counts = {k: v['questions'] for k, v in m._breakdowns(records, rows)['question_type'].items()}
    assert counts == dict(Q1=25, Q2=10, Q3=1, Q4=10, Q5=12, Q6=8, Q7=24, Q8=40, Q9=3)


def test_truncated_vector_blob_fails_scope_health(tmp_path):
    m = driver(); group, db, metadata = health_fixture(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE statement_vectors SET index_vector=x'01' WHERE stmt_id='s1'")
    with pytest.raises(ValueError, match='embedding'):
        m.validate_scope_health(group, db, metadata)


def test_native_preserved_invalid_time_source_v2_is_accepted(tmp_path):
    m = driver(); group, db, metadata = health_fixture(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE engrams SET payload_inline=replace(CAST(payload_inline AS TEXT),'source-turn-v1','source-turn-v2')")
    assert m.validate_scope_health(group, db, metadata)['source_turns'] == 2


def test_ledger_validation_is_read_only_and_does_not_create_missing_db(tmp_path):
    m = driver(); path = tmp_path / 'ledger.sqlite'
    with pytest.raises(ValueError, match='ledger'):
        m.read_ledger(path, 2)
    assert not path.exists()
    ledger = m.baseline.BudgetLedger(path, 2)
    reservation = ledger.reserve('scope', 'answer_judge', 2)
    ledger.charge_upper(reservation['id'])
    before = m.sha(path)
    assert m.read_ledger(path, 2) == ledger.snapshot()
    assert m.sha(path) == before
    assert not Path(str(path) + '-wal').exists() and not Path(str(path) + '-shm').exists()


def offline_stage_adapters(m, monkeypatch):
    """Replace only native/provider boundaries; run real cohort, ledger, stages and QA helpers."""
    class Response:
        ok, error, raw_completion = True, '', ''
        raw_xml = 'yes'
        def to_json(self): return json.dumps(dict(attempt_count=1, total_tokens=3, http_attempts=[{'http_status': 200}]))
    llm = SimpleNamespace(extract=lambda *_: Response())
    def construct(work, config, identity):
        core = SimpleNamespace(__file__=str(next((work / 'frozen/python/starling').glob('_core*.so'))),
                               StubEmbeddingAdapter=lambda dim: SimpleNamespace(request_count=0))
        runner = SimpleNamespace(BudgetLedger=m.baseline.BudgetLedger, BudgetBlocked=m.baseline.BudgetBlocked,
            history_holders=m.baseline.history_holders, _make_native_adapters=lambda *_: (llm, SimpleNamespace(request_count=0), llm, llm),
            _build_scope_database=fake_build, response_text=m.baseline.response_text,
            _response_attempts=m.baseline._response_attempts,
            answer_prompt=lambda c, l, record, recall, conf: record['question'] + '\n' + recall['block'] + conf['answer_policy'])
        audit = SimpleNamespace(_judge_prompt=lambda q, gold, answer: q + str(gold) + answer,
                                _parse_judge_verdict=lambda answer: answer == 'yes')
        parser = SimpleNamespace(_parse_option_index=lambda *_: 0)
        return runner, (core, None, audit, None, None, parser)
    def fake_build(group, scope_dir, modules, config, adapters, ledger, reservation):
        holders = m.baseline.history_holders(group['history']); db = scope_dir / 'frozen.db'
        with sqlite3.connect(db) as conn:
            conn.executescript('''CREATE TABLE statements (id TEXT,tenant_id TEXT,holder_id TEXT);
                CREATE TABLE statement_vectors (stmt_id TEXT,tenant_id TEXT,status TEXT,dim INTEGER,index_vector BLOB);
                CREATE TABLE source_documents (tenant_id TEXT,holder_id TEXT,engram_ref TEXT);
                CREATE TABLE engrams (id TEXT,tenant_id TEXT,payload_inline BLOB);''')
            for i, holder in enumerate(holders):
                conn.execute('INSERT INTO statements VALUES (?,?,?)', (str(i), 'default', holder))
                conn.execute("INSERT INTO statement_vectors VALUES (?,?,'embedded',1024,zeroblob(4096))", (str(i), 'default'))
                conn.execute('INSERT INTO source_documents VALUES (?,?,?)', ('default', holder, str(i)))
                payload = '\n'.join('@starling/source-turn-v1 ' + json.dumps(t) for t in group['history'] if t['speaker'] == holder)
                conn.execute('INSERT INTO engrams VALUES (?,?,?)', (str(i), 'default', payload.encode()))
        ledger.charge_upper(reservation['id'])
        embedding_res = ledger.reserve(group['group_id'], 'scope_embedding', m.baseline._embedding_reservation(len(holders)))
        ledger.settle(embedding_res['id'], 1)
        extraction = [dict(holder=h, extraction_failed=False, receipt={'channels': healthy_channels()}) for h in holders]
        m.baseline.write_extraction_receipt_archive(scope_dir, extraction)
        return db, dict(scope_state='complete', holder_complete=holders, holder_failures=[], extraction=extraction,
            database=dict(statements=len(holders), statement_vectors=len(holders)), embedding=dict(embedded=len(holders), failed=0, ticks=2),
            embedding_request_count=1, sources=dict(documents=len(holders), turns=len(group['history']), engram_refs=[str(i) for i in range(len(holders))]))
    def fake_query(task, parent, out, provenance, config, core, runtime, pipeline):
        gid, record, arm, embedder = task
        holders = m.baseline.history_holders(record['history'])
        strategy, mode, k = m.ablation.ARMS[arm]
        return dict(item_id=record['item_id'], group_id=gid, arm=arm, holders=holders, strategy=strategy, mode=mode, k=k,
            database_sha256=provenance['database_sha256'][gid], core_sha256=config['core_sha256'], status='ok', terminal=True,
            embedding_requests=len(holders) if arm == 'baseline' else 0,
            recall=dict(block='', source_refs=[], statement_ids=[], source_count=0, statement_count=0,
                context_bytes=0, source_context_bytes=0, statement_context_bytes=0,
                receipts=[dict(holder=h, degraded_paths=[]) for h in holders] if arm == 'baseline' else []))
    monkeypatch.setattr(m, 'frozen_modules', construct)
    monkeypatch.setattr(m.previous, '_build_embedder', lambda *_: SimpleNamespace(request_count=0))
    monkeypatch.setattr(m.ablation, 'query_one', fake_query)
    monkeypatch.setattr(m.qa_helpers, 'BOOTSTRAP_REPETITIONS', 100)
    return fake_build


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_full_offline_stage_chain_has_266_retrieval_and_532_fresh_qa_terminals(tmp_path, monkeypatch):
    m = driver(); offline_stage_adapters(m, monkeypatch)
    prepared, built, retrieved, qa_out = [tmp_path / name for name in ('prepare', 'build', 'retrieve', 'qa')]
    m.prepare(m.DEFAULT_PARENT, prepared)
    build_result = m.build(prepared, built)
    assert build_result['ledger']['committed'] == 585 + 8
    assert build_result['extraction_observed_requests'] == 65 * 3
    assert build_result['extraction_conservative_charge'] == 585
    before = m.inventory(built)
    retrieve_result = m.retrieve(built, retrieved, workers=2)
    assert m.inventory(built) == before
    assert retrieve_result['terminal_count'] == 266
    assert retrieve_result['ledger']['committed'] == 1336
    assert m.read(retrieved / 'comparison.json')['anchors']['source10']['hit'] == 0
    checked = m.check(retrieved)
    for mutation in ('missing', 'duplicate', 'holder', 'degradation_missing', 'source_embedding', 'wrong_db'):
        rows = deepcopy(checked['rows'])
        if mutation == 'missing': rows['baseline'].pop()
        elif mutation == 'duplicate': rows['baseline'][-1] = deepcopy(rows['baseline'][0])
        elif mutation == 'holder': rows['baseline'][0]['holders'].pop()
        elif mutation == 'degradation_missing': rows['baseline'][0]['recall']['receipts'][0].pop('degraded_paths')
        elif mutation == 'source_embedding': rows['source10'][0]['embedding_requests'] = 1
        else: rows['baseline'][0]['database_sha256'] = 'wrong'
        with pytest.raises(ValueError):
            m.validate_retrieval_inventory(checked['records'], checked['groups'], rows,
                retrieve_result['database_sha256'], checked['config'])
    # A zero-quality source context must not prevent QA once technical health passes.
    qa_result = m.qa(retrieved, qa_out, workers=2)
    assert qa_result['terminal_count'] == 532
    assert qa_result['native_requests'] == qa_result['ledger']['committed'] == 956
    assert qa_result['primary_endpoint'] == 'grounded_memory_v1_all_question_accuracy_gain'
    assert not qa_result['automatic_promotion']
    before = m.inventory(qa_out)
    assert m.check(qa_out)['stage'] == 'qa'
    assert m.inventory(qa_out) == before
    # Even a resealed terminal inventory cannot conceal a missing answer.
    next((qa_out / 'answers/legacy/baseline').glob('*.json')).unlink()
    (qa_out / 'seal.json').unlink(); m.seal_output(qa_out, 'qa')
    with pytest.raises(ValueError, match='inventory'):
        m.check(qa_out)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_partial_build_preserves_failed_seal_and_budget_and_blocks_followups(tmp_path, monkeypatch):
    m = driver(); fake_build = offline_stage_adapters(m, monkeypatch)
    original = m.frozen_modules
    def unhealthy_modules(*args):
        runner, modules = original(*args)
        def partial(*params):
            db, metadata = fake_build(*params); metadata['scope_state'] = 'partial'
            return db, metadata
        runner._build_scope_database = partial
        return runner, modules
    monkeypatch.setattr(m, 'frozen_modules', unhealthy_modules)
    prepared, built = tmp_path / 'prepare', tmp_path / 'build'
    m.prepare(m.DEFAULT_PARENT, prepared)
    with pytest.raises(ValueError, match='partial'):
        m.build(prepared, built)
    assert m.read(built / 'seal.json')['state'] == 'incomplete'
    assert m.read(built / 'failure-summary.json')['ledger']['charged_upper'] == 36
    assert len(list((built / 'runs').glob('*/scope.failure.json'))) == 1
    with pytest.raises(ValueError, match='incomplete'):
        m.retrieve(built, tmp_path / 'retrieved')
    with pytest.raises(ValueError, match='already exists'):
        m.build(prepared, built)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_failed_retrieval_preserves_terminals_and_charges_unknown_request_bound(tmp_path, monkeypatch):
    m = driver(); offline_stage_adapters(m, monkeypatch)
    original = m.ablation.query_one
    def failed_query(task, *args):
        row = original(task, *args)
        if task[2] == 'baseline':
            row.update(status='error', error='unknown request outcome', embedding_requests=0)
        return row
    monkeypatch.setattr(m.ablation, 'query_one', failed_query)
    prepared, built, retrieved = [tmp_path / name for name in ('prepare', 'build', 'retrieve')]
    m.prepare(m.DEFAULT_PARENT, prepared); m.build(prepared, built)
    with pytest.raises(ValueError, match='unhealthy'):
        m.retrieve(built, retrieved, workers=2)
    seal = m.read(retrieved / 'seal.json')
    failure = m.read(retrieved / 'failure-summary.json')
    assert seal['state'] == 'incomplete' and failure['saved_retrieval_receipts'] == 266
    assert failure['ledger']['charged_upper'] == 1336 and failure['ledger']['reserved'] == 0
    assert all(m.read(p)['budget_unknown'] for p in (retrieved / 'baseline/recalls').glob('*.json'))
    with pytest.raises(ValueError, match='incomplete'):
        m.qa(retrieved, tmp_path / 'qa')


def test_wal_formatted_frozen_database_health_is_repeatable_without_side_files(tmp_path):
    m = driver(); group, database, metadata = health_fixture(tmp_path)
    connection = sqlite3.connect(database)
    assert connection.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal'
    connection.close()
    assert database.read_bytes()[18:20] == b'\x02\x02'
    before = m.inventory(tmp_path)
    for _ in range(3):
        assert m.validate_scope_health(group, database, metadata)['statements'] == 2
        assert m.inventory(tmp_path) == before
        assert not Path(str(database) + '-wal').exists()
        assert not Path(str(database) + '-shm').exists()


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_qa_summary_with_judge_flips_is_order_independent(monkeypatch):
    m = driver(); monkeypatch.setattr(m.qa_helpers, 'BOOTSTRAP_REPETITIONS', 20)
    records, _, _ = m.select_cohort(*cohort(m))
    rows = [dict(item_id=r['item_id'], arm=a, policy=p, status='ok', terminal=True, fresh=True,
        correct=a == 'source10', native_attempt_count=2, charged_requests=2, tokens=6,
        prompt_sha256='identical answer prompt', judge_prompt=r['question'],
        answer={'raw_xml': 'same answer', 'response': {'total_tokens': 3}}, judge={'response': {'total_tokens': 3}})
        for r in records for p in m.POLICIES for a in m.ARMS]
    forward = m._qa_summary(records, rows, {})
    reverse = m._qa_summary(records, list(reversed(rows)), {})
    assert forward['judge_flip_audit']['judge_flip_groups'] > 0
    assert forward == reverse


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_native_scope_archive_seal_survives_process_exit(tmp_path):
    import subprocess
    import sys
    code = r'''
import importlib.util, json, sys
from pathlib import Path
from types import SimpleNamespace
root=Path(sys.argv[1]); work=Path(sys.argv[2]); scratch=work/'scratch'; out=work/'archived'
scratch.mkdir(); out.mkdir()
spec=importlib.util.spec_from_file_location('r55_native_exit',root/'scripts/run_socialmem_r55_expanded.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
parent=m.DEFAULT_PARENT;config=m.read(parent/'config.json');identity=m.read(parent/'identity.json')
runner,modules=m.frozen_modules(parent,config,identity);core=modules[0]
llm=core.FakeLLMAdapter();llm.set_default_response('[]')
modules[4].embed_seeded=lambda *a,**k:dict(embedded=0,failed=0,ticks=0)
group=dict(group_id='g',history=[dict(speaker='A',text='hello',turn_id='t1',observed_at='2026-01-01T00:00:00Z')])
ledger=runner.BudgetLedger(out/'request-ledger.sqlite',1000);reservation=ledger.reserve('g','scope_extraction',9)
runner._build_scope_database(group,scratch,modules,config,(llm,SimpleNamespace(request_count=0),llm,llm),ledger,reservation)
m.archive_scope_outputs(scratch,out,complete=True)
m.seal_output(out,'build',state='incomplete')
'''
    result = subprocess.run([sys.executable, '-c', code, str(ROOT), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    m = driver(); out = tmp_path / 'archived'
    assert (out / 'frozen.db').is_file() and (out / 'extraction.completed.json').is_file()
    assert not list(out.glob('network.db*')) and not list(out.glob('*-wal')) and not list(out.glob('*-shm'))
    sealed = m.read(out / 'seal.json')['files']; actual = m.inventory(out); actual.pop('seal.json')
    assert actual == sealed


def test_failure_archive_backs_up_committed_wal_state(tmp_path):
    m = driver(); scratch=tmp_path/'scratch';scratch.mkdir();out=tmp_path/'archived';out.mkdir()
    connection=sqlite3.connect(scratch/'network.db')
    try:
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('CREATE TABLE marker (value INTEGER)')
        connection.execute('INSERT INTO marker VALUES (42)');connection.commit()
        (scratch/'extraction.completed.json').write_text('{"raw":"preserved"}')
        m.archive_scope_outputs(scratch,out,complete=False)
        snapshot=sqlite3.connect('file:'+str(out/'diagnostic.db')+'?mode=ro&immutable=1',uri=True)
        try: assert snapshot.execute('SELECT value FROM marker').fetchall() == [(42,)]
        finally: snapshot.close()
        assert m.read(out/'extraction.completed.json') == {'raw':'preserved'}
        assert not list(out.glob('network.db*')) and not list(out.glob('*-wal')) and not list(out.glob('*-shm'))
    finally:
        connection.close()
