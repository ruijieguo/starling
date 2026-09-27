"""R5.6 rebuild provenance, native batching and accounting; no provider calls."""
from contextlib import closing
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/run_socialmem_r56_expanded.py'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def driver():
    assert SCRIPT.is_file(), 'R5.6 independent rebuild entry is required'
    return load(SCRIPT, 'r56_expanded_test')


def run_code(code, *args):
    result = subprocess.run([sys.executable, '-c', code, *map(str, args)], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_baseline_default_and_explicit_native_batch_policy():
    baseline = load(ROOT / 'scripts/run_socialmem_baseline.py', 'r56_mapping_test')
    assert baseline._build_extraction_config({}).to_native_policy().claim_batch_size == 0
    policy = baseline._build_extraction_config(dict(semantic_claim_contract=True,
        preserve_text_objects=True, claim_batch_size=8)).to_native_policy()
    assert policy.claim_batch_size == 8


@pytest.mark.parametrize('stage', ['prepare', 'build'])
def test_refuse_existing_output_before_reading_inputs(tmp_path, stage):
    m = driver(); out = tmp_path / 'exists'; out.mkdir()
    with pytest.raises(ValueError, match='already exists'):
        getattr(m, stage)(tmp_path / 'missing', out)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_fixed_historical_seals_validate_without_current_source_gate():
    m = driver(); result = m.validate_parents(m.DEFAULT_PARENT, m.DEFAULT_PROBE)
    assert len(result['groups']) == 8 and len(result['records']) == 133
    assert result['config']['claim_batch_size'] == 8
    assert result['config']['preserve_invalid_time'] is True
    assert result['config']['core_sha256'] == '4c5a7c39ae708a13d10065a0816a5c97a994929479cb0898f504c21e12b422f9'


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_historical_seal_rejects_added_file(tmp_path):
    m = driver(); parent = tmp_path / 'parent'
    parent.mkdir(); m.write(parent / 'seal.json', m.read(m.DEFAULT_PARENT / 'seal.json'))
    m.write(parent / 'extra.json', {})
    with pytest.raises(ValueError, match='seal'):
        m.validate_parents(parent, m.DEFAULT_PROBE)


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    driver(); out = tmp_path_factory.mktemp('r56-prepare') / 'prepare'
    run_code("""
import importlib.util,sys
from pathlib import Path
s=importlib.util.spec_from_file_location('m','scripts/run_socialmem_r56_expanded.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
m.baseline._make_native_adapters=lambda *_: (_ for _ in ()).throw(AssertionError('provider forbidden'))
result=m.prepare(m.DEFAULT_PARENT,Path(sys.argv[1]));m.check(Path(sys.argv[1]))
assert result['external_requests']==0
""", out)
    return out


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_prepare_freezes_current_runtime_and_native_851_bound(prepared):
    m = driver(); plans = m.read(prepared / 'batch-plans.json')
    assert plans['holder_count'] == 65 and plans['source_units'] == 1322
    assert plans['batches'] == 197 and plans['belief_request_upper_bound'] == 591
    assert plans['extraction_request_upper_bound'] == 851
    bounds = [s['extraction_request_upper_bound'] for s in plans['scopes'].values()]
    assert len(bounds) == 8 and len(set(bounds)) > 1 and sum(bounds) == 851
    assert not (prepared / 'request-ledger.sqlite').exists()
    for relative in ['bindings/python/module.cpp', 'build/CMakeCache.txt',
                     'tests/python/test_socialmem_r56_expanded.py']:
        assert (prepared / 'source' / relative).is_file()
    frozen = prepared / 'frozen/scripts/run_socialmem_baseline.py'
    assert m.sha(frozen) == m.sha(ROOT / 'scripts/run_socialmem_baseline.py')


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
@pytest.mark.parametrize('change', ['summary', 'config', 'core', 'source', 'parent', 'plan', 'target'])
def test_resealed_prepare_forgery_rejected(prepared, tmp_path, change):
    m = driver(); out = tmp_path / 'prepare'; shutil.copytree(prepared, out)
    if change == 'summary':
        value = m.read(out / 'summary.json'); value['extraction_conservative_bound'] = 585
        m.write(out / 'summary.json', value)
    elif change == 'config':
        value = m.read(out / 'config.json'); value['claim_batch_size'] = 0; m.write(out / 'config.json', value)
        identity = m.read(out / 'identity.json'); identity['config_sha256'] = m.sha(out / 'config.json')
        m.write(out / 'identity.json', identity)
    elif change == 'core': next((out / 'frozen/python/starling').glob('_core*.so')).write_bytes(b'wrong core')
    elif change == 'source': (out / 'source/scripts/run_socialmem_baseline.py').write_text('# changed')
    elif change == 'parent': m.write(out / 'parent-seal.json', {})
    else:
        value = m.read(out / 'batch-plans.json'); scope = next(iter(value['scopes'].values()))
        plan = next(iter(scope['holders'].values()))
        if change == 'plan': plan['batches'].pop()
        else: plan['batches'][0]['target_clause_ids'] = ['c9999']
        m.write(out / 'batch-plans.json', value)
    (out / 'seal.json').unlink(); m.seal_output(out, 'prepare')
    run_code("""
import importlib.util,sys
from pathlib import Path
s=importlib.util.spec_from_file_location('m','scripts/run_socialmem_r56_expanded.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
try:m.check(Path(sys.argv[1]))
except ValueError:pass
else:raise AssertionError('re-sealed forgery accepted')
""", out)


def response():
    usage = dict(prompt_tokens=10, completion_tokens=2, total_tokens=12)
    return dict(ok=True, error='', refusal=False, finish_reason='stop', attempt_count=1,
        **usage, http_attempts=[dict(curl_code=0, http_status=200,
        execution_certainty='response_received', response_body=json.dumps(dict(usage=usage)))])


def extraction_fixture():
    plan = dict(claim_batch_size=8, claim_protocol_retry_budget=1, source_payload_hash='source-hash',
        source_units=[{'clause_id': 'c0'}, {'clause_id': 'c1'}],
        batches=[dict(batch_index=i, target_clause_ids=[f'c{i}']) for i in range(2)],
        belief_request_upper_bound=6)
    belief = dict(holder='A', source_payload_hash='source-hash', claim_batch_size=8,
        claim_batch_plan=deepcopy(plan), claim_batches_complete=True, claim_batch_integrity_detail='',
        persistence_error='', failure_category='', attempts=[dict(attempt=i+1, terminal=True,
        batch_index=i, target_clause_ids=[f'c{i}'], extraction=response(),
        admission=dict(called=False, attempt_count=0, http_attempts=[])) for i in range(2)])
    general = dict(attempts=[dict(attempt=1, extraction=response(), admission=dict(called=True, **response()))])
    row = dict(holder='A', extraction_failed=False,
        receipt=dict(channels=dict(belief=belief, general_fact=general, episodic=dict(response=response()))))
    return [row], dict(holders={'A': plan}, extraction_request_upper_bound=10)


def test_batch_health_allows_semantic_rejection_and_protocol_retry():
    m = driver(); rows, scope = extraction_fixture()
    belief = rows[0]['receipt']['channels']['belief']; belief['failure_category'] = 'semantic_rejection'
    retry = deepcopy(belief['attempts'][0]); retry['terminal'] = False; retry['errors'] = [{'kind': 'schema_failure'}]
    belief['attempts'].insert(0, retry)
    for i, attempt in enumerate(belief['attempts'], 1): attempt['attempt'] = i
    assert m.validate_batch_receipts(rows, scope)['holders'] == 1
    usage = m.extraction_accounting(rows)
    assert usage['observed_native_requests'] == 6 and usage['observed_tokens'] == 72
    assert usage['usage_complete'] is True


@pytest.mark.parametrize('change', ['target', 'missing', 'incomplete', 'numbering', 'general_plan', 'late_failure', 'over_budget'])
def test_batch_receipt_tampering_and_late_failure_rejected(change):
    m = driver(); rows, scope = extraction_fixture(); channels = rows[0]['receipt']['channels']; belief=channels['belief']
    if change == 'target': belief['attempts'][1]['target_clause_ids'] = ['c0']
    elif change == 'missing': belief['attempts'].pop()
    elif change == 'incomplete': belief['claim_batches_complete'] = False
    elif change == 'numbering': belief['attempts'][1]['attempt'] = 1
    elif change == 'general_plan': channels['general_fact']['claim_batch_plan'] = belief['claim_batch_plan']
    elif change == 'late_failure': belief['attempts'][1]['extraction']['finish_reason'] = 'length'
    else: scope['extraction_request_upper_bound'] = 1
    with pytest.raises(ValueError): m.validate_batch_receipts(rows, scope)


def test_raw_usage_missing_is_unknown_not_zero():
    m = driver(); rows, _ = extraction_fixture()
    for response_row in m.previous.native_extraction_responses(rows):
        response_row['http_attempts'][0]['response_body'] = '{}'
    usage = m.extraction_accounting(rows)
    assert usage['observed_native_requests'] == 5
    assert usage['observed_tokens'] is None and usage['usage_complete'] is False
    assert usage['missing_token_usage'] == 5
    assert m.extraction_accounting(None)['local_attempt_count_unknown'] is True


def test_failure_snapshot_includes_committed_wal(tmp_path):
    m = driver(); scratch=tmp_path/'scratch'; scratch.mkdir(); out=tmp_path/'out'
    with closing(sqlite3.connect(scratch/'network.db')) as conn:
        conn.execute('PRAGMA journal_mode=WAL'); conn.execute('CREATE TABLE marker (value INTEGER)')
        conn.execute('INSERT INTO marker VALUES (42)'); conn.commit()
        m.write(scratch/'extraction.completed.json', {'extraction': []})
        m.previous.archive_scope_outputs(scratch,out,complete=False)
        with closing(sqlite3.connect((out/'diagnostic.db').as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
            assert db.execute('SELECT value FROM marker').fetchall() == [(42,)]
        m.seal_output(out,'build','incomplete'); m.verify_seal(out,allow_incomplete=True)
    assert not list(out.glob('*-wal')) and not list(out.glob('*-shm')) and not list(out.glob('network.db*'))


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_real_core_fake_llm_helper_batches_and_failed_build_are_auditable(prepared, tmp_path):
    driver()
    run_code(r'''
import importlib.util,json,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
s=importlib.util.spec_from_file_location('m','scripts/run_socialmem_r56_expanded.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
prepared,out=map(Path,sys.argv[1:]);checked=m.check(prepared)
runner,modules=m.frozen_modules(prepared,checked['config'],checked['identity']);core=modules[0]
llm=core.FakeLLMAdapter();llm.set_default_response('{"schema_version":2,"statements":[]}')
modules[4].embed_seeded=lambda *a,**k:dict(embedded=0,failed=0,ticks=0)
runner._make_native_adapters=lambda *_:(llm,SimpleNamespace(request_count=0),llm,llm)
m.frozen_modules=lambda *_:(runner,modules)
result=m.build(prepared,out)
assert result['state']=='incomplete' and result['healthy_scopes']==0,result
assert len(list((out/'runs').iterdir()))==1
scope=next((out/'runs').iterdir());rows=m.read(scope/'extraction.completed.json')['extraction']
assert all(r['receipt']['channels']['belief']['claim_batches_complete'] for r in rows)
assert any(len(r['receipt']['channels']['belief']['claim_batch_plan']['batches'])>1 for r in rows)
assert result['extraction_observed_requests']==0 and result['usage_complete'] is False
assert result['ledger']['reserved']==0 and result['ledger']['charged_upper']>0
assert (scope/'frozen.db').is_file() or (scope/'diagnostic.db').is_file()
assert not list(scope.glob('*-wal')) and not list(scope.glob('*-shm'))
m.check(out)
summary=m.read(out/'summary.json');summary['extraction_observed_requests']=999
m.write(out/'summary.json',summary);(out/'seal.json').unlink();m.seal_output(out,'build','incomplete')
try:m.check(out)
except ValueError:pass
else:raise AssertionError('re-sealed false HTTP accounting accepted')
''', prepared, tmp_path/'build')


def test_embedding_failure_reconciles_native_count_without_losing_upper_bound(tmp_path):
    m = driver(); ledger = m.baseline.BudgetLedger(tmp_path/'ledger.sqlite', 100)
    reserve = ledger.reserve('g', 'scope_embedding', 10)
    m.settle_failed_embedding(ledger, 'g', 3)
    assert ledger.snapshot() == dict(budget=100, committed=3, reserved=0, charged_upper=0, remaining=97)
    ledger.reserve('h', 'scope_embedding', 10)
    m.settle_failed_embedding(ledger, 'h', None)
    assert ledger.snapshot()['charged_upper'] == 10


@pytest.mark.parametrize('channel', ['belief_extract', 'belief_admission', 'general_extract', 'general_admission', 'episodic'])
@pytest.mark.parametrize('failure', ['length', 'http_failure', 'missing_raw'])
def test_all_five_native_response_kinds_fail_closed(channel, failure):
    m = driver(); rows, plans = extraction_fixture(); channels = rows[0]['receipt']['channels']
    channels['belief']['attempts'][0]['admission'] = dict(called=True, **response())
    responses = {'belief_extract': channels['belief']['attempts'][0]['extraction'],
        'belief_admission': channels['belief']['attempts'][0]['admission'],
        'general_extract': channels['general_fact']['attempts'][0]['extraction'],
        'general_admission': channels['general_fact']['attempts'][0]['admission'],
        'episodic': channels['episodic']['response']}
    bad = responses[channel]
    if failure == 'length': bad['finish_reason'] = 'length'
    elif failure == 'http_failure': bad['http_attempts'][0]['http_status'] = 503
    else: bad['http_attempts'][0].pop('response_body')
    with pytest.raises(ValueError): m.validate_batch_receipts(rows, plans)


def test_missing_admission_call_evidence_cannot_hide_possible_cost():
    m = driver(); rows, scope = extraction_fixture()
    rows[0]['receipt']['channels']['belief']['attempts'][0].pop('admission')
    with pytest.raises(ValueError): m.validate_batch_receipts(rows, scope)
    assert m.extraction_accounting(rows)['local_attempt_count_unknown'] is True


def scope_fixture(m, directory, gid='g', upper=10):
    import hashlib
    directory.mkdir(parents=True)
    rows, scope_plan = extraction_fixture()
    history = [dict(speaker='A', text='First source.', turn_id='t1', session_id='s1', observed_at=None),
               dict(speaker='A', text='Next source.', turn_id='t2', session_id='s1', observed_at=None)]
    payload = '\n'.join('@starling/source-turn-v2 ' + json.dumps(t) for t in history).encode()
    digest = hashlib.sha256(payload).hexdigest()
    plan = scope_plan['holders']['A']; plan['source_payload_hash'] = digest; plan['belief_request_upper_bound'] = upper-4
    scope_plan['extraction_request_upper_bound'] = upper
    belief = rows[0]['receipt']['channels']['belief']; belief['source_payload_hash'] = digest; belief['claim_batch_plan'] = deepcopy(plan)
    rows[0]['engram_ref'] = 'e1'; rows[0]['statement_ids'] = ['s1']
    db_path = directory/'frozen.db'
    with closing(sqlite3.connect(db_path)) as db:
        db.executescript('''CREATE TABLE statements(id TEXT,tenant_id TEXT,holder_id TEXT,semantic_claim_json TEXT);
        CREATE TABLE statement_vectors(stmt_id TEXT,tenant_id TEXT,status TEXT,dim INTEGER,index_vector BLOB);
        CREATE TABLE source_documents(tenant_id TEXT,holder_id TEXT,engram_ref TEXT);
        CREATE TABLE engrams(id TEXT,tenant_id TEXT,payload_inline BLOB,created_at TEXT);
        INSERT INTO statements VALUES('s1','default','A',NULL);
        INSERT INTO statement_vectors VALUES('s1','default','embedded',1024,zeroblob(4096));
        INSERT INTO source_documents VALUES('default','A','e1');''')
        db.execute('INSERT INTO engrams VALUES(?,?,?,?)', ('e1','default',payload,'2026-06-01T00:00:00Z')); db.commit()
    metadata = dict(group=gid, scope_state='complete', holder_failures=[],holder_complete=['A'],extraction=rows,
        database=dict(statements=1,statement_vectors=1), embedding=dict(failed=0,embedded=1,ticks=1),
        embedding_request_count=1,sources=dict(documents=1,turns=2,engram_refs=['e1']))
    return dict(group_id=gid,history=history),db_path,metadata,scope_plan


def test_database_source_turn_metadata_is_bound_to_native_plan(tmp_path):
    m=driver();group,db,metadata,plan=scope_fixture(m,tmp_path/'scope')
    m.validate_scope_health(group,db,metadata,plan)
    with closing(sqlite3.connect(db)) as conn:
        raw=conn.execute('SELECT payload_inline FROM engrams').fetchone()[0]
        conn.execute('UPDATE engrams SET payload_inline=?',(raw.replace(b's1',b's9'),));conn.commit()
    with pytest.raises(ValueError,match='SourceTurn|payload'): m.validate_scope_health(group,db,metadata,plan)


def test_success_summary_recomputes_scope_upper_bounds_and_native_usage(tmp_path):
    m=driver();out=tmp_path/'build';out.mkdir();ledger=m.baseline.BudgetLedger(out/'request-ledger.sqlite',12000)
    groups=[];plans=dict(scopes={})
    for index,upper in enumerate([100,101,102,103,104,105,106,130]):
        gid=f'g{index}';scope=out/'runs'/gid
        group,db,metadata,plan=scope_fixture(m,scope,gid,upper)
        groups.append(group);plans['scopes'][gid]=plan
        reservation=ledger.reserve(gid,'scope_extraction',upper);ledger.charge_upper(reservation['id'])
        emb=ledger.reserve(gid,'scope_embedding',7);ledger.settle(emb['id'],1)
        m.write(scope/'scope.started.json',dict(group=gid,reservation=reservation))
        m.write(scope/'scope.json',metadata);m.write(scope/'extraction.completed.json',dict(extraction=metadata['extraction']))
        m.baseline.write_extraction_receipt_archive(scope,metadata['extraction'])
        m.write(scope/'usage-and-http.json',m.extraction_accounting(metadata['extraction']))
        m.write(scope/'health.json',m.validate_scope_health(group,db,metadata,plan))
    summary=m.build_summary(out,groups,plans,'complete')
    assert summary['healthy_scopes']==8 and summary['extraction_conservative_charge']==851
    assert summary['ledger']['committed']==859 and summary['extraction_observed_requests']==40
    assert summary['extraction_observed_tokens']==480
    with closing(sqlite3.connect(ledger.path)) as conn:
        conn.execute('UPDATE reservations SET upper_bound=9 WHERE id=1');conn.commit()
    with pytest.raises(ValueError,match='reservation|charge'): m.build_summary(out,groups,plans,'complete')


def test_healthy_http_without_raw_usage_cannot_be_complete():
    m=driver();rows,scope=extraction_fixture()
    rows[0]['receipt']['channels']['episodic']['response']['http_attempts'][0]['response_body']='{}'
    with pytest.raises(ValueError,match='usage'): m.validate_batch_receipts(rows,scope)


def test_native_invalid_time_claim_preserves_full_source_turn(tmp_path):
    from starling import _core
    m=driver();group,db,metadata,scope_plan=scope_fixture(m,tmp_path/'scope')
    group['history'][0].update(text='I feel calm.',observed_at='not-a-time')
    payload=_core.claim_source_turn_payload(json.dumps(group['history']),True)
    policy=m.baseline._build_extraction_config(dict(semantic_claim_contract=True,
        preserve_text_objects=True,claim_batch_size=8,claim_protocol_retry_budget=1)).to_native_policy()
    plan=json.loads(_core.claim_extraction_batch_plan(payload,policy));scope_plan['holders']['A']=plan
    scope_plan['extraction_request_upper_bound']=7
    belief=metadata['extraction'][0]['receipt']['channels']['belief']
    belief.update(source_payload_hash=plan['source_payload_hash'],claim_batch_plan=deepcopy(plan))
    belief['attempts']=belief['attempts'][:1];belief['attempts'][0]['target_clause_ids']=['c0','c1']
    candidate=dict(holder='A',holder_perspective='FIRST_PERSON',subject='A',subject_kind='cognizer',
        predicate='feels',object='calm',modality='BELIEVES',polarity='POS',nesting_depth=0,confidence=None,
        evidence=dict(clause_id='c0',actor='A',attributed_to=None,assertion_scope='ASSERTED',
                      scope_markers=['ASSERTED'],time_text='',topic=None,event_time=None))
    parsed=json.loads(_core.claim_parse_response(json.dumps(dict(schema_version=2,statements=[candidate])),payload,'A',True))
    assert parsed['errors']==[]
    claim=parsed['statements'][0]['evidence'];claim['source_span']['engram_ref']='e1'
    belief['attempts'][0]['retained']=[deepcopy(parsed['statements'][0])]
    claim['source_time']='2026-06-01T00:00:00Z'
    assert claim['source_turn']['time_status']=='invalid' and claim['source_turn']['raw_observed_at']=='not-a-time'
    with closing(sqlite3.connect(db)) as conn:
        for name,value in dict(holder_perspective='first_person',subject_kind='cognizer',subject_id='A',predicate='feels',
                               object_value='calm',modality='believes',polarity='pos',nesting_depth=0).items():
            conn.execute('ALTER TABLE statements ADD COLUMN '+name+(' INTEGER' if name=='nesting_depth' else ' TEXT'))
            conn.execute('UPDATE statements SET '+name+'=?',(value,))
        conn.execute('UPDATE engrams SET payload_inline=?',(payload.encode(),))
        conn.execute('UPDATE statements SET semantic_claim_json=?',(json.dumps(claim),));conn.commit()
    assert m.validate_scope_health(group,db,metadata,scope_plan)['statements']==1
    claim['source_turn'].pop('raw_observed_at')
    with closing(sqlite3.connect(db)) as conn:
        conn.execute('UPDATE statements SET semantic_claim_json=?',(json.dumps(claim),));conn.commit()
    with pytest.raises(ValueError,match='SourceTurn'):m.validate_scope_health(group,db,metadata,scope_plan)


def test_terminal_batch_cannot_contain_protocol_errors():
    m=driver();rows,scope=extraction_fixture()
    rows[0]['receipt']['channels']['belief']['attempts'][0]['errors']=[{'kind':'schema_failure'}]
    with pytest.raises(ValueError):m.validate_batch_receipts(rows,scope)


def test_failure_database_snapshot_rechecks_native_source_proof(tmp_path):
    m=driver();group,db,metadata,plan=scope_fixture(m,tmp_path/'scope')
    proof=m.database_proof(db,plan)
    assert proof['statements']==1 and proof['source_documents']==1 and proof['database_sha256']==m.sha(db)
    with closing(sqlite3.connect(db)) as conn:
        conn.execute('UPDATE engrams SET payload_inline=?',(b'changed source',));conn.commit()
    with pytest.raises(ValueError,match='source|payload'):m.database_proof(db,plan)


def test_native_commit_statement_ids_must_exist_in_database(tmp_path):
    m=driver();group,db,metadata,plan=scope_fixture(m,tmp_path/'scope')
    metadata['extraction'][0]['statement_ids']=['missing-native-statement']
    with pytest.raises(ValueError,match='statement|commit'):m.validate_scope_health(group,db,metadata,plan)


def test_budget_blocked_stage_has_auditable_terminal_without_fake_scope(tmp_path):
    m=driver();out=tmp_path/'build';out.mkdir();ledger=m.baseline.BudgetLedger(out/'request-ledger.sqlite',12000)
    m.write(out/'build.failure.json',dict(category='budget_blocked',group='g',upper_bound=12001,remaining=12000))
    summary=m.build_summary(out,[dict(group_id='g')],dict(scopes={'g':dict(extraction_request_upper_bound=12001)}),'incomplete')
    assert summary['unexecuted_scopes']==['g'] and summary['healthy_scopes']==0
    assert summary['ledger']['committed']==0 and summary['extraction_observed_requests']==0
    assert summary['build_failure']['category']=='budget_blocked'


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_real_native_helper_persists_multibatch_claims_matching_receipt(prepared,tmp_path):
    driver()
    run_code(r'''
import importlib.util,json,sys
from pathlib import Path
from types import SimpleNamespace
s=importlib.util.spec_from_file_location('m','scripts/run_socialmem_r56_expanded.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
prepared,scratch=map(Path,sys.argv[1:]);scratch.mkdir();checked=m.check(prepared)
runner,modules=m.frozen_modules(prepared,checked['config'],checked['identity']);core,runtime=modules[:2]
config=checked['config'];policy=runner._build_extraction_config(config).to_native_policy()
history=[dict(speaker='A',text=f'I feel calm number {i}.',turn_id=f't{i}',observed_at='2026-01-01T00:00:00Z') for i in range(9)]
group=dict(group_id='g',history=history);plans=m.native_plans(runner,modules,[group],config)['scopes']['g']
payload=core.claim_source_turn_payload(json.dumps(history),True)
llm=core.FakeLLMAdapter();llm.set_default_response('{"schema_version":2,"statements":[]}')
rt=runtime._build_local_store_sqlite_runtime(scratch/'discovery.db');rt.start()
empty=core.memory_extract_llm(rt.adapter,llm,'','A',payload.encode(),policy)
receipt=json.loads(core.claim_extraction_receipt(empty));assert len(receipt['attempts'])==2
for clause in (0,8):
    candidate=dict(holder='A',holder_perspective='FIRST_PERSON',subject='A',subject_kind='cognizer',
        predicate='feels',object=f'calm number {clause}',modality='BELIEVES',polarity='POS',nesting_depth=0,
        confidence=None,evidence=dict(clause_id=f'c{clause}',actor='A',attributed_to=None,
        assertion_scope='ASSERTED',scope_markers=['ASSERTED'],time_text='',topic=None,event_time=None))
    raw=json.dumps(dict(schema_version=2,statements=[candidate]))
    parsed=json.loads(core.claim_parse_response(raw,payload,'A',True));assert parsed['errors']==[]
    target=next(a for a in receipt['attempts'] if f'c{clause}' in a['target_clause_ids'])
    llm.set_response(target['extraction']['prompt_input_hash'],raw)
    prompt=core.claim_admission_prompt(payload,json.dumps(dict(schema_version=2,statements=parsed['statements'])))
    llm.set_response(core.Extractor.compute_prompt_input_hash(prompt),
        '{"schema_version":1,"decisions":[{"index":0,"retain":true,"reason":"supported"}]}')
modules[4].embed_seeded=lambda *a,**k:dict(embedded=0,failed=0,ticks=0)
scope=scratch/'scope';scope.mkdir();ledger=runner.BudgetLedger(scratch/'ledger.sqlite',100)
reservation=ledger.reserve('g','scope_extraction',10)
database,metadata=runner._build_scope_database(group,scope,modules,config,
    (llm,SimpleNamespace(request_count=0),llm,llm),ledger,reservation)
assert len(metadata['extraction'][0]['statement_ids'])==2,metadata
proof=m.database_proof(database,plans,metadata['extraction'])
assert proof['statements']==2 and proof['source_documents']==1,proof
assert metadata['extraction'][0]['receipt']['channels']['belief']['claim_batches_complete'] is True
''', prepared,tmp_path/'native')


def test_provider_construction_failure_is_known_zero_before_native_entry():
    m=driver();usage=m.extraction_accounting(None,native_invoked=False)
    assert usage['observed_native_requests']==0 and usage['observed_tokens']==0
    assert usage['local_attempt_count_unknown'] is False and usage['remote_execution_unknown'] is False
    assert usage['usage_complete'] is True


def test_failed_belief_allows_independent_native_legacy_channel_commit(tmp_path):
    m=driver();group,db,metadata,plan=scope_fixture(m,tmp_path/'scope')
    metadata['extraction'][0]['extraction_failed']=True
    metadata['extraction'][0]['receipt']['channels']['belief']['claim_batches_complete']=False
    proof=m.database_proof(db,plan,metadata['extraction'])
    assert proof['statements']==1
