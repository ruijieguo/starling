#!/usr/bin/env python3
"""固定来源、同期四组合回答消融。提示逻辑由冻结C++核心提供。"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_socialmem_k30_controlled as base

ROOT=Path(__file__).resolve().parents[1]
PARENT_SEAL='f7316dea33dcf46fb135f898eb373d79be60ec2229741c9c31ca840c14faebef'
DIALOGUE_SEAL='a8fe8bebab8726ef33da4219001ecb0d6917af5376813425d32bf85e2a79b46d'
CORE_NAME='python/starling/_core.cpython-314-darwin.so'
CHANGED={CORE_NAME,'include/starling/retrieval/evidence_answer.hpp','src/retrieval/evidence_answer.cpp',
         'bindings/python/bind_05_retrieval.cpp','tests/cpp/test_evidence_answer.cpp'}
ARMS=('source_grounded','json_grounded','source_synthesis','json_synthesis')
SCRIPTS=('run_socialmem_answer_ablation.py','analyze_socialmem_answer_ablation.py','run_socialmem_k30_controlled.py')
sha,read,write=base.sha,base.read,base.write

def sample_key(record):return hashlib.sha256(('answer-ablation-v1|'+record['item_id']).encode()).hexdigest()

def select_sample(records):
    if len({r['item_id'] for r in records})!=len(records):raise ValueError('duplicate corpus items')
    networks=defaultdict(list)
    for record in records:
        if record['answer_format']!='multiple_choice':networks[str(record['source']['network_id'])].append(record)
    if len(networks)!=33 or any(len(rows)<3 for rows in networks.values()):raise ValueError('33 networks with at least 3 free questions required')
    return sorted([r for rows in networks.values() for r in sorted(rows,key=sample_key)[:3]],key=sample_key)

def task_order(records):
    tasks=[]
    for i,record in enumerate(sorted(records,key=sample_key)):
        for pos in range(4):tasks.append({'item_id':record['item_id'],'arm':ARMS[(i+pos)%4],'position':pos,'question_order':i})
    return tasks

def task_id(task):return hashlib.sha256((task['item_id']+'|'+task['arm']).encode()).hexdigest()

def perform_answer(record,prompt,runner,audit,answer_llm,judge_llm):
    started=time.perf_counter()
    row={'item_id':record['item_id'],'prompt':prompt,'correct':False,'status':'answer_failure','stages':{}}
    answer_ok=False;tick=time.perf_counter()
    try:
        payload,answer,error=runner.response_text(answer_llm.extract(prompt,''),'answer')
        row['answer']=payload
        if error:row['error']=error
        else:answer_ok=True
    except Exception as exc:
        row.update(error=f'{type(exc).__name__}: {exc}',budget_unknown=True)
    row['stages']['answer']={'seconds':time.perf_counter()-tick}
    if answer_ok:
        row['status']='judge_failure';tick=time.perf_counter()
        try:
            row['judge_prompt']=audit._judge_prompt(str(record['question']),str(record['answer']),answer)
            payload,verdict,error=runner.response_text(judge_llm.extract(row['judge_prompt'],''),'judge')
            row['judge']=payload
            if error:row['error']=error
            else:row.update(status='ok',correct=bool(audit._parse_judge_verdict(verdict)))
        except Exception as exc:
            row.update(error=f'{type(exc).__name__}: {exc}',budget_unknown=True)
        row['stages']['judge']={'seconds':time.perf_counter()-tick}
    row.update(terminal=True,elapsed_seconds=time.perf_counter()-started,
               native_attempt_count=sum(runner._response_attempts(row.get(s)) for s in ('answer','judge')))
    return row

def verify_score(record,row,audit):
    for stage in ('answer','judge'):
        payload=row.get(stage)
        if not payload:continue
        response=payload['response']
        if (payload.get('raw_completion')!=response.get('raw_completion') or
            payload.get('raw_xml')!=response.get('raw_response')):
            raise ValueError('completion text differs from native receipt')
        attempts=response.get('attempt_count')
        successful=response.get('ok') is True and not response.get('error') and bool(payload.get('raw_xml','').strip())
        if (type(attempts) is not int or attempts not in (0,1) or attempts!=len(response.get('http_attempts',[]))
            or (successful and attempts!=1)):
            raise ValueError('successful provider stage requires one attempt; failures may precede HTTP')
    answer=row.get('answer',{}).get('raw_xml','').strip()
    def success(stage):
        payload=row.get(stage,{});raw=payload.get('response',{})
        return raw.get('ok') is True and not raw.get('error') and bool(payload.get('raw_xml','').strip())
    if not success('answer'):
        expected_status,expected_correct='answer_failure',False
        if 'judge' in row or 'judge_prompt' in row:raise ValueError('judge executed after failed answer')
        if 'answer' not in row and not row.get('budget_unknown'):raise ValueError('missing answer without unknown request accounting')
    else:
        if row.get('judge_prompt')!=audit._judge_prompt(str(record['question']),str(record['answer']),answer):
            raise ValueError('judge prompt or answer changed')
        if success('judge'):expected_status,expected_correct='ok',bool(audit._parse_judge_verdict(row['judge']['raw_xml'].strip()))
        else:
            expected_status,expected_correct='judge_failure',False
            if 'judge' not in row and not row.get('budget_unknown'):raise ValueError('missing judge without unknown request accounting')
    if row['status']!=expected_status or row['correct']!=expected_correct:
        raise ValueError('status or score differs from native receipts and frozen judge')

def execute_task(work,task,record,prompt,runner,audit,answer,judge,ledger,fingerprint):
    work=Path(work);key=task_id(task)
    started=work/'started'/f'{key}.json';receipt=work/'receipts'/f'{key}.json'
    if (work/'completion-seal.json').exists() or started.exists() or receipt.exists():raise ValueError('sealed or already started task; retry prohibited')
    reservation=ledger.reserve(key,'answer_ablation',2)
    if reservation['state']!='reserved':raise ValueError('HTTP budget exhausted before request')
    started.parent.mkdir(exist_ok=True);receipt.parent.mkdir(exist_ok=True)
    try:
        if not runner._exclusive_started(started,{'task':task,'fingerprint':fingerprint,'reservation':reservation}):
            raise ValueError('task already started; retry prohibited')
        row=perform_answer(record,prompt,runner,audit,answer,judge)
        row.update(arm=task['arm'],task=task,fingerprint=fingerprint,reservation=reservation)
        if row.get('budget_unknown'):
            ledger.charge_upper(reservation['id']);row['charged_requests']=2
        else:
            ledger.settle(reservation['id'],row['native_attempt_count']);row['charged_requests']=row['native_attempt_count']
        runner._json_write(receipt,row)
        return {'item_id':record['item_id'],'arm':task['arm'],'status':row['status']}
    finally:ledger.charge_upper(reservation['id'])

def _archive(folder,digest):
    folder=Path(folder)
    if sha(folder/'completion-seal.json')!=digest:raise ValueError('parent seal changed')
    manifest=read(folder/'completion-seal.json');base.verify_files(folder,manifest['files'])
    return manifest

def _sample_record(r):
    return {k:r[k] for k in ('item_id','question','answer','answer_format','query_type','source')}

def _expected_packet(question,block):
    decoder=json.JSONDecoder();sources=[]
    for line in block.split('\n'):
        if not line.strip():continue
        if not line.startswith('[SOURCE] '):raise ValueError('invalid SOURCE prefix')
        meta,end=decoder.raw_decode(line[9:]);tail=line[9+end:].lstrip()
        if not tail.startswith('text=') or {'text','source_id'} & meta.keys():raise ValueError('invalid source metadata')
        sources.append({**meta,'source_id':len(sources)+1,'text':decoder.decode(tail[5:])})
    return {'schema_version':'synthesis_v1','question':question,'sources':sources,'semantic_verified':False}

def prepare(work,parent,dialogue):
    work,parent,dialogue=map(lambda p:Path(p).resolve(),(work,parent,dialogue))
    _archive(parent,PARENT_SEAL);_archive(dialogue,DIALOGUE_SEAL)
    if work.exists():raise ValueError('prepare requires a new directory')
    corpus=[json.loads(line) for line in (parent/'corpus.jsonl').read_text().splitlines() if line.strip()]
    selected=select_sample(base.select_records(corpus,read(parent/'network-split.json')))
    records=[_sample_record(r) for r in selected];work.mkdir(parents=True)
    original=read(parent/'identity.json')
    for name,digest in original['frozen_files'].items():
        source=ROOT/'build'/name if name==CORE_NAME else ROOT/name
        if name not in CHANGED:
            if source.is_file() and sha(source)!=digest:raise ValueError('unreviewed workspace change: '+name)
            source=parent/'frozen'/name
        dest=work/'frozen'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
    for name in SCRIPTS:shutil.copyfile(ROOT/'scripts'/name,work/name)
    for name in ('scope-manifest.json','network-split.json'):shutil.copyfile(parent/name,work/name)
    (work/'corpus.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records))
    write(work/'sample.json',records);write(work/'tasks.json',task_order(records))
    config={**read(parent/'config.json'),'core_sha256':sha(work/'frozen'/CORE_NAME),'http_budget':792}
    write(work/'config.json',config)
    identity={**original,'core_path':str(work/'frozen'/CORE_NAME),'core_sha256':config['core_sha256'],
      'corpus_sha256':sha(work/'corpus.jsonl'),'config_sha256':sha(work/'config.json'),
      'frozen_files':{name:sha(work/'frozen'/name) for name in original['frozen_files']}}
    write(work/'identity.json',identity)
    runner=base.load_runner(work);runner._verify_identity(work,config)
    core,*_=runner._frozen_imports(work,config,identity)
    old={read(p)['item_id']:read(p) for p in dialogue.glob('runs/*/questions/*.json')}
    prior={read(p)['item_id']:read(p) for p in parent.glob('runs/*/questions/*.json')}
    inputs={};prompts={}
    for r in records:
        key=r['item_id'];block=prior[key]['recall']['block']
        if block!=old[key]['recall']['block']:raise ValueError('historical source mismatch')
        inputs[key]={'block':block,'source_refs':prior[key]['recall']['source_refs']}
        prompts[key]={a:core.source_answer_ablation_prompt(r['question'],block,*a.split('_',1)) for a in ARMS}
        if prompts[key]['source_grounded']!=old[key]['prompt'] or prompts[key]['json_synthesis']!=prior[key]['prompt']:
            raise ValueError('historical diagonal prompt changed: '+key)
        expected=_expected_packet(r['question'],block)
        packet=json.loads(prompts[key]['json_synthesis'].rsplit('\n',1)[1])
        grounded=prompts[key]['json_grounded'].split('Recalled memories:\n',1)[1].rsplit('\n\nQuestion: ',1)[0]
        if packet!=expected or json.loads(grounded)!=expected:raise ValueError('lossy input packet')
        if block and block not in prompts[key]['source_synthesis']:raise ValueError('source input dropped')
    write(work/'inputs.json',inputs);write(work/'prompts.json',prompts)
    for source in [ROOT/'tests/python/test_answer_ablation.py',*sorted((ROOT/'docs').rglob('*.md'))]:
        target=work/'execution-sources'/source.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    pre={'verified':True,'questions':99,'networks':33,'historical_prompt_matches':198,'lossless_json_prompts':198,
         'requests':0,'core_sha256':config['core_sha256']}
    write(work/'native-preflight.json',pre)
    plan={'parent':str(parent),'dialogue':str(dialogue),'parent_seal':PARENT_SEAL,'dialogue_seal':DIALOGUE_SEAL,
      'questions':99,'networks':33,'arms':list(ARMS),'tasks':396,'http_budget':792,'workers':4,
      'sampling':'SHA256(answer-ablation-v1|item_id), 3 per development network',
      'files':{str(p.relative_to(work)):sha(p) for p in sorted(work.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}}
    write(work/'execution-plan.json',plan)

def verify_executor(work):
    # 不使用被核验模块提供的read/sha，避免实际导入副本逃逸冻结校验。
    plan=json.loads((Path(work)/'execution-plan.json').read_text())
    for path,name in [(Path(__file__),'run_socialmem_answer_ablation.py'),
                      (Path(base.__file__),'run_socialmem_k30_controlled.py')]:
        if hashlib.sha256(path.read_bytes()).hexdigest()!=plan['files'].get(name):
            raise ValueError('executing dependency differs from frozen file: '+name)

def check(work):
    verify_executor(work)
    work=Path(work).resolve();plan=read(work/'execution-plan.json')
    if (plan['parent_seal'],plan['dialogue_seal'])!=(PARENT_SEAL,DIALOGUE_SEAL):raise ValueError('unregistered parents')
    if (plan['questions'],plan['networks'],plan['tasks'],plan['http_budget'],plan['workers'],plan['arms'])!=(99,33,396,792,4,list(ARMS)):
        raise ValueError('registered scope changed')
    base.verify_files(work,plan['files'])
    for name in SCRIPTS:
        if plan['files'].get(name)!=sha(work/name):raise ValueError('unfrozen driver or analyzer')
    if sha(__file__)!=plan['files']['run_socialmem_answer_ablation.py']:raise ValueError('executing driver changed')
    parent,dialogue=Path(plan['parent']),Path(plan['dialogue'])
    _archive(parent,PARENT_SEAL);_archive(dialogue,DIALOGUE_SEAL)
    original=read(parent/'identity.json');identity=read(work/'identity.json');config=read(work/'config.json')
    if config!={**read(parent/'config.json'),'http_budget':792,'core_sha256':identity['core_sha256']}:
        raise ValueError('unreviewed configuration change')
    before,after=original['frozen_files'],identity['frozen_files']
    if before.keys()!=after.keys() or any(before[n]!=after[n] for n in before if n not in CHANGED):raise ValueError('unreviewed core or scoring change')
    for name,digest in after.items():
        if plan['files'].get('frozen/'+name)!=digest:raise ValueError('identity not covered by execution manifest')
    corpus=[json.loads(line) for line in (parent/'corpus.jsonl').read_text().splitlines() if line.strip()]
    selected=[_sample_record(r) for r in select_sample(base.select_records(corpus,read(parent/'network-split.json')))]
    if selected!=read(work/'sample.json') or selected!=[json.loads(s) for s in (work/'corpus.jsonl').read_text().splitlines()]:
        raise ValueError('sample differs from registered selection')
    if task_order(selected)!=read(work/'tasks.json'):raise ValueError('arm schedule changed')
    required={'sample.json','tasks.json','inputs.json','prompts.json','native-preflight.json','identity.json','config.json','corpus.jsonl','scope-manifest.json','network-split.json'}
    if not required<=plan['files'].keys():raise ValueError('incomplete execution freeze')
    runner=base.load_runner(work);runner._verify_identity(work,config)
    return runner

def _run_question(work_str,record,tasks):
    work=Path(work_str);verify_executor(work)
    runner=base.load_runner(work);config=read(work/'config.json');identity=read(work/'identity.json')
    core,_,audit,*_=runner._frozen_imports(work,config,identity)
    _,_,answer,judge=runner._make_native_adapters(core,config)
    ledger=runner.BudgetLedger(work/'request-ledger.sqlite',792)
    prompts=read(work/'prompts.json')[record['item_id']]
    fingerprint={'execution_plan_sha256':sha(work/'execution-plan.json')}
    return [execute_task(work,task,record,prompts[task['arm']],runner,audit,answer,judge,ledger,fingerprint) for task in tasks]

def run(work):
    work=Path(work).resolve()
    if (work/'completion-seal.json').exists():raise ValueError('sealed experiment cannot run')
    runner=check(work);config=read(work/'config.json')
    with runner._work_lock(work):
        if (work/'run-started.json').exists():raise ValueError('experiment already started; rerun prohibited')
        if (work/'request-ledger.sqlite').exists() or any((work/'receipts').glob('*.json')):raise ValueError('nonempty execution state')
        runner.BudgetLedger(work/'request-ledger.sqlite',792)
        fingerprint={'execution_plan_sha256':sha(work/'execution-plan.json')}
        if not runner._exclusive_started(work/'run-started.json',fingerprint):raise ValueError('already started')
        records=read(work/'sample.json');tasks=read(work/'tasks.json');finished=[]
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
            futures=[executor.submit(_run_question,str(work),r,[t for t in tasks if t['item_id']==r['item_id']]) for r in records]
            for future in concurrent.futures.as_completed(futures):
                finished.extend(future.result())
                progress={'terminal_tasks':len(finished),'total_tasks':396,'status_counts':dict(Counter(r['status'] for r in finished))}
                runner._json_write(work/'technical-progress.json',progress)
                print(json.dumps(progress),flush=True)
        audit=verify_terminal(work)
        write(work/'run-completion.json',{'state':'complete','questions':99,'tasks':396,'audit':audit})
        return audit

def verify_terminal(work):
    work=Path(work);tasks=read(work/'tasks.json');prompts=read(work/'prompts.json')
    expected={task_id(t):t for t in tasks};fingerprint={'execution_plan_sha256':sha(work/'execution-plan.json')}
    if read(work/'run-started.json')!=fingerprint:raise ValueError('run fingerprint changed')
    paths=list((work/'receipts').glob('*.json'));starts=list((work/'started').glob('*.json'))
    if len(paths)!=396 or {p.stem for p in paths}!=set(expected) or {p.stem for p in starts}!=set(expected):
        raise ValueError('incomplete terminal set')
    conn=sqlite3.connect(f'file:{work / "request-ledger.sqlite"}?mode=ro',uri=True)
    try:ledger={r[0]:r for r in conn.execute('SELECT id,scope,stage,upper_bound,actual,state FROM reservations')}
    finally:conn.close()
    if len(ledger)!=396:raise ValueError('reservation set differs')
    spec=importlib.util.spec_from_file_location('ablation_frozen_judge',work/'frozen/scripts/eval_judge_audit.py')
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    records={r['item_id']:r for r in read(work/'sample.json')}
    actual=charged=unknown=0;stages=Counter();states=Counter();tokens=0;ids=set()
    for path in paths:
        row=read(path);task=expected[path.stem];start=read(work/'started'/path.name)
        if (row.get('task')!=task or row.get('fingerprint')!=fingerprint or start!={'task':task,'fingerprint':fingerprint,'reservation':row.get('reservation')}
            or row.get('item_id')!=task['item_id'] or row.get('arm')!=task['arm'] or row.get('terminal') is not True
            or row.get('prompt')!=prompts[task['item_id']][task['arm']] or type(row.get('correct')) is not bool
            or row.get('status') not in ('ok','answer_failure','judge_failure') or (row['status']!='ok' and row['correct'])):
            raise ValueError('receipt identity, prompt or terminal mismatch')
        if any(k in row for k in ('evidence','embedding','recall')):raise ValueError('unexpected retrieval/planning stage')
        verify_score(records[task['item_id']],row,audit)
        count=0
        for stage in ('answer','judge'):
            response=row.get(stage,{}).get('response',{});n=response.get('attempt_count',0)
            if type(n) is not int or n not in (0,1) or n!=len(response.get('http_attempts',[])):raise ValueError('request count/attempt envelope mismatch')
            count+=n;stages[stage]+=n;tokens+=response.get('total_tokens',0)
        if row.get('native_attempt_count')!=count:raise ValueError('native request counter differs')
        rid=row['reservation']['id'];ids.add(rid);reservation=ledger.get(rid)
        is_unknown=bool(row.get('budget_unknown'));cost=2 if is_unknown else count
        if (reservation is None or reservation[1:4]!=(path.stem,'answer_ablation',2)
            or reservation[5]!=('charged_upper' if is_unknown else 'settled')
            or reservation[4]!=(None if is_unknown else count) or row.get('charged_requests')!=cost):
            raise ValueError('ledger settlement differs from receipt')
        actual+=count;charged+=cost;unknown+=is_unknown;states[row['status']]+=1
    if ids!=set(ledger) or not actual<=charged<=792:raise ValueError('request budget or reservation identity mismatch')
    return {'verified':True,'questions':99,'tasks':396,'actual_requests':actual,'charged_requests':charged,
      'unknown_budget_receipts':unknown,'requests_by_stage':dict(stages),'status_counts':dict(states),
      'observed_total_tokens':tokens,'http_budget':792}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('prepare','check','run'))
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--parent',type=Path,default=ROOT/'build/socialmem_20260918_synthesis_answer')
    p.add_argument('--dialogue',type=Path,default=ROOT/'build/socialmem_20260918_dialogue_expansion')
    args=p.parse_args()
    if args.mode=='prepare':prepare(args.work,args.parent,args.dialogue)
    if args.mode=='run':result=run(args.work)
    else:check(args.work);result={'verified':True,'questions':99,'tasks':396,'http_limit':792,'requests':0}
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
