#!/usr/bin/env python3
"""R5.6 immutable paired retrieval and fresh QA, after all eight rebuilds pass."""
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
import traceback

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('r56_evaluation_builder',ROOT/'scripts/run_socialmem_r56_expanded.py')
builder=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(builder)
previous=builder.previous;baseline=builder.baseline;qa_helpers=previous.qa_helpers;ablation=previous.ablation
read,write,sha,inventory=builder.read,builder.write,builder.sha,builder.inventory
text_sha=qa_helpers.text_sha
CORE_SHA256=builder.CORE_SHA256
ARMS=('baseline','source10');POLICIES=('legacy','grounded_memory_v1')
RETRIEVAL_BUDGET,QA_BUDGET=1336,956
OWN_FILES=('scripts/run_socialmem_r56_evaluate.py','tests/python/test_socialmem_r56_evaluate.py')


def validate_cohort(records,groups):
    previous.validate_record_groups(records,groups)
    result=dict(questions=len(records),scopes=len(groups),holders=sum(len(baseline.history_holders(g['history'])) for g in groups),
        retrieval_budget=sum(len(baseline.history_holders(r['history'])) for r in records),
        qa_budget=4*sum(1+int(r.get('answer_format','multiple_choice')!='multiple_choice') for r in records))
    if result!=dict(questions=133,scopes=8,holders=65,retrieval_budget=1336,qa_budget=956):
        raise ValueError('fixed cohort/task budget mismatch')
    return result


def validated_build(built):
    built=Path(built).resolve();checked=builder.check(built,'build')
    summary=checked['summary'];validate_cohort(checked['records'],checked['groups'])
    gids={g['group_id'] for g in checked['groups']};databases=summary.get('database_sha256',{})
    if (checked['stage']!='build' or summary.get('state')!='complete' or summary.get('healthy_scopes')!=8
        or checked['config'].get('core_sha256')!=CORE_SHA256 or checked['identity'].get('core_sha256')!=CORE_SHA256
        or set(databases)!=gids or set(summary.get('health',{}))!=gids):
        raise ValueError('eight healthy current-core databases are required before provider construction')
    for gid,digest in databases.items():
        path=built/'runs'/gid/'frozen.db'
        if not path.is_file() or any(Path(str(path)+s).exists() for s in ('-wal','-shm')) or sha(path)!=digest:
            raise ValueError('missing/live/changed build database')
    prepared=Path(read(built/'stage.json')['input']).resolve()
    return dict(**checked,built=built,prepared=prepared,databases=databases)


def runtime_modules(checked):
    return builder.frozen_modules(checked['prepared'],checked['config'],checked['identity'])


def source_paths():
    return sorted(set(builder.source_paths())|{ROOT/name for name in OWN_FILES})


def seal_output(out,stage,state='complete'):
    if (out/'seal.json').exists():raise ValueError('output already sealed')
    write(out/'seal.json',dict(schema='r56-evaluation-seal-v1',stage=stage,state=state,files=inventory(out)))


def verify_seal(out):
    out=Path(out);seal=read(out/'seal.json');actual=inventory(out);actual.pop('seal.json',None)
    if seal.get('schema')!='r56-evaluation-seal-v1' or seal.get('state') not in ('complete','incomplete'):
        raise ValueError('unknown evaluation seal')
    if not actual or actual!=seal.get('files'):raise ValueError('evaluation seal file set/hash mismatch')
    return seal


def freeze_stage(checked,out,stage,source,source_seal,workers,evidence=()):
    out.mkdir(parents=True)
    for name,value in [('config.json',checked['config']),('sample.json',checked['records']),('groups.json',checked['groups'])]:write(out/name,value)
    for path in source_paths():builder.copy_file(path,out/'source'/path.relative_to(ROOT))
    evidence_sources={str(Path(p).resolve()):sha(p) for p in evidence}
    for i,path in enumerate(evidence_sources):builder.copy_file(Path(path),out/'evidence'/f'{i}-{Path(path).name}')
    builder.copy_file(source/'seal.json',out/'input-seal.json')
    builder.copy_file(checked['built']/'seal.json',out/'build-seal.json')
    provenance=dict(build=str(checked['built']),build_seal_sha256=checked['seal_sha256'],
        prepare=str(checked['prepared']),prepare_seal_sha256=sha(checked['prepared']/'seal.json'),
        core_sha256=CORE_SHA256,database_sha256=checked['databases'])
    write(out/'provenance.json',provenance)
    write(out/'stage.json',dict(stage=stage,input=str(source),input_seal_sha256=source_seal,workers=workers))
    identity=dict(schema='r56-evaluation-identity-v1',core_sha256=CORE_SHA256,
        inputs={name:sha(out/name) for name in ('config.json','sample.json','groups.json','provenance.json','build-seal.json')},
        source_files=inventory(out/'source'),evidence_files=inventory(out/'evidence'),evidence_sources=evidence_sources)
    write(out/'identity.json',identity)
    return identity


def validate_identity(out):
    identity=read(out/'identity.json');provenance=read(out/'provenance.json');checked=validated_build(provenance['build'])
    expected=dict(build=str(checked['built']),build_seal_sha256=checked['seal_sha256'],prepare=str(checked['prepared']),
        prepare_seal_sha256=sha(checked['prepared']/'seal.json'),core_sha256=CORE_SHA256,database_sha256=checked['databases'])
    if provenance!=expected or sha(out/'build-seal.json')!=checked['seal_sha256']:raise ValueError('build/prepare provenance drift')
    if identity.get('schema')!='r56-evaluation-identity-v1' or identity.get('core_sha256')!=CORE_SHA256:raise ValueError('evaluation identity mismatch')
    for name,value in [('config.json',checked['config']),('sample.json',checked['records']),('groups.json',checked['groups'])]:
        if not builder.identical(read(out/name),value):raise ValueError('fixed evaluation input drift')
    inputs={name:sha(out/name) for name in ('config.json','sample.json','groups.json','provenance.json','build-seal.json')}
    sources={p.relative_to(ROOT).as_posix():sha(p) for p in source_paths()}
    if (identity.get('inputs')!=inputs or identity.get('source_files')!=sources or inventory(out/'source')!=sources
        or inventory(out/'evidence')!=identity.get('evidence_files')
        or any(sha(p)!=v for p,v in identity.get('evidence_sources',{}).items())):
        raise ValueError('evaluation source/input/evidence identity drift')
    return checked


def raw_accounting(payloads,*,missing_response=False):
    result=dict(observed_http_attempts=0,local_attempt_count_unknown=missing_response,remote_execution_unknown=missing_response,
        remote_execution_unknown_attempts=0,usage_complete=not missing_response,total_tokens=None,known_tokens=0,
        missing_token_usage=0,healthy_http=not missing_response)
    for payload in payloads:
        response=payload.get('response',{});http=response.get('http_attempts');count=response.get('attempt_count')
        if not isinstance(http,list):http=[];result['local_attempt_count_unknown']=True
        if type(count) is not int or count!=len(http):result['local_attempt_count_unknown']=True
        result['observed_http_attempts']+=len(http)
        healthy=(response.get('ok') is True and response.get('error')=='' and response.get('refusal') is False
            and response.get('finish_reason')=='stop' and count==1 and len(http)==1
            and response.get('raw_response')==payload.get('raw_xml')
            and response.get('raw_completion')==payload.get('raw_completion'))
        if not http:result['missing_token_usage']+=1;result['usage_complete']=False
        for attempt in http:
            result['remote_execution_unknown_attempts']+=int(attempt.get('execution_certainty')=='unknown')
            healthy &= (attempt.get('curl_code')==0 and 200<=int(attempt.get('http_status',0))<300
                        and attempt.get('execution_certainty')=='response_received')
            try:
                body=json.loads(attempt['response_body']);choice=body['choices'][0];message=choice['message']
                # Legacy native adapters may remove reasoning traces from raw_xml.
                # Keep the original completion bound to HTTP; do not duplicate that C++ transform.
                healthy &= (choice.get('finish_reason')=='stop' and not message.get('refusal')
                    and message.get('content')==payload.get('raw_completion'))
                if response.get('raw_http_response')!=attempt['response_body']:healthy=False
            except (KeyError,ValueError,TypeError,IndexError):body={};healthy=False
            try:
                usage=body['usage'];values=[usage[k] for k in ('prompt_tokens','completion_tokens','total_tokens')]
                if (not all(type(v) is int and v>=0 for v in values) or values[0]+values[1]!=values[2] or values[2]<=0
                    or any(response.get(k)!=usage[k] for k in ('prompt_tokens','completion_tokens','total_tokens'))):
                    raise ValueError('raw/native usage mismatch')
                result['known_tokens']+=values[2]
            except (KeyError,ValueError,TypeError):result['usage_complete']=False;result['missing_token_usage']+=1;healthy=False
        result['healthy_http'] &= bool(healthy)
    result['usage_complete'] &= not result['local_attempt_count_unknown']
    result['healthy_http'] &= not result['local_attempt_count_unknown']
    result['remote_execution_unknown'] |= bool(result['remote_execution_unknown_attempts'] or result['local_attempt_count_unknown'])
    if result['usage_complete']:result['total_tokens']=result['known_tokens']
    return result


class DeferredLedger:
    """Keep helper reservations durable until raw HTTP evidence determines settlement."""
    def __init__(self,ledger):self.ledger=ledger
    def reserve(self,*args):return self.ledger.reserve(*args)
    def settle(self,*args):pass
    def charge_upper(self,*args):pass


def settle_qa(ledger,reservation,accounting):
    if reservation['state']!='reserved':return 0
    upper=reservation['upper_bound'];actual=accounting['observed_http_attempts']
    if accounting['local_attempt_count_unknown'] or actual>upper:
        ledger.charge_upper(reservation['id']);return upper
    ledger.settle(reservation['id'],actual);return actual


def retrieval_accounting(row):
    invoked=row.get('native_invoked');count=row.get('embedding_requests')
    if type(invoked) is not bool:raise ValueError('retrieval native invocation evidence missing')
    if type(count) is not int or count<0:raise ValueError('native embedding count missing')
    if not invoked and (count or row.get('status')!='error' or 'recall' in row):
        raise ValueError('retrieval response/count without native invocation')
    source=row['arm']=='source10'
    if source and count:raise ValueError('source10 cannot call embedding')
    unknown=invoked and not source and row['status']=='error'
    return dict(observed_native_requests=count,raw_http_available=False,
        raw_http_detail='frozen embedding binding exposes counters and holder health only',
        token_usage_unknown=bool(count or unknown),total_tokens=None if count or unknown else 0,
        local_attempt_count_unknown=unknown,remote_execution_unknown=unknown)


def ledger_rows(path,budget):
    previous.read_ledger(path,budget)
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        return [dict(zip(('id','scope','stage','upper_bound','actual','state'),row))
            for row in db.execute('SELECT id,scope,stage,upper_bound,actual,state FROM reservations ORDER BY id')]


def reconcile_ledger(path,budget,expected):
    observed=ledger_rows(path,budget)
    if sorted(observed,key=lambda r:r['id'])!=sorted(expected,key=lambda r:r['id']):raise ValueError('per-terminal reservation/settlement mismatch')
    snapshot=previous.read_ledger(path,budget)
    if snapshot['reserved'] or snapshot['remaining']<0:raise ValueError('unfinished/over-budget ledger')
    return snapshot


def reservation_evidence(row,scope,stage,upper,actual,unknown):
    reservation=row.get('reservation',{})
    if reservation.get('state')=='blocked':
        # Both campaign budgets cover the sum of every task's maximum reservation.
        raise ValueError('fixed bounded campaign cannot contain an unreserved blocked task')
    if reservation!=dict(id=reservation.get('id'),state='reserved',upper_bound=upper) or type(reservation.get('id')) is not int:
        raise ValueError('terminal reservation identity mismatch')
    charged=upper if unknown or actual>upper else actual
    if row.get('charged_requests')!=charged:raise ValueError('terminal raw HTTP charge mismatch')
    return dict(id=reservation['id'],scope=scope,stage=stage,upper_bound=upper,
                actual=None if unknown or actual>upper else actual,state='charged_upper' if unknown or actual>upper else 'settled')


def read_retrieval_rows(out):
    return {arm:[read(path) for path in sorted((out/arm/'recalls').glob('*.json'))] for arm in ARMS}


def validate_context(core,record,row,plans,source_engrams,statement_reader):
    """Use native packet parsing and native row rendering; compare original SourceTurn evidence."""
    recall=row['recall'];packet=json.loads(core.grounded_memory_answer_packet(record['question'],json.dumps(recall,ensure_ascii=False)))
    for source in packet['sources']:
        ref=source['source_ref'];holder=ref['speaker'];holder_plan=plans['holders'].get(holder)
        if holder_plan is None or source_engrams.get(holder)!=ref.get('engram_ref'):raise ValueError('context source holder/engram mismatch')
        unit=next((u for u in holder_plan['source_units'] if u['clause_id']==ref.get('clause_id')),None)
        if unit is None or source['text']!=unit['utterance']:raise ValueError('context source text/clause mismatch')
        for key in ('speaker','session_id','turn_id','turn_index','observed_at','raw_observed_at','time_status'):
            if key in unit and ref.get(key)!=unit[key]:raise ValueError('context SourceTurn metadata mismatch')
    for statement in packet['statements']:
        stored=statement_reader(statement['statement_id'])
        label=getattr(core.ContextPackLabel,statement['label'],None)
        if label is None:raise ValueError('unknown native context statement label')
        if stored is None or core.render_context_line(stored,label)!=statement['text']:
            raise ValueError('context statement differs from native database rendering')


def retrieval_inventory(checked,rows,*,require_healthy=False):
    records=checked['records'];groups=checked['groups'];config=checked['config']
    indexed={r['item_id']:r for r in records};by_item={r['item_id']:g['group_id'] for g in groups for r in g['records']}
    if set(rows)!=set(ARMS):raise ValueError('retrieval arms mismatch')
    for arm,receipts in rows.items():
        ids=[r.get('item_id') for r in receipts]
        if len(ids)!=len(indexed) or set(ids)!=set(indexed):raise ValueError('retrieval duplicate/missing items')
        for row in receipts:
            record=indexed[row['item_id']];gid=by_item[row['item_id']]
            if row.get('group_id')!=gid or row.get('holders')!=baseline.history_holders(record['history']):
                raise ValueError('retrieval group/holder mismatch')
            ablation.validate_row(row,arm,checked['databases'][gid],CORE_SHA256,config['max_context_bytes'])
            if require_healthy and not ablation.healthy_embedding(row):raise ValueError('retrieval is not healthy enough for QA')
    return indexed,by_item


def verify_contexts(checked,rows,modules,errors=None):
    core,runtime=modules[:2];records={r['item_id']:r for r in checked['records']}
    with tempfile.TemporaryDirectory(prefix='r56-context-proof-') as temporary:
        for group in checked['groups']:
            gid=group['group_id'];target=Path(temporary)/(gid+'.db')
            shutil.copyfile(checked['built']/'runs'/gid/'frozen.db',target)
            rt=runtime._build_local_store_sqlite_runtime(target);rt.start()
            try:
                for row in [r for arm in ARMS for r in rows[arm] if r['group_id']==gid and r['status']!='error' and 'recall' in r]:
                    try:
                        validate_context(core,records[row['item_id']],row,checked['plans']['scopes'][gid],
                            checked['summary']['health'][gid]['database_proof']['source_engrams'],
                            lambda sid:core.get_statement_row(rt.adapter,'default',sid))
                    except Exception as exc:
                        if errors is None:raise
                        errors.append(dict(task=row['arm']+'/'+row['item_id'],error=f'{type(exc).__name__}: {exc}'))
            finally:
                stop=getattr(rt,'stop',None)
                if callable(stop):stop()


def retrieval_summary(out,checked,rows):
    retrieval_inventory(checked,rows);reservations=[];health=0;requests=0;unknown=False
    records={r['item_id']:r for r in checked['records']}
    for arm in ARMS:
        for row in rows[arm]:
            accounting=retrieval_accounting(row)
            if row.get('accounting')!=accounting:raise ValueError('retrieval accounting drift')
            upper=len(baseline.history_holders(records[row['item_id']]['history'])) if arm=='baseline' else 0
            expected=reservation_evidence(row,arm+'/'+row['item_id'],'query_embedding',upper,
                accounting['observed_native_requests'],accounting['local_attempt_count_unknown'])
            if expected:reservations.append(expected)
            requests+=accounting['observed_native_requests'];unknown|=accounting['local_attempt_count_unknown']
            health+=int(ablation.healthy_embedding(row))
    ledger=reconcile_ledger(out/'request-ledger.sqlite',RETRIEVAL_BUDGET,reservations)
    healthy=health==266
    if healthy and requests!=1336:raise ValueError('healthy retrieval native count must be 1336')
    return dict(stage='retrieve',state='complete' if healthy else 'incomplete',questions=133,terminal_count=266,
        healthy_terminals=health,qa_gate='passed_technical_health' if healthy else 'blocked_technical_health',
        gate_uses_anchor_scores=False,ledger=ledger,embedding_requests=requests,source10_embedding_requests=0,
        embedding_raw_http_available=False,embedding_token_usage_unknown=bool(requests or unknown),
        total_tokens=None if requests or unknown else 0,local_attempt_count_unknown=unknown,
        database_sha256=checked['databases'],unexecuted_stages=['qa'])


def qa_accounting(task,row):
    invoked=row.get('native_invoked')
    if type(invoked) is not bool:raise ValueError('QA native invocation evidence missing')
    payloads=[row[name] for name in ('answer','judge') if isinstance(row.get(name),dict)]
    if not invoked:
        if payloads:raise ValueError('QA response without native invocation')
        return raw_accounting([])
    missing='answer' not in row or any(not p.get('response',{}).get('http_attempts') for p in payloads)
    answer=row.get('answer',{})
    expected_judge=(task['record'].get('answer_format','multiple_choice')!='multiple_choice'
        and answer.get('response',{}).get('ok') is True and not answer.get('response',{}).get('error')
        and bool(answer.get('raw_xml','').strip()) and answer.get('response',{}).get('attempt_count')==1)
    missing |= bool(expected_judge and 'judge' not in row)
    return raw_accounting(payloads,missing_response=missing)


def qa_verdict(task,row,modules):
    accounting=qa_accounting(task,row)
    if row.get('reservation',{}).get('state')=='blocked':return 'budget_failure',False,None,accounting
    if not row['native_invoked'] or not accounting['healthy_http']:return 'technical_failure',False,None,accounting
    answer=row.get('answer',{});text=answer.get('raw_xml','').strip()
    if not text:return 'answer_failure',False,None,accounting
    record=task['record']
    if record.get('answer_format','multiple_choice')=='multiple_choice':
        try:prediction=modules[5]._parse_option_index(text,len(record['options']))
        except (ValueError,TypeError):prediction=None
        if prediction is None:return 'invalid_answer',False,None,accounting
        return 'ok',prediction==int(record['answer']),prediction,accounting
    if not row.get('judge',{}).get('raw_xml','').strip():return 'judge_failure',False,None,accounting
    return 'ok',bool(modules[2]._parse_judge_verdict(row['judge']['raw_xml'].strip())),None,accounting


def validate_qa_binding(task,row,modules):
    for name in ('item_id','arm','policy','prompt','prompt_sha256','context_sha256'):
        if row.get(name)!=task[name]:raise ValueError('QA native prompt/context/task binding mismatch: '+name)
    if row.get('terminal') is not True or row.get('fresh') is not True:raise ValueError('QA must contain fresh terminal evidence')
    record=task['record'];answer=row.get('answer',{})
    if 'judge_prompt' in row or 'judge' in row:
        if record.get('answer_format','multiple_choice')=='multiple_choice' or not answer:
            raise ValueError('unexpected judge response/prompt')
        expected=modules[2]._judge_prompt(str(record['question']),str(record['answer']),answer['raw_xml'].strip())
        if row.get('judge_prompt')!=expected or row.get('judge_prompt_sha256')!=text_sha(expected):
            raise ValueError('judge prompt differs from frozen question/gold and raw answer')


def validate_qa_terminal(task,row,modules):
    validate_qa_binding(task,row,modules);record=task['record']
    status,correct,prediction,accounting=qa_verdict(task,row,modules)
    if (row.get('status')!=status or type(row.get('correct')) is not bool or row['correct']!=correct
        or row.get('prediction')!=prediction or row.get('accounting')!=accounting):
        raise ValueError('QA raw response status/score/usage mismatch')
    upper=1+int(record.get('answer_format','multiple_choice')!='multiple_choice')
    return reservation_evidence(row,f"{task['arm']}/{task['policy']}/{task['item_id']}",'answer_judge',upper,
        accounting['observed_http_attempts'],accounting['local_attempt_count_unknown'])


def qa_summary(out,records,rows,tasks,modules,*,repetitions=100000):
    previous.validate_terminal_inventory(records,rows)
    taskmap={(t['item_id'],t['arm'],t['policy']):t for t in tasks};reservations=[]
    for row in rows:
        expected=validate_qa_terminal(taskmap[(row['item_id'],row['arm'],row['policy'])],row,modules)
        if expected:reservations.append(expected)
    ledger=reconcile_ledger(out/'request-ledger.sqlite',QA_BUDGET,reservations)
    rows=sorted(rows,key=lambda r:(r['item_id'],r['arm'],r['policy']));policies={}
    for policy in POLICIES:
        selected=[r for r in rows if r['policy']==policy];pairs={a:[r for r in selected if r['arm']==a] for a in ARMS}
        comparison=previous.compare_scores(records,pairs['baseline'],pairs['source10'],repetitions=repetitions)
        comparison['breakdowns']=previous._breakdowns(records,selected)
        comparison['arms']={a:dict(questions=133,correct=sum(r['correct'] for r in pairs[a]),
            ok=sum(r['status']=='ok' for r in pairs[a]),status_counts=dict(Counter(r['status'] for r in pairs[a]))) for a in ARMS}
        policies[policy]=comparison
    accounting=[r['accounting'] for r in rows];complete=all(a['usage_complete'] for a in accounting)
    return dict(stage='qa',state='complete',questions=133,terminal_count=532,terminal_inventory_complete=True,
        healthy_terminals=sum(r['status']=='ok' for r in rows),status_counts=dict(Counter(r['status'] for r in rows)),
        policies=policies,primary_endpoint='grounded_memory_v1_all_question_accuracy_gain',
        eligible_for_expanded_development=policies['grounded_memory_v1']['eligible_for_expanded_development'],automatic_promotion=False,
        ledger=ledger,observed_http_attempts=sum(a['observed_http_attempts'] for a in accounting),
        total_tokens=sum(a['known_tokens'] for a in accounting) if complete else None,
        known_tokens=sum(a['known_tokens'] for a in accounting),usage_complete=complete,
        missing_token_usage=sum(a['missing_token_usage'] for a in accounting),
        local_attempt_count_unknown=any(a['local_attempt_count_unknown'] for a in accounting),
        remote_execution_unknown=any(a['remote_execution_unknown'] for a in accounting),
        judge_flip_audit=previous.judge_flip_audit(rows),
        interpretation='133 additional historically used development questions; historical 57 excluded; no automatic promotion')


def make_tasks(checked,rows,runner,modules):
    indexed={a:{r['item_id']:r['recall'] for r in rows[a]} for a in ARMS}
    tasks=[qa_helpers.build_task(arm,policy,record,indexed[arm][record['item_id']],runner,checked['config'],modules)
           for record in checked['records'] for policy in POLICIES for arm in ARMS]
    if len(tasks)!=532 or sum(1+int(t['record'].get('answer_format','multiple_choice')!='multiple_choice') for t in tasks)!=956:
        raise ValueError('fixed fresh QA task inventory/budget mismatch')
    return tasks


def execution_plan(stage,workers,checked,tasks=()):
    common=dict(stage=stage,workers=workers,core_sha256=CORE_SHA256,runtime_prepare=str(checked['prepared']),
                database_sha256=checked['databases'])
    if stage=='retrieve':return dict(**common,arms={a:list(ablation.ARMS[a]) for a in ARMS},
        questions=133,tasks=266,http_budget=1336,source10_embedding_requests=0,answer_requests=0,judge_requests=0,per_query_copy=True)
    return dict(**common,arms=list(ARMS),policies=list(POLICIES),questions=133,tasks=532,http_budget=956,fresh=True,
        answer_model='qwen3.8-27b',answer_max_tokens=512,answer_enable_thinking=False,judge_max_tokens=64,
        judge_enable_thinking='provider_default_unset',max_retries=0,timeout_ms=120000,embedding_requests=0,
        bootstrap_seed=20260925,bootstrap_repetitions=100000,
        tasks_binding=[{k:t[k] for k in ('item_id','arm','policy','prompt_sha256','context_sha256')} for t in tasks])


def failure_task_specs(checked,stage):
    """Fixed task identities without constructing native prompts or providers."""
    specs={}
    for group in checked['groups']:
        for record in group['records']:
            item=record['item_id']
            for arm in ARMS:
                for policy in POLICIES if stage=='qa' else (None,):
                    scope='/'.join(filter(None,(arm,policy,item)))
                    path=(Path('answers')/policy/arm if policy else Path(arm)/'recalls')/(text_sha(item)+'.json')
                    upper=(1+int(record.get('answer_format','multiple_choice')!='multiple_choice') if policy else
                           len(baseline.history_holders(record['history'])) if arm=='baseline' else 0)
                    specs[scope]=dict(path=path,record=record,group_id=group['group_id'],arm=arm,policy=policy,
                        upper_bound=upper,stage='answer_judge' if policy else 'query_embedding')
    return specs


def failure_audit(out,checked,runner=None,modules=None,parent_rows=None):
    """Read surviving receipts and ledger independently; never synthesize terminal scores."""
    stage_info=read(out/'stage.json');stage=stage_info['stage'];specs=failure_task_specs(checked,stage)
    budget=QA_BUDGET if stage=='qa' else RETRIEVAL_BUDGET
    paths={spec['path'].as_posix():scope for scope,spec in specs.items()}
    saved=sorted((out/'answers').glob('*/*/*')) if stage=='qa' else sorted(out.glob('*/recalls/*'))
    saved=[p for p in saved if p.is_file()];invalid=[];receipts={};accountings={};valid=[];partial=[]
    ledger_path=out/'request-ledger.sqlite';ledger=None;reservations=[];by_scope={};ledger_unknown=False
    if ledger_path.exists():
        try:
            ledger=previous.read_ledger(ledger_path,budget);reservations=ledger_rows(ledger_path,budget)
            if ledger['remaining']<0:raise ValueError('over-budget failure ledger')
            for reservation in reservations:
                scope=reservation['scope'];spec=specs.get(scope)
                if (spec is None or scope in by_scope or reservation['stage']!=spec['stage']
                    or reservation['upper_bound']!=spec['upper_bound']
                    or reservation['state']!='settled' and reservation['actual'] is not None):
                    raise ValueError('failure ledger task/stage/bound/settlement mismatch')
                by_scope[scope]=reservation
        except Exception as exc:
            ledger_unknown=True;invalid.append(dict(task='ledger',error=f'{type(exc).__name__}: {exc}'))
    elif saved or (out/'execution-plan.json').exists():
        ledger_unknown=True;invalid.append(dict(task='ledger',error='execution plan or saved receipts without request ledger'))
    tasks={}
    if saved or (stage=='qa' and (out/'execution-plan.json').exists()):
        if modules is None:runner,modules=runtime_modules(checked)
        if stage=='qa':
            if parent_rows is None:parent_rows=read_retrieval_rows(Path(stage_info['input']))
            tasks={f"{t['arm']}/{t['policy']}/{t['item_id']}":t for t in make_tasks(checked,parent_rows,runner,modules)}
    plan_path=out/'execution-plan.json'
    if plan_path.exists():
        expected=execution_plan(stage,stage_info['workers'],checked,list(tasks.values()))
        if read(plan_path)!=expected:invalid.append(dict(task='execution-plan',error='native execution plan/binding mismatch'))
    elif reservations or saved:invalid.append(dict(task='execution-plan',error='missing execution plan for started tasks'))
    context_rows={arm:[] for arm in ARMS}
    for path in saved:
        relative=path.relative_to(out).as_posix();scope=paths.get(relative)
        if scope is None:
            invalid.append(dict(task=relative,error='unexpected receipt path'));continue
        spec=specs[scope]
        try:row=read(path);receipts[scope]=row
        except Exception as exc:
            receipts[scope]=None;invalid.append(dict(task=scope,error=f'{type(exc).__name__}: {exc}'));continue
        try:
            reservation=by_scope.get(scope)
            if reservation is None:raise ValueError('saved receipt without matching ledger reservation')
            expected_reservation=dict(id=reservation['id'],state='reserved',upper_bound=spec['upper_bound'])
            retrieval_partial=(stage=='retrieve' and all(k not in row for k in
                ('reservation','native_invoked','accounting','charged_requests')))
            if not retrieval_partial and row.get('reservation')!=expected_reservation:raise ValueError('receipt reservation identity mismatch')
            if stage=='qa':
                task=tasks[scope]
                is_partial=('native_invoked' not in row and 'accounting' not in row
                    and all(k in row for k in ('native_attempt_count','tokens','charged_requests')))
                if is_partial:
                    validate_qa_binding(task,row,modules)
                    # The old helper durably writes before the wrapper settles and rewrites.
                    # Its raw receipt is inspectable, but never promoted to a final R5.6 task.
                    normalized=dict(row,native_invoked=True)
                    status,correct,prediction,accounting=qa_verdict(task,normalized,modules)
                    if (type(row.get('correct')) is not bool or (row['correct'] and not correct)
                        or row.get('status')=='ok' and (status!='ok' or row['correct']!=correct
                            or row.get('prediction')!=prediction)):
                        raise ValueError('partial helper raw response score contradiction')
                    partial.append(scope)
                    actual=accounting['observed_http_attempts'];unknown=accounting['local_attempt_count_unknown']
                    if reservation['state']=='settled' and (unknown or reservation['actual']!=actual):
                        raise ValueError('partial receipt raw HTTP/settlement mismatch')
                else:
                    expected=validate_qa_terminal(task,row,modules);accounting=row['accounting']
                    if reservation!=expected:raise ValueError('terminal reservation/settlement mismatch')
                    valid.append(scope)
            else:
                if (row.get('item_id')!=spec['record']['item_id'] or row.get('group_id')!=spec['group_id']
                    or row.get('holders')!=baseline.history_holders(spec['record']['history'])):
                    raise ValueError('retrieval task/group/holder mismatch')
                ablation.validate_row(row,spec['arm'],checked['databases'][spec['group_id']],CORE_SHA256,
                                      checked['config']['max_context_bytes'])
                accounting=retrieval_accounting(dict(row,native_invoked=True) if retrieval_partial else row)
                if retrieval_partial:
                    if reservation['state']=='settled' and (accounting['local_attempt_count_unknown']
                        or reservation['actual']!=accounting['observed_native_requests']):
                        raise ValueError('partial native request/settlement mismatch')
                    partial.append(scope)
                else:
                    if row.get('accounting')!=accounting:raise ValueError('retrieval accounting drift')
                    expected=reservation_evidence(row,scope,spec['stage'],spec['upper_bound'],
                        accounting['observed_native_requests'],accounting['local_attempt_count_unknown'])
                    if reservation!=expected:raise ValueError('terminal reservation/settlement mismatch')
                    valid.append(scope)
                context_rows[spec['arm']].append(row)
            accountings[scope]=accounting
        except Exception as exc:
            invalid.append(dict(task=scope,error=f'{type(exc).__name__}: {exc}'))
            # Keep observed raw usage even when identity/verdict evidence is invalid.
            try:
                accountings[scope]=(qa_accounting(tasks[scope],dict(row,native_invoked=True)) if stage=='qa'
                    else retrieval_accounting(row))
            except Exception:pass
    if stage=='retrieve' and any(context_rows.values()):verify_contexts(checked,context_rows,modules,invalid)
    bad={entry['task'] for entry in invalid};valid=sorted(set(valid)-bad);partial=sorted(set(partial)-bad)
    missing=sorted(set(specs)-set(receipts));unstarted=[] if ledger_unknown else sorted(set(specs)-set(by_scope)-set(receipts))
    unverified=sorted(scope for scope in by_scope if scope not in set(valid)|set(partial))
    unresolved=[r for r in reservations if r['state']=='reserved']
    unknown_tasks=sorted(scope for scope,spec in specs.items() if spec['upper_bound'] and scope in by_scope and
        (scope not in accountings or scope in bad or accountings[scope]['local_attempt_count_unknown']))
    accounting=list(accountings.values());known=sum(a.get('known_tokens',0) for a in accounting)
    usage_complete=not unknown_tasks and not invalid and all(a.get('usage_complete',not a.get('token_usage_unknown',False)) for a in accounting)
    return dict(stage=stage,state='incomplete',artifact_state='incomplete',evidence_valid=not invalid,
        exception_sha256=sha(out/'exception.txt'),expected_task_count=len(specs),validated_terminal_count=len(valid),
        validated_terminal_tasks=valid,partial_receipt_tasks=partial,missing_receipt_tasks=missing,unstarted_tasks=unstarted,
        ledger_identity_unknown=ledger_unknown,start_state_unknown_tasks=missing if ledger_unknown else [],
        invalid_evidence=invalid,unverified_settlement_tasks=unverified,unresolved_reservations=unresolved,
        unknown_request_tasks=unknown_tasks,ledger=ledger,ledger_reservations=reservations,
        observed_http_attempts=sum(a.get('observed_http_attempts',0) for a in accounting),
        observed_native_requests=sum(a.get('observed_native_requests',0) for a in accounting),
        raw_http_available=stage=='qa',known_tokens=known,total_tokens=known if usage_complete else None,
        usage_complete=usage_complete,missing_token_usage=sum(a.get('missing_token_usage',0) for a in accounting),
        local_attempt_count_unknown=ledger_unknown or bool(unknown_tasks),
        remote_execution_unknown=ledger_unknown or bool(unknown_tasks) or any(a.get('remote_execution_unknown',False) for a in accounting),
        automatic_promotion=False,retry='refuse overwrite; no automatic replay')


def fail_stage(out,stage,exc,ledger,checked,runner,modules,parent_rows=None):
    if out.exists() and not (out/'seal.json').exists():
        (out/'exception.txt').write_text(traceback.format_exc())
        if ledger:
            try:pending=ledger_rows(out/'request-ledger.sqlite',QA_BUDGET if stage=='qa' else RETRIEVAL_BUDGET)
            except Exception:pending=[]  # The read-only audit reports an unreadable ledger explicitly.
            for row in pending:
                if row['state']=='reserved':
                    try:ledger.charge_upper(row['id'])
                    except Exception:pass  # Preserve the durable reservation as explicitly unresolved.
        summary=failure_audit(out,checked,runner,modules,parent_rows)
        write(out/'failure-summary.json',summary);write(out/'summary.json',summary);seal_output(out,stage,'incomplete')


def validate_workers(workers):
    if type(workers) is not int or not 1<=workers<=4:raise ValueError('workers must be 1..4')


def retrieve(built,out,workers=4,evidence=()):
    out=builder.new_output(out);validate_workers(workers);checked=validated_build(built);built=checked['built'];ledger=None;runner=modules=None
    try:
        freeze_stage(checked,out,'retrieve',built,checked['seal_sha256'],workers,evidence)
        runner,modules=runtime_modules(checked);core,runtime,_,_,pipeline,_=modules
        ledger=runner.BudgetLedger(out/'request-ledger.sqlite',RETRIEVAL_BUDGET)
        write(out/'execution-plan.json',execution_plan('retrieve',workers,checked))
        tasks=[]
        for group in checked['groups']:
            for record in group['records']:
                for arm in ARMS:
                    try:
                        embedder=(previous.previous._build_embedder(core,checked['config'],'dashscope') if arm=='baseline'
                                  else core.StubEmbeddingAdapter(checked['config']['embedding_dim']))
                        error=None
                    except Exception as exc:embedder=None;error=f'{type(exc).__name__}: {exc}'
                    tasks.append(((group['group_id'],record,arm,embedder),error))
        def execute(entry):
            task,creation_error=entry;gid,record,arm,embedder=task;strategy,mode,k=ablation.ARMS[arm]
            upper=len(baseline.history_holders(record['history'])) if arm=='baseline' else 0
            reservation=ledger.reserve(arm+'/'+record['item_id'],'query_embedding',upper)
            row=dict(item_id=record['item_id'],group_id=gid,arm=arm,strategy=strategy,mode=mode,k=k,
                holders=baseline.history_holders(record['history']),database_sha256=checked['databases'][gid],core_sha256=CORE_SHA256,
                terminal=True,status='error',embedding_requests=0,native_invoked=False)
            invoked=False
            try:
                if reservation['state']!='reserved':raise RuntimeError('retrieval budget exhausted')
                if creation_error:raise RuntimeError(creation_error)
                invoked=True
                row=ablation.query_one(task,built,out,dict(database_sha256=checked['databases']),checked['config'],core,runtime,pipeline)
            except Exception as exc:
                row.update(status='error',error=f'{type(exc).__name__}: {exc}',embedding_requests=int(getattr(embedder,'request_count',0)))
            row.update(reservation=reservation,native_invoked=invoked)
            accounting=retrieval_accounting(row);row['accounting']=accounting
            if reservation['state']=='reserved':
                if accounting['local_attempt_count_unknown'] or accounting['observed_native_requests']>upper:
                    ledger.charge_upper(reservation['id']);row['charged_requests']=upper
                else:ledger.settle(reservation['id'],accounting['observed_native_requests']);row['charged_requests']=accounting['observed_native_requests']
            else:row['charged_requests']=0
            write(out/arm/'recalls'/(text_sha(record['item_id'])+'.json'),row)
            return row
        rows={a:[] for a in ARMS}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for future in as_completed([pool.submit(execute,task) for task in tasks]):
                row=future.result();rows[row['arm']].append(row)
                count=sum(map(len,rows.values()))
                if count%20==0:print(f'retrieval terminals: {count}/266',flush=True)
        retrieval_inventory(checked,rows);verify_contexts(checked,rows,modules)
        summary=retrieval_summary(out,checked,rows)
        if summary['state']=='complete':write(out/'comparison.json',previous.retrieval_comparison(checked['records'],rows))
        validate_identity(out);builder.validate_loaded(checked['prepared'],checked['identity'])
        if sha(built/'seal.json')!=checked['seal_sha256']:raise ValueError('build seal changed during retrieval')
        write(out/'summary.json',summary);seal_output(out,'retrieve',summary['state'])
        return summary
    except BaseException as exc:fail_stage(out,'retrieve',exc,ledger,checked,runner,modules);raise


def execute_qa(task,out,runner,modules,ledger,adapters,creation_error=None):
    if adapters is None:
        upper=1+int(task['record'].get('answer_format','multiple_choice')!='multiple_choice')
        reservation=ledger.reserve(f"{task['arm']}/{task['policy']}/{task['item_id']}",'answer_judge',upper)
        row={k:task[k] for k in ('item_id','arm','policy','prompt','prompt_sha256','context_sha256')}
        row.update(terminal=True,fresh=True,reservation=reservation,native_invoked=False,error=creation_error or 'provider construction failed')
    else:
        row=qa_helpers.run_task(task,out,runner,modules,DeferredLedger(ledger),adapters)
        row['native_invoked']=row['reservation']['state']=='reserved'
    status,correct,prediction,accounting=qa_verdict(task,row,modules)
    for key in ('tokens','native_attempt_count','budget_unknown'):row.pop(key,None)
    row.update(status=status,correct=correct,prediction=prediction,accounting=accounting)
    row['charged_requests']=settle_qa(ledger,row['reservation'],accounting)
    write(out/row['policy']/row['arm']/(text_sha(row['item_id'])+'.json'),row)
    return row


def qa(contexts,out,workers=4,evidence=()):
    out=builder.new_output(out);validate_workers(workers);contexts=Path(contexts).resolve();parent=check(contexts,'retrieve')
    checked=parent['build'];ledger=None;runner=modules=None
    try:
        freeze_stage(checked,out,'qa',contexts,parent['seal_sha256'],workers,evidence)
        for arm in ARMS:shutil.copytree(contexts/arm/'recalls',out/'input-recalls'/arm)
        runner,modules=runtime_modules(checked);tasks=make_tasks(checked,parent['rows'],runner,modules)
        write(out/'execution-plan.json',execution_plan('qa',workers,checked,tasks))
        ledger=runner.BudgetLedger(out/'request-ledger.sqlite',QA_BUDGET);adapters=queue.Queue()
        for _ in range(workers):
            try:adapters.put((runner._make_native_adapters(modules[0],checked['config']),None))
            except Exception as exc:adapters.put((None,f'{type(exc).__name__}: {exc}'))
        def execute(task):
            pair,error=adapters.get()
            try:return execute_qa(task,out/'answers',runner,modules,ledger,pair,error)
            finally:adapters.put((pair,error))
        rows=[]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for future in as_completed([pool.submit(execute,task) for task in tasks]):
                rows.append(future.result())
                if len(rows)%20==0:print(f'QA terminals: {len(rows)}/532',flush=True)
        summary=qa_summary(out,checked['records'],rows,tasks,modules)
        validate_identity(out);builder.validate_loaded(checked['prepared'],checked['identity']);verify_seal(contexts)
        if sha(contexts/'seal.json')!=parent['seal_sha256']:raise ValueError('retrieval input changed during QA')
        write(out/'summary.json',summary);seal_output(out,'qa')
        return summary
    except BaseException as exc:fail_stage(out,'qa',exc,ledger,checked,runner,modules,parent['rows']);raise


def check(out,expected_stage=None):
    out=Path(out).resolve();seal=verify_seal(out);stage=read(out/'stage.json')
    if stage.get('stage')!=seal['stage'] or stage['stage'] not in ('retrieve','qa'):raise ValueError('evaluation stage mismatch')
    validate_workers(stage.get('workers'))
    if expected_stage and (stage['stage']!=expected_stage or seal['state']!='complete'):raise ValueError('incomplete or incorrect evaluation input')
    checked=validate_identity(out);source=Path(stage['input']).resolve()
    if source==out:raise ValueError('cyclic stage input')
    parent=None
    if stage['stage']=='retrieve':
        if source!=checked['built']:raise ValueError('retrieval requires fixed build input')
        digest=checked['seal_sha256']
    else:
        parent=check(source,'retrieve');digest=parent['seal_sha256']
        if parent['build']['seal_sha256']!=checked['seal_sha256']:raise ValueError('QA build input mismatch')
        for arm in ARMS:
            if inventory(out/'input-recalls'/arm)!=inventory(source/arm/'recalls'):raise ValueError('QA input recall copy drift')
    if stage.get('input_seal_sha256')!=digest or sha(out/'input-seal.json')!=digest:raise ValueError('stage input seal mismatch')
    if (out/'failure-summary.json').exists():
        summary=failure_audit(out,checked,parent_rows=parent['rows'] if parent else None)
        if (seal['state']!='incomplete' or not builder.identical(read(out/'summary.json'),summary)
            or not builder.identical(read(out/'failure-summary.json'),summary)):
            raise ValueError('recomputed failure audit summary mismatch')
        builder.validate_loaded(checked['prepared'],checked['identity']);verify_seal(out)
        return dict(stage=stage['stage'],build=checked,rows=[],summary=summary,seal_sha256=sha(out/'seal.json'))
    runner,modules=runtime_modules(checked)
    if stage['stage']=='retrieve':
        rows=read_retrieval_rows(out);retrieval_inventory(checked,rows)
        verify_contexts(checked,rows,modules);summary=retrieval_summary(out,checked,rows)
        plan=execution_plan('retrieve',stage['workers'],checked)
        if summary['state']=='complete' and read(out/'comparison.json')!=previous.retrieval_comparison(checked['records'],rows):
            raise ValueError('anchor diagnostic drift')
    else:
        tasks=make_tasks(checked,parent['rows'],runner,modules)
        rows=[read(path) for path in sorted((out/'answers').glob('*/*/*.json'))]
        summary=qa_summary(out,checked['records'],rows,tasks,modules);plan=execution_plan('qa',stage['workers'],checked,tasks)
    if (read(out/'execution-plan.json')!=plan or not builder.identical(read(out/'summary.json'),summary)
        or seal['state']!=summary['state']):raise ValueError('recomputed evaluation plan/summary mismatch')
    builder.validate_loaded(checked['prepared'],checked['identity']);verify_seal(out)
    return dict(stage=stage['stage'],build=checked,rows=rows,summary=summary,seal_sha256=sha(out/'seal.json'))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);stages=parser.add_subparsers(dest='stage',required=True)
    for name in ('retrieve','qa'):
        p=stages.add_parser(name);p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
        p.add_argument('--workers',type=int,default=4);p.add_argument('--evidence',type=Path,action='append',default=[])
    p=stages.add_parser('check');p.add_argument('--input',type=Path,required=True)
    args=parser.parse_args(argv)
    result=check(args.input)['summary'] if args.stage=='check' else globals()[args.stage](args.input,args.out,args.workers,args.evidence)
    print(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False));return int(result['state']!='complete')


if __name__=='__main__':raise SystemExit(main())
