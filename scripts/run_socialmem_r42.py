#!/usr/bin/env python3
"""R4.2 固定 57 题：主体优先检索一次、冻结上下文、交替双臂，禁止重试。"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import shutil
import sqlite3
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'build/socialmem_20260921_structured_eval_hybrid_holder_isolation_r35_dashscope'
PARENT_CORE='9d23b3d699653b81b1ef07160a9ad2b8ebd5a1a7f81f1e256ef83f50e0bf853a'
ARMS=('retrieval','native_answer')
BUDGET=600

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(temp,path)
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def candidate_config(parent,core):
    return {**parent,'arm':'r42_support_lane','core_sha256':core,'source_strategy':'evidence_profile_v4',
            'answer_policy':'legacy','http_budget':BUDGET}

def validate_config(parent,candidate):
    digest=candidate.get('core_sha256','')
    if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest) or candidate!=candidate_config(parent,digest):
        raise ValueError('R4 configuration drift')

def task_order(records):
    if len({r['item_id'] for r in records})!=len(records):raise ValueError('duplicate items')
    return [{'item_id':r['item_id'],'arm':ARMS[(i+j)%2],'position':j,'question_order':i}
            for i,r in enumerate(records) for j in range(2)]
def task_id(task):return hashlib.sha256((task['item_id']+'|'+task['arm']).encode()).hexdigest()
def item_id(key):return hashlib.sha256(key.encode()).hexdigest()

def anchor_coverage(record,recall):
    anchors=record.get('source',{}).get('evidence_anchors',[])
    refs={(r.get('speaker'),r.get('turn_id')) for r in recall.get('source_refs',[])}
    return {'total':len(anchors),'source_hits':sum(bool(a.get('turn_id')) and
        (a.get('speaker_display_name'),a.get('turn_id')) in refs for a in anchors)}

def interval(records,differences):
    if not records:return None
    groups=defaultdict(list)
    for r,d in zip(records,differences,strict=True):groups[r['source']['network_id']].append(d)
    cells=[(sum(v),len(v)) for _,v in sorted(groups.items())]
    rng=random.Random(20260921);draws=[]
    for _ in range(100000):
        sample=[rng.choice(cells) for _ in cells]
        draws.append(100*sum(s for s,n in sample)/sum(n for s,n in sample))
    draws.sort()
    def quantile(q):
        pos=q*(len(draws)-1);i=int(pos);return draws[i]+(draws[min(i+1,len(draws)-1)]-draws[i])*(pos-i)
    return [quantile(.025),quantile(.975)]

def paired(records,left,right):
    pairs=[(int(left[r['item_id']]['correct']),int(right[r['item_id']]['correct'])) for r in records]
    changes=[b-a for a,b in pairs]
    return {'n':len(records),'left_correct':sum(a for a,b in pairs),'right_correct':sum(b for a,b in pairs),
        'net_change':sum(changes),'delta_pp':100*sum(changes)/len(records) if records else None,
        'new_correct':sum(a==0 and b==1 for a,b in pairs),'regressed':sum(a==1 and b==0 for a,b in pairs),
        'network_bootstrap_95ci_pp':interval(records,changes),'bootstrap_samples':100000,'bootstrap_seed':20260921}

def analyze_rows(records,rows):
    wanted={(r['item_id'],a) for r in records for a in ARMS};keys=[(r['item_id'],r['arm']) for r in rows]
    if len({r['item_id'] for r in records})!=len(records) or len(keys)!=len(set(keys)) or set(keys)!=wanted:
        raise ValueError('incomplete or duplicate task set')
    if any(r.get('terminal') is not True or type(r.get('correct')) is not bool or
           r.get('status') not in ('ok','answer_failure','judge_failure','invalid_answer','query_failure') or
           (r['status']!='ok' and r['correct']) for r in rows):raise ValueError('invalid result')
    by={a:{r['item_id']:r for r in rows if r['arm']==a} for a in ARMS}
    def summary(rs,arm):
        result=[by[arm][r['item_id']] for r in rs]
        return {'n':len(result),'correct':sum(r['correct'] for r in result),
                'accuracy':sum(r['correct'] for r in result)/len(result) if result else None,
                'status_counts':dict(Counter(r['status'] for r in result))}
    normal=[r for r in records if all(by[a][r['item_id']]['status']=='ok' for a in ARMS)]
    return {'arms':{a:summary(records,a) for a in ARMS},'paired':paired(records,by[ARMS[0]],by[ARMS[1]]),
        'common_normal':paired(normal,by[ARMS[0]],by[ARMS[1]]),
        'by_format':{v:{a:summary([r for r in records if r.get('answer_format')==v],a) for a in ARMS}
                     for v in sorted({r.get('answer_format','') for r in records})},
        'by_query_type':{v:{a:summary([r for r in records if r.get('query_type')==v],a) for a in ARMS}
                     for v in sorted({r.get('query_type','') for r in records})},'promoted':False}

def files_in(folder):
    return {str(p.relative_to(folder)):sha(p) for p in sorted(Path(folder).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}

def parent_inputs(parent):
    config=read(parent/'config.json');identity=read(parent/'identity.json')
    if config['core_sha256']!=PARENT_CORE or identity['core_sha256']!=PARENT_CORE:
        raise ValueError('unexpected R3.5 parent core')
    for rel,key in [('corpus.jsonl','corpus_sha256'),('config.json','config_sha256'),('scope-manifest.json','scope_manifest_sha256')]:
        if sha(parent/rel)!=identity[key]:raise ValueError('parent identity drift: '+rel)
    core_files=list((parent/'frozen/python/starling').glob('_core*.so'))
    if len(core_files)!=1 or sha(core_files[0])!=PARENT_CORE:raise ValueError('parent core artifact mismatch')
    runner=load(parent/'frozen/scripts/run_socialmem_baseline.py','r42_parent_runner')
    selector=load(ROOT/'scripts/run_socialmem_structured_eval.py','r42_selection')
    records=selector.select_records(runner._read_jsonl(parent/'corpus.jsonl'))
    groups=runner.prepare_groups(records)
    if len(groups)!=7:raise ValueError('parent scope mismatch')
    old={read(p)['item_id']:read(p) for p in parent.glob('runs/*/questions/*.json')}
    if set(old)!={r['item_id'] for r in records} or len(old)!=57 or sum(bool(r['correct']) for r in old.values())!=16:
        raise ValueError('parent terminal cohort mismatch')
    required=['config.json','identity.json','corpus.jsonl','scope-manifest.json','summary.json']
    required+= [str(p.relative_to(parent)) for p in parent.glob('runs/*/questions/*.json')]
    for g in groups:
        root=parent/'runs'/g['group_id'];db=root/'frozen.db'
        if not db.is_file() or (Path(str(db)+'-wal').exists() and Path(str(db)+'-wal').stat().st_size):
            raise ValueError('parent database absent or active WAL')
        required.extend([str(db.relative_to(parent)),str((root/'scope.json').relative_to(parent))])
    return config,records,groups,old,{name:sha(parent/name) for name in required}

def prepare(work,parent=PARENT):
    work,parent=Path(work).resolve(),Path(parent).resolve()
    if work.exists():raise ValueError('new experiment directory required')
    config,records,groups,old,parent_files=parent_inputs(parent)
    work.mkdir(parents=True)
    for name in ('corpus.jsonl','scope-manifest.json','network-split.json'):shutil.copyfile(parent/name,work/name)
    for tree in ('python/starling','src','include','bindings','migrations','docs'):
        shutil.copytree(ROOT/tree,work/'frozen'/tree,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.so'))
    scripts=['run_socialmem_baseline.py','eval_ladder.py','eval_ladder_pipeline.py','eval_judge_audit.py','eval_longmemeval.py','eval_adapters.py']
    for name in scripts:
        p=work/'frozen/scripts'/name;p.parent.mkdir(exist_ok=True);shutil.copyfile(ROOT/'scripts'/name,p)
    core=list((ROOT/'build/python/starling').glob('_core*.so'))
    if len(core)!=1:raise ValueError('one built core required')
    frozen_core=work/'frozen/python/starling'/core[0].name;shutil.copyfile(core[0],frozen_core)
    candidate=candidate_config(config,sha(frozen_core));validate_config(config,candidate)
    write(work/'config.json',candidate)
    write(work/'identity.json',{'core_sha256':sha(frozen_core),'core_path':str(frozen_core),
        'config_sha256':sha(work/'config.json'),'corpus_sha256':sha(work/'corpus.jsonl'),
        'scope_manifest_sha256':sha(work/'scope-manifest.json'),'frozen_files':files_in(work/'frozen')})
    write(work/'sample.json',records);write(work/'groups.json',groups);write(work/'tasks.json',task_order(records))
    write(work/'parent-results.json',old);write(work/'parent-config.json',config)
    for g in groups:
        dest=work/'source-databases'/g['group_id'];dest.mkdir(parents=True)
        for name in ('frozen.db','scope.json'):shutil.copyfile(parent/'runs'/g['group_id']/name,dest/name)
    shutil.copyfile(__file__,work/'run_socialmem_r42.py')
    bound=sum(len({t['speaker'] for t in r['history']}) for r in records)+202
    if bound>BUDGET:raise ValueError('preflight request bound exceeds budget')
    write(work/'execution-plan.json',{'parent':str(parent),'parent_files':parent_files,'questions':57,'scopes':7,
        'arms':list(ARMS),'tasks':114,'http_budget':BUDGET,'request_bound':bound,'workers':4,
        'files':files_in(work)})
    return {'prepared':True,'request_bound':bound,'budget':BUDGET,'network_requests':0}

def check(work):
    work=Path(work);plan=read(work/'execution-plan.json')
    if (plan['questions'],plan['tasks'],plan['scopes'],plan['http_budget'],plan['arms'])!=(57,114,7,BUDGET,list(ARMS)):
        raise ValueError('execution scope drift')
    required={'config.json','identity.json','corpus.jsonl','scope-manifest.json','network-split.json',
              'sample.json','groups.json','tasks.json','parent-results.json','parent-config.json','run_socialmem_r42.py'}
    required.update('frozen/'+name for name in files_in(work/'frozen'))
    required.update('source-databases/'+name for name in files_in(work/'source-databases'))
    if set(plan['files'])!=required:raise ValueError('incomplete frozen manifest')
    for name,digest in plan['files'].items():
        if not (work/name).is_file() or sha(work/name)!=digest:raise ValueError('frozen input drift: '+name)
    for name,digest in plan['parent_files'].items():
        if sha(Path(plan['parent'])/name)!=digest:raise ValueError('parent drift: '+name)
    if sha(__file__)!=plan['files']['run_socialmem_r42.py']:raise ValueError('executing driver drift')
    validate_config(read(work/'parent-config.json'),read(work/'config.json'))
    if read(work/'tasks.json')!=task_order(read(work/'sample.json')):raise ValueError('task order drift')
    runner=load(work/'frozen/scripts/run_socialmem_baseline.py','r42_frozen_baseline')
    runner._verify_identity(work,read(work/'config.json'))
    return runner

def worker_modules(work):
    runner=load(work/'frozen/scripts/run_socialmem_baseline.py','r42_worker_baseline')
    cfg=read(work/'config.json');identity=read(work/'identity.json')
    return runner,cfg,runner._frozen_imports(work,cfg,identity)

def recall_group(work_text,group):
    work=Path(work_text);runner,cfg,modules=worker_modules(work)
    core,runtime,_,ladder,pipe,_=modules
    _,embedder,_,_=runner._make_native_adapters(core,cfg)
    ledger=runner.BudgetLedger(work/'request-ledger.sqlite',BUDGET)
    outcomes=[]
    with tempfile.TemporaryDirectory(prefix='r40-recall-') as tmp:
        db=Path(tmp)/'query.db';shutil.copyfile(work/'source-databases'/group['group_id']/'frozen.db',db)
        rt=runtime._build_local_store_sqlite_runtime(db);rt.start()
        for record in group['records']:
            key=record['item_id'];holders=runner.history_holders(group['history']);before=embedder.request_count
            reservation=ledger.reserve(key,'recall',len(holders))
            if reservation['state']!='reserved':raise ValueError('query budget exhausted')
            row={'item_id':key,'group_id':group['group_id'],'status':'query_failure','reservation':reservation}
            try:
                r=pipe.recall_observer_block(core,adapter=rt.adapter,embedder=embedder,index=core.SqliteBlobVectorIndex(),
                    question=record['question'],allowed_holders=holders,mode='hybrid',now_iso=cfg['query_time'],
                    k=cfg['k'],max_context_bytes=cfg['max_context_bytes'],include_unknown_time=cfg['include_unknown_time'],
                    source_strategy=cfg['source_strategy'],min_source_items=cfg['min_source_items'],
                    source_seed_k=cfg['source_seed_k'],source_seed_max_context_bytes=cfg['source_seed_max_context_bytes'],
                    source_dialogue_radius=cfg['source_dialogue_radius'])
                row['recall']=r
                if any(x.get('degraded_paths') for x in r['receipts']):raise ValueError('native retrieval degraded')
                # Native packet validation runs for both arms before any answer request.
                row['packet']=json.loads(core.grounded_memory_answer_packet(record['question'],json.dumps(r,ensure_ascii=False)))
                row['prompts']={a:runner.answer_prompt(core,ladder,record,r,{**cfg,
                    'answer_policy':'grounded_memory_v1' if a=='native_answer' else 'legacy'}) for a in ARMS}
                row['status']='ok'
            except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
            finally:
                row['embedding_requests']=int(embedder.request_count)-int(before)
                ledger.settle(reservation['id'],row['embedding_requests'])
            row['terminal']=True
            write(work/'recalls'/(item_id(key)+'.json'),row);outcomes.append({'item_id':key,'status':row['status']})
    return outcomes

def recall_all(work):
    work=Path(work).resolve();runner=check(work)
    with runner._work_lock(work):
        if (work/'recall-started.json').exists():raise ValueError('recall already started; retry prohibited')
        runner.BudgetLedger(work/'request-ledger.sqlite',BUDGET)
        write(work/'recall-started.json',{'execution_plan_sha256':sha(work/'execution-plan.json')})
        done=[]
        with concurrent.futures.ProcessPoolExecutor(max_workers=4,max_tasks_per_child=1) as pool:
            fs=[pool.submit(recall_group,str(work),g) for g in read(work/'groups.json')]
            for f in concurrent.futures.as_completed(fs):
                done+=f.result();write(work/'recall-progress.json',{'terminal':len(done),'status_counts':dict(Counter(r['status'] for r in done))})
                print(json.dumps({'recall_terminal':len(done)}),flush=True)
        rows=[read(p) for p in (work/'recalls').glob('*.json')]
        if len(rows)!=57 or {r['item_id'] for r in rows}!={r['item_id'] for r in read(work/'sample.json')}:raise ValueError('incomplete recall set')
        write(work/'recall-seal.json',{'files':files_in(work/'recalls'),'questions':57,
                                     'status_counts':dict(Counter(r['status'] for r in rows))})
    return read(work/'recall-seal.json')['status_counts']

def verify_recalls(work):
    seal=read(work/'recall-seal.json')
    if seal['questions']!=57 or seal['files']!=files_in(work/'recalls'):raise ValueError('frozen recall drift')
    if read(work/'recall-started.json')['execution_plan_sha256']!=sha(work/'execution-plan.json'):
        raise ValueError('recall fingerprint drift')

def verify_run_fingerprint(work):
    fp=read(work/'run-started.json')
    if fp!={'execution_plan_sha256':sha(work/'execution-plan.json'),'recall_seal_sha256':sha(work/'recall-seal.json')}:
        raise ValueError('run fingerprint drift')
    return fp

def verify_completion_seal(work):
    for name,digest in read(work/'completion-seal.json')['files'].items():
        if not (work/name).is_file() or sha(work/name)!=digest:raise ValueError('completion seal drift: '+name)

def parse_mc(longmem,text,options):
    try:return longmem._parse_option_index(text,len(options))
    except ValueError:return None

def perform(record,prompt,runner,audit,longmem,answer_llm,judge_llm):
    row={'item_id':record['item_id'],'prompt':prompt,'correct':False,'status':'answer_failure'}
    started=time.perf_counter()
    try:
        payload,text,error=runner.response_text(answer_llm.extract(prompt,''),'answer');row['answer']=payload
        if error:row['error']=error
        elif record['answer_format']=='multiple_choice':
            pred=parse_mc(longmem,text,record['options'])
            if pred is None:row.update(status='invalid_answer',error='invalid option')
            else:row.update(status='ok',prediction=pred,correct=pred==int(record['answer']))
        else:
            row['status']='judge_failure';row['judge_prompt']=audit._judge_prompt(record['question'],str(record['answer']),text)
            payload,verdict,error=runner.response_text(judge_llm.extract(row['judge_prompt'],''),'judge');row['judge']=payload
            if error:row['error']=error
            else:row.update(status='ok',correct=bool(audit._parse_judge_verdict(verdict)))
    except Exception as exc:row.update(error=f'{type(exc).__name__}: {exc}',budget_unknown=True)
    row.update(terminal=True,elapsed_seconds=time.perf_counter()-started,
        native_attempt_count=sum(runner._response_attempts(row.get(s)) for s in ('answer','judge')))
    return row

def answer_item(work_text,record,tasks):
    work=Path(work_text);runner,cfg,modules=worker_modules(work);core,_,audit,_,_,longmem=modules
    _,_,answer,judge=runner._make_native_adapters(core,cfg)
    ledger=runner.BudgetLedger(work/'request-ledger.sqlite',BUDGET)
    context=read(work/'recalls'/(item_id(record['item_id'])+'.json'))
    fingerprint={'execution_plan_sha256':sha(work/'execution-plan.json'),'recall_seal_sha256':sha(work/'recall-seal.json')}
    done=[]
    for t in tasks:
        tid=task_id(t);bound=1+int(record['answer_format']!='multiple_choice')
        if (work/'started'/(tid+'.json')).exists() or (work/'receipts'/(tid+'.json')).exists():raise ValueError('task already started')
        reservation=ledger.reserve(tid,'answer',bound)
        if reservation['state']!='reserved':raise ValueError('answer budget exhausted')
        start={'task':t,'fingerprint':fingerprint,'reservation':reservation}
        write(work/'started'/(tid+'.json'),start)
        try:
            if context['status']!='ok':
                row={'item_id':record['item_id'],'status':'query_failure','correct':False,'terminal':True,'native_attempt_count':0}
            else:row=perform(record,context['prompts'][t['arm']],runner,audit,longmem,answer,judge)
            row.update(start,arm=t['arm'],recall_sha256=sha(work/'recalls'/(item_id(record['item_id'])+'.json')))
            if row.get('budget_unknown'):ledger.charge_upper(reservation['id'])
            else:ledger.settle(reservation['id'],row['native_attempt_count'])
            write(work/'receipts'/(tid+'.json'),row);done.append({'item_id':record['item_id'],'arm':t['arm'],'status':row['status']})
        finally:ledger.charge_upper(reservation['id'])
    return done

def run(work):
    work=Path(work).resolve();runner=check(work);verify_recalls(work)
    with runner._work_lock(work):
        if (work/'run-started.json').exists():raise ValueError('already started; retry prohibited')
        write(work/'run-started.json',{'execution_plan_sha256':sha(work/'execution-plan.json'),'recall_seal_sha256':sha(work/'recall-seal.json')})
        done=[];tasks=read(work/'tasks.json')
        with concurrent.futures.ProcessPoolExecutor(max_workers=4,max_tasks_per_child=1) as pool:
            fs=[pool.submit(answer_item,str(work),r,[t for t in tasks if t['item_id']==r['item_id']]) for r in read(work/'sample.json')]
            for f in concurrent.futures.as_completed(fs):
                done+=f.result();progress={'terminal_tasks':len(done),'total_tasks':114,'status_counts':dict(Counter(r['status'] for r in done))}
                write(work/'technical-progress.json',progress);print(json.dumps(progress),flush=True)
        write(work/'run-completion.json',verify_terminal(work))
    return read(work/'run-completion.json')

def verify_terminal(work):
    work=Path(work);runner=check(work);verify_recalls(work)
    if (work/'completion-seal.json').exists():verify_completion_seal(work)
    records={r['item_id']:r for r in read(work/'sample.json')};tasks={task_id(t):t for t in read(work/'tasks.json')}
    rows={p.stem:read(p) for p in (work/'receipts').glob('*.json')}
    starts={p.stem:read(p) for p in (work/'started').glob('*.json')}
    if set(rows)!=set(tasks) or set(starts)!=set(tasks):raise ValueError('terminal task mismatch')
    audit=load(work/'frozen/scripts/eval_judge_audit.py','r42_verify_judge')
    longmem=load(work/'frozen/scripts/eval_longmemeval.py','r42_verify_mc')
    fp=verify_run_fingerprint(work);ids=set();attempts=0;expected_cost=0;stages=Counter();tokens=Counter()
    with sqlite3.connect(f'file:{work / "request-ledger.sqlite"}?mode=ro',uri=True) as conn:
        reservations={r[0]:r[1:] for r in conn.execute('SELECT id,scope,stage,upper_bound,actual,state FROM reservations')}
    def verify_reservation(row,scope,stage,bound,count):
        nonlocal expected_cost
        rid=row['reservation']['id']
        if rid in ids:raise ValueError('duplicate reservation')
        ids.add(rid)
        unknown=bool(row.get('budget_unknown'))
        expected=(scope,stage,bound,None if unknown else count,'charged_upper' if unknown else 'settled')
        if reservations.get(rid)!=expected:raise ValueError('reservation mismatch')
        expected_cost+=bound if unknown else count
    for key,record in records.items():
        r=read(work/'recalls'/(item_id(key)+'.json'))
        count=r['embedding_requests'];verify_reservation(r,key,'recall',len({t['speaker'] for t in record['history']}),count)
        stages['query_embedding']+=count
    for tid,row in rows.items():
        task=tasks[tid];record=records[task['item_id']]
        ctxfile=work/'recalls'/(item_id(record['item_id'])+'.json');context=read(ctxfile)
        if row.get('task')!=task or row.get('fingerprint')!=fp or row.get('recall_sha256')!=sha(ctxfile) or starts[tid]!={k:row[k] for k in ('task','fingerprint','reservation')}:
            raise ValueError('task or context identity drift')
        if row['item_id']!=record['item_id'] or row['arm']!=task['arm'] or not row['terminal']:raise ValueError('terminal identity mismatch')
        count=0
        for stage in ('answer','judge'):
            p=row.get(stage)
            if not p:continue
            native=p['response'];n=native['attempt_count']
            if n not in (0,1) or n!=len(native['http_attempts']) or p['raw_xml']!=native['raw_response'] or p['raw_completion']!=native['raw_completion']:
                raise ValueError('native response drift')
            count+=n;stages[stage]+=n;tokens[row['arm']]+=native.get('total_tokens',0)
        if count!=row['native_attempt_count']:raise ValueError('attempt count mismatch')
        verify_reservation(row,tid,'answer',1+int(record['answer_format']!='multiple_choice'),count)
        attempts+=count
        if context['status']=='ok' and row.get('prompt')!=context['prompts'][row['arm']]:raise ValueError('prompt drift')
        if context['status']!='ok':
            if row['status']!='query_failure' or count or row['correct']:raise ValueError('query failure scored')
            continue
        def successful(stage):
            p=row.get(stage,{})
            return p.get('response',{}).get('ok') is True and not p['response'].get('error') and bool(p.get('raw_xml','').strip())
        expected_correct=False
        if successful('answer'):
            answer_text=row['answer']['raw_xml'].strip()
            if record['answer_format']=='multiple_choice':
                if 'judge' in row:raise ValueError('MC unexpected judge')
                pred=parse_mc(longmem,answer_text,record['options'])
                expected_status='ok' if pred is not None else 'invalid_answer';expected_correct=pred==int(record['answer'])
            else:
                if row.get('judge_prompt')!=audit._judge_prompt(record['question'],str(record['answer']),answer_text):raise ValueError('judge prompt drift')
                expected_status='ok' if successful('judge') else 'judge_failure'
                if expected_status=='ok':expected_correct=bool(audit._parse_judge_verdict(row['judge']['raw_xml'].strip()))
        else:expected_status='answer_failure'
        if row['status']!=expected_status or row['correct']!=expected_correct:raise ValueError('score differs from frozen protocol')
    if ids!=set(reservations) or expected_cost>BUDGET:raise ValueError('ledger task coverage mismatch')
    snap=runner.BudgetLedger(work/'request-ledger.sqlite',BUDGET).snapshot()
    if snap['reserved'] or snap['committed']!=expected_cost:raise ValueError('unsettled ledger')
    return {'verified':True,'tasks':114,'recalls':57,'requests_by_stage':dict(stages),
            'actual_requests':sum(stages.values()),'ledger':snap,'observed_answer_judge_tokens':dict(tokens)}

def analyze(work):
    work=Path(work)
    if (work/'completion-seal.json').exists():raise ValueError('analysis already sealed')
    audit=verify_terminal(work)
    records=read(work/'sample.json');rows=[read(p) for p in (work/'receipts').glob('*.json')]
    result=analyze_rows(records,rows);result['request_audit']=audit
    old=read(work/'parent-results.json');result['vs_r35']={}
    for a in ARMS:
        by={r['item_id']:r for r in rows if r['arm']==a};normal=[r for r in records if old[r['item_id']]['status']==by[r['item_id']]['status']=='ok']
        result['vs_r35'][a]={'all':paired(records,old,by),'common_normal':paired(normal,old,by)}
    cov=[];scopes={}
    for g in read(work/'groups.json'):
        scopes[g['group_id']]=read(work/'source-databases'/g['group_id']/'scope.json').get('scope_state','unknown')
    for r in records:
        ctx=read(work/'recalls'/(item_id(r['item_id'])+'.json'))
        cov.append({'item_id':r['item_id'],'query_type':r['query_type'],'format':r['answer_format'],
            'scope_state':scopes[ctx['group_id']], 'r35':anchor_coverage(r,old[r['item_id']]['recall']),
            'r40':anchor_coverage(r,ctx.get('recall',{}))})
    result['coverage']={name:{'total':sum(r[name]['total'] for r in cov),'source_hits':sum(r[name]['source_hits'] for r in cov)} for name in ('r35','r40')}
    result['coverage_by_query_type']={q:{name:{'total':sum(r[name]['total'] for r in cov if r['query_type']==q),
         'source_hits':sum(r[name]['source_hits'] for r in cov if r['query_type']==q)} for name in ('r35','r40')} for q in sorted({r['query_type'] for r in cov})}
    by={(r['item_id'],r['arm']):r for r in rows}
    result['by_scope_state']={s:{a:{'n':sum(r['scope_state']==s for r in cov),
        'correct':sum(by[r['item_id'],a]['correct'] for r in cov if r['scope_state']==s)} for a in ARMS} for s in sorted(set(scopes.values()))}
    result['limitations']=['57题开发诊断，不是全量成绩','父为35/36完整holder，不能晋升生产',
        'R3.5比较包含服务时间与查询embedding变动','区间不包含生成和裁判重复运行方差','公开锚点不是完整答案要点']
    write(work/'analysis.json',result);write(work/'coverage-details.json',cov)
    write(work/'completion-seal.json',{'files':{k:v for k,v in files_in(work).items() if k!='completion-seal.json' and not k.endswith(('.lock','-wal','-shm'))},'tasks':114,'promoted':False})
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('prepare','check','recall','run','analyze','verify'))
    p.add_argument('--work',type=Path,required=True);p.add_argument('--parent',type=Path,default=PARENT)
    args=p.parse_args()
    if args.mode=='prepare':result=prepare(args.work,args.parent)
    elif args.mode=='check':check(args.work);result={'verified':True,'network_requests':0}
    elif args.mode=='recall':result=recall_all(args.work)
    elif args.mode=='run':result=run(args.work)
    elif args.mode=='analyze':result=analyze(args.work)
    else:result=verify_terminal(args.work)
    print(json.dumps(result,ensure_ascii=False,indent=2))
