"""R56 host orchestration: sealed source, native batches, bounded calls and commit audit."""
from contextlib import closing
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/run_socialmem_r56_kwame_probe.py'


def driver():
    assert SCRIPT.is_file(), 'independent native R56 Kwame probe is required'
    spec = importlib.util.spec_from_file_location('r56_probe_test', SCRIPT)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def response(contract='claim_extraction_v2'):
    body = '{"usage":{"prompt_tokens":100,"completion_tokens":20,"total_tokens":120}}'
    return dict(ok=True, error='', finish_reason='stop', refusal=False, attempt_count=1,
        prompt='native generated prompt', prompt_input_hash=digest('native generated prompt'),
        output_contract=contract, output_mode='json_object', raw_completion='native output',
        raw_response='native output', raw_http_response=body,
        prompt_tokens=100, completion_tokens=20, total_tokens=120,
        http_attempts=[dict(attempt=1, http_status=200, curl_code=0, execution_certainty='response_received',
                            response_body=body)])


@pytest.fixture
def rig(tmp_path, monkeypatch):
    m = driver(); repo = tmp_path / 'repo'; parent = tmp_path / 'parent'; parent.mkdir()
    for relative in ('scripts/run_socialmem_r56_kwame_probe.py', 'scripts/run_socialmem_baseline.py',
                     'tests/python/test_socialmem_r56_kwame_probe.py'):
        target = repo / relative; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    native = repo / 'build/python/starling/_core.fixture.so'; native.parent.mkdir(parents=True)
    native.write_bytes(b'new frozen native batch core')
    runtime_py = repo / 'python/starling/runtime.py'; runtime_py.parent.mkdir(parents=True)
    runtime_py.write_text('# frozen runtime fixture\n')
    (runtime_py.parent / '__init__.py').write_text('# frozen package\n')
    source = repo / 'src/extractor.cpp'; source.parent.mkdir(); source.write_text('// source fixture\n')
    monkeypatch.setattr(m, 'ROOT', repo)
    payload = '\n'.join(f'Kwame: source unit {i}' for i in range(33))
    prompt = 'original unbatched prompt\n'
    monkeypatch.setattr(m, 'PAYLOAD_SHA256', digest(payload)); monkeypatch.setattr(m, 'PAYLOAD_BYTES', len(payload.encode()))
    monkeypatch.setattr(m, 'PROMPT_SHA256', digest(prompt))
    (parent / 'source-payload.txt').write_text(payload); (parent / 'prompt.txt').write_text(prompt)
    (parent / 'inputs').mkdir()
    with closing(sqlite3.connect(parent / 'inputs/source.db')) as db:
        db.executescript('CREATE TABLE source_documents (tenant_id TEXT,holder_id TEXT,engram_ref TEXT);'
                        'CREATE TABLE engrams (id TEXT,tenant_id TEXT,payload_inline BLOB);')
        db.execute('INSERT INTO source_documents VALUES (?,?,?)', ('default', 'Kwame', 'old-engram'))
        db.execute('INSERT INTO engrams VALUES (?,?,?)', ('old-engram', 'default', payload.encode())); db.commit()
    original = dict(core_sha256='old-native-core', extract_model='qwen3.8-27b', extract_provider='dashscope',
        extract_endpoint='https://example.invalid/v1', extract_enable_thinking=False, extract_max_tokens=8192,
        timeout_ms=120000, max_retries=0, semantic_claim_contract=True, preserve_text_objects=True,
        claim_allow_code_fence=True, claim_protocol_retry_budget=1, claim_output_mode='json_object',
        created_at='2026-06-01T00:00:00Z')
    m.write(parent / 'original-config.json', original)
    m.write(parent / 'binding.json', dict(scope=m.SCOPE, holder='Kwame', tenant_id='default', engram_ref='old-engram',
        payload_sha256=digest(payload), payload_bytes=len(payload.encode()), prompt_sha256=digest(prompt),
        database_sha256=m.sha(parent / 'inputs/source.db')))
    m.write(parent / 'inputs/failed-scope.json', dict(group=m.SCOPE, extraction=[dict(holder='Kwame',
        engram_ref='old-engram', receipt={'channels': {'belief': dict(source_payload_hash=digest(payload),
        prompt=prompt, prompt_input_hash=digest(prompt))}})]))
    m.write(parent / 'seal.json', dict(schema='r55-capacity-seal-v1', state='complete', files=m.inventory(parent)))
    monkeypatch.setattr(m, 'PARENT_SEAL_SHA256', m.sha(parent / 'seal.json'))
    monkeypatch.setattr(m, 'PARENT_FILE_COUNT', len(m.read(parent / 'seal.json')['files']))
    units = [dict(clause_id=f'c{i}', byte_start=i, byte_end=i+1, payload_hash=digest(payload)) for i in range(33)]
    batches = [dict(batch_index=i, target_clause_ids=[f'c{j}' for j in range(i*8,min(i*8+8,33))]) for i in range(5)]
    plan = dict(claim_batch_size=8, claim_protocol_retry_budget=1, source_payload_hash=digest(payload),
                source_units=units, batches=batches, belief_request_upper_bound=15)
    receipt = dict(holder='Kwame', semantic_claim_contract=True, source_payload_hash=digest(payload),
        claim_batch_size=8, claim_batch_plan=plan, claim_batches_complete=True,
        failure_category='', failure_detail='', persistence_error='', accepted_by_predicate={'feels': 1},
        rejected_by_predicate={}, attempts=[])
    for batch in batches:
        receipt['attempts'].append(dict(attempt=batch['batch_index']+1, terminal=True,
            batch_index=batch['batch_index'], target_clause_ids=batch['target_clause_ids'],
            errors=[], semantic_rejections=[], semantic_rejected=0, retained=[], extraction=response(),
            admission=dict(called=False, attempt_count=0, http_attempts=[], semantic_rejected=0)))
    receipt['attempts'][0]['admission'] = dict(response('claim_admission_v1'), called=True, semantic_rejected=0)
    c = SimpleNamespace(m=m, repo=repo, parent=parent, native=native, source=source, payload=payload, prompt=prompt,
        prepared=tmp_path/'prepared', out=tmp_path/'run', plan=plan, receipt=receipt,
        calls=[], constructions=[], commits=[], error=None, bad_commit=False, bad_proof=False, before_extract=None)
    class Runtime:
        def __init__(self, path):
            self.adapter = path
            with closing(sqlite3.connect(path)) as db:
                db.executescript('CREATE TABLE engrams (id TEXT,tenant_id TEXT,payload_inline BLOB);'
                    'CREATE TABLE statements (id TEXT,tenant_id TEXT,holder_id TEXT,semantic_claim_json TEXT);'
                    'CREATE TABLE extraction_attempt (id TEXT);'); db.commit()
        def start(self): pass
    def remember_prepare(adapter, **kwargs):
        assert kwargs['holder_id']=='Kwame' and kwargs['payload']==payload.encode()
        with closing(sqlite3.connect(adapter)) as db:
            db.execute('INSERT INTO engrams VALUES (?,?,?)', ('new-engram', 'default', kwargs['payload'])); db.commit()
        return SimpleNamespace(engram_ref='new-engram', should_extract=True, outcome='stored',
                               created_at_iso8601=kwargs['created_at_iso8601'])
    def extract(adapter, llm, prompt_template, holder_id, source_payload, policy):
        c.calls.append((holder_id, source_payload, policy.claim_batch_size, policy.claim_protocol_retry_budget))
        if c.before_extract: c.before_extract()
        if c.error: raise c.error
        return object()
    def commit(adapter, llm, **kwargs):
        c.commits.append(kwargs)
        failed = not c.receipt['claim_batches_complete']
        ids = [] if failed else ['statement-1']
        with closing(sqlite3.connect(adapter)) as db:
            db.execute('INSERT INTO extraction_attempt VALUES (?)', ('audit',))
            if ids:
                proof = dict(clause_id='c0', source_span=dict(engram_ref='new-engram', span_start=0,
                             span_end=1, source_hash='wrong' if c.bad_proof else digest(payload)))
                db.execute('INSERT INTO statements VALUES (?,?,?,?)', (ids[0], 'default', 'Kwame', json.dumps(proof)))
            db.commit()
        return dict(engram_ref='new-engram', statement_ids=['wrong-id'] if c.bad_commit else ids,
            extraction_failed=failed, source_preserved=True, structured_claims_persisted=bool(ids),
            failure_category='transport_failure' if failed else '', failure_detail='', outcome='stored')
    core = SimpleNamespace(ValidationPolicy=SimpleNamespace,
        OutputMode=SimpleNamespace(JsonObject=object()),
        claim_extraction_prompt=lambda *args: prompt, claim_extraction_batch_plan=lambda *args: json.dumps(c.plan),
        memory_remember_prepare=remember_prepare, memory_extract_llm=extract, memory_remember_commit=commit,
        claim_extraction_receipt=lambda result: json.dumps(c.receipt),
        OpenAIAdapterConfig=SimpleNamespace(from_env=lambda: SimpleNamespace()))
    def construct(config): c.constructions.append(config); return object()
    core.OpenAIAdapter=construct
    def frozen(out, identity):
        core.__file__=str(next((out/'frozen/python/starling').glob('_core*.so')))
        return core, SimpleNamespace(_build_local_store_sqlite_runtime=Runtime)
    monkeypatch.setattr(m, 'load_frozen', frozen)
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'offline-fixture')
    c.core=core
    return c


def test_prepare_and_check_are_offline_and_freeze_new_native_core(rig):
    c=rig; summary=c.m.prepare(c.parent,c.prepared)
    assert summary['external_requests']==0 and summary['belief_request_upper_bound']==15
    checked=c.m.check(c.prepared)
    assert checked['plan']['batches'][-1]['target_clause_ids']==['c32']
    assert checked['config']['core_sha256']==c.m.sha(c.native)
    assert c.m.sha(c.prepared/'inputs/source-payload.txt')==digest(c.payload)
    assert c.calls==c.constructions==[]


@pytest.mark.parametrize('what',['parent_seal','parent_file','payload','holder','prompt','core','config','plan','source'])
def test_input_or_frozen_drift_is_rejected_before_provider(rig,what):
    c=rig
    if what.startswith('parent'):
        if what=='parent_seal': c.m.PARENT_SEAL_SHA256='0'*64
        else: (c.parent/'unexpected').write_text('drift')
        with pytest.raises(ValueError): c.m.prepare(c.parent,c.prepared)
    else:
        c.m.prepare(c.parent,c.prepared)
        if what=='payload': (c.prepared/'inputs/source-payload.txt').write_text('drift')
        elif what=='holder':
            binding=c.m.read(c.prepared/'binding.json'); binding['holder']='Other'; c.m.write(c.prepared/'binding.json',binding)
        elif what=='prompt': (c.prepared/'inputs/original-prompt.txt').write_text('drift')
        elif what=='core': c.native.write_bytes(b'changed core')
        elif what=='config':
            config=c.m.read(c.prepared/'config.json');config['claim_batch_size']=16;c.m.write(c.prepared/'config.json',config)
        elif what=='plan':
            c.plan['belief_request_upper_bound']=18
        else: c.source.write_text('// changed source\n')
        with pytest.raises(ValueError): c.m.run(c.prepared,c.out)
    assert c.calls==c.constructions==[]


@pytest.mark.parametrize('stage',['prepare','run'])
def test_existing_output_is_refused_before_input_reads(rig,stage):
    rig.out.mkdir()
    with pytest.raises(ValueError,match='already exists'):
        getattr(rig.m,stage)(Path('/absent'),rig.out)
    assert rig.calls==rig.constructions==[]


def test_native_belief_only_run_commits_snapshot_and_settles_observed_six_requests(rig):
    c=rig;c.m.prepare(c.parent,c.prepared);result=c.m.run(c.prepared,c.out)
    assert result['status']=='kwame_probe_passed'
    assert len(c.calls)==len(c.commits)==len(c.constructions)==1
    config,=c.constructions
    assert (config.max_tokens,config.timeout_ms,config.enable_thinking,config.max_retries)==(8192,120000,False,0)
    assert c.calls[0]==('Kwame',c.payload.encode(),8,1)
    assert result['ledger']==dict(budget=15,committed=6,remaining=9,reserved=0,charged_upper=0)
    assert result['accounting']['observed_local_http_attempts']==6
    assert result['accounting']['observed_total_tokens']==720
    assert result['accounting']['usage_complete'] is True
    assert result['database']['statement_ids']==['statement-1']
    assert c.m.read(c.out/'native-receipt.json')==c.receipt
    assert not (c.out/'live.db').exists() and not Path(str(c.out/'frozen.db')+'-wal').exists()
    assert c.m.check(c.out)['summary']['status']=='kwame_probe_passed'


def test_later_batch_transport_failure_commits_failure_audit_and_zero_claims(rig):
    c=rig;c.receipt['claim_batches_complete']=False
    c.receipt['failure_category']='transport_failure';c.receipt['attempts']=c.receipt['attempts'][:3]
    bad=c.receipt['attempts'][-1];bad['terminal']=False
    bad['extraction'].update(ok=False,error='curl56',finish_reason='',prompt_tokens=0,completion_tokens=0,total_tokens=0)
    bad['extraction']['http_attempts'][0].update(http_status=0,curl_code=56,execution_certainty='unknown',response_body='')
    c.m.prepare(c.parent,c.prepared);result=c.m.run(c.prepared,c.out)
    assert result['status']=='technical_failure' and len(c.commits)==1
    assert result['database']['statement_ids']==[] and result['database']['extraction_attempt_count']==1
    assert result['accounting']['observed_local_http_attempts']==4
    assert result['accounting']['remote_execution_unknown_attempts']==1
    assert result['accounting']['usage_complete'] is False
    assert result['accounting']['observed_total_tokens']==360
    assert result['ledger']['committed']==4 and result['ledger']['charged_upper']==0
    assert c.m.read(c.out/'native-receipt.json')==c.receipt


@pytest.mark.parametrize('what',['exception','missing_http','bad_commit','bad_proof','post_input_drift','post_config_drift'])
def test_failed_terminal_preserves_evidence_and_never_repeats_native_entry(rig,what):
    c=rig;c.m.prepare(c.parent,c.prepared)
    if what=='exception': c.error=RuntimeError('native call outcome unknown')
    elif what=='missing_http': c.receipt['attempts'][0]['extraction'].pop('http_attempts')
    elif what=='bad_commit': c.bad_commit=True
    elif what=='bad_proof': c.bad_proof=True
    elif what=='post_input_drift': c.before_extract=lambda: c.source.write_text('drift')
    else: c.before_extract=lambda: (c.out/'config.json').write_text('{}')
    result=c.m.run(c.prepared,c.out)
    assert result['status']=='technical_failure' and result['terminal'] is True and len(c.calls)==1
    if what in ('exception','missing_http'):
        assert result['ledger']['charged_upper']==15 and result['accounting']['local_attempt_count_unknown'] is True
    if what=='exception':
        assert c.commits==[] and result['accounting']['observed_local_http_attempts']==0
    else: assert c.m.read(c.out/'native-receipt.json')==c.receipt
    assert (c.out/'seal.json').exists()


def test_corrected_protocol_errors_remain_separate_from_successful_terminal(rig):
    c=rig
    correction=deepcopy(c.receipt['attempts'][0]);correction.update(terminal=False,errors=[{'kind':'schema_failure'}])
    correction['admission']=dict(called=False,attempt_count=0,http_attempts=[],semantic_rejected=0)
    c.receipt['attempts'].insert(0,correction)
    for i,attempt in enumerate(c.receipt['attempts'],1):attempt['attempt']=i
    c.m.prepare(c.parent,c.prepared);result=c.m.run(c.prepared,c.out)
    assert result['status']=='kwame_probe_passed'
    assert result['protocol_error_attempts']==1 and result['accounting']['observed_local_http_attempts']==7


def test_native_plan_and_default_prompt_are_required_before_freezing(rig):
    rig.core.claim_extraction_prompt=lambda *args:'changed default prompt'
    with pytest.raises(ValueError,match='prompt'):rig.m.prepare(rig.parent,rig.prepared)
    assert rig.calls==rig.constructions==[]


def test_policy_passes_native_output_enum_instead_of_config_wire_name(rig):
    config={**rig.m.read(rig.parent/'original-config.json'),'claim_batch_size':8}
    assert rig.m.make_policy(rig.core,config).claim_output_mode is rig.core.OutputMode.JsonObject


def test_nonfatal_semantic_rejection_category_does_not_hide_healthy_persisted_claims(rig):
    rig.receipt['failure_category']='semantic_rejection'
    rig.receipt['failure_detail']='one rejected candidate retained as diagnostic'
    rig.receipt['attempts'][0]['semantic_rejections']=[{'kind':'scope_failure'}]
    rig.m.prepare(rig.parent,rig.prepared)
    result=rig.m.run(rig.prepared,rig.out)
    assert result['status']=='kwame_probe_passed' and result['semantic_rejections']==1


def test_contradictory_admission_called_flag_does_not_erase_observed_http(rig):
    rig.receipt['attempts'][0]['admission']['called']=False
    report=rig.m.receipt_accounting(rig.receipt)
    assert report['observed_local_http_attempts']==6
    assert report['local_attempt_count_unknown'] is True and not report['healthy_http']


def test_failure_before_native_entry_is_known_zero_spend(rig):
    c=rig;c.m.prepare(c.parent,c.prepared)
    def unavailable(*args): raise RuntimeError('provider config unavailable before native entry')
    c.m.make_extract_adapter=unavailable
    result=c.m.run(c.prepared,c.out)
    assert result['status']=='technical_failure' and c.calls==[]
    assert result['ledger']['committed']==0
    assert result['accounting']['local_attempt_count_unknown'] is False
    assert result['accounting']['remote_execution_unknown'] is False


@pytest.mark.parametrize('what',['success_ledger','failure_ledger','reserved','unknown_unpaid','failed_usage','false_revalidation'])
def test_resealed_cost_or_terminal_claims_cannot_bypass_native_receipts(rig,what):
    c=rig
    if what in ('failure_ledger','failed_usage'):
        c.receipt['claim_batches_complete']=False;c.receipt['failure_category']='transport_failure'
    elif what=='unknown_unpaid':c.error=RuntimeError('unknown native outcome')
    c.m.prepare(c.parent,c.prepared);c.m.run(c.prepared,c.out)
    terminal=c.m.read(c.out/'terminal.json')
    if what in ('success_ledger','failure_ledger','unknown_unpaid'):
        with closing(sqlite3.connect(c.out/'request-ledger.sqlite')) as db:
            db.execute("UPDATE reservations SET actual=0,state='settled'");db.commit()
        terminal['ledger']=dict(budget=15,committed=0,remaining=15,reserved=0,charged_upper=0)
    elif what=='reserved':
        with closing(sqlite3.connect(c.out/'request-ledger.sqlite')) as db:
            db.execute("UPDATE reservations SET actual=NULL,state='reserved'");db.commit()
        terminal['ledger']=dict(budget=15,committed=0,remaining=0,reserved=15,charged_upper=0)
    elif what=='failed_usage':terminal['accounting']['observed_total_tokens']=0
    else:terminal['input_revalidation_ok']=False
    c.m.write(c.out/'terminal.json',terminal);c.m.write(c.out/'summary.json',terminal)
    (c.out/'seal.json').unlink();c.m.seal(c.out,'run')
    with pytest.raises(ValueError):c.m.check(c.out)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_real_frozen_native_batches_commit_original_kwame_source_with_fake_llm():
    driver()
    code = r'''
import importlib.util,json,tempfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('probe',Path('scripts/run_socialmem_r56_kwame_probe.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory(prefix='r56-native-fixture-') as scratch:
    scratch=Path(scratch); prepared=scratch/'prepare'; out=scratch/'run'
    summary=m.prepare(m.DEFAULT_PARENT,prepared)
    checked=m.check(prepared); core,runtime=checked['core'],checked['runtime']
    assert summary['belief_request_upper_bound']==15 and len(checked['plan']['batches'])==5
    assert checked['identity']['core_sha256']!=m.read(m.DEFAULT_PARENT/'original-config.json')['core_sha256']
    source=checked['payload'];policy=m.make_policy(core,checked['config'])
    fake=core.FakeLLMAdapter();fake.set_default_response('{"schema_version":2,"statements":[]}')
    rt=runtime._build_local_store_sqlite_runtime(scratch/'discovery.db');rt.start()
    empty=core.memory_extract_llm(rt.adapter,fake,'','Kwame',source.encode(),policy)
    receipt=json.loads(core.claim_extraction_receipt(empty))
    assert receipt['claim_batches_complete'] is True and len(receipt['attempts'])==5
    row=dict(holder='Kwame',holder_perspective='FIRST_PERSON',subject='Kwame',subject_kind='cognizer',
        predicate='feels',object='proud of having my waterproofs',modality='BELIEVES',polarity='POS',
        nesting_depth=0,confidence=None,evidence=dict(clause_id='c24',actor='Kwame',attributed_to=None,
        assertion_scope='ASSERTED',scope_markers=['ASSERTED'],time_text='',topic=None,event_time=None))
    raw=json.dumps(dict(schema_version=2,statements=[row]))
    parsed=json.loads(core.claim_parse_response(raw,source,'Kwame',True))
    assert parsed['errors']==[] and len(parsed['statements'])==1
    target=next(a for a in receipt['attempts'] if 'c24' in a['target_clause_ids'])
    fake.set_response(target['extraction']['prompt_input_hash'],raw)
    admission=core.claim_admission_prompt(source,json.dumps(dict(schema_version=2,statements=parsed['statements'])))
    fake.set_response(core.Extractor.compute_prompt_input_hash(admission),
        '{"schema_version":1,"decisions":[{"index":0,"retain":true,"reason":"supported"}]}')
    m.make_extract_adapter=lambda core,config:fake
    result=m.run(prepared,out)
    actual=m.read(out/'native-receipt.json');commit=m.read(out/'commit.json')
    assert actual['claim_batches_complete'] is True, result
    assert commit['extraction_failed'] is False and len(commit['statement_ids'])==1, commit
    assert result['database']['statement_ids']==commit['statement_ids'],result
    assert result['accounting']['observed_local_http_attempts']==0
    assert result['status']=='technical_failure'  # FakeLLM has no live HTTP/usage evidence.
    assert result['input_revalidation_ok'] is True
    m.check(out)
    last=receipt['attempts'][-1]
    fake.set_response(last['extraction']['prompt_input_hash'],'',False,'late native transport failure')
    failed=m.run(prepared,scratch/'late-failure')
    failed_commit=m.read(scratch/'late-failure/commit.json')
    assert failed_commit['extraction_failed'] is True and failed_commit['statement_ids']==[],failed_commit
    assert failed['database']['statement_count']==0 and failed['database']['extraction_attempt_count']>=1,failed
    assert failed['status']=='technical_failure'
    assert m.read(scratch/'late-failure/native-receipt.json')['claim_batches_complete'] is False
    m.check(scratch/'late-failure')
    print(json.dumps(dict(native_batches=len(actual['claim_batch_plan']['batches']),
        native_complete=actual['claim_batches_complete'],claims=result['database']['statement_count'],
        late_failure_claims=failed['database']['statement_count'],external_requests=0,
        core_sha256=checked['identity']['core_sha256']),sort_keys=True))
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout, end='')
