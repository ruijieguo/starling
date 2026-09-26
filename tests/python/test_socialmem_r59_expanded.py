"""R5.9 fixed-core eight-scope orchestration; offline fixtures only."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/run_socialmem_r59_expanded.py'


def driver():
    assert SCRIPT.is_file(), 'independent R5.9 expanded entry is required'
    spec = importlib.util.spec_from_file_location('r59_test_driver', SCRIPT)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def run_code(code, *args):
    driver()
    setup = """
import importlib.util,json,sys,tempfile,sqlite3
from pathlib import Path
s=importlib.util.spec_from_file_location('r59','scripts/run_socialmem_r59_expanded.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
"""
    result = subprocess.run([sys.executable, '-c', setup + code, *map(str, args)],
                            cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('stage', ['prepare', 'build'])
def test_existing_output_refused_before_inputs(tmp_path, stage):
    m = driver(); out = tmp_path / 'existing'; out.mkdir()
    with pytest.raises(ValueError, match='already exists'):
        getattr(m, stage)(tmp_path / 'missing', out)


def test_historical_cohort_identity_is_distinct_from_candidate_core():
    m = driver(); value = m.historical_inputs(m.DEFAULT_PARENT)
    assert len(value['records']) == 133 and len(value['groups']) == 8
    assert value['config']['core_sha256'] == 'ead8046e4a28d257f3429d865523c1af1f6275fd0cb1ba98d8fa8023894d6fef'
    assert value['config']['claim_batch_target_units'] is True
    assert value['config']['claim_batch_size'] == 8
    assert value['parent_config']['core_sha256'] != value['config']['core_sha256']


@pytest.mark.parametrize('input_kind', ['parent', 'probe'])
def test_historical_or_success_probe_seal_drift_rejected(tmp_path, input_kind):
    m = driver(); path = tmp_path / 'bad'; path.mkdir(); m.write(path / 'seal.json', {})
    with pytest.raises(ValueError, match='seal'):
        m.historical_inputs(path) if input_kind == 'parent' else m.qualify_probe(path)


def test_wrong_current_core_rejected_before_prepare_output(tmp_path, monkeypatch):
    m = driver(); monkeypatch.setattr(m, 'CORE_SHA256', '0' * 64)
    with pytest.raises(ValueError, match='core'):
        m.prepare(m.DEFAULT_PARENT, tmp_path / 'prepare')
    assert not (tmp_path / 'prepare').exists()


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    out = tmp_path_factory.mktemp('r59') / 'prepare'
    run_code("m.prepare(m.DEFAULT_PARENT,Path(sys.argv[1]));m.check(Path(sys.argv[1]))\n", out)
    return out


def test_current_core_full_cohort_native_plans_and_qualification(prepared):
    m = driver(); plans = m.read(prepared / 'batch-plans.json')
    assert {k: plans[k] for k in ('holder_count', 'source_units', 'batches', 'belief_request_upper_bound',
                                  'extraction_request_upper_bound')} == dict(holder_count=65, source_units=1322,
                                  batches=197, belief_request_upper_bound=591, extraction_request_upper_bound=851)
    assert all(p['claim_batch_prompt_profile'] == 'target_units_v1'
               for scope in plans['scopes'].values() for p in scope['holders'].values())
    qualification = m.read(prepared / 'qualification.json')
    assert qualification['returncode'] == 0 and qualification['summary']['candidate_passed'] is True
    assert len(qualification['checker_files']) >= 3 and qualification['stdout_sha256']
    assert m.read(prepared / 'summary.json')['external_requests'] == 0
    for name in ('scripts/run_socialmem_r59_expanded.py', 'scripts/run_socialmem_r58_paired_probe.py',
                 'scripts/run_socialmem_r56_expanded.py', 'scripts/run_socialmem_baseline.py'):
        assert (prepared / 'source' / name).is_file()


@pytest.mark.parametrize('tamper', ['true_string', 'false', 'core', 'profile', 'source', 'summary', 'groups'])
def test_resealed_prepare_drift_is_rejected(prepared, tmp_path, tamper):
    m = driver(); target = tmp_path / 'prepare'; shutil.copytree(prepared, target)
    if tamper in ('true_string', 'false'):
        value = m.read(target / 'config.json'); value['claim_batch_target_units'] = 'true' if tamper == 'true_string' else False
        m.write(target / 'config.json', value)
    elif tamper == 'core': next((target / 'frozen/python/starling').glob('_core*.so')).write_bytes(b'bad core')
    elif tamper == 'profile':
        value = m.read(target / 'batch-plans.json')
        next(iter(next(iter(value['scopes'].values()))['holders'].values())).pop('claim_batch_prompt_profile')
        m.write(target / 'batch-plans.json', value)
    elif tamper == 'source': (target / 'source/scripts/run_socialmem_r59_expanded.py').write_text('forged')
    elif tamper == 'groups':
        value = m.read(target / 'groups.json'); value.pop(); m.write(target / 'groups.json', value)
    else: m.write(target / 'summary.json', {'state': 'complete', 'external_requests': 0})
    (target / 'seal.json').unlink(); m.seal_output(target, 'prepare')
    run_code("""
try:m.check(Path(sys.argv[1]))
except (ValueError,RuntimeError):pass
else:raise AssertionError('resealed prepare forgery accepted')
""", target)


def test_read_only_check_does_not_need_current_source_match(prepared):
    run_code("""
prepared=Path(sys.argv[1]);before=m.inventory(prepared)
m.current_source_files=lambda: {'changed': 'source'}
assert m.check(prepared)['summary']['state']=='complete'
assert before==m.inventory(prepared)
try:m.check(prepared,require_current=True)
except ValueError:pass
else:raise AssertionError('live source mismatch accepted for build')
""", prepared)


def test_second_frozen_runtime_root_is_rejected(prepared,tmp_path):
    target = tmp_path / 'copy'; shutil.copytree(prepared,target)
    run_code("""
m.check(Path(sys.argv[1]))
try:m.check(Path(sys.argv[2]))
except (ValueError,RuntimeError):pass
else:raise AssertionError('loaded a second frozen runtime root')
""",prepared,target)


NATIVE_SETUP = r'''
import threading,os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
checked=m.check(Path(sys.argv[1]));runner=checked['runner'];modules=checked['modules'];core,runtime=modules[:2]
root=Path(sys.argv[2]);root.mkdir()
history=[dict(speaker='A',text=f'I feel calm number {i}. Water boils at 100 C.',turn_id=f't{i}',
 observed_at='2026-01-01T00:00:00Z') for i in range(9)]
history.append(dict(speaker='B',text='I am here.',turn_id='b',observed_at=None))
group=dict(group_id='fixture',history=history)
plans=m.native_plans(runner,modules,[group],checked['config'])
checked=dict(checked,groups=[group],plans=plans)
policy=runner._build_extraction_config(checked['config']).to_native_policy()
prompts={};kinds={};episodic_prompts={};mode='success';calls=[]
def claim(clause):
 return dict(holder='A',holder_perspective='FIRST_PERSON',subject='A',subject_kind='cognizer',predicate='feels',
  object=f'calm number {clause}',modality='BELIEVES',polarity='POS',nesting_depth=0,confidence=None,
  evidence=dict(clause_id=f'c{clause}',actor='A',attributed_to=None,assertion_scope='ASSERTED',
   scope_markers=['ASSERTED'],time_text='',topic=None,event_time=None))
for holder in ('A','B'):
 turns=[dict(speaker=t['speaker'],text=t['text'],session_id=None,turn_id=t['turn_id'],turn_index=None,
  observed_at=t['observed_at']) for t in history if t['speaker']==holder]
 payload=core.claim_source_turn_payload(json.dumps(turns),True)
 rt=runtime._build_local_store_sqlite_runtime(root/(holder+'-discovery.db'));rt.start()
 fake=core.FakeLLMAdapter();fake.set_default_response('{"schema_version":2,"statements":[]}')
 cfg=runner._build_extraction_config(checked['config'])
 bundle=core.memory_remember_extract_all(rt.adapter,fake,cfg.belief_prompt,cfg.episodic_prompt,
  cfg.general_fact_prompt,holder,payload.encode(),policy=policy)
 receipt=json.loads(core.memory_remember_bundle_receipt(bundle))
 episodic_prompts[holder]=receipt['channels']['episodic']['prompt_input_hash']
 for attempt in receipt['channels']['belief']['attempts']:
  clause=0 if attempt['batch_index']==0 else 8
  raw=json.dumps(dict(schema_version=2,statements=[claim(clause)] if holder=='A' else []))
  digest=attempt['extraction']['prompt_input_hash'];prompts[digest]=raw;kinds[digest]=holder+str(clause)
  if holder=='A':
   parsed=json.loads(core.claim_parse_response(raw,payload,holder,True));assert parsed['errors']==[]
   prompt=core.claim_admission_prompt(payload,json.dumps(dict(schema_version=2,statements=parsed['statements'])))
   digest=core.Extractor.compute_prompt_input_hash(prompt)
   prompts[digest]='{"schema_version":1,"decisions":[{"index":0,"retain":true,"reason":"supported"}]}'
   kinds[digest]='admission'
 if holder=='A':
  response=receipt['channels']['general_fact']['attempts'][0]['extraction']
  prompts[response['prompt_input_hash']]=json.dumps([dict(holder='A',holder_perspective='FIRST_PERSON',
   subject='water',subject_kind='entity',predicate='has_value',object='boiling point 100 C',
   modality='BELIEVES',polarity='POS',nesting_depth=0)])
 del rt
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  request=json.loads(self.rfile.read(int(self.headers['Content-Length'])));calls.append(request)
  digest=core.Extractor.compute_prompt_input_hash(request['messages'][-1]['content'])
  text=prompts.get(digest,'[]');kind=kinds.get(digest,'legacy')
  if mode=='late_scope' and kind=='A8':text=json.dumps(dict(schema_version=2,statements=[claim(0)]))
  if mode=='admission_failure' and kind=='admission':text='{}'
  body=dict(choices=[dict(message=dict(content=text,refusal=None),finish_reason='length' if mode=='truncated' and kind=='A8' else 'stop')],
   usage=dict(prompt_tokens=10,completion_tokens=2,total_tokens=12))
  if mode=='missing_usage' and kind=='A8':body.pop('usage')
  raw=json.dumps(body).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)))
  self.end_headers();self.wfile.write(raw)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
class CountedStub(core.StubEmbeddingAdapter):
 @property
 def request_count(self):return 0
def adapters(value):
 os.environ['R59_FIXTURE_KEY']='offline-fixture'
 with m.paired.helpers.baseline._provider_environment('R59_FIXTURE_KEY',f'http://127.0.0.1:{server.server_port}/v1'):
  cfg=core.OpenAIAdapterConfig.from_env()
 cfg.model='qwen3.8-27b';cfg.max_tokens=8192;cfg.timeout_ms=120000;cfg.max_retries=0;cfg.enable_thinking=False
 llm=core.OpenAIAdapter(cfg)
 return llm,CountedStub(1024),llm,llm
m.make_adapters=adapters
ledger=runner.BudgetLedger(root/'request-ledger.sqlite',12000);scope=root/'scope'
'''


def test_native_multibatch_scope_replays_nonempty_claims_and_allows_empty_holder(prepared,tmp_path):
    run_code(NATIVE_SETUP+r'''
result=m.run_scope(checked,group,scope,ledger)
assert result['status']=='passed',result
assert result['database']['statements']==3 and result['database']['vectors']==3,result
assert result['native_replay']['verified'] and result['native_replay']['holders']==2
assert result['accounting']['observed_native_requests']==len(calls)
assert result['accounting']['known_tokens']==12*len(calls)
before=m.inventory(scope);assert m.scope_audit(scope,checked,group)==result;assert m.inventory(scope)==before
assert not list(scope.glob('*-wal')) and not list(scope.glob('*-shm'))
''',prepared,tmp_path/'native')


def test_legacy_default_clock_replays_across_seconds_without_mutating_evidence(prepared,tmp_path):
    run_code(NATIVE_SETUP+r'''
import time
result=m.run_scope(checked,group,scope,ledger);assert result['status']=='passed',result
before=m.inventory(scope);time.sleep(1.1)
assert m.scope_audit(scope,checked,group)==result
assert before==m.inventory(scope)
''',prepared,tmp_path/'clock')


def test_nonempty_native_episodic_event_coexists_with_claims_and_legacy_fact(prepared,tmp_path):
    run_code(NATIVE_SETUP+r'''
event_time='2026-01-01T09:00:00Z'
prompts[episodic_prompts['A']]=json.dumps([dict(actor='A',actor_kind='cognizer',action='put',theme='report',
 location='desk',participants=['A'],time=event_time)])
result=m.run_scope(checked,group,scope,ledger);assert result['status']=='passed',result
assert result['database']['statements']==4 and result['database']['vectors']==4
with m.paired.immutable(scope/'frozen.db') as db:
 db.row_factory=sqlite3.Row
 event=dict(db.execute("SELECT * FROM statements WHERE modality='occurred'").fetchone())
 extension=dict(db.execute('SELECT * FROM episodic_events WHERE statement_id=?',(event['id'],)).fetchone())
 assert event['event_time_start']==event_time and event['observed_at']==checked['config']['created_at']
 assert extension['event_time']==event_time and extension['location']=='desk'
 spans=json.loads(event['source_spans_json'])
 assert len(spans)==1 and spans[0]['source_hash']=='episodic-'+str(extension['seq'])
 assert spans[0]['observed_at']==checked['config']['created_at']
 assert spans[0]['engram_ref']==result['database']['source_engrams']['A']
# Native episodic extension persistence is best effort. Its absence must not
# invalidate the durable OCCURRED statement; statement time stays mandatory.
with sqlite3.connect(scope/'frozen.db') as db:db.execute('DELETE FROM episodic_events')
db.close()
assert m.scope_audit(scope,checked,group)['status']=='passed'
with sqlite3.connect(scope/'frozen.db') as db:
 db.execute("UPDATE statements SET event_time_start='1900-01-01T00:00:00Z' WHERE modality='occurred'")
db.close()
assert m.scope_audit(scope,checked,group)['status']=='technical_failure'
''',prepared,tmp_path/'episodic')


def test_overlapping_episodic_and_legacy_events_keep_distinct_native_clock_provenance(prepared,tmp_path):
    run_code(NATIVE_SETUP+r'''
legacy_prompt=next(digest for digest,text in prompts.items() if text.startswith('[{'))
prompts[legacy_prompt]=json.dumps([dict(holder='A',holder_perspective='FIRST_PERSON',subject='A',
 subject_kind='cognizer',predicate='put',object='report',modality='OCCURRED',polarity='POS',nesting_depth=0)])
prompts[episodic_prompts['A']]=json.dumps([dict(actor='A',actor_kind='cognizer',action='put',theme='report',
 location='desk',participants=['A'],time='2026-01-01T09:00:00Z')])
result=m.run_scope(checked,group,scope,ledger)
assert result['status']=='passed',result
assert result['database']['statements']==4 and result['accounting']['known_tokens']==108
with m.paired.immutable(scope/'frozen.db') as db:
 values=db.execute("SELECT id,observed_at,source_spans_json FROM statements WHERE modality='occurred'").fetchall()
assert len(values)==2
events={json.loads(spans)[0]['source_hash']:(sid,observed,json.loads(spans)) for sid,observed,spans in values}
assert set(events)=={'episodic-1','chunk-0'}
assert events['episodic-1'][1]==checked['config']['created_at']
# Qualification must not depend on the optional event extension table.
with sqlite3.connect(scope/'frozen.db') as db:db.execute('DELETE FROM episodic_events')
db.close()
assert m.scope_audit(scope,checked,group)['status']=='passed'
# An episodic row moved into the valid legacy clock window remains a forgery.
sid,_,spans=events['episodic-1'];legacy_clock=events['chunk-0'][1]
for span in spans:span['observed_at']=legacy_clock
with sqlite3.connect(scope/'frozen.db') as db:
 db.execute('UPDATE statements SET observed_at=?,source_spans_json=? WHERE id=?',(legacy_clock,json.dumps(spans),sid))
db.close()
audited=m.scope_audit(scope,checked,group)
assert audited['status']=='technical_failure' and audited['evidence_errors'],audited
''',prepared,tmp_path/'channel-clock')


@pytest.mark.parametrize('fault',['missing','duplicate','unknown'])
def test_scope_receipt_holder_inventory_preserves_subtotal_but_marks_unknown(prepared,tmp_path,fault):
    run_code(NATIVE_SETUP+f'\nfault={fault!r}\n'+r'''
result=m.run_scope(checked,group,scope,ledger);assert result['status']=='passed',result
rows=m.read(scope/'extraction.completed.json')['extraction']
if fault=='missing':rows.pop()
elif fault=='duplicate':rows.append(json.loads(json.dumps(rows[0])))
else:rows[-1]['holder']='OUTSIDE_SCOPE'
visible=m.extraction_accounting(rows,True,core)
m.write(scope/'extraction.completed.json',dict(extraction=rows))
# The native archive helper refuses duplicate holders; keep its prior archive
# while presenting the corrupted completed list to the read-only auditor.
if fault!='duplicate':m.baseline.write_extraction_receipt_archive(scope,rows)
metadata=m.read(scope/'scope.json');metadata['extraction']=rows;m.write(scope/'scope.json',metadata)
audited=m.scope_audit(scope,checked,group);cost=audited['accounting']
assert audited['status']=='technical_failure',audited
assert cost['known_tokens']==visible['known_tokens'] and cost['observed_native_requests']==visible['observed_native_requests']
assert cost['observed_tokens'] is None and not cost['usage_complete'],cost
assert cost['local_attempt_count_unknown'] and cost['remote_execution_unknown'],cost
assert not cost['healthy_http'],cost
''',prepared,tmp_path/'holder-cost')


@pytest.mark.parametrize('tamper',['missing_window','outside_window','span_disagrees','semantic_clock','commit_id'])
def test_runtime_clock_and_commit_binding_cannot_hide_forged_evidence(prepared,tmp_path,tamper):
    run_code(NATIVE_SETUP+f'\ntamper={tamper!r}\n'+r'''
result=m.run_scope(checked,group,scope,ledger);assert result['status']=='passed',result
if tamper=='missing_window':
 value=m.read(scope/'scope.started.json');value.pop('native_started_at',None);m.write(scope/'scope.started.json',value)
elif tamper=='commit_id':
 rows=m.read(scope/'extraction.completed.json')['extraction'];rows[0]['statement_ids'].pop()
 m.write(scope/'extraction.completed.json',dict(extraction=rows));m.baseline.write_extraction_receipt_archive(scope,rows)
 metadata=m.read(scope/'scope.json');metadata['extraction']=rows;m.write(scope/'scope.json',metadata)
else:
 with sqlite3.connect(scope/'frozen.db') as db:
  if tamper=='semantic_clock':db.execute("UPDATE statements SET observed_at='1900-01-01T00:00:00Z' WHERE semantic_claim_json IS NOT NULL")
  else:
   db.execute("UPDATE statements SET observed_at='1900-01-01T00:00:00Z' WHERE semantic_claim_json IS NULL")
   if tamper=='outside_window':
    for sid,raw in db.execute('SELECT id,source_spans_json FROM statements WHERE semantic_claim_json IS NULL').fetchall():
     spans=json.loads(raw)
     for span in spans:span['observed_at']='1900-01-01T00:00:00Z'
     db.execute('UPDATE statements SET source_spans_json=? WHERE id=?',(json.dumps(spans),sid))
 db.close()
audited=m.scope_audit(scope,checked,group)
assert audited['status']=='technical_failure' and audited['evidence_errors'],audited
''',prepared,tmp_path/'clock-forgery')


@pytest.mark.parametrize('mode',['late_scope','truncated','missing_usage','admission_failure'])
def test_native_failed_belief_stops_scope_but_keeps_independent_legacy_write(prepared,tmp_path,mode):
    run_code(NATIVE_SETUP+f'\nmode={mode!r}\n'+r'''
result=m.run_scope(checked,group,scope,ledger)
assert result['status']=='technical_failure',result
assert result['accounting']['observed_native_requests']==len(calls)
with m.paired.immutable(scope/'frozen.db') as db:
 if mode!='missing_usage':assert db.execute('SELECT count(*) FROM statements WHERE semantic_claim_json IS NOT NULL').fetchone()[0]==0
 assert db.execute('SELECT count(*) FROM statements WHERE semantic_claim_json IS NULL').fetchone()[0]==1
assert m.scope_audit(scope,checked,group)==result
assert ledger.snapshot()['reserved']==0
''',prepared,tmp_path/'failed')


@pytest.mark.parametrize('tamper',['nested_admission','predicate','object','source_time','source_spans','missing_claim',
                                  'confidence','canonical_hash','event_time','governance'])
def test_native_scope_tampering_cannot_be_hidden_by_rewriting_analysis(prepared,tmp_path,tamper):
    run_code(NATIVE_SETUP+f'\ntamper={tamper!r}\n'+r'''
result=m.run_scope(checked,group,scope,ledger);assert result['status']=='passed',result
if tamper=='nested_admission':
 rows=m.read(scope/'extraction.completed.json')['extraction']
 rows[0]['receipt']['channels']['belief']['attempts'][0]['admission']['structured_output']['total_tokens']=999
 m.write(scope/'extraction.completed.json',dict(extraction=rows));m.baseline.write_extraction_receipt_archive(scope,rows)
 metadata=m.read(scope/'scope.json');metadata['extraction']=rows;m.write(scope/'scope.json',metadata)
else:
 with sqlite3.connect(scope/'frozen.db') as db:
  if tamper=='predicate':db.execute("UPDATE statements SET predicate='forged' WHERE semantic_claim_json IS NOT NULL")
  elif tamper=='object':db.execute("UPDATE statements SET object_value='forged' WHERE semantic_claim_json IS NOT NULL")
  elif tamper=='source_time':db.execute("UPDATE engrams SET created_at='1900-01-01T00:00:00Z'")
  elif tamper=='source_spans':db.execute("UPDATE statements SET source_spans_json='[]' WHERE semantic_claim_json IS NOT NULL")
  elif tamper=='confidence':db.execute("UPDATE statements SET confidence=0.01 WHERE semantic_claim_json IS NOT NULL")
  elif tamper=='canonical_hash':db.execute("UPDATE statements SET canonical_object_hash='forged' WHERE semantic_claim_json IS NOT NULL")
  elif tamper=='event_time':db.execute("UPDATE statements SET event_time_start='1900-01-01' WHERE semantic_claim_json IS NOT NULL")
  elif tamper=='governance':db.execute("UPDATE statements SET review_status='auto_accepted' WHERE semantic_claim_json IS NOT NULL")
  else:db.execute("DELETE FROM statements WHERE semantic_claim_json IS NOT NULL")
 db.close()
audited=m.scope_audit(scope,checked,group);assert audited['status']=='technical_failure',audited
assert audited['evidence_errors'] or not audited['accounting']['healthy_http']
''',prepared,tmp_path/'tamper')


@pytest.mark.parametrize('fault',['adapters','native','archive','analysis','terminal','settlement'])
def test_scope_interruptions_preserve_read_only_partial_evidence(prepared,tmp_path,fault):
    run_code(NATIVE_SETUP+f'\nfault={fault!r}\n'+r'''
original=m.scope_audit
def broken(*args,**kwargs):raise RuntimeError('injected '+fault)
if fault=='adapters':m.make_adapters=broken
elif fault=='native':m.scope_worker=broken
elif fault=='archive':m.archive_scope=broken
elif fault=='analysis':m.scope_audit=broken
elif fault=='settlement':ledger.settle=broken
else:
 original_write=m.write
 def broken_write(path,value):
  if Path(path).name=='terminal.json':raise RuntimeError('injected terminal')
  return original_write(path,value)
 m.write=broken_write
result=m.run_scope(checked,group,scope,ledger);m.scope_audit=original
assert result['status']=='technical_failure',result
assert m.scope_audit(scope,checked,group)==result
if fault=='adapters':assert result['accounting']['observed_native_requests']==0 and not result['accounting']['local_attempt_count_unknown']
elif fault=='native':assert result['accounting']['local_attempt_count_unknown']
else:assert result['accounting']['observed_native_requests']==len(calls)
''',prepared,tmp_path/'interrupted')


@pytest.mark.parametrize('fault',['empty','usage_mismatch','certainty','hidden_admission'])
def test_raw_multichannel_cost_preserves_known_usage_and_unknown_consumption(prepared,tmp_path,fault):
    run_code(NATIVE_SETUP+f'\nfault={fault!r}\n'+r'''
m.run_scope(checked,group,scope,ledger)
rows=m.read(scope/'extraction.completed.json')['extraction'];expected=len(calls)
if fault=='empty':rows=[]
elif fault=='usage_mismatch':rows[0]['receipt']['channels']['general_fact']['attempts'][0]['extraction']['total_tokens']=999
elif fault=='certainty':rows[0]['receipt']['channels']['episodic']['response']['http_attempts'][0]['execution_certainty']='unregistered'
else:
 admission=rows[0]['receipt']['channels']['belief']['attempts'][0]['admission']
 admission.pop('called');admission.pop('attempt_count')
report=m.extraction_accounting(rows,True,core)
if fault=='empty':assert report['local_attempt_count_unknown'] and report['observed_tokens'] is None
else:
 assert report['observed_native_requests']==expected and report['known_tokens']==12*expected,report
 assert not report['healthy_http'],report
 if fault in ('certainty','hidden_admission'):assert report['remote_execution_unknown'],report
''',prepared,tmp_path/'cost')


@pytest.mark.parametrize('kind',['extraction','admission'])
@pytest.mark.parametrize('mutation',['missing','coerced_type'])
def test_belief_structured_evidence_requires_every_native_duplicate_field(prepared,tmp_path,kind,mutation):
    run_code(NATIVE_SETUP+f'\nkind={kind!r};mutation={mutation!r}\n'+r'''
result=m.run_scope(checked,group,scope,ledger);assert result['status']=='passed',result
original=m.read(scope/'extraction.completed.json')['extraction']
fields=original[0]['receipt']['channels']['belief']['attempts'][0][kind]['structured_output']
accepted=[]
for missing in fields:
 if mutation=='coerced_type' and type(fields[missing]) not in (int,bool):continue
 rows=json.loads(json.dumps(original))
 nested=rows[0]['receipt']['channels']['belief']['attempts'][0][kind]['structured_output']
 if mutation=='missing':nested.pop(missing)
 else:nested[missing]=int(nested[missing]) if type(nested[missing]) is bool else float(nested[missing])
 accounting=m.extraction_accounting(rows,True,core)
 assert accounting['observed_native_requests']==len(calls) and accounting['known_tokens']==12*len(calls)
 assert accounting['usage_complete'] and not accounting['local_attempt_count_unknown']
 if accounting['healthy_http']:accepted.append(missing)
assert not accepted,{'mutation':mutation,'duplicate_fields_wrongly_accepted':accepted}
rows=json.loads(json.dumps(original))
rows[0]['receipt']['channels']['belief']['attempts'][0][kind]['structured_output'].pop('total_tokens')
m.write(scope/'extraction.completed.json',dict(extraction=rows));m.baseline.write_extraction_receipt_archive(scope,rows)
metadata=m.read(scope/'scope.json');metadata['extraction']=rows;m.write(scope/'scope.json',metadata)
audited=m.scope_audit(scope,checked,group)
assert audited['status']=='technical_failure' and not audited['accounting']['healthy_http'],audited
assert audited['accounting']['known_tokens']==12*len(calls)
''',prepared,tmp_path/'nested-fields')


FULL_NATIVE_SETUP = NATIVE_SETUP + r'''
checked=m.check(Path(sys.argv[1]));prompts.clear();kinds.clear();calls.clear()
for group in checked['groups']:
 path=root/(group['group_id']+'-discovery.db');rt=runtime._build_local_store_sqlite_runtime(path);rt.start()
 runner.retain_history_sources(core,rt.adapter,group['history'],checked['config']['created_at'],preserve_invalid_time=True)
 with sqlite3.connect(path) as db:sources=db.execute('SELECT d.holder_id,e.payload_inline FROM source_documents d JOIN engrams e ON e.id=d.engram_ref').fetchall()
 for holder,payload in sources:
  fake=core.FakeLLMAdapter();fake.set_default_response('{"schema_version":2,"statements":[]}')
  cfg=runner._build_extraction_config(checked['config'])
  bundle=core.memory_remember_extract_all(rt.adapter,fake,cfg.belief_prompt,cfg.episodic_prompt,cfg.general_fact_prompt,
   holder,payload,policy=policy);receipt=json.loads(core.memory_remember_bundle_receipt(bundle))
  for attempt in receipt['channels']['belief']['attempts']:
   prompts[attempt['extraction']['prompt_input_hash']]='{"schema_version":2,"statements":[]}'
  digest=receipt['channels']['general_fact']['attempts'][0]['extraction']['prompt_input_hash']
  prompts[digest]=json.dumps([dict(holder=holder,holder_perspective='FIRST_PERSON',subject='water',subject_kind='entity',
   predicate='has_value',object='boiling point 100 C',modality='BELIEVES',polarity='POS',nesting_depth=0)])
 del rt
'''


@pytest.fixture(scope='module')
def built(prepared,tmp_path_factory):
    root=tmp_path_factory.mktemp('r59-build')/'fixture'
    run_code(FULL_NATIVE_SETUP+r'''
summary=m.build(Path(sys.argv[1]),root/'build')
assert summary['state']=='complete' and summary['healthy_scopes']==8,summary
assert summary['retrieval_ready'] and not summary['qa_ready']
assert summary['extraction_conservative_charge']==851
assert summary['extraction_observed_requests']==len(calls)
assert summary['extraction_known_tokens']==12*len(calls)
assert summary['ledger']['reserved']==0 and summary['ledger']['committed']==851
''',prepared,root)
    return root/'build'


def test_eight_native_scopes_are_rechecked_without_provider_or_mutation(built):
    run_code("""
out=Path(sys.argv[1]);before=m.inventory(out);result=m.check(out)
assert result['summary']['healthy_scopes']==8 and result['summary']['retrieval_ready']
assert result['audit_program_files'] and before==m.inventory(out)
assert result['prepared']!=out and result['prepared'] in Path(result['modules'][0].__file__).parents
""",built)


@pytest.mark.parametrize('tamper',['id','id_type','upper','state','summary','missing_scope','extra_legacy',
                                  'derived_sources','duplicate_derived'])
def test_resealed_build_cannot_forge_ledger_or_eight_healthy_scopes(built,tmp_path,tamper):
    m=driver();target=tmp_path/'build';shutil.copytree(built,target)
    gid=m.read(target/'groups.json')[0]['group_id'];scope=target/'runs'/gid
    if tamper in ('id','id_type','upper','state'):
        value=m.read(scope/'scope.started.json');key={'id':'id','id_type':'id','upper':'upper_bound','state':'state'}[tamper]
        value['reservation'][key]={'id':999,'id_type':True,'upper':1,'state':'settled'}[tamper]
        m.write(scope/'scope.started.json',value)
    elif tamper=='summary':
        value=m.read(target/'summary.json');value['extraction_observed_requests']=0;m.write(target/'summary.json',value)
    elif tamper=='missing_scope':shutil.rmtree(scope)
    else:
        import sqlite3
        with sqlite3.connect(scope/'frozen.db') as db:
            if tamper=='derived_sources':db.execute("UPDATE statements SET derived_from_json='[]' WHERE holder_id='__common_ground__'")
            elif tamper=='duplicate_derived':
                columns=[r[1] for r in db.execute('PRAGMA table_info(statements)')]
                values=["'extra-derived'" if k=='id' else k for k in columns]
                db.execute('INSERT INTO statements ('+','.join(columns)+') SELECT '+','.join(values)+" FROM statements WHERE holder_id='__common_ground__'")
            else:
                columns=[r[1] for r in db.execute('PRAGMA table_info(statements)')]
                values=["'extra-legacy'" if k=='id' else "'OUTSIDE_SCOPE'" if k=='holder_id' else k for k in columns]
                db.execute('INSERT INTO statements ('+','.join(columns)+') SELECT '+','.join(values)+
                           " FROM statements WHERE holder_id!='__common_ground__' LIMIT 1")
        db.close()
    (target/'seal.json').unlink();m.seal_output(target,'build')
    run_code("""
try:m.check(Path(sys.argv[1]))
except (ValueError,RuntimeError):pass
else:raise AssertionError('resealed forged build accepted')
""",target)


@pytest.mark.parametrize('fault',['adapters','native','ledger','terminal','analysis','initialize','stage_summary','summary_write'])
def test_build_stops_later_scopes_and_partial_check_preserves_unknown(prepared,tmp_path,fault):
    run_code(NATIVE_SETUP+f'\nfault={fault!r}\n'+r'''
def broken(*args,**kwargs):raise RuntimeError('injected '+fault)
if fault=='adapters':m.make_adapters=broken
elif fault=='native':m.scope_worker=broken
elif fault=='ledger':m.make_ledger=broken
elif fault=='analysis':m.scope_audit=broken
elif fault=='initialize':m.copy_file=broken
elif fault=='stage_summary':m.build_summary=broken
else:
 original_write=m.write
 def broken_write(path,value):
  if Path(path).name==('summary.json' if fault=='summary_write' else 'terminal.json'):raise RuntimeError('injected '+fault)
  return original_write(path,value)
 m.write=broken_write
original_audit=m.scope_audit
out=root/'build';summary=m.build(Path(sys.argv[1]),out)
assert summary['state']=='incomplete' and not summary['retrieval_ready'] and not summary['qa_ready'],summary
assert len(summary['unexecuted_scopes'])>=7
if fault=='native':assert summary['local_attempt_count_unknown']
if fault=='adapters':assert summary['extraction_known_tokens']==0 and not summary['local_attempt_count_unknown']
before=m.inventory(out);assert m.check(out)['summary']==summary and before==m.inventory(out)
''',prepared,tmp_path/'stage')


@pytest.mark.parametrize('fault',['copy','native_plan','summary_write'])
def test_prepare_interruption_is_sealed_and_read_only_auditable(tmp_path,fault):
    run_code(f'\nfault={fault!r}\n'+r'''
def broken(*args,**kwargs):raise RuntimeError('injected '+fault)
if fault=='copy':m.copy_file=broken
elif fault=='native_plan':m.native_plans=broken
else:
 original_write=m.write
 def broken_write(path,value):
  if Path(path).name=='summary.json':raise RuntimeError('injected summary write')
  return original_write(path,value)
 m.write=broken_write
out=Path(sys.argv[1]);summary=m.prepare(m.DEFAULT_PARENT,out)
assert summary['state']=='incomplete' and summary['external_requests']==0,summary
before=m.inventory(out);assert m.check(out)['summary']==summary and before==m.inventory(out)
try:m.check(out,'prepare')
except ValueError:pass
else:raise AssertionError('incomplete prepare admitted to build')
''',tmp_path/'prepare')
