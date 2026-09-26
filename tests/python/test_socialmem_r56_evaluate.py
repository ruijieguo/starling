"""Independent R5.6 paired evaluation; all fixtures are offline."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts/run_socialmem_r56_evaluate.py'


def driver():
    assert SCRIPT.is_file(), 'R5.6 independent retrieve/QA entry is required'
    spec=importlib.util.spec_from_file_location('r56_evaluate_test',SCRIPT)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def response(text='yes', *, usage=True):
    usage_row=dict(prompt_tokens=10,completion_tokens=2,total_tokens=12)
    body=dict(choices=[dict(finish_reason='stop',message=dict(content=text,refusal=None))])
    if usage:body['usage']=usage_row
    raw=json.dumps(body)
    return dict(raw_xml=text,raw_completion=text,response=dict(ok=True,error='',refusal=False,
        finish_reason='stop',attempt_count=1,raw_response=text,raw_completion=text,raw_http_response=raw,
        **usage_row,http_attempts=[dict(attempt=1,curl_code=0,http_status=200,
        execution_certainty='response_received',response_body=raw)]))


@pytest.mark.parametrize('stage',['retrieve','qa'])
def test_existing_output_refused_before_input_inspection(tmp_path,stage):
    m=driver();out=tmp_path/'exists';out.mkdir()
    with pytest.raises(ValueError,match='already exists'):getattr(m,stage)(tmp_path/'missing',out)


@pytest.mark.parametrize('problem',['partial','old_core','missing_database'])
def test_unhealthy_build_rejected_before_provider(tmp_path,monkeypatch,problem):
    m=driver()
    records=m.builder.read(m.builder.DEFAULT_PARENT/'sample.json');groups=m.builder.read(m.builder.DEFAULT_PARENT/'groups.json')
    checked=dict(stage='build',config=dict(core_sha256=m.CORE_SHA256),records=records,groups=groups,
        identity=dict(core_sha256=m.CORE_SHA256),summary=dict(state='complete',healthy_scopes=8,database_sha256={}),seal_sha256='seal')
    if problem=='partial':checked['summary']['state']='incomplete'
    elif problem=='old_core':checked['config']['core_sha256']='old'
    monkeypatch.setattr(m.builder,'check',lambda *_:checked)
    monkeypatch.setattr(m,'runtime_modules',lambda *_:pytest.fail('must reject before importing adapters'))
    with pytest.raises(ValueError):m.retrieve(tmp_path/'build',tmp_path/'out')


def test_fixed_task_inventory_and_budgets():
    m=driver();records=m.read(m.builder.DEFAULT_PARENT/'sample.json');groups=m.read(m.builder.DEFAULT_PARENT/'groups.json')
    assert m.validate_cohort(records,groups)==dict(questions=133,scopes=8,holders=65,retrieval_budget=1336,qa_budget=956)
    with pytest.raises(ValueError):m.validate_cohort(records+[records[0]],groups)
    with pytest.raises(ValueError):m.validate_cohort(records[:-1],groups)


def test_raw_usage_missing_stays_unknown_and_not_zero():
    m=driver();usage=m.raw_accounting([response(usage=False)])
    assert usage['observed_http_attempts']==1 and usage['total_tokens'] is None
    assert usage['known_tokens']==0 and usage['missing_token_usage']==1 and not usage['usage_complete']
    assert m.raw_accounting([],missing_response=True)['local_attempt_count_unknown'] is True
    assert m.raw_accounting([])['total_tokens']==0


@pytest.mark.parametrize('field',['count','body','finish','content','usage'])
def test_raw_response_evidence_rejects_inconsistency(field):
    m=driver();value=response()
    if field=='count':value['response']['attempt_count']=2
    elif field=='body':value['response']['http_attempts'][0]['response_body']='{}'
    elif field=='finish':value['response']['finish_reason']='length'
    elif field=='content':value['raw_xml']='forged answer'
    else:value['response']['total_tokens']=999
    assert m.raw_accounting([value])['healthy_http'] is False


def test_deferred_ledger_charges_unknown_upper_without_double_settlement(tmp_path):
    m=driver();ledger=m.baseline.BudgetLedger(tmp_path/'ledger.sqlite',10)
    deferred=m.DeferredLedger(ledger)
    reservation=deferred.reserve('x','answer_judge',2);deferred.settle(reservation['id'],1)
    assert ledger.snapshot()['reserved']==2
    charged=m.settle_qa(ledger,reservation,m.raw_accounting([response()],missing_response=True))
    assert charged==2 and ledger.snapshot()['charged_upper']==2 and ledger.snapshot()['reserved']==0


def test_main_endpoint_uses_all_133_and_net_seven_with_ci():
    m=driver();records=[dict(item_id=str(i),network_id='n'+str(i%6),query_type='q') for i in range(133)]
    left=[dict(item_id=r['item_id'],status='ok',correct=False,terminal=True) for r in records]
    right=[{**r,'correct':i<6} for i,r in enumerate(left)]
    result=m.previous.compare_scores(records,left,right,repetitions=200)
    assert result['denominator']==133 and not result['eligible_for_expanded_development']
    for r in right:r['correct']=int(r['item_id'])<12
    assert m.previous.compare_scores(records,left,right,repetitions=200)['eligible_for_expanded_development']
    for r in right[:7]:r.update(status='technical_failure',correct=False)
    assert not m.previous.compare_scores(records,left,right,repetitions=200)['eligible_for_expanded_development']


def test_low_anchor_scores_do_not_gate_qa():
    m=driver();records=[dict(item_id='q',source=dict(evidence_anchors=[dict(turn_id='missing')]))]
    rows={a:[dict(item_id='q',recall=dict(source_refs=[]))] for a in m.ARMS}
    comparison=m.previous.retrieval_comparison(records,rows)
    assert comparison['gate_uses_anchor_scores'] is False and comparison['qa_gate']=='passed_technical_health'


def test_source10_accounting_has_zero_embedding_and_baseline_usage_unknown():
    m=driver()
    usage=m.retrieval_accounting(dict(arm='source10',status='ok',embedding_requests=0,native_invoked=True))
    assert usage['observed_native_requests']==0 and usage['total_tokens']==0
    usage=m.retrieval_accounting(dict(arm='baseline',status='ok',embedding_requests=10,native_invoked=True))
    assert usage['observed_native_requests']==10 and usage['raw_http_available'] is False
    assert usage['total_tokens'] is None and usage['token_usage_unknown'] is True
    assert usage['remote_execution_unknown'] is False


def test_complete_terminal_set_rejects_missing_duplicates_and_failed_credit():
    m=driver();records=[dict(item_id='q')]
    rows=[dict(item_id='q',arm=a,policy=p,terminal=True,fresh=True,status='ok',correct=False) for a in m.ARMS for p in m.POLICIES]
    m.previous.validate_terminal_inventory(records,rows)
    for wrong in (rows[:-1],rows+[rows[0]],[{**r,'status':'technical_failure','correct':True} for r in rows]):
        with pytest.raises(ValueError):m.previous.validate_terminal_inventory(records,wrong)


@pytest.fixture(scope='module')
def native():
    m=driver();prepared=ROOT/'build/socialmem_20260925_r56_expanded/prepare'
    checked=m.builder.check(prepared,'prepare');runner,modules=m.builder.frozen_modules(prepared,checked['config'],checked['identity'])
    return m,checked,runner,modules


def empty_recall():
    return dict(block='',labels=[],source_refs=[],statement_ids=[],source_count=0,statement_count=0,
                context_bytes=0,source_context_bytes=0,statement_context_bytes=0,receipts=[],source_diagnostics={})


class Response:
    def __init__(self,text,usage=True):
        self.payload=response(text,usage=usage);self.raw_xml=text;self.raw_completion=text;self.ok=True;self.error=''
    def to_json(self):return json.dumps(self.payload['response'])


class Adapter:
    def __init__(self,text='yes',usage=True,error=None):self.text=text;self.usage=usage;self.error=error
    def extract(self,*_):
        if self.error:raise RuntimeError(self.error)
        return Response(self.text,self.usage)


def native_task(native,free=True):
    m,checked,runner,modules=native
    record=next(r for r in checked['records'] if (r.get('answer_format','multiple_choice')!='multiple_choice')==free)
    return m.qa_helpers.build_task('source10','grounded_memory_v1',record,empty_recall(),runner,checked['config'],modules)


def test_real_failed_build_is_rejected_before_any_provider(tmp_path,monkeypatch):
    m=driver();built=ROOT/'build/socialmem_20260925_r56_expanded/build'
    assert m.read(built/'seal.json')['state']=='incomplete'
    monkeypatch.setattr(m,'runtime_modules',lambda *_:pytest.fail('provider boundary must not be reached'))
    with pytest.raises(ValueError,match='incomplete'):m.retrieve(built,tmp_path/'retrieve')
    assert not (tmp_path/'retrieve').exists()


@pytest.mark.parametrize('change',['answer_prompt','judge_prompt','correct','raw_answer'])
def test_native_reconstructed_prompts_and_raw_verdict_reject_forgery(native,tmp_path,change):
    m,_,runner,modules=native;task=native_task(native)
    ledger=runner.BudgetLedger(tmp_path/'ledger.sqlite',956)
    row=m.execute_qa(task,tmp_path/'answers',runner,modules,ledger,(None,None,Adapter('calm'),Adapter('yes')))
    assert row['status']=='ok' and row['correct'] and row['charged_requests']==2
    m.validate_qa_terminal(task,row,modules)
    if change=='answer_prompt':row['prompt']+=' attacker';row['prompt_sha256']=m.text_sha(row['prompt'])
    elif change=='judge_prompt':row['judge_prompt']+=' attacker';row['judge_prompt_sha256']=m.text_sha(row['judge_prompt'])
    elif change=='correct':row['correct']=False
    else:row['answer']['raw_xml']='forged answer'
    with pytest.raises(ValueError):m.validate_qa_terminal(task,row,modules)


def test_invalid_multiple_choice_is_zero_terminal_not_stage_exception(native,tmp_path):
    m,_,runner,modules=native;task=native_task(native,False);ledger=runner.BudgetLedger(tmp_path/'ledger.sqlite',956)
    row=m.execute_qa(task,tmp_path/'answers',runner,modules,ledger,(None,None,Adapter('cannot answer'),Adapter()))
    assert row['terminal'] and row['status']=='invalid_answer' and row['correct'] is False
    assert row['charged_requests']==1
    m.validate_qa_terminal(task,row,modules)


def test_missing_usage_and_judge_exception_preserve_raw_partial_cost(native,tmp_path):
    m,_,runner,modules=native;task=native_task(native)
    for name,answer,judge,want_unknown in [('usage',Adapter('calm',False),Adapter('yes'),False),
                                         ('exception',Adapter('calm'),Adapter(error='unknown remote result'),True)]:
        path=tmp_path/name;ledger=runner.BudgetLedger(path/'ledger.sqlite',956)
        row=m.execute_qa(task,path/'answers',runner,modules,ledger,(None,None,answer,judge))
        assert row['status']=='technical_failure' and row['correct'] is False
        assert row['accounting']['total_tokens'] is None and row['charged_requests']==2
        assert row['accounting']['local_attempt_count_unknown'] is want_unknown
        if want_unknown:assert row['accounting']['observed_http_attempts']==1 and ledger.snapshot()['charged_upper']==2
        m.validate_qa_terminal(task,row,modules)


def test_true_native_fake_llm_does_not_count_as_http_success(native,tmp_path):
    m,_,runner,modules=native;core=modules[0];task=native_task(native)
    llm=core.FakeLLMAdapter();llm.set_default_response('yes');ledger=runner.BudgetLedger(tmp_path/'ledger.sqlite',956)
    row=m.execute_qa(task,tmp_path/'answers',runner,modules,ledger,(None,None,llm,llm))
    assert row['terminal'] and row['status']=='technical_failure' and not row['correct']
    assert row['accounting']['observed_http_attempts']==0 and row['accounting']['local_attempt_count_unknown']
    assert ledger.snapshot()['charged_upper']==2


def test_real_native_source10_uses_stub_without_embedding_and_binds_text(native,tmp_path):
    from contextlib import closing
    m,checked,runner,modules=native;core,runtime,_,_,pipeline,_=modules
    config=checked['config'];history=[dict(speaker='A',text='I feel calm.',turn_id='t1',observed_at='2026-01-01T00:00:00Z'),
        dict(speaker='A',text='I like hiking.',turn_id='t2',observed_at='2026-01-01T00:01:00Z')]
    group=dict(group_id='g',history=history);record=dict(item_id='q',question='How does A feel?',history=history)
    built=tmp_path/'built';scope=built/'runs/g';scope.mkdir(parents=True)
    rt=runtime._build_local_store_sqlite_runtime(tmp_path/'live.db');rt.start()
    runner.retain_history_sources(core,rt.adapter,history,config['created_at'],preserve_invalid_time=True)
    with closing(sqlite3.connect(tmp_path/'live.db')) as db,closing(sqlite3.connect(scope/'frozen.db')) as target:
        db.backup(target);refs=dict(db.execute('SELECT holder_id,engram_ref FROM source_documents'))
    digest=m.sha(scope/'frozen.db');plans=m.builder.native_plans(runner,modules,[group],config)['scopes']['g']
    row=m.ablation.query_one(('g',record,'source10',core.StubEmbeddingAdapter(1024)),built,tmp_path/'out',
        dict(database_sha256={'g':digest}),config,core,runtime,pipeline)
    assert row['status']=='ok' and row['embedding_requests']==0 and row['recall']['source_count']>0
    m.validate_context(core,record,row,plans,refs,lambda *_:None)
    row['recall']['block']=row['recall']['block'].replace('calm','angry')
    row['recall']['context_bytes']=len(row['recall']['block'].encode())
    with pytest.raises(ValueError,match='source text'):m.validate_context(core,record,row,plans,refs,lambda *_:None)
    assert m.sha(scope/'frozen.db')==digest and not list(scope.glob('*-wal')) and not list(scope.glob('*-shm'))


def retrieval_stage_fixture(m,checked,tmp_path):
    built=tmp_path/'build';built.mkdir()
    databases={}
    for group in checked['groups']:
        path=built/'runs'/group['group_id']/'frozen.db';path.parent.mkdir(parents=True)
        with sqlite3.connect(path) as db:db.execute('CREATE TABLE fixture_marker(value INTEGER)')
        databases[group['group_id']]=m.sha(path)
    m.write(built/'seal.json',dict(fixture='synthetic provenance boundary only',state='complete'))
    actual={**checked,'stage':'build','built':built,'prepared':ROOT/'build/socialmem_20260925_r56_expanded/prepare',
        'databases':databases,'seal_sha256':m.sha(built/'seal.json'),
        'summary':dict(state='complete',healthy_scopes=8,database_sha256=databases,
            health={gid:dict(database_proof=dict(source_engrams={})) for gid in databases})}
    out=tmp_path/'retrieve';m.freeze_stage(actual,out,'retrieve',built,actual['seal_sha256'],4)
    ledger=m.baseline.BudgetLedger(out/'request-ledger.sqlite',1336);rows={a:[] for a in m.ARMS}
    for group in checked['groups']:
        for record in group['records']:
            for arm in m.ARMS:
                holders=m.baseline.history_holders(record['history']);upper=len(holders) if arm=='baseline' else 0
                reservation=ledger.reserve(arm+'/'+record['item_id'],'query_embedding',upper);ledger.settle(reservation['id'],upper)
                recall=empty_recall()
                if arm=='baseline':recall['receipts']=[dict(holder=h,degraded_paths=[]) for h in holders]
                strategy,mode,k=m.ablation.ARMS[arm]
                row=dict(item_id=record['item_id'],group_id=group['group_id'],arm=arm,strategy=strategy,mode=mode,k=k,
                    holders=holders,core_sha256=m.CORE_SHA256,database_sha256=databases[group['group_id']],
                    status='ok',terminal=True,embedding_requests=upper,recall=recall,native_invoked=True,
                    reservation=reservation,charged_requests=upper)
                row['accounting']=m.retrieval_accounting(row);rows[arm].append(row)
                m.write(out/arm/'recalls'/(m.text_sha(record['item_id'])+'.json'),row)
    summary=m.retrieval_summary(out,actual,rows);m.write(out/'summary.json',summary)
    m.write(out/'comparison.json',m.previous.retrieval_comparison(checked['records'],rows))
    m.write(out/'execution-plan.json',m.execution_plan('retrieve',4,actual));m.seal_output(out,'retrieve')
    return actual,out,rows


@pytest.mark.parametrize('change',['missing','duplicate','holder','strategy','core','database','context_bytes'])
def test_retrieval_inventory_binds_every_item_holder_strategy_and_database(native,tmp_path,change):
    m,checked,_,_=native;actual,out,rows=retrieval_stage_fixture(m,checked,tmp_path)
    m.retrieval_inventory(actual,rows,require_healthy=True)
    row=rows['baseline'][0]
    if change=='missing':rows['baseline'].pop()
    elif change=='duplicate':rows['baseline'][-1]=deepcopy(row)
    elif change=='holder':row['holders'].pop()
    elif change=='strategy':row['strategy']='evidence_profile_v9'
    elif change=='core':row['core_sha256']='old'
    elif change=='database':row['database_sha256']='wrong'
    else:row['recall']['context_bytes']=17
    with pytest.raises(ValueError):m.retrieval_inventory(actual,rows)


def test_sealed_retrieval_check_is_read_only_and_rejects_resealed_summary(native,tmp_path,monkeypatch):
    m,checked,_,_=native;actual,out,rows=retrieval_stage_fixture(m,checked,tmp_path)
    monkeypatch.setattr(m,'validated_build',lambda *_:actual)
    before=m.inventory(out)
    verified=m.check(out)
    assert verified['summary']['healthy_terminals']==266 and verified['summary']['embedding_requests']==1336
    assert verified['summary']['total_tokens'] is None and verified['summary']['gate_uses_anchor_scores'] is False
    assert m.inventory(out)==before
    summary=m.read(out/'summary.json');summary['embedding_requests']=0;m.write(out/'summary.json',summary)
    (out/'seal.json').unlink();m.seal_output(out,'retrieve')
    with pytest.raises(ValueError,match='summary'):m.check(out)


def test_full_fresh_qa_stage_rechecks_prompts_scores_and_ledger(native,tmp_path,monkeypatch):
    m,checked,runner,modules=native;actual,contexts,_=retrieval_stage_fixture(m,checked,tmp_path)
    monkeypatch.setattr(m,'validated_build',lambda *_:actual)
    monkeypatch.setattr(runner,'_make_native_adapters',lambda *_:(None,None,Adapter('0'),Adapter('yes')))
    monkeypatch.setattr(m,'runtime_modules',lambda *_:(runner,modules))
    out=tmp_path/'qa';summary=m.qa(contexts,out,workers=4)
    assert summary['terminal_count']==532 and summary['ledger']['committed']==956
    assert summary['usage_complete'] and summary['total_tokens']==11472
    before=m.inventory(out);verified=m.check(out)
    assert verified['summary']==summary and m.inventory(out)==before
    path=next((out/'answers/grounded_memory_v1/source10').glob('*.json'))
    row=m.read(path);row['prompt']+=' forged';row['prompt_sha256']=m.text_sha(row['prompt']);m.write(path,row)
    plan=m.read(out/'execution-plan.json')
    binding=next(t for t in plan['tasks_binding'] if (t['item_id'],t['arm'],t['policy'])==(row['item_id'],row['arm'],row['policy']))
    binding['prompt_sha256']=row['prompt_sha256'];m.write(out/'execution-plan.json',plan)
    (out/'seal.json').unlink();m.seal_output(out,'qa')
    with pytest.raises(ValueError,match='prompt|binding'):m.check(out)


def test_source_only_failure_cannot_invent_provider_uncertainty():
    m=driver();usage=m.retrieval_accounting(dict(arm='source10',status='error',embedding_requests=0,native_invoked=True))
    assert usage['local_attempt_count_unknown'] is False and usage['remote_execution_unknown'] is False
    assert usage['total_tokens']==0 and usage['token_usage_unknown'] is False


def test_fixed_bounded_task_cannot_forge_blocked_reservation_without_ledger():
    m=driver();row=dict(reservation=dict(state='blocked',remaining=0),charged_requests=0)
    with pytest.raises(ValueError):m.reservation_evidence(row,'a/p/q','answer_judge',2,0,False)


def test_retrieval_provider_construction_failures_seal_all_terminals_and_block_qa(native,tmp_path,monkeypatch):
    m,checked,_,_=native;actual,_,_=retrieval_stage_fixture(m,checked,tmp_path)
    monkeypatch.setattr(m,'validated_build',lambda *_:actual)
    def unavailable(*_):raise RuntimeError('fixture provider unavailable before invocation')
    monkeypatch.setattr(m.previous.previous,'_build_embedder',unavailable)
    out=tmp_path/'failed-retrieve';summary=m.retrieve(actual['built'],out,workers=4)
    assert summary['state']=='incomplete' and summary['terminal_count']==266 and summary['healthy_terminals']==133
    assert summary['embedding_requests']==0 and summary['ledger']['committed']==0
    assert summary['total_tokens']==0 and summary['local_attempt_count_unknown'] is False
    assert m.check(out)['summary']==summary
    with pytest.raises(ValueError,match='incomplete'):m.qa(out,tmp_path/'forbidden-qa')
    assert not (tmp_path/'forbidden-qa').exists()


def test_native_reasoning_trace_removal_preserves_both_raw_representations():
    m=driver();value=response('<think>private reasoning</think>yes')
    value['raw_xml']='yes';value['response']['raw_response']='yes'
    assert m.raw_accounting([value])['healthy_http'] is True


def test_failed_recall_is_preserved_without_being_promoted_or_aborting_audit(native,tmp_path):
    m,checked,_,modules=native;actual,out,rows=retrieval_stage_fixture(m,checked,tmp_path)
    row=rows['baseline'][0];row.update(status='error',error='native receipt validation rejected context')
    row['recall']['block']='malformed source diagnostic';row['recall']['context_bytes']=len(row['recall']['block'])
    m.retrieval_inventory(actual,rows)
    m.verify_contexts(actual,rows,modules)
    with pytest.raises(ValueError):m.retrieval_inventory(actual,rows,require_healthy=True)


@pytest.mark.parametrize('change',['missing','non_boolean','count_without_call','success_without_call','recall_without_call'])
def test_retrieval_invocation_evidence_cannot_be_missing_or_contradictory(change):
    m=driver();row=dict(arm='baseline',status='error',embedding_requests=0,native_invoked=False)
    if change=='missing':row.pop('native_invoked')
    elif change=='non_boolean':row['native_invoked']='true'
    elif change=='count_without_call':row['embedding_requests']=1
    elif change=='success_without_call':row['status']='ok'
    else:row['recall']=empty_recall()
    with pytest.raises(ValueError):m.retrieval_accounting(row)


def test_frozen_stage_runtime_failure_has_read_only_zero_call_audit(native,tmp_path,monkeypatch):
    m,checked,runner,modules=native;actual,_,_=retrieval_stage_fixture(m,checked,tmp_path)
    monkeypatch.setattr(m,'validated_build',lambda *_:actual)
    def broken(*_):raise RuntimeError('injected runtime initialization failure')
    monkeypatch.setattr(m,'runtime_modules',broken)
    out=tmp_path/'runtime-failure'
    with pytest.raises(RuntimeError,match='initialization'):m.retrieve(actual['built'],out)
    monkeypatch.setattr(m,'runtime_modules',lambda *_:(runner,modules))
    before=m.inventory(out);summary=m.check(out)['summary']
    assert summary['state']==summary['artifact_state']=='incomplete' and summary['evidence_valid'] is True
    assert summary['expected_task_count']==266 and summary['validated_terminal_count']==0
    assert len(summary['missing_receipt_tasks'])==len(summary['unstarted_tasks'])==266
    assert summary['ledger'] is None and summary['observed_http_attempts']==0 and summary['total_tokens']==0
    assert m.inventory(out)==before
    with pytest.raises(ValueError,match='incomplete'):m.check(out,'retrieve')


@pytest.mark.parametrize('fault',['settlement','terminal_write','summary'])
def test_stage_exception_preserves_receipts_ledger_and_missing_state(native,tmp_path,monkeypatch,fault):
    m,checked,runner,modules=native;actual,contexts,_=retrieval_stage_fixture(m,checked,tmp_path)
    monkeypatch.setattr(m,'validated_build',lambda *_:actual)
    monkeypatch.setattr(m,'runtime_modules',lambda *_:(runner,modules))
    monkeypatch.setattr(runner,'_make_native_adapters',lambda *_:(None,None,Adapter('0'),Adapter('yes')))
    out=tmp_path/'qa-failure';fired=[]
    if fault=='settlement':
        original=m.settle_qa
        def broken(*args):
            if not fired:fired.append(True);raise RuntimeError('injected ledger settlement failure')
            return original(*args)
        monkeypatch.setattr(m,'settle_qa',broken)
    elif fault=='terminal_write':
        original=m.write
        def broken(path,value):
            if out/'answers' in Path(path).parents and not fired:
                fired.append(True);raise RuntimeError('injected terminal write failure')
            return original(path,value)
        monkeypatch.setattr(m,'write',broken)
    else:
        def broken(*args,**kwargs):raise RuntimeError('injected summary failure')
        monkeypatch.setattr(m,'qa_summary',broken)
    with pytest.raises(RuntimeError,match='injected'):m.qa(contexts,out)
    before=m.inventory(out);summary=m.check(out)['summary']
    assert summary['artifact_state']=='incomplete' and summary['expected_task_count']==532
    assert summary['ledger']['committed']==956 and summary['ledger']['reserved']==0
    assert summary['ledger']['charged_upper']==(2 if fault=='settlement' else 0)
    assert summary['validated_terminal_count']==(532 if fault=='summary' else 531)
    assert len(summary['partial_receipt_tasks'])==(0 if fault=='summary' else 1)
    assert summary['missing_receipt_tasks']==[] and 'policies' not in summary
    assert m.inventory(out)==before
    with pytest.raises(ValueError,match='incomplete'):m.check(out,'qa')
    forged=m.read(out/'failure-summary.json');forged['observed_http_attempts']=0
    m.write(out/'failure-summary.json',forged);m.write(out/'summary.json',forged)
    (out/'seal.json').unlink();m.seal_output(out,'qa','incomplete')
    with pytest.raises(ValueError):m.check(out)


@pytest.mark.parametrize('fault',['terminal_write','context'])
def test_retrieval_stage_failure_audits_partial_and_invalid_context(native,tmp_path,monkeypatch,fault):
    m,checked,runner,modules=native;actual,_,fixture_rows=retrieval_stage_fixture(m,checked,tmp_path)
    monkeypatch.setattr(m,'validated_build',lambda *_:actual)
    monkeypatch.setattr(m,'runtime_modules',lambda *_:(runner,modules))
    monkeypatch.setattr(m.previous.previous,'_build_embedder',lambda *_:None)
    indexed={(r['arm'],r['item_id']):r for arm in m.ARMS for r in fixture_rows[arm]}
    target=fixture_rows['baseline'][0];scope=target['arm']+'/'+target['item_id']
    def query(task,built,out,*_):
        _,record,arm,_=task;row=deepcopy(indexed[(arm,record['item_id'])])
        for key in ('reservation','accounting','native_invoked','charged_requests'):row.pop(key)
        if fault=='context' and arm+'/'+record['item_id']==scope:
            block='[SOURCE] {"speaker":"nonexistent"} text="forged source"';row['recall'].update(block=block,labels=['SOURCE'],source_count=1,
                source_refs=[dict(speaker='nonexistent',engram_ref='forged',clause_id='c0',turn_id='t0')],
                context_bytes=len(block),source_context_bytes=len(block))
        m.ablation.write(out/arm/'recalls'/(m.text_sha(record['item_id'])+'.json'),row)
        return row
    monkeypatch.setattr(m.ablation,'query_one',query)
    out=tmp_path/'retrieve-failure';fired=[]
    if fault=='terminal_write':
        original=m.write
        def broken(path,value):
            if Path(path).parent.name=='recalls' and not fired:
                fired.append(True);raise RuntimeError('injected retrieval terminal write failure')
            return original(path,value)
        monkeypatch.setattr(m,'write',broken)
    with pytest.raises((ValueError,RuntimeError)):m.retrieve(actual['built'],out)
    before=m.inventory(out);summary=m.check(out)['summary']
    assert summary['validated_terminal_count']==265 and summary['missing_receipt_tasks']==[]
    assert summary['ledger']['committed']==1336 and summary['total_tokens'] is None
    assert summary['evidence_valid']==(fault=='terminal_write')
    if fault=='terminal_write':assert len(summary['partial_receipt_tasks'])==1
    else:
        assert summary['partial_receipt_tasks']==[]
        assert any(e['task']==scope and 'context source' in e['error'] for e in summary['invalid_evidence'])
    assert m.inventory(out)==before


def test_failure_audit_preserves_unresolved_reservation_when_conservative_charge_fails(native,tmp_path,monkeypatch):
    m,checked,runner,modules=native;actual,_,_=retrieval_stage_fixture(m,checked,tmp_path)
    monkeypatch.setattr(m,'validated_build',lambda *_:actual)
    out=tmp_path/'reservation-failure';m.freeze_stage(actual,out,'retrieve',actual['built'],actual['seal_sha256'],1)
    m.write(out/'execution-plan.json',m.execution_plan('retrieve',1,actual))
    ledger=m.baseline.BudgetLedger(out/'request-ledger.sqlite',1336);record=checked['records'][0]
    scope='baseline/'+record['item_id'];upper=len(m.baseline.history_holders(record['history']))
    ledger.reserve(scope,'query_embedding',upper)
    def broken(*_):raise RuntimeError('injected ledger finalization failure')
    monkeypatch.setattr(ledger,'charge_upper',broken)
    try:raise RuntimeError('injected interrupted provider call')
    except RuntimeError as exc:m.fail_stage(out,'retrieve',exc,ledger,actual,runner,modules)
    before=m.inventory(out);summary=m.check(out)['summary']
    assert summary['ledger']['reserved']==upper and summary['ledger']['committed']==0
    assert len(summary['unresolved_reservations'])==1 and summary['unknown_request_tasks']==[scope]
    assert summary['observed_http_attempts']==0 and summary['total_tokens'] is None
    assert summary['local_attempt_count_unknown'] and summary['remote_execution_unknown']
    assert summary['validated_terminal_count']==0 and len(summary['unstarted_tasks'])==265
    assert m.inventory(out)==before


@pytest.mark.parametrize('tamper',['prompt','score','ledger'])
def test_failure_audit_cannot_hide_saved_terminal_contradictions(native,tmp_path,monkeypatch,tamper):
    import shutil
    m,checked,runner,modules=native;actual,contexts,rows=retrieval_stage_fixture(m,checked,tmp_path)
    monkeypatch.setattr(m,'validated_build',lambda *_:actual)
    out=tmp_path/'partial-qa';m.freeze_stage(actual,out,'qa',contexts,m.sha(contexts/'seal.json'),1)
    for arm in m.ARMS:shutil.copytree(contexts/arm/'recalls',out/'input-recalls'/arm)
    tasks=m.make_tasks(actual,rows,runner,modules);m.write(out/'execution-plan.json',m.execution_plan('qa',1,actual,tasks))
    ledger=m.baseline.BudgetLedger(out/'request-ledger.sqlite',956);task=tasks[0]
    row=m.execute_qa(task,out/'answers',runner,modules,ledger,(None,None,Adapter('0'),Adapter('yes')))
    try:raise RuntimeError('fixture interruption after first completed task')
    except RuntimeError as exc:m.fail_stage(out,'qa',exc,ledger,actual,runner,modules,rows)
    summary=m.check(out)['summary']
    assert summary['evidence_valid'] and summary['validated_terminal_count']==1
    assert len(summary['missing_receipt_tasks'])==len(summary['unstarted_tasks'])==531
    path=out/'answers'/task['policy']/task['arm']/(m.text_sha(task['item_id'])+'.json')
    if tamper=='prompt':row['prompt']+=' forged';row['prompt_sha256']=m.text_sha(row['prompt']);m.write(path,row)
    elif tamper=='score':row['correct']=not row['correct'];m.write(path,row)
    else:
        with sqlite3.connect(out/'request-ledger.sqlite') as db:db.execute('UPDATE reservations SET actual=0')
    (out/'seal.json').unlink();m.seal_output(out,'qa','incomplete')
    with pytest.raises(ValueError,match='failure audit summary'):m.check(out)
    audit=m.failure_audit(out,actual,runner,modules,rows)
    assert not audit['evidence_valid'] and audit['validated_terminal_count']==0 and audit['invalid_evidence']
    m.write(out/'summary.json',audit);m.write(out/'failure-summary.json',audit)
    (out/'seal.json').unlink();m.seal_output(out,'qa','incomplete')
    before=m.inventory(out);assert m.check(out)['summary']==audit and m.inventory(out)==before
    assert m.main(['check','--input',str(out)])==1


def test_unreadable_failure_ledger_cannot_claim_tasks_were_unstarted(native,tmp_path,monkeypatch):
    m,checked,runner,modules=native;actual,_,_=retrieval_stage_fixture(m,checked,tmp_path)
    monkeypatch.setattr(m,'validated_build',lambda *_:actual)
    out=tmp_path/'unreadable-ledger';m.freeze_stage(actual,out,'retrieve',actual['built'],actual['seal_sha256'],1)
    m.write(out/'execution-plan.json',m.execution_plan('retrieve',1,actual))
    ledger=m.baseline.BudgetLedger(out/'request-ledger.sqlite',1336)
    ledger.reserve('baseline/'+checked['records'][0]['item_id'],'query_embedding',10)
    with sqlite3.connect(out/'request-ledger.sqlite') as db:db.execute('ALTER TABLE reservations RENAME TO damaged')
    try:raise RuntimeError('fixture damaged ledger after provider boundary')
    except RuntimeError as exc:m.fail_stage(out,'retrieve',exc,ledger,actual,runner,modules)
    before=m.inventory(out);summary=m.check(out)['summary']
    assert not summary['evidence_valid'] and summary['ledger_identity_unknown']
    assert summary['unstarted_tasks']==[] and len(summary['start_state_unknown_tasks'])==266
    assert summary['local_attempt_count_unknown'] and summary['remote_execution_unknown']
    assert summary['total_tokens'] is None and m.inventory(out)==before


def test_missing_failure_ledger_with_saved_receipts_is_unknown(native,tmp_path,monkeypatch):
    m,checked,runner,modules=native;actual,out,_=retrieval_stage_fixture(m,checked,tmp_path)
    monkeypatch.setattr(m,'validated_build',lambda *_:actual)
    (out/'seal.json').unlink();(out/'request-ledger.sqlite').unlink()
    try:raise RuntimeError('fixture missing ledger with saved receipts')
    except RuntimeError as exc:m.fail_stage(out,'retrieve',exc,None,actual,runner,modules)
    before=m.inventory(out);summary=m.check(out)['summary']
    assert not summary['evidence_valid'] and summary['ledger_identity_unknown']
    assert summary['unstarted_tasks']==[] and summary['validated_terminal_count']==0
    assert summary['local_attempt_count_unknown'] and summary['remote_execution_unknown']
    assert summary['total_tokens'] is None and m.inventory(out)==before


def test_missing_failure_ledger_after_execution_plan_cannot_claim_zero_calls(native,tmp_path,monkeypatch):
    m,checked,runner,modules=native;actual,_,_=retrieval_stage_fixture(m,checked,tmp_path)
    monkeypatch.setattr(m,'validated_build',lambda *_:actual)
    out=tmp_path/'missing-ledger-no-receipts';m.freeze_stage(actual,out,'retrieve',actual['built'],actual['seal_sha256'],1)
    m.write(out/'execution-plan.json',m.execution_plan('retrieve',1,actual))
    ledger=m.baseline.BudgetLedger(out/'request-ledger.sqlite',1336);record=checked['records'][0]
    ledger.reserve('baseline/'+record['item_id'],'query_embedding',len(m.baseline.history_holders(record['history'])))
    (out/'request-ledger.sqlite').unlink()
    try:raise RuntimeError('fixture ledger lost after provider boundary before first receipt')
    except RuntimeError as exc:m.fail_stage(out,'retrieve',exc,None,actual,runner,modules)
    before=m.inventory(out);summary=m.check(out)['summary']
    assert summary['ledger_identity_unknown'] and summary['unstarted_tasks']==[]
    assert len(summary['start_state_unknown_tasks'])==len(summary['missing_receipt_tasks'])==266
    assert summary['local_attempt_count_unknown'] and summary['remote_execution_unknown']
    assert summary['observed_http_attempts']==0 and summary['total_tokens'] is None
    assert m.inventory(out)==before
